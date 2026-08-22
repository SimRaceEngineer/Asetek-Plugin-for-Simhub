# -*- coding: utf-8 -*-
"""
scid_echelle.py -- a quelle echelle de ticks l orderflow dit-il quelque
                   chose ? Et ou sont les endroits troubles ?

  python scid_echelle.py --liste
  python scid_echelle.py --fichier C:\\SierraChart\\Data\\YMU26-CBOT.scid
  python scid_echelle.py --fichier ... --jours 5 --melanges 3

CE QU ON CHERCHE

    En 1 tick, delta et mouvement de prix sont du bruit -- c est le
    constat de depart. La question est de savoir si en agregeant par
    3, 5, 8, 10, 20, 30, 50, 100, 200, 500 ou 1000 ticks une structure
    apparait, et laquelle.

LE PIEGE, ET LE TEMOIN QUI LE DESAMORCE

    Agreger N ticks fait de delta ET de la variation de prix des sommes
    de N termes. Leur correlation MONTE avec N mecaniquement, meme sur
    du bruit pur. Un balayage sans temoin conclura toujours  plus c est
    gros, mieux c est , et ce sera faux.

    Le temoin : les prix restent dans leur ordre, les bornes de barres
    aussi, et SEULS les deltas sont relus dans un ordre melange. On
    casse ainsi  ce delta-la avec ce moment-la  sans toucher a la
    marche du prix. Ce qui reste apres soustraction du temoin est ce
    que l appariement apporte. C est la seule colonne a lire.

    Melanger les TICKS ENTIERS, le reflexe naturel, serait FAUX : cela
    detruirait la marche aleatoire du prix en meme temps que le lien
    teste. Le temoin aurait alors une distribution de variations sans
    rapport avec le reel -- mesure au banc, un tel temoin annonce 3,2
    fois plus d absorption que le hasard sur du bruit pur, c est a dire
    un faux positif franc.

L ABSORPTION, ET POURQUOI C EST ELLE QU ON VEUT

    Un endroit trouble n est pas un endroit ou ca bouge : c est un
    endroit ou ca NE bouge PAS alors que ca devrait. Beaucoup de delta,
    peu de prix parcouru : quelqu un tient le niveau. Le script compte
    les barres du dernier decile de |delta| ET du premier decile de
    |variation|, puis regarde a quels PRIX elles se concentrent.

    Le temoin sert la aussi : en remelangeant les seuls deltas il y a
    toujours des barres qui remplissent les deux conditions par
    hasard. Le nombre observe ne vaut que compare a ce nombre-la.

CE QUE CE SCRIPT NE FAIT PAS

    Il ne convertit pas les niveaux vers le CFD et ne corrige pas
    l heure : la base future/CFD derive d environ 20 points par semaine
    et doit etre MESUREE sur la semaine en cours, pas supposee. C est
    le travail de scid_visites.py. Ici les prix sont ceux du future et
    les heures celles du fichier. La conversion vient apres.

    Aucune ecriture, aucun ordre. Lecture seule.
"""
import argparse
import datetime
import math
import os
import random
import struct
import sys
from array import array

SEP = "=" * 84
ORIGINE = datetime.datetime(1899, 12, 30)
EN_TETE = 56
ENREG = 40
FMT = "<q4f4I"
ECHELLES = [1, 3, 5, 8, 10, 20, 30, 50, 100, 200, 500, 1000]
MINI_BARRES = 30
SEUIL_SIGMA = 3.0


def humain(n):
    for u in ("", "k", "M"):
        if abs(n) < 1000:
            return "%.0f%s" % (n, u) if u else "%d" % n
        n /= 1000.0
    return "%.1fG" % n


def mediane(v):
    if not v:
        return 0.0
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def ecart_type(v):
    n = len(v)
    if n < 2:
        return 0.0
    m = sum(v) / n
    return math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))


def quantile(v, q):
    if not v:
        return 0.0
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(len(s) * q)))]


def pearson(x, y):
    n = len(x)
    if n < 3:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    sxy = sxx = syy = 0.0
    for i in range(n):
        a = x[i] - mx
        b = y[i] - my
        sxy += a * b
        sxx += a * a
        syy += b * b
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


