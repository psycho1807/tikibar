#!/usr/bin/env python3
"""
Serveur relais Tikibar -> imprimante PM290C (Etikez/Cerise "sticker printer")

La PM290C n'a pas d'API officielle, mais elle utilise en interne le protocole
Bluetooth Low Energy generique des "cat printers" chinois (memes puces que les
GB01/GB02/GT01, reverse-engineered par la communaute open source, notamment
https://github.com/rbaron/catprinter). Confirme ici car Home Assistant a
detecte la PM290C annoncant le service BLE 0000af30-...-34fb, qui correspond
exactement a ce protocole.

Ce script :
1. Recoit une commande en HTTP POST (JSON: lieu, boisson, glacons, text)
2. Genere un ticket sous forme d'image (texte -> bitmap 384px de large)
3. Se connecte en Bluetooth a la PM290C et envoie l'image selon le protocole
   "cat printer" (memes commandes que catprinter/cmds.py)

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

# Adresse Bluetooth de la PM290C, telle que vue par Home Assistant (Linux/BlueZ).
# IMPORTANT : sur macOS, CoreBluetooth masque les vraies adresses MAC pour des
# raisons de confidentialite et donne un identifiant different par app/systeme.
# Se connecter directement avec l'adresse ci-dessus NE MARCHE PAS sur Mac : on
# laisse donc PRINTER_ADDRESS a None pour forcer une decouverte par scan
# (filtree sur le service BLE du protocole "cat printer"), qui fonctionne sur
# toutes les plateformes.
PRINTER_ADDRESS = None

PRINT_WIDTH = 384  # largeur d'impression en pixels, standard pour ces imprimantes 58mm

# ---------------------------------------------

# ---- Protocole BLE "cat printer" (port de catprinter/ble.py) ----

POSSIBLE_SERVICE_UUIDS = [
    "0000ae30-0000-1000-8000-00805f9b34fb",
    "0000af30-0000-1000-8000-00805f9b34fb",
]
TX_CHARACTERISTIC_UUID = "0000ae01-0000-1000-8000-00805f9b34fb"
RX_CHARACTERISTIC_UUID = "0000ae02-0000-1000-8000-00805f9b34fb"
PRINTER_READY_NOTIFICATION = b"\x51\x78\xae\x01\x01\x00\x00\x00\xff"

# ---- Protocole d'impression (port de catprinter/cmds.py) ----


def to_unsigned_byte(val):
    return val if val >= 0 else val & 0xFF


def bs(lst):
    return bytearray(map(to_unsigned_byte, lst))


CMD_GET_DEV_STATE = bs([81, 120, -93, 0, 1, 0, 0, 0, -1])
CMD_SET_QUALITY_200_DPI = bs([81, 120, -92, 0, 1, 0, 50, -98, -1])
CMD_LATTICE_START = bs(
    [81, 120, -90, 0, 11, 0, -86, 85, 23, 56, 68, 95, 95, 95, 68, 56, 44, -95, -1]
)
CMD_LATTICE_END = bs(
    [81, 120, -90, 0, 11, 0, -86, 85, 23, 0, 0, 0, 0, 0, 0, 0, 23, 17, -1]
)
CMD_SET_PAPER = bs([81, 120, -95, 0, 2, 0, 48, 0, -7, -1])

CHECKSUM_TABLE = bs(
    [
        0, 7, 14, 9, 28, 27, 18, 21, 56, 63, 54, 49, 36, 35, 42, 45, 112, 119, 126,
        121, 108, 107, 98, 101, 72, 79, 70, 65, 84, 83, 90, 93, -32, -25, -18, -23,
        -4, -5, -14, -11, -40, -33, -42, -47, -60, -61, -54, -51, -112, -105, -98,
        -103, -116, -117, -126, -123, -88, -81, -90, -95, -76, -77, -70, -67, -57,
        -64, -55, -50, -37, -36, -43, -46, -1, -8, -15, -10, -29, -28, -19, -22,
        -73, -80, -71, -66, -85, -84, -91, -94, -113, -120, -127, -122, -109, -108,
        -99, -102, 39, 32, 41, 46, 59, 60, 53, 50, 31, 24, 17, 22, 3, 4, 13, 10, 87,
        80, 89, 94, 75, 76, 69, 66, 111, 104, 97, 102, 115, 116, 125, 122, -119,
        -114, -121, -128, -107, -110, -101, -100, -79, -74, -65, -72, -83, -86, -93,
        -92, -7, -2, -9, -16, -27, -30, -21, -20, -63, -58, -49, -56, -35, -38, -45,
        -44, 105, 110, 103, 96, 117, 114, 123, 124, 81, 86, 95, 88, 77, 74, 67, 68,
        25, 30, 23, 16, 5, 2, 11, 12, 33, 38, 47, 40, 61, 58, 51, 52, 78, 73, 64, 71,
        82, 85, 92, 91, 118, 113, 120, 127, 106, 109, 100, 99, 62, 57, 48, 55, 34,
        37, 44, 43, 6, 1, 8, 15, 26, 29, 20, 19, -82, -87, -96, -89, -78, -75, -68,
        -69, -106, -111, -104, -97, -118, -115, -124, -125, -34, -39, -48, -41, -62,
        -59, -52, -53, -26, -31, -24, -17, -6, -3, -12, -13,
    ]
)


def chk_sum(b_arr, i, i2):
    b2 = 0
    for i3 in range(i, i + i2):
        b2 = CHECKSUM_TABLE[(b2 ^ b_arr[i3]) & 0xFF]
    return b2


def cmd_feed_paper(how_much):
    b_arr = bs([81, 120, -67, 0, 1, 0, how_much & 0xFF, 0, 0xFF])
    b_arr[7] = chk_sum(b_arr, 6, 1)
    return bs(b_arr)


def cmd_set_energy(val):
    b_arr = bs([81, 120, -81, 0, 2, 0, (val >> 8) & 0xFF, val & 0xFF, 0, 0xFF])
    b_arr[8] = chk_sum(b_arr, 6, 2)
    return bs(b_arr)


def cmd_apply_energy():
    b_arr = bs([81, 120, -66, 0, 1, 0, 1, 0, 0xFF])
    b_arr[7] = chk_sum(b_arr, 6, 1)
    return bs(b_arr)


def encode_run_length_repetition(n, val):
    res = []
    while n > 0x7F:
        res.append(0x7F | (val << 7))
        n -= 0x7F
    if n > 0:
        res.append((val << 7) | n)
    return res


def run_length_encode(img_row):
    res = []
    count = 0
    last_val = -1
    for val in img_row:
        if val == last_val:
            count += 1
        else:
            res.extend(encode_run_length_repetition(count, last_val))
            count = 1
        last_val = val
    if count > 0:
        res.extend(encode_run_length_repetition(count, last_val))
    return res


def byte_encode(img_row):
    def bit_encode(chunk_start, bit_index):
        return 1 << bit_index if img_row[chunk_start + bit_index] else 0

    res = []
    for chunk_start in range(0, len(img_row), 8):
        byte = 0
        for bit_index in range(8):
            byte |= bit_encode(chunk_start, bit_index)
        res.append(byte)
    return res


def cmd_print_row(img_row):
    encoded_img = run_length_encode(img_row)
    if len(encoded_img) > PRINT_WIDTH // 8:
        encoded_img = byte_encode(img_row)
        b_arr = bs([81, 120, -94, 0, len(encoded_img), 0] + list(encoded_img) + [0, 0xFF])
        b_arr[-2] = chk_sum(b_arr, 6, len(encoded_img))
        return b_arr
    b_arr = bs([81, 120, -65, 0, len(encoded_img), 0] + list(encoded_img) + [0, 0xFF])
    b_arr[-2] = chk_sum(b_arr, 6, len(encoded_img))
    return b_arr


def cmds_print_img(img, energy=0xFFFF):
    data = bytearray()
    data += CMD_GET_DEV_STATE
    data += CMD_SET_QUALITY_200_DPI
    data += cmd_set_energy(energy)
    data += cmd_apply_energy()
    data += CMD_LATTICE_START
    for row in img:
        data += cmd_print_row(row)
    data += cmd_feed_paper(25)
    data += CMD_SET_PAPER
    data += CMD_SET_PAPER
    data += CMD_SET_PAPER
    data += CMD_LATTICE_END
    data += CMD_GET_DEV_STATE
    return data


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
    (True = encre noire), format attendu par cmds_print_img."""
    px = img.load()
    w, h = img.size
    rows = []
    for y in range(h):
        row = [px[x, y] < 127 for x in range(w)]
        rows.append(row)
    return rows


