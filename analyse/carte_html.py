# -*- coding: utf-8 -*-
r"""
carte_html.py -- la carte des profils EN COULEURS, dans le navigateur

  python carte_html.py
  python carte_html.py --ouvre
  python carte_html.py --sortie cartes\ma_carte.html

POURQUOI UN SECOND FICHIER

    profils_croises.py sort de l ASCII : `###`, `XXX`, ` . `. Un
    terminal n a pas de degrade. La demande etait un tableau type
    nuancier, du plus rouge au plus vert -- ca ne se fait que dans un
    navigateur.

    Ce fichier ne recopie PAS la logique de profils_croises : il l
    IMPORTE. La fusion des jumeaux 206/207, le decoupage des seaux, la
    definition des familles et le seuil de Bonferroni viennent de la
    meme source. Deux copies de la regle de fusion qui divergent en
    silence, c est exactement ce qui a coute une soiree sur le plafond
    du REPL.

CE QUE LA PAGE CONTIENT

    TOUTES les pages sont calculees d avance et embarquees dans le
    fichier : 4 actifs x 2 cotes x 3 seances x 4 rails x 4 unites de
    temps = 384 grilles de 60 cases. Les menus ne rechargent rien, ils
    montrent ce qui est deja la. La page est autonome : aucun reseau,
    aucun serveur, aucun acces au fichier de trades. On peut la copier
    ailleurs, elle continue de fonctionner.

LA COULEUR

    Le fond de chaque case est une interpolation continue sur

        t = (moyenne - reference) * racine(n) / sigma

    et JAMAIS sur la moyenne seule -- sinon la case la plus verte
    serait toujours celle a trois signaux. Rouge sature a t = -seuil,
    vert sature a t = +seuil, avec le seuil de Bonferroni du nombre de
    cellules enumerees. Une case sous --min-n n est pas coloree du
    tout : elle reste grise et affiche son effectif en creux.

    LA REFERENCE EST CELLE DE LA PERIODE ET DE L ACTIF, pas celle de
    la page. C est ce qui rend deux pages comparables : si la
    reference bougeait avec la seance et le rails choisis, un vert sur
    une page et un vert sur une autre ne voudraient pas la meme chose.
    La moyenne de la page est affichee a part, pour memoire.

CE QU IL FAUT AVOIR EN TETE EN LA REGARDANT

    La reference post-cassure est NEGATIVE (-5,46 EUR/signal au
    14/08). Une case verte dit "mieux que -5,46", pas "gagnante". La
    moyenne reelle est ecrite dans la case, en euros : c est elle qui
    dit si on est au-dessus de zero, pas la couleur.

Lecteur SEUL : lit un .jsonl, ecrit un .html. Aucun ordre, aucun
collecteur, aucun etat modifie.
"""
import argparse
import io
import json
import math
import os
import sys
import datetime as dt

import profils_croises as pc

SORTIE = os.path.join("cartes", "panel_profils.html")

GAPS = (None, "WIDENING", "NARROWING", "STEADY")
CONS = (None, "ALIGNE", "PASALIGNE")
CHUR = (None, "CLEAN", "MIXED", "CHURN", "horsCHURN")
RAILS = (None, "TIGHT_CROSS", "MID", "WIDE")
SEANCES = ("toutes", "US", "hors")
COTES = ("DEPUIS", "AVANT")
UTS = ("M1", "M3", "M5", "M15")

ETI = {None: "indiff", "WIDENING": "WIDENING", "NARROWING": "NARROWING",
       "STEADY": "STEADY", "ALIGNE": "ALIGNE", "PASALIGNE": "PAS ALIGNE",
       "CLEAN": "CLEAN", "MIXED": "MIXED", "CHURN": "CHURN",
       "horsCHURN": "hors CHURN", "TIGHT_CROSS": "TIGHT", "MID": "MID",
       "WIDE": "WIDE"}


def cle(cote, actif, seance, rails, ut):
    return "%s|%s|%s|%s|%s" % (cote, actif, seance, rails or "-", ut)


