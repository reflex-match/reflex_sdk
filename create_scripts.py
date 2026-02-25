#!/usr/bin/env python3
# coding: utf-8
"""
Convertit récursivement les *.json* contenus dans `format/**`
en fichiers .oris écrits dans `sdk/**` (arborescence conservée).

Types gérés :
  • read   → =fsdk_read(...)
  • write  → =fsdk_write(...)
  • new    → =fsdk_new(...)
  • multi  → fsdk_... \n&\n fsdk_... \n&\n ...   (sans fwpa, ni store)

Comportement spécial (type absent) :
  • si `operations` existe :
      - len > 1 → enchaîne les blocs comme `multi`
      - len = 1 → génère un seul bloc standard (=fsdk_*)

Règles valeurs:
  • &param  → 'param'               (reprend la valeur en base)
  • $param  → $fpar("param")        (valeur reçue dans la requête HTTP)

Règle "ré-ouvrir après $fpar":
  • Sans $fpar → ,json=true&...
  • Avec $fpar → ,="json=true...="$fpar("x")&"…"$fpar("y")&"…"
                  ^——— guillemets rouvrts précédés d’un « & »
"""

import json, shutil, os
from pathlib import Path

ROOT_DIR   = Path(__file__).resolve().parent
FORMAT_DIR = ROOT_DIR / "format"
SDK_DIR    = ROOT_DIR / "sdk"
SCHEMA     = ROOT_DIR / "schema.json"

# ──────────────────────────────────────────────────────────────────────────────
def load_schema() -> dict:
    if not SCHEMA.exists():
        raise FileNotFoundError("schema.json manquant")
    return json.loads(SCHEMA.read_text(encoding="utf-8"))

# ───────────────────────── valeurs LITERAL / & / $ ───────────────────────────
def val_read_to_oris(val):
    if isinstance(val, str):
        if val.startswith("&"):
            return "'{}'".format(val[1:])
        if val.startswith("$"):
            return '$fpar("{}")'.format(val[1:])
    return str(val)

def val_write_new_to_oris(val):
    if isinstance(val, str):
        if val.startswith("&"):
            return "'{}'".format(val[1:])
        if val.startswith("$"):
            return '$fpar("{}")'.format(val[1:])
    return str(val)

# ───────────────────────── helpers d’assemblage de la ligne paramètres ───────
# Chaque élément est soit ('L', texte_litteral) soit ('D', '$fpar("...")')
def _combine_param_segments(segments, *, end_amp: bool=False) -> str:
    has_dyn = any(kind == 'D' for kind, _ in segments)
    if not has_dyn:
        lit = "".join(text for kind, text in segments if kind == 'L')
        if end_amp:
            lit += "&"
        return "," + lit

    out = [",="]
    in_quote = False
    last_was_dyn = False

    def open_q():
        nonlocal in_quote
        if not in_quote:
            out.append('"'); in_quote = True

    def close_q():
        nonlocal in_quote
        if in_quote:
            out.append('"'); in_quote = False

    for kind, text in segments:
        if kind == 'L':
            if not text:
                continue
            if last_was_dyn:
                out.append("&")
            open_q()
            out.append(text)
            last_was_dyn = False
        else:
            close_q()
            out.append(text)
            last_was_dyn = True

    if end_amp:
        if last_was_dyn:
            out.append("&")
            open_q(); out.append("&"); close_q()
        else:
            open_q(); out.append("&"); close_q()
    else:
        close_q()
    return "".join(out)

def _add_value(segments, prefix_lit: str, value_str: str):
    if value_str.startswith("$fpar("):
        if prefix_lit:
            segments.append(('L', prefix_lit))
        segments.append(('D', value_str))
    else:
        segments.append(('L', prefix_lit + value_str))

# ─────────────────────────────── outils communs ──────────────────────────────
def sorted_indices(request_fields, schema_fields, base):
    try:
        return sorted(schema_fields.index(f) for f in request_fields)
    except ValueError as err:
        missing = str(err).split("'")[1]
        raise ValueError(f"Champ « {missing} » absent de la table « {base} »")

def build_filter_segments(filters, schema_fields, base, *, for_write_new: bool):
    if not filters:
        return []
    segs = []
    conv = val_write_new_to_oris if for_write_new else val_read_to_oris
    for field, v in filters.items():
        if field not in schema_fields:
            raise ValueError(f"Champ « {field} » absent de la table « {base} »")
        idx = schema_fields.index(field)
        prefix = f"&fils{idx}==&fil{idx}="
        _add_value(segs, prefix, conv(v))
    return segs

