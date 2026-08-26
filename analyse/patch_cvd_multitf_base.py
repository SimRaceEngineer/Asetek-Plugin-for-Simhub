#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cvd_multitf_base.py -- la base des ticks se mesure, le pas se met a l echelle.

DEUX DEFAUTS TROUVES AU PREMIER PASSAGE REEL
--------------------------------------------
1. LE CADRAGE ECOULE ETAIT VIDE : 401 entrees sur 401 sans donnee,
   alors que 398 fenetres de ticks avaient bien ete lues.

   cale_decalage ne compare que des PRIX. Il etablit qu il faut
   demander les ticks de la barre m dans [m+7200, m+7260] -- il ne dit
   RIEN de la base dans laquelle MT5 renvoie le champ "time" de ces
   ticks.

   L outil du 25/08 ne dependait pas de cette base : une seule fenetre
   M1, et le filtre jusqu_a ne coupait rien. La version multi-unites
   decoupe des sous-fenetres EN COMPARANT les temps des ticks. Si la
   base retournee n est pas decalee, deb + 7200 tombe deux heures dans
   le futur, la sous-fenetre est vide, et l OHLCV rend None a chaque
   fois.

   On ne suppose donc plus : apres avoir trouve le decalage de
   REQUETE, on relit les ticks d une barre connue et on regarde si
   leur time ressemble a m ou a m + decalage. Deux mesures pour deux
   questions differentes, au lieu d une mesure et d une supposition.

2. LE BALAYAGE DU PAS NE BALAYAIT RIEN. Sur M3, "closes" rend
   +548.96 pour pas = 0, 1, 2 ET 5 : les quatre memes chiffres. Les
   deltas grandissent avec la duree de la bougie -- quelques dizaines
   en M1, plusieurs centaines en M15 -- donc un pas absolu de 5 y est
   indistinguable de zero. Seul M1 reagissait.

   Le pas devient donc RELATIF : une fraction de l ecart-type des
   deltas de cette unite et de cet actif. --pas 0.25 veut alors dire
   "un quart d ecart-type", et signifie la meme chose en M1 qu en M15.
   L echelle mesuree est affichee, pour qu on voie ce qu on compare.

   --pas-absolu retablit l ancien comportement, en points de delta.

USAGE
-----
    python patch_cvd_multitf_base.py                <- simulation
    python patch_cvd_multitf_base.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\cvd_multitf.py"
SUFFIXE_BAK = ".bak_base"
MARQUEUR = "BASE_MESUREE"

A1 = '''    dec, n = max(compte.items(), key=lambda kv: kv[1])
    if n < minimum:
        return None, ("le meilleur decalage (%+d s) ne tient que sur %d"
                      " barre(s)" % (dec, n))
    return dec, "%+d s, verifie sur %d barre(s) sur %d" % (dec, n, len(r))'''
B1 = '''    dec, n = max(compte.items(), key=lambda kv: kv[1])
    if n < minimum:
        return None, None, ("le meilleur decalage (%+d s) ne tient que sur"
                            " %d barre(s)" % (dec, n))

    # BASE_MESUREE -- deux questions differentes, deux mesures.
    #
    # Le decalage ci-dessus dit ou DEMANDER les ticks d une barre. Il
    # ne dit rien de la base dans laquelle MT5 renvoie leur champ
    # "time" : cale_decalage ne compare que des prix. Supposer que les
    # deux coincident a vide le cadrage ECOULE au premier passage reel,
    # 401 entrees sur 401 -- la sous-fenetre tombait deux heures dans
    # le futur.
    #
    # On relit donc les ticks d une barre connue et on regarde si leur
    # time ressemble a m ou a m + decalage.
    m0 = int(r[0]["time"])
    base = 0
    try:
        tk = mt5.copy_ticks_range(
            sym, datetime.datetime.utcfromtimestamp(m0 + dec),
            datetime.datetime.utcfromtimestamp(m0 + dec + 60),
            mt5.COPY_TICKS_ALL)
    except Exception:
        tk = None
    if tk is not None and len(tk) > 0:
        vu = int(tk[0]["time"])
        base = dec if abs(vu - (m0 + dec)) < abs(vu - m0) else 0
    return dec, base, ("%+d s pour la requete, %+d s dans les"
                       " horodatages, verifie sur %d barre(s) sur %d"
                       % (dec, base, n, len(r)))'''

