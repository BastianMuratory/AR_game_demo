"""ÉTAPE 3 : transformer les marqueurs vus (en pixels) en état du jeu (en cm).

Deux parties :
  A. Board : le plateau. Les 4 marqueurs de coin donnent la correspondance
     "pixels de l'image <-> cm sur la table" (une homographie, calculée par OpenCV).
     On en déduit aussi où se trouve la caméra, pour que Godot place la sienne au même endroit.
  B. CardTracker : les cartes. Chaque autre marqueur est converti en cm, lissé et suivi
     dans le temps (posée, en charge, jouée, retirée).

L'état envoyé à Godot ressemble à ça :
    {"type": "state", "calibrated": True, "board": {"w": 60.0, "h": 40.0}, "camera": {...},
     "cards": [{"id": 12, "x": 31.2, "y": 18.5, "angle": -4.0, "stable": True, "progress": 1.0}]}

    x, y   : position en cm (0, 0 = coin haut-gauche, y vers le bas)
    angle  : direction de la flèche de la carte, en degrés (0 = vers la droite, 90 = vers le bas)
    stable : la carte est restée immobile assez longtemps : elle est "jouée"
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

import config as C


class StateBuilder:
    """Point d'entrée de l'étape 3 : update(marqueurs) -> état."""

    def __init__(self):
        self.board = Board()
        self.cards = CardTracker()

    def update(self, markers: dict, now: float, image_size: tuple[int, int]) -> dict:
        self.board.update(markers, image_size)          # A. où est le plateau dans l'image ?
        cards_cm = self.cards_in_cm(markers) if self.board.ready else {}
        self.cards.update(cards_cm, now)                # B. où sont les cartes ?
        return {
            "type": "state",
            "calibrated": self.board.ready,
            "board": {"w": round(self.board.w, 2), "h": round(self.board.h, 2)} if self.board.measured else None,
            "camera": self.board.camera,
            "cards": [card.to_dict(now) for card in self.cards.cards.values()],
        }

    def cards_in_cm(self, markers: dict) -> dict:
        """Marqueurs de carte en cm : {id: (x, y, angle)}."""
        result = {}
        for marker_id, corners_px in markers.items():
            if marker_id in C.CORNER_IDS:
                continue
            corners = self.board.pixels_to_cm(corners_px)
            center = corners.mean(axis=0)
            top_middle = (corners[0] + corners[1]) / 2   # milieu du bord "haut" du marqueur = la flèche
            dx, dy = top_middle - center
            angle = math.degrees(math.atan2(dy, dx))
            x, y = center
            m = C.OUTSIDE_MARGIN_CM
            if -m <= x <= self.board.w + m and -m <= y <= self.board.h + m:  # sinon : trop loin, ignoré
                result[marker_id] = (float(x), float(y), angle)
        return result

    def video_frame(self, image):
        """L'image entière de la caméra, pour Godot (réduite si elle est trop large)."""
        h, w = image.shape[:2]
        if w <= C.VIDEO_MAX_WIDTH:
            return image
        new_size = (C.VIDEO_MAX_WIDTH, round(h * C.VIDEO_MAX_WIDTH / w))
        return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)

    def top_view(self, image):
        """Le plateau vu de dessus, "redressé" (fenêtre de debug, touche p)."""
        size = (round(self.board.w * C.PX_PER_CM), round(self.board.h * C.PX_PER_CM))
        scale = np.diag([C.PX_PER_CM, C.PX_PER_CM, 1.0])  # cm -> pixels de la vue
        return cv2.warpPerspective(image, scale @ self.board.px_to_cm, size)


