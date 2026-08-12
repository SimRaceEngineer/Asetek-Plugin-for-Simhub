# -*- coding: utf-8 -*-
"""
departage.py -- ce qui separe les fenetres qui gagnent de celles qui perdent

  python departage.py --jour 2026-08-12
  python departage.py --depuis 2026-08-05
  python departage.py --jour 2026-08-12 --decalage 60

LA QUESTION, POSEE PAR LA JOURNEE DU 12/08

    L horloge de regime met dans le meme etat DOUTEUX :

        10h34-11h24   50 min   20 tickets   +391.78
        14h24-14h54   30 min   10 tickets   +216.26
        13h39-14h09   30 min    7 tickets   +201.14

    et aussi :

        12h30-13h04   34 min   13 tickets   -399.45
        15h58-16h24   26 min   13 tickets   -337.72
        09h25-10h05   40 min   30 tickets   -259.37

    DOUTEUX n est donc pas un etat, c est un sac. Tant qu on ne sait pas
    le couper, l horloge ne peut rien commander.

LE CRITERE TESTE ICI, ET POURQUOI CELUI-LA

    En tendance, un suiveur ne se retourne pas : il suit et il encaisse.
    En hachoir, il se retourne sans arret et paie chaque aller-retour.

    Le NOMBRE DE RETOURNEMENTS SAR PAR HEURE mesure exactement ca. Il a
    trois vertus qu aucun verdict par trade n a :

      1. il existe A CHAQUE MINUTE, qu on trade ou non -- ce qui comble
         les trous INCONNU de l horloge (US100 y passe 281 minutes sur
         689) ;
      2. il se calcule d avance sur des bougies, sans attendre qu une
         position se cloture ;
      3. il se decline par pas de temps, donc il tranche enfin M1 contre
         M5 -- ce que le verdict churn, unique par trade, ne peut pas.

    On y ajoute le RATIO D EFFICACITE : deplacement net divise par
    chemin parcouru, sur les clotures de la fenetre. 1 = ligne droite,
    proche de 0 = surplace. C est la meme idee mesuree autrement ; si
    les deux disent la meme chose, c est un point de plus.

CE QU IL N INVENTE PAS

    Le SAR vient de sar_anchor._compute_sar quand il accepte nos
    bougies -- le meme calcul que la stack. Sinon, Wilder aux parametres
    de sar_anchor, et le module DIT lequel il a utilise. Deux SAR de
    parametres differents ne se comparent pas.

    Les fenetres, les etats et les euros viennent de horloge_regime,
    importe. Aucun decoupage n est refait ici.

UNE PRECAUTION D HORAIRE

    Les bougies MT5 sont en heure SERVEUR, les tickets portent l heure
    ecrite par la stack. Si les deux differaient, on comparerait des
    fenetres decalees et le resultat serait faux sans avoir l air faux.
    Le module IMPRIME donc les deux plages horaires du jour ; si elles
    ne se superposent pas, --decalage les recale, en minutes.

CE QUE CE SCRIPT NE FAIT PAS

    Il ne conclut pas a votre place et il refuse de conclure sous
    MINI_FENETRES fenetres exploitables. Il compare des medianes ; avec
    six fenetres par camp, une seule journee ne prouve rien -- elle
    indique ou regarder.

LECTURE SEULE. Aucun ordre. Ecrit panels/departage.txt.
"""
import argparse
import io
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import horloge_regime as H
except ImportError:
    print("KO : horloge_regime.py introuvable a cote de ce script.")
    print("Il porte le decoupage en fenetres et les euros par fenetre.")
    print("Les refaire ici donnerait deux decoupages differents du meme")
    print("jour, donc deux verites.")
    sys.exit(1)

try:
    import MetaTrader5 as mt5
except ImportError:
    print("KO : MetaTrader5 introuvable dans cet interpreteur.")
    print("Ce script lit des bougies -- il ne peut rien faire sans.")
    sys.exit(1)

AF_DEPART, AF_PAS, AF_MAX = 0.02, 0.02, 0.20
MINI_FENETRES = 6       # par camp, sous ce nombre on ne compare pas
MINI_TICKETS = 3        # une fenetre sans tickets ne departage rien
MINI_BARRES = 10        # sous ce nombre de bougies M1, pas de ratio
MINI_BARRES_M5 = 5      # ... et en M5, ou dix bougies font cinquante min
DEST = os.path.join(_ICI, "panels")
LARG = 100


