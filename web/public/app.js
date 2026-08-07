/* Grille jouable : rendu fidèle maquette + saisie clavier.
   Le sens de saisie (horizontal/vertical) se choisit : bouton du bandeau,
   ou nouveau clic sur la case déjà sélectionnée. */

const grilleEl = document.getElementById("grille");
const choixEl = document.getElementById("choix-grille");
const sensBtn = document.getElementById("sens");
const sensLibelle = document.getElementById("sens-libelle");

const etat = {
  data: null,      // JSON de la grille
  values: [],      // lettres saisies
  words: [],       // {cells: [[r,c]...], dir: "h"|"v"}
  cellWords: [],   // cellWords[r][c] = {h: index|null, v: index|null}
  sel: null,       // {r, c}
  dir: "h",
};

const FLAMME =
  '<svg viewBox="0 0 24 24" fill="#e3262a">' +
  '<path d="M12 2c1 4-3 5-3 9a3 3 0 0 0 6 0c0-2-1-3-1-3 3 1 5 3 5 7' +
  'a7 7 0 0 1-14 0c0-6 6-8 7-13z"/></svg>';

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
          clue.slots.forEach((slot, i) => {
            const slotEl = document.createElement("div");
            slotEl.className = "slot";
            if (slot.text.length > 55) slotEl.classList.add("tres-long");
            else if (slot.text.length > 32) slotEl.classList.add("long");
            slotEl.textContent = slot.text;
            slotEl.title = slot.text;
            slotEl.addEventListener("click", () => {
              selectionner(slot.row, slot.col, slot.horizontal ? "h" : "v");
            });
            div.appendChild(slotEl);
            div.appendChild(fleche(slot.arrow, i, clue.slots.length));
          });
        } else {
          div.className = "case deco";
          div.innerHTML = FLAMME;
        }
      } else {
        div.className = "case lettre";
        div.addEventListener("click", () => clicLettre(r, c));
      }
      grilleEl.appendChild(div);
    }
  }
  ajusterTaille();
  rafraichir();
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
      el.textContent = etat.values[r][c];
      el.classList.remove("mot-actif", "case-active");
    }
  }
  if (!etat.sel) return;
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
  grilleEl.focus({ preventScroll: true });
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

function surTouche(event) {
  if (!etat.sel || event.ctrlKey || event.metaKey || event.altKey) return;
  const { key } = event;
  if (key === "ArrowRight") deplacer(0, 1);
  else if (key === "ArrowLeft") deplacer(0, -1);
  else if (key === "ArrowDown") deplacer(1, 0);
  else if (key === "ArrowUp") deplacer(-1, 0);
  else if (key === "Backspace") {
    if (etat.values[etat.sel.r][etat.sel.c]) {
      etat.values[etat.sel.r][etat.sel.c] = "";
      rafraichir();
    } else {
      avancerDansMot(-1);
      etat.values[etat.sel.r][etat.sel.c] = "";
      rafraichir();
    }
  } else {
    const lettre = key
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toUpperCase();
    if (!/^[A-Z]$/.test(lettre)) return;
    etat.values[etat.sel.r][etat.sel.c] = lettre;
    avancerDansMot(1);
    rafraichir();
  }
  event.preventDefault();
}

function ajusterTaille() {
  const { data } = etat;
  if (!data) return;
  const largeur = Math.min(window.innerWidth - 90, 900);
  const hauteur = window.innerHeight - 190;
  const taille = Math.max(
    30,
    Math.min(64, Math.floor(largeur / data.width), Math.floor(hauteur / data.height))
  );
  grilleEl.style.setProperty("--cell", `${taille}px`);
}

async function chargerGrille(id) {
  const info = etat.index.grids.find((g) => g.id === id);
  const data = await (await fetch(`data/${info.file}`)).json();
  construireModele(data);
  rendre();
  const url = new URL(window.location);
  url.searchParams.set("g", id);
  window.history.replaceState(null, "", url);
}

function grilleDuJour(index) {
  const debut = new Date(index.dailyStart + "T00:00:00");
  const jours = Math.max(0, Math.floor((Date.now() - debut) / 86_400_000));
  return index.dailyOrder[jours % index.dailyOrder.length];
}

async function demarrer() {
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
  document.addEventListener("keydown", surTouche);
  window.addEventListener("resize", () => {
    ajusterTaille();
  });
}

demarrer();