def calcule(sig, a):
    """Toutes les grilles, d avance. Rend (donnees, references).

    La reference d une case est celle de sa PERIODE et de son ACTIF --
    volontairement pas celle de la page. Deux pages deviennent ainsi
    comparables entre elles."""
    actifs = sorted(set(s["actif"] for s in sig)) + ["TOUS"]
    donnees, refs = {}, {}

    for cote in COTES:
        for actif in actifs:
            base = [s for s in sig if s["jour"]
                    and ((s["jour"] >= a.cassure) == (cote == "DEPUIS"))
                    and (actif == "TOUS" or s["actif"] == actif)]
            if not base:
                continue
            mref = sum(s["pnl"] for s in base) / len(base)
            refs["%s|%s" % (cote, actif)] = [round(mref, 2), len(base)]
            for seance in SEANCES:
                lot1 = [s for s in base
                        if seance == "toutes" or s["seance"] == seance]
                for rails in RAILS:
                    lot = [s for s in lot1
                           if rails is None or s["rails"] == rails]
                    if not lot:
                        continue
                    mpage = sum(s["pnl"] for s in lot) / len(lot)
                    for ut in UTS:
                        cases = []
                        for g in GAPS:
                            for c2 in CONS:
                                ligne = []
                                for ch in CHUR:
                                    v = [s["pnl"] for s in lot
                                         if (g is None
                                             or s["gap"].get(ut) == g)
                                         and (c2 is None
                                              or pc.colle(s, "cons", c2, ut))
                                         and (ch is None
                                              or pc.colle(s, "churn", ch, ut))]
                                    n = len(v)
                                    if n == 0:
                                        ligne.append([0, 0, 0])
                                        continue
                                    m = sum(v) / n
                                    t = (m - mref) * math.sqrt(n) / a.sigma
                                    ligne.append([n, round(m, 1),
                                                  round(t, 2)])
                                cases.append(ligne)
                        donnees[cle(cote, actif, seance, rails, ut)] = {
                            "n": len(lot), "moy": round(mpage, 2),
                            "c": cases}
    return donnees, refs, actifs


def routes(chemin):
    """Les routes servies, LUES dans price_action.py au moment de la
    generation.

    Une liste ecrite en dur ici divergerait le jour ou une route est
    ajoutee ou renommee -- c est le motif des deux constantes jumelles
    qui a coute une soiree le 14/08. On la relit, donc elle ne peut pas
    mentir.

    Les /api/ sont ecartees : ce sont des points de donnees, pas des
    pages. Si le fichier est introuvable, on rend une barre minimale
    plutot que rien : une carte sans navigation reste lisible, une
    carte qui refuse de se generer ne sert a personne."""
    mini = ["/repl", "/raw", "/rails_trades"]
    try:
        src = io.open(chemin, encoding="utf-8", errors="replace").read()
    except IOError:
        return mini, False
    import re as _re
    vues = _re.findall(r'parsed\.path == "(/[^"]*)"', src)
    prop = sorted(set(r for r in vues
                      if r != "/" and not r.startswith("/api/")))
    return (prop, True) if prop else (mini, False)


def etiquette(r):
    return r.lstrip("/").replace("_", " ").upper()


