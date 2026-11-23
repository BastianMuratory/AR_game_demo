"""ÉTAPE 2 : trouver les marqueurs ArUco dans l'image.

detect(image) renvoie un dictionnaire {id du marqueur: ses 4 coins en pixels}, par exemple
    {0: [[x, y], [x, y], [x, y], [x, y]], 12: ...}
Les 4 coins sont dans l'ordre : haut-gauche, haut-droit, bas-droit, bas-gauche du marqueur
IMPRIMÉ (donc ils tournent avec la carte). Un marqueur qu'on ne voit pas n'est pas dans le dictionnaire.

Ce fichier ne sait rien du plateau ni des cartes : il ne fait que "voir".
"""
from __future__ import annotations

import cv2

import config as C

# La famille de marqueurs utilisée partout (impression, simulation, détection).
DICTIONARY = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, C.ARUCO_DICT))


class MarkerDetector:
    def __init__(self):
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX  # coins plus précis
        self.detector = cv2.aruco.ArucoDetector(DICTIONARY, params)

    def detect(self, image) -> dict:
        corners, ids, _rejected = self.detector.detectMarkers(image)
        if ids is None:
            return {}
        return {int(marker_id): quad.reshape(4, 2) for marker_id, quad in zip(ids.flatten(), corners)}


def marker_image(marker_id: int, size_px: int):
    """Image noir et blanc d'un marqueur (pour l'impression et la simulation)."""
    return cv2.aruco.generateImageMarker(DICTIONARY, marker_id, size_px)
