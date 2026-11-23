"""Fenêtre de debug : dessine par-dessus l'image caméra ce que le tracker a compris.
Ne fait pas partie du jeu : on peut s'en passer (option --no-window)."""
from __future__ import annotations

import cv2
import numpy as np

import config as C

GREEN, ORANGE, RED, BLACK = (0, 220, 0), (0, 200, 255), (0, 0, 255), (0, 0, 0)


def draw_debug(image, markers: dict, state_builder, now: float):
    picture = image.copy()
    board = state_builder.board

    def write(text, color, y=40):
        """Texte avec un contour noir, lisible sur n'importe quel fond."""
        cv2.putText(picture, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, BLACK, 5, cv2.LINE_AA)
        cv2.putText(picture, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

    # Étape 2 : contour et numéro de chaque marqueur vu (fonction toute faite d'OpenCV).
    if markers:
        corners = [quad.reshape(1, 4, 2).astype(np.float32) for quad in markers.values()]
        ids = np.array([[marker_id] for marker_id in markers], np.int32)
        cv2.aruco.drawDetectedMarkers(picture, corners, ids)

    # Étape 3A : le plateau.
    if not board.ready:
        if board.size_samples:
            write(f"Mesure du plateau... {int(board.measuring_progress * 100)} %  (ne bouge pas les coins)", ORANGE)
        else:
            write(f"Pose les 4 marqueurs de coin (IDs {C.CORNER_IDS})", RED)
        return picture
    cv2.polylines(picture, [board.corners_px.astype(np.int32)], True, GREEN, 2, cv2.LINE_AA)
    write(f"Plateau {board.w:.1f} x {board.h:.1f} cm  (c = remesurer)", GREEN)
    if board.warning:
        write(board.warning, RED, 75)

    # Étape 3B : les cartes (flèche = direction, arc de cercle = charge).
    for card in state_builder.cards.cards.values():
        arrow_tip = (card.x + 5 * card.dx, card.y + 5 * card.dy)
        start, end = board.cm_to_pixels([(card.x, card.y), arrow_tip]).astype(int)
        color = GREEN if card.stable else ORANGE
        cv2.arrowedLine(picture, tuple(start), tuple(end), color, 3, cv2.LINE_AA, tipLength=0.3)
        cv2.ellipse(picture, tuple(start), (28, 28), -90, 0, 360 * card.progress(now), color, 3, cv2.LINE_AA)
        cv2.putText(picture, str(card.id), (start[0] + 32, start[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
                    cv2.LINE_AA)
    return picture
