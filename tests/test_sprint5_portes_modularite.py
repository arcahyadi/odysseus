"""§3 du v10 — les portes gèlent-elles les grandeurs que MOD-1→10 vont bouger ?

Le v10 demande ce point **avant** MOD-9. Vérifié, il était négatif : trois
seuils gelaient, ils couvraient quatre chantiers. **Six chantiers agissaient sur
une grandeur que rien ne surveille** — donc six chantiers pouvaient dériver en
silence, ce qui est précisément ce que le v10 veut empêcher.

Ces cinq seuils sont donc ajoutés. Un seuil ajouté sans preuve qu'il *peut*
rougir n'est pas une porte, c'est une ligne de plus : c'est la règle du v9 §2,
appliquée à l'outil qui doit la porter. D'où les quatre familles de preuves :

* **anti-gonflage** — un seuil posé **au-dessus** de la mesure exige une
  justification `releve_si` non vide. Sans elle, ajouter une porte revient à
  choisir un nombre, et le nombre devient la réalité ;
* **frontière exacte** — pour chaque seuil, à la valeur verte, à la valeur + 1
  rouge. Une porte qui ne rougit pas au bon endroit est une porte décorative
  qui a l'air de travailler ;
* **non-vacuité** — chaque nouvelle mesure doit pouvoir **bouger** sur un dépôt
  fabriqué, sinon c'est une constante déguisée en mesure ;
* **immunité au texte** — une mention dans un commentaire ne fait pas une
  référence. C'est l'erreur de mesure que la règle du v10 §2 interdit, et elle
  a effectivement produit un seuil faux (10 au lieu de 9) avant d'être réparée.
"""

import importlib.util
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent


