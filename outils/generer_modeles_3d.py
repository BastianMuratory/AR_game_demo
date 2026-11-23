"""Fabrique les modèles 3D de départ du jeu (fichiers .glb dans godot/models/).

Tu n'as besoin de lancer ce script qu'UNE fois : les .glb sont déjà dans le projet.
Ensuite, modifie les modèles directement dans Blender (Fichier > Importer > glTF 2.0,
puis Fichier > Exporter > glTF 2.0 au même endroit).

ATTENTION : relancer ce script ÉCRASE les .glb de godot/models/ (et donc tes retouches).

    python outils/generer_modeles_3d.py

Le format .glb (glTF binaire) est un format 3D standard : Blender, Godot et la plupart des
logiciels 3D savent le lire et l'écrire. Ce script l'écrit "à la main" avec numpy, sans
aucun logiciel 3D, en assemblant des formes simples (boîtes, cylindres, cônes, sphères...).

Conventions (les mêmes que dans le jeu) :
  - 1 unité (1 mètre dans Blender) = 5 cm sur la table.
  - Y vers le haut, l'origine du modèle est au sol, au centre.
  - Un matériau nommé "couleur" est recoloré par le jeu (couleur du joueur ou de la carte).
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import numpy as np

MODELS_DIR = Path(__file__).resolve().parent.parent / "godot" / "models"


# ============================================================ formes simples
# Chaque forme renvoie une liste de triangles : tableau (n, 3, 3) = n triangles de 3 points (x, y, z).
# Les triangles sont dans le sens inverse des aiguilles d'une montre vus de l'extérieur.

def quad(a, b, c, d):
    """Un rectangle (4 points dans l'ordre) = 2 triangles."""
    return [[a, b, c], [a, c, d]]


def box(size, center=(0, 0, 0)):
    sx, sy, sz = np.array(size) / 2
    cx, cy, cz = center
    p = lambda x, y, z: (cx + x * sx, cy + y * sy, cz + z * sz)
    tris = []
    tris += quad(p(-1, -1, 1), p(1, -1, 1), p(1, 1, 1), p(-1, 1, 1))      # avant (+z)
    tris += quad(p(1, -1, -1), p(-1, -1, -1), p(-1, 1, -1), p(1, 1, -1))  # arrière
    tris += quad(p(1, -1, 1), p(1, -1, -1), p(1, 1, -1), p(1, 1, 1))      # droite (+x)
    tris += quad(p(-1, -1, -1), p(-1, -1, 1), p(-1, 1, 1), p(-1, 1, -1))  # gauche
    tris += quad(p(-1, 1, 1), p(1, 1, 1), p(1, 1, -1), p(-1, 1, -1))      # dessus
    tris += quad(p(-1, -1, -1), p(1, -1, -1), p(1, -1, 1), p(-1, -1, 1))  # dessous
    return tris


def cylinder(r_bottom, r_top, height, center=(0, 0, 0), sides=12):
    """Cylindre (ou cône si r_top = 0) debout, centré sur `center`."""
    cx, cy, cz = center
    y0, y1 = cy - height / 2, cy + height / 2
    ring = lambda r, y, i: (cx + r * math.cos(2 * math.pi * i / sides), y, cz - r * math.sin(2 * math.pi * i / sides))
    tris = []
    for i in range(sides):
        b0, b1 = ring(r_bottom, y0, i), ring(r_bottom, y0, i + 1)
        t0, t1 = ring(r_top, y1, i), ring(r_top, y1, i + 1)
        if r_top > 0:
            tris += quad(b0, b1, t1, t0)
            tris.append([(cx, y1, cz), t0, t1])        # couvercle du haut
        else:
            tris.append([b0, b1, (cx, y1, cz)])        # pointe du cône
        tris.append([(cx, y0, cz), b1, b0])            # fond
    return tris


def sphere(radius, center=(0, 0, 0), sides=12, rings=8, stretch_y=1.0):
    """Sphère (sides=4, rings=2 donne un octaèdre : un "cristal")."""
    cx, cy, cz = center

    def p(i, j):
        lat = math.pi * j / rings - math.pi / 2       # de -90° (bas) à +90° (haut)
        lon = 2 * math.pi * i / sides
        return (cx + radius * math.cos(lat) * math.cos(lon),
                cy + radius * stretch_y * math.sin(lat),
                cz - radius * math.cos(lat) * math.sin(lon))

    tris = []
    for j in range(rings):
        for i in range(sides):
            a, b, c, d = p(i, j), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1)
            if j == 0:
                tris.append([a, c, d])                 # calotte du bas
            elif j == rings - 1:
                tris.append([a, b, c])                 # calotte du haut
            else:
                tris += quad(a, b, c, d)
    return tris


