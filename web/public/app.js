/* Grille jouable : rendu fidèle maquette + saisie clavier.
   Le sens de saisie (horizontal/vertical) se choisit : bouton du bandeau,
   ou nouveau clic sur la case déjà sélectionnée. */

const grilleEl = document.getElementById("grille");
const choixEl = document.getElementById("choix-grille");
const sensBtn = document.getElementById("sens");
const sensLibelle = document.getElementById("sens-libelle");
const solutionsBtn = document.getElementById("solutions");
const verifierBtn = document.getElementById("verifier");
const indiceBtn = document.getElementById("indice");
const etatEl = document.getElementById("bandeau-etat");
const clavierEl = document.getElementById("clavier-mobile");

// Sentinelle du clavier virtuel : certains claviers Android n'émettent
// pas de vrais keydown ; on lit les variations du champ invisible, et la
// sentinelle permet de détecter un retour arrière (le champ raccourcit).
const SENTINELLE = "•";

const etat = {
  data: null,      // JSON de la grille
  values: [],      // lettres saisies
  words: [],       // {cells: [[r,c]...], dir: "h"|"v"}
  cellWords: [],   // cellWords[r][c] = {h: index|null, v: index|null}
  sel: null,       // {r, c}
  dir: "h",
  solutions: false, // grille finalisée affichée (la saisie est conservée)
  aides: new Set(), // cases révélées par le bouton Indice ("r,c")
  fautes: new Set(), // cases marquées fausses par la vérification
};

// right = →, right_down = ↴ (part à droite puis descend),
// down = ↓, down_right = ↳ (descend puis part à droite)
const ICONE_SENS = {
  right: "→",
  right_down: "↴",
  down: "↓",
  down_right: "↳",
};

// 0 = le mot part vers la droite, 1 = le mot part vers le bas
const VERS_LE_BAS = { right: 0, right_down: 0, down: 1, down_right: 1 };

const BALLON =
  '<img src="img/ballon.png" alt="" loading="lazy">';

function fleche(type, slotIndex, slotCount) {
  // Petit triangle (ou coude) rouge qui pointe vers la première lettre.
  const t = 8; // taille du triangle en px
  const el = document.createElement("span");
  el.className = "fleche";
  const y = slotCount === 2 ? (slotIndex === 0 ? 25 : 75) : 50;
  if (type === "right") {
    el.style.cssText = `right:${-t}px;top:calc(${y}% - ${t / 2}px)`;
    el.innerHTML =
      `<svg width="${t}" height="${t}"><path d="M0 0 L${t} ${t / 2} L0 ${t} Z" fill="#e3262a"/></svg>`;
  } else if (type === "down") {
    el.style.cssText = `bottom:${-t}px;left:calc(50% - ${t / 2}px)`;
    el.innerHTML =
      `<svg width="${t}" height="${t}"><path d="M0 0 L${t} 0 L${t / 2} ${t} Z" fill="#e3262a"/></svg>`;
  } else if (type === "down_right") {
    // coude : descend sous la case puis pointe vers la droite
    el.style.cssText = `bottom:${-t - 4}px;left:calc(50% - 2px)`;
    el.innerHTML =
      `<svg width="${t + 6}" height="${t + 4}">` +
      `<path d="M2 0 V${t / 2 + 2} H${t - 2}" stroke="#e3262a" stroke-width="3" fill="none"/>` +
      `<path d="M${t - 3} ${(t + 4) / 2 - t / 2 + 1} L${t + 5} ${t / 2 + 2} L${t - 3} ${t + 3} Z" fill="#e3262a"/></svg>`;
  } else if (type === "right_down") {
    // coude : sort à droite puis pointe vers le bas
    el.style.cssText = `right:${-t - 4}px;top:calc(${y}% - 2px)`;
    el.innerHTML =
      `<svg width="${t + 4}" height="${t + 6}">` +
      `<path d="M0 2 H${t / 2 + 2} V${t - 2}" stroke="#e3262a" stroke-width="3" fill="none"/>` +
      `<path d="M${t / 2 + 2 - t / 2 + 1} ${t - 3} L${t / 2 + 2} ${t + 5} L${t + 3} ${t - 3} Z" fill="#e3262a"/></svg>`;
  }
  return el;
}

