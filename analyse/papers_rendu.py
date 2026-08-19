# -*- coding: utf-8 -*-
r"""
papers_rendu.py -- le rendu des papers, en couleur, ET copiable

  python papers_rendu.py
  python papers_rendu.py --detail 80

LECTEUR SEUL. N ENVOIE AUCUN ORDRE, N IMPORTE PAS MetaTrader5.
Il ecrit UNIQUEMENT cartes\papers_rendu.html et panels\.

POURQUOI UN BOUTON COPIER DANS LA PAGE

    Un panneau que tu ne peux pas me renvoyer ne sert qu a toi. Les
    autres cartes ont leur bouton ; celle-ci n en avait pas, donc le
    rendu restait sur ton ecran.

    La page embarque donc SON PROPRE texte, en clair, avec un bouton
    qui le met dans le presse-papier -- et un repli : un bloc
    depliable, selectionnable a la main si le navigateur refuse le
    presse-papier. Le meme texte est aussi ecrit dans
    panels\panel_papers_rendu.txt, lisible avec `type`.

    Les deux sorties sortent des MEMES nombres, calcules une fois :
    stats() et calc_croise() servent au HTML comme au texte. Deux
    calculs auraient diverge.

LA FENETRE OBSERVEE

    Le panneau lit FENETRE dans papers_moteur.py et teste les positions
    ouvertes avec sa fonction dans_fenetre(). Montrer un paper en
    position sur un ticket que le moteur n aurait jamais pris serait
    pire qu une absence : ce serait faux sans en avoir l air.

CE QU IL MONTRE, DANS CET ORDRE

 1. QUI EST EN POSITION, DEPUIS QUAND, COMBIEN.
    Le journal des tickets contient aussi les trades ENCORE OUVERTS :
    ils portent un volume mais pas de pnl_eur. Le moteur les saute --
    il ne peut pas dimensionner un resultat qui n existe pas encore.
    Ce panneau, lui, pose la MEME question a chaque paper sur ces
    tickets-la : l aurais-tu pris ? La question est posee par
    papers_moteur.accepte() -- la fonction du moteur, importee.

 2. LE RENDU, un paper par ligne : prises, WR, Wilson, PnL, PnL/trade,
    RR realise, RR d equilibre, Sharpe par trade, MFE/MAE, pire creux,
    balance, courbe.

 3. PAR HEURE (Paris), PAR ACTIF, PAR SETUP, PAR UNITE DE TEMPS.
    Le journal des prises garde le TICKET, pas le setup : ces vues
    viennent d une jointure sur tickets_rails.jsonl. La vue PAR HEURE
    sert aussi de controle : aucune ligne ne doit sortir de la fenetre.

 4. LE DETAIL des dernieres prises.

CE QUE LE SHARPE VEUT DIRE ICI

    Moyenne / ecart-type des PnL PAR TRADE. Ce n est pas un Sharpe
    annualise : il n y a ni taux sans risque ni periode de reference.
    Il sert a comparer les 17 entre eux, pas a etre publie.

CE QUE CE PANNEAU NE PEUT PAS DIRE

    Les papers filtrent les entrees du moteur churn, ils ne les
    choisissent pas. Un paper qui bat les autres a mieux FILTRE -- il
    n a pas mieux TIME.
"""
import argparse
import io
import json
import math
import os
import sys

SOURCE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
JOURNAL = os.path.join("docs", "papers_live", "trades.jsonl")
SORTIE_H = os.path.join("cartes", "papers_rendu.html")
SORTIE_T = os.path.join("panels", "panel_papers_rendu.txt")

VERT, ROUGE, BLEU, JAUNE = "#3fb950", "#f85149", "#58a6ff", "#e3b341"
GRIS, TEXTE, MAUVE = "#6e7681", "#e6edf3", "#d2a8ff"

