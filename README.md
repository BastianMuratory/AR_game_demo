# squelette du jeu de cartes ArUco en réalité augmentée

Un téléphone/webcam filme la table. Python repère les cartes (ArUco) et envoie à Godot leur position, leur angle, la vidéo entière de la caméra et la position de la caméra. Godot affiche la vidéo en plein écran et dessine l'arène en 3D par-dessus, pile dans le rectangle des 4 coins (réalité augmentée), puis fait partir les sorts.

Vidéo de test : 
https://youtu.be/mGVcxRI21ug?si=HsoQ84G0HkhxqRV5


## Comment lancer l'application

penser à installer les packages python nécéssaires : `pip install -r requirements.txt`

Pour lancer l'application il faut lancer 2 projets, l'application Godot et le tracker de marqueur Aruco en python (pour l'instant, j'espère simplifier tout ça dans le futur)

| Fichier | Version |
|---|---|
| `lancer_telephone.bat` | téléphone qui filme en utilisant Iriun (https://iriun.com) |
| `lancer_webcam_pc.bat` | webcam du PC (caméra 0 ; sinon `lancer_webcam_pc.bat --camera 1`) |
| `lancer_simulation.bat` | table simulée, cartes posées toutes seules (`--sim` seul : à la souris) |

Lancer Godot, et ajouter le projet : `godot/project.godot` puis lancer avec le bouton play en haut à droite

## Démarrage rapide, sans rien imprimer

```bash
cd tracker
pip install -r requirements.txt
python tracker.py --sim --demo      # les cartes se posent toutes seules
# ou : python tracker.py --sim      # tu poses les cartes à la souris
```

Ouvre ensuite `godot/project.godot` dans Godot (4.3 minimum, testé avec la 4.7) et appuie sur **F5**.

Dans la fenêtre de simulation : **clic** pour poser ou déplacer une carte, **clic droit** pour la retirer, **a/e** pour la tourner, **1/2/3** pour changer de famille, **x** pour tout retirer.
En mode `--demo`, les deux cartes **Base** se posent en premier, puis les sorts et les tours.

Dans Godot : **C** passe de la vue vidéo (réalité augmentée) aux vues 3D libres et inversement, **R** relance la partie, **B** pose les deux bases à leur place par défaut (pour tester sans cartes), **F/G** lancent une boule de feu de test.

## Avec le vrai matériel

1. `python make_markers.py`, puis imprime `cartes_a_imprimer.pdf` en **taille réelle (100 %)** sur papier **mat**.
2. Pose les 4 marqueurs de coin aux coins de ta zone de jeu, dans l'ordre indiqué sur la page (0 haut-gauche, 1 haut-droit, 2 bas-droit, 3 bas-gauche). **Pas besoin de mesurer** : au démarrage, le tracker mesure le plateau tout seul grâce à la taille connue des carrés noirs (5 cm). N'importe quelle taille marche, et un rectangle approximatif suffit. Si tu déplaces les coins, appuie sur **c** pour remesurer.
3. Fixe le téléphone au-dessus de la table et ouvre **Iriun Webcam** sur le PC et sur le téléphone (même Wi-Fi, ou câble USB pour moins de latence).
4. Double-clique sur **`lancer_iriun.bat`**. Il installe ce qui manque, trouve la caméra Iriun par son nom et lance le tracker. La touche **p** affiche la vue redressée du plateau (debug), **c** remesure le plateau.
5. Lance Godot.

### Iriun : options et dépannage

- `python tracker.py` : caméra automatique (Iriun si elle est là, sinon la dernière caméra trouvée).
- `python tracker.py --camera iriun` : exige Iriun, avec un message clair si l'appli PC n'est pas lancée.
- `python tracker.py --list-cameras` : liste les caméras avec leur nom ; `--camera 2` force un index.
- `lancer_iriun.bat --sim` ou `lancer_iriun.bat --list-cameras` : le .bat transmet les options au tracker.
- **Tu vois le logo Iriun au lieu de la table** : le téléphone n'est pas connecté. Ouvre l'appli sur le téléphone, vérifie le Wi-Fi ou passe en USB (débogage USB activé sur Android).
- **Résolution** : le tracker demande du 1280 × 720. Si l'image est floue ou petite, règle la résolution dans l'appli Iriun du PC (Paramètres) puis ajuste `CAMERA_WIDTH`/`CAMERA_HEIGHT` dans `config.py`.
- **Mise au point** : verrouille la mise au point dans l'appli du téléphone (appui sur l'écran) pour qu'elle ne « pompe » pas quand une main passe.

## Ajouter une carte