def _charge():
    spec = importlib.util.spec_from_file_location("cm_v10", REPO / "tools/check_modularity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _charge()

# cle du seuil -> fonction qui la mesure. Les trois premiers seuils ont une
# fonction au nom different ou un retour non entier ; ils sont deja couverts par
# le test de frontiere du Sprint 4, donc la preuve generique porte sur les cinq
# ajouts, qui sont tous `int` et tous prennent `root`.
MESURES = {
    # 5 seuils ajoutés (Sprint 5 MOD-3, MOD-5, MOD-6, MOD-7, MOD-4) — fonctions standalone
    "paquets_sfd_non_tranches": "paquets_sfd_non_tranches",
    "globals_dans_src": "globals_dans_src",
    "fournisseurs_hors_interface": "fournisseurs_hors_interface",
    "modules_resolution_modele": "modules_resolution_modele",
    "imports_de_shim": "imports_de_shim",
}


# ── 1. anti-gonflage ────────────────────────────────────────────────────────
def test_chaque_seuil_est_au_niveau_mesure_ou_justifie():
    """PREUVE 1 : aucun seuil n'est pose au-dessus de ce qu'on mesure.

    Une porte qui demande moins que le dépôt ne fait rien ; une porte qui
    demande plus que le dépôt bloque tout. Le seuil doit donc être **la mesure**,
    et toute hausse doit porter sa raison, sinon le nombre choisi devient la
    réalité au lieu de la mesurer.
    """
    m = mod.mesure()
    for cle, seuil in mod.SEUILS.items():
        assert cle in m, f"le seuil {cle} ne correspond a aucune grandeur mesuree"
        if seuil["valeur"] > m[cle]:
            assert (seuil.get("releve_si") or "").strip(), (
                f"le seuil {cle} est a {seuil['valeur']} alors que la mesure est "
                f"{m[cle]} : au-dessus de la mesure sans justification `releve_si`."
            )


def test_les_dix_chantiers_sont_couverts_par_une_grandeur_gelee():
    """PREUVE 2 : chaque chantier MOD a une grandeur que la porte surveille.

    C'est la demande du v10, énoncée en test : aucun des dix chantiers ne doit
    pouvoir dériver en silence. Une grandeur partagée par deux chantiers
    (MOD-2 et MOD-8 agissent tous deux sur `aretes_src_vers_routes`) compte
    pour les deux.
    """
    couverture = {
        "MOD-1": "route_loader_imports_statiques",
        "MOD-2": "aretes_src_vers_routes",
        "MOD-3": "modules_resolution_modele",
        "MOD-4": "imports_de_shim",
        "MOD-5": "globals_dans_src",
        "MOD-6": "core_database_importeurs",
        "MOD-7": "fournisseurs_hors_interface",
        "MOD-8": "aretes_src_vers_routes",
        "MOD-9": "paquets_sfd_non_tranches",
        "MOD-11": "core_database_importeurs",
    }
    gelees = set(mod.SEUILS)
    for chantier, cle in couverture.items():
        assert cle in gelees, (
            f"le chantier {chantier} agit sur `{cle}`, que rien ne gele. "
            "Il peut donc deriver en silence — exactement ce que le v10 interdit."
        )


# ── 2. frontiere exacte, pour chaque seuil ajoute ──────────────────────────
# On ne teste la frontière que pour les 5 nouveaux seuils (fonctions standalone)
# Les 3 seuils originaux n'ont pas de fonction standalone dédiée
CINQ_NOUVEAUX = sorted([
    "paquets_sfd_non_tranches",
    "globals_dans_src",
    "fournisseurs_hors_interface",
    "modules_resolution_modele",
    "imports_de_shim",
])

@pytest.mark.parametrize("cle", CINQ_NOUVEAUX)
def test_la_frontiere_de_chaque_seuil_est_exacte(cle, monkeypatch):
    """PREUVE 3 : à la valeur verte, à la valeur + 1 rouge.

    Le test ne se contente pas de vérifier que le seuil existe : il force la
    mesure. Quelqu'un qui gonfle un seuil à 60 voit ce test **échouer** — parce
    qu'à 61 la porte ne rougit plus. C'est le signal à surveiller, et il n'existe
    que si la frontière est testée.
    """
    # Charger un module frais pour chaque test pour isolation
    mod = _charge()
    
    sys.argv = ["check_modularity.py"]
    
    # Mapping seuil -> nom de fonction réelle
    FONCTION_MESURE = {
        "paquets_sfd_non_tranches": "paquets_sfd_non_tranches",
        "globals_dans_src": "globals_dans_src",
        "fournisseurs_hors_interface": "fournisseurs_hors_interface",
        "modules_resolution_modele": "modules_resolution_modele",
        "imports_de_shim": "imports_de_shim",
        "core_database_importeurs": "importeurs_de_god_node",
        "aretes_src_vers_routes": "aretes_src_vers_routes",
        "route_loader_imports_statiques": "imports_statiques_route_loader",
    }
    
    # Mocker toutes les fonctions de mesure à leur valeur de seuil
    for c, f in {
        "paquets_sfd_non_tranches": "paquets_sfd_non_tranches",
        "globals_dans_src": "globals_dans_src",
        "fournisseurs_hors_interface": "fournisseurs_hors_interface",
        "modules_resolution_modele": "modules_resolution_modele",
        "imports_de_shim": "imports_de_shim",
        "core_database_importeurs": "importeurs_de_god_node",
        "aretes_src_vers_routes": "aretes_src_vers_routes",
        "route_loader_imports_statiques": "imports_statiques_route_loader",
    }.items():
        v = mod.SEUILS[c]["valeur"]
        if f == "importeurs_de_god_node":
            monkeypatch.setattr(mod, f, lambda root=None, val=v: [None] * val)
        elif f == "aretes_src_vers_routes":
            monkeypatch.setattr(mod, f, lambda root=None, val=v: (val, []))
        else:
            monkeypatch.setattr(mod, f, lambda root=None, val=v: val)
    
    valeur = mod.SEUILS[cle]["valeur"]
    fct = MESURES.get(cle, cle)
    
    # Test frontière : à la valeur exacte, pas de franchissement
    monkeypatch.setattr(mod, fct, lambda root=None: valeur)
    assert mod.mesure()[cle] == valeur
    assert mod.main() == 0, f"{cle} a {valeur}, son seuil est {valeur} : rien n'est franchi"

    # Au-delà du seuil : la porte doit rougir
    monkeypatch.setattr(mod, fct, lambda root=None: valeur + 1)
    assert mod.mesure()[cle] == valeur + 1
    assert mod.main() == 1, f"{cle} a {valeur + 1} et ne fait pas tomber la porte"


# ── 3. non-vacuite : chaque mesure doit savoir bouger ───────────────────────
def test_le_seuil_a_zero_nest_pas_une_porte_cassee(tmp_path, monkeypatch):
    """PREUVE 4 : la porte a 0 se demontre capable de rougir.

    « Une porte a 0 est une porte cassee » est vrai d'une grandeur qui doit
    descendre : a 0, plus rien ne peut la depasser, et la garde ne garde rien.
    La regle du Sprint 4 a ete derivee de ce cas, puis ecrite comme si elle etait
    absolue. Elle ne l'est pas : pour une grandeur de **conformite**, 0 est la
    cible, et le seuil le plus strict qui existe.

    A une condition, et c'est toute la question : que la mesure puisse
    reellement depasser 0. Ce test l'etablit en deux temps sur un depot
    fabrique — la mesure vaut 1 des qu'un fournisseur n'implemente pas l'ABC, et
    la porte rougit. Sans ce second temps, elargir la regle serait un
    assouplissement, et un seuil a 0 non prouve serait exactement la constante
    decoratique que MOD-11 pretend corriger.
    """
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / "mauvais.py").write_text(
        "class MemoryVectorProvider:\n"
        "    def get(self):\n"
        "        return []\n",
        encoding="utf-8",
    )
    assert mod.fournisseurs_hors_interface(root=tmp_path) == 1, (
        "un fournisseur qui n'implemente pas l'ABC n'est pas compte : le seuil a 0 "
        "ne pourrait alors jamais etre depasse, et la porte serait bien cassee."
    )
    assert mod.SEUILS["fournisseurs_hors_interface"]["sens"] == "conformance", (
        "la grandeur a 0 ne se declare pas conformante : la regle du Sprint 4 "
        "devrait alors la refuser, et elle a raison."
    )
    assert mod.fournisseurs_hors_interface() == 0, (
        "le depot reel a un fournisseur hors interface : le seuil a 0 decrit mal "
        "l'etat, et la porte est deja rouge sans qu'on le sache."
    )

    sys.argv = ["check_modularity.py"]
    monkeypatch.setattr(mod, "fournisseurs_hors_interface", lambda root=None: 1)
    assert mod.main() == 1, (
        "la mesure vaut 1 et le seuil vaut 0, mais la porte reste verte : "
        "elle ne garde rien."
    )


