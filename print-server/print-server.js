// Serveur relais Tikibar -> imprimante réseau (Brother HL-L3230CDW, laser, pas thermique)
//
// Rôle : reçoit les commandes envoyées par le site (bouton "Envoyer") en HTTP,
// et les imprime sur une imprimante laser réseau via "raw printing" (port 9100,
// aussi appelé JetDirect/AppSocket — supporté nativement par les Brother HL).
// Fonctionne depuis n'importe quel téléphone (iPhone ou Android) puisque le
// navigateur ne fait qu'un simple fetch() HTTP — pas besoin de driver ou d'app.
//
// À faire tourner sur un PC / Mac / Raspberry Pi sur le même réseau WiFi que
// l'imprimante ET que les invités.

const express = require('express');
const cors = require('cors');
const net = require('net');

// ------------------ CONFIG À ADAPTER ------------------

// Port du serveur relais (ce que tu mets dans PRINT_RELAY_URL côté site,
// ex: http://192.168.100.20:4000/print)
const PORT = 4000;

// Adresse IP de l'imprimante Brother HL-L3230CDW sur le réseau local.
const PRINTER_IP = '192.168.100.28';

// Port raw printing de l'imprimante (9100 = standard JetDirect/AppSocket).
const PRINTER_PORT = 9100;

// --------------------------------------------------------

function buildTicket({ lieu, boisson, glacons }) {
  const line = '-'.repeat(40);
  const now = new Date().toLocaleString('fr-FR');
  return [
    '',
    '        *** TIKIBAR ***',
    line,
    `  Lieu     : ${lieu}`,
    `  Boisson  : ${boisson}`,
    `  Glacons  : ${glacons}`,
    line,
    `  ${now}`,
    '',
    '',
    '',
  ].join('\r\n');
}

function printRaw(text) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host: PRINTER_IP, port: PRINTER_PORT }, () => {
      // \f (form feed) éjecte/termine la page sur la plupart des imprimantes en mode texte brut.
      socket.write(text + '\f', 'ascii', () => {
        socket.end();
      });
    });
    socket.setTimeout(5000);
    socket.on('timeout', () => {
      socket.destroy();
      reject(new Error('Timeout de connexion à l\'imprimante'));
    });
    socket.on('error', reject);
    socket.on('close', () => resolve());
  });
}

const app = express();
app.use(cors());
app.use(express.json());

app.post('/print', async (req, res) => {
  try {
    const { lieu, boisson, glacons } = req.body || {};
    if (!lieu || !boisson || !glacons) {
      return res.status(400).json({ ok: false, error: 'Commande incomplète' });
    }

    // Les accents ne passent pas toujours bien en texte brut ASCII selon le
    // firmware — on les simplifie pour être sûr que ça s'imprime correctement.
    const strip = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '');
    const ticket = buildTicket({ lieu: strip(lieu), boisson: strip(boisson), glacons: strip(glacons) });

    await printRaw(ticket);
    console.log('Ticket envoyé à l\'imprimante :', { lieu, boisson, glacons });
    res.json({ ok: true });
  } catch (err) {
    console.error('Erreur impression :', err);
    res.status(500).json({ ok: false, error: String(err) });
  }
});

app.get('/health', (req, res) => res.json({ ok: true }));

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Serveur d'impression Tikibar lancé sur http://0.0.0.0:${PORT}`);
  console.log(`Mets PRINT_RELAY_URL = "http://<IP-de-cette-machine>:${PORT}/print" dans tikibar.html`);
  console.log(`Imprimante cible : ${PRINTER_IP}:${PRINTER_PORT}`);
});
