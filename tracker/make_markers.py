"""Génère un PDF A4 à imprimer : les 4 marqueurs de coin + les cartes de godot/cards.json.

  python make_markers.py                  # 3 cartes par famille -> cartes_a_imprimer.pdf
  python make_markers.py --per-family 10  # toutes les cartes

Imprime à 100 % / "taille réelle" (pas "ajuster à la page"), sur papier MAT.
"""
from __future__ import annotations

import argparse

from PIL import Image, ImageDraw, ImageFont

import config as C
from step2_detect import marker_image
from cards import hex_to_rgb, load_families

DPI = 300                                          # résolution d'impression
A4 = (int(21.0 / 2.54 * DPI), int(29.7 / 2.54 * DPI))
CARD_W_CM, CARD_H_CM = 6.3, 8.8
MARKER_CM = 4.0


def cm(v: float) -> int:
    """Centimètres -> pixels de la page."""
    return int(round(v / 2.54 * DPI))


def font(size_px: int, bold: bool = False):
    """Une police lisible, quel que soit le système (sinon celle par défaut de Pillow)."""
    names = ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size_px)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size_px)   # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def marker_img(mid: int, size_cm: float) -> Image.Image:
    return Image.fromarray(marker_image(mid, cm(size_cm))).convert("RGB")


def wrap(draw, text, fnt, max_w):
    """Coupe un texte en lignes qui tiennent dans max_w pixels."""
    lines, cur = [], ""
    for word in text.split():
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


def corner_page() -> Image.Image:
    """Page 1 : les 4 marqueurs de coin, avec leur nom."""
    page = Image.new("RGB", A4, "white")
    d = ImageDraw.Draw(page)
    d.text((cm(1.5), cm(1.2)), "Marqueurs de coin du plateau", fill="black", font=font(cm(0.7), True))
    help_txt = ("Découpe-les et pose-les aux 4 coins de ta zone de jeu, dans l'ordre ci-dessous "
                "(à peu près en rectangle, pas besoin d'être précis). Le tracker mesure le plateau "
                "tout seul grâce à la taille des carrés noirs : imprime cette page en TAILLE RÉELLE.")
    for i, line in enumerate(wrap(d, help_txt, font(cm(0.4)), A4[0] - cm(3))):
        d.text((cm(1.5), cm(2.2) + i * cm(0.55)), line, fill="black", font=font(cm(0.4)))
    labels = ["haut-gauche", "haut-droit", "bas-droit", "bas-gauche"]
    for k, (mid, label) in enumerate(zip(C.CORNER_IDS, labels)):
        col, row = k % 2, k // 2
        x, y = cm(2.5) + col * cm(9), cm(5) + row * cm(10.5)
        page.paste(marker_img(mid, C.CORNER_MARKER_CM), (x, y))
        s = cm(C.CORNER_MARKER_CM)
        # repère du centre + cadre de découpe avec marge blanche
        d.rectangle([x - cm(1), y - cm(1), x + s + cm(1), y + s + cm(1)], outline=(170, 170, 170), width=2)
        d.text((x, y + s + cm(1.3)), f"COIN {mid} – {label}", fill="black", font=font(cm(0.45), True))
    return page


def card_img(mid: int, fam: dict) -> Image.Image:
    """Une carte : bandeau de couleur, flèche, marqueur, texte de la règle."""
    w, h = cm(CARD_W_CM), cm(CARD_H_CM)
    card = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(card)
    color = hex_to_rgb(fam["color"])
    d.rectangle([0, 0, w, cm(1.3)], fill=color)
    d.text((cm(0.3), cm(0.25)), fam["name"], fill="white", font=font(cm(0.6), True))
    # flèche = direction du sort (vers le bord "haut" du marqueur)
    ax = w // 2
    d.polygon([(ax, cm(1.45)), (ax - cm(0.45), cm(2.15)), (ax + cm(0.45), cm(2.15))], fill=color)
    ms = cm(MARKER_CM)
    card.paste(marker_img(mid, MARKER_CM), ((w - ms) // 2, cm(2.8)))
    y = cm(2.8) + ms + cm(0.5)  # garder du blanc autour du marqueur
    for line in wrap(d, fam["text"], font(cm(0.32)), w - cm(0.6)):
        d.text((cm(0.3), y), line, fill=(60, 60, 60), font=font(cm(0.32)))
        y += cm(0.42)
    d.text((w - cm(1.0), h - cm(0.55)), f"#{mid}", fill=(150, 150, 150), font=font(cm(0.3)))
    d.rectangle([0, 0, w - 1, h - 1], outline=(160, 160, 160), width=2)  # trait de coupe
    return card


def card_pages(per_family: int) -> list[Image.Image]:
    """Les cartes, 9 par page (3 x 3)."""
    cards = []
    for fam in load_families():
        for mid in range(fam["first_id"], fam["first_id"] + min(per_family, fam["count"])):
            cards.append(card_img(mid, fam))
    pages, per_page = [], 9
    gx = (A4[0] - 3 * cm(CARD_W_CM)) // 2
    gy = (A4[1] - 3 * cm(CARD_H_CM)) // 2
    for i in range(0, len(cards), per_page):
        page = Image.new("RGB", A4, "white")
        for k, c in enumerate(cards[i:i + per_page]):
            page.paste(c, (gx + (k % 3) * cm(CARD_W_CM), gy + (k // 3) * cm(CARD_H_CM)))
        pages.append(page)
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-family", type=int, default=3)
    ap.add_argument("-o", "--output", default="cartes_a_imprimer.pdf")
    args = ap.parse_args()
    pages = [corner_page()] + card_pages(args.per_family)
    pages[0].save(args.output, "PDF", resolution=DPI, save_all=True, append_images=pages[1:])
    print(f"{args.output} : {len(pages)} page(s). Imprime en taille réelle (100 %).")


if __name__ == "__main__":
    main()