# ----------------------------------------------------------------- le SAR

def sar_officiel(rates):
    """_compute_sar de sar_anchor, s il accepte nos bougies.

    Copie conforme de sarkeep_m5.sar_officiel : c est le meme besoin, et
    diverger d un detail invaliderait la comparaison M1/M5."""
    try:
        import sar_anchor as _sa
    except Exception:
        return None
    fn = getattr(_sa, "_compute_sar", None)
    if not callable(fn):
        return None
    try:
        out = fn(rates)
    except Exception:
        return None
    if not out or len(out) < 3:
        return None
    try:
        float(out[-1][0])
    except (TypeError, IndexError, ValueError):
        return None
    return out


def sar_serie(hauts, bas):
    """Parabolic SAR de Wilder. Rend [(sar, sens)]. Secours seulement."""
    n = len(hauts)
    if n < 3:
        return []
    haussier = hauts[1] >= hauts[0]
    sar = bas[0] if haussier else hauts[0]
    ep = hauts[0] if haussier else bas[0]
    af = AF_DEPART
    out = [(sar, "BULL" if haussier else "BEAR")]
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if haussier:
            sar = min(sar, bas[i - 1], bas[max(0, i - 2)])
        else:
            sar = max(sar, hauts[i - 1], hauts[max(0, i - 2)])
        if haussier:
            if bas[i] < sar:
                haussier = False
                sar, ep, af = ep, bas[i], AF_DEPART
            elif hauts[i] > ep:
                ep = hauts[i]
                af = min(af + AF_PAS, AF_MAX)
        else:
            if hauts[i] > sar:
                haussier = True
                sar, ep, af = ep, hauts[i], AF_DEPART
            elif bas[i] < ep:
                ep = bas[i]
                af = min(af + AF_PAS, AF_MAX)
        out.append((sar, "BULL" if haussier else "BEAR"))
    return out


def serie_du_jour(actif, tf, jour):
    """[(minute, sens, close)] pour toute la journee.

    Le SAR est calcule sur la journee ENTIERE puis decoupe, jamais
    fenetre par fenetre : le SAR a une memoire (facteur d acceleration,
    point extreme) et le repartir a zero a chaque fenetre inventerait des
    retournements a chaque frontiere."""
    d0 = datetime.strptime(jour, "%Y-%m-%d")
    r = mt5.copy_rates_range(actif, tf, d0, d0 + timedelta(days=1))
    if r is None or len(r) < MINI_BARRES:
        return [], None
    off = sar_officiel(r)
    if off is not None and len(off) == len(r):
        sens = []
        for i, x in enumerate(off):
            try:
                s = float(x[0])
            except (TypeError, ValueError, IndexError):
                sens = []
                break
            sens.append("BULL" if s < float(r[i]["close"]) else "BEAR")
        if sens:
            return ([(datetime.fromtimestamp(r[i]["time"]).hour * 60
                      + datetime.fromtimestamp(r[i]["time"]).minute,
                      sens[i], float(r[i]["close"])) for i in range(len(r))],
                    "sar_anchor._compute_sar")
    s = sar_serie([float(b["high"]) for b in r], [float(b["low"]) for b in r])
    if not s:
        return [], None
    return ([(datetime.fromtimestamp(r[i]["time"]).hour * 60
              + datetime.fromtimestamp(r[i]["time"]).minute,
              s[i][1], float(r[i]["close"])) for i in range(len(r))],
            "Wilder local (%.2f/%.2f/%.2f)" % (AF_DEPART, AF_PAS, AF_MAX))


def dans(serie, m0, m1, dec):
    return [x for x in serie if m0 <= x[0] - dec < m1]


def retournements(serie, m0, m1, dec):
    """Nombre de changements de sens DANS la fenetre.

    On compare chaque bougie a la precedente de la SERIE COMPLETE, pas de
    la tranche : sinon le premier changement de chaque fenetre serait
    perdu."""
    n = 0
    for i in range(1, len(serie)):
        m = serie[i][0] - dec
        if m0 <= m < m1 and serie[i][1] != serie[i - 1][1]:
            n += 1
    return n


def efficacite(tranche, mini=None):
    """Deplacement net / chemin parcouru. 1 = ligne droite, 0 = surplace.

    Le minimum de bougies differe selon le pas de temps : exiger dix
    bougies M5 reviendrait a n avoir de ratio que sur les fenetres de
    cinquante minutes, c est-a-dire presque aucune."""
    if len(tranche) < (MINI_BARRES if mini is None else mini):
        return None
    c = [x[2] for x in tranche]
    chemin = sum(abs(c[i] - c[i - 1]) for i in range(1, len(c)))
    if chemin <= 0:
        return None
    return abs(c[-1] - c[0]) / chemin


