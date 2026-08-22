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

SIMULTANE N EST PAS PREDICTIF

    Comparer le delta d une barre a la variation de CETTE MEME barre
    est une tautologie : un trade execute a l ask EST un tick haussier.
    Mesure sur le Dow : 0,365 de correlation des 1 tick, temoin 0,000,
    194 sigma -- et rien d exploitable. Ce tableau est conserve parce
    qu il repond a  y a-t-il une echelle privilegiee , mais la question
    qui se traduit en ordres est celle du tableau suivant : le delta de
    la barre t contre la variation de la barre t+1.

L ABSORPTION, ET POURQUOI C EST ELLE QU ON VEUT

    Un endroit trouble n est pas un endroit ou ca bouge : c est un
    endroit ou ca NE bouge PAS alors que ca devrait. Beaucoup de delta,
    peu de prix parcouru : quelqu un tient le niveau. Le script compte
    les barres du dernier decile de |delta| ET du premier decile de
    |variation|, puis regarde a quels PRIX elles se concentrent.

    Le temoin sert la aussi : en remelangeant les seuls deltas il y a
    toujours des barres qui remplissent les deux conditions par
    hasard. Le nombre observe ne vaut que compare a ce nombre-la.

    Deux pieges y sont desamorces : un  dernier decile  qui laisse
    passer 47 pour cent des barres ne filtre rien (les parts reelles
    sont affichees, ces lignes sont ecartees), et une concentration
    classee par delta brut designe les prix ou le marche a sejourne,
    pas les niveaux tenus (elle est corrigee du nombre de visites).

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


def quand(sec, gabarit="%Y-%m-%d %H:%M"):
    """Heure UTC lisible. utcfromtimestamp est deprecie depuis 3.12 et
    inondait la sortie d avertissements en plein milieu des tableaux."""
    return datetime.datetime.fromtimestamp(
        sec, datetime.timezone.utc).strftime(gabarit)


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
def lit_scid(chemin, derniers=None):
    """(temps, prix, vol, bid, ask, mode, taille, total).

    derniers : ne lire que les N derniers enregistrements. Les
    enregistrements sont de taille fixe et chronologiques, donc on se
    positionne directement -- inutile d analyser 31 millions de ticks
    pour n en garder 400 000. Sur MESU26 (1167 Mo) cela evite environ
    750 Mo de RAM sur une machine qui fait tourner la stack en meme
    temps. None = tout lire, comportement d origine.
    """
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

        total = (taille - te) // tr
        depart = te
        if derniers is not None and total > derniers:
            depart = te + (total - derniers) * tr
        t, p, v, b, a = array("q"), array("f"), array("I"), array("I"), array("I")
        f.seek(depart)
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
        return (t, p, v, b, a, mode, taille, total), None
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
    print("BALAYAGE D ECHELLE -- delta et prix DE LA MEME BARRE")
    print(SEP)
    print("")
    print("  ATTENTION : ce tableau mesure une relation SIMULTANEE, donc")
    print("  en grande partie mecanique -- un trade a l ask est un tick")
    print("  haussier. Il sert a reponder  y a-t-il une echelle")
    print("  privilegiee , pas  peut-on gagner de l argent . Pour ca,")
    print("  voir le tableau suivant.")
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


def decile_par_rang(v, haut, part=0.10):
    """Indices du decile par rang. N est utilise que la ou les ex aequo
    ne dominent pas -- voir la note de compte_troubles."""
    n = len(v)
    combien = max(1, int(n * part))
    ordre = sorted(range(n), key=lambda i: abs(v[i]), reverse=haut)
    return set(ordre[:combien])


def suit(dd, dp, top):
    """Gain moyen en points si on suit le flux d une barre du decile.

    On prend les barres du dernier decile de |delta|, on parie dans le
    sens du delta, et on regarde la variation de la barre SUIVANTE.
    C est la seule facon de transformer une correlation en points.
    """
    g = []
    for i in top:
        if i + 1 < len(dp):
            sens = 1.0 if dd[i] > 0 else (-1.0 if dd[i] < 0 else 0.0)
            g.append(sens * dp[i + 1])
    return (sum(g) / len(g)) if g else 0.0


