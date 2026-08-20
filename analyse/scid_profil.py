#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scid_profil.py -- profil de volume par niveau, depuis un fichier
                  Sierra Chart .scid. Volume reel, cote agresseur.

LECTEUR SEUL. N ECRIT RIEN, NE MODIFIE RIEN.

  python scid_profil.py "C:\\SierraChart\\Data\\YMU26-CBOT.scid"
  python scid_profil.py FICHIER --bas 53596 --haut 53705 --pas 5
  python scid_profil.py FICHIER --depuis 2026-08-18 --pas 10

CE QU IL LIT
    En-tete 56 octets : signature SCID, taille d en-tete, taille
    d enregistrement, version. Tout est verifie, rien n est suppose.
    Enregistrement 40 octets : horodatage, OHLC, NumTrades,
    TotalVolume, BidVolume, AskVolume.

    Le champ horodatage a connu DEUX encodages selon la version de
    Sierra Chart -- double en jours depuis 1899-12-30, ou entier
    64 bits en microsecondes depuis la meme origine. Le script decode
    les deux, garde celui qui produit une date plausible, et le dit.

CE QU IL REND
    Par niveau de prix : volume total, volume au bid, volume a l ask,
    delta, nombre de trades, et une barre. Puis le POC (le niveau le
    plus echange), le delta cumule, et -- si une bande est demandee --
    ce que cette bande pese par rapport au reste.

  BidVolume = volume execute a l offre (vendeurs agressifs).
  AskVolume = volume execute a la demande (acheteurs agressifs).
  delta = ask - bid. Positif = acheteurs a l initiative.