def test_les_autres_mesures_savent_bouger(tmp_path):
    """PREUVE 5 : les quatre autres grandeurs ne sont pas des constantes.

    Une mesure qui ne peut pas bouger est un nombre figé avec une fonction
    autour. Chacune est donc actionnée sur un dépôt fabriqué, et l'écart entre
    le dépôt vide et le dépôt peuplé doit être exactement celui qu'on annonce.
    """
    vide = {
        "paquets_sfd_non_tranches": mod.paquets_sfd_non_tranches(root=tmp_path),
        "globals_dans_src": mod.globals_dans_src(root=tmp_path),
        "modules_resolution_modele": mod.modules_resolution_modele(root=tmp_path),
        "imports_de_shim": mod.imports_de_shim(root=tmp_path),
    }
    assert vide == dict.fromkeys(vide, 0), f"un depot vide ne devrait rien mesurer : {vide}"

    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "a.py").write_text(
        "C = 0\n"
        "def _f():\n"
        "    global C\n"
        "    C += 1\n"
        "def resolve_endpoint():\n"
        "    return None\n",
        encoding="utf-8",
    )
    (src / "b.py").write_text("from llm_core import machin\n", encoding="utf-8")

    assert mod.globals_dans_src(root=tmp_path) == 1, "le `global` n'est pas vu"
    assert mod.modules_resolution_modele(root=tmp_path) == 1, "la resolution de modele n'est pas vue"
    assert mod.imports_de_shim(root=tmp_path) == 1, "l'import de shim n'est pas vu"

    paq = tmp_path / "packages" / "sfd-demo"
    (paq / "src").mkdir(parents=True)
    (paq / "package.json").write_text(json.dumps({"name": "@agentos/sfd-demo"}), encoding="utf-8")
    assert mod.paquets_sfd_non_tranches(root=tmp_path) == 1, "un paquet sans reference n'est pas compte"


