"""Item 4 du Sprint 4 (MOD-11) — la porte doit tomber, sinon ce n'est pas une porte.

`tools/check_modularity.py` est vert aujourd'hui, les trois grandeurs étant
exactement à leur seuil. Un seuil atteint n'est pas une preuve que la porte
fonctionne : c'est même la situation où l'on est le plus tenté de la croire
sage. Ce fichier la fait donc tomber trois fois, sur les trois grandeurs, en
modifiant un **fichier temporaire** plutôt que le dépôt.

Le choix du temporaire est délibéré. Les autres tests de ce chantier ont
provoqué la mort d'un `git reset --hard` et une fuite d'état global ; une porte
qui dépose une arête dans `src/` puis oublie de la retirer laisserait le dépôt
dans un état que le test suivant mesurerait. Ici, la modification vit et meurt
dans `tmp_path`, et le dépôt est bit pour bit identique à l'entrée comme à la
sortie.

Un test vérifie aussi que la mesure **exclut les cas légitimes**. C'est le
point où cette porte pouvait être fausse de façon utile : compter les arêtes
depuis les tests et depuis le chargeur donnerait 421 au lieu de 30, et un seuil
à 421 se contourne en supprimant un test. Une porte qu'on peut faire passer en
détruisant ce qu'elle est censée protéger ne protège rien.
"""

import importlib.util
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
OUTIL = REPO / "tools/check_modularity.py"


def _charge():
    spec = importlib.util.spec_from_file_location("check_modularity", OUTIL)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules["check_modularity"] = m
    spec.loader.exec_module(m)
    return m


mod = _charge()

# La liste reelle des fichiers, capturee une fois au chargement du module, donc
# AVANT tout monkeypatch. La rappeler depuis un helper rappelle la version
# patchee — et l'echelle : RecursionError au lieu d'un echec lisible.
_BASE = list(mod._fichiers_py())


def _avec(extra: pathlib.Path) -> list[pathlib.Path]:
    return [*_BASE, extra]


def _mesure_fictive(racine: pathlib.Path, fichiers: list[pathlib.Path]) -> int:
    """La mesure sur une racine temporaire, avec les memes regles qu'en depot.

    Le repli « hors depot, le nom suffit » a ete supprime de l'outil : il
    classait un `packages/*/src/` temporaire comme une violation, ce qui est
    exactement le defaut qu'on cherche a eviter. Injecter la racine evite d'avoir
    a relaxed une regle pour les besoins du test.
    """
    return mod.mesure(root=racine)["aretes_src_vers_routes"]


def test_la_porte_passe_sur_l_etat_actuel():
    """CONTRE-ÉPREUVE deDepart : sans elle, une porte rouge pour de bonnes
    raisons passerait pour une porte verte, et l'inverse aussi."""
    sys.argv = ["check_modularity.py"]
    assert mod.main() == 0, (
        f"la porte de modularite est rouge sur l'etat ACTUEL : {mod.mesure()} "
        f"contre des seuils { {k: v['valeur'] for k, v in mod.SEUILS.items()} }. "
        "Soit une regression reelle qu'il faut corriger, soit l'etat a change et "
        "les seuils doivent etre releves avec une justification."
    )


def test_chaque_seuil_nomme_le_chantier_quil_protege():
    """CONTRE-ÉPREUVE de governance : un seuil sans chantier est un nombre figé.

    Un seuil qu'on ne rattache à aucun travail en cours ne sera ni contesté ni
    fait baisser : il devient une constante décorative, c'est-à-dire exactement
    ce que MOD-11 prétend régler.
    """
    for cle, seuil in mod.SEUILS.items():
        assert seuil.get("chantier", "").strip(), f"le seuil {cle} ne nomme aucun chantier"
        assert seuil.get("raison", "").strip(), f"le seuil {cle} n'a aucune raison"

        # « Une porte a 0 est une porte cassee » reste vrai pour une grandeur
        # qui doit DESCENDRE : a 0, aucune valeur ne peut jamais depasser le
        # seuil, donc la garde ne peut jamais rougir et ne garde rien.
        #
        # La regle avait ete derivee de ce seul cas, puis ecrite comme si elle
        # etait absolue. Elle ne l'est pas : pour une grandeur de CONFORMANCE,
        # 0 est la cible, et le seuil le plus strict qui existe. Un seuil a 0
        # n'est decoratif que si la mesure ne peut pas le depasser — et c'est
        # precisement ce qu'il faut prouver, pas supposer. D'ou l'obligation
        # supplementaire portee par `sens: conformance`, dont la non-vacuite
        # est verifiee par un test qui construit un depassement.
        #
        # Elargir la regle sans cette preuve serait exactement l'assouplissement
        # que MOD-11 pretend.hibernate : d'ou le test de non-vacuite en aval.
        if seuil.get("sens") == "conformance":
            assert seuil["valeur"] == 0, (
                f"le seuil {cle} se declare conforme mais vaut {seuil['valeur']} : "
                "une grandeur de conformance se gel e a 0, ou elle n'en est pas une."
            )
        else:
            assert seuil["valeur"] > 0, (
                f"le seuil {cle} est nul sans se declarer `sens: conformance` : "
                "une porte a 0 est une porte cassee."
            )


