#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
es_pilote.py -- l ES pilote-t-il le Dow ? Mesure du decalage.

LECTEUR SEUL. N ECRIT RIEN.

  python es_pilote.py --es "C:\\SierraChart\\Data\\MESU26-CME.scid" \\
                      --ym "C:\\SierraChart\\Data\\YMU26-CBOT.scid"
  python es_pilote.py ... --jour 2026-08-19 --heures 13:00-20:00
  python es_pilote.py ... --instant "2026-08-19 15:45" --fenetre 15

CE QUE CA TESTE, ET CE QUE CA NE TESTE PAS

    ES et YM sont correles a plus de 95 pour cent en intraday.
    Constater qu ils bougent ensemble ne prouve RIEN. La seule chose
    qui etablirait que l ES pilote, c est un DECALAGE : le delta de
    l ES doit predire le rendement du YM AVANT que celui-ci ait lieu.

    D ou trois mesures, et pas une :

      A. delta ES  ->  rendement YM, a tous les decalages
      B. delta YM  ->  rendement YM   (temoin : le YM s explique-t-il
                                       lui-meme aussi bien ?)
      C. delta ES  ->  rendement ES   (temoin : la mesure fonctionne-
                                       t-elle la ou elle doit ?)

    Si A culmine a un decalage POSITIF et depasse B, l ES devance.
    Si A culmine a zero, tout bouge ensemble et rien n est etabli.
    Si C ne culmine pas non plus, c est la mesure qui ne vaut rien,
    pas l hypothese.

    La correlation ne dit jamais la causalite. Elle peut seulement
    la refuter -- et c est deja beaucoup.

    --heures compte : la nuit, le YM ne cote quasiment pas, et des
    milliers de seaux a rendement nul diluent toutes les correlations.