1. Ajoute une famille dans `godot/cards.json` (type, nom, plage d'IDs, couleur, texte). Ce fichier est lu à la fois par Godot et par l'impression.
2. Ajoute le `type` dans le `match` de `_on_card_played()` (`godot/scripts/main.gd`). Si la carte crée un objet 3D, fais-lui une scène dans `godot/scenes/` avec son modèle (voir « Modèles 3D »).
3. Relance `python make_markers.py`.

Les IDs 0 à 3 sont réservés aux coins. Le dictionnaire `DICT_4X4_50` va jusqu'à l'ID 49.

## Modifier un modèle dans Blender

1. Dans Blender : **Fichier > Importer > glTF 2.0**, choisis par exemple `godot/models/tour.glb`.
2. Modifie-le (formes, couleurs, objets en plus...).
3. **Fichier > Exporter > glTF 2.0**, format **glTF Binary (.glb)**, et écrase le même fichier.
4. Reviens dans Godot : il réimporte le fichier tout seul, le jeu utilise le nouveau modèle.

Tu peux aussi enregistrer ton `.blend` n'importe où (par exemple dans un dossier `modeles_blender/` à côté de `godot/`) et n'exporter que le `.glb`.

### Les 4 règles à respecter

- **Échelle** : 1 m dans Blender = 1 unité Godot = **5 cm sur la table**. La base fait environ 2 m de large (10 cm sur la table), la tour 1,6 m de haut.
- **Origine** : le point (0, 0, 0) du modèle est **au sol, au centre** : c'est lui qui est posé sur la carte.
- **Matériau `couleur`** : tout matériau qui s'appelle exactement `couleur` est recoloré par le jeu (bleu ou rouge pour les toits de la base, couleur de la carte pour le cristal, les sorts et l'anneau). Les autres matériaux gardent tes couleurs. Si tu veux un matériau qui brille, mets-lui de l'émission (« Emission Strength » au-dessus de 1 = halo lumineux).
- **Noms d'objets utilisés par le jeu** : dans `tour.glb`, l'objet **`Cristal`** flotte et tourne. Garde ce nom (sinon la tour marche quand même, mais sans cette animation).

### Remplacer un modèle par un tout autre fichier

Tu peux aussi utiliser un modèle trouvé ailleurs (Godot Asset Library, Sketchfab, Kenney...) : ouvre la scène (ex. `scenes/tour.tscn`) dans Godot, supprime le nœud `Modele`, glisse ton fichier `.glb` / `.gltf` / `.fbx` / `.blend` dans la scène, et renomme-le **`Modele`**. Le script cherche ce nœud par son nom. Ajuste sa taille et sa position dans l'inspecteur.

### Repartir des modèles de départ

`python outils/generer_modeles_3d.py` refabrique les 5 `.glb` à partir de formes simples (boîtes, cylindres, cônes...). **Attention : ça écrase tes modifications.**

## Ce que le tracker envoie

À chaque image, un message texte :

```json
{"type": "state", "calibrated": true, "board": {"w": 60, "h": 40},
 "cards": [{"id": 12, "x": 31.2, "y": 18.5, "angle": -4.0, "stable": true, "progress": 1.0}]}
```

`x` et `y` sont en cm (origine au coin haut-gauche, y vers le bas). `angle` est en degrés (0 vers la droite, 90 vers le bas). Une fois le plateau mesuré, `camera` donne la pose de la vraie caméra dans le repère plateau (`pos` en cm, z vers le bas), ses axes, son champ de vision vertical `fov_y` et `warp`, une petite correction 2D qui fait tomber le plateau pile sur les coins. Ce message est suivi d'un message binaire : l'image JPEG entière de la caméra.

**Champ de vision** : `CAMERA_HFOV_DEG` dans `config.py` (65° par défaut, bien pour la plupart des téléphones). Le plateau reste aligné même si la valeur est fausse ; seule la hauteur apparente des objets 3D en dépend. Si les tours paraissent trop hautes ou trop plates, change cette valeur.

## Dépannage

- **Godot reste sur « En attente du tracker »** : vérifie que `tracker.py` tourne. Si le port 8765 est déjà pris, change-le dans `config.py` **et** dans `net_client.gd`.
- **La caméra ne s'ouvre pas** : `--list-cameras`, puis `--camera <index>`. Sur macOS, autorise le Terminal à accéder à la caméra.
- **Les cartes sont mal détectées** : les reflets sont la cause n°1 (papier brillant, pochettes de protection). Éclaire de façon diffuse, rapproche le téléphone ou agrandis les marqueurs.
- **Le plateau « tremble »** : baisse `CORNER_SMOOTHING` et `SMOOTHING` dans `config.py`.
- **Taille mesurée bizarre** : vérifie que la page des coins est imprimée en taille réelle (le carré noir doit faire 5 cm, sinon change `CORNER_MARKER_CM`). Sur une grande table filmée de loin, des coins plus grands (8–10 cm) rendent la mesure plus précise. Tu peux aussi forcer les dimensions avec `BOARD_W_CM` / `BOARD_H_CM`.
- **Message « Coins inversés »** : les IDs ne sont pas posés dans l'ordre 0-1-2-3 en tournant dans le sens des aiguilles d'une montre.