# ---------------------------------------------------------------- lecture
def lit_scid(chemin):
    """(temps, prix, vol, bid, ask). Repris de scid_visites, inchange."""
    if not os.path.isfile(chemin):
        return None, "fichier introuvable"
    taille = os.path.getsize(chemin)
    f = open(chemin, "rb")
    try:
        brut = f.read(EN_TETE)
        if len(brut) < EN_TETE or brut[:4] != b"SCID":
            return None, "signature absente : ce n est pas un .scid"
        te, tr = struct.unpack("<II", brut[4:12])
        if te != EN_TETE or tr != ENREG:
            return None, "tailles inattendues (%d / %d)" % (te, tr)
        f.seek(te)
        b8 = f.read(tr)[:8]
        if len(b8) < 8:
            return None, "fichier sans aucun tick (en-tete seul)"
        (vi,) = struct.unpack("<q", b8)
        (vd,) = struct.unpack("<d", b8)
        bornes = (datetime.datetime(1990, 1, 1), datetime.datetime(2100, 1, 1))

        def _mi(v):
            try:
                return ORIGINE + datetime.timedelta(microseconds=v)
            except Exception:
                return None

        def _mj(v):
            try:
                return ORIGINE + datetime.timedelta(days=v)
            except Exception:
                return None

        if _mi(vi) is not None and bornes[0] <= _mi(vi) <= bornes[1]:
            mode = "micro"
        elif _mj(vd) is not None and bornes[0] <= _mj(vd) <= bornes[1]:
            mode = "double"
        else:
            return None, "aucun encodage de date plausible"

        t, p, v, b, a = array("q"), array("f"), array("I"), array("I"), array("I")
        f.seek(te)
        paquet = 65536 * tr
        base = int((ORIGINE - datetime.datetime(1970, 1, 1)).total_seconds())
        while True:
            bloc = f.read(paquet)
            if not bloc:
                break
            util = bloc[:len(bloc) - len(bloc) % tr]
            for m in struct.iter_unpack(FMT, util):
                if mode == "micro":
                    sec = base + m[0] // 1000000
                else:
                    (jours,) = struct.unpack("<d", struct.pack("<q", m[0]))
                    sec = base + int(jours * 86400)
                t.append(sec)
                p.append(m[4])
                v.append(m[6])
                b.append(m[7])
                a.append(m[8])
            if len(bloc) < paquet:
                break
        return (t, p, v, b, a, mode, taille), None
    finally:
        f.close()


def deltas(b, a):
    """Delta par tick : volume a l achat moins volume a la vente."""
    return [a[i] - b[i] for i in range(len(b))]


def barres(p, d, vols, n, perm=None):
    """(variation, delta, prix_median, volume) par barre de n ticks.

    La variation est prise de CLOTURE A CLOTURE, d une barre a la
    suivante -- pas entre le premier et le dernier tick DANS la barre.
    Prendre l ecart interne jetterait le saut entre deux barres, et a
    n = 1 il vaudrait zero par construction : la ligne  1 tick  ne
    mesurerait alors plus rien du tout.

    perm : le TEMOIN. Les prix restent dans leur ordre, les bornes de
    barres aussi ; seuls les deltas sont relus dans un autre ordre.

    Melanger les TICKS entiers, comme on serait tente de le faire,
    serait faux : cela detruirait la marche aleatoire du prix en meme
    temps que le lien qu on veut tester, et donnerait un temoin dont la
    distribution de variations n a plus rien a voir avec le reel. La
    comparaison ne voudrait alors plus rien dire. Ici le temoin ne
    casse QUE l appariement  ce delta-la avec ce moment-la .
    """
    dp, dd, px, dv = [], [], [], []
    m = len(p)
    prec = None
    for i in range(0, m - n + 1, n):
        j1 = i + n - 1
        p1 = p[j1]
        p0 = prec if prec is not None else p[i]
        prec = p1
        t = 0
        vt = 0
        lo = hi = p[i]
        for k in range(i, i + n):
            t += d[perm[k]] if perm is not None else d[k]
            if vols is not None:
                vt += vols[k]
            q = p[k]
            if q < lo:
                lo = q
            if q > hi:
                hi = q
        dp.append(p1 - p0)
        dd.append(float(t))
        px.append((lo + hi) / 2.0)
        dv.append(vt)
    return dp, dd, px, dv


