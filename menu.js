// Menu partage entre le site (index.html) et la page d'administration (admin.html).
//
// Chaque boisson a une liste d'"ingredients" (cles courtes). La page admin
// permet de cocher/decocher la disponibilite de chaque ingredient de base
// (alcools, mixeurs...) : des qu'un ingredient manque, tous les cocktails qui
// en ont besoin disparaissent automatiquement du menu des invites.
// Les ingredients mineurs (citron, sucre, glacons, jus courants...) ne sont
// pas suivis : on part du principe qu'ils sont presque toujours disponibles.

const menu = {
  "Grands classiques": [
    ["Mojito", "Rhum blanc, sucre de canne, citron vert, menthe, eau gazeuse.", ["rhum"]],
    ["Gin tonic", "Gin, tonic, glaçons, zeste de citron ou concombre.", ["gin"]],
    ["Piña colada", "Rhum blanc, jus d'ananas, crème de coco, glace pilée.", ["rhum", "creme_coco"]],
    ["Margarita", "Tequila, triple sec, jus de citron vert, sel.", ["tequila", "triple_sec"]],
    ["Moscow mule", "Vodka, ginger beer, citron vert, glaçons.", ["vodka", "ginger_beer"]],
    ["Daiquiri", "Rhum blanc, jus de citron vert, sirop de sucre.", ["rhum"]],
    ["Negroni", "Gin, Campari, vermouth rouge, à parts égales.", ["gin", "campari", "vermouth_rouge"]],
    ["Cosmopolitan", "Vodka, triple sec, jus de cranberry, citron vert.", ["vodka", "triple_sec"]],
    ["Whisky sour", "Whisky, jus de citron, sirop de sucre, trait d'angostura.", ["whisky"]],
    ["St-Germain Spritz", "St-Germain, vin pétillant, eau gazeuse, zeste de citron.", ["st_germain", "vin_petillant"]],
    ["Cuba Libre", "Rhum blanc, Coca, citron vert.", ["rhum", "coca"]],
    ["Dark 'n' Stormy", "Rhum ambré, ginger beer, citron vert.", ["rhum", "ginger_beer"]],
    ["Ti' Punch", "Rhum ambré, sucre de canne, citron vert.", ["rhum"]],
    ["Whisky Buck", "Whisky, ginger beer, citron vert.", ["whisky", "ginger_beer"]],
    ["Americano", "Campari, vermouth rouge, eau gazeuse.", ["campari", "vermouth_rouge"]],
    ["Campari Spritz", "Campari, vin pétillant, eau gazeuse.", ["campari", "vin_petillant"]],
    ["Vodka Cranberry", "Vodka, jus de cranberry.", ["vodka"]],
    ["Screwdriver", "Vodka, jus de fruits.", ["vodka"]],
    ["Rhum Punch tropical", "Rhum ambré, jus d'ananas, jus de cranberry, sirop de sucre.", ["rhum"]],
    ["Planteur", "Rhum ambré, jus d'ananas, jus de cranberry, trait d'angostura, sirop de sucre.", ["rhum"]],
    ["Tequila Sunrise", "Tequila, jus d'orange, grenadine.", ["tequila"]],
    ["Paloma", "Tequila, citron vert, sel, soda pamplemousse.", ["tequila"]],
    ["Kir Royal", "Vin pétillant, crème de cassis.", ["vin_petillant", "creme_cassis"]]
  ],
  "Spiritueux": [
    ["Whisky", "Servi sec ou sur glaçons, au choix.", ["whisky"]],
    ["Rhum", "Blanc ou ambré, avec ou sans glaçons.", ["rhum"]],
    ["Vodka", "Pure, avec ou sans glaçons.", ["vodka"]],
    ["Vin", "Rouge, blanc ou rosé, au choix.", ["vin"]],
    ["Bière", "Corona, Desperados ou Leffe, au choix.", ["biere"]]
  ],
  "Softs": [
    ["Coca", "Coca-Cola bien frais.", ["coca"]],
    ["Red Bull", "Red Bull glacé.", ["red_bull"]],
    ["Limonade", "Limonade pétillante.", ["limonade"]],
    ["Jus de fruits", "Orange, pomme ou ananas.", ["jus_fruits"]],
    ["Perrier", "Eau gazeuse Perrier, glaçons.", ["perrier"]]
  ]
};

// Seule la categorie "Spiritueux" propose le choix des glacons (whisky, rhum,
// vodka, vin, biere...) - les cocktails ont deja les glacons dans la recette.
const GLACONS_CATEGORIES = ["Spiritueux"];

// Ingredients suivis par la page admin, groupes pour l'affichage.
// Cle -> libelle affiche.
const INGREDIENTS = {
  "Alcools": {
    rhum: "Rhum (blanc ou ambré)",
    gin: "Gin",
    vodka: "Vodka",
    tequila: "Tequila",
    whisky: "Whisky",
    vin: "Vin",
    biere: "Bière",
  },
  "Liqueurs & apéritifs": {
    triple_sec: "Triple sec",
    campari: "Campari",
    vermouth_rouge: "Vermouth rouge",
    st_germain: "St-Germain",
    creme_cassis: "Crème de cassis",
    creme_coco: "Crème de coco",
  },
  "Mixeurs & softs": {
    ginger_beer: "Ginger beer",
    vin_petillant: "Vin pétillant",
    coca: "Coca",
    red_bull: "Red Bull",
    limonade: "Limonade",
    jus_fruits: "Jus de fruits",
    perrier: "Perrier",
  },
};

// Point d'acces de la fonction Netlify servant de pont vers Home Assistant
// pour la gestion du stock (lecture publique, ecriture protegee par mot de passe).
const STOCK_URL = "https://tikibar-apero.netlify.app/.netlify/functions/stock";