CSS = """
body{background:#0d1117;color:#e6edf3;font:13px -apple-system,Segoe UI,
 Roboto,Helvetica,Arial,sans-serif;margin:0;padding:18px 22px}
h3{color:#e6edf3;font-size:17px;margin:0 0 4px}
h4{color:#e6edf3;font-size:14px;margin:22px 0 6px;
 border-bottom:1px solid #21262d;padding-bottom:4px}
table{border-collapse:collapse;margin:6px 0 2px;font-size:12px}
td,th{padding:3px 9px 3px 0;text-align:left;white-space:nowrap}
th{color:#6e7681;font-weight:600}
tr:hover td{background:#161b22}
.leg{color:#8b949e;font-size:11.5px;margin:2px 0 8px;line-height:1.5;
 max-width:1000px}
.num{text-align:right}
button{background:#238636;color:#fff;border:1px solid #2ea043;
 border-radius:6px;padding:7px 14px;font-size:12.5px;font-weight:600;
 cursor:pointer;margin:0 8px 0 0}
button:hover{background:#2ea043}
details{margin:8px 0}
summary{color:#58a6ff;cursor:pointer;font-size:12px}
pre{background:#0e1116;color:#c9d1d9;font:11.5px Consolas,monospace;
 padding:12px 14px;overflow:auto;border:1px solid #21262d;border-radius:6px}
"""

JS = """
function papersCopie(){
  var t=document.getElementById('brut'), b=document.getElementById('bcopie');
  t.style.display='block'; t.select(); t.setSelectionRange(0,999999);
  var ok=false;
  try{ ok=document.execCommand('copy'); }catch(e){}
  t.style.display='none';
  if(!ok && navigator.clipboard){
    navigator.clipboard.writeText(t.value).then(function(){
      b.textContent='copie !';});
    return;
  }
  b.textContent = ok ? 'copie !' : 'echec -- ouvre le bloc et Ctrl+C';
}
"""


# ======================================================================
# lecture
# ======================================================================
def lire_jsonl(chemin):
    out, ko = [], 0
    if not os.path.isfile(chemin):
        return out, ko
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                ko += 1
                continue
            if isinstance(o, dict):
                out.append(o)
    return out, ko


def esc(x):
    return (u"%s" % x).replace("&", "&amp;").replace("<", "&lt;") \
                      .replace(">", "&gt;")


def col(v):
    return VERT if v > 0 else (ROUGE if v < 0 else GRIS)


def eur(v, d=0):
    return "<td class='num' style='color:%s;font-weight:700'>%+.*f</td>" \
        % (col(v), d, v)


# ======================================================================
# calcul -- une seule fois, pour les deux sorties
# ======================================================================
def stats(prises, PM):
    n = len(prises)
    if not n:
        return None
    pnls = [p.get("pnl") or 0.0 for p in prises]
    gains = [x for x in pnls if x > 0]
    pertes = [-x for x in pnls if x < 0]
    tot = sum(pnls)
    moy = tot / n
    p = len(gains) / float(n)
    ec = math.sqrt(sum((x - moy) ** 2 for x in pnls) / n)
    cum, haut, creux = 0.0, 0.0, 0.0
    for x in pnls:
        cum += x
        haut = max(haut, cum)
        creux = min(creux, cum - haut)
    return {
        "n": n, "wr": 100.0 * p, "tot": tot, "moy": moy,
        "rr": ((sum(gains) / len(gains)) / (sum(pertes) / len(pertes)))
              if gains and pertes else None,
        "rr_eq": PM.rr_equilibre(p),
        "wilson": 100.0 * PM.wilson_bas(p, n),
        "sharpe": (moy / ec) if ec > 0 else None,
        "mfe": sum(q.get("mfe") or 0.0 for q in prises) / n,
        "mae": sum(q.get("mae") or 0.0 for q in prises) / n,
        "creux": creux, "balance": prises[-1].get("balance"),
        "debut": min(q.get("ts") or "" for q in prises),
        "fin": max(q.get("ts") or "" for q in prises)}


