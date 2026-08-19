# -*- coding: utf-8 -*-
r"""
papers_rendu.py -- le rendu des papers, en couleur, comme rails_trades

  python papers_rendu.py
  python papers_rendu.py --detail 80

LECTEUR SEUL. N ENVOIE AUCUN ORDRE, N IMPORTE PAS MetaTrader5.
Il ecrit UNIQUEMENT cartes\papers_rendu.html et panels\.

CE QU IL MONTRE, DANS CET ORDRE

 1. QUI EST EN POSITION, DEPUIS QUAND, COMBIEN.
    Le journal des tickets contient aussi les trades ENCORE OUVERTS :
    ils portent un volume mais pas de pnl_eur. Le moteur les saute --
    il ne peut pas dimensionner un resultat qui n existe pas encore.
    Ce panneau, lui, pose la MEME question a chaque paper sur ces
    tickets-la : l aurais-tu pris ? Ce qui donne, sans rien envoyer,
    qui serait en position maintenant et depuis quand.

    La question est posee par papers_moteur.accepte() -- la fonction
    du moteur, importee, pas reecrite. Deux ecritures du meme filtre
    auraient diverge.

 2. LE RENDU, un paper par ligne : prises, WR, PnL, PnL/trade, RR
    realise, RR d equilibre, borne basse de Wilson, Sharpe par trade,
    MFE/MAE, pire creux, balance, courbe.

 3. PAR HEURE (Paris), PAR ACTIF, PAR SETUP, PAR UNITE DE TEMPS.
    Le journal des prises ne garde pas le setup ni l etat des TF : il
    garde le TICKET. Ces quatre vues viennent donc d une JOINTURE sur
    tickets_rails.jsonl -- rien n est recopie, tout est joint.

 4. LE DETAIL des dernieres prises.

CE QUE LE SHARPE VEUT DIRE ICI

    Moyenne / ecart-type des PnL PAR TRADE. Ce n est pas un Sharpe
    annualise : il n y a ni taux sans risque ni periode de reference.
    Il sert a comparer les 17 entre eux, pas a etre publie.

CE QUE CE PANNEAU NE PEUT PAS DIRE

    Les papers filtrent les entrees du moteur churn, ils ne les
    choisissent pas. Leur PnL est celui du trade reel, remis a
    l echelle de la balance fictive. Un paper qui bat les autres a
    mieux FILTRE -- il n a pas mieux TIME.
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
.sep td{border-top:1px solid #21262d}
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
# statistiques
# ======================================================================
def stats(prises, PM):
    """Tout ce qui se calcule sur une liste de prises."""
    n = len(prises)
    if not n:
        return None
    pnls = [p.get("pnl") or 0.0 for p in prises]
    gains = [x for x in pnls if x > 0]
    pertes = [-x for x in pnls if x < 0]
    tot = sum(pnls)
    moy = tot / n
    p = len(gains) / float(n)
    var = sum((x - moy) ** 2 for x in pnls) / n
    ec = math.sqrt(var)
    # pire creux sur la courbe cumulee
    cum, haut, creux = 0.0, 0.0, 0.0
    for x in pnls:
        cum += x
        haut = max(haut, cum)
        creux = min(creux, cum - haut)
    return {
        "n": n, "wr": 100.0 * p, "tot": tot, "moy": moy,
        "gain_moy": (sum(gains) / len(gains)) if gains else 0.0,
        "perte_moy": (sum(pertes) / len(pertes)) if pertes else 0.0,
        "rr": ((sum(gains) / len(gains)) / (sum(pertes) / len(pertes)))
              if gains and pertes else None,
        "rr_eq": PM.rr_equilibre(p),
        "wilson": 100.0 * PM.wilson_bas(p, n),
        "sharpe": (moy / ec) if ec > 0 else None,
        "mfe": sum(p2.get("mfe") or 0.0 for p2 in prises) / n,
        "mae": sum(p2.get("mae") or 0.0 for p2 in prises) / n,
        "creux": creux,
        "balance": prises[-1].get("balance"),
        "debut": min(p2.get("ts") or "" for p2 in prises),
        "fin": max(p2.get("ts") or "" for p2 in prises),
    }


def courbe(prises, w=118, h=26):
    """Petite courbe de PnL cumule, en SVG inline."""
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
    c = col(pts[-1])
    return ("<td><svg width='%d' height='%d'>"
            "<line x1='0' y1='%.1f' x2='%d' y2='%.1f' stroke='#30363d' "
            "stroke-width='1'/>"
            "<polyline points='%s' fill='none' stroke='%s' "
            "stroke-width='1.4'/></svg></td>" % (w, h, zero, w, zero, xy, c))


# ======================================================================
# sections
# ======================================================================
def sec_positions(add, jeu, tickets, PM):
    ouverts = [t for t in tickets
               if isinstance(t.get("volume"), (int, float))
               and t.get("volume") > 0 and t.get("pnl_eur") is None
               and isinstance(t.get("entry_ts"), str)]
    add("<h4>&#128308; QUI EST EN POSITION &mdash; maintenant, et depuis "
        "quand</h4>")
    add("<div class='leg'>Tickets du moteur churn encore OUVERTS "
        "(volume present, pnl absent), passes au filtre de chaque paper "
        "par <b>papers_moteur.accepte()</b> &mdash; la fonction du "
        "moteur, importee, pas reecrite. Aucun ordre n est envoye : "
        "c est ce que le paper AURAIT en position.</div>")
    if not ouverts:
        add("<div class='leg' style='color:%s'>Aucun ticket ouvert dans "
            "le journal : il ne contient que des trades clos. La colonne "
            "&laquo; en position &raquo; restera vide tant que "
            "rails_join.py n y ecrira pas les positions en cours.</div>"
            % JAUNE)
        return
    add("<div class='leg'>%d ticket(s) ouvert(s) dans le journal.</div>"
        % len(ouverts))
    add("<table><tr><th>magic</th><th>paper</th><th class='num'>pos.</th>"
        "<th>depuis</th><th>actifs</th><th>sens</th></tr>")
    vide = 0
    for magic, nom, actif, sens, pred in jeu:
        pris = [t for t in ouverts
                if PM.accepte((magic, nom, actif, sens, pred), t)]
        if not pris:
            vide += 1
            continue
        vieux = min(t["entry_ts"] for t in pris)
        acts = sorted(set(t.get("asset") or "?" for t in pris))
        sens_v = sorted(set(t.get("dir") or "?" for t in pris))
        add("<tr><td style='color:%s;font-weight:700'>%d</td><td>%s</td>"
            "<td class='num' style='color:%s;font-weight:700'>%d</td>"
            "<td style='color:%s'>%s</td><td>%s</td>"
            "<td style='color:%s;font-weight:700'>%s</td></tr>"
            % (JAUNE, magic, esc(nom), BLEU, len(pris), GRIS, esc(vieux),
               esc(", ".join(acts)),
               VERT if sens_v == ["BUY"] else ROUGE, esc("/".join(sens_v))))
    add("</table>")
    add("<div class='leg'>%d paper(s) sans aucune position ouverte.</div>"
        % vide)


def sec_rendu(add, jeu, par, PM):
    add("<h4>&#127942; LE RENDU &mdash; un paper par ligne</h4>")
    add("<div class='leg'>Balance fictive de depart 20 000, lot = "
        "balance / 20 000 (plancher 0,01). <b>RR eq.</b> = "
        "(1&minus;p)/p : le rapport gain/perte qu il FAUT atteindre pour "
        "etre a l equilibre a ce taux de reussite &mdash; c est le seul "
        "chiffre qu on ne peut pas surajuster. <b>Wilson</b> = borne "
        "basse a 95&nbsp;% du taux de reussite : ce qu on peut affirmer, "
        "pas ce qu on a vu. <b>Sharpe</b> = moyenne / ecart-type PAR "
        "TRADE, non annualise, bon pour comparer les 17 entre eux.</div>")
    tous = [x for pr in par.values() for x in pr]
    if tous:
        add("<div class='leg'>Periode couverte par le journal : "
            "<b>%s</b> &rarr; <b>%s</b>. La colonne <b>prises</b> est "
            "le nombre de trades pris sur cette periode.</div>"
            % (esc(min(x.get("ts") or "" for x in tous)),
               esc(max(x.get("ts") or "" for x in tous))))
    add("<table><tr><th>magic</th><th>paper</th><th>actif</th>"
        "<th class='num'>prises</th><th class='num'>WR</th>"
        "<th class='num'>Wilson</th><th class='num'>PnL</th>"
        "<th class='num'>PnL/tr</th><th class='num'>RR</th>"
        "<th class='num'>RR eq.</th><th class='num'>Sharpe</th>"
        "<th class='num'>MFE</th><th class='num'>MAE</th>"
        "<th class='num'>creux</th><th class='num'>balance</th>"
        "<th>courbe</th><th>derniere</th></tr>")
    lignes = []
    for magic, nom, actif, sens, pred in jeu:
        pr = par.get(magic) or []
        s = stats(pr, PM)
        lignes.append((magic, nom, actif, s))
    lignes.sort(key=lambda x: -(x[3]["tot"] if x[3] else -1e18))
    for magic, nom, actif, s in lignes:
        if not s:
            add("<tr><td style='color:%s;font-weight:700'>%d</td><td>%s</td>"
                "<td>%s</td><td class='num' style='color:%s'>0</td>"
                "<td colspan='13' style='color:%s'>aucune prise</td></tr>"
                % (GRIS, magic, esc(nom), esc(actif or "tous"), GRIS, GRIS))
            continue
        rr = "%.2f" % s["rr"] if s["rr"] is not None else "&ndash;"
        sh = "%.2f" % s["sharpe"] if s["sharpe"] is not None else "&ndash;"
        # Sans aucune perte, le RR realise n existe pas -- le peindre
        # en rouge dirait "il ne bat pas son equilibre" : c est faux.
        crr = GRIS if s["rr"] is None else (
            VERT if s["rr"] > s["rr_eq"] else ROUGE)
        add("<tr><td style='color:%s;font-weight:700'>%d</td><td>%s</td>"
            "<td style='color:%s'>%s</td>"
            "<td class='num' style='font-weight:700'>%d</td>"
            "<td class='num'>%.0f%%</td>"
            "<td class='num' style='color:%s'>%.0f%%</td>"
            "%s%s"
            "<td class='num' style='color:%s;font-weight:700'>%s</td>"
            "<td class='num' style='color:%s'>%.2f</td>"
            "<td class='num'>%s</td>"
            "<td class='num' style='color:%s'>%+.1f</td>"
            "<td class='num' style='color:%s'>%+.1f</td>"
            "%s"
            "<td class='num' style='color:%s'>%.0f</td>"
            "%s"
            "<td style='color:%s'>%s</td></tr>"
            % (JAUNE, magic, esc(nom), BLEU, esc(actif or "tous"),
               s["n"], s["wr"], MAUVE, s["wilson"],
               eur(s["tot"]), eur(s["moy"], 2),
               crr, rr,
               GRIS, s["rr_eq"], sh,
               VERT, s["mfe"], ROUGE, s["mae"],
               eur(s["creux"]),
               TEXTE, s["balance"] or 0.0,
               courbe(par.get(magic) or []),
               GRIS, esc((s["fin"] or "")[5:16])))
    add("</table>")
    add("<div class='leg'><b style='color:%s'>RR vert</b> = le rapport "
        "gain/perte realise depasse le RR d equilibre : le paper gagne "
        "pour une raison structurelle, pas par une serie. "
        "<b style='color:%s'>RR rouge</b> = il ne le depasse pas, et le "
        "PnL positif eventuel ne tient qu au hasard de la periode.</div>"
        % (VERT, ROUGE))


def croise(add, titre, legende, jeu, par, cle, ordre=None):
    """Une vue paper x dimension. cle(prise) rend le libelle ou None."""
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
    if not dims:
        return
    add("<h4>%s</h4>" % titre)
    if legende:
        add("<div class='leg'>%s</div>" % legende)
    ks = ordre or sorted(dims)
    add("<table><tr><th>%s</th><th class='num'>prises</th>"
        "<th class='num'>WR</th><th class='num'>PnL</th>"
        "<th>meilleur paper</th><th class='num'>son PnL</th>"
        "<th>pire paper</th><th class='num'>son PnL</th></tr>" % titre[:24])
    for k in ks:
        if k not in dims:
            continue
        d = dims[k]
        n = sum(v[0] for v in d.values())
        w = sum(v[1] for v in d.values())
        tot = sum(v[2] for v in d.values())
        best = max(d.items(), key=lambda x: x[1][2])
        pire = min(d.items(), key=lambda x: x[1][2])
        add("<tr><td style='font-weight:700'>%s</td>"
            "<td class='num'>%d</td><td class='num'>%.0f%%</td>%s"
            "<td style='color:%s'>%s</td>%s"
            "<td style='color:%s'>%s</td>%s</tr>"
            % (esc(k), n, 100.0 * w / n if n else 0, eur(tot),
               JAUNE, best[0], eur(best[1][2]),
               JAUNE, pire[0], eur(pire[1][2])))
    add("</table>")


def sec_detail(add, journal, tick, combien):
    add("<h4>&#128269; DETAIL &mdash; les %d dernieres prises</h4>"
        % combien)
    add("<table><tr><th>quand</th><th>magic</th><th>paper</th>"
        "<th>actif</th><th>sens</th><th>setup</th>"
        "<th class='num'>lot</th><th class='num'>PnL</th>"
        "<th class='num'>PnL reel</th><th class='num'>balance</th></tr>")
    for p in sorted(journal, key=lambda x: str(x.get("ts") or ""))[-combien:][::-1]:
        t = tick.get(p.get("ticket")) or {}
        d = p.get("sens")
        add("<tr><td style='color:%s'>%s</td>"
            "<td style='color:%s;font-weight:700'>%s</td><td>%s</td>"
            "<td>%s</td><td style='color:%s;font-weight:700'>%s</td>"
            "<td style='color:%s'>%s</td>"
            "<td class='num'>%.2f</td>%s"
            "<td class='num' style='color:%s'>%+.2f</td>"
            "<td class='num'>%.0f</td></tr>"
            % (GRIS, esc((p.get("ts") or "")[5:16]),
               JAUNE, esc(p.get("magic")), esc(p.get("nom")),
               esc(p.get("actif")),
               VERT if d == "BUY" else ROUGE, esc(d),
               BLEU, esc(t.get("rails_setup") or "?"),
               p.get("lot") or 0.0, eur(p.get("pnl") or 0.0, 2),
               GRIS, p.get("pnl_reel") or 0.0,
               p.get("balance") or 0.0))
    add("</table>")


# ======================================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=SOURCE)
    p.add_argument("--journal", default=JOURNAL)
    p.add_argument("--detail", type=int, default=60)
    a = p.parse_args()

    try:
        import papers_moteur as PM
    except ImportError:
        print("KO : papers_moteur.py doit etre dans le meme dossier.")
        print("Le filtre de chaque paper y est defini une seule fois ;")
        print("ce panneau l importe au lieu de le reecrire.")
        return 1

    pe, pr, manque = PM._charge_modules()
    if manque:
        print("KO : introuvable(s) -- %s" % ", ".join(manque))
        return 1
    jeu = PM.papers(pe, pr)

    journal, ko_j = lire_jsonl(a.journal)
    tickets, ko_t = lire_jsonl(a.source)
    tick = dict((t.get("ticket"), t) for t in tickets
                if t.get("ticket") is not None)

    par = {}
    for x in journal:
        par.setdefault(x.get("magic"), []).append(x)
    for k in par:
        par[k].sort(key=lambda x: str(x.get("ts") or ""))

    L = []
    add = L.append
    add("<h3>&#128200; PAPERS &mdash; le rendu des %d traders papier</h3>"
        % len(jeu))
    add("<div class='leg'>%d prise(s) au journal, %d ticket(s) source. "
        "Lecture seule : aucun ordre n a ete envoye, MetaTrader5 n est "
        "pas importe. Les papers FILTRENT les entrees du moteur churn, "
        "ils ne les choisissent pas &mdash; un paper qui bat les autres "
        "a mieux filtre, il n a pas mieux time.</div>"
        % (len(journal), len(tickets)))
    if ko_j or ko_t:
        add("<div class='leg' style='color:%s'>%d ligne(s) illisible(s) "
            "au journal, %d a la source.</div>" % (JAUNE, ko_j, ko_t))

    sec_positions(add, jeu, tickets, PM)

    if not journal:
        add("<div class='leg' style='color:%s'>Le journal des prises est "
            "vide : lance <b>papers_moteur.py</b> d abord. Ce panneau "
            "n invente aucune ligne.</div>" % JAUNE)
    else:
        sec_rendu(add, jeu, par, PM)
        croise(add, "PAR HEURE (Paris)",
               "L heure d entree du ticket. Les creneaux qui paient et "
               "ceux qui saignent, tous papers confondus, avec le "
               "meilleur et le pire sur chaque creneau.",
               jeu, par, lambda x: (x.get("ts") or "")[11:13] + "h")
        croise(add, "PAR ACTIF", "", jeu, par,
               lambda x: x.get("actif"))
        croise(add, "PAR SETUP RAILS",
               "Joint sur tickets_rails.jsonl par le numero de ticket : "
               "le journal des prises garde le ticket, pas le setup.",
               jeu, par,
               lambda x: (tick.get(x.get("ticket")) or {}).get("rails_setup"),
               ordre=["TIGHT_CROSS", "MID", "WIDE"])
        croise(add, "PAR UNITES DE TEMPS SERREES",
               "Signature _tf_sig de l actif trade a l entree, jointe "
               "depuis le ticket. 'M1+M3' = ces deux unites etaient "
               "serrees au moment de la prise.",
               jeu, par,
               lambda x: (pe.sig(tick[x["ticket"]])
                          if x.get("ticket") in tick else None))
        sec_detail(add, journal, tick, a.detail)

    add("<div class='leg' style='margin-top:18px'>Ecrit par "
        "papers_rendu.py. Aucun ordre envoye, aucun processus touche.</div>")

    corps = "\n".join(L)
    html = ("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Papers -- rendu</title><style>%s</style></head>"
            "<body>%s</body></html>\n" % (CSS, corps))
    for dossier in ("cartes", "panels"):
        if not os.path.isdir(dossier):
            os.makedirs(dossier)
    io.open(SORTIE_H, "w", encoding="utf-8", newline="").write(html)
    io.open(SORTIE_T, "w", encoding="utf-8", newline="").write(
        u"papers_rendu : %d prises, %d papers, %d tickets\n"
        % (len(journal), len(jeu), len(tickets)))
    print("  papers   : %d" % len(jeu))
    print("  prises   : %d" % len(journal))
    print("  tickets  : %d" % len(tickets))
    print("  ecrit    : %s" % SORTIE_H)
    print("  ecrit    : %s" % SORTIE_T)
    return 0


if __name__ == "__main__":
    sys.exit(main())
