#!/usr/bin/env python3
"""
Serveur relais Tikibar -> imprimante PM290C (Etikez/Cerise "sticker printer")

IMPORTANT (reecrit apres capture Bluetooth reelle) : contrairement a ce qu'on
pensait au depart, cette imprimante ne parle PAS le protocole binaire "cat
printer" (GB01/GB02/GT01). Une capture du trafic Bluetooth reel de l'app
Labelnize (via `pymobiledevice3 btlogger`) a revele qu'elle parle en fait
**TSPL** (Trans-Shift Printer Language), un protocole texte tres repandu sur
les imprimantes d'etiquettes thermiques (SIZE / GAP / DIRECTION / DENSITY /
CLS / PRINT / BITMAP), envoye sur le canal BLE service 0xff00, caracteristique
d'ecriture 0xff04 (write-without-response), caracteristique de notification
0xff03.

Ce script :
1. Recoit une commande en HTTP POST (JSON: lieu, boisson, glacons, text)
2. Genere un ticket sous forme d'image (texte -> bitmap 384px de large)
3. Se connecte en Bluetooth a la PM290C et envoie l'image en TSPL

A faire tourner sur une machine avec Bluetooth a portee de l'imprimante
(ex: le Mac de Psycho, ou la machine qui heberge Home Assistant).

Installation :
    pip install flask bleak pillow --break-system-packages

Lancement :
    python3 cat_print_server.py
"""

import asyncio
import textwrap
from datetime import datetime

from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
from bleak import BleakClient, BleakScanner

# ------------------ CONFIG ------------------

PORT = 4001

# Adresse Bluetooth de la PM290C. Sur macOS, CoreBluetooth masque les vraies
# adresses MAC (confidentialite) : on laisse a None pour forcer une
# decouverte par scan a chaque impression, qui fonctionne partout.
PRINTER_ADDRESS = None

PRINT_WIDTH = 384       # largeur d'impression en pixels
PRINT_WIDTH_MM = 54     # largeur physique en mm (confirmee par la capture reelle Labelnize)
PRINT_WIDTH_BYTES = PRINT_WIDTH // 8  # 48, confirme par la capture ("BITMAP 0,0,48,...")

# ---------------------------------------------

# ---- Canal BLE reel (confirme par capture Bluetooth de Labelnize) ----
# L'imprimante expose plusieurs "personnalites" GATT ; celle-ci est la seule
# qui repond et que Labelnize utilise reellement.
WRITE_CHARACTERISTIC_UUID = "0000ff04-0000-1000-8000-00805f9b34fb"
NOTIFY_CHARACTERISTIC_UUID = "0000ff03-0000-1000-8000-00805f9b34fb"

CHUNK_SIZE = 244  # taille de decoupe observee dans la capture reelle (limite MTU)

# ---- Protocole TSPL ----


def build_tspl_job(bitmap_bytes, width_bytes, height_px, width_mm, height_mm, density=10):
    """Construit un job d'impression TSPL complet (commandes texte + bitmap brut),
    calque exactement sur ce qu'envoie Labelnize (capture Bluetooth reelle)."""
    header = (
        f"SIZE {width_mm} mm,{height_mm} mm\r\n"
        "GAP 0,0\r\n"
        "DIRECTION 0,0\r\n"
        f"DENSITY {density}\r\n"
        "CLS\r\n"
        "PRINT 1,1\r\n"
        f"BITMAP 0,0,{width_bytes},{height_px},1,"
    ).encode("ascii")
    return header + bitmap_bytes + b"\r\n"


def byte_encode_msb(img_row):
    """Empaquette une ligne de pixels (bool, True = noir) en octets,
    bit de poids FORT en premier (MSB first, standard TSPL/ESC-POS)."""
    res = bytearray()
    for chunk_start in range(0, len(img_row), 8):
        byte = 0
        for bit_index in range(8):
            if img_row[chunk_start + bit_index]:
                byte |= 1 << (7 - bit_index)
        res.append(byte)
    return bytes(res)


def img_to_tspl_bitmap(rows, width_bytes):
    out = bytearray()
    for row in rows:
        out += byte_encode_msb(row)
    return bytes(out)


# ---- Rendu du ticket texte -> image monochrome 384px ----