def bloc_prediction(p, d, echelles, melanges, rng):
    print("")
    print(SEP)
    print("LE FLUX ANNONCE-T-IL LA BARRE SUIVANTE ?")
    print(SEP)
    print("")
    print("  Le tableau precedent comparait le delta d une barre a la")
    print("  variation de CETTE MEME barre. C est une tautologie : un")
    print("  trade execute a l ask EST un tick haussier. La correlation")
    print("  ne pouvait pas etre nulle, et elle ne rapporte rien.")
    print("")
    print("  Ici on decale d une barre : delta de la barre t contre")
    print("  variation de la barre t+1. C est la seule version de la")
    print("  question qui se traduise en ordres.")
    print("")
    print("  pts = gain moyen en points si on suit le flux des barres du")
    print("  dernier decile de |delta|. temoin = le meme calcul, deltas")
    print("  remelanges. C est  pts  moins  pts temoin  qui se gagne.")
    print("")
    print("   ticks   barres    reel   temoin    ECART   sigma"
          "      pts   pts tem")
    print("  " + "-" * 76)
    droit = list(range(len(p)))
    lignes = []
    for n in echelles:
        if len(p) // n < MINI_BARRES:
            continue
        dp, dd, _px, _dv = barres(p, d, None, n)
        if len(dp) < MINI_BARRES + 1:
            continue
        a = dd[:-1]
        b = dp[1:]
        r = pearson(a, b)
        top = decile_par_rang(dd, True)
        pts = suit(dd, dp, top)
        temoins, tpts = [], []
        for _k in range(melanges):
            melange = droit[:]
            rng.shuffle(melange)
            mdp, mdd, _m, _w = barres(p, d, None, n, perm=melange)
            temoins.append(pearson(mdd[:-1], mdp[1:]))
            tpts.append(suit(mdd, mdp, decile_par_rang(mdd, True)))
        tm = sum(temoins) / len(temoins)
        sd = ecart_type(temoins)
        ec = r - tm
        sig = (ec / sd) if sd > 0 else 0.0
        tp = sum(tpts) / len(tpts)
        print("   %5d %8d %7.3f %8.3f %8.3f %7.1f %8.3f %9.3f"
              % (n, len(dp), r, tm, ec, sig, pts, tp))
        lignes.append((abs(sig), n, ec, sig, pts - tp))
    print("  " + "-" * 76)
    print("")
    if not lignes:
        print("  Pas assez de barres.")
        return
    lignes.sort(reverse=True)
    _a, n, ec, sig, net = lignes[0]
    if sig < SEUIL_SIGMA:
        print("  AUCUNE ECHELLE N ANNONCE LA SUIVANTE. Le meilleur cas est")
        print("  %d ticks (%+.3f, %.1f sigma) et ne passe pas le seuil."
              % (n, ec, sig))
        print("")
        print("  Le flux et le prix bougent ensemble -- le tableau")
        print("  precedent le montrait -- mais le flux ne PRECEDE pas le")
        print("  prix. C est la difference entre un thermometre et une")
        print("  prevision meteo.")
        return
    print("  MEILLEURE ECHELLE : %d ticks, ecart %+.3f, %.1f sigma."
          % (n, ec, sig))
    print("  Gain net apres temoin : %+.3f point(s) par barre suivie."
          % net)
    print("")
    print("  Avant d en faire quoi que ce soit : compare ce gain au")
    print("  spread et a la commission de l actif. Un ecart significatif")
    print("  plus petit que le cout d aller-retour se perd a coup sur.")