# ----------------------------------------------------------------------------
# A. Le plateau
# ----------------------------------------------------------------------------
class Board:
    def __init__(self):
        self.reset()

    def reset(self):
        """Oublie la mesure du plateau (touche c) : à refaire si tu déplaces les coins."""
        self.w = self.h = 0.0           # taille du plateau (cm)
        self.size_samples = []          # mesures de (largeur, hauteur), une par image
        self.corners_px = None          # centres des 4 coins dans l'image (pixels, lissés)
        self.px_to_cm = None            # homographie pixels -> cm
        self.cm_to_px = None            # homographie cm -> pixels
        self.camera = None              # où est la caméra (envoyé à Godot)
        self.warning = ""
        if C.BOARD_W_CM and C.BOARD_H_CM:  # taille forcée dans config.py
            self.w, self.h = float(C.BOARD_W_CM), float(C.BOARD_H_CM)

    @property
    def measured(self) -> bool:
        """On connaît la taille du plateau."""
        return self.w > 0

    @property
    def ready(self) -> bool:
        """On sait convertir des pixels en cm."""
        return self.px_to_cm is not None

    @property
    def measuring_progress(self) -> float:
        return len(self.size_samples) / C.CALIBRATION_FRAMES

    def corners_cm(self):
        """Les 4 coins du plateau en cm, dans l'ordre haut-gauche, haut-droit, bas-droit, bas-gauche."""
        return np.float32([[0, 0], [self.w, 0], [self.w, self.h], [0, self.h]])

    def update(self, markers: dict, image_size):
        if not all(cid in markers for cid in C.CORNER_IDS):
            return  # un coin est caché (une main...) : on garde la position d'avant

        # 1. Position des 4 coins dans l'image, lissée pour éviter que le plateau tremble.
        corners = np.float32([markers[cid].mean(axis=0) for cid in C.CORNER_IDS])
        camera_moved = self.corners_px is None or np.abs(corners - self.corners_px).max() > C.CORNER_JUMP_PX
        if camera_moved:
            self.corners_px = corners
        else:
            self.corners_px += C.CORNER_SMOOTHING * (corners - self.corners_px)

        # 2. Taille du plateau : mesurée sur plusieurs images, puis on garde la médiane.
        if not self.measured:
            self.size_samples.append(measure_board_size(markers))
            if len(self.size_samples) < C.CALIBRATION_FRAMES:
                return
            self.w, self.h = (float(v) for v in np.median(self.size_samples, axis=0))
            print(f"[plateau] Mesuré : {self.w:.1f} x {self.h:.1f} cm (touche c pour remesurer)")
            if cv2.contourArea(self.corners_px, oriented=True) < 0:
                self.warning = "Coins dans le mauvais ordre ? Verifie les IDs 0-1-2-3"

        # 3. Correspondance pixels <-> cm (OpenCV calcule l'homographie à partir des 4 coins).
        self.px_to_cm = cv2.getPerspectiveTransform(self.corners_px, self.corners_cm())
        self.cm_to_px = np.linalg.inv(self.px_to_cm)

        # 4. Où est la caméra ? (pour aligner la caméra 3D de Godot sur la vidéo)
        self.camera = find_camera(self.corners_cm(), self.corners_px, image_size)

    def pixels_to_cm(self, points):
        return cv2.perspectiveTransform(np.float32(points).reshape(-1, 1, 2), self.px_to_cm).reshape(-1, 2)

    def cm_to_pixels(self, points):
        return cv2.perspectiveTransform(np.float32(points).reshape(-1, 1, 2), self.cm_to_px).reshape(-1, 2)