A2 = '''        dtick = {}
        for actif, s in sorted(sym.items()):
            d, note = cale_decalage(s)
            dtick[actif] = d
            print("     %-6s %s" % (actif, note if d is not None
                                    else "ECHEC : %s" % note))'''
B2 = '''        dtick, dbase = {}, {}
        for actif, s in sorted(sym.items()):
            d, base, note = cale_decalage(s)
            dtick[actif] = d
            dbase[actif] = base
            print("     %-6s %s" % (actif, note if d is not None
                                    else "ECHEC : %s" % note))'''

A3 = '''                faits += 1
                for nom, mn in UNITES:
                    deb = debut_bougie(t["ts_srv"], mn)
                    sous = [x for x in tk if int(x["time"]) >= deb + dt]
                    x = ohlcv(sous, t["ts_srv"] + dt)
                    if x is None:
                        continue
                    ecoulee[(t["ts"], t["actif"], nom)] = ankit(*x)
            print("     reconstruites %d, sans ticks %d" % (faits, rates))'''
B3 = '''                faits += 1
                # La base des horodatages, MESUREE, et non le decalage
                # de requete : ce sont deux choses differentes.
                db = dbase[t["actif"]]
                for nom, mn in UNITES:
                    deb = debut_bougie(t["ts_srv"], mn)
                    sous = [x for x in tk if int(x["time"]) >= deb + db]
                    x = ohlcv(sous, t["ts_srv"] + db)
                    if x is None:
                        continue
                    ecoulee[(t["ts"], t["actif"], nom)] = ankit(*x)
                    poses += 1
            print("     fenetres lues %d, sans ticks %d, portions"
                  " reconstruites %d" % (faits, rates, poses))
            if poses == 0:
                print("     AUCUNE PORTION. Le cadrage ECOULE sera vide :")
                print("     ne pas lire ses lignes comme un resultat.")'''

A4 = '''            faits = rates = 0
            for t in tickets:'''
B4 = '''            faits = rates = poses = 0
            for t in tickets:'''

# ------------------------------------------------------- le pas relatif
A5 = '''    ap.add_argument("--sans-ticks", action="store_true",
                    help="cadrage CLOSES seul : pas d appel aux ticks")'''
B5 = '''    ap.add_argument("--sans-ticks", action="store_true",
                    help="cadrage CLOSES seul : pas d appel aux ticks")
    ap.add_argument("--pas-absolu", action="store_true",
                    help="le pas est en points de delta, comme avant. Par"
                         " defaut il est RELATIF : une fraction de"
                         " l ecart-type des deltas de l unite, ce qui lui"
                         " donne le meme sens en M1 qu en M15.")'''

A6 = '''        print("  %-4s %s"
              % (nom, "  ".join("%s %d bougies" % (k, len(D[(nom, k)]))
                                for k in sorted(sym))))'''
B6 = '''        print("  %-4s %s"
              % (nom, "  ".join("%s %d bougies" % (k, len(D[(nom, k)]))
                                for k in sorted(sym))))

    # L ECHELLE DES DELTAS, PAR UNITE ET PAR ACTIF.
    # Un delta grandit avec la duree de la bougie : quelques dizaines en
    # M1, plusieurs centaines en M15. Un pas absolu de 5 est donc
    # significatif sur l une et invisible sur l autre -- au premier
    # passage reel, M3 rendait le MEME chiffre pour pas 0, 1, 2 et 5.
    # On mesure l ecart-type pour donner au pas le meme sens partout.
    ECH = {}
    for nom, mn in UNITES:
        for actif in sorted(sym):
            v = list(D[(nom, actif)].values())
            if len(v) > 1:
                moy = sum(v) / len(v)
                ECH[(nom, actif)] = (sum((x - moy) ** 2 for x in v)
                                     / (len(v) - 1.0)) ** 0.5
            else:
                ECH[(nom, actif)] = 0.0
    print("")
    print("  ECHELLE DES DELTAS (ecart-type) -- un pas relatif de 1"
          " vaut ceci")
    for nom, mn in UNITES:
        print("     %-4s %s" % (nom, "  ".join(
            "%s %8.1f" % (k, ECH[(nom, k)]) for k in sorted(sym))))'''

