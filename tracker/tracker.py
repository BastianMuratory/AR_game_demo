"""Tracker de cartes ArUco -> Godot.

À chaque image, 4 étapes, une par fichier :

    1. step1_frames.py  récupérer une image de la caméra           -> image
    2. step2_detect.py  trouver les marqueurs ArUco                 -> {id: 4 coins en pixels}
    3. step3_state.py   construire l'état (plateau + cartes, en cm) -> dictionnaire "state"
    4. step4_send.py    envoyer l'état et la vidéo à Godot          -> Godot (net_client.gd)

Utilisation :
  python tracker.py --sim                 # sans caméra : table simulée, clique pour poser des cartes
  python tracker.py --sim --demo          # idem, mais les cartes se posent toutes seules
  python tracker.py                       # caméra auto : Iriun si elle est là, sinon la dernière trouvée
  python tracker.py --camera iriun        # exige Iriun Webcam
  python tracker.py --camera 1            # force un numéro de caméra
  python tracker.py --list-cameras        # liste les caméras
  python tracker.py --camera http://192.168.1.20:8080/video   # flux réseau (appli "IP Webcam"...)

Touches (fenêtre caméra) : Échap = quitter · p = vue redressée du plateau · c = remesurer le plateau
"""
from __future__ import annotations

import argparse
import time

import cv2

import config as C
from debug_view import draw_debug
from step1_frames import list_cameras, open_camera
from step2_detect import MarkerDetector
from step3_state import StateBuilder
from step4_send import GodotSender

CAMERA_WINDOW = "Arcanes - camera"
TOP_VIEW_WINDOW = "Arcanes - plateau redresse (debug)"


def main():
    args = parse_args()
    if args.list_cameras:
        list_cameras()
        return

    # --- Préparation : un objet par étape ------------------------------------
    camera = open_camera(args.camera, C.CAMERA_WIDTH, C.CAMERA_HEIGHT, sim=args.sim, demo=args.demo)  # 1
    detector = MarkerDetector()                                                                       # 2
    state_builder = StateBuilder()                                                                    # 3
    sender = GodotSender(port=args.port)                                                              # 4
    sender.start()

    window = None if args.no_window else DebugWindow(camera)

    # --- Boucle principale ---------------------------------------------------
    while True:
        # 1. Récupérer une image
        image = camera.read()
        if image is None:
            time.sleep(0.01)
            continue
        now = time.monotonic()
        height, width = image.shape[:2]

        # 2. Trouver les marqueurs
        markers = detector.detect(image)

        # 3. Construire l'état (plateau + cartes, en cm)
        state = state_builder.update(markers, now, (width, height))

        # 4. Envoyer l'état et la vidéo à Godot (on ne prépare la vidéo que si Godot écoute)
        video = state_builder.video_frame(image) if sender.has_clients else None
        sender.send(state, video)

        # Fenêtre de debug (facultative)
        if window is not None and not window.show(image, markers, state_builder, sender, now):
            break

    camera.release()
    cv2.destroyAllWindows()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", default="auto", help="auto (défaut), iriun, un numéro, ou l'adresse d'un flux")
    parser.add_argument("--list-cameras", action="store_true", help="liste les caméras et quitte")
    parser.add_argument("--sim", action="store_true", help="caméra simulée, pas besoin de cartes imprimées")
    parser.add_argument("--demo", action="store_true", help="avec --sim : pose des cartes automatiquement")
    parser.add_argument("--port", type=int, default=C.WS_PORT)
    parser.add_argument("--no-window", action="store_true", help="pas de fenêtre de debug")
    return parser.parse_args()


class DebugWindow:
    """Fenêtre OpenCV : montre ce que voit le tracker et gère le clavier (et la souris en simulation)."""

    def __init__(self, camera):
        self.sim = camera.source if camera.is_sim else None
        self.show_top_view = False
        self.fps = 0.0
        self.last_time = time.monotonic()
        cv2.namedWindow(CAMERA_WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(CAMERA_WINDOW, 1280, 720)
        if self.sim is not None:
            cv2.setMouseCallback(CAMERA_WINDOW, self.sim.on_mouse)

    def show(self, image, markers, state_builder, sender, now) -> bool:
        """Affiche une image. Renvoie False quand il faut quitter."""
        self.fps = 0.9 * self.fps + 0.1 / max(now - self.last_time, 1e-6)  # moyenne glissante
        self.last_time = now

        picture = draw_debug(image, markers, state_builder, now)
        cv2.putText(picture, f"{self.fps:4.1f} fps | Godot: {sender.client_count}", (picture.shape[1] - 260, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        if self.sim is not None:
            self.sim.draw_help(picture)
        cv2.imshow(CAMERA_WINDOW, picture)
        if self.show_top_view and state_builder.board.ready:
            cv2.imshow(TOP_VIEW_WINDOW, state_builder.top_view(image))

        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # Échap
            return False
        if key == ord("c"):
            state_builder.board.reset()
        elif key == ord("p"):
            self.show_top_view = not self.show_top_view
            if not self.show_top_view:
                cv2.destroyWindow(TOP_VIEW_WINDOW)
        elif self.sim is not None and key != 255:
            self.sim.on_key(key)
        return True


if __name__ == "__main__":
    main()