def render_ticket(lieu, boisson, glacons):
    font_big = ImageFont.load_default()
    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
        font_small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
    except Exception:
        font_small = font_big

    lines = [
        ("*** TIKIBAR ***", font_big, True),
        ("", font_small, False),
        (f"Lieu: {lieu}", font_small, False),
        (f"Boisson: {boisson}", font_small, False),
        (f"Glacons: {glacons}", font_small, False),
        ("", font_small, False),
        (datetime.now().strftime("%d/%m/%Y %H:%M"), font_small, False),
        ("", font_small, False),
    ]

    # Enveloppe le texte trop long pour tenir dans PRINT_WIDTH
    wrapped = []
    for text, font, center in lines:
        if len(text) > 26:
            for chunk in textwrap.wrap(text, width=26):
                wrapped.append((chunk, font, center))
        else:
            wrapped.append((text, font, center))

    line_height = 30
    img_height = line_height * len(wrapped) + 20
    # La hauteur doit etre un multiple de 8 pour un empaquetage bitmap propre.
    img_height = ((img_height + 7) // 8) * 8
    img = Image.new("L", (PRINT_WIDTH, img_height), color=255)
    draw = ImageDraw.Draw(img)

    y = 10
    for text, font, center in wrapped:
        if text:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            x = (PRINT_WIDTH - w) // 2 if center else 10
            draw.text((x, y), text, fill=0, font=font)
        y += line_height

    return img


def img_to_bool_rows(img):
    """Convertit une image PIL en niveaux de gris en lignes de booleens
    (True = encre noire)."""
    px = img.load()
    w, h = img.size
    rows = []
    for y in range(h):
        row = [px[x, y] < 127 for x in range(w)]
        rows.append(row)
    return rows


# ---- Connexion Bluetooth et envoi ----

POSSIBLE_SCAN_SERVICE_UUIDS = [
    "0000ff00-0000-1000-8000-00805f9b34fb",
    "0000ae30-0000-1000-8000-00805f9b34fb",
    "0000af30-0000-1000-8000-00805f9b34fb",
]


async def find_printer():
    if PRINTER_ADDRESS:
        return PRINTER_ADDRESS

    def filter_fn(device, adv_data):
        if device.name and "PM290" in device.name:
            return True
        return any(u in (adv_data.service_uuids or []) for u in POSSIBLE_SCAN_SERVICE_UUIDS)

    device = await BleakScanner.find_device_by_filter(filter_fn, timeout=15)
    if device is None:
        raise RuntimeError("Imprimante introuvable en Bluetooth (allumee ? a portee ?)")
    return device.address


async def print_ticket_ble(img):
    rows = img_to_bool_rows(img)
    height_px = len(rows)
    bitmap = img_to_tspl_bitmap(rows, PRINT_WIDTH_BYTES)
    height_mm = round(height_px * PRINT_WIDTH_MM / PRINT_WIDTH, 1)

    job = build_tspl_job(bitmap, PRINT_WIDTH_BYTES, height_px, PRINT_WIDTH_MM, height_mm)
    print(f"[debug] image: {height_px} lignes x {PRINT_WIDTH}px, job TSPL de {len(job)} octets")

    address = await find_printer()
    print(f"[debug] imprimante trouvee: {address}")

    async with BleakClient(address) as client:
        print(f"[debug] connecte: {client.is_connected}")

        def on_notify(_sender, payload):
            raw = bytes(payload)
            print(f"[debug] notification recue ({len(raw)} octets): {raw.hex()}")

        try:
            await client.start_notify(NOTIFY_CHARACTERISTIC_UUID, on_notify)
        except Exception as e:
            print(f"[debug] abonnement notify impossible (non bloquant): {e}")

        # Decoupe en morceaux de CHUNK_SIZE octets, comme observe dans la
        # capture reelle du trafic Labelnize. Pas de pause = paquets perdus
        # en cours de route (write-without-response n'a pas d'accuse de
        # reception), d'ou les impressions tronquees observees. On ralentit
        # nettement et on verifie que chaque ecriture reussit vraiment.
        n_chunks = 0
        total = len(job)
        for i in range(0, total, CHUNK_SIZE):
            chunk = job[i:i + CHUNK_SIZE]
            for attempt in range(3):
                try:
                    await client.write_gatt_char(WRITE_CHARACTERISTIC_UUID, chunk, response=False)
                    break
                except Exception as e:
                    print(f"[debug] echec ecriture morceau {n_chunks} (tentative {attempt+1}): {e}")
                    await asyncio.sleep(0.2)
            else:
                raise RuntimeError(f"Echec d'envoi du morceau {n_chunks} apres 3 tentatives")
            n_chunks += 1
            if n_chunks % 10 == 0:
                print(f"[debug] {i + len(chunk)}/{total} octets envoyes")
            await asyncio.sleep(0.08)

        print(f"[debug] job envoye en {n_chunks} morceaux ({total} octets)")
        await asyncio.sleep(2.5)  # laisse le temps a l'imprimante de traiter/imprimer


# ---- Serveur HTTP ----

app = Flask(__name__)


@app.route("/print", methods=["POST"])
def http_print():
    payload = request.get_json(force=True, silent=True) or {}
    lieu = payload.get("lieu", "?")
    boisson = payload.get("boisson", "?")
    glacons = payload.get("glacons", "?")

    try:
        img = render_ticket(lieu, boisson, glacons)
        asyncio.run(print_ticket_ble(img))
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Erreur impression: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/print_test", methods=["GET"])
def http_print_test():
    """Imprime un rectangle noir de N lignes pour trouver la limite de
    memoire tampon de l'imprimante par dichotomie.
    Exemple : curl "http://localhost:4001/print_test?rows=40" """
    rows = int(request.args.get("rows", 40))
    img = Image.new("L", (PRINT_WIDTH, rows), color=0)  # tout noir
    try:
        asyncio.run(print_ticket_ble(img))
        return jsonify({"ok": True, "rows": rows, "job_bytes": rows * PRINT_WIDTH_BYTES + 90})
    except Exception as e:
        print(f"Erreur impression test: {e}")
        return jsonify({"ok": False, "rows": rows, "error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    print(f"Serveur d'impression Tikibar (PM290C via BLE, protocole TSPL) sur http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