function construireModele(data) {
  etat.data = data;
  etat.values = data.solution.map((row) => row.split("").map(() => ""));
  etat.words = [];
  etat.cellWords = data.solution.map((row) =>
    row.split("").map(() => ({ h: null, v: null }))
  );
  for (const cell of data.clues) {
    for (const slot of cell.slots) {
      const cells = [];
      for (let i = 0; i < slot.len; i += 1) {
        cells.push(slot.horizontal ? [slot.row, slot.col + i] : [slot.row + i, slot.col]);
      }
      const dir = slot.horizontal ? "h" : "v";
      const index = etat.words.length;
      etat.words.push({ cells, dir, slot });
      for (const [r, c] of cells) etat.cellWords[r][c][dir] = index;
    }
  }
  etat.sel = null;
}

function rendre() {
  const { data } = etat;
  grilleEl.style.setProperty("--cols", data.width);
  grilleEl.style.setProperty("--rows", data.height);
  grilleEl.innerHTML = "";
  const parClef = new Map(data.clues.map((c) => [`${c.row},${c.col}`, c]));
  for (let r = 0; r < data.height; r += 1) {
    for (let c = 0; c < data.width; c += 1) {
      const div = document.createElement("div");
      div.dataset.r = r;
      div.dataset.c = c;
      if (data.solution[r][c] === "#") {
        const clue = parClef.get(`${r},${c}`);
        if (clue) {
          div.className = "case def";
          // Ordre géométrique : le mot qui part vers la droite en haut,
          // celui qui descend en bas — l'œil associe la définition à son mot.
          const slots = [...clue.slots].sort(
            (a, b) => VERS_LE_BAS[a.arrow] - VERS_LE_BAS[b.arrow]
          );
          slots.forEach((slot, i) => {
            const slotEl = document.createElement("div");
            slotEl.className = "slot";
            // À deux dans la case, chaque définition a moitié moins de
            // place : la police se réduit plus tôt.
            const [long, tresLong] = slots.length === 2 ? [24, 38] : [32, 55];
            if (slot.text.length > tresLong) slotEl.classList.add("tres-long");
            else if (slot.text.length > long) slotEl.classList.add("long");
            // Icône et texte dans un même bloc en ligne : sinon la flexbox
            // de la case en fait deux colonnes et le texte déborde.
            const contenu = document.createElement("span");
            if (slots.length === 2) {
              const dirEl = document.createElement("span");
              dirEl.className = "dir";
              dirEl.textContent = ICONE_SENS[slot.arrow];
              contenu.appendChild(dirEl);
            }
            contenu.appendChild(document.createTextNode(slot.text));
            slotEl.appendChild(contenu);
            slotEl.title = slot.text;
            slotEl.addEventListener("click", () => {
              selectionner(slot.row, slot.col, slot.horizontal ? "h" : "v");
            });
            div.appendChild(slotEl);
            // Case double : les icônes dans les définitions suffisent, les
            // flèches externes ajoutaient de la confusion.
            if (slots.length === 1) {
              div.appendChild(fleche(slot.arrow, i, 1));
            }
          });
        } else {
          div.className = "case deco";
          div.innerHTML = BALLON;
        }
      } else {
        div.className = "case lettre";
        div.addEventListener("click", () => clicLettre(r, c));
      }
      grilleEl.appendChild(div);
    }
  }
  ajusterTaille();
  ajusterDebordements();
  rafraichir();
}

function ajusterDebordements() {
  // Les classes de police couvrent presque tout ; pour les définitions
  // sans variante courte au lexique, on réduit finement jusqu'à tenir.
  for (const slot of grilleEl.querySelectorAll(".slot")) {
    slot.style.fontSize = "";
    let taille = parseFloat(getComputedStyle(slot).fontSize);
    let garde = 8;
    while (slot.scrollHeight > slot.clientHeight + 1 && garde-- > 0) {
      taille -= 0.4;
      slot.style.fontSize = `${taille}px`;
    }
  }
}

function celluleEl(r, c) {
  return grilleEl.children[r * etat.data.width + c];
}