# -------------------------------------------------------------- assemblage

def mediane(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def fmt(x, n=2):
    return "-" if x is None else ("%.*f" % (n, x))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--jour")
    p.add_argument("--depuis")
    p.add_argument("--actifs", nargs="*", default=H.ACTIFS)
    p.add_argument("--fenetre", type=int, default=H.FENETRE)
    p.add_argument("--decalage", type=int, default=0,
                   help="minutes a retrancher a l heure des bougies")
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
    L.append("  DEPARTAGE -- ce qui separe les fenetres qui gagnent"
             " de celles qui perdent")
    L.append("=" * LARG)
    L.append("critere 1 : retournements SAR par heure, en M1 et en M5")
    L.append("critere 2 : ratio d efficacite (net / chemin), 1 = ligne"
             " droite")
    L.append("les deux se calculent sur des bougies, donc a chaque minute,")
    L.append("meme quand on ne trade pas")
    L.append("")

    tout = []
    for jour in cibles:
        ech = H.echantillons(lot, jour, a.fenetre, 1)
        if not ech:
            L.append("%s : aucun verdict horodate." % jour)
            continue
        ivs = H.intervalles(ech)

        series, moteurs = {}, set()
        for act in a.actifs:
            for nom, tf in (("M1", mt5.TIMEFRAME_M1), ("M5", mt5.TIMEFRAME_M5)):
                s, moteur = serie_du_jour(act, tf, jour)
                series[(act, nom)] = s
                if moteur:
                    moteurs.add(moteur)

        toutes = [x for k, x in series.items() if x]
        if not toutes:
            L.append("%s : aucune bougie recuperee. MT5 est-il connecte ?"
                     % jour)
            continue

        bm0 = min(x[0][0] for x in toutes) - a.decalage
        bm1 = max(x[-1][0] for x in toutes) - a.decalage
        tm0 = min(H._mn(s["ts"]) for s in lot if s["jour"] == jour)
        tm1 = max(H._mn(s["ts"]) for s in lot if s["jour"] == jour)
        L.append("-" * LARG)
        L.append(" %s" % jour)
        L.append("-" * LARG)
        L.append("SAR : %s" % (", ".join(sorted(moteurs)) or "indisponible"))
        L.append("bougies %s-%s   tickets %s-%s   decalage applique %d min"
                 % (H.hm(bm0), H.hm(bm1), H.hm(tm0), H.hm(tm1), a.decalage))
        # Les bougies couvrent la seance entiere, les tickets seulement
        # les heures ou l on a trade : comparer les DEBUTS crierait au
        # loup tous les jours. Ce qui compte est que les tickets tombent
        # DANS la couverture des bougies.
        if tm0 < bm0 - 5 or tm1 > bm1 + 5:
            L.append("ATTENTION : des tickets tombent hors de la plage des"
                     " bougies. Les fenetres")
            L.append("comparees ne sont pas les memes. Utilise --decalage"
                     " avant de lire")
            L.append("quoi que ce soit ci-dessous.")
        L.append("")

        L.append("%-13s %-8s %5s %6s %9s %8s %8s %7s %7s"
                 % ("plage", "etat", "tk", "duree", "EUR", "SAR/h M1",
                    "SAR/h M5", "ER M1", "ER M5"))
        L.append("-" * LARG)
        for m0, m1, e, _pa in ivs:
            d, eur = H.chiffres(lot, jour, m0, m1)
            duree = max(1, m1 - m0)
            f1 = f5 = 0
            e1, e5 = [], []
            for act in a.actifs:
                s1, s5 = series.get((act, "M1")), series.get((act, "M5"))
                if s1:
                    f1 += retournements(s1, m0, m1, a.decalage)
                    e1.append(efficacite(dans(s1, m0, m1, a.decalage)))
                if s5:
                    f5 += retournements(s5, m0, m1, a.decalage)
                    e5.append(efficacite(dans(s5, m0, m1, a.decalage),
                                         MINI_BARRES_M5))
            r1 = 60.0 * f1 / duree
            r5 = 60.0 * f5 / duree
            me1, me5 = mediane(e1), mediane(e5)
            L.append("%-13s %-8s %5d %5dm %+9.2f %8.1f %8.1f %7s %7s"
                     % ("%s-%s" % (H.hm(m0), H.hm(m1)), e, len(d), duree,
                        eur, r1, r5, fmt(me1), fmt(me5)))
            if len(d) >= MINI_TICKETS:
                tout.append({"jour": jour, "m0": m0, "m1": m1, "etat": e,
                             "tk": len(d), "eur": eur, "r1": r1, "r5": r5,
                             "e1": me1, "e5": me5})
        L.append("-" * LARG)
        L.append("")

    mt5.shutdown()

    L.append("=" * LARG)
    L.append("  LE CRITERE DEPARTAGE-T-IL ?")
    L.append("=" * LARG)
    gagne = sorted([x for x in tout if x["eur"] > 0],
                   key=lambda x: -x["eur"])
    perd = sorted([x for x in tout if x["eur"] < 0], key=lambda x: x["eur"])
    L.append("%d fenetres d au moins %d tickets : %d gagnantes, %d perdantes"
             % (len(tout), MINI_TICKETS, len(gagne), len(perd)))
    L.append("")

    if len(gagne) < MINI_FENETRES or len(perd) < MINI_FENETRES:
        L.append("MOINS DE %d FENETRES PAR CAMP. On ne compare pas."
                 % MINI_FENETRES)
        L.append("Deux fenetres de plus retourneraient n importe quelle")
        L.append("mediane calculee ici. Relance sur plusieurs seances :")
        L.append("    python departage.py --depuis 2026-08-05")
    else:
        L.append("%-12s %10s %10s %8s %8s"
                 % ("camp", "SAR/h M1", "SAR/h M5", "ER M1", "ER M5"))
        L.append("-" * LARG)
        for nom, camp in (("gagnantes", gagne), ("perdantes", perd)):
            L.append("%-12s %10s %10s %8s %8s"
                     % (nom, fmt(mediane([x["r1"] for x in camp]), 1),
                        fmt(mediane([x["r5"] for x in camp]), 1),
                        fmt(mediane([x["e1"] for x in camp])),
                        fmt(mediane([x["e5"] for x in camp]))))
        L.append("-" * LARG)
        L.append("")
        for clef, nom, sens in (("r1", "SAR/h M1", -1), ("r5", "SAR/h M5", -1),
                                ("e1", "ER M1", 1), ("e5", "ER M5", 1)):
            g = mediane([x[clef] for x in gagne])
            pp = mediane([x[clef] for x in perd])
            if g is None or pp is None:
                continue
            ecart = g - pp
            attendu = "gagnantes < perdantes" if sens < 0 else \
                      "gagnantes > perdantes"
            ok = (ecart < 0) if sens < 0 else (ecart > 0)
            L.append("  %-10s gagnantes %8s   perdantes %8s   %s"
                     % (nom, fmt(g, 2), fmt(pp, 2),
                        "DANS LE SENS ATTENDU" if ok else "A CONTRE-SENS"))
            L.append("             attendu : %s" % attendu)
        L.append("")
        L.append("  Une mediane n est pas un test. Un critere qui va dans le")
        L.append("  bon sens sur une journee peut s inverser la suivante --")
        L.append("  c est arrive quatre fois le 12/08. Ce tableau dit ou")
        L.append("  regarder, il ne dit pas quoi couper.")

    L.append("")
    L.append("=" * LARG)
    L.append("  LES SIX MEILLEURES ET LES SIX PIRES, EN CLAIR")
    L.append("=" * LARG)
    L.append("%-12s %-13s %-8s %5s %9s %8s %8s %7s"
             % ("jour", "plage", "etat", "tk", "EUR", "SAR/h M1",
                "SAR/h M5", "ER M1"))
    L.append("-" * LARG)
    for titre, camp in (("+", gagne[:6]), ("-", perd[:6])):
        for x in camp:
            L.append("%-12s %-13s %-8s %5d %+9.2f %8.1f %8.1f %7s"
                     % (x["jour"], "%s-%s" % (H.hm(x["m0"]), H.hm(x["m1"])),
                        x["etat"], x["tk"], x["eur"], x["r1"], x["r5"],
                        fmt(x["e1"])))
        L.append("-" * LARG)

    for l in L:
        print(l)
    H.ecrire(["# departage.txt",
              "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "# via departage.py", ""] + L,
             os.path.join(a.dest, "departage.txt"))
    print()
    print("ecrit : %s" % os.path.join(a.dest, "departage.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