def compte_troubles(p, d, n, vols=None, perm=None):
    """(indices, dp, dd, px, dv, seuil_d, seuil_p, part_d, part_p).

    Les seuils sont pris sur la VALEUR du quantile, ce qui inclut tous
    les ex aequo. C est voulu, et c est le seul choix correct ici.

    Decouper au RANG serait tentant -- cela garantirait pile 10 pour
    cent -- mais quand la moitie des barres sont a egalite a zero, le
    tri departage les ex aequo par ordre d apparition : on selectionne
    alors le DEBUT DU FICHIER, pas les barres les plus plates. Mesure
    au banc : la version par rang ne retrouvait que 3 des 11 niveaux
    d absorption plantes, contre 11 sur 11 par valeur.

    Le prix a payer est que les parts selectionnees ne valent plus 10
    pour cent. Elles sont donc RENDUES a l appelant : quand la part de
    |delta| approche 100 pour cent, le filtre ne filtre plus rien et le
    rapport vaut 1,00 par construction -- ce n est pas  pas
    d absorption , c est  le test n a pas pu regarder .
    """
    dp, dd, px, dv = barres(p, d, vols, n, perm=perm)
    if len(dp) < MINI_BARRES:
        return None
    sd = quantile([abs(x) for x in dd], 0.90)
    sp = quantile([abs(x) for x in dp], 0.10)
    pas_d = [i for i in range(len(dd)) if abs(dd[i]) >= sd]
    ens_p = set(i for i in range(len(dp)) if abs(dp[i]) <= sp)
    idx = [i for i in pas_d if i in ens_p]
    part_d = len(pas_d) / float(len(dd))
    part_p = len(ens_p) / float(len(dp))
    return idx, dp, dd, px, dv, sd, sp, part_d, part_p


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
    print("   ticks   barres  troubles  attendues   rapport   sigma"
          "   part d  part v")
    print("  " + "-" * 78)
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
        part_d, part_v = r[7], r[8]
        vide = part_d > 0.30
        print("   %5d %8d %9d %10.1f %9.2f %7.1f %7.0f%% %6.0f%%%s"
              % (n, len(r[1]), len(idx), att, rap, sig,
                 100 * part_d, 100 * part_v, "  <-- vide" if vide else ""))
        if not vide:
            garde.append((sig, n, idx, r, att))
    print("  " + "-" * 78)
    print("")
    print("  part d / part v : ce que les seuils laissent reellement")
    print("  passer. Un  dernier decile  qui laisse passer 47 pour cent")
    print("  des barres ne filtre rien : le rapport vaut alors 1,00 par")
    print("  construction. Ces lignes sont marquees  vide  et ecartees.")
    print("")
    if not garde:
        print("")
        print("  AUCUNE ECHELLE EXPLOITABLE : partout le seuil de |delta|")
        print("  laisse passer plus de 30 pour cent des barres, donc ne")
        print("  filtre rien. C est le cas quand les deltas sont de tres")
        print("  petits entiers avec beaucoup d ex aequo. Le test n a pas")
        print("  pu regarder -- ce n est pas une absence d absorption.")
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
    _idx, dp, dd, px, dv, seuil_d, seuil_p, _pd, _pv = r
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
        h = quand(t[j])
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

    # Concentration CORRIGEE du temps passe. Classer par delta cumule
    # brut revient a designer les prix ou le marche a sejourne : un
    # niveau visite 10 000 fois accumule plus de delta qu un niveau
    # reellement tenu visite 200 fois. On divise donc par le nombre de
    # barres passees a ce prix. Mesure au banc : la version brute
    # classait en tete des prix ou le marche avait seulement sejourne ;
    # la version /visite retrouve 11 niveaux plantes sur 11, avec une
    # separation nette (75 a 121 par visite) contre le bruit (23).
    sejour = {}
    for i in range(len(px)):
        k = round(px[i])
        sejour[k] = sejour.get(k, 0) + 1
    brut = {}
    combien_troubles = {}
    for i in idx:
        k = round(px[i])
        brut[k] = brut.get(k, 0.0) + abs(dd[i])
        combien_troubles[k] = combien_troubles.get(k, 0) + 1
    if brut:
        # Filtrer sur le nombre de barres TROUBLES, pas sur le sejour :
        # un seuil de sejour eliminerait justement les niveaux peu
        # visites, ceux que la correction est censee faire ressortir.
        # Mesure au banc : filtrer sur le sejour median ne laissait
        # passer que 3 des 11 niveaux plantes.
        TROUBLES_MINI = 5
        retenus = [(k, v) for k, v in brut.items()
                   if combien_troubles.get(k, 0) >= TROUBLES_MINI]
        print("")
        print("  Ou ca se concentre. La colonne  brut  designe surtout")
        print("  les prix ou le marche a sejourne ; la colonne  /visite")
        print("  corrige ce sejour et c est la seule a comparer entre")
        print("  niveaux. Minimum %d barres troubles pour figurer."
              % TROUBLES_MINI)
        print("")
        print("      prix     visites   troubles       brut     /visite")
        print("  " + "-" * 60)
        if not retenus:
            print("   aucun prix n atteint le minimum de barres troubles.")
        for k, v in sorted(retenus, key=lambda kv: -kv[1] / sejour[kv[0]])[:12]:
            print("   %9d %9d %10d %10.0f %11.2f"
                  % (k, sejour[k], combien_troubles.get(k, 0), v,
                     v / sejour[k]))
        print("  " + "-" * 60)


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
            d0 = quand(t[0], "%Y-%m-%d")
            d1 = quand(t[-1], "%Y-%m-%d")
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
        d, err = lit_scid(chemin, derniers=a.maxi)
        if d is None:
            print("  %s" % err)
            continue
        t, p_, v, b, aa, mode, taille, total = d
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
        print("  %s ticks dans le fichier, %s lus, %s retenus"
              % (humain(total), humain(len(t)), humain(len(pp))))
        print("  (%d derniers jours, plafond %s)"
              % (a.jours, humain(a.maxi)))
        print("  du %s au %s"
              % (quand(tt[0]), quand(tt[-1])))
        print("  volume total %s contrats" % humain(sum(v[i0:])))
        dd = deltas(bb, ab)
        bloc_balayage(pp, dd, ECHELLES, a.melanges, rng)
        bloc_prediction(pp, dd, ECHELLES, a.melanges, rng)
        bloc_absorption(tt, pp, dd, vv, ECHELLES, a.melanges, rng,
                        a.combien)

    print("")
    print(SEP)
    print(" Lecture seule. Aucun fichier ecrit, aucun ordre envoye.")
    print(SEP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
