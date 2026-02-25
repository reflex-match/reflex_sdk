#!/usr/bin/env python3
# coding: utf-8
"""
Met à jour le fichier schema.json à partir des fichiers .ini du dossier bd/.

- La clé de chaque table = valeur de 'titre' dans la section [PARAM].
- Le chemin utilisé = "doc_reflex/1_data/bd/<nom_fichier>.ini".
- Les champs = toutes les valeurs ‘*_name’ de la section [CHAMPS] (dans l’ordre).
"""

import json
import re
from pathlib import Path

# --- Réglages -----------------------------------------------------------------

# Dossier contenant les .ini à analyser
BD_DIR = Path("bd")

# Chemin du fichier JSON à maintenir
SCHEMA_JSON = Path("schema.json")

# Préfixe fixe du chemin à écrire dans le JSON
PATH_PREFIX = "doc_reflex/1_data/bd/"

# -----------------------------------------------------------------------------


def extract_table_info(ini_path: Path) -> tuple[str, list[str]]:
    """Extrait (titre, [liste_champs]) depuis un fichier .ini."""
    titre = None
    champs: list[str] = []

    with ini_path.open(encoding="utf-8") as f:
        lines = f.readlines()

    # Trouver le titre
    for line in lines:
        if line.strip().startswith("titre"):
            titre = line.split("=", 1)[1].strip()
            break

    # Trouver la section [CHAMPS]
    try:
        start = lines.index("[CHAMPS]\n") + 1
    except ValueError:
        raise ValueError(f"Section [CHAMPS] manquante dans {ini_path}")

    for line in lines[start:]:
        if line.startswith("["):
            break
        m = re.match(r"\s*\d+_name\s*=\s*(.+)", line)
        if m:
            champs.append(m.group(1).strip())

    if not titre:
        raise ValueError(f"Champ 'titre' manquant dans {ini_path}")

    return titre, champs


def main() -> None:
    # On vide le contenu précédent → on repart toujours de zéro
    schema = {}

    # Parcourir tous les .ini
    for ini_file in BD_DIR.glob("*.ini"):
        titre, champs = extract_table_info(ini_file)
        schema[titre] = {
            "path": f"{PATH_PREFIX}{ini_file.name}",
            "fields": champs,
        }
        print(f"✓ {titre} ({ini_file.name}) ajouté·e – {len(champs)} champs")

    # Sauvegarder en écrasant le fichier (vide + réécriture complète)
    with SCHEMA_JSON.open("w", encoding="utf-8") as f:
        json.dump(schema, f, indent=4, ensure_ascii=False)

    print(f"\n✅ schema.json réécrit ({len(schema)} table(s)).")


if __name__ == "__main__":
    main()
