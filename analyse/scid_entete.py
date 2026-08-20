# -*- coding: utf-8 -*-
"""
scid_entete.py -- que contient reellement un fichier Sierra Chart .scid ?

Lecture seule stricte. Aucun octet n est ecrit.

Le format documente est :

  en-tete, 56 octets
    char     FileTypeUniqueHeaderID[4]   "SCID"
    uint32   HeaderSize
    uint32   RecordSize
    uint16   Version
    uint16   Unused1
    uint32   UTCStartIndex
    char     Reserve[36]

  enregistrement, 40 octets
    8 octets DateTime
    float    Open, High, Low, Close
    uint32   NumTrades
    uint32   TotalVolume
    uint32   BidVolume
    uint32   AskVolume

Le champ DateTime a connu DEUX encodages selon la version de Sierra
Chart : un double = jours depuis 1899-12-30, et un entier signe 64
bits = microsecondes depuis la meme origine. Ce script n en suppose
aucun : il decode les deux, garde celui qui produit une date
plausible, et le dit.

Usage :
    python scid_entete.py CHEMIN.scid
    python scid_entete.py CHEMIN.scid --echantillon 500000
    python scid_entete.py CHEMIN.scid --tout        (relit tout, long)
"""

import os
import sys
import struct
import datetime

SEP = "=" * 92

ORIGINE = datetime.datetime(1899, 12, 30)
EN_TETE = 56
ENREG = 40

FMT_ENREG = "<q4f4I"   # les 8 premiers octets relus ensuite selon l encodage


def humain(n):
    for unite, seuil in (("To", 1024 ** 4), ("Go", 1024 ** 3),
                         ("Mo", 1024 ** 2), ("ko", 1024)):
        if n >= seuil:
            return "%.1f %s" % (n / float(seuil), unite)
    return "%d o" % n


def date_double(brut8):
    (v,) = struct.unpack("<d", brut8)
    try:
        return ORIGINE + datetime.timedelta(days=v)
    except Exception:
        return None


def date_micro(brut8):
    (v,) = struct.unpack("<q", brut8)
    try:
        return ORIGINE + datetime.timedelta(microseconds=v)
    except Exception:
        return None


def plausible(d):
    return d is not None and datetime.datetime(1990, 1, 1) <= d <= datetime.datetime(2100, 1, 1)


def decode_enreg(brut, mode):
    """-> (date, o, h, b, c, ntrades, vol, vbid, vask)"""
    _dt, o, h, b, c, nt, vt, vb, va = struct.unpack(FMT_ENREG, brut)
    d = date_micro(brut[:8]) if mode == "micro" else date_double(brut[:8])
    return d, o, h, b, c, nt, vt, vb, va


def ligne(e):
    d, o, h, b, c, nt, vt, vb, va = e
    quand = d.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if d else "(date illisible)"
    return ("  %s  O %10.2f  H %10.2f  B %10.2f  C %10.2f"
            "  trades %6d  vol %8d  bid %8d  ask %8d"
            % (quand, o, h, b, c, nt, vt, vb, va))


