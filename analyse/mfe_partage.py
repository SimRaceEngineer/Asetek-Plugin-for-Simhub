#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""mfe_partage.py -- le MFE separe des gagnants et des perdants.

CE QU IL CORRIGE
----------------
Le rendu affiche une colonne MFE et une colonne MAE. Ce sont des
MOYENNES SUR TOUTES LES PRISES -- papers_rendu.py, lignes 184-185 :

    "mfe": sum(q.get("mfe") or 0.0 for q in prises) / n,
    "mae": sum(q.get("mae") or 0.0 for q in prises) / n,

Melanger gagnants et perdants dans une seule moyenne rend la colonne
illisible, et elle a deja produit une erreur d interpretation : le
27/08, quatre lectures automatiques ont compare ce MFE moyen au PnL
NET par trade et en ont conclu que le systeme rendait 90 % du
mouvement favorable. C est faux. Le PnL net est la petite difference
entre un gain moyen et une perte moyenne du meme ordre : sur 240007,
+46 de gain moyen contre -45 de perte moyenne, pour +5,91 net. Le
gain moyen se compare au MFE, pas l esperance nette.

Ce panneau ne raconte rien. Il separe.

LES TROIS QUESTIONS
-------------------
    1. Sur un GAGNANT, combien rend-on du plus haut atteint ?
       gain moyen contre MFE moyen des seuls gagnants.

    2. Un PERDANT etait-il DEJA EN GAIN avant de mourir, et de
       combien ? C est la seule question a laquelle le break-even et
       le cliquet repondent. Si les perdants ne passent jamais en
       gain, un BE ne sert a rien ; s ils y passent souvent et loin,
       c est le plus gros gisement du systeme.

    3. Sort-on au pire point ? perte moyenne contre MAE moyen des
       seuls perdants. Un rapport proche de 1 dit qu on sort au creux.

CE QU IL NE PEUT PAS DIRE
-------------------------
Le gisement du break-even calcule ici est une BORNE HAUTE, pas un
gain. Il compte ce que les perdants passes par +X auraient cesse de
perdre ; il ne compte PAS ce que le meme BE aurait coute sur les
gagnants qui repassent par +X avant de repartir. Ce cout-la ne se
mesure que barre par barre. La borne sert a savoir si ca vaut la
peine de faire le rejeu, pas a decider a sa place.

La colonne MAE du cote GAGNANTS est la seule borne dont on dispose
sur ce cout : un BE pose sous ce niveau ne peut pas tuer le gagnant
moyen.

Les seuils sont exprimes en R -- R etant la PERTE MOYENNE du magic
lui-meme, pas un stop theorique. Les lots varient d un paper a l
autre (lot = balance / 20 000), donc un seuil en euros ne serait pas
comparable d une ligne a l autre.

LES DEUX CONTROLES D UNITE
--------------------------
Le champ mfe est suppose etre dans la meme unite que pnl. On le
VERIFIE au lieu de le supposer : sur un gagnant, mfe doit etre >=
pnl, toujours. Si la regle est violee souvent, les deux champs ne
sont pas dans la meme unite et le panneau le dit en grand au lieu
de rendre des colonnes fausses.

Le signe de mae n est pas suppose non plus : il est deduit de la
population. On travaille ensuite sur des valeurs absolues.

OU IL ECRIT
-----------
    panels\panel_mfe_partage.txt
    cartes\mfe_partage.html          visible dans la liste /cartes

LECTURE SEULE. N importe pas MetaTrader5, n envoie aucun ordre, ne
touche a aucun processus.

USAGE
-----
    python mfe_partage.py
    python mfe_partage.py --min-n 20
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

JOURNAL = os.path.join("docs", "papers_live", "trades.jsonl")
SORTIE_T = os.path.join("panels", "panel_mfe_partage.txt")
SORTIE_H = os.path.join("cartes", "mfe_partage.html")

LARGE = 118
SEUILS = (0.25, 0.50, 0.75, 1.00)


# ----------------------------------------------------------------------
# lecture
# ----------------------------------------------------------------------
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


def noms_des_papers():
    """Les noms viennent du moteur, ils ne sont pas recopies ici.

    Leur absence n empeche rien : ce panneau calcule sur des nombres,
    pas sur des libelles. On le dit, et on continue avec les magics.
    """
    try:
        import papers_moteur as PM
        pe, pr, manque = PM._charge_modules()
        if manque:
            return {}, "modules absents : %s" % ", ".join(manque)
        return dict((j[0], j[1]) for j in PM.papers(pe, pr)), ""
    except Exception as e:
        return {}, str(e)[:120]


