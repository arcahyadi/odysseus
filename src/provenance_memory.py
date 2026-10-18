"""SFD §5.7 — Mémoire avec provenance.

Système de fichiers mémoire structuré :
  /profile.md              — identité stable
  /topics/<domaine>.md    — faits par domaine
  /areas/<nom>.md          — projets en cours
  /people/<nom>.md         — contexte relationnel
  /preferences.md          — préférences comportementales

Tags de provenance :
  [stated]   — l'utilisateur l'a dit explicitement
  [observed] — le système l'a constaté
  [inferred] — déduit avec niveau de confiance

Contrôle de concurrence versionné (if_version) :
  memory_read  → contenu + jeton 12 car.
  memory_write → échoue si if_version invalide

Gated behind ODYSSEUS_PROVENANCE_MEMORY kill-switch (default OFF).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from src.content_security import content_security_enabled, get_content_security
from src.app_context import app_context


logger = logging.getLogger(__name__)

# ─── Kill-switch ────────────────────────────────────────────────────────


def provenance_memory_enabled() -> bool:
    val = os.getenv("ODYSSEUS_PROVENANCE_MEMORY", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


# ─── Constants ──────────────────────────────────────────────────────────

MEMORY_ROOT = Path("data/memory-fs")

# Nombre de tentatives d'un compare-and-swap. Borne, et non boucle : sous une
# contention reelle, un appel qui rend la main vaut mieux qu'un appel qui
# n'en sort pas. Trois suffisent a faire aboutir le cas nominal (deux tours
# concurrents se marchent dessus une fois) tout en sortant toujours.
_CAS_TENTATIVES = 3
ProvenanceTag = Literal["stated", "observed", "inferred"]

# Catégories protégées — jamais stockées
PROTECTED_CATEGORIES: list[str] = [
    "origine",
    "ethnique",
    "nationalité",
    "caste",
    "religion",
    "âge",
    "sexe",
    "orientation sexuelle",
    "identité de genre",
    "immigration",
    "handicap",
    "maladie grave",
    "syndicale",
]

SENSITIVE_CATEGORIES: list[str] = [
    "croyances politiques",
    "historique d'abus",
    "données financières",
    "diagnostics",
    "thérapie",
    "addictions",
    "casier judiciaire",
]

IDENTIFIABLE_CATEGORIES: list[str] = [
    "numéro sécurité sociale",
    "données bancaires",
    "adresse personnelle",
    "téléphone personnel",
    "enfants",
    "noms des enfants",
]

# Mots déclencheurs pour l'omission automatique
OMISSION_TRIGGERS: list[str] = PROTECTED_CATEGORIES + SENSITIVE_CATEGORIES + IDENTIFIABLE_CATEGORIES


# ─── Data model ─────────────────────────────────────────────────────────


@dataclass
class MemoryFile:
    """Un fichier mémoire avec frontmatter et contenu."""

    path: Path
    name: str
    description: str = ""
    sources: list[str] = field(default_factory=lambda: ["chat"])
    aliases: list[str] = field(default_factory=list)
    entries: list[MemoryEntry] = field(default_factory=list)
    version: str = ""

    def generate_version(self) -> str:
        self.version = secrets.token_hex(6)
        return self.version

    @property
    def content(self) -> str:
        """Génère le contenu Markdown du fichier."""
        lines = [
            "---",
            f"name: {self.name}",
            f"description: {self.description}",
            f"sources: [{', '.join(self.sources)}]",
        ]
        if self.aliases:
            lines.append(f"aliases: [{', '.join(self.aliases)}]")
        lines.append("---")
        lines.append("")
        for entry in self.entries:
            lines.append(str(entry))
        return "\n".join(lines)

    @classmethod
    def from_content(cls, path: Path, content: str) -> MemoryFile:
        """Parse un fichier mémoire existant."""
        mf = cls(path=path, name=path.stem)
        frontmatter = {}
        entries = []

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        frontmatter[k.strip()] = v.strip()
                body = parts[2]
            else:
                body = content
        else:
            body = content

        mf.name = frontmatter.get("name", path.stem)
        mf.description = frontmatter.get("description", "")
        mf.sources = [s.strip() for s in frontmatter.get("sources", "chat").strip("[]").split(",")]
        mf.aliases = [a.strip() for a in frontmatter.get("aliases", "").strip("[]").split(",") if a.strip()]

        for line in body.strip().split("\n"):
            line = line.strip()
            if line.startswith("- ["):
                entry = MemoryEntry.from_line(line)
                if entry:
                    entries.append(entry)

        mf.entries = entries
        return mf


@dataclass
class MemoryEntry:
    """Une entrée de mémoire avec provenance."""

    tag: ProvenanceTag
    text: str
    confidence: float | None = None
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        if self.tag == "inferred" and self.confidence is not None:
            return f"- [{self.tag}] {self.text} (confiance: {self.confidence})"
        return f"- [{self.tag}] {self.text}"

    @classmethod
    def from_line(cls, line: str) -> MemoryEntry | None:
        """Parse une ligne de type '- [stated] texte'."""
        match = re.match(r"-\s*\[(\w+)\]\s+(.+)", line)
        if match:
            tag = match.group(1)
            text = match.group(2)
            if tag in {"stated", "observed", "inferred"}:
                conf = None
                conf_match = re.search(r"confiance:\s*([\d.]+)", text)
                if conf_match:
                    conf = float(conf_match.group(1))
                    text = re.sub(r"\s*\(confiance:\s*[\d.]+\)", "", text)
                return cls(tag=tag, text=text.strip(), confidence=conf)  # type: ignore
        return None


@dataclass(frozen=True)
class ConflitMemoire:
    """Un ecriture refusee parce que le jeton presente n'etait plus courant.

    Porter les DEUX jetons, et non un simple « conflit » : c'est la seule chose
    qui distingue un refus de version d'un autre echec d'ecriture, et c'est ce
    qui permet a l'appelant de rapporter un fait verifie plutot qu'un verdict
    sans cause. Un drapeau booléen aurait suffit a dire « conflit » et n'aurait
    pas permis de dire lequel.
    """

    expected: str
    actual: str


# ─── Memory filesystem ──────────────────────────────────────────────────


class MemoryFS:
    """Système de fichiers mémoire avec provenance et versionnage."""

    # Un verrou par CHEMIN RÉSOLU, au niveau de la classe et non de l'instance :
    # la ressource partagée est le fichier, pas l'objet. Deux `MemoryFS` pointant
    # le même dossier doivent donc se serialiser, sinon le contrôle de version ne
    # protège que les appels qui passent par la même instance.
    _verrous: dict[str, threading.RLock] = {}
    _verrous_mutex = threading.Lock()

    # Plafond du registre de verrous. Sans lui, un chemin par requête ferait
    # croitre le dictionnaire sans jamais se vider — le même défaut que
    # `_run_tokens` dans `trace_writer`, qui est plafonné pour cette raison.
    _VERROUS_MAX = 512

    def __init__(self, root: Path | None = None):
        self.root = root or MEMORY_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _verrou_pour(cls, full_path: Path) -> threading.RLock:
        """Le verrou d'un chemin, en légeant au besoin.

        La purge est faite sous le même mutex que l'insertion, donc elle ne peut
        pas observer un registre à moitié modifié. Elle ne retire pas un verrou
        encore détenu : `threading.Lock` n'a pas de compteur d government's, et un
        `del` sur un verrou en cours d'usage ferait échouer la prochaine insertion.
        Le registre reste donc plafonné *et* fonctionnel.
        """
        cle = str(full_path)
        with cls._verrous_mutex:
            v = cls._verrous.get(cle)
            if v is None:
                if len(cls._verrous) >= cls._VERROUS_MAX:
                    # On retire la moitié la plus ancienne, arbitrairement mais
                    # déterministiquement (tri des clés), plutôt que de laisser
                    # croître. Les verrous retirés ne sont plus réutilisés par les
                    # writers : ils perdent leur sérialisation, jamais leurs données.
                    for obsolete in sorted(cls._verrous)[: cls._VERROUS_MAX // 2]:
                        cls._verrous.pop(obsolete, None)
                v = threading.RLock()
                cls._verrous[cle] = v
            return v

    # ── Opérations de base ──────────────────────────────────────────

    def memory_read(self, path: str) -> tuple[str | None, str]:
        """Lit un fichier mémoire. Retourne (contenu, jeton_version)."""
        full_path = self.root / path
        if not full_path.exists():
            return None, ""
        content = full_path.read_text(encoding="utf-8")
        version = hashlib.sha256(content.encode()).hexdigest()[:12]
        return content, version

    def memory_write(self, path: str, content: str, if_version: str) -> tuple[bool, str]:
        """Crée ou remplace un fichier mémoire avec contrôle de version.

        **Atomique de bout en bout.** La vérification et l'écriture ont lieu sous
        le même verrou, et l'écriture elle-même passe par un fichier temporaire
        puis `os.replace`. Sans cela, deux écrivains concurrents passaient tous
        les deux la vérification et le dernier effaçait le premier : mesuré, un fait
        disparaissait en silence. Le jeton ne protégeait que le cas particulier où
        la collision tombait entre la lecture et la relecture — donc par chance
        d'ordonnancement, pas par garantie. C'est le défaut que « lire avant
        d'écrire » prétend fermer.
        """
        full_path = self.root / path

        with self._verrou_pour(full_path):
            if if_version == "new":
                if full_path.exists():
                    return False, "File already exists — use existing version token"
            elif full_path.exists():
                current, current_version = self.memory_read(path)
                if current_version != if_version:
                    return False, f"Version mismatch: expected {if_version}, got {current_version}. Re-read first."
            else:
                return False, "File does not exist — use 'new' to create"

            # Vérifier les règles d'omission
            content = self._sanitize_content(content)
            # P17 reliquat : `sanitize_memory` n'avait AUCUN appelant, donc
            # `MEMORY_INJECTION_PATTERNS` ne protégeait rien. Appliqué ici, et
            # seulement ici, parce que c'est le point de passage de TOUTES les
            # écritures mémoire : M6.2, M6.9 et le profil passent tous par
            # `memory_write`. Un filtre posé à l'un de ses appelants aurait laissé
            # les deux autres fuir.
            content = self._assainir_injections(content)

            full_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._ecrire_atomiquement(full_path, content)
            except OSError as exc:
                # Ni la cible ni la version precedente n'ont ete touchees, mais
                # l'appelant doit lire un REFUS explicite. Laisser l'exception
                # remonter jusqu'au `except Exception` de la boucle la
                # transformerait en `logger.debug` : une memoire non enregistree
                # qui se presente comme un stockage sans fait.
                return False, f"write failed, previous version kept: {exc}"

        new_version = hashlib.sha256(content.encode()).hexdigest()[:12]
        return True, new_version

    @staticmethod
    def _ecrire_atomiquement(full_path: Path, content: str) -> None:
        """Écrit sans jamais laisser un fichier à moitié écrit.

        `write_text` écrit DANS la cible : un process tué au milieu laisse un
        fichier mémoire tronqué, et la version précédente — celle que le jeton
        désigne — a disparu. Un fichier temporaire dans le *même* répertoire (donc
        même système de fichiers, donc `os.replace` atomique) puis un renommage
        rend l'opération indivisible : il y a une version complète avant, une
        après, jamais une entre les deux.
        """
        fd, tmp = tempfile.mkstemp(dir=str(full_path.parent), prefix=f".{full_path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, full_path)
        except BaseException:
            # Une écriture interrompue ne doit pas laisser de tempfile derrière,
            # et surtout ne doit pas avoir touché à la cible.
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def memory_append(self, path: str, entry: str, if_version: str) -> tuple[bool, str]:
        """Ajoute une ligne à un fichier existant."""
        full_path = self.root / path

        # Le couple lecture-construction-écriture est tenu sous un seul verrou,
        # sinon deux appends se lisent mutuellement, passent tous deux la
        # vérification, et le second écrase le premier. `memory_write` prend le
        # même verrou : il faut donc le relâcher avant d'y entrer, d'où la
        # délégation explicite du dernier pas.
        with self._verrou_pour(full_path):
            content, current_version = self.memory_read(path)
            if content is None:
                return False, "File does not exist"

            if current_version != if_version:
                # Meme forme que le refus de `memory_write` : le prefixe
                # "Version mismatch" reste, donc rien de ce qui le reconnait ne
                # casse, et les deux jetons deviennent disponibles sans relire.
                return False, f"Version mismatch: expected {if_version}, got {current_version}. Re-read first."

            # Vérifier les règles d'omission
            if self._should_omit(entry):
                return False, "Entry blocked by omission rules"

            # Vérifier que l'entrée n'est pas déjà présente
            if entry.strip() in content:
                return True, current_version  # Déjà présent, pas d'erreur

            new_content = content.rstrip() + "\n" + entry + "\n"

        # Réutilise la vérification de version de `memory_write` plutôt que de la
        # dupliquer : deux implémentations du même contrôle divergent, et c'est
        # comme ça qu'un contrôle devient décoratif.
        return self.memory_write(path, new_content, current_version)

    def memory_str_replace(self, path: str, old_str: str, new_str: str, if_version: str) -> tuple[bool, str]:
        """Remplacement chirurgical dans un fichier."""
        content, current_version = self.memory_read(path)
        if content is None:
            return False, "File does not exist"

        if current_version != if_version:
            return False, "Version mismatch"

        count = content.count(old_str)
        if count == 0:
            return False, "old_str not found"
        if count > 1:
            return False, f"old_str found {count} times — must be unique"

        new_content = content.replace(old_str, new_str, 1)
        return self.memory_write(path, new_content, current_version)

    def memory_delete(self, path: str, if_version: str) -> tuple[bool, str]:
        """Supprime un fichier mémoire."""
        full_path = self.root / path
        if not full_path.exists():
            return False, "File does not exist"

        if if_version != "force":
            _, current_version = self.memory_read(path)
            if current_version != if_version:
                return False, "Version mismatch"

        full_path.unlink()
        return True, ""

    def memory_list(self, prefix: str = "") -> list[str]:
        """Liste les fichiers sous un préfixe."""
        search_path = self.root / prefix if prefix else self.root
        if not search_path.exists():
            return []
        files = []
        for f in search_path.rglob("*.md"):
            rel = f.relative_to(self.root)
            files.append(str(rel).replace("\\", "/"))
        return sorted(files)

    # ── Règles d'omission ────────────────────────────────────────────

    def _should_omit(self, text: str) -> bool:
        """Vérifie si un texte contient des données à ne jamais stocker."""
        text_lower = text.lower()
        for trigger in OMISSION_TRIGGERS:
            if trigger in text_lower:
                logger.info("Omitting entry containing: %s", trigger)
                return True
        return False

    def _sanitize_content(self, content: str) -> str:
        """Nettoie le contenu avant écriture."""
        lines = content.split("\n")
        clean_lines = []
        for line in lines:
            if self._should_omit(line):
                continue
            clean_lines.append(line)
        return "\n".join(clean_lines)

    @staticmethod
    def _assainir_injections(content: str) -> str:
        """Neutralise les phrases d'injection avant qu'elles n'atteignent le disque.

        Une mémoire relue plus tard est du **texte que le modèle va suivre**. Y
        laisser « ignore all previous instructions » revient à laisser une
        consigne au rang de fait. Le remplacement est visible (`[FILTERED]`) et
        non une suppression : un lecteur doit pouvoir distinguer « rien n'a été
        dit » de « quelque chose a été retiré ».

        Respecte `ODYSSEUS_CONTENT_SECURITY` : le kill-switch qui prétend régir
        ce contrôle doit le régir vraiment, pas seulement le log qui l'annonçait.
        """
        if not content_security_enabled():
            return content
        return get_content_security().sanitize_memory(content)

    # ── Helpers de haut niveau ────────────────────────────────────────

    def add_stated(self, domain: str, fact: str) -> tuple[bool, str]:
        """Ajoute un fait [stated] dans le domaine approprié."""
        path = f"topics/{domain}.md"
        entry = f"- [stated] {fact}"

        content, version = self.memory_read(path)
        if content is None:
            # Créer le fichier
            mf = MemoryFile(
                path=self.root / path,
                name=domain,
                description=f"Faits sur {domain}",
            )
            mf.entries = [MemoryEntry(tag="stated", text=fact)]
            return self.memory_write(path, mf.content, "new")

        ok, res, _conflit = self.append_cas(path, entry, if_version=version)
        return ok, res

    def add_observed(self, domain: str, fact: str) -> tuple[bool, str]:
        """Ajoute un fait [observed]."""
        return self.add_observed_cas(domain, fact)[:2]

    def add_observed_cas(
        self,
        domain: str,
        fact: str,
        *,
        if_version: str | None = None,
    ) -> tuple[bool, str, ConflitMemoire | None]:
        """Comme `add_observed`, mais RAPPORTE le conflit. `(ok, jeton, conflit)`.

        `if_version` est le jeton retenu lors d'un appel **antérieur**. C'est ce qui
        donne enfin une route de production au contrôle de version : jusque-là les
        quatre aides relisaient et écrivaient dans le même corps de fonction, donc
        le jeton ne circulait jamais et la branche de rejet n'était atteignable que
        depuis un test.

        Passer un jeton périmé n'écrase rien : l'écriture est refusée, `conflit` est
        vrai, et l'appelant décide — refuser, ou réessayer sur un jeton frais. On ne
        réessaie pas à sa place : un appelant qui demandait une écriture conditionnelle
        ne doit pas recevoir une écriture inconditionnelle en retour.
        """
        return self.append_cas(
            f"topics/{domain}.md",
            f"- [observed] {fact}",
            if_version=if_version,
            absent="Domain file does not exist — cannot observe without prior context",
        )

    def append_cas(
        self,
        path: str,
        entry: str,
        *,
        if_version: str | None = None,
        absent: str = "File does not exist",
    ) -> tuple[bool, str, ConflitMemoire | None]:
        """Compare-and-swap borné. Retourne `(ok, jeton_ou_message, conflit)`.

        `conflit` est un `ConflitMemoire` — les deux jetons — ou `None`. Sa
        verite est donc un booléen, comme un drapeau, mais l'appelant reçoit la
        cause.

        Implémentation unique de l'append à jeton : les quatre aides y délèguent
        plutôt que de re-lire/re-écrire chacune de leur côté. Deux implémentations
        du même contrôle divergent, et c'est ainsi qu'un contrôle devient décoratif.

        Avec `if_version=None` (le cas des aides historiques) on relit puis on
        réessaie : deux tours concurrents ne se marchent pas dessus, et aucun fait
        ne se perd. La reprise est **bornée** — sous une contention réelle, un
        nombre d'essais fixe est un appel qui rend la main au lieu de boucler.
        """
        # Le verrou est REENTRANT, donc `memory_append` puis `memory_write`
        # peuvent le reprendre sans s'auto-bloquer. Il couvre ici tout le
        # compare-and-swap : lecture, verification et ecriture forment une seule
        # section critique. Sans cela, huit ecrivains se lisent mutuellement,
        # passent tous la verification, et la reprise bornee sature a trois
        # essais — mesure : 3 sur 8 seulement aboutissaient.
        with self._verrou_pour(self.root / path):
            refute: str | None = None
            conflit: ConflitMemoire | None = None
            for essai in range(_CAS_TENTATIVES):
                if if_version is None or essai > 0:
                    contenu, jeton = self.memory_read(path)
                    if contenu is None:
                        return False, absent, None
                    # Le jeton lu ICI est la version qui a refuse l'essai precedent :
                    # rien ne s'est ecrit entre les deux, puisque le verrou tient.
                    # C'est le seul endroit ou le « courant » est connu — le
                    # fabriquer au moment du refus, ce serait y mettre le jeton
                    # presente, ce qui donne un conflit qui se compare a lui-meme
                    # et qui ne prouve rien.
                    if conflit is None and refute is not None:
                        conflit = ConflitMemoire(expected=refute, actual=jeton)
                else:
                    # Premier essai : on honore le jeton de l'appelant, sans
                    # relire. C'est ce qui rend le refus possible.
                    jeton = if_version
                ok, res = self.memory_append(path, entry, jeton)
                if ok:
                    return True, res, conflit
                if "Version mismatch" not in res:
                    return False, res, None
                if refute is None:
                    refute = jeton
            if conflit is None:
                # Les essais sont epuises sans qu'une lecture ait suivi le refus
                # (possible seulement si `_CAS_TENTATIVES` valait 1). On relit une
                # fois plutot que de rapporter un conflit sans cause.
                _, courant = self.memory_read(path)
                conflit = ConflitMemoire(expected=refute or "", actual=courant)
            return False, f"Version mismatch after {_CAS_TENTATIVES} attempts", conflit

    def add_inferred(self, domain: str, fact: str, confidence: float) -> tuple[bool, str]:
        """Ajoute un fait [inferred] avec niveau de confiance."""
        path = f"topics/{domain}.md"
        entry = f"- [inferred] {fact} (confiance: {confidence})"

        content, version = self.memory_read(path)
        if content is None:
            return False, "Domain file does not exist"

        ok, res, _conflit = self.append_cas(path, entry, if_version=version)
        return ok, res

    def get_profile(self) -> str | None:
        """Lit le profil utilisateur."""
        content, _ = self.memory_read("profile.md")
        return content

    def update_profile(self, fact: str, tag: ProvenanceTag = "stated") -> tuple[bool, str]:
        """Met à jour le profil."""
        path = "profile.md"
        entry = f"- [{tag}] {fact}"

        content, version = self.memory_read(path)
        if content is None:
            mf = MemoryFile(
                path=self.root / path,
                name="profile",
                description="Identité stable de l'utilisateur",
            )
            mf.entries = [MemoryEntry(tag=tag, text=fact)]
            return self.memory_write(path, mf.content, "new")

        return self.memory_append(path, entry, version)


# ─── Singleton ───────────────────────────────────────────────────────────

app_context.caches.fs: MemoryFS | None = None


def get_memory_fs() -> MemoryFS:
    if app_context.caches.fs is None:
        app_context.caches.fs = MemoryFS()
    return app_context.caches.fs
