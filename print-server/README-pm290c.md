# Tikibar → PM290C (impression automatique via Bluetooth)

La PM290C utilise en interne le protocole "cat printer" générique (BLE, même
puce que les GB01/GB02 reverse-engineered par la communauté open source :
https://github.com/rbaron/catprinter). Confirmé : Home Assistant a détecté
l'imprimante annonçant le service Bluetooth `0000af30-...`, qui correspond
exactement à ce protocole. Pas besoin de Labelnize.

## Installation (sur la machine qui a du Bluetooth et est à portée de la PM290C)

```bash
pip install flask bleak pillow --break-system-packages
```

## Lancer le serveur

```bash
cd print-server
python3 cat_print_server.py
```

Première fois : macOS va demander l'autorisation Bluetooth pour le Terminal
(ou l'app qui lance Python) — accepte.

## Tester sans passer par le site

```bash
curl -X POST http://localhost:4001/print \
  -H "Content-Type: application/json" \
  -d '{"lieu":"Tikibar","boisson":"Mojito","glacons":"Avec glaçons"}'
```

Si un ticket sort de la PM290C, c'est bon.

## Adresse Bluetooth de l'imprimante

Actuellement configurée en dur dans `cat_print_server.py` :
`PRINTER_ADDRESS = "51:82:C1:A7:C3:86"` (trouvée via le scan Bluetooth de
Home Assistant). Si l'imprimante est réinitialisée ou remplacée, mets
`PRINTER_ADDRESS = None` pour repasser en découverte automatique (scan de 10s
au premier appel), ou redemande-moi de la retrouver via Home Assistant.

## Attention

- Un seul appareil peut être connecté en BLE à la fois. Si l'iPhone est
  connecté à la PM290C via Labelnize au même moment, la connexion Python
  peut échouer — ferme Labelnize (ou désactive son Bluetooth) pendant que ce
  serveur tourne.
- Le rendu du ticket utilise Arial (polices système macOS). Sur une autre
  plateforme, adapte les chemins de police dans `render_ticket()`.