# ----------------------------------------------------------------------
# calcul
# ----------------------------------------------------------------------
def moy(v):
    return (sum(v) / float(len(v))) if v else 0.0


def partage(prises):
    """Rend le dictionnaire d une population, ou None si elle est vide."""
    g = [p for p in prises if (p.get("pnl") or 0.0) > 0]
    d = [p for p in prises if (p.get("pnl") or 0.0) < 0]
    if not g and not d:
        return None

    gain = moy([p["pnl"] for p in g])
    perte = moy([-p["pnl"] for p in d])
    mfe_g = moy([abs(p.get("mfe") or 0.0) for p in g])
    mfe_d = moy([abs(p.get("mfe") or 0.0) for p in d])
    mae_g = moy([abs(p.get("mae") or 0.0) for p in g])
    mae_d = moy([abs(p.get("mae") or 0.0) for p in d])

    # R = la perte moyenne de CE magic. Les lots varient d un paper a
    # l autre : un seuil en euros ne serait pas comparable.
    R = perte or 1.0
    gisement = []
    for k in SEUILS:
        vise = [p for p in d if abs(p.get("mfe") or 0.0) >= k * R]
        gisement.append((k, len(vise), sum(-p["pnl"] for p in vise)))

    return {
        "n": len(g) + len(d), "ng": len(g), "nd": len(d),
        "gain": gain, "perte": perte,
        "mfe_g": mfe_g, "mfe_d": mfe_d,
        "mae_g": mae_g, "mae_d": mae_d,
        "rendu": mfe_g - gain,
        "part": (100.0 * gain / mfe_g) if mfe_g > 0 else 0.0,
        "au_creux": (100.0 * perte / mae_d) if mae_d > 0 else 0.0,
        "mfe_d_en_R": (mfe_d / R) if R else 0.0,
        "gisement": gisement,
        "pnl": sum(p.get("pnl") or 0.0 for p in g + d)}


def controle_unite(journal):
    """mfe et pnl sont-ils dans la meme unite ? On teste, on ne suppose pas."""
    g = [p for p in journal if (p.get("pnl") or 0.0) > 0
         and p.get("mfe") is not None]
    if not g:
        return None, 0, 0
    viol = [p for p in g if abs(p["mfe"]) + 1e-9 < p["pnl"]]
    return (100.0 * len(viol) / len(g)), len(viol), len(g)


def signe_mae(journal):
    neg = sum(1 for p in journal
              if isinstance(p.get("mae"), (int, float)) and p["mae"] < 0)
    pos = sum(1 for p in journal
              if isinstance(p.get("mae"), (int, float)) and p["mae"] > 0)
    return neg, pos


def famille(magic):
    m = int(magic or 0)
    if 220000 <= m < 230000:
        return "220xxx"
    if 230000 <= m < 240000:
        return "DS 23xxxx"
    if 240000 <= m < 250000:
        return "MR 24xxxx"
    return "autres"


# ----------------------------------------------------------------------
# rendu texte
# ----------------------------------------------------------------------
def barre(c="="):
    return c * LARGE