"""

import argparse
import datetime
import math
import os
import struct
import sys

SEP = "=" * 96
ORIGINE = datetime.datetime(1899, 12, 30)
EN_TETE = 56
ENREG = 40
FMT = "<q4f4I"
EPOCH_US = int((ORIGINE - datetime.datetime(1970, 1, 1)).total_seconds()) * 10 ** 6


def charge(chemin, jour=None):
    """(microsecondes epoch, prix, vol, bid, ask) filtres sur un jour."""
    if not os.path.isfile(chemin):
        return None, "introuvable : %s" % chemin
    taille = os.path.getsize(chemin)
    f = open(chemin, "rb")
    try:
        e = f.read(EN_TETE)
        if len(e) < EN_TETE or e[:4] != b"SCID":
            return None, "%s : signature absente" % os.path.basename(chemin)
        te, tr = struct.unpack("<II", e[4:12])
        if te != EN_TETE or tr != ENREG:
            return None, "%s : tailles inattendues" % os.path.basename(chemin)

        f.seek(te)
        b8 = f.read(tr)[:8]
        (vi,) = struct.unpack("<q", b8)
        micro = True
        try:
            d = ORIGINE + datetime.timedelta(microseconds=vi)
            micro = datetime.datetime(1990, 1, 1) <= d <= datetime.datetime(2100, 1, 1)
        except Exception:
            micro = False
        if not micro:
            return None, "%s : encodage de date non gere" % os.path.basename(chemin)

        borne0 = borne1 = None
        if jour:
            j = datetime.datetime.strptime(jour, "%Y-%m-%d")
            borne0 = int((j - datetime.datetime(1970, 1, 1)).total_seconds()) * 10 ** 6
            borne1 = borne0 + 86400 * 10 ** 6

        T, P, V, B, A = [], [], [], [], []
        f.seek(te)
        paquet = 65536 * tr
        while True:
            bloc = f.read(paquet)
            if not bloc:
                break
            for m in struct.iter_unpack(FMT, bloc[:len(bloc) - len(bloc) % tr]):
                us = EPOCH_US + m[0]
                if borne0 is not None and not (borne0 <= us < borne1):
                    continue
                T.append(us)
                P.append(m[4])
                V.append(m[6])
                B.append(m[7])
                A.append(m[8])
            if len(bloc) < paquet:
                break
        return (T, P, V, B, A, taille), None
    finally:
        f.close()


def dernier_jour(chemin):
    """Le dernier jour present dans le fichier, sans tout charger."""
    taille = os.path.getsize(chemin)
    with open(chemin, "rb") as f:
        n = (taille - EN_TETE) // ENREG
        if n <= 0:
            return None
        f.seek(EN_TETE + (n - 1) * ENREG)
        m = struct.unpack(FMT, f.read(ENREG))
        d = datetime.datetime.fromtimestamp((EPOCH_US + m[0]) / 10 ** 6,
                                            datetime.timezone.utc)
        return d.strftime("%Y-%m-%d")


def seaux(T, P, V, B, A, pas_us):
    """Par seau : delta, volume, dernier prix. Puis le rendement."""
    if not T:
        return [], [], [], []
    d0 = (T[0] // pas_us) * pas_us
    d1 = (T[-1] // pas_us) * pas_us
    n = int((d1 - d0) // pas_us) + 1
    delta = [0.0] * n
    vol = [0.0] * n
    prix = [None] * n
    for i in range(len(T)):
        k = int((T[i] - d0) // pas_us)
        delta[k] += A[i] - B[i]
        vol[k] += V[i]
        prix[k] = P[i]
    dernier = None
    for k in range(n):
        if prix[k] is None:
            prix[k] = dernier
        else:
            dernier = prix[k]
    rend = [0.0] * n
    for k in range(1, n):
        if prix[k] is not None and prix[k - 1] is not None:
            rend[k] = prix[k] - prix[k - 1]
    return delta, vol, rend, d0


def correle(x, y, decalage):
    """Correlation de Pearson entre x(t) et y(t + decalage)."""
    n = len(x)
    if decalage >= 0:
        a = x[:n - decalage] if decalage else x
        b = y[decalage:]
    else:
        a = x[-decalage:]
        b = y[:n + decalage]
    m = min(len(a), len(b))
    if m < 30:
        return None, m
    a, b = a[:m], b[:m]
    ma = sum(a) / m
    mb = sum(b) / m
    va = sum((u - ma) ** 2 for u in a)
    vb = sum((u - mb) ** 2 for u in b)
    if va <= 0 or vb <= 0:
        return None, m
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(m))
    return cov / math.sqrt(va * vb), m


def tableau(titre, x, y, pas_ms, portee):
    print(SEP)
    print(titre)
    print(SEP)
    print()
    lignes = []
    for k in range(-portee, portee + 1):
        r, m = correle(x, y, k)
        if r is not None:
            lignes.append((k, r, m))
    if not lignes:
        print("  pas assez de points communs.")
        print()
        return None
    meilleur = max(lignes, key=lambda l: abs(l[1]))
    for k, r, m in lignes:
        barre = "#" * int(abs(r) * 50)
        signe = "  <== maximum" if k == meilleur[0] else ""
        print("   %+6d ms  r = %+7.4f  n=%6d  %s%s"
              % (k * pas_ms, r, m, barre, signe))
    print()
    k, r, m = meilleur
    if k > 0:
        sens = "le premier DEVANCE le second de %d ms" % (k * pas_ms)
    elif k < 0:
        sens = "le second devance le premier de %d ms" % (-k * pas_ms)
    else:
        sens = "SIMULTANE -- aucun decalage"
    print("  maximum : r = %+.4f a %+d ms  --  %s" % (r, k * pas_ms, sens))
    print()
    return meilleur


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--es", required=True)
    p.add_argument("--ym", required=True)
    p.add_argument("--jour")
    p.add_argument("--pas", type=int, default=250, help="taille du seau, ms")
    p.add_argument("--portee", type=int, default=12,
                   help="nombre de seaux de decalage explores de chaque cote")
    p.add_argument("--heures",
                   help="restreint aux heures UTC, ex 13:00-20:00. La nuit "
                        "le YM ne cote presque pas et des milliers de seaux "
                        "a rendement nul ecrasent les correlations.")
    p.add_argument("--instant")
    p.add_argument("--fenetre", type=int, default=10, help="minutes")
    a = p.parse_args()

    print(SEP)
    print("L ES PILOTE-T-IL LE DOW ?")
    print(SEP)
    print()
    print("  Lecture seule. Rien n est ecrit, rien n est envoye.")
    print()

    jour = a.jour
    if not jour:
        if a.instant:
            jour = a.instant[:10]
        else:
            jour = dernier_jour(a.ym)
        print("  jour non precise : %s (dernier present dans le YM)" % jour)
    print("  jour analyse : %s   seau : %d ms" % (jour, a.pas))
    print()

    es, err = charge(a.es, jour)
    if err:
        print("  %s" % err)
        return
    ym, err = charge(a.ym, jour)
    if err:
        print("  %s" % err)
        return
    print("  ES : %d enregistrement(s)   YM : %d enregistrement(s)"
          % (len(es[0]), len(ym[0])))
    if not es[0] or not ym[0]:
        print("  l un des deux n a rien ce jour-la. Choisis un autre jour.")
        return
    print()

    pas_us = a.pas * 1000
    de, ve, re, o_es = seaux(es[0], es[1], es[2], es[3], es[4], pas_us)
    dy, vy, ry, o_ym = seaux(ym[0], ym[1], ym[2], ym[3], ym[4], pas_us)

    # aligner les deux grilles sur la meme origine
    if o_es < o_ym:
        saut = int((o_ym - o_es) // pas_us)
        de, ve, re = de[saut:], ve[saut:], re[saut:]
    elif o_ym < o_es:
        saut = int((o_es - o_ym) // pas_us)
        dy, vy, ry = dy[saut:], vy[saut:], ry[saut:]
    n = min(len(de), len(dy))
    de, ve, re = de[:n], ve[:n], re[:n]
    dy, vy, ry = dy[:n], vy[:n], ry[:n]
    # apres l alignement, l origine commune est la PLUS TARDIVE des deux.
    # Prendre celle du YM sans y penser decalait tous les index de la
    # section --instant.
    origine = max(o_es, o_ym)
    debut = datetime.datetime.fromtimestamp(origine / 10 ** 6,
                                            datetime.timezone.utc)
    fin = datetime.datetime.fromtimestamp((origine + n * pas_us) / 10 ** 6,
                                          datetime.timezone.utc)
    print("  %d seau(x) alignes, soit %.1f h" % (n, n * a.pas / 3600000.0))
    print("  couverture reelle : %s -> %s UTC"
          % (debut.strftime("%Y-%m-%d %H:%M:%S"), fin.strftime("%H:%M:%S")))
    print()

    DE, RE, DY, RY = list(de), list(re), list(dy), list(ry)
    garde = None
    if a.heures:
        try:
            h0, h1 = a.heures.split("-")
            m0 = int(h0[:2]) * 60 + int(h0[3:5])
            m1 = int(h1[:2]) * 60 + int(h1[3:5])
        except (ValueError, IndexError):
            print("  --heures mal forme, attendu HH:MM-HH:MM. Ignore.")
            print()
            m0 = m1 = None
        if m0 is not None:
            garde = []
            for k in range(n):
                t = datetime.datetime.fromtimestamp(
                    (origine + k * pas_us) / 10 ** 6, datetime.timezone.utc)
                mn = t.hour * 60 + t.minute
                if (m0 <= mn < m1) if m0 <= m1 else (mn >= m0 or mn < m1):
                    garde.append(k)
            if len(garde) < 100:
                print("  la plage %s ne laisse que %d seau(x) : ignoree."
                      % (a.heures, len(garde)))
                print()
                garde = None
            else:
                de = [de[k] for k in garde]
                re = [re[k] for k in garde]
                dy = [dy[k] for k in garde]
                ry = [ry[k] for k in garde]
                print("  restreint a %s UTC : %d seau(x) sur %d, soit %.1f h"
                      % (a.heures, len(de), n, len(de) * a.pas / 3600000.0))
                print("  Les seaux ecartes sont ceux ou le YM ne cote")
                print("  quasiment pas -- leur rendement nul diluait tout.")
                print()

    A = tableau("A. DELTA ES  ->  RENDEMENT YM   (l hypothese)",
                de, ry, a.pas, a.portee)
    B = tableau("B. DELTA YM  ->  RENDEMENT YM   (temoin : le YM seul)",
                dy, ry, a.pas, a.portee)
    C = tableau("C. DELTA ES  ->  RENDEMENT ES   (temoin : la mesure)",
                de, re, a.pas, a.portee)

    print(SEP)
    print("CE QUE CA ETABLIT")
    print(SEP)
    print()
    if not (A and B and C):
        print("  une mesure au moins n a pas abouti : rien n est conclu.")
    else:
        ka, ra, _ = A
        kb, rb, _ = B
        kc, rc, _ = C
        if abs(rc) < 0.05:
            print("  Le temoin C est plat (r=%+.4f) : le delta n explique" % rc)
            print("  meme pas le rendement de son PROPRE instrument. La")
            print("  mesure ne vaut rien a ce pas de temps -- ce n est pas")
            print("  l hypothese qui est refutee, c est l outil. Essaie un")
            print("  seau plus large : --pas 1000 ou --pas 5000.")
        elif ka > 0 and abs(ra) > abs(rb):
            print("  L ES DEVANCE le YM de %d ms, et il l explique mieux"
                  % (ka * a.pas))
            print("  que le YM ne s explique lui-meme (%+.4f contre %+.4f)."
                  % (ra, rb))
            print("  C est le seul cas qui soutient ton hypothese.")
        elif ka == 0:
            print("  Le maximum est a ZERO : ES et YM bougent ENSEMBLE.")
            print("  C est ce a quoi on s attend de deux indices arbitres")
            print("  en permanence. Ca ne dit pas que l ES pilote -- ca")
            print("  dit qu on ne peut pas les separer a ce pas de temps.")
            print("  Pour trancher il faudrait descendre sous la")
            print("  milliseconde, ce que ce fichier ne permet pas.")
            if abs(rb) > abs(ra):
                print()
                print("  Et le YM s explique MIEUX par son propre flux")
                print("  (%+.4f) que par celui de l ES (%+.4f)." % (rb, ra))
                print("  L hypothese du pilotage n est pas soutenue ici.")
        elif ka < 0:
            print("  Le maximum est a %d ms : c est le YM qui devance."
                  % (ka * a.pas))
            print("  L hypothese est prise a REBOURS par la mesure.")
        else:
            print("  L ES devance de %d ms mais explique MOINS bien"
                  % (ka * a.pas))
            print("  (%+.4f) que le delta du YM lui-meme (%+.4f)." % (ra, rb))
            print("  Le decalage existe mais n apporte rien de plus.")
    print()

    # --- l instant demande -------------------------------------------------
    if a.instant:
        print(SEP)
        print("AUTOUR DE %s (UTC), +/- %d min" % (a.instant, a.fenetre))
        print(SEP)
        print()
        try:
            t0 = datetime.datetime.strptime(a.instant[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            print("  format attendu : \"AAAA-MM-JJ HH:MM\"")
            return
        if garde is not None:
            print("  --heures est actif : le deroule ci-dessous ignore ce")
            print("  filtre et repart de la serie complete.")
            print()
        c = int((t0 - datetime.datetime(1970, 1, 1)).total_seconds()) * 10 ** 6
        i0 = max(0, int((c - a.fenetre * 60 * 10 ** 6 - origine) // pas_us))
        i1 = min(n, int((c + a.fenetre * 60 * 10 ** 6 - origine) // pas_us))
        if i1 <= i0:
            print("  Cet instant n est pas couvert par le fichier.")
            print("  Plage disponible ce jour-la : %s -> %s UTC."
                  % (debut.strftime("%H:%M:%S"), fin.strftime("%H:%M:%S")))
            demande = t0.strftime("%H:%M")
            if c >= origine + n * pas_us:
                print("  %s UTC est APRES la fin des donnees : ce moment n a"
                      % demande)
                print("  pas encore ete enregistre. Choisis un jour anterieur")
                print("  avec --jour, ou une heure plus tot.")
            else:
                print("  %s UTC est AVANT le debut des donnees." % demande)
            return
        print("     heure UTC        dES     rES      dYM     rYM")
        print("     " + "-" * 60)
        pas_aff = max(1, (i1 - i0) // 60)
        for k in range(i0, i1, pas_aff):
            t = datetime.datetime.fromtimestamp((origine + k * pas_us) / 10 ** 6,
                                                datetime.timezone.utc)
            print("     %s  %+8.0f %+7.2f %+8.0f %+7.2f"
                  % (t.strftime("%H:%M:%S.%f")[:12], DE[k], RE[k], DY[k], RY[k]))
        print()
        print("  dES / dYM : delta du seau. rES / rYM : variation de prix.")
        print("  Une ligne ou dES est fort et rYM suit au seau SUIVANT")
        print("  est ce que tu cherches. Une ou les quatre bougent")
        print("  ensemble ne montre qu une chose : ils sont arbitres.")
        print()

    print(SEP)
    print("  Rien n a ete ecrit, rien n a ete envoye.")
    print(SEP)


if __name__ == "__main__":
    main()