def calc_positions(jeu, tickets, PM, fenetre):
    """Rend (n_ouverts, [(magic, nom, n, depuis, actifs, sens)]).

    La fenetre est celle du moteur, testee par sa propre fonction : un
    paper ne peut pas etre montre en position sur un ticket qu il n
    aurait jamais pris.
    """
    ouverts = [t for t in tickets
               if isinstance(t.get("volume"), (int, float))
               and t.get("volume") > 0 and t.get("pnl_eur") is None
               and isinstance(t.get("entry_ts"), str)
               and PM.dans_fenetre(t, fenetre)]
    out = []
    for magic, nom, actif, sens, pred in jeu:
        pris = [t for t in ouverts
                if PM.accepte((magic, nom, actif, sens, pred), t)]
        if not pris:
            continue
        out.append((magic, nom, len(pris),
                    min(t["entry_ts"] for t in pris),
                    ", ".join(sorted(set(t.get("asset") or "?"
                                         for t in pris))),
                    "/".join(sorted(set(t.get("dir") or "?"
                                        for t in pris)))))
    return len(ouverts), out


def calc_rendu(jeu, par, PM):
    lignes = [(m, nom, actif, stats(par.get(m) or [], PM))
              for m, nom, actif, _s, _p in jeu]
    lignes.sort(key=lambda x: -(x[3]["tot"] if x[3] else -1e18))
    return lignes


def calc_croise(jeu, par, cle):
    dims = {}
    for magic, nom, actif, sens, pred in jeu:
        for p in par.get(magic) or []:
            k = cle(p)
            if k is None:
                continue
            d = dims.setdefault(k, {}).setdefault(magic, [0, 0, 0.0])
            d[0] += 1
            d[1] += 1 if (p.get("pnl") or 0) > 0 else 0
            d[2] += p.get("pnl") or 0.0
    return dims


def resume_croise(dims, ordre=None):
    """[(cle, n, wr, pnl, meilleur, son_pnl, pire, son_pnl)]"""
    out = []
    for k in (ordre or sorted(dims)):
        if k not in dims:
            continue
        d = dims[k]
        n = sum(v[0] for v in d.values())
        w = sum(v[1] for v in d.values())
        tot = sum(v[2] for v in d.values())
        best = max(d.items(), key=lambda x: x[1][2])
        pire = min(d.items(), key=lambda x: x[1][2])
        out.append((k, n, 100.0 * w / n if n else 0.0, tot,
                    best[0], best[1][2], pire[0], pire[1][2]))
    return out


def courbe(prises, w=118, h=26):
    if len(prises) < 2:
        return "<td></td>"
    cum, pts = 0.0, []
    for p in prises:
        cum += p.get("pnl") or 0.0
        pts.append(cum)
    lo, hi = min(pts + [0.0]), max(pts + [0.0])
    ec = (hi - lo) or 1.0
    n = len(pts)
    xy = " ".join("%.1f,%.1f" % (w * i / float(n - 1),
                                 h - (h - 2) * (v - lo) / ec - 1)
                  for i, v in enumerate(pts))
    zero = h - (h - 2) * (0.0 - lo) / ec - 1
    return ("<td><svg width='%d' height='%d'>"
            "<line x1='0' y1='%.1f' x2='%d' y2='%.1f' stroke='#30363d' "
            "stroke-width='1'/><polyline points='%s' fill='none' "
            "stroke='%s' stroke-width='1.4'/></svg></td>"
            % (w, h, zero, w, zero, xy, col(pts[-1])))


# ======================================================================
# rendu HTML
# ======================================================================
def h_positions(add, n_ouv, pos, n_papers):
    add("<h4>&#128308; QUI EST EN POSITION &mdash; maintenant, et depuis "
        "quand</h4>")
    add("<div class='leg'>Tickets du moteur churn encore OUVERTS "
        "(volume present, pnl absent) ET dans la fenetre, passes au "
        "filtre de chaque paper par <b>papers_moteur.accepte()</b> "
        "&mdash; la fonction du moteur, importee, pas reecrite. Aucun "
        "ordre n est envoye : c est ce que le paper AURAIT en "
        "position.</div>")
    if not n_ouv:
        add("<div class='leg' style='color:%s'>Aucun ticket ouvert dans "
            "la fenetre : le journal ne contient que des trades clos, ou "
            "les ouverts tombent hors plage horaire. Cette section "
            "restera vide tant que ce sera le cas.</div>" % JAUNE)
        return
    add("<div class='leg'>%d ticket(s) ouvert(s) dans la fenetre.</div>"
        % n_ouv)
    add("<table><tr><th>magic</th><th>paper</th><th class='num'>pos.</th>"
        "<th>depuis</th><th>actifs</th><th>sens</th></tr>")
    for magic, nom, n, depuis, acts, sens in pos:
        add("<tr><td style='color:%s;font-weight:700'>%d</td><td>%s</td>"
            "<td class='num' style='color:%s;font-weight:700'>%d</td>"
            "<td style='color:%s'>%s</td><td>%s</td>"
            "<td style='color:%s;font-weight:700'>%s</td></tr>"
            % (JAUNE, magic, esc(nom), BLEU, n, GRIS, esc(depuis),
               esc(acts), VERT if sens == "BUY" else ROUGE, esc(sens)))
    add("</table>")
    add("<div class='leg'>%d paper(s) sans aucune position ouverte.</div>"
        % (n_papers - len(pos)))


