"""Caméra simulée : une table vue un peu de biais, avec de vrais marqueurs ArUco dessinés dessus.

L'image passe par EXACTEMENT le même code de détection que la vraie caméra : ça permet de
tout tester sans rien imprimer (sauf l'éclairage).

Souris (dans la fenêtre caméra) :
  clic gauche sur le vide   -> pose une nouvelle carte de la famille choisie
  clic gauche + glisser     -> déplace une carte
  clic droit                -> retire la carte la plus proche
Clavier : 1/2/3 famille · a/e tourner la carte choisie · x tout retirer
"""
from __future__ import annotations

import math
import time

import cv2
import numpy as np

import config as C
from cards import ascii_name, family_for_id, hex_to_bgr, load_families
from step2_detect import marker_image

PX = 12                      # pixels par cm sur la "table" dessinée
MARGIN = 10.0                # cm de table autour du plateau
CARD_W, CARD_H = 6.3, 8.8    # taille d'une carte (cm)
MARKER_CM = 4.0              # taille du marqueur imprimé sur la carte
CAM_W, CAM_H = 1280, 720
# Où sont "vraiment" posés les 4 coins sur la table (cm) : pas tout à fait en rectangle exprès.
SIM_CORNERS = [(0.0, 0.0), (60.0, 0.4), (60.6, 40.3), (-0.3, 39.8)]
# Où la table apparaît dans l'image de la caméra (le téléphone filme un peu de biais).
TABLE_IN_IMAGE = [[150, 30], [1150, 55], [1235, 700], [60, 680]]