function rafraichir() {
  const { data } = etat;
  for (let r = 0; r < data.height; r += 1) {
    for (let c = 0; c < data.width; c += 1) {
      if (data.solution[r][c] === "#") continue;
      const el = celluleEl(r, c);
      el.textContent = etat.solutions
        ? data.solution[r][c]
        : etat.values[r][c];
      el.classList.toggle("revele", etat.solutions);
      el.classList.toggle(
        "aide", !etat.solutions && etat.aides.has(`${r},${c}`)
      );
      el.classList.toggle(
        "faux", !etat.solutions && etat.fautes.has(`${r},${c}`)
      );
      el.classList.remove("mot-actif", "case-active");
    }
  }
  if (etat.solutions || !etat.sel) return;
  const mot = motCourant();
  if (mot) {
    for (const [r, c] of mot.cells) celluleEl(r, c).classList.add("mot-actif");
  }
  celluleEl(etat.sel.r, etat.sel.c).classList.add("case-active");
}

function motCourant() {
  if (!etat.sel) return null;
  const index = etat.cellWords[etat.sel.r][etat.sel.c][etat.dir];
  return index === null ? null : etat.words[index];
}

function fixerSens(dir) {
  etat.dir = dir;
  sensLibelle.textContent = dir === "h" ? "→ horizontal" : "↓ vertical";
  rafraichir();
}

function selectionner(r, c, dir) {
  etat.sel = { r, c };
  const ici = etat.cellWords[r][c];
  if (dir && ici[dir] !== null) fixerSens(dir);
  else if (ici[etat.dir] === null) fixerSens(etat.dir === "h" ? "v" : "h");
  else rafraichir();
  // Le focus va au champ invisible : sur téléphone il invoque le clavier
  // virtuel, sur ordinateur les keydown remontent au document.
  clavierEl.value = SENTINELLE;
  clavierEl.focus({ preventScroll: true });
}

function clicLettre(r, c) {
  const ici = etat.cellWords[r][c];
  if (etat.sel && etat.sel.r === r && etat.sel.c === c) {
    // Nouveau clic sur la case sélectionnée : on bascule le sens.
    const autre = etat.dir === "h" ? "v" : "h";
    if (ici[autre] !== null) fixerSens(autre);
    return;
  }
  selectionner(r, c);
}

function deplacer(dr, dc) {
  if (!etat.sel) return;
  const { data } = etat;
  let { r, c } = etat.sel;
  while (true) {
    r += dr;
    c += dc;
    if (r < 0 || r >= data.height || c < 0 || c >= data.width) return;
    if (data.solution[r][c] !== "#") break;
  }
  selectionner(r, c);
}

function avancerDansMot(sens) {
  const mot = motCourant();
  if (!mot || !etat.sel) return;
  const position = mot.cells.findIndex(
    ([r, c]) => r === etat.sel.r && c === etat.sel.c
  );
  const suivant = mot.cells[position + sens];
  if (suivant) {
    etat.sel = { r: suivant[0], c: suivant[1] };
    rafraichir();
  }
}

// ------------------------------------------------ progression et contrôle

function cleStockage() {
  return `nizzle:${etat.data.id}`;
}

function sauvegarder() {
  try {
    localStorage.setItem(cleStockage(), JSON.stringify({
      values: etat.values,
      aides: [...etat.aides],
      t: Date.now(),
    }));
  } catch (e) {
    // stockage plein ou bloqué : le jeu continue sans sauvegarde
  }
}

function restaurer() {
  try {
    const brut = localStorage.getItem(cleStockage());
    if (!brut) return;
    const sauve = JSON.parse(brut);
    if (
      Array.isArray(sauve.values)
      && sauve.values.length === etat.data.height
      && sauve.values.every((ligne) => ligne.length === etat.data.width)
    ) {
      etat.values = sauve.values;
      etat.aides = new Set(sauve.aides || []);
    }
  } catch (e) {
    // sauvegarde illisible : on repart de zéro
  }
}

function afficherEtat(message, classe) {
  etatEl.hidden = !message;
  etatEl.textContent = message || "";
  etatEl.className = `bandeau-etat ${classe || ""}`;
}

function poserLettre(r, c, lettre, aide = false) {
  etat.values[r][c] = lettre;
  etat.fautes.delete(`${r},${c}`);
  if (aide) etat.aides.add(`${r},${c}`);
  else etat.aides.delete(`${r},${c}`);
  sauvegarder();
  verifierCompletion();
}