def h_rendu(add, lignes, par, periode):
    add("<h4>&#127942; LE RENDU &mdash; un paper par ligne</h4>")
    add("<div class='leg'>Balance fictive de depart 20 000, lot = "
        "balance / 20 000 (plancher 0,01). <b>RR eq.</b> = "
        "(1&minus;p)/p : le rapport gain/perte qu il FAUT atteindre pour "
        "etre a l equilibre a ce taux &mdash; le seul chiffre qu on ne "
        "peut pas surajuster. <b>Wilson</b> = borne basse a 95&nbsp;% du "
        "taux : ce qu on peut affirmer, pas ce qu on a vu. "
        "<b>Sharpe</b> = moyenne / ecart-type PAR TRADE, non "
        "annualise.</div>")
    if periode:
        add("<div class='leg'>Periode couverte : <b>%s</b> &rarr; "
            "<b>%s</b>. La colonne <b>prises</b> est le nombre de trades "
            "pris sur cette periode.</div>"
            % (esc(periode[0]), esc(periode[1])))
    add("<table><tr><th>magic</th><th>paper</th><th>actif</th>"
        "<th class='num'>prises</th><th class='num'>WR</th>"
        "<th class='num'>Wilson</th><th class='num'>PnL</th>"
        "<th class='num'>PnL/tr</th><th class='num'>RR</th>"
        "<th class='num'>RR eq.</th><th class='num'>Sharpe</th>"
        "<th class='num'>MFE</th><th class='num'>MAE</th>"
        "<th class='num'>creux</th><th class='num'>balance</th>"
        "<th>courbe</th><th>derniere</th></tr>")
    for magic, nom, actif, s in lignes:
        if not s:
            add("<tr><td style='color:%s;font-weight:700'>%d</td><td>%s</td>"
                "<td>%s</td><td class='num' style='color:%s'>0</td>"
                "<td colspan='13' style='color:%s'>aucune prise</td></tr>"
                % (GRIS, magic, esc(nom), esc(actif or "tous"), GRIS, GRIS))
            continue
        rr = "%.2f" % s["rr"] if s["rr"] is not None else "&ndash;"
        sh = "%.2f" % s["sharpe"] if s["sharpe"] is not None else "&ndash;"
        # Sans aucune perte, le RR realise n existe pas -- le peindre en
        # rouge dirait "il ne bat pas son equilibre" : c est faux.
        crr = GRIS if s["rr"] is None else (
            VERT if s["rr"] > s["rr_eq"] else ROUGE)
        add("<tr><td style='color:%s;font-weight:700'>%d</td><td>%s</td>"
            "<td style='color:%s'>%s</td>"
            "<td class='num' style='font-weight:700'>%d</td>"
            "<td class='num'>%.0f%%</td>"
            "<td class='num' style='color:%s'>%.0f%%</td>%s%s"
            "<td class='num' style='color:%s;font-weight:700'>%s</td>"
            "<td class='num' style='color:%s'>%.2f</td>"
            "<td class='num'>%s</td>"
            "<td class='num' style='color:%s'>%+.1f</td>"
            "<td class='num' style='color:%s'>%+.1f</td>%s"
            "<td class='num' style='color:%s'>%.0f</td>%s"
            "<td style='color:%s'>%s</td></tr>"
            % (JAUNE, magic, esc(nom), BLEU, esc(actif or "tous"),
               s["n"], s["wr"], MAUVE, s["wilson"],
               eur(s["tot"]), eur(s["moy"], 2), crr, rr,
               GRIS, s["rr_eq"], sh, VERT, s["mfe"], ROUGE, s["mae"],
               eur(s["creux"]), TEXTE, s["balance"] or 0.0,
               courbe(par.get(magic) or []),
               GRIS, esc((s["fin"] or "")[5:16])))
    add("</table>")
    add("<div class='leg'><b style='color:%s'>RR vert</b> = le rapport "
        "gain/perte realise depasse le RR d equilibre : le paper gagne "
        "pour une raison structurelle, pas par une serie. "
        "<b style='color:%s'>RR rouge</b> = il ne le depasse pas, et le "
        "PnL positif eventuel ne tient qu au hasard de la periode.</div>"
        % (VERT, ROUGE))