def main():
    if len(sys.argv) < 2:
        print("usage : python scid_entete.py CHEMIN.scid")
        return
    chemin = sys.argv[1]
    args = sys.argv[2:]
    tout = "--tout" in args
    ech = 200000
    if "--echantillon" in args:
        i = args.index("--echantillon")
        if i + 1 < len(args):
            try:
                ech = int(args[i + 1])
            except ValueError:
                pass

    print(SEP)
    print("SIERRA CHART .scid -- LECTURE DE L EN-TETE")
    print(SEP)
    print()
    print("  Lecture seule. Aucun octet n est ecrit.")
    print()

    if not os.path.isfile(chemin):
        print("  introuvable : %s" % chemin)
        return

    taille = os.path.getsize(chemin)
    print("  fichier : %s" % chemin)
    print("  taille  : %s (%d octets)" % (humain(taille), taille))
    print()

    f = open(chemin, "rb")
    try:
        brut = f.read(EN_TETE)
        if len(brut) < EN_TETE:
            print("  fichier plus court que l en-tete : ce n est pas un .scid")
            return

        magie = brut[:4]
        taille_entete, taille_enreg = struct.unpack("<II", brut[4:12])
        version, _inutilise = struct.unpack("<HH", brut[12:16])
        (debut_utc,) = struct.unpack("<I", brut[16:20])

        print(SEP)
        print("EN-TETE, TEL QU IL EST ECRIT DANS LE FICHIER")
        print(SEP)
        try:
            lisible = magie.decode("ascii")
        except Exception:
            lisible = repr(magie)
        print("  signature      : %s" % lisible)
        print("  taille en-tete : %d" % taille_entete)
        print("  taille enreg.  : %d" % taille_enreg)
        print("  version        : %d" % version)
        print("  UTCStartIndex  : %d" % debut_utc)
        print()

        if magie != b"SCID":
            print("  La signature n est pas SCID. On s arrete : le reste")
            print("  du decodage n aurait aucun sens.")
            return
        if taille_enreg != ENREG or taille_entete != EN_TETE:
            print("  Tailles inattendues (attendu %d / %d)." % (EN_TETE, ENREG))
            print("  On s arrete plutot que d inventer un decodage.")
            return

        utiles = taille - taille_entete
        nb = utiles // taille_enreg
        reste = utiles % taille_enreg
        print("  enregistrements : %d" % nb)
        if reste:
            print("  reste non aligne : %d octet(s) -- fichier tronque ?" % reste)
        print()
        if nb == 0:
            print("  aucun enregistrement.")
            return

        # --- quel encodage de date ? on teste, on ne suppose pas ---------
        f.seek(taille_entete)
        premier = f.read(taille_enreg)
        dd = date_double(premier[:8])
        dm = date_micro(premier[:8])

        print(SEP)
        print("QUEL ENCODAGE DE DATE ? (teste, pas suppose)")
        print(SEP)
        print("  lu comme double  (jours)          : %s   %s"
              % (dd or "illisible", "plausible" if plausible(dd) else "rejete"))
        print("  lu comme int64   (microsecondes)  : %s   %s"
              % (dm or "illisible", "plausible" if plausible(dm) else "rejete"))
        print()

        if plausible(dm) and not plausible(dd):
            mode = "micro"
        elif plausible(dd) and not plausible(dm):
            mode = "double"
        elif plausible(dd) and plausible(dm):
            mode = "micro"
            print("  Les deux passent. On garde les microsecondes (format")
            print("  actuel), mais VERIFIE la coherence des dates ci-dessous.")
            print()
        else:
            print("  Aucun des deux ne donne une date plausible.")
            print("  On s arrete : mieux vaut pas de reponse qu une fausse.")
            return
        print("  encodage retenu : %s" % mode)
        print()

        # --- premiers, milieu, derniers ---------------------------------
        def lire(i):
            f.seek(taille_entete + i * taille_enreg)
            b = f.read(taille_enreg)
            if len(b) < taille_enreg:
                return None
            return decode_enreg(b, mode)

        print(SEP)
        print("PREMIERS ENREGISTREMENTS")
        print(SEP)
        for i in range(min(5, nb)):
            e = lire(i)
            if e:
                print(ligne(e))
        print()
        print(SEP)
        print("MILIEU")
        print(SEP)
        for i in range(nb // 2, min(nb // 2 + 3, nb)):
            e = lire(i)
            if e:
                print(ligne(e))
        print()
        print(SEP)
        print("DERNIERS")
        print(SEP)
        for i in range(max(0, nb - 5), nb):
            e = lire(i)
            if e:
                print(ligne(e))
        print()

        p, d = lire(0), lire(nb - 1)
        if p and d and p[0] and d[0]:
            duree = d[0] - p[0]
            print("  couverture : du %s au %s"
                  % (p[0].strftime("%Y-%m-%d %H:%M:%S"),
                     d[0].strftime("%Y-%m-%d %H:%M:%S")))
            print("               soit %d jours" % duree.days)
            print()

        # --- statistiques -----------------------------------------------
        combien = nb if tout else min(ech, nb)
        print(SEP)
        if tout:
            print("STATISTIQUES SUR LA TOTALITE (%d enregistrements)" % combien)
        else:
            print("STATISTIQUES SUR LES %d PREMIERS (--tout pour tous)" % combien)
        print(SEP)

        f.seek(taille_entete)
        vol = vbid = vask = ntr = 0
        vus = 0
        sans_cote = 0
        paquet = 8192
        while vus < combien:
            n = min(paquet, combien - vus)
            b = f.read(n * taille_enreg)
            if len(b) < taille_enreg:
                break
            for k in range(len(b) // taille_enreg):
                m = b[k * taille_enreg:(k + 1) * taille_enreg]
                _dt, _o, _h, _bb, _c, nt, vt, vb, va = struct.unpack(FMT_ENREG, m)
                ntr += nt
                vol += vt
                vbid += vb
                vask += va
                if vb == 0 and va == 0:
                    sans_cote += 1
                vus += 1
        print("  enregistrements lus : %d" % vus)
        print("  trades              : %d" % ntr)
        print("  volume total        : %d" % vol)
        print("  volume au bid       : %d" % vbid)
        print("  volume a l ask      : %d" % vask)
        print("  delta (ask - bid)   : %d" % (vask - vbid))
        print("  sans cote (bid=ask=0) : %d  (%.1f %%)"
              % (sans_cote, 100.0 * sans_cote / vus if vus else 0))
        print()
        if sans_cote == vus:
            print("  AUCUN enregistrement ne porte de cote agresseur.")
            print("  Ce fichier ne permet donc PAS de delta. Il ne contient")
            print("  que du prix et du volume agrege.")
        elif vbid + vask > 0:
            print("  Le cote agresseur est present. Le delta et le delta")
            print("  cumule sont donc calculables directement, sans")
            print("  abonnement supplementaire.")
        print()

    finally:
        f.close()

    print(SEP)
    print("  Ce script n a rien ecrit, rien efface, rien envoye.")
    print(SEP)


if __name__ == "__main__":
    main()