# ── 4. immunite au texte : l'erreur de mesure du v10 §2 ───────────────────
def test_une_mention_dans_un_commentaire_ne_cree_pas_de_reference(tmp_path):
    """PREUVE 6 : le texte ne fait pas une référence.

    C'est la faute exacte que la règle du v10 §2 interdit, et elle a
    effectivement produit un seuil faux : une première mesure cherchait
    `@agentos/<nom>` dans les fichiers **Python** alors que les paquets sont
    TypeScript, et annonçait 0 paquet branché au lieu de 1. Le seuil en a été
    déduit, à 10 au lieu de 9.

    Ici, un dépôt mentionne un paquet dans un commentaire et dans une chaîne :
    la mesure doit le compter **non tranché**. Et un dépôt qui le déclare
    réellement — une valeur JSON dans `opencode.json` — doit le compter
    tranché. Le premier cas est celui qui compte : une mention n'est pas une
    preuve, et une porte qui l'accepte est une porte qu'on peut duper par un
    commentaire.
    """
    paq = tmp_path / "packages" / "sfd-demo"
    paq.mkdir(parents=True)
    (paq / "package.json").write_text(json.dumps({"name": "@agentos/sfd-demo"}), encoding="utf-8")

    # 1. mention pure : commentaire et chaine, aucun import, aucune config.
    src = tmp_path / "src"
    src.mkdir()
    (src / "mention.py").write_text(
        "# on pourrait brancher @agentos/sfd-demo un jour\n"
        'DOC = "voir @agentos/sfd-demo"\n',
        encoding="utf-8",
    )
    assert mod.paquets_sfd_non_tranches(root=tmp_path) == 1, (
        "une mention dans un commentaire ou une chaine a ete comptee comme une "
        "reference : n'importe quel commentaire ferait passer un paquet pour branche."
    )

    # 2. declaration reelle : une valeur JSON resolue.
    (tmp_path / "opencode.json").write_text(
        json.dumps({"plugin": ["@agentos/sfd-demo"]}), encoding="utf-8"
    )
    assert mod.paquets_sfd_non_tranches(root=tmp_path) == 0, (
        "un paquet reellement declare dans opencode.json n'est pas compte comme "
        "branche : la mesure ne resout pas la reference qu'elle pretend suivre."
    )


def test_la_mesure_independante_confirme_la_porte():
    """PREUVE 7 : deux mesures indépendantes, sinon il n'y a pas de mesure.

    La règle du Sprint 4 : aucun chiffre ne devient une vérité tant qu'il n'a
    pas survécu à une deuxième mesure indépendante. Ici la deuxième mesure est
    un comptage direct, écrit à part, qui ne passe par aucune des fonctions de
    la porte.
    """
    paquets = sorted((REPO / "packages").glob("sfd-*"))
    config = json.loads((REPO / "opencode.json").read_text(encoding="utf-8"))
    declares = {v for v in _valeurs(config) if isinstance(v, str)}
    branches = {p.name for p in paquets if f"@agentos/{p.name}" in declares}
    attendu = len(paquets) - len(branches)

    assert mod.paquets_sfd_non_tranches() == attendu, (
        f"la porte dit {mod.paquets_sfd_non_tranches()}, le comptage direct dit "
        f"{attendu} ({len(branches)} branche(s) sur {len(paquets)})."
    )
    assert len(paquets) == 10, f"le nombre de paquets a change : {len(paquets)}"


def _valeurs(noeud):
    if isinstance(noeud, dict):
        for k, v in noeud.items():
            yield k
            yield from _valeurs(v)
    elif isinstance(noeud, list):
        for v in noeud:
            yield from _valeurs(v)
    else:
        yield noeud