CSS = r"""
:root { color-scheme: dark; }
body { background:#0e1116; color:#c9d1d9; margin:0; padding:18px 22px;
       font:15px/1.5 Consolas,"DejaVu Sans Mono",monospace; }
h1 { font-size:19px; margin:0 0 4px; color:#e6edf3; font-weight:600; }
.sous { color:#7d8590; margin:0 0 16px; font-size:13px; }
.barre { display:flex; flex-wrap:wrap; gap:14px; align-items:flex-end;
         background:#161b22; border:1px solid #30363d; border-radius:6px;
         padding:10px 14px; margin-bottom:14px; }
.champ { display:flex; flex-direction:column; gap:3px; }
.champ label { font-size:10px; text-transform:uppercase;
               letter-spacing:.08em; color:#7d8590; }
select { background:#0d1117; color:#c9d1d9; border:1px solid #30363d;
         border-radius:4px; padding:4px 8px; font:inherit; }
.entete { background:#161b22; border:1px solid #30363d; border-radius:6px;
          padding:12px 16px; margin-bottom:14px; font-size:14px; }
.entete b { color:#e6edf3; }
.gros { font-size:17px; }
table { border-collapse:separate; border-spacing:2px; margin:0 0 22px; }
caption { text-align:left; color:#e6edf3; font-size:15px; padding:8px 0;
          font-weight:600; }
th { font-weight:500; font-size:13px; color:#8b949e; padding:5px 10px;
     text-align:center; white-space:nowrap; }
th.ligne { text-align:right; }
td { width:118px; height:54px; text-align:center; border-radius:4px;
     padding:2px; vertical-align:middle; }
.moy { display:block; font-size:17px; font-weight:600; }
.eff { display:block; font-size:12px; opacity:.78; }
.vide { background:#12161c; color:#3d444d; }
.souscrit { background:#161b22; color:#565f6b; }
.leg { display:flex; align-items:center; gap:0; margin:2px 0 10px; }
.leg i { display:block; width:34px; height:18px; font-style:normal; }
.note { color:#7d8590; font-size:13px; max-width:1100px; margin:0 0 8px; }
.note b { color:#c9d1d9; }
.avert { border-left:3px solid #d29922; padding:8px 12px; margin:14px 0;
         background:#1c1a12; color:#c9d1d9; max-width:980px;
         font-size:13px; }
.sep { height:1px; background:#21262d; margin:22px 0 16px; }
.chrome { position:sticky; top:0; z-index:9; display:flex; gap:12px;
          align-items:center; flex-wrap:wrap; background:#161b22;
          border-bottom:1px solid #30363d; padding:8px 22px;
          margin:-18px -22px 16px; }
.chrome .titre { color:#e6edf3; font-weight:600; }
.chrome a, .chrome button { background:#0d1117; color:#58a6ff;
          border:1px solid #30363d; border-radius:4px; padding:5px 12px;
          font:inherit; font-weight:bold; text-decoration:none;
          cursor:pointer; }
.chrome a:hover, .chrome button:hover { border-color:#58a6ff; }
.chrome .quand { color:#7d8590; font-size:12px; margin-left:auto; }
#etat { font-size:12px; }
.nav { display:flex; flex-wrap:wrap; gap:4px; margin:0 0 16px;
       max-height:190px; overflow-y:auto; padding:8px;
       background:#0d1117; border:1px solid #21262d;
       border-radius:6px; }
.nav a { color:#58a6ff; text-decoration:none; font-size:11px;
         font-weight:bold; padding:3px 7px; border-radius:3px;
         border:1px solid #21262d; white-space:nowrap; }
.nav a:hover { border-color:#58a6ff; background:#161b22; }
.nav a.ici { color:#0d1117; background:#58a6ff;
             border-color:#58a6ff; }
.navt { color:#7d8590; font-size:11px; margin:0 0 4px; }
"""