"""

import argparse
import datetime
import os
import struct
import sys

SEP = "=" * 96
ORIGINE = datetime.datetime(1899, 12, 30)
EN_TETE = 56
ENREG = 40
FMT = "<q4f4I"


def humain(n):
    for u, s in (("To", 1024 ** 4), ("Go", 1024 ** 3),
                 ("Mo", 1024 ** 2), ("ko", 1024)):
        if n >= s:
            return "%.1f %s" % (n / float(s), u)
    return "%d o" % n


def d_double(b8):
    try:
        (v,) = struct.unpack("<d", b8)
        return ORIGINE + datetime.timedelta(days=v)
    except Exception:
        return None


def d_micro(b8):
    try:
        (v,) = struct.unpack("<q", b8)
        return ORIGINE + datetime.timedelta(microseconds=v)
    except Exception:
        return None


def plausible(d):
    return d is not None and datetime.datetime(1990, 1, 1) <= d <= datetime.datetime(2100, 1, 1)


def jour(s):
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fichier")
    p.add_argument("--bas", type=float)
    p.add_argument("--haut", type=float)
    p.add_argument("--pas", type=float, default=5.0)
    p.add_argument("--depuis")
    p.add_argument("--jusqua")
    p.add_argument("--lignes", type=int, default=60,
                   help="niveaux affiches au maximum")
    a = p.parse_args()

    print(SEP)
    print("PROFIL DE VOLUME -- %s" % os.path.basename(a.fichier))
    print(SEP)
    print()
    print("  Lecture seule. Aucun octet n est ecrit.")
    print()

    if not os.path.isfile(a.fichier):
        print("  introuvable : %s" % a.fichier)
        return
    taille = os.path.getsize(a.fichier)
    print("  taille : %s" % humain(taille))

    f = open(a.fichier, "rb")
    try:
        brut = f.read(EN_TETE)
        if len(brut) < EN_TETE:
            print("  plus court que l en-tete : ce n est pas un .scid")
            return
        magie = brut[:4]
        te, tr = struct.unpack("<II", brut[4:12])
        version = struct.unpack("<H", brut[12:14])[0]
        try:
            lisible = magie.decode("ascii")
        except Exception:
            lisible = repr(magie)
        print("  signature %s   en-tete %d   enregistrement %d   version %d"
              % (lisible, te, tr, version))
        if magie != b"SCID" or te != EN_TETE or tr != ENREG:
            print("  format inattendu. On s arrete plutot que d inventer.")
            return

        nb = (taille - te) // tr
        print("  %d enregistrement(s)" % nb)
        if nb == 0:
            print("  fichier vide.")
            return

        f.seek(te)
        premier = f.read(tr)
        dd, dm = d_double(premier[:8]), d_micro(premier[:8])
        if plausible(dm) and not plausible(dd):
            mode = "micro"
        elif plausible(dd) and not plausible(dm):
            mode = "double"
        elif plausible(dd) and plausible(dm):
            mode = "micro"
        else:
            print("  aucun encodage de date plausible. Arret.")
            return
        print("  dates lues en %s" % ("microsecondes" if mode == "micro" else "jours"))
        print()

        depuis, jusqua = jour(a.depuis), jour(a.jusqua)
        if jusqua:
            jusqua += datetime.timedelta(days=1)

        # --- balayage ----------------------------------------------------
        seaux = {}
        vus = lus = 0
        t_min = t_max = None
        p_min = p_max = None
        f.seek(te)
        paquet = 65536 * tr
        while True:
            bloc = f.read(paquet)
            if not bloc:
                break
            for m in struct.iter_unpack(FMT, bloc[:len(bloc) - len(bloc) % tr]):
                lus += 1
                dt = (ORIGINE + datetime.timedelta(microseconds=m[0])) \
                    if mode == "micro" else d_double(struct.pack("<q", m[0]))
                if dt is None:
                    continue
                if depuis and dt < depuis:
                    continue
                if jusqua and dt >= jusqua:
                    continue
                prix = m[4]                      # close
                if t_min is None or dt < t_min:
                    t_min = dt
                if t_max is None or dt > t_max:
                    t_max = dt
                if p_min is None or prix < p_min:
                    p_min = prix
                if p_max is None or prix > p_max:
                    p_max = prix
                if a.bas is not None and prix < a.bas:
                    continue
                if a.haut is not None and prix > a.haut:
                    continue
                seau = round(prix / a.pas) * a.pas
                s = seaux.get(seau)
                if s is None:
                    s = seaux[seau] = [0, 0, 0, 0]   # vol, bid, ask, trades
                s[0] += m[6]
                s[1] += m[7]
                s[2] += m[8]
                s[3] += m[5]
                vus += 1
            if len(bloc) < paquet:
                break

        print("  %d enregistrement(s) lus, %d retenus" % (lus, vus))
        if t_min and t_max:
            print("  periode couverte : %s -> %s"
                  % (t_min.strftime("%Y-%m-%d %H:%M"),
                     t_max.strftime("%Y-%m-%d %H:%M")))
        if p_min is not None:
            print("  prix parcourus  : %.1f -> %.1f" % (p_min, p_max))
        print()
        if not seaux:
            print("  aucun enregistrement dans ces bornes.")
            if a.bas is not None and p_min is not None:
                print("  Les prix du fichier vont de %.1f a %.1f : la bande"
                      % (p_min, p_max))
                print("  demandee (%.1f - %.1f) est en dehors." % (a.bas, a.haut))
                print("  Sur un future, l ecart avec le CFD est normal --")
                print("  c est la base. Compare les deux echelles avant")
                print("  de conclure quoi que ce soit.")
            return

        # --- profil -------------------------------------------------------
        vmax = max(s[0] for s in seaux.values()) or 1
        niveaux = sorted(seaux, reverse=True)
        if len(niveaux) > a.lignes:
            print("  %d niveaux : seuls les %d plus echanges sont affiches."
                  % (len(niveaux), a.lignes))
            gardes = sorted(niveaux, key=lambda k: -seaux[k][0])[:a.lignes]
            niveaux = sorted(gardes, reverse=True)
            print()

        print(SEP)
        print("PROFIL PAR NIVEAU")
        print(SEP)
        print()
        print("     niveau      volume        bid        ask       delta"
              "   trades")
        print("     " + "-" * 88)
        for n in niveaux:
            vol, bid, ask, tr_ = seaux[n]
            delta = ask - bid
            barre = "#" * int(40.0 * vol / vmax)
            print("  %10.1f  %10d %10d %10d  %10d %8d  %s"
                  % (n, vol, bid, ask, delta, tr_, barre))
        print()

        tv = sum(s[0] for s in seaux.values())
        tb = sum(s[1] for s in seaux.values())
        ta = sum(s[2] for s in seaux.values())
        poc = max(seaux, key=lambda k: seaux[k][0])
        print(SEP)
        print("CE QUE CA DIT")
        print(SEP)
        print()
        print("  volume total     : %d" % tv)
        print("  au bid / a l ask : %d / %d" % (tb, ta))
        print("  delta cumule     : %+d  (%s)"
              % (ta - tb,
                 "acheteurs a l initiative" if ta > tb
                 else ("vendeurs a l initiative" if tb > ta else "equilibre")))
        print("  POC              : %.1f  (%d contrats, %.1f %% du total)"
              % (poc, seaux[poc][0], 100.0 * seaux[poc][0] / tv if tv else 0))
        print()
        forts = sorted(seaux, key=lambda k: -abs(seaux[k][2] - seaux[k][1]))[:5]
        print("  desequilibres les plus francs :")
        for n in forts:
            vol, bid, ask, _t = seaux[n]
            d = ask - bid
            part = 100.0 * abs(d) / vol if vol else 0
            print("    %10.1f  delta %+8d  soit %5.1f %% de son volume"
                  % (n, d, part))
        print()
        if a.bas is None:
            print("  Aucune bande demandee : ce profil porte sur tout le")
            print("  fichier. Pour juger une zone, relance avec --bas et")
            print("  --haut, puis compare avec les zones voisines : un")
            print("  niveau dense entoure de niveaux denses ne prouve rien.")
            print()

    finally:
        f.close()

    print(SEP)
    print("  Rien n a ete ecrit, rien n a ete envoye.")
    print(SEP)


if __name__ == "__main__":
    main()