def torus(radius, thickness, center=(0, 0, 0), sides=32, tube_sides=8):
    """Anneau à plat sur le sol."""
    cx, cy, cz = center

    def p(i, j):
        u, v = 2 * math.pi * i / sides, 2 * math.pi * j / tube_sides
        r = radius + thickness * math.cos(v)
        return (cx + r * math.cos(u), cy + thickness * math.sin(v), cz - r * math.sin(u))

    tris = []
    for i in range(sides):
        for j in range(tube_sides):
            tris += quad(p(i, j), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1))
    return tris


def flat_arrow(length, width, thickness, center=(0, 0, 0)):
    """Triangle épais posé à plat, pointe vers +x."""
    cx, cy, cz = center
    pts = [(cx + length / 2, cz), (cx - length / 2, cz - width / 2), (cx - length / 2, cz + width / 2)]
    y0, y1 = cy - thickness / 2, cy + thickness / 2
    top = [(x, y1, z) for x, z in pts]
    bot = [(x, y0, z) for x, z in pts]
    tris = [[top[0], top[1], top[2]], [bot[0], bot[2], bot[1]]]
    for i in range(3):
        k = (i + 1) % 3
        tris += quad(bot[i], bot[k], top[k], top[i])
    return tris


# ============================================================ matériaux
def material(name, color, roughness=0.85, metallic=0.0, emission=0.0):
    """color : couleur comme dans un sélecteur de couleur (0 à 1, la même que Color() dans Godot).
    emission > 0 : le matériau brille (au-delà de 1, il déclenche le halo "glow" de Godot)."""
    color = [c ** 2.2 for c in color]  # le format glTF range les couleurs en "linéaire"
    m = {"name": name, "pbrMetallicRoughness": {"baseColorFactor": [*color, 1.0],
                                                "metallicFactor": metallic, "roughnessFactor": roughness}}
    if emission > 0:
        m["emissiveFactor"] = list(color)
        m["extensions"] = {"KHR_materials_emissive_strength": {"emissiveStrength": emission}}
    return m


PIERRE = material("pierre", (0.58, 0.55, 0.50))
PIERRE_SOMBRE = material("pierre_sombre", (0.40, 0.38, 0.36))
BOIS = material("bois", (0.42, 0.27, 0.15))


# ============================================================ écriture du fichier .glb
def write_glb(path: Path, parts: list[tuple[str, list, dict]], root_name: str):
    """parts = [(nom de l'objet, triangles, matériau), ...] -> un fichier .glb.

    Chaque partie devient un objet séparé (visible et renommable dans Blender et dans Godot).
    Les normales sont "plates" (une par face) pour un style low-poly bien lisible.
    """
    materials, mat_index = [], {}
    buffer = bytearray()
    accessors, views, meshes, nodes = [], [], [], []

    def add_view(data: bytes, target):
        while len(buffer) % 4:
            buffer.append(0)
        views.append({"buffer": 0, "byteOffset": len(buffer), "byteLength": len(data), "target": target})
        buffer.extend(data)
        return len(views) - 1

    for name, tris, mat in parts:
        if mat["name"] not in mat_index:
            mat_index[mat["name"]] = len(materials)
            materials.append(mat)
        tri = np.asarray(tris, np.float32)                        # (n, 3, 3)
        normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        lengths = np.linalg.norm(normals, axis=1, keepdims=True)
        keep = lengths[:, 0] > 1e-9                                # retire les triangles plats
        tri, normals = tri[keep], normals[keep] / lengths[keep]
        positions = tri.reshape(-1, 3)
        normals = np.repeat(normals, 3, axis=0).astype(np.float32)
        indices = np.arange(len(positions), dtype=np.uint32)

        pos_view = add_view(positions.tobytes(), 34962)
        nor_view = add_view(normals.tobytes(), 34962)
        idx_view = add_view(indices.tobytes(), 34963)
        accessors.append({"bufferView": pos_view, "componentType": 5126, "count": len(positions), "type": "VEC3",
                          "min": positions.min(axis=0).tolist(), "max": positions.max(axis=0).tolist()})
        accessors.append({"bufferView": nor_view, "componentType": 5126, "count": len(normals), "type": "VEC3"})
        accessors.append({"bufferView": idx_view, "componentType": 5125, "count": len(indices), "type": "SCALAR"})
        a = len(accessors)
        meshes.append({"name": name, "primitives": [{"attributes": {"POSITION": a - 3, "NORMAL": a - 2},
                                                     "indices": a - 1, "material": mat_index[mat["name"]]}]})
        nodes.append({"name": name, "mesh": len(meshes) - 1})

    nodes.append({"name": root_name, "children": list(range(len(nodes)))})
    gltf = {
        "asset": {"version": "2.0", "generator": "ArucoTD generer_modeles_3d.py"},
        "extensionsUsed": ["KHR_materials_emissive_strength"],
        "scene": 0, "scenes": [{"nodes": [len(nodes) - 1]}],
        "nodes": nodes, "meshes": meshes, "materials": materials,
        "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(buffer)}],
    }
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode()
    json_bytes += b" " * (-len(json_bytes) % 4)
    buffer.extend(b"\0" * (-len(buffer) % 4))
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(json_bytes) + 8 + len(buffer)))
        f.write(struct.pack("<II", len(json_bytes), 0x4E4F534A)); f.write(json_bytes)   # "JSON"
        f.write(struct.pack("<II", len(buffer), 0x004E4942)); f.write(buffer)            # "BIN"
    print(f"  {path.relative_to(MODELS_DIR.parent.parent)}  ({len(parts)} objets)")