# BRUTE (r""") : ce bloc contient du JavaScript, donc des
# echappements qui appartiennent a JS et non a Python. Sans le r,
# Python transforme le \n de L.join("\\n") en vraie fin de ligne
# DANS le litteral JavaScript -- erreur de syntaxe, script mort, et
# la page s affiche vide sans aucun message. Vu le 14/08 a 21:34.
JS = r"""
const D = DONNEES, R = REFERENCES, SEUIL = SEUILT, MINN = MINEFF;
const GAPS = GAPSJS, CONS = CONSJS, CHUR = CHURJS, UTS = UTSJS;

// Les deux branches partent du MEME neutre. Une premiere version avait
// un neutre par branche -- violace d un cote, bleute de l autre -- et
// la barre de legende montrait une couture au centre, la ou l echelle
// est censee ne rien dire.
const NEUT = [32, 36, 42], ROUGE = [152, 28, 32], VERT = [24, 138, 56];
function coul(t) {
  const x = Math.max(-1, Math.min(1, t / SEUIL));
  const a = Math.pow(Math.abs(x), 0.7);
  const c = x >= 0 ? VERT : ROUGE;
  return "rgb(" + Math.round(NEUT[0] + (c[0] - NEUT[0]) * a) + ","
    + Math.round(NEUT[1] + (c[1] - NEUT[1]) * a) + ","
    + Math.round(NEUT[2] + (c[2] - NEUT[2]) * a) + ")";
}
function txt(t) {
  return Math.abs(t) / SEUIL > 0.55 ? "#f0f6fc" : "#c9d1d9";
}
// La legende est peinte par coul(), pas par une seconde formule. Une
// legende dessinee a part finit toujours par mentir sur l echelle qu
// elle decrit ; ici elle ne peut pas.
(function () {
  let h = "";
  for (let i = 0; i <= 40; i++)
    h += "<i style='background:" + coul(SEUIL * (i - 20) / 20) + "'></i>";
  document.getElementById("leg").innerHTML = h;
})();
function v(id) { return document.getElementById(id).value; }

function dessine() {
  const cote = v("cote"), actif = v("actif"), seance = v("seance"),
        rails = v("rails");
  const ref = R[cote + "|" + actif];
  const e = document.getElementById("entete");
  if (!ref) { e.innerHTML = "Aucun signal.";
              document.getElementById("grilles").innerHTML = ""; return; }
  e.innerHTML = "<span class='gros'>reference de la periode : <b>"
    + (ref[0] > 0 ? "+" : "") + ref[0].toFixed(2) + " EUR/signal</b></span>"
    + " sur " + ref[1] + " signaux (" + cote + " la cassure, actif "
    + actif + ").<br>La couleur mesure l ecart <b>a cette reference</b>."
    + (ref[0] < 0 ? " Elle est <b>negative</b> : une case verte dit"
       + " &laquo; mieux que " + ref[0].toFixed(2) + " &raquo;, pas"
       + " &laquo; gagnante &raquo;. Le chiffre en euros dans la case dit"
       + " le niveau reel." : "");

  const choix = v("ut");
  const vues = choix === "toutes" ? UTS : [choix];
  let h = "";
  for (const ut of vues) {
    const k = cote + "|" + actif + "|" + seance + "|" + rails + "|" + ut;
    const g = D[k];
    if (!g) { h += "<p class='note'>ut " + ut
              + " : aucun signal dans cette page.</p>"; continue; }
    h += "<table><caption>unite de temps " + ut + " &mdash; " + g.n
      + " signaux dans la page, moyenne de page "
      + (g.moy > 0 ? "+" : "") + g.moy.toFixed(2) + "</caption><tr><th></th>";
    for (const c of CHUR) h += "<th>" + c + "</th>";
    h += "</tr>";
    let i = 0;
    for (const gp of GAPS) for (const cs of CONS) {
      h += "<tr><th class='ligne'>" + gp + " / " + cs + "</th>";
      for (let j = 0; j < CHUR.length; j++) {
        const c = g.c[i][j], n = c[0], m = c[1], t = c[2];
        if (n === 0) h += "<td class='vide'>&middot;</td>";
        else if (n < MINN) h += "<td class='souscrit'><span class='moy'>"
          + (m > 0 ? "+" : "") + m.toFixed(1) + "</span><span class='eff'>n="
          + n + "</span></td>";
        else h += "<td style='background:" + coul(t) + ";color:" + txt(t)
          + "'><span class='moy'>" + (m > 0 ? "+" : "") + m.toFixed(1)
          + "</span><span class='eff'>n=" + n + " &middot; t="
          + (t > 0 ? "+" : "") + t.toFixed(2) + "</span></td>";
      }
      h += "</tr>";
      i++;
    }
    h += "</table>";
  }
  document.getElementById("grilles").innerHTML = h;
}
// --- le bouton copier -------------------------------------------------
// Il rend du TEXTE et non du HTML : la destination est le REPL, pas un
// navigateur. C est par ce bouton que les chiffres d une page arrivent
// dans une conversation ; une page sans lui est une page dont on ne
// peut pas discuter.
function pad(s, n) {
  s = String(s);
  while (s.length < n) s += " ";
  return s;
}
function texte() {
  const cote = v("cote"), actif = v("actif"), seance = v("seance"),
        rails = v("rails");
  const ref = R[cote + "|" + actif];
  const L = [];
  L.push("CARTE DES PROFILS -- cote " + cote + " | actif " + actif
         + " | seance " + seance + " | rails " + rails);
  if (ref) L.push("reference de la periode : " + ref[0].toFixed(2)
                  + " EUR/signal sur " + ref[1] + " signaux");
  L.push("t = (moyenne - reference) x racine(n) / sigma. Seuil de");
  L.push("Bonferroni |t| >= " + SEUIL.toFixed(2) + " sur les cellules");
  L.push("enumerees. Sous " + MINN + " signaux : pas de t, non mesurable.");
  L.push("Ces cellules ont ete ENUMEREES, pas annoncees d avance.");
  const vues = v("ut") === "toutes" ? UTS : [v("ut")];
  for (const ut of vues) {
    const g = D[cote + "|" + actif + "|" + seance + "|" + rails + "|" + ut];
    L.push("");
    if (!g) { L.push("ut " + ut + " : aucun signal dans cette page.");
              continue; }
    L.push("ut " + ut + " -- " + g.n + " signaux dans la page, moyenne "
           + g.moy.toFixed(2));
    L.push(pad("gap / consensus", 26) + pad("churn", 12) + pad("n", 7)
           + pad("moy", 9) + "t");
    let i = 0;
    for (const gp of GAPS) for (const cs of CONS) {
      for (let j = 0; j < CHUR.length; j++) {
        const c = g.c[i][j];
        if (c[0] === 0) continue;
        L.push(pad(gp + " / " + cs, 26) + pad(CHUR[j], 12)
               + pad(c[0], 7) + pad(c[1].toFixed(1), 9)
               + (c[0] < MINN ? "n<" + MINN : c[2].toFixed(2)));
      }
      i++;
    }
  }
  return L.join("\n");
}
function copier() {
  const t = texte();
  const e = document.getElementById("etat");
  function fin(ok) {
    e.textContent = ok ? "copie, " + t.length + " caracteres"
                       : "copie impossible -- selectionne la page a la main";
    e.style.color = ok ? "#3fb950" : "#f85149";
    setTimeout(function () { e.textContent = ""; }, 5000);
  }
  // navigator.clipboard exige un contexte SUR. Cette page est servie en
  // http:// sur un nom de machine, donc l API y est absente et un
  // bouton ecrit naivement ne ferait rien, sans erreur visible. La zone
  // de texte cachee marche dans les deux cas ; l API moderne n est
  // qu un repli.
  try {
    const z = document.createElement("textarea");
    z.value = t;
    z.style.position = "fixed";
    z.style.top = "-1000px";
    document.body.appendChild(z);
    z.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(z);
    if (ok) { fin(true); return; }
  } catch (err) { /* on tente l API en dessous */ }
  if (navigator.clipboard) {
    navigator.clipboard.writeText(t).then(function () { fin(true); },
                                          function () { fin(false); });
  } else { fin(false); }
}
document.getElementById("copier").addEventListener("click", copier);

for (const id of ["cote", "actif", "seance", "rails", "ut"])
  document.getElementById(id).addEventListener("change", dessine);
dessine();
"""