class SimCamera:
    def __init__(self, demo=False):
        self.demo = demo
        self.families = load_families()
        self.family_index = 0
        self.cards = {}          # id -> {"x", "y", "angle"} (cm, degrés)
        self.placed_at = {}      # id -> heure de pose (mode démo)
        self.selected = None     # carte qu'on tient à la souris
        self.dragging = False
        self.rng = np.random.default_rng(1)
        self.start_time = time.monotonic()
        self.next_demo_card = 1.0
        self.last_frame_time = 0.0

        # Taille de la table dessinée (plateau + marge tout autour).
        self.origin = np.float32(SIM_CORNERS).min(axis=0)
        self.W, self.H = np.float32(SIM_CORNERS).max(axis=0) - self.origin
        self.table_size = (int((self.W + 2 * MARGIN) * PX), int((self.H + 2 * MARGIN) * PX))
        self.table = self.draw_table()

        # Homographie "table dessinée -> image caméra" (et l'inverse, pour la souris).
        tw, th = self.table_size
        self.to_image = cv2.getPerspectiveTransform(np.float32([[0, 0], [tw, 0], [tw, th], [0, th]]),
                                                    np.float32(TABLE_IN_IMAGE))
        self.to_table = np.linalg.inv(self.to_image)

    # --------------------------------------------------------------- dessin
    def to_pixels(self, x_cm, y_cm):
        """Position sur la table (cm) -> pixel de la table dessinée."""
        return (int(round((x_cm - self.origin[0] + MARGIN) * PX)),
                int(round((y_cm - self.origin[1] + MARGIN) * PX)))

    def draw_table(self):
        tw, th = self.table_size
        table = np.full((th, tw, 3), (60, 95, 140), np.uint8)                   # bois
        table = cv2.add(table, self.rng.integers(0, 8, table.shape, dtype=np.uint8))  # un peu de grain
        corners = np.int32([self.to_pixels(x, y) for x, y in SIM_CORNERS])
        cv2.fillPoly(table, [corners], (55, 80, 45))                             # tapis vert
        cv2.line(table, tuple((corners[0] + corners[1]) // 2), tuple((corners[2] + corners[3]) // 2),
                 (90, 120, 80), 2)                                               # ligne du milieu
        for marker_id, (x, y) in zip(C.CORNER_IDS, SIM_CORNERS):
            self.paste_marker(table, marker_id, x, y, C.CORNER_MARKER_CM)
        return table

    def paste_marker(self, image, marker_id, x_cm, y_cm, size_cm):
        """Colle un marqueur (avec sa marge blanche) centré sur (x, y)."""
        size = int(size_cm * PX)
        border = int(0.8 * PX)
        cx, cy = self.to_pixels(x_cm, y_cm)
        x0, y0 = cx - size // 2, cy - size // 2
        cv2.rectangle(image, (x0 - border, y0 - border), (x0 + size + border, y0 + size + border), (235, 235, 235), -1)
        image[y0:y0 + size, x0:x0 + size] = cv2.cvtColor(marker_image(marker_id, size), cv2.COLOR_GRAY2BGR)

    def card_image(self, card_id):
        """Image d'une carte vue de dessus (flèche vers le haut) et position du centre de son marqueur."""
        family = family_for_id(card_id, self.families) or self.families[0]
        color = hex_to_bgr(family["color"])
        w, h = int(CARD_W * PX), int(CARD_H * PX)
        card = np.full((h, w, 3), 240, np.uint8)
        cv2.rectangle(card, (0, 0), (w - 1, int(1.3 * PX)), color, -1)
        cv2.putText(card, ascii_name(family["name"]), (4, PX), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (255, 255, 255), 1)
        size = int(MARKER_CM * PX)
        mx, my = (w - size) // 2, 3 * PX
        card[my:my + size, mx:mx + size] = cv2.cvtColor(marker_image(card_id, size), cv2.COLOR_GRAY2BGR)
        arrow = np.int32([[w // 2, int(1.5 * PX)], [w // 2 - 8, int(2.3 * PX)], [w // 2 + 8, int(2.3 * PX)]])
        cv2.fillPoly(card, [arrow], color)
        return card, (mx + size / 2, my + size / 2)

    def draw_cards(self, table):
        tw, th = self.table_size
        for card_id, c in self.cards.items():
            card, (mcx, mcy) = self.card_image(card_id)
            # Tourner la carte autour du centre de son marqueur, puis la déplacer à sa place.
            # (angle 0 = vers la droite ; sur l'image de la carte, la flèche pointe vers le haut)
            move = cv2.getRotationMatrix2D((mcx, mcy), -90.0 - c["angle"], 1.0)
            tx, ty = self.to_pixels(c["x"], c["y"])
            move[:, 2] += (tx - mcx, ty - mcy)
            placed = cv2.warpAffine(card, move, (tw, th))
            mask = cv2.warpAffine(np.full(card.shape[:2], 255, np.uint8), move, (tw, th)) > 127
            table[mask] = placed[mask]

    def read(self):
        """Même interface qu'une vraie caméra : renvoie (True, image)."""
        wait = 1 / 30 - (time.monotonic() - self.last_frame_time)  # environ 30 images par seconde
        if wait > 0:
            time.sleep(wait)
        self.last_frame_time = time.monotonic()
        if self.demo:
            self.demo_step(self.last_frame_time - self.start_time)
        table = self.table.copy()
        self.draw_cards(table)
        image = cv2.warpPerspective(table, self.to_image, (CAM_W, CAM_H), borderValue=(35, 35, 35))
        image = cv2.GaussianBlur(image, (3, 3), 0)  # un peu de flou, comme une vraie caméra
        return True, image

    # --------------------------------------------------------------- démo automatique
    def demo_step(self, t):
        """Pose et retire des cartes tout seul."""
        family_type = lambda cid: family_for_id(cid, self.families)["type"]
        # Les sorts sont "repris en main" au bout de 2,5 s (les tours et les bases restent).
        for card_id in [c for c, t0 in self.placed_at.items() if t - t0 > 2.5 and family_type(c) not in ("tower", "base")]:
            self.cards.pop(card_id, None)
            del self.placed_at[card_id]
        if t < self.next_demo_card:
            return
        self.next_demo_card = t + self.rng.uniform(1.2, 2.2)

        # Pour commencer, chaque joueur pose sa base près de son bord du plateau.
        bases = [f for f in self.families if f["type"] == "base"]
        if bases and not any(family_type(c) == "base" for c in self.cards):
            first = bases[0]["first_id"]
            self.cards[first] = {"x": 6.0, "y": self.H / 2, "angle": 0.0}
            self.cards[first + 1] = {"x": self.W - 6.0, "y": self.H / 2, "angle": 180.0}
            self.placed_at[first] = self.placed_at[first + 1] = t
            return

        towers = [c for c in self.cards if family_type(c) == "tower"]
        if len(towers) >= 2:  # pas plus de 2 tours : on retire la plus ancienne
            oldest = min(towers, key=lambda c: self.placed_at.get(c, 0))
            self.cards.pop(oldest)
            self.placed_at.pop(oldest, None)

        # Ensuite : surtout des boules de feu, parfois une tour (jamais de nouvelle base).
        playable = [i for i, f in enumerate(self.families) if f["type"] != "base"]
        weights = [0.7 if self.families[i]["type"] == "fireball" else 0.3 for i in playable]
        self.family_index = int(self.rng.choice(playable, p=np.array(weights) / sum(weights)))
        card_id = self.free_id()
        if card_id is None:
            return
        left = self.rng.random() < 0.5  # joueur de gauche ou de droite
        x = self.rng.uniform(12, self.W / 2 - 4) if left else self.rng.uniform(self.W / 2 + 4, self.W - 12)
        y = self.rng.uniform(6, self.H - 6)
        enemy_x = self.W - 6 if left else 6  # la carte vise la forteresse d'en face
        angle = math.degrees(math.atan2(self.H / 2 - y, enemy_x - x)) + self.rng.normal(0, 6)
        self.cards[card_id] = {"x": float(x), "y": float(y), "angle": float(angle)}
        self.placed_at[card_id] = t

    # --------------------------------------------------------------- souris et clavier
    def free_id(self):
        """Premier ID libre dans la famille choisie."""
        family = self.families[self.family_index]
        for card_id in range(family["first_id"], family["first_id"] + family["count"]):
            if card_id not in self.cards:
                return card_id
        return None

    def nearest_card(self, x, y, max_distance=5.0):
        close = [(math.dist((c["x"], c["y"]), (x, y)), cid) for cid, c in self.cards.items()]
        close = [item for item in close if item[0] < max_distance]
        return min(close)[1] if close else None

    def on_mouse(self, event, u, v, _flags, _param):
        # pixel de l'image caméra -> cm sur la table
        px, py = cv2.perspectiveTransform(np.float32([[[u, v]]]), self.to_table)[0, 0]
        x, y = px / PX - MARGIN + self.origin[0], py / PX - MARGIN + self.origin[1]

        if event == cv2.EVENT_LBUTTONDOWN:
            card_id = self.nearest_card(x, y, 3.5)
            if card_id is None:  # clic dans le vide : nouvelle carte
                card_id = self.free_id()
                if card_id is None:
                    return
                self.cards[card_id] = {"x": x, "y": y, "angle": 0.0 if x < self.W / 2 else 180.0}
            self.selected, self.dragging = card_id, True
        elif event == cv2.EVENT_MOUSEMOVE and self.dragging and self.selected in self.cards:
            self.cards[self.selected].update(x=x, y=y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.dragging = False
        elif event == cv2.EVENT_RBUTTONDOWN:
            card_id = self.nearest_card(x, y)
            if card_id is not None:
                del self.cards[card_id]

    def on_key(self, key):
        letter = chr(key)
        if letter in "123":
            self.family_index = min(int(letter) - 1, len(self.families) - 1)
        elif letter in "ae" and self.selected in self.cards:
            self.cards[self.selected]["angle"] += -15 if letter == "a" else 15
        elif letter == "x":
            self.cards.clear()

    def draw_help(self, image):
        family = ascii_name(self.families[self.family_index]["name"])
        lines = [f"SIMULATION - famille: {family} (1/2/3 pour changer)",
                 "clic: poser/deplacer  clic droit: retirer  a/e: tourner  x: tout retirer  Echap: quitter"]
        for i, line in enumerate(lines):
            y = CAM_H - 40 + i * 24
            cv2.putText(image, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(image, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
