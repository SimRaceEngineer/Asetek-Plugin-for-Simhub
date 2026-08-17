# -*- coding: utf-8 -*-
r"""
contrat_continu.py -- raccorder les echeances en une seule serie

  python contrat_continu.py --racine MES --montre
  python contrat_continu.py --racine MES

POURQUOI

    Un future n est liquide que sur son trimestre. `MESU26` est
    l echeance de septembre : ses barres remontent a janvier, mais
    jusqu a la mi-juin elles ne valent rien -- quelques transactions
    eparses sur un contrat que personne ne traite encore.

    Mesure faite le 17/08 sur YM : mediane de 131 barres d une minute
    par jour, pour une moyenne de 471. Un fichier qui affiche six mois
    n en donne que deux et demi d exploitable.

    Pour couvrir mars a aout il faut donc DEUX echeances, et savoir
    ou passer de l une a l autre.

COMMENT ON TROUVE LA BASCULE : PAR LE VOLUME, PAS PAR LE CALENDRIER

    On pourrait coder les dates de roulement du CME. On ne le fait pas :
    ce serait une constante inventee de plus, et le roulement REEL ne
    tombe pas toujours le jour theorique.

    A chaque journee, le contrat de reference est simplement celui qui
    a le PLUS DE VOLUME. La bascule est le jour ou cet argmax change.
    C est mesure sur les donnees qu on a, et si le telechargement d une
    echeance est incomplet, ca se voit : le tableau montre plusieurs
    bascules au lieu d une.

CE QU IL ECRIT, ET CE QU IL N ECRIT PAS

    Un CSV continu avec une colonne `contrat` EN PLUS. La provenance de
    chaque barre est conservee.

    Les prix ne sont PAS ajustes. Deux echeances ne cotent pas au meme
    niveau -- il y a une base entre elles -- donc le raccord porte un
    saut artificiel. Ajuster retro-activement changerait tous les prix
    passes, ce qui est la pratique standard mais rend les niveaux
    absolus faux et casse le lien avec les niveaux de la stack.

    On garde donc les prix bruts et on laisse la colonne `contrat`
    permettre a l aval d ECARTER toute fenetre qui enjambe le raccord.
    Une fenetre a cheval sur deux contrats ne mesure pas un mouvement
    de marche, elle mesure la base.

LECTEUR SEUL : lit cartes\scid\of_*.csv, ecrit un CSV a cote.
"""
import argparse
import csv
import io
import os
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "scid")
LARG = 100


def horo(s):
    if not s:
        return None
    s = s.strip().replace("T", " ")
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s[:19], f)
        except ValueError:
            continue
    return None


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def charge(dossier, racine):
    """Les barres de chaque echeance dont le nom commence par `racine`."""
    out = {}
    if not os.path.isdir(dossier):
        return out
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("of_") or not nom.endswith(".csv"):
            continue
        sym = nom[3:-4]
        if racine and not sym.upper().startswith(racine.upper()):
            continue
        lignes = []
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            for r in csv.DictReader(f, delimiter=";"):
                t = horo(r.get("ts"))
                if t:
                    r["_t"] = t
                    lignes.append(r)
        if lignes:
            lignes.sort(key=lambda r: r["_t"])
            out[sym] = lignes
    return out


