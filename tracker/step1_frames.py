"""ÉTAPE 1 : récupérer les images de la caméra.

open_camera(...) renvoie un objet avec une méthode read() qui donne une image (ou None).

Iriun installe une "webcam virtuelle" sur le PC : le téléphone envoie sa vidéo à l'appli
Iriun du PC, qui la présente à Windows comme une webcam ordinaire. On la retrouve par son nom.
"""
from __future__ import annotations

import platform

import cv2


class Camera:
    """Une vraie caméra (cv2.VideoCapture) ou la table simulée, avec la même méthode read()."""

    def __init__(self, source, is_sim=False):
        self.source = source
        self.is_sim = is_sim
        self.misses = 0  # nombre d'images ratées d'affilée

    def read(self):
        """Renvoie la dernière image (tableau numpy BGR), ou None si la caméra n'a rien donné."""
        ok, frame = self.source.read()
        if ok:
            self.misses = 0
            return frame
        self.misses += 1
        if self.misses == 90:  # environ 1 seconde sans image
            print("[cam] Plus d'image : le téléphone est-il toujours connecté à Iriun ?")
        return None

    def release(self):
        if not self.is_sim:
            self.source.release()


def open_camera(choice="auto", width=1280, height=720, sim=False, demo=False) -> Camera:
    """choice : 'auto', 'iriun', un numéro de caméra ('0', '1'...) ou l'adresse d'un flux vidéo."""
    if sim:
        from sim import SimCamera
        return Camera(SimCamera(demo=demo), is_sim=True)

    if "://" in choice:  # flux réseau (appli "IP Webcam"...)
        cap = cv2.VideoCapture(choice)
    else:
        index = choose_camera_index(choice)
        cap = cv2.VideoCapture(index, camera_backend())
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    if not cap.isOpened() or not cap.read()[0]:
        raise SystemExit(f"La caméra '{choice}' ne renvoie pas d'image. Essaie --list-cameras.")
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[cam] Caméra ouverte en {w}x{h}")
    return Camera(cap)


def choose_camera_index(choice: str) -> int:
    """Trouve le numéro de la caméra à ouvrir."""
    if choice.isdigit():
        return int(choice)

    names = camera_names()
    for i, name in enumerate(names):
        if "iriun" in name.lower():
            print(f"[cam] Iriun Webcam trouvée : caméra {i}")
            return i

    if choice == "iriun" and names:
        raise SystemExit("Iriun Webcam n'apparaît pas dans les caméras de Windows.\n"
                         "  -> Lance l'appli Iriun Webcam sur le PC (https://iriun.com), puis relance.\n"
                         "  Caméras vues : " + ", ".join(names))

    # Pas de nom disponible : on prend la dernière caméra qui marche (souvent la virtuelle).
    working = working_cameras()
    if not working:
        raise SystemExit("Aucune caméra trouvée. L'appli Iriun est-elle lancée sur le PC ?")
    print(f"[cam] Caméras trouvées : {working}, j'utilise la {working[-1]}. Sinon : --camera <numéro>")
    return working[-1]


def camera_backend() -> int:
    """La bonne façon d'ouvrir une caméra selon le système."""
    return {"Windows": cv2.CAP_DSHOW, "Darwin": cv2.CAP_AVFOUNDATION}.get(platform.system(), cv2.CAP_V4L2)


def camera_names() -> list[str]:
    """Noms des caméras dans l'ordre de leurs numéros (Windows seulement, via pygrabber)."""
    try:
        from pygrabber.dshow_graph import FilterGraph
        return list(FilterGraph().get_input_devices())
    except Exception:
        return []


def working_cameras(max_index=8) -> list[int]:
    """Numéros des caméras qui renvoient vraiment une image."""
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, camera_backend())
        if cap.isOpened() and cap.read()[0]:
            found.append(i)
        cap.release()
    return found


def list_cameras():
    """Affiche les caméras disponibles (option --list-cameras)."""
    names = camera_names()
    working = working_cameras()
    if not working:
        print("Aucune caméra ne répond.")
    for i in working:
        name = names[i] if i < len(names) else "?"
        print(f"  caméra {i} : {name}" + ("   <- Iriun" if "iriun" in name.lower() else ""))
