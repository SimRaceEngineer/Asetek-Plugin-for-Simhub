# -*- coding: utf-8 -*-
"""
familles.py -- le x60, et les autres : mener ou seulement etre la

  python familles.py --depuis 2026-07-21
  python familles.py --setup 60
  python familles.py --depuis 2026-07-21 --setup 60 --detail

L HYPOTHESE A TESTER

    Les magics en x60 tradent peu et gagnent beaucoup. Sur 261 fenetres,
    six magics -- 206160, 207160, 206260, 207260, 206360, 207360 --
    totalisent 137 tickets et environ +5 742 EUR pendant que le corpus
    entier perd. Et quand l un d eux ALLUME, la fenetre semble partir.

    Chaque ligne prise seule porte moins de cinq allumages, donc ne se
    lit pas. Mais six lignes independantes qui pointent dans le meme
    sens, ce n est pas un tirage a treize. On les teste donc EN FAMILLE.

LA QUESTION QUE L HYPOTHESE NE TRANCHE PAS

    Le x60 MENE-t-il, ou est-il seulement PRESENT ? Si les fenetres ou
    il trade sont bonnes qu il ait allume ou non, alors allumer
    n apporte rien -- c est la famille qui est bonne, pas son rang.

    Le tableau central separe donc trois populations :

        il ALLUME       il est le premier entre de la fenetre
        il est PRESENT  il trade dans la fenetre, sans l ouvrir
        il est ABSENT   aucun de ses tickets

    Si « allume » ne fait pas mieux que « present », l ignition ne sert
    a rien et il ne reste qu un bon setup.

LA DECOMPOSITION DU MAGIC, ET ELLE EST DEDUITE

    Sur six chiffres, le module lit :

        M 206 3 02   ->  bras 206, actif 3, setup 02

    bras 206 / 207 / 208, actif 1 = US30, 2 = US500, 3 = US100. Cette
    lecture est INFEREE des donnees, pas documentee : M207302 trade
    US100, M206202 trade US500, M207102 trade US30. Le module IMPRIME sa
    decomposition et VERIFIE l actif contre celui du ticket. Si les deux
    se contredisent, il le dit et ne range rien.

    Les magics qui n ont pas six chiffres -- M2411, M2403 -- sont
    ranges a part, jamais forces dans le moule.

LECTURE SEULE. Aucun ordre. Ecrit panels/familles.txt.
"""
import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import horloge_regime as H
except ImportError:
    print("KO : horloge_regime.py introuvable a cote de ce script.")
    sys.exit(1)

ACTIF_CODE = {"1": "US30", "2": "US500", "3": "US100"}
MINI = 20             # tickets sous lesquels une ligne ne se lit pas
MINI_FEN = 8          # fenetres sous lesquelles une ligne ne se lit pas
DEST = os.path.join(_ICI, "panels")
LARG = 100

RE_MAGIC = re.compile(r"^M(\d+)$")


def decomposer(magic):
    """(bras, actif_attendu, setup) ou (None, None, None)."""
    m = RE_MAGIC.match(str(magic))
    if not m or len(m.group(1)) != 6:
        return None, None, None
    d = m.group(1)
    return d[:3], ACTIF_CODE.get(d[3]), d[4:]


def agrege(lot):
    n = len(lot)
    eur = sum(s["pnl"] for s in lot if s["pnl"] is not None)
    w = sum(1 for s in lot if (s["pnl"] or 0) > 0)
    return n, eur, (eur / n if n else 0.0), (100.0 * w / n if n else 0.0)