A7 = '''                    ok = passe(cour, prec, t["sens"], pas)'''
B7 = '''                    p_eff = (pas if a.pas_absolu
                             else pas * ECH.get((nom, t["actif"]), 0.0))
                    ok = passe(cour, prec, t["sens"], p_eff)'''

A8 = '''            print("=" * 74)
            print("  %s   pas = %g" % (nom, pas))
            print("=" * 74)'''
B8 = '''            print("=" * 74)
            print("  %s   pas = %g %s" % (nom, pas,
                  "points" if a.pas_absolu else "ecart-type"))
            print("=" * 74)'''

REMPL = ((A1, B1, "la fin de cale_decalage"),
         (A2, B2, "l appel a cale_decalage"),
         (A4, B4, "l initialisation des compteurs"),
         (A3, B3, "la reconstruction par unite"),
         (A5, B5, "les options de la ligne de commande"),
         (A6, B6, "l affichage des bougies lues"),
         (A8, B8, "le titre de bloc"),
         (A7, B7, "l appel a passe()"))


def lire(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        return f.read()


def applique(s):
    for a, _, quoi in REMPL:
        if s.count(a) != 1:
            return None, "%s attendu 1 fois, trouve %d" % (quoi, s.count(a))
    for a, b, _ in REMPL:
        s = s.replace(a, b, 1)
    return s, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_cvd_multitf_base -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    if MARQUEUR in s:
        print("")
        print("Deja pose : la base des horodatages est mesuree.")
        return 0

    neuf, err = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        return 1
    print("        les huit ancres uniques.")
    print("")
    print("a faire :")
    print("   + la BASE des horodatages de ticks est MESUREE, en plus")
    print("     du decalage de requete. Ce sont deux questions")
    print("     differentes, et supposer qu elles coincident a vide le")
    print("     cadrage ECOULE : 401 entrees sur 401 sans donnee.")
    print("   + le pas devient RELATIF a l ecart-type des deltas de")
    print("     l unite. Un pas absolu de 5 est significatif en M1 et")
    print("     invisible en M15 : M3 rendait le meme chiffre pour")
    print("     pas 0, 1, 2 et 5.")
    print("   + l echelle mesuree est affichee, et le nombre de")
    print("     portions reellement reconstruites aussi")
    print("   + --pas-absolu retablit l ancien comportement")

    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = a.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(a.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    print("ecrit : %s" % a.cible)

    relu = lire(a.cible)
    manques = [x for x in (MARQUEUR, "dbase", "ECHELLE DES DELTAS",
                           "pas_absolu", "portions") if x not in relu]
    if manques:
        print("relu  : INCOMPLET, manque %s -- RESTAURER %s"
              % (", ".join(manques), bak))
        return 1
    try:
        compile(relu, a.cible, "exec")
        print("relu  : les cinq marques y sont, et le fichier compile.")
    except SyntaxError as e:
        print("relu  : ERREUR DE SYNTAXE ligne %s -- RESTAURER %s"
              % (e.lineno, bak))
        return 1

    print("")
    print("-" * 68)
    print("  python cvd_multitf.py --pas 0,0.25,0.5,1")
    print("")
    print("Le controle : 'portions reconstruites' doit etre proche de")
    print("quatre fois le nombre de fenetres lues. S il reste a zero, la")
    print("base est encore fausse et le cadrage ECOULE ne veut rien dire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