# ───────────────────────────── sous-conversions ──────────────────────────────
def _to_read(op, schema):
    base = op["base"]; fields = op.get("fields", []); filt = op.get("filters", {})
    path = schema[base]["path"]; s_fields = schema[base]["fields"]
    if isinstance(fields, str) and fields.strip() == "*":
        mask = ";".join(map(str, range(len(s_fields))))
    else:
        mask = ";".join(map(str, sorted_indices(fields, s_fields, base)))
    segments = [('L', "json=true")]
    segments += build_filter_segments(filt, s_fields, base, for_write_new=False)
    params_line = _combine_param_segments(segments, end_amp=False)
    return f"fsdk_read(\n{path}\n,{mask}\n{params_line}\n)"

def _to_write(op, schema):
    base, fdict, filt = op["base"], op.get("fields", {}), op.get("filters", {})
    path = schema[base]["path"]; s_fields = schema[base]["fields"]
    # Masque = uniquement les colonnes modifiées
    mask = ";".join(map(str, sorted_indices(fdict.keys(), s_fields, base)))
    segments = [('L', "json=true")]
    for k, v in fdict.items():
        idx = s_fields.index(k)
        _add_value(segments, f"&mch{idx}=", val_write_new_to_oris(v))
    segments += build_filter_segments(filt, s_fields, base, for_write_new=True)
    params_line = _combine_param_segments(segments, end_amp=False)
    return f"fsdk_write(\n{path}\n,{mask}\n{params_line}\n)"

def _to_new(op, schema):
    base, fdict = op["base"], op.get("fields", {})
    path = schema[base]["path"]; s_fields = schema[base]["fields"]
    # 🔁 Changement : masque = uniquement les colonnes modifiées (PAS de 0 automatique)
    mask = ";".join(map(str, sorted_indices(fdict.keys(), s_fields, base)))
    segments = [('L', "json=true")]
    for k, v in fdict.items():
        idx = s_fields.index(k)
        _add_value(segments, f"&mch{idx}=", val_write_new_to_oris(v))
    params_line = _combine_param_segments(segments, end_amp=True)  # NEW → termine par &
    return f"fsdk_new(\n{path}\n,{mask}\n{params_line}\n)"

def op_to_oris(op, schema):
    t = op["type"]
    if t == "read":  return _to_read(op, schema)
    if t == "write": return _to_write(op, schema)
    if t == "new":   return _to_new(op, schema)
    raise ValueError(f"type « {t} » non pris en charge")

# ───────────────────────────── type « multi » (séquence & séparateurs) ──────
def multi_to_oris(data, schema):
    parts = []
    for op in data.get("operations", []):
        inner = op_to_oris(op, schema)
        if inner.startswith("="):
            inner = inner.lstrip("=")
        parts.append(inner)
    return "\n&\n".join(parts)

# ───────────────────────────── conversion fichier ────────────────────────────
def json_file_to_oris(json_path: Path, schema: dict) -> str:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    t = data.get("type")

    if t == "multi":
        return multi_to_oris(data, schema)

    if t is None and isinstance(data.get("operations"), list):
        ops = data["operations"]
        if len(ops) == 0:
            raise ValueError(f"{json_path.name}: 'operations' est vide")
        if len(ops) == 1:
            return "=" + op_to_oris(ops[0], schema)
        return multi_to_oris(data, schema)

    if t == "read":
        return "=" + _to_read(data, schema)
    if t == "write":
        return "=" + _to_write(data, schema)
    if t == "new":
        return "=" + _to_new(data, schema)

    raise ValueError(f"{json_path.name}: type « {t} » non pris en charge")

def mirror_format_tree():
    for root, dirs, files in os.walk(FORMAT_DIR):
        rel_root = Path(root).relative_to(FORMAT_DIR)
        (SDK_DIR / rel_root).mkdir(parents=True, exist_ok=True)
        for file in files:
            src = Path(root) / file
            dst = SDK_DIR / rel_root / file
            if src.suffix.lower() != ".json" and not dst.exists():
                shutil.copy2(src, dst)

# ──────────────────────────────────────────────────────────────────────────────
def main():
    schema = load_schema()
    mirror_format_tree()
    ok = ko = 0
    for json_file in FORMAT_DIR.rglob("*.json"):
        rel = json_file.relative_to(FORMAT_DIR)
        out = (SDK_DIR / rel).with_suffix(".oris")
        try:
            out.write_text(json_file_to_oris(json_file, schema), encoding="utf-8")
            print(f"✓ {json_file} → {out}")
            ok += 1
        except Exception as e:
            print(f"⚠️  {json_file}: ignoré – {e}")
            ko += 1
    print(f"\n✅ Fin : {ok} fichier(s) généré(s), {ko} ignoré(s).")

# if __name__ == "__main__":
#     main()