def rendu(journal, noms, souci_noms, min_n, chemin):
    L = []
    a = L.append

    par = {}
    for x in journal:
        par.setdefault(x.get("magic"), []).append(x)

    a(barre())
    a("MFE / MAE -- SEPARES GAGNANTS ET PERDANTS")
    a(barre())
    # Le chemin AFFICHE doit etre celui qu on a lu, pas la constante :
    # un panneau qui nomme une autre source que la sienne ment sans
    # en avoir l air.
    a("  source : %s   (%d prise(s))" % (chemin, len(journal)))

    taux, nv, ng = controle_unite(journal)
    if taux is None:
        a("  CONTROLE D UNITE : impossible, aucun gagnant avec un mfe.")
    elif taux > 5.0:
        a("")
        a("  !! CONTROLE D UNITE ECHOUE : sur %d gagnants, %d ont un MFE"
          % (ng, nv))
        a("     INFERIEUR a leur propre gain (%.1f %%). C est impossible si" % taux)
        a("     mfe et pnl sont dans la meme unite. Les colonnes MFE")
        a("     ci-dessous ne sont donc PAS comparables aux colonnes de")
        a("     gain, et il ne faut rien en conclure avant d avoir")
        a("     verifie comment le journal remplit ce champ.")
        a("")
    else:
        a("  controle d unite : %d/%d gagnants avec mfe < gain (%.1f %%)"
          % (nv, ng, taux))
        a("                     -> mfe et pnl sont bien dans la meme unite.")

    neg, pos = signe_mae(journal)
    a("  signe du mae     : %d negatif(s), %d positif(s) -- on travaille"
      % (neg, pos))
    a("                     en valeur absolue, la convention n est pas supposee.")
    if souci_noms:
        a("  noms des papers  : indisponibles (%s), magics seuls." % souci_noms)
    a("")
    a("  R = la PERTE MOYENNE du magic lui-meme, pas un stop theorique.")
    a("  Les lots varient d un paper a l autre : un seuil en euros ne")
    a("  serait pas comparable d une ligne a l autre.")
    a("")

    # ---------------- table principale
    a(barre("-"))
    a("%-7s %-22s | %5s %7s %7s %7s %7s %6s | %5s %7s %7s %7s %6s"
      % ("MAGIC", "PAPER", "n", "gain", "MFE", "MAE", "rendu", "part",
         "n", "perte", "MFE+", "MAE", "creux"))
    a("%-7s %-22s | %s | %s"
      % ("", "", "        G A G N A N T S                     ",
         "        P E R D A N T S            "))
    a(barre("-"))

    lignes = []
    for magic, prises in par.items():
        s = partage(prises)
        if s and s["n"] >= min_n:
            lignes.append((magic, s))
    lignes.sort(key=lambda t: -t[1]["n"])

    for magic, s in lignes:
        a("%-7s %-22s | %5d %+7.1f %7.1f %7.1f %7.1f %5.0f%% | "
          "%5d %7.1f %7.1f %7.1f %5.0f%%"
          % (magic, (noms.get(magic) or "")[:22],
             s["ng"], s["gain"], s["mfe_g"], s["mae_g"], s["rendu"],
             s["part"], s["nd"], s["perte"], s["mfe_d"], s["mae_d"],
             s["au_creux"]))

    # ---------------- familles et total
    a(barre("-"))
    for fam in ("220xxx", "DS 23xxxx", "MR 24xxxx", "autres"):
        gr = [x for x in journal if famille(x.get("magic")) == fam]
        s = partage(gr)
        if s and s["n"] >= min_n:
            a("%-7s %-22s | %5d %+7.1f %7.1f %7.1f %7.1f %5.0f%% | "
              "%5d %7.1f %7.1f %7.1f %5.0f%%"
              % ("", fam, s["ng"], s["gain"], s["mfe_g"], s["mae_g"],
                 s["rendu"], s["part"], s["nd"], s["perte"], s["mfe_d"],
                 s["mae_d"], s["au_creux"]))
    tous = partage(journal)
    if tous:
        a("%-7s %-22s | %5d %+7.1f %7.1f %7.1f %7.1f %5.0f%% | "
          "%5d %7.1f %7.1f %7.1f %5.0f%%"
          % ("", "TOUS", tous["ng"], tous["gain"], tous["mfe_g"],
             tous["mae_g"], tous["rendu"], tous["part"], tous["nd"],
             tous["perte"], tous["mfe_d"], tous["mae_d"],
             tous["au_creux"]))
    a(barre("-"))
    a("  gain / perte  moyennes des gagnants / des perdants")
    a("  MFE   plus haut atteint, moyenne SUR CETTE POPULATION SEULE")
    a("  MAE   (cote gagnants) le plus bas atteint par un trade qui a")
    a("        pourtant fini en gain. C est la seule borne dont on")
    a("        dispose sur le COUT d un break-even : un BE pose sous")
    a("        ce niveau ne peut pas tuer le gagnant moyen.")
    a("  rendu MFE des gagnants moins leur gain : ce qu on laisse au")
    a("        retour, sur les seuls trades qui ont fini en gain")
    a("  part  gain / MFE des gagnants : la fraction capturee")
    a("  MFE+  jusqu ou les PERDANTS sont montes en gain avant de mourir")
    a("  creux perte / MAE des perdants. Proche de 100 %, on sort au")
    a("        plus mauvais point du trade.")
    a("")

    # ---------------- gisement du break-even
    a(barre())
    a("LE GISEMENT DU BREAK-EVEN -- borne haute, pas un gain")
    a(barre())
    a("  Combien de PERDANTS etaient deja montes a +X avant de mourir,")
    a("  et combien ont-ils perdu ? Un break-even pose a +X aurait")
    a("  transforme ces pertes en ~0.")
    a("")
    a("  C EST UNE BORNE HAUTE. Elle ne compte pas ce que le meme BE")
    a("  aurait coute sur les gagnants qui repassent par +X avant de")
    a("  repartir : ils auraient ete fermes a 0 au lieu de courir. Ce")
    a("  cout ne se mesure que barre par barre. Cette borne sert a")
    a("  savoir si le rejeu vaut la peine, pas a decider a sa place.")
    a("")
    a(barre("-"))
    entete = "%-7s %-22s %7s" % ("MAGIC", "PAPER", "perdants")
    for k in SEUILS:
        entete += "   %5s   %9s" % ("+%.2fR" % k, "perte evi")
    a(entete)
    a(barre("-"))
    for magic, s in lignes:
        ligne = "%-7s %-22s %7d" % (magic, (noms.get(magic) or "")[:22],
                                    s["nd"])
        for k, nb, som in s["gisement"]:
            part = (100.0 * nb / s["nd"]) if s["nd"] else 0.0
            ligne += "   %4.0f%%   %+9.0f" % (part, som)
        a(ligne)
    a(barre("-"))
    if tous:
        ligne = "%-7s %-22s %7d" % ("", "TOUS", tous["nd"])
        for k, nb, som in tous["gisement"]:
            part = (100.0 * nb / tous["nd"]) if tous["nd"] else 0.0
            ligne += "   %4.0f%%   %+9.0f" % (part, som)
        a(ligne)
    a(barre("-"))
    a("  +0.25R  part des perdants montes a un quart de leur perte")
    a("          moyenne avant de mourir, et ce qu ils ont perdu")
    a("  perte evi  la somme de leurs pertes -- ce qu un BE a ce niveau")
    a("             aurait au mieux cesse de perdre")
    a("")

    a(barre())
    a("CE QUE CE PANNEAU NE DIT PAS")
    a(barre())
    a("  Il ne dit pas ou placer le break-even. Il dit s il y a")
    a("  quelque chose a y gagner, et de quel ordre de grandeur.")
    a("")
    a("  Il ne dit rien du cout du BE sur les gagnants. Seul le rejeu")
    a("  barre par barre, qui compte les deux sens, le mesure.")
    a("")
    a("  Le MFE d un trade sorti tot est TRONQUE : on ne saura jamais")
    a("  d ici jusqu ou il serait alle. Les colonnes MFE sont donc")
    a("  elles-memes des minorants du mouvement disponible.")
    return "\n".join(L)


