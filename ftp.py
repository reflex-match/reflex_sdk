#!/usr/bin/env python3
"""
Synchronise uniquement les fichiers *.oris du dossier local ./sdk vers
/Reflex/www/doc_Reflex/1_Data/sdk sur kaizis.com.

• Les fichiers *.oris existants côté FTP sont écrasés.
• Les autres fichiers (PDF, images, etc.) ne sont pas envoyés.
"""

import os
from ftplib import FTP, error_perm
from pathlib import PurePosixPath
from typing import List

# ── PARAMÈTRES DE CONNEXION ───────────────────────────────────────────────────
HOST       = "kaizis.com"
USER       = "swann.williame"
PASSWORD   = "swa74321"
PORT       = 14148
TIMEOUT    = 15  # secondes pour connecter
# ──────────────────────────────────────────────────────────────────────────────

# ── CHEMINS ───────────────────────────────────────────────────────────────────
LOCAL_DIR  = "sdk"  # dossier local à transférer (relatif au cwd)
REMOTE_DIR = "/Reflex/www/doc_Reflex/1_Data/sdk"  # dossier racine distant
# ──────────────────────────────────────────────────────────────────────────────


def ensure_remote_path(ftp: FTP, remote_path: str) -> None:
    """
    Garantit que `remote_path` existe côté serveur.
    Crée récursivement les dossiers manquants puis se positionne dedans.
    """
    ftp.cwd("/")  # on part de la racine
    for part in PurePosixPath(remote_path).parts:
        if not part or part == "/":
            continue
        try:
            ftp.cwd(part)
        except error_perm:
            ftp.mkd(part)
            ftp.cwd(part)


def upload_file(ftp: FTP, local_file: str, remote_filename: str) -> None:
    """Envoie un fichier en écrasant la version distante si elle existe."""
    with open(local_file, "rb") as f:
        ftp.storbinary(f"STOR {remote_filename}", f)


def upload_directory(local_root: str, remote_root: str, ftp: FTP) -> None:
    """
    Parcourt récursivement local_root et envoie tous les *.oris
    sous remote_root (écrase les fichiers existants).
    """
    for dirpath, _, filenames in os.walk(local_root):
        # Sous-chemin relatif (peut être ".")
        rel_path = os.path.relpath(dirpath, local_root)
        remote_path = (
            remote_root
            if rel_path == "."
            else f"{remote_root}/{rel_path.replace(os.sep, '/')}"
        )

        # Filtre les fichiers *.oris
        oris_files = [fn for fn in filenames if fn.lower().endswith(".oris")]
        if not oris_files:
            # Aucun fichier .oris ici : on passe au répertoire suivant
            continue

        # S'assure que le dossier existe côté FTP
        ensure_remote_path(ftp, remote_path)

        # Envoie les fichiers *.oris
        for filename in oris_files:
            local_file = os.path.join(dirpath, filename)
            print(f"→ {local_file}  ⇒  {remote_path}/{filename}")
            upload_file(ftp, local_file, filename)


def main() -> None:
    if not os.path.isdir(LOCAL_DIR):
        print(f"[ERREUR] Dossier local '{LOCAL_DIR}' introuvable.")
        return

    try:
        ftp = FTP()
        print(f"Connexion à {HOST}:{PORT} …")
        ftp.connect(host=HOST, port=PORT, timeout=TIMEOUT)
        ftp.login(user=USER, passwd=PASSWORD)
        ftp.set_pasv(True)

        print(
            f"Synchronisation des fichiers *.oris de '{LOCAL_DIR}' → '{REMOTE_DIR}' "
            "(les fichiers existants seront remplacés)…"
        )
        upload_directory(LOCAL_DIR, REMOTE_DIR, ftp)

        print("Transfert terminé, fermeture de la session.")
        ftp.quit()

    except error_perm as e:
        print(f"[FTP] Erreur : {e}")
    except OSError as e:
        print(f"[Réseau] Erreur : {e}")


if __name__ == "__main__":
    main()
