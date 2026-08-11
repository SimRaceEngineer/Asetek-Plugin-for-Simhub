# -*- coding: utf-8 -*-
"""
rails_range.py -- le panel rails scinde au 05/08 : tendance d un cote, range de l autre

  python rails_range.py
  python rails_range.py --bascule 2026-08-05

CE QU IL CORRIGE
    Le panel 8095 agrege tout depuis le 28/07. Or le 28/07 au 04/08 est
    une jambe de TENDANCE (US30 +2735 points, 93% de la largeur du canal)
    et le 05/08 au 11/08 est un RANGE (12 a 27% de la largeur, les deux
    seances les plus calmes des soixante). Les deux periodes sont
    melangees dans chaque cellule du panel, et une moyenne entre deux
    regimes opposes ne decrit aucun des deux.

    Ce script recalcule tout, cote a cote. Rien d autre : memes champs,
    meme lecture, meme corpus. Seule la scission est nouvelle.

    Heureux hasard du plancher : le corpus rails ne remonte pas avant le
    28/07, donc le compartiment "avant" EST la jambe de tendance, presque
    a la seance pres. La comparaison est donc tendance contre range, pas
    "l ete contre maintenant".

CE QU IL LIT
    Les memes rails_trades*.jsonl que oos_v9.py, avec SA normalisation --
    importee, pas recopiee. Deux lectures divergentes du meme fichier
    produiraient des chiffres incomparables avec le gel V9, et on ne
    saurait pas lequel croire.

    Un champ de plus, que oos_v9 ne garde pas : le magic. C est la moitie
    de la question posee -- y a-t-il des magics qui passent en range.

LES PETITS EFFECTIFS SONT LE PIEGE PRINCIPAL
    Le range ne fait qu une poignee de seances. Decoupe par heure ET par
    magic, on tombe vite sur des cellules de trois tickets. Trois lectures
    externes du panel ont deja presente des cellules de 2 a 26 tickets
    comme des regles.

    Toute cellule sous MINI tickets est donc imprimee en grise, avec un
    point d interrogation. Elle n est pas cachee -- la cacher serait une
    autre facon de mentir -- mais elle ne se lit pas.

CE QU IL NE FAIT PAS
    Il ne gele rien. Le gel V9 est ferme, son empreinte est posee, son
    verdict tombe le 01/09. Ce qui sort d ici est une observation qui
    pourra nourrir un gel V10, apres septembre.
"""
import argparse
import io
import json
import os
import sys

try:
    import oos_v9 as O
except ImportError:
    print("KO : oos_v9.py introuvable a cote de ce script.")
    print("Il porte la normalisation des champs rails (CLEFS_POS, _etat_tf,")
    print("_sens...). La recopier ici produirait deux lectures du meme")
    print("fichier, donc des chiffres incomparables avec le gel V9.")
    sys.exit(1)

BASCULE = "2026-08-05"
MINI = 30          # sous ce nombre de tickets, une cellule ne se lit pas
CLEFS_MAGIC = ["magic", "magic_number", "magicnumber", "mg"]


