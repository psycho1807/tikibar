// Menu partage entre le site (index.html) et la page d'administration (admin.html).
// Modifier les boissons ici les met a jour aux deux endroits.

const menu = {
  "Grands classiques": [
    ["Mojito", "Rhum blanc, sucre de canne, citron vert, menthe, eau gazeuse."],
    ["Gin tonic", "Gin, tonic, glaçons, zeste de citron ou concombre."],
    ["Piña colada", "Rhum blanc, jus d'ananas, crème de coco, glace pilée."],
    ["Margarita", "Tequila, triple sec, jus de citron vert, sel."],
    ["Moscow mule", "Vodka, ginger beer, citron vert, glaçons."],
    ["Daiquiri", "Rhum blanc, jus de citron vert, sirop de sucre."],
    ["Negroni", "Gin, Campari, vermouth rouge, à parts égales."],
    ["Cosmopolitan", "Vodka, triple sec, jus de cranberry, citron vert."],
    ["Whisky sour", "Whisky, jus de citron, sirop de sucre, trait d'angostura."],
    ["St-Germain Spritz", "St-Germain, vin pétillant, eau gazeuse, zeste de citron."],
    ["Cuba Libre", "Rhum blanc, Coca, citron vert."],
    ["Dark 'n' Stormy", "Rhum ambré, ginger beer, citron vert."],
    ["Ti' Punch", "Rhum ambré, sucre de canne, citron vert."],
    ["Whisky Buck", "Whisky, ginger beer, citron vert."],
    ["Americano", "Campari, vermouth rouge, eau gazeuse."],
    ["Campari Spritz", "Campari, vin pétillant, eau gazeuse."],
    ["Vodka Cranberry", "Vodka, jus de cranberry."],
    ["Screwdriver", "Vodka, jus de fruits."],
    ["Rhum Punch tropical", "Rhum ambré, jus d'ananas, jus de cranberry, sirop de sucre."],
    ["Planteur", "Rhum ambré, jus d'ananas, jus de cranberry, trait d'angostura, sirop de sucre."],
    ["Tequila Sunrise", "Tequila, jus d'orange, grenadine."],
    ["Paloma", "Tequila, citron vert, sel, soda pamplemousse."],
    ["Kir Royal", "Vin pétillant, crème de cassis."]
  ],
  "Spiritueux": [
    ["Whisky", "Servi sec ou sur glaçons, au choix."],
    ["Rhum", "Blanc ou ambré, avec ou sans glaçons."],
    ["Vodka", "Pure, avec ou sans glaçons."],
    ["Vin", "Rouge, blanc ou rosé, au choix."],
    ["Bière", "Corona, Desperados ou Leffe, au choix."]
  ],
  "Softs": [
    ["Coca", "Coca-Cola bien frais."],
    ["Red Bull", "Red Bull glacé."],
    ["Limonade", "Limonade pétillante."],
    ["Jus de fruits", "Orange, pomme ou ananas."],
    ["Perrier", "Eau gazeuse Perrier, glaçons."]
  ]
};

// Seule la categorie "Spiritueux" propose le choix des glacons (whisky, rhum,
// vodka, vin, biere...) - les cocktails ont deja les glacons dans la recette.
const GLACONS_CATEGORIES = ["Spiritueux"];

// Point d'acces de la fonction Netlify servant de pont vers Home Assistant
// pour la gestion du stock (lecture publique, ecriture protegee par mot de passe).
const STOCK_URL = "https://tikibar-apero.netlify.app/.netlify/functions/stock";
