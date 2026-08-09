// Serveur relais Tikibar -> imprimante de tickets (ESC/POS)
//
// Rôle : reçoit les commandes envoyées par le site (bouton "Imprimer au bar")
// en HTTP, et les imprime sur une imprimante thermique. Fonctionne depuis
// n'importe quel téléphone (iPhone ou Android) puisque le navigateur ne fait
// qu'un simple fetch() HTTP — pas besoin de Web Bluetooth/USB côté client.
//
// À faire tourner sur un PC / Mac / Raspberry Pi connecté à l'imprimante,
// sur le même réseau WiFi que les invités.

const express = require('express');
const cors = require('cors');
const { ThermalPrinter, PrinterTypes } = require('node-thermal-printer');

// ------------------ CONFIG À ADAPTER ------------------

// Port du serveur relais (ce que tu mets dans PRINT_RELAY_URL côté site,
// ex: http://192.168.1.50:4000/print)
const PORT = 4000;

// Type d'imprimante : PrinterTypes.EPSON ou PrinterTypes.STAR selon la marque.
const PRINTER_TYPE = PrinterTypes.EPSON;

// Interface de connexion à l'imprimante — choisis UNE des trois lignes ci-dessous :
//
// 1) Imprimante réseau / WiFi (a une adresse IP, port souvent 9100) :
const PRINTER_INTERFACE = 'tcp://192.168.1.100:9100';
//
// 2) Imprimante USB branchée sur cette machine (Linux, exemple) :
// const PRINTER_INTERFACE = '/dev/usb/lp0';
//
// 3) Imprimante Bluetooth appairée comme port série :
// const PRINTER_INTERFACE = '/dev/tty.thermalprinter'; // macOS, nom variable

// --------------------------------------------------------

const printer = new ThermalPrinter({
  type: PRINTER_TYPE,
  interface: PRINTER_INTERFACE,
  removeSpecialCharacters: false,
  options: { timeout: 5000 }
});

const app = express();
app.use(cors());
app.use(express.json());

app.post('/print', async (req, res) => {
  try {
    const { lieu, boisson, glacons, text } = req.body || {};
    if (!lieu || !boisson || !glacons) {
      return res.status(400).json({ ok: false, error: 'Commande incomplète' });
    }

    const isConnected = await printer.isPrinterConnected();
    if (!isConnected) {
      return res.status(503).json({ ok: false, error: 'Imprimante non connectée' });
    }

    printer.clear();
    printer.alignCenter();
    printer.bold(true);
    printer.println('🍹 TIKIBAR 🍹');
    printer.bold(false);
    printer.drawLine();
    printer.alignLeft();
    printer.println(`Lieu     : ${lieu}`);
    printer.println(`Boisson  : ${boisson}`);
    printer.println(`Glaçons  : ${glacons}`);
    printer.drawLine();
    printer.alignCenter();
    printer.println(new Date().toLocaleTimeString('fr-FR'));
    printer.cut();

    await printer.execute();
    console.log('Ticket imprimé :', text);
    res.json({ ok: true });
  } catch (err) {
    console.error('Erreur impression :', err);
    res.status(500).json({ ok: false, error: String(err) });
  }
});

app.get('/health', (req, res) => res.json({ ok: true }));

app.listen(PORT, () => {
  console.log(`Serveur d'impression Tikibar lancé sur http://0.0.0.0:${PORT}`);
  console.log(`Mets PRINT_RELAY_URL = "http://<IP-de-cette-machine>:${PORT}/print" dans tikibar.html`);
});
