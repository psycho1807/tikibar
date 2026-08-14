// Fonction Netlify servant de pont securise entre le site Tikibar (statique,
// heberge sur Netlify ET GitHub Pages) et Home Assistant : lit/ecrit la liste
// des boissons en rupture de stock. Le jeton HA et le mot de passe admin
// restent cote serveur (variables d'environnement Netlify), jamais exposes
// au navigateur.
//
// CORS est active volontairement : le meme site est duplique sur
// tikibar-apero.netlify.app ET psycho1807.github.io/tikibar, et les deux
// doivent pouvoir appeler cette fonction.

const ENTITY_ID = "input_text.tikibar_indisponibles";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Admin-Secret",
  "Content-Type": "application/json",
};

function getEnv(key) {
  // process.env fonctionne toujours dans le runtime Node des Netlify
  // Functions ; le global Netlify.env est une API plus recente, utilisee
  // en repli si jamais disponible.
  if (typeof process !== "undefined" && process.env && process.env[key]) {
    return process.env[key];
  }
  if (typeof Netlify !== "undefined" && Netlify.env) {
    return Netlify.env.get(key);
  }
  return undefined;
}

export default async (req, context) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  try {
    return await handle(req);
  } catch (err) {
    return json(500, { error: "Erreur interne: " + (err && err.message ? err.message : String(err)) });
  }
};

async function handle(req) {
  const HA_URL = getEnv("HA_URL");
  const HA_TOKEN = getEnv("HA_TOKEN");
  const ADMIN_SECRET = getEnv("ADMIN_SECRET");

  if (!HA_URL || !HA_TOKEN) {
    return json(500, { error: "Serveur mal configure (HA_URL/HA_TOKEN manquants)." });
  }

  if (req.method === "GET") {
    try {
      const r = await fetch(`${HA_URL}/api/states/${ENTITY_ID}`, {
        headers: { Authorization: `Bearer ${HA_TOKEN}` },
      });
      if (!r.ok) throw new Error("HA HTTP " + r.status);
      const data = await r.json();
      const indisponibles = (data.state || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      return json(200, { indisponibles });
    } catch (err) {
      return json(502, { error: "Impossible de lire le stock depuis Home Assistant." });
    }
  }

  if (req.method === "POST") {
    const secret = req.headers.get("x-admin-secret");
    if (!ADMIN_SECRET || secret !== ADMIN_SECRET) {
      return json(401, { error: "Mot de passe admin incorrect." });
    }
    let body;
    try {
      body = await req.json();
    } catch {
      return json(400, { error: "JSON invalide." });
    }
    const list = Array.isArray(body.indisponibles) ? body.indisponibles : [];
    const value = list.map(String).join(",").slice(0, 255);

    try {
      const r = await fetch(`${HA_URL}/api/services/input_text/set_value`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${HA_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ entity_id: ENTITY_ID, value }),
      });
      if (!r.ok) throw new Error("HA HTTP " + r.status);
      return json(200, { ok: true, indisponibles: list });
    } catch (err) {
      return json(502, { error: "Impossible de mettre a jour Home Assistant." });
    }
  }

  return json(405, { error: "Methode non supportee." });
}

function json(status, obj) {
  return new Response(JSON.stringify(obj), { status, headers: CORS_HEADERS });
}
