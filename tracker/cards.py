"""Lecture de godot/cards.json : la liste des familles de cartes, partagée avec Godot."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

CARDS_FILE = Path(__file__).resolve().parent.parent / "godot" / "cards.json"


def load_families() -> list[dict]:
    return json.loads(CARDS_FILE.read_text(encoding="utf-8"))["families"]


def family_for_id(card_id: int, families: list[dict]) -> dict | None:
    """La famille à laquelle appartient un ID (chaque famille a une plage d'IDs)."""
    for family in families:
        if family["first_id"] <= card_id < family["first_id"] + family["count"]:
            return family
    return None


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """'#ff6a1a' -> (255, 106, 26)"""
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def hex_to_bgr(color: str) -> tuple[int, int, int]:
    """OpenCV range les couleurs à l'envers : bleu, vert, rouge."""
    r, g, b = hex_to_rgb(color)
    return b, g, r


def ascii_name(text: str) -> str:
    """Retire les accents (les polices d'OpenCV ne les connaissent pas)."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