function effacerLettre(r, c) {
  etat.values[r][c] = "";
  etat.fautes.delete(`${r},${c}`);
  etat.aides.delete(`${r},${c}`);
  sauvegarder();
  afficherEtat(null);
}

function casesLettres() {
  const cases = [];
  for (let r = 0; r < etat.data.height; r += 1) {
    for (let c = 0; c < etat.data.width; c += 1) {
      if (etat.data.solution[r][c] !== "#") cases.push([r, c]);
    }
  }
  return cases;
}

function verifierCompletion() {
  const cases = casesLettres();
  if (!cases.every(([r, c]) => etat.values[r][c])) {
    afficherEtat(null);
    return;
  }
  const fausses = cases.filter(
    ([r, c]) => etat.values[r][c] !== etat.data.solution[r][c]
  );
  if (fausses.length === 0) {
    afficherEtat("🎉 Bravo, grille terminée !", "victoire");
  } else {
    // Grille pleine mais fautive : on montre où ça cloche.
    for (const [r, c] of fausses) etat.fautes.add(`${r},${c}`);
    afficherEtat(
      `La grille est pleine mais ${fausses.length} lettre(s) `
      + "clochent — elles sont barrées.",
      "erreurs"
    );
  }
}

function verifier() {
  if (etat.solutions) return;
  const remplies = casesLettres().filter(([r, c]) => etat.values[r][c]);
  const fausses = remplies.filter(
    ([r, c]) => etat.values[r][c] !== etat.data.solution[r][c]
  );
  for (const [r, c] of fausses) etat.fautes.add(`${r},${c}`);
  if (!remplies.length) afficherEtat("Rien à vérifier pour l'instant.", "");
  else if (!fausses.length) afficherEtat("Tout est juste, continue !", "victoire");
  else afficherEtat(`${fausses.length} lettre(s) fausse(s), barrées.`, "erreurs");
  rafraichir();
}

function indice() {
  if (etat.solutions || !etat.sel) return;
  const { r, c } = etat.sel;
  poserLettre(r, c, etat.data.solution[r][c], true);
  avancerDansMot(1);
  rafraichir();
}

// ------------------------------------------------------------------ saisie

function surTouche(event) {
  if (etat.solutions) return;
  if (!etat.sel || event.ctrlKey || event.metaKey || event.altKey) return;
  const { key } = event;
  if (key === "ArrowRight") deplacer(0, 1);
  else if (key === "ArrowLeft") deplacer(0, -1);
  else if (key === "ArrowDown") deplacer(1, 0);
  else if (key === "ArrowUp") deplacer(-1, 0);
  else if (key === "Backspace") {
    if (!etat.values[etat.sel.r][etat.sel.c]) avancerDansMot(-1);
    effacerLettre(etat.sel.r, etat.sel.c);
    rafraichir();
  } else {
    const lettre = key
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toUpperCase();
    if (!/^[A-Z]$/.test(lettre)) return;
    poserLettre(etat.sel.r, etat.sel.c, lettre);
    avancerDansMot(1);
    rafraichir();
  }
  event.preventDefault();
}

function surSaisieMobile() {
  // Chemin des claviers virtuels sans keydown fiable (Android).
  const texte = clavierEl.value;
  clavierEl.value = SENTINELLE;
  if (etat.solutions || !etat.sel) return;
  if (texte.length < SENTINELLE.length) {
    // le champ a raccourci : retour arrière
    if (!etat.values[etat.sel.r][etat.sel.c]) avancerDansMot(-1);
    effacerLettre(etat.sel.r, etat.sel.c);
    rafraichir();
    return;
  }
  const lettre = texte[texte.length - 1]
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toUpperCase();
  if (!/^[A-Z]$/.test(lettre)) return;
  poserLettre(etat.sel.r, etat.sel.c, lettre);
  avancerDansMot(1);
  rafraichir();
}

function basculerSolutions(actif) {
  etat.solutions = actif;
  solutionsBtn.textContent = actif ? "Masquer les solutions" : "Solutions";
  solutionsBtn.classList.toggle("actif", actif);
}