def bloc_balayage(p, d, echelles, melanges, rng):
    print("")
    print(SEP)
    print("BALAYAGE D ECHELLE -- le reel contre le melange")
    print(SEP)
    print("")
    print("  correlation entre le delta d une barre et sa variation de prix.")
    print("  temoin = les memes deltas dans un ordre melange, prix et")
    print("  bornes de barres inchanges, %d tirage(s)." % melanges)
    print("")
    print("   ticks   barres   |var| med    reel   temoin    ECART   sigma")
    print("  " + "-" * 70)
    n_ticks = len(p)
    droit = list(range(n_ticks))
    resultats = []
    for n in echelles:
        if n_ticks // n < MINI_BARRES:
            print("   %5d      -- moins de %d barres, ignore"
                  % (n, MINI_BARRES))
            continue
        dp, dd, _px, _dv = barres(p, d, None, n)
        r = pearson(dd, dp)
        temoins = []
        for _k in range(melanges):
            melange = droit[:]
            rng.shuffle(melange)
            mdp, mdd, _m, _w = barres(p, d, None, n, perm=melange)
            temoins.append(pearson(mdd, mdp))
        tm = sum(temoins) / len(temoins) if temoins else 0.0
        sd = ecart_type(temoins)
        ec = r - tm
        sig = (ec / sd) if sd > 0 else 0.0
        med = mediane([abs(x) for x in dp])
        print("   %5d %8d %10.2f %7.3f %8.3f %8.3f %7.1f"
              % (n, len(dp), med, r, tm, ec, sig))
        resultats.append((abs(sig), n, r, tm, ec, len(dp)))
    print("  " + "-" * 70)
    print("")
    if not resultats:
        print("  Trop peu de ticks pour balayer quoi que ce soit.")
        return None
    resultats.sort(reverse=True)
    sig, n, r, tm, ec, nb = resultats[0]
    print("  sigma = de combien d ecarts-types du temoin le reel s ecarte.")
    print("  Un tirage de %d melanges donne une precision grossiere : on"
          % melanges)
    print("  exige %.0f sigma avant de retenir une echelle." % SEUIL_SIGMA)
    print("")
    if sig < SEUIL_SIGMA:
        print("  AUCUNE ECHELLE NE SE DETACHE. Le plus gros ecart est a")
        print("  %d ticks (%+.3f, soit %.1f sigma) et ne passe pas le"
              % (n, ec, sig))
        print("  seuil. Autrement dit : agreger davantage ne fait pas")
        print("  apparaitre de lien entre delta et prix que le hasard ne")
        print("  produise deja. Le  plus c est gros mieux c est  de la")
        print("  colonne reel est un artefact d agregation, rien d autre.")
        secours = max(x[1] for x in resultats)
        print("")
        print("  Pour la suite on prend %d ticks PAR CONVENTION (la plus"
              % secours)
        print("  grande echelle exploitable), pas parce qu elle gagne.")
        return secours
    print("  RETENU : %d ticks -- ecart %+.3f, soit %.1f sigma."
          % (n, ec, sig))
    print("  (reel %+.3f, temoin %+.3f, sur %d barres)" % (r, tm, nb))
    print("")
    print("  Lire la colonne ECART, pas la colonne reel. Si ECART reste")
    print("  plat quand reel monte, c est l agregation qui parle, pas le")
    print("  marche -- et il n y a aucune echelle privilegiee.")
    return n


def compte_troubles(p, d, n, vols=None, perm=None):
    """(indices troubles, ...) a l echelle n. perm = temoin."""
    dp, dd, px, dv = barres(p, d, vols, n, perm=perm)
    if len(dp) < MINI_BARRES:
        return None
    sd = quantile([abs(x) for x in dd], 0.90)
    sp = quantile([abs(x) for x in dp], 0.10)
    idx = [i for i in range(len(dp))
           if abs(dd[i]) >= sd and abs(dp[i]) <= sp]
    return idx, dp, dd, px, dv, sd, sp


