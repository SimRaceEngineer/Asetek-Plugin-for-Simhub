# -*- coding: utf-8 -*-
"""
signal_avance.py -- le meme critere, mais utilisable AVANT

  python signal_avance.py --depuis 2026-08-05
  python signal_avance.py --depuis 2026-08-05 --passe 30 --futur 30
  python signal_avance.py --jour 2026-08-12 --pas 5

CE QUI CLOCHAIT DANS departage.py

    Il comptait les retournements SAR A L INTERIEUR d une fenetre, puis
    les comparait aux euros de cette meme fenetre. On ne connait ce
    compte qu une fois la fenetre finie : c est un signal POSTERIEUR. Il
    decrit la journee, il ne peut rien commander.

    « Cette periode a ete hachee et elle a perdu » n apprend rien. Ce
    qu il faut savoir, c est : « les trente dernieres minutes ont ete
    hachees -- que va faire la demi-heure qui vient ? »

LA FORME CORRECTE, ET ELLE TIENT EN UNE LIGNE

    A chaque instant t d une grille :

        MESURE   sur [t - passe, t)   -- strictement du passe
        RESULTAT sur [t, t + futur)   -- strictement de l avenir

    Aucune bougie posterieure a t n entre dans la mesure, aucun ticket
    anterieur a t n entre dans le resultat. C est ce qui separe une
    description d une prevision, et c est verifiable en lisant les deux
    bornes ci-dessous.

    La mesure glisse a chaque minute : elle est donc disponible AVANT le
    mouvement, et PENDANT -- ce qui etait la demande.

CE QU ON MESURE, TOUJOURS SUR LE PASSE

    SAR/h M1, SAR/h M5   retournements par heure sur la fenetre passee
    ER M1, ER M5         deplacement net / chemin parcouru, meme fenetre

    Les deux viennent de departage.py, importe. Le SAR est celui de
    sar_anchor quand il accepte nos bougies -- le module le dit.

CE QU ON EN FAIT

    On range les instants par quartile de chaque mesure, et on regarde
    les euros du futur dans chaque quartile. Si le critere sert, le
    quartile le plus hache doit perdre nettement plus que le plus calme,
    et l ordre doit etre MONOTONE. Un ecart entre extremes sans monotonie
    est presque toujours du bruit.

LES DEUX LIMITES, ECRITES PLUTOT QUE TUES

    1. Les quartiles sont decoupes sur les memes journees que celles ou
       on les evalue. C est de l in-sample : le seuil est choisi apres
       coup. Le tableau indique une piste, il ne donne pas un seuil a
       coder. Pour un vrai seuil il faudra couper le corpus en deux.

    2. Un instant sans aucun ticket dans son futur n apprend rien sur la
       rentabilite : il est compte a part, jamais comme un zero. Melanger
       « on n a pas trade » et « on a trade pour zero euro » ferait
       paraitre calme n importe quel creneau desert.

LECTURE SEULE. Aucun ordre. Ecrit panels/signal_avance.txt.
"""
import argparse
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import departage as D
except ImportError:
    print("KO : departage.py introuvable a cote de ce script.")
    print("Il porte le SAR, le ratio d efficacite et la lecture des")
    print("bougies. Les recopier ici donnerait deux calculs du meme")
    print("indicateur, donc deux verites.")
    sys.exit(1)

H = D.H
mt5 = D.mt5

PASSE = 30            # minutes de mesure, en arriere
FUTUR = 30            # minutes de resultat, en avant
PAS = 5               # minutes entre deux instants de la grille
QUARTS = 4
MINI_POINTS = 40      # instants exploitables sous lesquels on ne conclut pas
MINI_PAR_SEAU = 8
DEST = os.path.join(_ICI, "panels")
LARG = 100

MESURES = [("r1", "SAR/h M1", -1), ("r5", "SAR/h M5", -1),
           ("e1", "ER M1", 1), ("e5", "ER M5", 1)]


def quartiles(v, n=QUARTS):
    """Bornes de seaux. Rend n-1 valeurs, ou moins si trop d ex aequo."""
    v = sorted(x for x in v if x is not None)
    if len(v) < n * 2:
        return []
    out = []
    for k in range(1, n):
        b = v[int(len(v) * k / float(n))]
        if not out or b > out[-1]:
            out.append(b)
    return out