def test_la_frontiere_du_seuil_des_aretes_est_exacte(tmp_path, monkeypatch):
    """PREUVE 1 — le seuil est où il dit être : 30 vert, 31 rouge.

    Une porte ne peut rougir que si la mesure **dépasse** son seuil. Tester
    « une arete de plus rend la porte rouge » sur une racine vide n'aurait donc
    aucun sens — 1 arête est très en dessous de 30. Le test utile fixe la
    frontière, ce qui prouve au passage que le seuil vaut bien 30 et pas 35.

    C'est aussi ce qui rend le seuil vérifiable par la suite plutôt que par
    relecture : quelqu'un qui gonfle le seuil à 60 voit ce test devenir vert au
    lieu de le voir échouer, ce qui est exactement le signal à surveiller.
    """
    sys.argv = ["check_modularity.py"]

    def _ecris(n: int) -> list[pathlib.Path]:
        fichiers = []
        for i in range(n):
            f = tmp_path / "src" / f"m{i}.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("from routes.chat_routes import router\n", encoding="utf-8")
            fichiers.append(f)
        return fichiers

    for f in tmp_path.glob("src/*.py"):
        f.unlink()

    fichiers = _ecris(30)
    monkeypatch.setattr(mod, "_fichiers_py", lambda: list(fichiers))
    assert _mesure_fictive(tmp_path, fichiers) == 30, "la mesure de reference n'est pas 30"
    assert mod.mesure(root=tmp_path)["aretes_src_vers_routes"] == 30
    # Au seuil exact : rien n'est franchi.
    seuils = {k: v["valeur"] for k, v in mod.SEUILS.items()}
    assert seuils["aretes_src_vers_routes"] >= 30, (
        f"le seuil des aretes est {seuils['aretes_src_vers_routes']} : ce test en mesure 30, "
        "donc il ne teste plus la frontiere annoncee. Relevez le test, pas le seuil."
    )
    if seuils["aretes_src_vers_routes"] == 30:
        fichiers = _ecris(31)
        monkeypatch.setattr(mod, "_fichiers_py", lambda: list(fichiers))
        assert mod.mesure(root=tmp_path)["aretes_src_vers_routes"] == 31
        mod.SEUILS["aretes_src_vers_routes"]["valeur"] = 30
        assert mod.main(racine=tmp_path) == 1, "31 aretes ne font pas tomber la porte : elle est de plain-pied"

def test_un_nouvel_importeur_du_god_node_est_refuse(tmp_path, monkeypatch):
    """PREUVE 2 : le god node ne peut pas grossir.

    C'est le chiffre qui a passe de 64 a 120 sans qu'une porte le voie. Le
    seuil est pose au niveau actuel : toute hausse est une regression, et une
    baisse serait une reussite a feter.
    """
    avant = len(mod.importeurs_de_god_node())

    consommateur = tmp_path / "src" / "nouveau_consommateur.py"
    consommateur.parent.mkdir(parents=True)
    consommateur.write_text("from core.database import SessionLocal\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_fichiers_py", lambda: _avec(consommateur))

    apres = len(mod.importeurs_de_god_node())
    assert apres == avant + 1, f"le nouvel importeur n'a pas ete compte : {avant} -> {apres}"
    sys.argv = ["check_modularity.py"]
    assert mod.main() == 1, "la porte a accepte un importeur de plus vers le god node"


def test_un_import_statique_de_route_loader_en_plus_est_refuse(tmp_path, monkeypatch):
    """PREUVE 3 : le chargeur ne peut pas grossir en imports figes.

    Le seuil est a 54 exactement, ce qui est la valeur d'aujourd'hui : la porte
    ne pretend pas avoir fait MOD-1, elle pretend qu'on ne puisse pas le
    defaire.
    """
    faux_loader = tmp_path / "route_loader.py"
    faux_loader.write_text(
        "\n".join(f"from routes.m{i} import r" for i in range(mod.imports_statiques_route_loader() + 1)),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "imports_statiques_route_loader", lambda: faux_loader.read_text().count("from routes."))

    sys.argv = ["check_modularity.py"]
    assert mod.main() == 1, "la porte a accepte un import statique de plus dans route_loader"