function ajusterTaille() {
  const { data } = etat;
  if (!data) return;
  const telephone = window.innerWidth < 600;
  const marge = telephone ? 26 : 90;
  const largeur = Math.min(window.innerWidth - marge, 900);
  const hauteur = window.innerHeight - (telephone ? 150 : 190);
  // Plancher : en dessous, les définitions ne tiennent plus (la passe
  // ajusterDebordements compense sur téléphone). Les grands formats
  // défilent, comme un magazine qu'on parcourt.
  const taille = Math.max(
    telephone ? 40 : 56,
    Math.min(64, Math.floor(largeur / data.width), Math.floor(hauteur / data.height))
  );
  grilleEl.style.setProperty("--cell", `${taille}px`);
  positionnerRails();
}

function positionnerRails() {
  // Centre la bande de zigzag entre le bord de l'écran et le cadre rouge.
  const plateau = document.querySelector(".plateau");
  const espace = Math.floor(plateau.getBoundingClientRect().left);
  // 178 px = largeur de la bande de zigzag (image 115 + décalage 63)
  const centrage = Math.max(0, (espace - 178) / 2);
  for (const rail of document.querySelectorAll(".rail")) {
    rail.classList.toggle("visible", espace >= 150);
    rail.style.width = `${espace}px`;
    rail.style.padding = `0 ${centrage}px`;
  }
}

async function chargerGrille(id) {
  const info = etat.index.grids.find((g) => g.id === id);
  const data = await (await fetch(`data/${info.file}`)).json();
  construireModele(data);
  etat.aides = new Set();
  etat.fautes = new Set();
  restaurer();
  basculerSolutions(false);
  afficherEtat(null);
  rendre();
  verifierCompletion();
  rafraichir();
  const url = new URL(window.location);
  url.searchParams.set("g", id);
  window.history.replaceState(null, "", url);
}

function grilleDuJour(index) {
  const debut = new Date(index.dailyStart + "T00:00:00");
  const jours = Math.max(0, Math.floor((Date.now() - debut) / 86_400_000));
  return index.dailyOrder[jours % index.dailyOrder.length];
}

function peuplerRails() {
  // Caricatures de footballeurs sur les côtés (img/joueurs/joueur-NN.png,
  // fournies par Nico) : les fichiers absents disparaissent sans bruit.
  const gauche = document.querySelector(".rail-gauche");
  const droite = document.querySelector(".rail-droite");
  for (let i = 1; i <= 24; i += 1) {
    const img = document.createElement("img");
    img.src = `img/joueurs/joueur-${String(i).padStart(2, "0")}.png`;
    img.alt = "";
    img.loading = "lazy";
    img.addEventListener("error", () => img.remove());
    (i % 2 ? gauche : droite).appendChild(img);
  }
}

async function demarrer() {
  peuplerRails();
  document.getElementById("date-jour").textContent =
    new Date().toLocaleDateString("fr-FR");
  etat.index = await (await fetch("data/index.json")).json();

  const parFormat = new Map();
  for (const g of etat.index.grids) {
    const clef = `${g.width} × ${g.height}`;
    if (!parFormat.has(clef)) parFormat.set(clef, []);
    parFormat.get(clef).push(g);
  }
  for (const [format, grilles] of parFormat) {
    const groupe = document.createElement("optgroup");
    groupe.label = format;
    for (const g of grilles) {
      const option = document.createElement("option");
      option.value = g.id;
      option.textContent = `${g.id} (difficulté ${g.difficulty})`;
      groupe.appendChild(option);
    }
    choixEl.appendChild(groupe);
  }

  const demande = new URL(window.location).searchParams.get("g");
  const id = etat.index.grids.some((g) => g.id === demande)
    ? demande
    : grilleDuJour(etat.index);
  choixEl.value = id;
  await chargerGrille(id);

  choixEl.addEventListener("change", () => chargerGrille(choixEl.value));
  sensBtn.addEventListener("click", () => {
    fixerSens(etat.dir === "h" ? "v" : "h");
    grilleEl.focus({ preventScroll: true });
  });
  solutionsBtn.addEventListener("click", () => {
    basculerSolutions(!etat.solutions);
    rafraichir();
  });
  verifierBtn.addEventListener("click", verifier);
  indiceBtn.addEventListener("click", indice);
  clavierEl.addEventListener("input", surSaisieMobile);
  document.addEventListener("keydown", surTouche);
  window.addEventListener("resize", () => {
    ajusterTaille();
    ajusterDebordements();
  });
}

demarrer();
