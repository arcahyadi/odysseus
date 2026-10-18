"""
Hash-anchored edit validator.

Calcule un hash SHA256 du contenu original d'un fichier avant édition,
puis vérifie ce hash avant d'appliquer une modification.
Si le fichier a changé entre-temps, la modification est rejetée.

Usage :
    from src.hash_edit_validator import compute_file_hash, validate_and_edit

    # Avant édition : capturer le hash
    original_hash = compute_file_hash("src/my_file.py")

    # Plus tard, appliquer la modification de façon sécurisée
    result = validate_and_edit("src/my_file.py", original_hash, new_content)
    if not result["success"]:
        print("Conflit :", result["error"])
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def compute_file_hash(path: str | Path) -> str:
    """
    Calcule le hash SHA256 du contenu d'un fichier.

    Paramètres
    ----------
    path : str | Path
        Chemin vers le fichier à hasher.

    Retourne
    --------
    str
        Hex-digest SHA256 du contenu binaire du fichier.

    Lève
    ----
    FileNotFoundError
        Si le fichier n'existe pas.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {file_path}")

    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def validate_and_edit(
    path: str | Path,
    original_hash: str,
    new_content: str,
    encoding: str = "utf-8",
) -> dict:
    """
    Valide le hash courant du fichier puis écrit le nouveau contenu.

    Paramètres
    ----------
    path : str | Path
        Chemin vers le fichier à modifier.
    original_hash : str
        Hash SHA256 attendu (capturé avant la modification).
    new_content : str
        Nouveau contenu à écrire dans le fichier.
    encoding : str
        Encodage pour l'écriture (défaut : utf-8).

    Retourne
    --------
    dict avec les clés :
        success (bool)  : True si l'écriture a eu lieu.
        error (str)     : Message d'erreur si success=False, sinon "".
        path (str)      : Chemin absolu du fichier.
        new_hash (str)  : Hash du contenu écrit (si success=True).
    """
    file_path = Path(path).resolve()

    # --- Vérification existence ---
    if not file_path.exists():
        return {
            "success": False,
            "error": f"Fichier introuvable : {file_path}",
            "path": str(file_path),
            "new_hash": "",
        }

    # --- Vérification du hash ---
    current_hash = compute_file_hash(file_path)
    if current_hash != original_hash:
        return {
            "success": False,
            "error": (
                f"Conflit de hash : le fichier a été modifié depuis la capture du hash. "
                f"Attendu={original_hash[:12]}… Actuel={current_hash[:12]}…"
            ),
            "path": str(file_path),
            "new_hash": "",
        }

    # --- Écriture ---
    try:
        file_path.write_text(new_content, encoding=encoding)
    except OSError as exc:
        return {
            "success": False,
            "error": f"Erreur d'écriture : {exc}",
            "path": str(file_path),
            "new_hash": "",
        }

    new_hash = compute_file_hash(file_path)
    return {
        "success": True,
        "error": "",
        "path": str(file_path),
        "new_hash": new_hash,
    }


def safe_edit_workflow(
    path: str | Path,
    transform,
    encoding: str = "utf-8",
) -> dict:
    """
    Workflow complet : lit le fichier, applique une transformation, réécrit.

    Paramètres
    ----------
    path : str | Path
        Chemin vers le fichier.
    transform : callable(str) -> str
        Fonction qui reçoit le contenu actuel et retourne le nouveau contenu.
    encoding : str
        Encodage du fichier.

    Retourne
    --------
    dict identique à validate_and_edit().
    """
    file_path = Path(path)

    try:
        original_hash = compute_file_hash(file_path)
        current_content = file_path.read_text(encoding=encoding)
    except FileNotFoundError as exc:
        return {
            "success": False,
            "error": str(exc),
            "path": str(file_path.resolve()),
            "new_hash": "",
        }

    try:
        new_content = transform(current_content)
    except Exception as exc:
        return {
            "success": False,
            "error": f"Erreur dans la fonction transform : {exc}",
            "path": str(file_path.resolve()),
            "new_hash": "",
        }

    return validate_and_edit(file_path, original_hash, new_content, encoding=encoding)