# ============================================================ les modèles du jeu
def base():
    """La forteresse d'un joueur : un donjon, 4 tours d'angle, des créneaux, une porte."""
    roof = material("couleur", (0.25, 0.5, 1.0))   # recoloré par le jeu (bleu J1, rouge J2)
    parts = [
        ("Donjon", box((1.3, 1.1, 1.3), (0, 0.55, 0)), PIERRE),
        ("Donjon_haut", box((0.8, 0.9, 0.8), (0, 1.55, 0)), PIERRE),
        ("Donjon_toit", cylinder(0.65, 0.0, 0.9, (0, 2.45, 0), sides=4), roof),
        ("Porte", box((0.4, 0.55, 0.06), (0, 0.28, 0.66)), BOIS),
    ]
    créneaux = []
    for i in range(-2, 3):  # créneaux sur le bord du donjon
        for side in (-1, 1):
            créneaux += box((0.14, 0.16, 0.14), (i * 0.28, 1.18, side * 0.58))
            créneaux += box((0.14, 0.16, 0.14), (side * 0.58, 1.18, i * 0.28))
    parts.append(("Creneaux", créneaux, PIERRE_SOMBRE))
    for k, (sx, sz) in enumerate([(-1, -1), (1, -1), (1, 1), (-1, 1)]):
        x, z = sx * 0.75, sz * 0.75
        parts.append((f"Tour_{k + 1}", cylinder(0.28, 0.28, 1.5, (x, 0.75, z)), PIERRE))
        parts.append((f"Tour_{k + 1}_toit", cylinder(0.38, 0.0, 0.6, (x, 1.8, z)), roof))
    write_glb(MODELS_DIR / "base.glb", parts, "Base")


def tour():
    """La tour posée par une carte : un socle en pierre et un cristal qui flotte (et tourne)."""
    crystal = material("couleur", (0.64, 0.36, 1.0), roughness=0.3, emission=4.0)
    parts = [
        ("Socle_bas", cylinder(0.42, 0.42, 0.15, (0, 0.075, 0), sides=8), PIERRE_SOMBRE),
        ("Socle", cylinder(0.35, 0.22, 0.9, (0, 0.6, 0), sides=8), PIERRE),
        ("Socle_haut", cylinder(0.3, 0.3, 0.1, (0, 1.05, 0), sides=8), PIERRE_SOMBRE),
        # Le jeu fait flotter et tourner l'objet nommé "Cristal" : garde ce nom dans Blender.
        ("Cristal", sphere(0.22, (0, 1.4, 0), sides=4, rings=2, stretch_y=1.4), crystal),
    ]
    write_glb(MODELS_DIR / "tour.glb", parts, "Tour")


def boule_de_feu():
    core = material("couleur", (1.0, 0.65, 0.35), roughness=0.5, emission=4.0)
    write_glb(MODELS_DIR / "boule_de_feu.glb", [("Coeur", sphere(0.28), core)], "BouleDeFeu")


def projectile():
    """Le petit projectile tiré par les tours."""
    core = material("couleur", (0.8, 0.6, 1.0), roughness=0.5, emission=6.0)
    write_glb(MODELS_DIR / "projectile.glb", [("Coeur", sphere(0.12, sides=8, rings=6), core)], "Projectile")


def anneau():
    """L'anneau de charge qui apparaît sous chaque carte, avec une flèche dans le sens du sort."""
    glow = material("couleur", (1.0, 1.0, 1.0), roughness=0.5, emission=0.5)
    parts = [
        ("Anneau", torus(0.66, 0.06), glow),
        ("Fleche", flat_arrow(0.45, 0.4, 0.04, (0.98, 0.02, 0)), glow),
    ]
    write_glb(MODELS_DIR / "anneau.glb", parts, "AnneauDeCharge")


if __name__ == "__main__":
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print("Modèles écrits :")
    base()
    tour()
    boule_de_feu()
    projectile()
    anneau()