# ---- Connexion Bluetooth et envoi ----


async def find_printer():
    if PRINTER_ADDRESS:
        return PRINTER_ADDRESS

    def filter_fn(device, adv_data):
        if device.name and "PM290" in device.name:
            return True
        return any(u in (adv_data.service_uuids or []) for u in POSSIBLE_SERVICE_UUIDS)

    device = await BleakScanner.find_device_by_filter(filter_fn, timeout=15)
    if device is None:
        raise RuntimeError("Imprimante introuvable en Bluetooth (allumee ? a portee ?)")
    return device.address


async def print_ticket_ble(img):
    rows = img_to_bool_rows(img)
    data = cmds_print_img(rows)

    address = await find_printer()
    async with BleakClient(address) as client:
        chunk_size = (client.mtu_size or 23) - 3
        if chunk_size < 20:
            chunk_size = 20

        ready = asyncio.Event()

        def on_notify(_sender, payload):
            if bytes(payload) == PRINTER_READY_NOTIFICATION:
                ready.set()

        await client.start_notify(RX_CHARACTERISTIC_UUID, on_notify)

        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            await client.write_gatt_char(TX_CHARACTERISTIC_UUID, chunk)
            await asyncio.sleep(0.02)

        try:
            await asyncio.wait_for(ready.wait(), timeout=20)
        except asyncio.TimeoutError:
            pass  # on n'echoue pas juste parce que la notif finale a ete manquee


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


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    print(f"Serveur d'impression Tikibar (PM290C via BLE) sur http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