def volume_par_jour(lignes):
    v = {}
    for r in lignes:
        d = r["_t"].date()
        v[d] = v.get(d, 0.0) + (flt(r.get("volume")) or 0.0)
    return v


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--racine", default="MES",
                   help="prefixe des echeances, ex MES ou YM")
    p.add_argument("--sortie", default=None)
    p.add_argument("--montre", action="store_true",
                   help="affiche et n ecrit rien")
    a = p.parse_args()

    contrats = charge(a.entree, a.racine)
    if not contrats:
        print("KO : aucun of_%s*.csv dans %s." % (a.racine, a.entree))
        print("     Lancer d abord : python lire_scid.py --dossier ...")
        return 1

    print("=" * LARG)
    print("CONTRAT CONTINU -- racine %s" % a.racine)
    print("=" * LARG)
    print("  %d echeance(s) : %s" % (len(contrats), ", ".join(sorted(contrats))))
    print()
    print("  Le contrat de reference d une journee est celui qui porte le")
    print("  PLUS DE VOLUME ce jour-la. La bascule est mesuree, pas lue")
    print("  dans un calendrier de roulement.")
    print()

    vols = dict((s, volume_par_jour(l)) for s, l in contrats.items())
    jours = sorted(set(d for v in vols.values() for d in v))
    if not jours:
        print("KO : aucune journee.")
        return 1

    # Le dominant de chaque journee, puis les plages.
    dominant = {}
    for d in jours:
        best = None
        for s in contrats:
            v = vols[s].get(d, 0.0)
            if best is None or v > best[1]:
                best = (s, v)
        if best and best[1] > 0:
            dominant[d] = best[0]

    plages = []
    for d in jours:
        s = dominant.get(d)
        if s is None:
            continue
        if plages and plages[-1][0] == s:
            plages[-1][2] = d
            plages[-1][3] += 1
        else:
            plages.append([s, d, d, 1])

    print("  %-16s %-12s %-12s %8s %14s"
          % ("contrat", "du", "au", "jours", "volume total"))
    for s, d0, d1, n in plages:
        tot = sum(v for d, v in vols[s].items() if d0 <= d <= d1)
        print("  %-16s %-12s %-12s %8d %14.0f"
              % (s, d0, d1, n, tot))
    print()
    if len(plages) == 1:
        print("  Une seule plage : soit une seule echeance a des donnees,")
        print("  soit le raccord n a pas lieu d etre.")
    elif len(plages) == 2:
        print("  UNE bascule, le %s. C est ce qu on attend d un roulement"
              % plages[1][1])
        print("  trimestriel propre.")
    else:
        print("  %d plages, donc %d bascules. C est PLUS que le roulement"
              % (len(plages), len(plages) - 1))
        print("  trimestriel n en produirait. Deux causes possibles : une")
        print("  echeance telechargee partiellement, ou des journees ou")
        print("  les volumes sont si proches que l argmax oscille. Les")
        print("  plages d un ou deux jours ci-dessus designent laquelle.")

    # Ce que chaque echeance apporte VRAIMENT, au-dela de sa presence.
    print()
    print("  %-16s %10s %12s %12s"
          % ("contrat", "jours", "med barres/j", "dont dominant"))
    for s in sorted(contrats):
        parj = {}
        for r in contrats[s]:
            d = r["_t"].date()
            parj[d] = parj.get(d, 0) + 1
        c = sorted(parj.values())
        med = c[len(c) // 2] if c else 0
        dom = sum(1 for d in parj if dominant.get(d) == s)
        print("  %-16s %10d %12d %12d" % (s, len(parj), med, dom))
    print()
    print("  `dont dominant` est le seul chiffre qui compte : une")
    print("  echeance peut avoir des barres sur six mois et n etre")
    print("  liquide que sur deux.")

    if a.montre:
        print()
        print("  Rien n a ete ecrit (--montre).")
        return 0

    dest = a.sortie or os.path.join(a.entree, "of_%s_continu.csv" % a.racine)
    n = 0
    with io.open(dest, "w", encoding="utf-8", newline="") as g:
        w = None
        for d in jours:
            s = dominant.get(d)
            if not s:
                continue
            for r in contrats[s]:
                if r["_t"].date() != d:
                    continue
                if w is None:
                    cols = [c for c in r if not c.startswith("_")]
                    w = csv.DictWriter(g, fieldnames=cols + ["contrat"],
                                       delimiter=";", extrasaction="ignore")
                    w.writeheader()
                r2 = dict((k, v) for k, v in r.items()
                          if not k.startswith("_"))
                r2["contrat"] = s
                w.writerow(r2)
                n += 1
    print()
    print("ecrit : %s (%d barres, %d octets)"
          % (dest, n, os.path.getsize(dest)))
    print()
    print("Les prix ne sont PAS ajustes : le raccord porte la base entre")
    print("les deux echeances. La colonne `contrat` permet d ecarter en")
    print("aval toute fenetre qui l enjambe -- une fenetre a cheval ne")
    print("mesure pas un mouvement de marche, elle mesure la base.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