def h_croise(add, titre, legende, res):
    if not res:
        return
    add("<h4>%s</h4>" % titre)
    if legende:
        add("<div class='leg'>%s</div>" % legende)
    add("<table><tr><th>%s</th><th class='num'>prises</th>"
        "<th class='num'>WR</th><th class='num'>PnL</th>"
        "<th>meilleur paper</th><th class='num'>son PnL</th>"
        "<th>pire paper</th><th class='num'>son PnL</th></tr>"
        % esc(titre[:24]))
    for k, n, wr, tot, best, bp, pire, pp in res:
        add("<tr><td style='font-weight:700'>%s</td>"
            "<td class='num'>%d</td><td class='num'>%.0f%%</td>%s"
            "<td style='color:%s'>%s</td>%s<td style='color:%s'>%s</td>%s"
            "</tr>" % (esc(k), n, wr, eur(tot), JAUNE, best, eur(bp),
                       JAUNE, pire, eur(pp)))
    add("</table>")


def h_detail(add, derniers, tick, combien):
    add("<h4>&#128269; DETAIL &mdash; les %d dernieres prises</h4>"
        % combien)
    add("<table><tr><th>quand</th><th>magic</th><th>paper</th>"
        "<th>actif</th><th>sens</th><th>setup</th>"
        "<th class='num'>lot</th><th class='num'>PnL</th>"
        "<th class='num'>PnL reel</th><th class='num'>balance</th></tr>")
    for p in derniers:
        t = tick.get(p.get("ticket")) or {}
        d = p.get("sens")
        add("<tr><td style='color:%s'>%s</td>"
            "<td style='color:%s;font-weight:700'>%s</td><td>%s</td>"
            "<td>%s</td><td style='color:%s;font-weight:700'>%s</td>"
            "<td style='color:%s'>%s</td><td class='num'>%.2f</td>%s"
            "<td class='num' style='color:%s'>%+.2f</td>"
            "<td class='num'>%.0f</td></tr>"
            % (GRIS, esc((p.get("ts") or "")[5:16]),
               JAUNE, esc(p.get("magic")), esc(p.get("nom")),
               esc(p.get("actif")), VERT if d == "BUY" else ROUGE, esc(d),
               BLEU, esc(t.get("rails_setup") or "?"),
               p.get("lot") or 0.0, eur(p.get("pnl") or 0.0, 2),
               GRIS, p.get("pnl_reel") or 0.0, p.get("balance") or 0.0))
    add("</table>")


# ======================================================================
# rendu TEXTE -- le meme, copiable
# ======================================================================
def t_positions(a, n_ouv, pos, n_papers):
    a("")
    a("QUI EST EN POSITION -- maintenant, et depuis quand")
    a("-" * 100)
    if not n_ouv:
        a("  Aucun ticket ouvert dans la fenetre : le journal ne contient")
        a("  que des trades clos, ou les ouverts tombent hors plage.")
        return
    a("  %d ticket(s) ouvert(s) dans la fenetre." % n_ouv)
    a("  %-7s %-28s %4s  %-19s %-22s %s"
      % ("MAGIC", "PAPER", "POS", "DEPUIS", "ACTIFS", "SENS"))
    for magic, nom, n, depuis, acts, sens in pos:
        a("  %-7d %-28s %4d  %-19s %-22s %s"
          % (magic, nom[:28], n, depuis, acts[:22], sens))
    a("  %d paper(s) sans aucune position ouverte." % (n_papers - len(pos)))