# ----------------------------------------------------------------------
def page_html(txt):
    h = (txt.replace("&", "&amp;").replace("<", "&lt;")
         .replace(">", "&gt;"))
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<title>MFE partage</title></head>'
            '<body style="margin:0;background:#0e1116">'
            '<pre style="font:12px Consolas,monospace;color:#c9d1d9;'
            'background:#0e1116;padding:16px 20px;margin:0;'
            'white-space:pre">' + h + '</pre></body></html>\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--journal", default=JOURNAL)
    ap.add_argument("--min-n", type=int, default=5, dest="min_n",
                    help="effectif minimal pour afficher une ligne")
    a = ap.parse_args()

    journal, ko = lire_jsonl(a.journal)
    if not journal:
        print("ABANDON : %s vide ou absent." % a.journal)
        print("Lance papers_moteur.py d abord. Ce panneau n invente rien.")
        return 2
    if ko:
        print("  %d ligne(s) illisible(s), ignoree(s)." % ko)

    noms, souci = noms_des_papers()
    txt = rendu(journal, noms, souci, a.min_n, a.journal)
    print(txt)

    for d in ("panels", "cartes"):
        if not os.path.isdir(d):
            os.makedirs(d)
    io.open(SORTIE_T, "w", encoding="utf-8", newline="").write(txt + "\n")
    io.open(SORTIE_H, "w", encoding="utf-8", newline="").write(page_html(txt))
    print("")
    print("  ecrit : %s" % SORTIE_T)
    print("  ecrit : %s   (liste /cartes)" % SORTIE_H)
    return 0


if __name__ == "__main__":
    sys.exit(main())