def page(donnees, refs, actifs, zc, a, nsig, nbrut, cellules):
    def opts(vals, defaut):
        return "".join(
            '<option value="%s"%s>%s</option>'
            % (x, " selected" if x == defaut else "", ETI.get(x, x))
            for x in vals)

    liste, lues = routes(a.panneau)
    nav_titre = ("%d routes lues dans %s"
                 % (len(liste), a.panneau)) if lues else \
        ("%s illisible -- navigation minimale" % a.panneau)
    nav_html = "".join(
        '<a href="%s"%s>%s</a>'
        % (r, ' class="ici"' if r == "/profils" else "",
           etiquette(r)) for r in liste)

    js = JS
    js = js.replace("DONNEES", json.dumps(donnees, separators=(",", ":")))
    js = js.replace("REFERENCES", json.dumps(refs, separators=(",", ":")))
    js = js.replace("SEUILT", "%.4f" % zc)
    js = js.replace("MINEFF", str(a.min_n))
    js = js.replace("GAPSJS", json.dumps([ETI[g] for g in GAPS]))
    js = js.replace("CONSJS", json.dumps([ETI[c] for c in CONS]))
    js = js.replace("CHURJS", json.dumps([ETI[c] for c in CHUR]))
    js = js.replace("UTSJS", json.dumps(list(UTS)))

    return (
        "<!doctype html><html lang=fr><head><meta charset=utf-8>"
        "<title>Carte des profils</title><style>%s</style></head><body>"
        "<div class=chrome>"
        "<span class=titre>Carte des profils</span>"
        "<a href=\"/\">&larr; PANNEAU</a>"
        "<a href=\"/repl\">REPL</a>"
        "<button id=copier>copier</button>"
        "<span id=etat></span>"
        "<span class=quand>%d signaux &middot; cassure au %s &middot; "
        "genere le %s</span>"
        "</div>"
        "<p class=sous>%d enregistrements &rarr; %d signaux (jumeaux "
        "206/207 fusionnes) &middot; sigma = %.0f EUR</p>"
        "<div class=barre>"
        "<div class=champ><label>cote</label><select id=cote>%s</select></div>"
        "<div class=champ><label>actif</label><select id=actif>%s</select>"
        "</div>"
        "<div class=champ><label>seance</label><select id=seance>%s</select>"
        "</div>"
        "<div class=champ><label>rails</label><select id=rails>%s</select>"
        "</div>"
        "<div class=champ><label>unite de temps</label>"
        "<select id=ut>%s</select></div>"
        "</div>"
        "<p class=navt>%s</p>"
        "<div class=nav>%s</div>"
        "<div class=entete id=entete></div>"
        "<div class=leg id=leg></div>"
        "<p class=note>Gauche : t = &minus;%.2f. Droite : t = +%.2f. "
        "C est le seuil de <b>Bonferroni</b> pour les %d cellules "
        "enumerees &mdash; pas 1,96, pas 2,9. Une case atteint le bord de "
        "l echelle seulement si elle passe ce seuil.</p>"
        "<p class=note>Le fond code <b>t = (moyenne &minus; reference) "
        "&times; racine(n) / sigma</b>, jamais la moyenne seule : sans le "
        "racine(n), la case la plus verte serait toujours celle a trois "
        "signaux. Le gros chiffre est la <b>moyenne en euros</b>, la ligne "
        "du dessous l effectif et le t. Sous %d signaux la case reste "
        "<b>grise</b> : elle affiche sa moyenne mais n est pas coloree, "
        "parce qu a cet effectif la couleur ne voudrait rien dire.</p>"
        "<div class=avert>Ces %d cellules ont ete <b>enumerees, pas "
        "annoncees d avance</b>. Une case verte est un candidat a ecrire "
        "dans HYPOTHESES.md et a mesurer sur donnees neuves &mdash; jamais "
        "une regle a appliquer. Le seuil corrige le nombre de cases ; il ne "
        "corrige pas le fait qu on a choisi apres avoir vu.</div>"
        "<div class=sep></div>"
        "<div id=grilles></div>"
        "<script>%s</script></body></html>"
    ) % (CSS, nsig, a.cassure,
         dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), nbrut, nsig,
         a.sigma,
         opts(COTES, "DEPUIS"), opts(actifs, "TOUS"),
         opts(SEANCES, "US"), opts([r or "-" for r in RAILS], "-"),
         opts(("toutes",) + UTS, "toutes"),
         nav_titre, nav_html,
         zc, zc, cellules, a.min_n, cellules, js)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trades", default=pc.TRADES)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--cassure", default=pc.CASSURE)
    p.add_argument("--sigma", type=float, default=pc.SIGMA)
    p.add_argument("--min-n", type=int, default=pc.MIN_N, dest="min_n")
    p.add_argument("--limite", type=int, default=200000)
    p.add_argument("--panneau", default="price_action.py",
                   help="fichier ou lire les routes servies")
    p.add_argument("--ouvre", action="store_true",
                   help="ouvre la page dans le navigateur par defaut")
    a = p.parse_args()

    brut = pc.charger(a.trades, a.limite)
    if not brut:
        print("KO : %s introuvable ou vide." % a.trades)
        print("     Lance depuis le dossier de la stack.")
        return 1
    sig = pc.signaux(brut, list(UTS))
    if not sig:
        print("KO : aucun signal exploitable (entry_captured_live ?).")
        return 1

    donnees, refs, actifs = calcule(sig, a)
    cellules = len(donnees) * len(GAPS) * len(CONS) * len(CHUR)
    zc = pc.seuil_bonferroni(cellules)
    print("%d enregistrements -> %d signaux." % (len(brut), len(sig)))
    print("%d grilles x 60 cases = %d cellules -> seuil |t| >= %.2f"
          % (len(donnees), cellules, zc))

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write(
        page(donnees, refs, actifs, zc, a, len(sig), len(brut), cellules))
    plein = os.path.abspath(a.sortie)
    print("ecrit : %s (%d octets)" % (a.sortie, os.path.getsize(a.sortie)))
    print()
    print("Ouvre : %s" % plein)
    print("La page est autonome -- aucun reseau, aucun serveur. Elle ne")
    print("touche pas au panneau 8095 et ne relit pas les trades.")

    if a.ouvre:
        # webbrowser plutot que start : pas de shell, pas de guillemets a
        # echapper dans un chemin qui contient des espaces.
        import webbrowser
        webbrowser.open("file:///" + plein.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