def t_rendu(a, lignes, periode):
    a("")
    a("LE RENDU -- un paper par ligne")
    a("-" * 118)
    if periode:
        a("  periode couverte : %s -> %s" % periode)
    a("  %-7s %-26s %-6s %5s %5s %6s %9s %8s %5s %5s %7s %7s %7s %8s %9s"
      % ("MAGIC", "PAPER", "ACTIF", "n", "WR", "WILSON", "PnL", "PnL/tr",
         "RR", "RReq", "SHARPE", "MFE", "MAE", "CREUX", "BALANCE"))
    for magic, nom, actif, s in lignes:
        if not s:
            a("  %-7d %-26s %-6s %5d   aucune prise"
              % (magic, nom[:26], actif or "tous", 0))
            continue
        a("  %-7d %-26s %-6s %5d %4.0f%% %5.0f%% %+9.0f %+8.2f %5s %5.2f "
          "%7s %+7.1f %+7.1f %+8.0f %9.0f"
          % (magic, nom[:26], actif or "tous", s["n"], s["wr"], s["wilson"],
             s["tot"], s["moy"],
             ("%.2f" % s["rr"]) if s["rr"] is not None else "-",
             s["rr_eq"],
             ("%.2f" % s["sharpe"]) if s["sharpe"] is not None else "-",
             s["mfe"], s["mae"], s["creux"], s["balance"] or 0.0))
    a("  RR > RReq = le paper gagne pour une raison structurelle.")
    a("  RR < RReq = son PnL positif eventuel ne tient qu au hasard.")


def t_croise(a, titre, res):
    if not res:
        return
    a("")
    a(titre)
    a("-" * 88)
    a("  %-22s %6s %5s %9s   %-8s %9s   %-8s %9s"
      % ("", "PRISES", "WR", "PnL", "MEILLEUR", "SON PnL", "PIRE", "SON PnL"))
    for k, n, wr, tot, best, bp, pire, pp in res:
        a("  %-22s %6d %4.0f%% %+9.0f   %-8s %+9.0f   %-8s %+9.0f"
          % (str(k)[:22], n, wr, tot, best, bp, pire, pp))


def t_detail(a, derniers, tick, combien):
    a("")
    a("DETAIL -- les %d dernieres prises" % combien)
    a("-" * 96)
    a("  %-12s %-7s %-24s %-6s %-5s %-12s %6s %9s %9s"
      % ("QUAND", "MAGIC", "PAPER", "ACTIF", "SENS", "SETUP", "LOT",
         "PnL", "BALANCE"))
    for p in derniers:
        t = tick.get(p.get("ticket")) or {}
        a("  %-12s %-7s %-24s %-6s %-5s %-12s %6.2f %+9.2f %9.0f"
          % ((p.get("ts") or "")[5:16], p.get("magic"),
             (p.get("nom") or "")[:24], p.get("actif") or "?",
             p.get("sens") or "?", (t.get("rails_setup") or "?")[:12],
             p.get("lot") or 0.0, p.get("pnl") or 0.0,
             p.get("balance") or 0.0))


