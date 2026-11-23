"""Tous les réglages du tracker, au même endroit.

Les distances sont en cm, les durées en secondes.
"""

# --- Plateau ----------------------------------------------------------------
# Les 4 marqueurs de coin, dans l'ordre : haut-gauche, haut-droit, bas-droit, bas-gauche.
CORNER_IDS = [0, 1, 2, 3]

# Taille réelle du carré noir des marqueurs de coin (imprimés à 100 %).
# Connaître cette taille permet au tracker de MESURER le plateau tout seul.
CORNER_MARKER_CM = 5.0

# Taille du plateau (distance entre les CENTRES des coins).
# None = mesurée automatiquement au démarrage (recommandé). Mets deux nombres pour la forcer.
BOARD_W_CM = None
BOARD_H_CM = None

# Nombre d'images utilisées pour mesurer le plateau (on garde la valeur médiane).
CALIBRATION_FRAMES = 30

# Famille de marqueurs ArUco : 4x4 cases, IDs 0 à 49. De grosses cases = détection facile.
ARUCO_DICT = "DICT_4X4_50"

# --- Suivi des cartes -------------------------------------------------------
# Une carte doit rester immobile ce temps-là pour être "jouée".
STABLE_TIME = 0.6
# Si la carte bouge de plus que ça pendant la charge, la charge recommence.
STILL_TOLERANCE_CM = 1.5
# Une carte qu'on ne voit plus pendant ce temps est considérée comme retirée
# (évite qu'une main qui passe au-dessus "retire" la carte).
LOST_TIMEOUT = 0.5
# Lissage des positions : 0 = figé, 1 = aucun lissage.
SMOOTHING = 0.35
# Lissage des coins du plateau (la caméra est fixe, on peut lisser fort).
CORNER_SMOOTHING = 0.2
# Si un coin saute de plus que ça (pixels), la caméra a bougé : on recale tout de suite.
CORNER_JUMP_PX = 25.0
# Les marqueurs trop loin en dehors du plateau sont ignorés.
OUTSIDE_MARGIN_CM = 8.0

# --- Caméra -----------------------------------------------------------------
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
# Champ de vision horizontal de la caméra, en degrés (65 convient à la plupart des téléphones).
# Il sert à placer la caméra 3D de Godot comme la vraie. Le plateau reste aligné même si
# la valeur est fausse ; seule la hauteur apparente des objets 3D change.
CAMERA_HFOV_DEG = 65.0

# --- Envoi vers Godot -------------------------------------------------------
WS_HOST = "127.0.0.1"
WS_PORT = 8765
# La vidéo envoyée à Godot est réduite si elle est plus large que ça (pixels).
VIDEO_MAX_WIDTH = 1280
JPEG_QUALITY = 75
# Résolution de la vue "plateau redressé" de la fenêtre de debug (touche p).
PX_PER_CM = 16
