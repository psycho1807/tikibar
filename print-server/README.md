# Tikibar – serveur d'impression

Petit serveur qui reçoit les commandes du site Tikibar et les imprime sur une
imprimante réseau (configuré ici pour une **Brother HL-L3230CDW**, `192.168.100.28`)
via "raw printing" sur le port 9100 (JetDirect/AppSocket), nativement supporté
par cette imprimante — pas besoin de driver ni de logiciel Brother.

## Pourquoi ce serveur ?

Un iPhone (Safari) ne peut pas envoyer un job d'impression directement à une
imprimante réseau depuis un site web. La solution : le téléphone envoie la
commande en HTTP à ce petit serveur (lancé sur un PC/Mac sur le même réseau
que l'imprimante), qui l'imprime.

## Installation

```bash
cd print-server
npm install
```

## Configuration

Déjà réglé dans `print-server.js` pour ton imprimante :

- `PRINTER_IP = '192.168.100.28'`
- `PRINTER_PORT = 9100`

Change ces valeurs si l'IP de l'imprimante change.

## Lancer le serveur

```bash
npm start
```

Le terminal affiche l'URL à utiliser, par exemple :

```
http://0.0.0.0:4000
Mets PRINT_RELAY_URL = "http://192.168.100.20:4000/print" dans tikibar.html
```

Trouve l'IP locale de la machine qui fait tourner ce serveur (celle où tu
lances `npm start`, pas celle de l'imprimante) :
- Mac : `ipconfig getifaddr en0`
- Windows : `ipconfig` (regarde "Adresse IPv4")
- Linux/Raspberry Pi : `hostname -I`

Mets cette URL dans la constante `PRINT_RELAY_URL` du fichier `index.html` du
site, puis republie sur GitHub Pages.

## Tester sans passer par le site

```bash
curl -X POST http://localhost:4000/print \
  -H "Content-Type: application/json" \
  -d '{"lieu":"Tikibar","boisson":"Mojito","glacons":"Avec glaçons"}'
```

Si ça imprime un ticket, tout est bon.

## Important

- Le téléphone des invités, cette machine ET l'imprimante doivent être sur le
  **même réseau WiFi** (sauf si tu exposes le serveur publiquement, ce qui
  demande des précautions supplémentaires).
- Ce serveur n'a aucune authentification — à réserver à un réseau WiFi privé
  de confiance (la fête, pas internet ouvert).
- Les accents peuvent parfois mal s'afficher en impression texte brut selon
  le firmware — le serveur les simplifie automatiquement pour limiter le
  risque.