def bloc_absorption(t, p, d, v, echelles, melanges, rng, combien):
    print("")
    print(SEP)
    print("LES ENDROITS TROUBLES -- beaucoup de delta, peu de prix")
    print(SEP)
    print("")
    print("  Une barre  trouble  est dans le dernier decile de |delta| ET")
    print("  dans le premier decile de |variation| : le flux pousse fort,")
    print("  le prix ne bouge pas. Quelqu un tient le niveau.")
    print("")
    print("  Le decoupage en deciles en produit MECANIQUEMENT quelques")
    print("  unes, meme sur du bruit. La colonne  attendues  dit combien,")
    print("  mesuree en remelangeant les seuls deltas. Seul l ecart")
    print("  compte, jamais le compte brut.")
    print("")
    print("   ticks   barres  troubles  attendues   rapport   sigma")
    print("  " + "-" * 62)
    droit = list(range(len(p)))
    garde = []
    for n in echelles:
        r = compte_troubles(p, d, n, vols=v)
        if r is None:
            continue
        idx = r[0]
        faux = []
        for _k in range(melanges):
            melange = droit[:]
            rng.shuffle(melange)
            rm = compte_troubles(p, d, n, perm=melange)
            if rm is not None:
                faux.append(len(rm[0]))
        att = sum(faux) / len(faux) if faux else 0.0
        sd = ecart_type(faux)
        sig = ((len(idx) - att) / sd) if sd > 0 else 0.0
        rap = (len(idx) / att) if att > 0 else 0.0
        print("   %5d %8d %9d %10.1f %9.2f %7.1f"
              % (n, len(r[1]), len(idx), att, rap, sig))
        garde.append((sig, n, idx, r, att))
    print("  " + "-" * 62)
    print("")
    if not garde:
        print("  Pas assez de barres a aucune echelle.")
        return
    garde.sort(key=lambda g: -g[0])
    sig, n, idx, r, att = garde[0]
    if sig < SEUIL_SIGMA or not idx:
        print("  AUCUNE ECHELLE NE MONTRE D ABSORPTION. Le meilleur cas")
        print("  est %d ticks (%.1f sigma) et ne passe pas le seuil de"
              % (n, sig))
        print("  %.0f sigma. Les barres  troubles  qu on trouverait ici"
              % SEUIL_SIGMA)
        print("  sont celles que le decoupage fabrique tout seul : les")
        print("  memes deltas remelanges en donnent autant.")
        print("")
        print("  Conclusion a ce stade : ce fichier ne contient pas de")
        print("  niveau tenu reperable par delta contre variation, a")
        print("  aucune des echelles balayees.")
        return
    _idx, dp, dd, px, dv, seuil_d, seuil_p = r
    print("  ECHELLE RETENUE : %d ticks -- %d barres troubles contre %.1f"
          % (n, len(idx), att))
    print("  attendues, soit %.1f sigma au-dessus du hasard."
          % sig)
    print("  seuils : |delta| >= %.0f (dernier decile), |var| <= %.2f"
          % (seuil_d, seuil_p))
    print("")
    print("   quand              prix        delta    var       volume")
    print("  " + "-" * 66)
    idx = sorted(idx, key=lambda i: -abs(dd[i]))
    for i in idx[:combien]:
        j = i * n
        h = datetime.datetime.utcfromtimestamp(t[j]).strftime("%Y-%m-%d %H:%M")
        print("   %-16s %10.2f %11.0f %6.2f %12d"
              % (h, px[i], dd[i], dp[i], dv[i]))
    print("  " + "-" * 66)
    if len(idx) > combien:
        print("   ... et %d autres, --combien pour en voir plus"
              % (len(idx) - combien))
    print("")
    print("  Heures brutes du fichier, prix du FUTURE. Ni le decalage")
    print("  horaire ni la base future/CFD ne sont appliques ici --")
    print("  scid_visites.py les MESURE, il ne faut pas les supposer.")

    seaux = {}
    for i in idx:
        seaux[round(px[i])] = seaux.get(round(px[i]), 0) + abs(dd[i])
    if seaux:
        print("")
        print("  Ou ca se concentre, par prix entier :")
        for prix, d in sorted(seaux.items(), key=lambda kv: -kv[1])[:12]:
            print("    %10d   delta cumule %10.0f" % (prix, d))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*", default=[])
    p.add_argument("--dossier", default=r"C:\SierraChart\Data")
    p.add_argument("--liste", action="store_true")
    p.add_argument("--jours", type=int, default=5,
                   help="ne garder que les N derniers jours du fichier")
    p.add_argument("--maxi", type=int, default=400000,
                   help="plafond de ticks analyses, les plus recents")
    p.add_argument("--melanges", type=int, default=3)
    p.add_argument("--combien", type=int, default=20)
    p.add_argument("--graine", type=int, default=7)
    a = p.parse_args()
    rng = random.Random(a.graine)
    if a.melanges < 2:
        print("  --melanges doit valoir au moins 2 : sigma se calcule sur")
        print("  la dispersion des tirages, un seul tirage n en a pas.")
        return 1

    if a.liste or not a.fichier:
        print(SEP)
        print("FICHIERS .scid DISPONIBLES")
        print(SEP)
        print("")
        if not os.path.isdir(a.dossier):
            print("  dossier introuvable : %s" % a.dossier)
            return 1
        noms = sorted(f for f in os.listdir(a.dossier)
                      if f.lower().endswith(".scid"))
        if not noms:
            print("  aucun .scid dans %s" % a.dossier)
            return 1
        print("   %-28s %10s %12s  %s" % ("fichier", "taille", "ticks", "periode"))
        print("  " + "-" * 78)
        for nom in noms:
            c = os.path.join(a.dossier, nom)
            d, err = lit_scid(c)
            if d is None:
                print("   %-28s  %s" % (nom[:28], err))
                continue
            t = d[0]
            if not len(t):
                print("   %-28s  vide" % nom[:28])
                continue
            d0 = datetime.datetime.utcfromtimestamp(t[0]).strftime("%Y-%m-%d")
            d1 = datetime.datetime.utcfromtimestamp(t[-1]).strftime("%Y-%m-%d")
            print("   %-28s %9.0f Mo %12s  %s -> %s"
                  % (nom[:28], os.path.getsize(c) / 1048576.0,
                     humain(len(t)), d0, d1))
        print("  " + "-" * 78)
        print("")
        print("  Relance avec --fichier <chemin> pour balayer les echelles.")
        return 0

    for chemin in a.fichier:
        print("")
        print(SEP)
        print("FICHIER : %s" % os.path.basename(chemin))
        print(SEP)
        d, err = lit_scid(chemin)
        if d is None:
            print("  %s" % err)
            continue
        t, p_, v, b, aa, mode, taille = d
        if not len(t):
            print("  fichier vide")
            continue
        fin = t[-1]
        debut = fin - a.jours * 86400
        i0 = 0
        for i in range(len(t) - 1, -1, -1):
            if t[i] < debut:
                i0 = i + 1
                break
        if len(t) - i0 > a.maxi:
            i0 = len(t) - a.maxi
        pp = p_[i0:]
        bb = b[i0:]
        ab = aa[i0:]
        tt = t[i0:]
        vv = v[i0:]
        print("")
        print("  %s ticks au total, %s retenus (%d derniers jours, plafond %s)"
              % (humain(len(t)), humain(len(pp)), a.jours, humain(a.maxi)))
        print("  du %s au %s"
              % (datetime.datetime.utcfromtimestamp(tt[0]).strftime("%Y-%m-%d %H:%M"),
                 datetime.datetime.utcfromtimestamp(tt[-1]).strftime("%Y-%m-%d %H:%M")))
        print("  volume total %s contrats" % humain(sum(v[i0:])))
        dd = deltas(bb, ab)
        bloc_balayage(pp, dd, ECHELLES, a.melanges, rng)
        bloc_absorption(tt, pp, dd, vv, ECHELLES, a.melanges, rng,
                        a.combien)

    print("")
    print(SEP)
    print(" Lecture seule. Aucun fichier ecrit, aucun ordre envoye.")
    print(SEP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
