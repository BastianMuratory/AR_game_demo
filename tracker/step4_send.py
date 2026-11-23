"""ÉTAPE 4 : envoyer l'état et la vidéo à Godot.

Le tracker est un petit serveur WebSocket (ws://127.0.0.1:8765). Godot s'y connecte
(godot/scripts/net_client.gd) et reçoit, à chaque nouvelle image :
  - un message TEXTE   : l'état en JSON
  - un message BINAIRE : l'image de la caméra en JPEG

Le serveur tourne en arrière-plan (un "thread") pour ne jamais ralentir la boucle principale.
send() ne fait que déposer les dernières données ; le thread de chaque Godot connecté les
envoie dès qu'il est prêt. Si Godot prend du retard, il saute simplement des images.
"""
from __future__ import annotations

import json
import threading

import cv2
from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve

import config as C


class GodotSender:
    def __init__(self, host=C.WS_HOST, port=C.WS_PORT):
        self.host, self.port = host, port
        self.client_count = 0
        self.latest = None          # (numéro, texte JSON, image JPEG ou None)
        self.counter = 0
        self.new_data = threading.Condition()  # sert à réveiller les envois quand une image arrive

    @property
    def has_clients(self) -> bool:
        return self.client_count > 0

    def start(self):
        server = serve(self.talk_to_godot, self.host, self.port, max_size=None, compression=None)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"[ws] En écoute sur ws://{self.host}:{self.port}")

    def send(self, state: dict, image=None):
        """Publie l'état (et l'image) les plus récents. Ne bloque jamais."""
        jpeg = None
        if image is not None:
            ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, C.JPEG_QUALITY])
            jpeg = buffer.tobytes() if ok else None
        with self.new_data:
            self.counter += 1
            self.latest = (self.counter, json.dumps(state), jpeg)
            self.new_data.notify_all()

    def talk_to_godot(self, websocket):
        """Tourne dans son propre thread tant qu'un Godot est connecté."""
        self.client_count += 1
        print(f"[ws] Godot connecté ({self.client_count} client(s))")
        last_sent = 0
        try:
            while True:
                with self.new_data:  # attend des données plus récentes que celles déjà envoyées
                    self.new_data.wait_for(lambda: self.latest and self.latest[0] != last_sent)
                    last_sent, text, jpeg = self.latest
                websocket.send(text)
                if jpeg is not None:
                    websocket.send(jpeg)
        except ConnectionClosed:
            pass
        finally:
            self.client_count -= 1
            print(f"[ws] Godot déconnecté ({self.client_count} client(s))")
