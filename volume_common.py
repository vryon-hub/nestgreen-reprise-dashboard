# -*- coding: utf-8 -*-
"""Aides communes aux scripts qui écrivent volume_data.json / hourly_data.json."""
import json
import os


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    """Écriture atomique : jamais de fichier de données à moitié écrit."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def ensure_index(names, name):
    """Index de `name` dans la liste ; l'ajoute EN FIN si absent (les index déjà
    utilisés par les lignes existantes ne bougent jamais)."""
    try:
        return names.index(name)
    except ValueError:
        names.append(name)
        return len(names) - 1