def ligne(nom, lot, mini=MINI):
    n, eur, par, wr = agrege(lot)
    return ("%-24s %7d %12.2f %11.2f %6.0f%%%s"
            % (nom, n, eur, par, wr, "" if n >= mini else "  ?"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--depuis")
    p.add_argument("--jour")
    p.add_argument("--setup", default="60")
    p.add_argument("--detail", action="store_true")
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()

    chemins = a.fichier or H.O.sources(None)
    lot, brut = H.charger(chemins)
    if not lot:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        return 1
    if a.depuis:
        lot = [s for s in lot if s["jour"] >= a.depuis]
    if a.jour:
        lot = [s for s in lot if s["jour"] == a.jour]
    if not lot:
        print("Aucun ticket sur la periode demandee.")
        return 1

    L = []
    L.append("=" * LARG)
    L.append("  FAMILLES DE MAGIC -- mener, ou seulement etre la")
    L.append("=" * LARG)
    L.append("%d tickets, %s -> %s"
             % (len(lot), min(s["jour"] for s in lot),
                max(s["jour"] for s in lot)))
    L.append("")

    # ------------------------------------------------ la decomposition
    L.append("=" * LARG)
    L.append("  LA DECOMPOSITION DU MAGIC -- deduite, pas documentee")
    L.append("=" * LARG)
    conflits, hors = [], defaultdict(int)
    for s in lot:
        bras, att, setup = decomposer(s["magic"])
        s["bras"], s["setup"] = bras, setup
        if bras is None:
            hors[s["magic"]] += 1
        elif att and s["actif"] and att != s["actif"]:
            conflits.append((s["magic"], att, s["actif"]))
    vus = {}
    for s in lot:
        if s["bras"]:
            vus.setdefault((s["bras"], s["setup"]), set()).add(s["actif"])
    L.append("  bras lus    : %s"
             % ", ".join(sorted(set(s["bras"] for s in lot if s["bras"]))))
    L.append("  setups lus  : %s"
             % ", ".join(sorted(set(s["setup"] for s in lot if s["setup"]))))
    L.append("  actif : 1 = US30, 2 = US500, 3 = US100")
    if conflits:
        L.append("")
        L.append("  ATTENTION : %d tickets ou le chiffre d actif contredit"
                 % len(conflits))
        L.append("  l actif du ticket. La decomposition est fausse et le")
        L.append("  reste de ce fichier ne doit pas etre lu.")
        for mg, att, reel in conflits[:5]:
            L.append("    %s annonce %s, le ticket dit %s" % (mg, att, reel))
    else:
        L.append("  Aucun conflit : le chiffre d actif colle au ticket sur")
        L.append("  les %d tickets a six chiffres."
                 % sum(1 for s in lot if s["bras"]))
    if hors:
        L.append("")
        L.append("  Hors format (ranges a part, jamais forces) : %s"
                 % ", ".join("%s x%d" % (k, v)
                             for k, v in sorted(hors.items(),
                                                key=lambda kv: -kv[1])[:8]))
    L.append("")

    # ------------------------------------------------ par setup
    L.append("=" * LARG)
    L.append("  PAR SETUP -- les trois actifs et les deux bras reunis")
    L.append("=" * LARG)
    L.append("%-24s %7s %12s %11s %7s"
             % ("", "N", "EUR total", "EUR/ticket", "WR"))
    L.append("-" * LARG)
    par_setup = defaultdict(list)
    for s in lot:
        par_setup[s["setup"] or "hors format"].append(s)
    for k, v in sorted(par_setup.items(), key=lambda kv: -agrege(kv[1])[2]):
        L.append(ligne("setup %s" % k, v))
    L.append("-" * LARG)
    L.append("  Trie par EUR/ticket. Un ? signale moins de %d tickets." % MINI)
    L.append("")

    cible = a.setup
    fam = [s for s in lot if s["setup"] == cible]
    if not fam:
        L.append("Aucun ticket de setup %s sur la periode." % cible)
        for l in L:
            print(l)
        return 1

    L.append("=" * LARG)
    L.append("  LE SETUP %s DANS LE DETAIL" % cible)
    L.append("=" * LARG)
    L.append("%-24s %7s %12s %11s %7s"
             % ("", "N", "EUR total", "EUR/ticket", "WR"))
    L.append("-" * LARG)
    for act in ("US30", "US500", "US100"):
        for bras in sorted(set(s["bras"] for s in fam if s["bras"])):
            v = [s for s in fam if s["actif"] == act and s["bras"] == bras]
            if v:
                L.append(ligne("%s  %s" % (act, bras), v))
    L.append("-" * LARG)
    L.append(ligne("TOUT LE SETUP %s" % cible, fam))
    L.append(ligne("TOUT LE RESTE", [s for s in lot if s["setup"] != cible]))
    L.append("-" * LARG)
    L.append("")

    # ------------------------------------------------ mener ou etre la
    L.append("=" * LARG)
    L.append("  ALLUMER, ETRE PRESENT, OU ETRE ABSENT")
    L.append("=" * LARG)
    jours = sorted(set(s["jour"] for s in lot))
    fenetres = []
    for jour in jours:
        duj = [s for s in lot if s["jour"] == jour]
        ech = H.echantillons(duj, jour, H.FENETRE, 1)
        if not ech:
            continue
        for m0, m1, e, _pa in H.intervalles(ech):
            d, eur = H.chiffres(duj, jour, m0, m1)
            if len(d) < 3:
                continue
            prem = min(d, key=lambda s: s["ts"])
            fenetres.append({
                "jour": jour, "m0": m0, "m1": m1, "eur": eur, "tk": len(d),
                "allume": prem["setup"] == cible,
                "present": any(s["setup"] == cible for s in d),
                "prem": prem["magic"], "d": d})
    if not fenetres:
        L.append("  Aucune fenetre exploitable.")
    else:
        L.append("%-26s %8s %12s %13s %12s"
                 % ("", "fenetres", "EUR total", "EUR/fenetre",
                    "part gagnantes"))
        L.append("-" * LARG)
        groupes = [
            ("le setup %s ALLUME" % cible,
             [f for f in fenetres if f["allume"]]),
            ("il est PRESENT sans allumer",
             [f for f in fenetres if f["present"] and not f["allume"]]),
            ("il est ABSENT",
             [f for f in fenetres if not f["present"]]),
        ]
        for nom, g in groupes:
            if not g:
                L.append("%-26s %8d %12s %13s %12s" % (nom, 0, "-", "-", "-"))
                continue
            eur = sum(f["eur"] for f in g)
            gag = 100.0 * sum(1 for f in g if f["eur"] > 0) / len(g)
            L.append("%-26s %8d %12.2f %13.2f %11.0f%%%s"
                     % (nom, len(g), eur, eur / len(g), gag,
                        "" if len(g) >= MINI_FEN else "  ?"))
        L.append("-" * LARG)
        al = [f for f in fenetres if f["allume"]]
        pr = [f for f in fenetres if f["present"] and not f["allume"]]
        if len(al) >= MINI_FEN and len(pr) >= MINI_FEN:
            ma = sum(f["eur"] for f in al) / len(al)
            mp = sum(f["eur"] for f in pr) / len(pr)
            L.append("  ALLUMER rapporte %+.2f par fenetre, ETRE PRESENT"
                     " %+.2f." % (ma, mp))
            if ma > mp:
                L.append("  Allumer fait mieux qu etre present : le RANG")
                L.append("  ajoute quelque chose au setup.")
            else:
                L.append("  Allumer ne fait pas mieux qu etre present : ce")
                L.append("  n est pas l ignition qui paie, c est le setup.")
                L.append("  L hypothese du declencheur ne tient pas ici.")
        else:
            L.append("  PAS ASSEZ DE FENETRES POUR TRANCHER : %d allumages,"
                     % len(al))
            L.append("  %d presences sans allumage, minimum %d de chaque."
                     % (len(pr), MINI_FEN))
            L.append("  C est la question centrale et elle reste ouverte.")
            L.append("  Il faut plus d historique, ou un setup plus frequent.")
        L.append("")
        L.append("  Rappel : une fenetre ou le setup %s allume contient" % cible)
        L.append("  aussi ses propres tickets. Une partie du gain de la")
        L.append("  ligne « ALLUME » est donc le sien, pas celui qu il")
        L.append("  aurait fait gagner aux autres. Le tableau suivant separe.")
        L.append("")

        L.append("=" * LARG)
        L.append("  DANS LES FENETRES OU IL ALLUME : LUI, ET LES AUTRES")
        L.append("=" * LARG)
        L.append("%-24s %7s %12s %11s %7s"
                 % ("", "N", "EUR total", "EUR/ticket", "WR"))
        L.append("-" * LARG)
        sien = [s for f in al for s in f["d"] if s["setup"] == cible]
        autre = [s for f in al for s in f["d"] if s["setup"] != cible]
        L.append(ligne("ses tickets a lui", sien))
        L.append(ligne("ceux de tous les autres", autre))
        L.append("-" * LARG)
        L.append("  C est CETTE ligne qui dirait qu il entraine les autres.")
        L.append("  Si « les autres » perdent quand meme, alors le x60 gagne")
        L.append("  seul et ne tire personne -- ce serait une raison de le")
        L.append("  faire trader plus, pas d en faire un feu vert.")

    if a.detail:
        L.append("")
        L.append("=" * LARG)
        L.append("  LES FENETRES OU LE SETUP %s ALLUME" % cible)
        L.append("=" * LARG)
        for f in sorted(al, key=lambda x: -x["eur"]):
            L.append("  %s  %s-%s  %2d tickets  %+10.2f  premier : %s"
                     % (f["jour"], H.hm(f["m0"]), H.hm(f["m1"]), f["tk"],
                        f["eur"], f["prem"]))

    for l in L:
        print(l)
    H.ecrire(["# familles.txt",
              "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "# via familles.py --setup %s" % cible, ""] + L,
             os.path.join(a.dest, "familles.txt"))
    print()
    print("ecrit : %s" % os.path.join(a.dest, "familles.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