# ======================================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=SOURCE)
    p.add_argument("--journal", default=JOURNAL)
    p.add_argument("--detail", type=int, default=60)
    p.add_argument("--detail-texte", type=int, default=25,
                   dest="detail_texte")
    a = p.parse_args()

    try:
        import papers_moteur as PM
    except ImportError:
        print("KO : papers_moteur.py doit etre dans le meme dossier.")
        print("Le filtre de chaque paper y est defini une seule fois ;")
        print("ce panneau l importe au lieu de le reecrire.")
        return 1
    if not hasattr(PM, "accepte") or not hasattr(PM, "dans_fenetre"):
        print("KO : papers_moteur.py n est pas la version du 19/08.")
        print("Il lui manque accepte() ou dans_fenetre().")
        print("Recopie papers_moteur_v3.py.")
        return 1

    pe, pr, manque = PM._charge_modules()
    if manque:
        print("KO : introuvable(s) -- %s" % ", ".join(manque))
        return 1
    jeu = PM.papers(pe, pr)
    fenetre = getattr(PM, "FENETRE", None)

    journal, ko_j = lire_jsonl(a.journal)
    tickets, ko_t = lire_jsonl(a.source)
    tick = dict((t.get("ticket"), t) for t in tickets
                if t.get("ticket") is not None)

    par = {}
    for x in journal:
        par.setdefault(x.get("magic"), []).append(x)
    for k in par:
        par[k].sort(key=lambda x: str(x.get("ts") or ""))

    # --- calcul, une seule fois
    n_ouv, pos = calc_positions(jeu, tickets, PM, fenetre)
    lignes = calc_rendu(jeu, par, PM) if journal else []
    periode = None
    if journal:
        ts = [x.get("ts") or "" for x in journal]
        periode = (min(ts), max(ts))
    vues = []
    if journal:
        vues = [
            ("PAR HEURE (Paris)",
             "L heure d entree du ticket. Sert aussi de controle : aucune "
             "ligne ne doit sortir de la fenetre observee.",
             resume_croise(calc_croise(
                 jeu, par, lambda x: (x.get("ts") or "")[11:13] + "h"))),
            ("PAR ACTIF", "",
             resume_croise(calc_croise(jeu, par,
                                       lambda x: x.get("actif")))),
            ("PAR SETUP RAILS",
             "Joint sur tickets_rails.jsonl par le numero de ticket : le "
             "journal des prises garde le ticket, pas le setup.",
             resume_croise(calc_croise(
                 jeu, par,
                 lambda x: (tick.get(x.get("ticket")) or {}).get(
                     "rails_setup")),
                 ordre=["TIGHT_CROSS", "MID", "WIDE"])),
            ("PAR UNITES DE TEMPS SERREES",
             "Signature _tf_sig de l actif trade a l entree, jointe depuis "
             "le ticket. 'M1+M3' = ces deux unites etaient serrees.",
             resume_croise(calc_croise(
                 jeu, par,
                 lambda x: (pe.sig(tick[x["ticket"]])
                            if x.get("ticket") in tick else None)))),
        ]
    ordonne = sorted(journal, key=lambda x: str(x.get("ts") or ""))
    deborde = []
    if fenetre:
        deborde = [x for x in journal
                   if not (fenetre[0] <= (x.get("ts") or "")[11:16]
                           < fenetre[1])]

    # --- texte
    T = []
    at = T.append
    at("=" * 118)
    at("PAPERS -- LE RENDU  (%d papers, %d prises, %d tickets source)"
       % (len(jeu), len(journal), len(tickets)))
    at("=" * 118)
    at("  Lecture seule : aucun ordre envoye, MetaTrader5 non importe.")
    at("  Fenetre observee : %s" % ("%s -> %s (fin exclue), heure Paris"
                                    % fenetre if fenetre
                                    else "AUCUNE -- toutes les heures"))
    if deborde:
        at("  ATTENTION : %d prise(s) du journal tombent HORS fenetre."
           % len(deborde))
        at("  Reconstruire : python papers_moteur.py --reset --oui")
    at("  Les papers FILTRENT les entrees du moteur churn, ils ne les")
    at("  choisissent pas -- ils mesurent un filtre, pas un timing.")
    if ko_j or ko_t:
        at("  %d ligne(s) illisible(s) au journal, %d a la source."
           % (ko_j, ko_t))
    t_positions(at, n_ouv, pos, len(jeu))
    if not journal:
        at("")
        at("  Le journal des prises est VIDE : lance papers_moteur.py")
        at("  d abord. Ce panneau n invente aucune ligne.")
    else:
        t_rendu(at, lignes, periode)
        for titre, _leg, res in vues:
            t_croise(at, titre, res)
        t_detail(at, ordonne[-a.detail_texte:][::-1], tick,
                 a.detail_texte)
    at("")
    at("=" * 118)
    txt = "\n".join(T)

    # --- html
    L = []
    add = L.append
    add("<h3>&#128200; PAPERS &mdash; le rendu des %d traders papier</h3>"
        % len(jeu))
    add("<div style='margin:10px 0 4px'>"
        "<button id='bcopie' onclick='papersCopie()'>&#128203; Copier "
        "tout le texte</button></div>")
    add("<textarea id='brut' readonly style='position:absolute;"
        "left:-9999px;top:0;width:400px;height:200px'>%s</textarea>"
        % esc(txt))
    add("<details><summary>voir le texte brut (repli si le bouton "
        "echoue : selectionner, Ctrl+C)</summary><pre>%s</pre></details>"
        % esc(txt))
    if fenetre:
        add("<div class='leg'>Fenetre observee : <b style='color:%s'>%s "
            "&rarr; %s</b> (fin exclue), heure de Paris. 14:00 est la "
            "definition du panneau lui-meme (<b>_sess</b> : US si heure "
            "&ge; 14) ; 19:00 vient de la consigne. Aucun ticket hors de "
            "cette plage n est pris.</div>"
            % (JAUNE, esc(fenetre[0]), esc(fenetre[1])))
        if deborde:
            add("<div class='leg' style='color:%s'><b>%d prise(s) du "
                "journal tombent HORS fenetre</b> : elles datent d avant "
                "la pose de la fenetre. Le rendu ci-dessous les compte "
                "encore. Reconstruire : <b>python papers_moteur.py "
                "--reset --oui</b></div>" % (ROUGE, len(deborde)))
    else:
        add("<div class='leg' style='color:%s'>Aucune fenetre horaire : "
            "toutes les heures sont prises.</div>" % ROUGE)
    add("<div class='leg'>%d prise(s) au journal, %d ticket(s) source. "
        "Lecture seule : aucun ordre n a ete envoye, MetaTrader5 n est "
        "pas importe. Les papers FILTRENT les entrees du moteur churn, "
        "ils ne les choisissent pas &mdash; un paper qui bat les autres "
        "a mieux filtre, il n a pas mieux time.</div>"
        % (len(journal), len(tickets)))
    if ko_j or ko_t:
        add("<div class='leg' style='color:%s'>%d ligne(s) illisible(s) "
            "au journal, %d a la source.</div>" % (JAUNE, ko_j, ko_t))

    h_positions(add, n_ouv, pos, len(jeu))
    if not journal:
        add("<div class='leg' style='color:%s'>Le journal des prises est "
            "vide : lance <b>papers_moteur.py</b> d abord. Ce panneau "
            "n invente aucune ligne.</div>" % JAUNE)
    else:
        h_rendu(add, lignes, par, periode)
        for titre, leg, res in vues:
            h_croise(add, titre, leg, res)
        h_detail(add, ordonne[-a.detail:][::-1], tick, a.detail)
    add("<div class='leg' style='margin-top:18px'>Ecrit par "
        "papers_rendu.py. Aucun ordre envoye, aucun processus touche.</div>")

    html = ("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Papers -- rendu</title><style>%s</style>"
            "<script>%s</script></head><body>%s</body></html>\n"
            % (CSS, JS, "\n".join(L)))
    for dossier in ("cartes", "panels"):
        if not os.path.isdir(dossier):
            os.makedirs(dossier)
    io.open(SORTIE_H, "w", encoding="utf-8", newline="").write(html)
    io.open(SORTIE_T, "w", encoding="utf-8", newline="").write(txt + u"\n")
    print("  papers   : %d" % len(jeu))
    print("  prises   : %d" % len(journal))
    print("  tickets  : %d" % len(tickets))
    print("  ouverts  : %d  (dans la fenetre)" % n_ouv)
    if deborde:
        print("  HORS FENETRE au journal : %d -- relance avec"
              " --reset --oui" % len(deborde))
    print("  ecrit    : %s   (bouton Copier dans la page)" % SORTIE_H)
    print("  ecrit    : %s   (type %s)" % (SORTIE_T, SORTIE_T))
    return 0


if __name__ == "__main__":
    sys.exit(main())
