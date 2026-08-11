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

TX_CHARACTERISTIC_UUID = "0000ae01-0000-1000-8000-00805f9b34fb"
RX_CHARACTERISTIC_UUID = "0000ae02-0000-1000-8000-00805f9b34fb"

# ---- Protocole d'impression ----
# Aligne sur https://github.com/opuu/cat-printer (SDK JS activement maintenu,
# teste avec succes en connexion sur cette PM290C precise) plutot que sur
# l'implementation Python plus ancienne de rbaron/catprinter : les deux
# divergent sur plusieurs points (pas de commandes "lattice"/DPI, energie sur
# 4 octets, pas d'inversion de bits, get_device_state avec payload [1]).

CMD_GET_DEV_STATE = 0xA3
CMD_SPEED = 0xBD
CMD_ENERGY = 0xAF
CMD_APPLY_ENERGY = 0xBE
CMD_BITMAP = 0xA2
CMD_FEED = 0xA1

DEFAULT_SPEED = 32
DEFAULT_ENERGY = 24000  # 0x5DE0, valeur par defaut du SDK JS de reference


def crc8(data):
    'CRC-8, polynome 0x07 (identique a la table utilisee par les autres implementations "cat printer")'
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def make_command(command, payload):
    payload = bytes(payload)
    header = bytes(
        [0x51, 0x78, command, 0x00, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]
    )
    return header + payload + bytes([crc8(payload), 0xFF])


def cmd_get_device_state():
    return make_command(CMD_GET_DEV_STATE, [1])


def cmd_set_speed(speed):
    return make_command(CMD_SPEED, [speed & 0xFF])


def cmd_set_energy(energy):
    return make_command(
        CMD_ENERGY,
        [energy & 0xFF, (energy >> 8) & 0xFF, (energy >> 16) & 0xFF, (energy >> 24) & 0xFF],
    )


def cmd_apply_energy():
    return make_command(CMD_APPLY_ENERGY, [1])


def cmd_feed(lines):
    return make_command(CMD_FEED, [lines & 0xFF, (lines >> 8) & 0xFF])


def byte_encode(img_row):
    'Empaquette une ligne de pixels (bool) en octets, bit de poids faible en premier'
    res = bytearray()
    for chunk_start in range(0, len(img_row), 8):
        byte = 0
        for bit_index in range(8):
            if img_row[chunk_start + bit_index]:
                byte |= 1 << bit_index
        res.append(byte)
    return bytes(res)


def cmd_draw_row(img_row):
    encoded = byte_encode(img_row)
    return make_command(CMD_BITMAP, encoded)


def cmds_print_img(img, speed=DEFAULT_SPEED, energy=DEFAULT_ENERGY):
    'Retourne une LISTE de commandes individuelles (une par ecriture BLE), comme le SDK de reference'
    cmds = [
        cmd_get_device_state(),
        cmd_set_speed(speed),
        cmd_set_energy(energy),
        cmd_apply_energy(),
    ]
    for row in img:
        # Les lignes entierement blanches sont ignorees (comme le SDK de reference)
        if any(row):
            cmds.append(cmd_draw_row(row))
    cmds.append(cmd_set_speed(8))
    cmds.append(cmd_feed(80))
    return cmds


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


POSSIBLE_SCAN_SERVICE_UUIDS = [
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
    cmds = cmds_print_img(rows)
    print(f"[debug] image: {len(rows)} lignes x {PRINT_WIDTH}px, {len(cmds)} commandes a envoyer")

    address = await find_printer()
    print(f"[debug] imprimante trouvee: {address}")

    async with BleakClient(address) as client:
        print(f"[debug] connecte: {client.is_connected}")

        def on_notify(_sender, payload):
            print(f"[debug] notification recue: {bytes(payload)!r}")

        await client.start_notify(RX_CHARACTERISTIC_UUID, on_notify)

        # Une commande = une ecriture BLE, comme le fait le SDK JS de reference
        # (au lieu de tout concatener puis decouper par MTU).
        for cmd in cmds:
            await client.write_gatt_char(TX_CHARACTERISTIC_UUID, cmd, response=False)
            await asyncio.sleep(0.03)

        print(f"[debug] {len(cmds)} commandes envoyees")
        await asyncio.sleep(0.5)  # laisse le temps au firmware de traiter la fin


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