def charger(chemins):
    """Comme oos_v9.charger, plus le magic. Meme normalisation, importee."""
    par = {}
    brut = 0
    for ch in chemins:
        for l in io.open(ch, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            brut += 1
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts = str(O._prem(o, O.CLEFS_TS) or "")
            pnl = O._nombre(O._prem(o, O.CLEFS_PNL))
            tk = O._prem(o, O.CLEFS_TICKET)
            if len(ts) < 16 or pnl is None or tk is None or tk in par:
                continue
            mg = O._nombre(O._prem(o, CLEFS_MAGIC))
            s = {"jour": ts[:10], "hm": ts[11:16], "heure": ts[11:13],
                 "pnl": pnl, "sens": O._sens(o),
                 "magic": ("M%d" % int(mg)) if mg else "M?"}
            for tf in O.TFS:
                s["biais_" + tf.lower()] = O._etat_tf(o, tf)[0]
            par[tk] = s
    if not par:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        print("Lance  python oos_v9.py --champs  pour voir ce qu elles contiennent.")
        sys.exit(1)
    return list(par.values())


def agrege(lot):
    p = sum(s["pnl"] for s in lot)
    n = len(lot)
    w = sum(1 for s in lot if s["pnl"] > 0)
    return p, n, w


def duo(lab, avant, depuis, largeur=22):
    """Une ligne : la meme cellule dans les deux regimes, cote a cote."""
    out = "%-*s" % (largeur, lab[:largeur])
    for lot in (avant, depuis):
        if not lot:
            out += "%22s" % "-"
            continue
        p, n, w = agrege(lot)
        marque = " ?" if n < MINI else "  "
        out += "%9.2f %4d %3.0f%%%s" % (p / n, n, 100.0 * w / n, marque)
    return out


def bloc(titre, clef, av, dp, ordre=None, largeur=22):
    print()
    print("=" * 92)
    print("  " + titre)
    print("=" * 92)
    print("%-*s %21s %21s" % (largeur, "", "TENDANCE 28/07-04/08", "RANGE depuis 05/08"))
    print("%-*s %9s %4s %4s   %9s %4s %4s"
          % (largeur, "", "EUR/tr", "N", "WR", "EUR/tr", "N", "WR"))
    print("-" * 92)
    ga, gd = {}, {}
    for s in av:
        ga.setdefault(clef(s), []).append(s)
    for s in dp:
        gd.setdefault(clef(s), []).append(s)
    cles = ordre if ordre is not None else sorted(set(ga) | set(gd))
    for c in cles:
        if not ga.get(c) and not gd.get(c):
            continue
        print(duo(str(c), ga.get(c, []), gd.get(c, []), largeur))
    print("-" * 92)


def main():
    global MINI
    p = argparse.ArgumentParser()
    p.add_argument("--bascule", default=BASCULE)
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--mini", type=int, default=MINI)
    a = p.parse_args()
    MINI = a.mini

    ch = O.sources(a.fichier)
    lot = charger(ch)
    lot.sort(key=lambda s: (s["jour"], s["hm"]))

    av = [s for s in lot if s["jour"] < a.bascule]
    dp = [s for s in lot if s["jour"] >= a.bascule]
    ja = sorted(set(s["jour"] for s in av))
    jd = sorted(set(s["jour"] for s in dp))

    print("=== SCALP-EA / PANEL RAILS SCINDE AU %s ===" % a.bascule)
    print("fichiers : %s" % ", ".join(os.path.basename(c) for c in ch))
    print("%d tickets exploitables, %s -> %s"
          % (len(lot), lot[0]["jour"], lot[-1]["jour"]))
    print()
    print("  TENDANCE  %d tickets sur %d seances (%s)"
          % (len(av), len(ja), ", ".join(ja) if ja else "aucune"))
    print("  RANGE     %d tickets sur %d seances (%s)"
          % (len(dp), len(jd), ", ".join(jd) if jd else "aucune"))
    if not av or not dp:
        print()
        print("Un des deux compartiments est vide : la comparaison n a pas")
        print("de sens. Verifie --bascule contre les dates ci-dessus.")
        return 1
    pa, na, wa = agrege(av)
    pd_, nd, wd = agrege(dp)
    print()
    print("  ensemble  tendance %+9.2f EUR  %+6.2f/ticket  WR %.0f%%"
          % (pa, pa / na, 100.0 * wa / na))
    print("            range    %+9.2f EUR  %+6.2f/ticket  WR %.0f%%"
          % (pd_, pd_ / nd, 100.0 * wd / nd))

    bloc("PAR HEURE -- quelles heures restent tradables en range",
         lambda s: s["heure"] + "h", av, dp,
         ordre=["%02dh" % h for h in range(24)])

    # Les magics sont composes : base + actif + pas de temps. La famille
    # regroupe donc le module, le magic entier isole la variante -- les deux
    # se lisent, et la famille tient debout quand le magic seul n a plus que
    # six tickets.
    fams = sorted(set(s["magic"][:4] for s in lot),
                  key=lambda f: -sum(1 for s in dp if s["magic"][:4] == f))
    bloc("PAR FAMILLE DE MAGIC", lambda s: s["magic"][:4], av, dp, ordre=fams)

    mags = sorted(set(s["magic"] for s in lot),
                  key=lambda m: -sum(1 for s in dp if s["magic"] == m))
    bloc("PAR MAGIC ENTIER -- y en a-t-il qui passent en range",
         lambda s: s["magic"], av, dp, ordre=mags)

    bloc("PAR SENS", lambda s: s["sens"] or "(inconnu)", av, dp,
         ordre=["ACHAT", "VENTE", "(inconnu)"])

    for tf in ("m1", "m3", "m5", "m15"):
        bloc("BIAIS DES RAILS %s x SENS -- le gel V9 famille X, reteste"
             % tf.upper(),
             lambda s, t=tf: "%s / %s" % (s["biais_" + t] or "?",
                                          s["sens"] or "?"),
             av, dp)

    print()
    print("COMMENT LIRE, ET SURTOUT COMMENT NE PAS LIRE")
    print("  Une cellule suivie de ? compte moins de %d tickets. Elle est" % MINI)
    print("  imprimee pour que rien ne soit cache, pas pour etre lue. Trois")
    print("  lectures externes du panel ont deja presente des cellules de 2 a")
    print("  26 tickets comme des regles.")
    print("  L unite honnete est la seance, pas le ticket. Le range n en")
    print("  compte que %d : meme une cellule bien remplie repose sur une" % len(jd))
    print("  poignee de journees, et deux mauvaises journees suffiraient a")
    print("  retourner n importe laquelle des lignes ci-dessus.")
    print("  Ce tableau ne gele rien. Le gel V9 est ferme et rend son verdict")
    print("  le 01/09 ; ce qui sort d ici pourra nourrir un V10, apres.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