def seau(x, bornes):
    for i, b in enumerate(bornes):
        if x < b:
            return i
    return len(bornes)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--jour")
    p.add_argument("--depuis")
    p.add_argument("--actifs", nargs="*", default=H.ACTIFS)
    p.add_argument("--passe", type=int, default=PASSE)
    p.add_argument("--futur", type=int, default=FUTUR)
    p.add_argument("--pas", type=int, default=PAS)
    p.add_argument("--decalage", type=int, default=0)
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()

    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        return 1

    chemins = a.fichier or H.O.sources(None)
    lot, brut = H.charger(chemins)
    if not lot:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        return 1

    jours = sorted(set(s["jour"] for s in lot))
    if a.jour:
        cibles = [a.jour]
    elif a.depuis:
        cibles = [j for j in jours if j >= a.depuis]
    else:
        cibles = jours[-1:]

    L = []
    L.append("=" * LARG)
    L.append("  SIGNAL EN AVANCE -- mesure sur le passe, resultat sur"
             " l avenir")
    L.append("=" * LARG)
    L.append("mesure   : les %d minutes AVANT t   [t-%d, t)"
             % (a.passe, a.passe))
    L.append("resultat : les %d minutes APRES t   [t, t+%d)"
             % (a.futur, a.futur))
    L.append("un instant tous les %d min, sur %d seance(s)"
             % (a.pas, len(cibles)))
    L.append("aucune bougie posterieure a t dans la mesure, aucun ticket")
    L.append("anterieur a t dans le resultat")
    L.append("")

    points, moteurs = [], set()
    sans_ticket = 0
    for jour in cibles:
        series = {}
        for act in a.actifs:
            for nom, tf in (("M1", mt5.TIMEFRAME_M1),
                            ("M5", mt5.TIMEFRAME_M5)):
                s, moteur = D.serie_du_jour(act, tf, jour)
                series[(act, nom)] = s
                if moteur:
                    moteurs.add(moteur)
        dispo = [x for x in series.values() if x]
        if not dispo:
            L.append("%s : aucune bougie recuperee." % jour)
            continue
        m0 = min(x[0][0] for x in dispo) - a.decalage
        m1 = max(x[-1][0] for x in dispo) - a.decalage

        t = m0 + a.passe
        while t + a.futur <= m1:
            f1 = f5 = 0
            e1, e5 = [], []
            for act in a.actifs:
                s1, s5 = series.get((act, "M1")), series.get((act, "M5"))
                if s1:
                    f1 += D.retournements(s1, t - a.passe, t, a.decalage)
                    e1.append(D.efficacite(
                        D.dans(s1, t - a.passe, t, a.decalage)))
                if s5:
                    f5 += D.retournements(s5, t - a.passe, t, a.decalage)
                    e5.append(D.efficacite(
                        D.dans(s5, t - a.passe, t, a.decalage),
                        D.MINI_BARRES_M5))
            d, eur = H.chiffres(lot, jour, t, t + a.futur)
            if not d:
                sans_ticket += 1
                t += a.pas
                continue
            points.append({
                "jour": jour, "t": t,
                "r1": 60.0 * f1 / a.passe, "r5": 60.0 * f5 / a.passe,
                "e1": D.mediane(e1), "e5": D.mediane(e5),
                "tk": len(d), "eur": eur})
            t += a.pas

    mt5.shutdown()

    L.append("SAR : %s" % (", ".join(sorted(moteurs)) or "indisponible"))
    L.append("%d instants avec au moins un ticket dans leur futur,"
             " %d sans" % (len(points), sans_ticket))
    L.append("  Les instants sans ticket sont ecartes, jamais comptes comme")
    L.append("  zero euro : « on n a pas trade » n est pas « on a trade pour")
    L.append("  rien », et les confondre ferait paraitre calme n importe")
    L.append("  quel creneau desert.")
    L.append("")

    if len(points) < MINI_POINTS:
        L.append("MOINS DE %d INSTANTS EXPLOITABLES. On ne conclut pas."
                 % MINI_POINTS)
        L.append("Relance sur plus de seances :")
        L.append("    python signal_avance.py --depuis 2026-07-28")
        for l in L:
            print(l)
        H.ecrire(L, os.path.join(a.dest, "signal_avance.txt"))
        return 0

    for clef, nom, sens in MESURES:
        v = [x[clef] for x in points if x[clef] is not None]
        bornes = quartiles(v)
        L.append("=" * LARG)
        L.append("  %s -- mesure sur les %d minutes precedentes"
                 % (nom, a.passe))
        L.append("=" * LARG)
        if not bornes:
            L.append("  Trop d ex aequo pour decouper en quartiles.")
            L.append("")
            continue
        L.append("  seuils : %s"
                 % "  ".join(D.fmt(b, 2) for b in bornes))
        L.append("%-10s %10s %8s %8s %12s %12s"
                 % ("quartile", "plage", "instants", "tickets", "EUR",
                    "EUR/ticket"))
        L.append("-" * LARG)
        seaux = defaultdict(lambda: [0, 0, 0.0, []])
        for x in points:
            if x[clef] is None:
                continue
            i = seau(x[clef], bornes)
            seaux[i][0] += 1
            seaux[i][1] += x["tk"]
            seaux[i][2] += x["eur"]
            seaux[i][3].append(x[clef])
        moyennes = []
        for i in sorted(seaux):
            n, tk, eur, vals = seaux[i]
            m = ("%s a %s" % (D.fmt(min(vals), 1), D.fmt(max(vals), 1)))
            par = eur / tk if tk else None
            moyennes.append((i, n, par))
            L.append("%-10s %10s %8d %8d %+12.2f %12s"
                     % ("Q%d" % (i + 1), m, n, tk, eur,
                        D.fmt(par) if par is not None else "-"))
        L.append("-" * LARG)

        util = [(i, par) for i, n, par in moyennes
                if n >= MINI_PAR_SEAU and par is not None]
        if len(util) < 2:
            L.append("  Seaux trop maigres pour comparer.")
        else:
            suite = [par for _i, par in util]
            croit = all(suite[k] <= suite[k + 1] for k in range(len(suite) - 1))
            decroit = all(suite[k] >= suite[k + 1]
                          for k in range(len(suite) - 1))
            attendu_croit = sens > 0
            monotone = croit if attendu_croit else decroit
            L.append("  du quartile le plus %s au plus %s : %s"
                     % ("faible", "fort",
                        "  ".join("%+.2f" % s for s in suite)))
            if monotone:
                L.append("  MONOTONE DANS LE SENS ATTENDU. C est le seul cas")
                L.append("  qui merite qu on continue a creuser.")
            elif croit or decroit:
                # Une inversion propre n est pas du bruit : c est une
                # information, et souvent plus interessante que l accord.
                L.append("  MONOTONE, MAIS A CONTRE-SENS. Ce n est pas du")
                L.append("  bruit : le critere trie, dans l autre sens que")
                L.append("  celui qu on attendait. A comprendre avant de")
                L.append("  s en servir -- ou de le jeter.")
            else:
                L.append("  NON MONOTONE. Un ecart entre extremes sans")
                L.append("  monotonie est presque toujours du bruit : on ne")
                L.append("  code pas un seuil la-dessus.")
        L.append("")

    L.append("=" * LARG)
    L.append("  CE QUE CE TABLEAU N EST PAS")
    L.append("=" * LARG)
    L.append("  Les quartiles sont decoupes sur les journees memes ou on les")
    L.append("  evalue : le seuil est choisi apres coup. Un critere peut")
    L.append("  paraitre net ainsi et ne rien valoir sur la seance suivante.")
    L.append("  Pour un seuil utilisable, il faut couper le corpus en deux :")
    L.append("  seuils sur la premiere moitie, verdict sur la seconde.")
    L.append("")
    L.append("  Et meme monotone, un critere ne dit pas COMBIEN on gagne a")
    L.append("  s en servir : couper les trades du pire quartile suppose que")
    L.append("  les autres restent identiques, ce qui est un plafond, pas")
    L.append("  une prevision.")

    for l in L:
        print(l)
    H.ecrire(["# signal_avance.txt",
              "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "# via signal_avance.py", ""] + L,
             os.path.join(a.dest, "signal_avance.txt"))
    print()
    print("ecrit : %s" % os.path.join(a.dest, "signal_avance.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