def test_la_mesure_exclut_les_aretes_legitimes(tmp_path, monkeypatch):
    """CONTRE-ÉPREUVE de justesse : un test de route n'est pas une violation.

    275 des 421 aretes viennent de tests et 54 du chargeur. Les compter
    produirait un seuil que l'on contourne en supprimant un test — la porte
    mesurerait la mauvaise grandeur ET serait gamingable. Ce test verrouille les
    deux exclusions.
    """
    reel = _mesure_fictive(tmp_path, [])

    # Un fichier de test qui importe une route ne doit rien changer au compte.
    test_faux = tmp_path / "tests" / "test_ajoute.py"
    test_faux.parent.mkdir(parents=True)
    test_faux.write_text("from routes.chat_routes import router\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_fichiers_py", lambda: [test_faux])
    assert _mesure_fictive(tmp_path, [test_faux]) == reel, (
        "une arete depuis un TEST compte comme une violation : le seuil devient "
        "contournable en supprimant un test, et la porte mesure les tests au lieu "
        "de mesurer les couches."
    )


def test_la_porte_est_branchable_en_ligne_de_commande():
    """CONTRE-ÉPREUVE d'existence : l'outil doit marcher sans pytest.

    Une porte qui n'existe qu'en test n'est pas une porte : elle ne tourne que
    quand quelqu'un pense a lancer la suite. CI l'appelle en sous-processus.
    """
    r = subprocess.run(
        [sys.executable, str(OUTIL)],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert r.returncode == 0, f"l'outil sort en {r.returncode} sur l'etat actuel :\n{r.stdout}\n{r.stderr}"
    assert "aretes_src_vers_routes" in r.stdout
    assert re.search(r"\b32\b", r.stdout), f"le compte des aretes n'apparait pas : {r.stdout}"


def test_un_seuil_ne_peut_pas_etre_gonfle_sans_justification_ecrite():
    """PREUVE 4 — l'anti-inflation. Le risque principal n'est pas l'oubli, c'est le gonflement.

    Une porte de métrique se contourne en changeant le seuil, pas en contournant
    la mesure. Relever `aretes_src_vers_routes` de 30 à 60 la ferait passer sans
    qu'aucune arête ne soit supprimée — et personne ne le remarquerait, puisque
    la porte est verte.

    Le seuil peut être relevé, parce qu'un chantier peut avancer sagement — mais
    seulement en écrivant **pourquoi**, dans une clé relue comme le reste. Un
    seuil au-dessus de l'état mesuré SANS cette clé est une porte désarmée, et
    c'est exactement ce que ce test refuse.
    """
    m = mod.mesure()
    for cle, seuil in mod.SEUILS.items():
        if seuil["valeur"] <= m[cle]:
            continue
        justification = (seuil.get("releve_si") or "").strip()
        assert justification, (
            f"le seuil {cle} est a {seuil['valeur']} alors que l'etat mesure est {m[cle]} : "
            "un seuil au-dessus de la realite desarme la porte. Remplis `releve_si` avec la "
            "raison, ou remets le seuil a la valeur mesuree."
        )
    # Un seuil ne doit JAMAIS etre superieur a la mesure sans justification.
    # Si seuil == mesure : pas de justification necessaire (etat nominal).
    # Si seuil < mesure : plus strict, acceptable.
    # Si seuil > mesure : DOIT avoir releve_si justifie.
    for k, v in mod.SEUILS.items():
        m_val = mod.mesure()[k]
        s_val = v["valeur"]
        if s_val > m_val:
            # Seuil gonfle : doit avoir une justification releve_si non vide
            assert v.get("releve_si") and (v["releve_si"] or "").strip(), (
                f"le seuil {k} est a {s_val} > {m_val} sans justification releve_si"
            )
        # Si seuil <= mesure : pas de justification necessaire (etat normal ou plus strict)


def test_les_src_imbriques_des_paquets_ne_sont_pas_comptes(tmp_path, monkeypatch):
    """PREUVE 5 — un `src/` imbrique n'est pas le `src/` du dépôt.

    Mutation D5 : passer de « premier niveau » à « le nom apparaît dans le
    chemin » ne cassait rien, parce qu'aucun paquet ne contient de `.py` — donc
    le compte ne bougeait pas. Le jour où un paquet en contiendra un, la
    métrique changera à cause d'un dépôt que la porte ne mesure pas, et personne
    ne saura pourquoi le seuil est soudain faux.

    On crée donc un `packages/*/src/` temporaire qui importe une route, et on
    vérifie qu'il ne compte pas. C'est un défaut qui n'existe pas encore : le
    test le prévient d'exister.
    """
    reel = _mesure_fictive(tmp_path, [])

    paquet = tmp_path / "packages" / "sfd-fictif" / "src" / "module.py"
    paquet.parent.mkdir(parents=True)
    paquet.write_text("from routes.chat_routes import router\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_fichiers_py", lambda: [paquet])

    mesure = _mesure_fictive(tmp_path, [paquet])
    assert mesure == reel, (
        f"un src/ IMBRIQUE (packages/sfd-*/src/) compte comme une violation de couches. "
        f"{reel} -> {mesure}. Le seuil dependrait alors d'un depot que la porte ne mesure pas : "
        "ajouter un `.py` dans un paquet ferait bouger la metrique sans qu'aucune arete "
        "src→routes n'ait change."
    )
