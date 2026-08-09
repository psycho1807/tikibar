# Tikibar – serveur d'impression

Petit serveur qui reçoit les commandes du site Tikibar et les imprime sur une
imprimante de tickets (ESC/POS : Epson TM-xxx, Star, etc.).

## Pourquoi ce serveur ?

Un iPhone (Safari) ne peut pas parler directement en Bluetooth/USB à une
imprimante depuis un site web. La solution universelle : le téléphone envoie
la commande en HTTP à ce petit serveur (lancé sur un PC/Mac/Raspberry Pi
connecté à l'imprimante), qui l'imprime.

## Installation

```bash
cd print-server
npm install
```

## Configuration

Ouvre `print-server.js` et adapte le bloc CONFIG en haut du fichier :

- `PRINTER_TYPE` : `EPSON` ou `STAR` selon la marque de l'imprimante.
- `PRINTER_INTERFACE` : décommente la ligne qui correspond à ta connexion
  (réseau/WiFi avec IP, USB, ou Bluetooth en port série).

## Lancer le serveur

```bash
npm start
```

Le terminal affiche l'URL à utiliser, par exemple :

```
http://0.0.0.0:4000
Mets PRINT_RELAY_URL = "http://192.168.1.50:4000/print" dans tikibar.html
```

Trouve l'IP locale de cette machine (`ipconfig getifaddr en0` sur Mac,
`hostname -I` sur Raspberry Pi/Linux) et mets cette URL dans la constante
`PRINT_RELAY_URL` du fichier `index.html` du site, puis republie sur GitHub
Pages.

## Important

- Le téléphone des invités et cette machine doivent être sur le **même
  réseau WiFi** (sauf si tu exposes le serveur publiquement, ce qui demande
  des précautions supplémentaires).
- Ce serveur n'a aucune authentification — à réserver à un réseau WiFi privé
  de confiance (la fête, pas internet ouvert).