def measure_board_size(markers: dict) -> tuple[float, float]:
    """Largeur et hauteur du plateau (cm), grâce à la taille connue des marqueurs de coin.

    Chaque coin est un carré de CORNER_MARKER_CM de côté posé sur la table : à lui seul, il
    donne la correspondance pixels -> cm. On s'en sert pour mesurer les côtés du plateau,
    et on fait la moyenne des 4 mesures (une par coin).
    """
    s = C.CORNER_MARKER_CM / 2
    square_cm = np.float32([[-s, -s], [s, -s], [s, s], [-s, s]])
    centers_px = np.float32([markers[cid].mean(axis=0) for cid in C.CORNER_IDS]).reshape(-1, 1, 2)
    widths, heights = [], []
    for cid in C.CORNER_IDS:
        marker_px_to_cm = cv2.getPerspectiveTransform(np.float32(markers[cid]), square_cm)
        tl, tr, br, bl = cv2.perspectiveTransform(centers_px, marker_px_to_cm).reshape(-1, 2)
        widths.append((np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2)   # haut et bas
        heights.append((np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2)  # gauche et droite
    return float(np.mean(widths)), float(np.mean(heights))


def find_camera(corners_cm, corners_px, image_size):
    """Position et orientation de la caméra, vues depuis le plateau.

    Repère du plateau : x vers la droite, y vers le bas du plateau, z vers le BAS (dans la
    table), en cm. cv2.solvePnP retrouve la caméra à partir des 4 coins (points connus en cm
    ET vus en pixels).
    """
    w, h = image_size
    focal = (w / 2) / math.tan(math.radians(C.CAMERA_HFOV_DEG) / 2)   # focale en pixels
    camera_matrix = np.array([[focal, 0, w / 2], [0, focal, h / 2], [0, 0, 1]])
    points_3d = np.hstack([corners_cm, np.zeros((4, 1), np.float32)])  # le plateau est à z = 0

    ok, rotation_vec, position_vec = cv2.solvePnP(points_3d, corners_px, camera_matrix, None,
                                                  flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        return None
    rotation, _ = cv2.Rodrigues(rotation_vec)          # plateau -> caméra
    camera_pos = (-rotation.T @ position_vec).ravel()  # centre de la caméra dans le repère plateau
    if camera_pos[2] > 0:
        return None  # caméra "sous" la table : les coins sont dans le mauvais ordre

    # Petite correction 2D : la caméra calculée ne retombe jamais PILE sur les 4 coins (focale
    # approximative, plateau pas parfaitement rectangle). On envoie à Godot l'homographie qui
    # ramène les coins vus sur les coins calculés, en coordonnées d'écran de 0 à 1.
    projected, _ = cv2.projectPoints(points_3d, rotation_vec, position_vec, camera_matrix, None)
    size = np.float32([w, h])
    warp = cv2.getPerspectiveTransform(corners_px / size, projected.reshape(-1, 2).astype(np.float32) / size)

    return {
        "pos": camera_pos.round(3).tolist(),
        "right": rotation[0].round(5).tolist(),    # axes de la caméra (droite, bas, avant)
        "down": rotation[1].round(5).tolist(),     # dans le repère du plateau
        "forward": rotation[2].round(5).tolist(),
        "fov_y": round(math.degrees(2 * math.atan(h / 2 / focal)), 3),  # champ de vision vertical
        "warp": (warp / warp[2, 2]).round(7).ravel().tolist(),
    }


# ----------------------------------------------------------------------------
# B. Les cartes
# ----------------------------------------------------------------------------
@dataclass
class Card:
    id: int
    x: float               # position lissée (cm)
    y: float
    dx: float              # direction lissée (vecteur de longueur 1)
    dy: float
    charge_start: float    # moment où la carte a commencé à se charger
    last_seen: float
    anchor: tuple          # position au début de la charge
    stable: bool = False   # True = la carte est jouée

    def progress(self, now) -> float:
        """Charge de 0 à 1."""
        return 1.0 if self.stable else min(1.0, (now - self.charge_start) / C.STABLE_TIME)

    def to_dict(self, now) -> dict:
        return {"id": self.id, "x": round(self.x, 2), "y": round(self.y, 2),
                "angle": round(math.degrees(math.atan2(self.dy, self.dx)), 1),
                "stable": self.stable, "progress": round(self.progress(now), 2)}


class CardTracker:
    def __init__(self):
        self.cards: dict[int, Card] = {}

    def update(self, seen: dict, now: float):
        for card_id, (x, y, angle) in seen.items():
            self.observe(card_id, x, y, angle, now)
        # cartes qu'on ne voit plus depuis trop longtemps : retirées
        for card_id in list(self.cards):
            if now - self.cards[card_id].last_seen > C.LOST_TIMEOUT:
                del self.cards[card_id]

    def observe(self, card_id, x, y, angle, now):
        dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        card = self.cards.get(card_id)
        if card is None:  # nouvelle carte
            self.cards[card_id] = Card(card_id, x, y, dx, dy, now, now, anchor=(x, y))
            return

        # Lissage : on avance un peu vers la nouvelle mesure (évite les tremblements).
        a = C.SMOOTHING
        card.x += a * (x - card.x)
        card.y += a * (y - card.y)
        # On lisse la direction (et pas l'angle) pour éviter le saut de -180° à +180°.
        card.dx += a * (dx - card.dx)
        card.dy += a * (dy - card.dy)
        length = math.hypot(card.dx, card.dy) or 1.0
        card.dx, card.dy = card.dx / length, card.dy / length
        card.last_seen = now

        if not card.stable:
            if math.dist((x, y), card.anchor) > C.STILL_TOLERANCE_CM:
                card.charge_start, card.anchor = now, (x, y)  # elle bouge encore : la charge recommence
            elif now - card.charge_start >= C.STABLE_TIME:
                card.stable = True
