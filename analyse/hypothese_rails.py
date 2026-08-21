#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hypothese_rails.py -- HYPOTHESES GELEES LE 20/08/2026, AVANT MESURE.
                      v3 : seuil strict, et controle contre le meme sens.

LECTEUR SEUL. N ECRIT RIEN.

  python hypothese_rails.py
  python hypothese_rails.py --sortie mfe_pts --mini 25

L ENONCE, MOT POUR MOT

    premier jet :
    "il faut que les deux rails rsi en m3 ou m5 soit au dessus du 50
     et que le rsi close sous ses rails pour qu on appercoive un gain
     potentiel"

    precise ensuite :
    "deux rails rsi en m3 ou m5 au dessus du niveau 50 avec un rsi m3
     ou m5 identique au rail qui close sous les rails + qui close sous
     le level50, la on a un reverse qui peut produire [...] essaie la
     close sous les rails + la close sous le lvl50 peut etre que ce
     sera d autant mieux"

    le controle, du meme auteur :
    "rsi rails au dessus des 50 avec le rsi qui close en dessous en r1
     ca ne veut rien dire, ca peut etre du bruit"

    gele mais NON TESTE ici, faute de donnees :
    "le m1 peut servir a reprendre sur un pullback sur une ma 50 100
     sur le mouvement precedent" -- les moyennes mobiles ne sont pas
     dans le journal.

CE QUI A CHANGE EN v3

    1. Le critere du meme signe dans les deux moities etait TROP
       FAIBLE : la v2 en retenait 17 sur 24. Sur du bruit pur, la
       moitie des tests passe deja ce filtre. Il faut desormais le
       meme signe ET au moins --seuil points dans la PIRE moitie.

    2. La periode est une baisse de trois semaines. Un reversal
       baissier qui marche pendant que son miroir haussier echoue a
       une explication plus simple que la regle : vendre marchait.
       Comparer a TOUTES les entrees ne separe pas les deux. La v3
       compare donc aussi la regle aux entrees DU MEME SENS sur la
       MEME moitie -- si les ventes ordinaires font deja autant, la
       regle ne fait que detecter la tendance.

CE QUI EST TESTE

    Par unite de temps, et TOUJOURS sur la meme unite pour toutes les
    conditions, trois marches d une meme echelle :

      1. rails seuls        rails_pos = BOTH>50
      2. + RSI sous rails   ... ET rsi_pos = BELOW
      3. + RSI sous 50      ... ET rsi < 50

    Si l enonce est juste, la marche 1 est plate et chaque marche
    suivante ameliore. Si la marche 3 n apporte rien sur la 2, la
    condition du niveau 50 est inutile et il faut le dire.

    Et la symetrique haussiere, gelee le meme jour pour ne pas la
    declarer apres coup : BOTH<50, ABOVE, rsi > 50.

UNITES DISPONIBLES

    M1, M3, M5, M15. rails_entry ne capture PAS H1 : la demande le
    mentionnait, la donnee n existe pas.

LA DISCIPLINE

    Tout est mesure DEUX FOIS, sur la premiere moitie de la periode
    et sur la seconde, decoupees par date. Un effet qui ne va pas
    dans le meme sens des deux cotes est du bruit, et il est ecarte.

    Attention : ce script fait 24 tests. Plus on en fait, plus il est
    probable que l un passe le filtre par chance. Le nombre est
    rappele en fin de sortie, et c est a lire avant de se rejouir.

CE QUE CA NE DIT PAS

    Le resultat est celui du moteur churn, pas d une strategie qui
    entrerait sur cet etat. L entree du churn n est pas celle qu on
    prendrait sur un reversal : deux strategies qui entrent a des
    instants differents sur le meme etat n ont aucune raison de faire
    le meme resultat. Ce qui est mesure ici est un FILTRE candidat.
"""

import argparse
import gzip
import io
import json
import math
import os
import sys

SEP = "=" * 108
DEFAUT = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
UNITES = ("M1", "M3", "M5", "M15")


def ouvre(c):
    if c.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(c, "rb"), encoding="utf-8",
                               errors="replace")
    return io.open(c, encoding="utf-8", errors="replace")


def lit(base, actif):
    out = []
    for c in (base, base + ".gz"):
        if not os.path.isfile(c):
            continue
        with ouvre(c) as f:
            for l in f:
                l = l.strip()
                if not l:
                    continue
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if isinstance(o, dict) and o.get("asset") == actif:
                    out.append(o)
    return out


def champ(t, actif, tf, cle):
    """Un champ des rails de l ACTIF TRADE sur CETTE unite de temps.

    rails_entry[actif][tf][cle], et a defaut le champ a plat
    rails_pos_m5 / rsi_pos_m5 -- le journal porte les deux formes.
    """
    d = ((t.get("rails_entry") or {}).get(actif) or {}).get(tf)
    if isinstance(d, dict) and d.get(cle) is not None:
        return d.get(cle)
    return t.get("%s_%s" % (cle, tf.lower()))


def marches(t, actif, tf, hausse):
    """(rails seuls, + RSI du bon cote, + RSI franchit 50).

    Les trois conditions portent sur LA MEME unite de temps : c est
    l enonce, "un rsi m3 ou m5 IDENTIQUE au rail".
    """
    pos_voulu = "BOTH<50" if hausse else "BOTH>50"
    rsi_voulu = "ABOVE" if hausse else "BELOW"
    un = champ(t, actif, tf, "rails_pos") == pos_voulu
    if not un:
        return False, False, False
    deux = champ(t, actif, tf, "rsi_pos") == rsi_voulu
    if not deux:
        return True, False, False
    r = champ(t, actif, tf, "rsi")
    if not isinstance(r, (int, float)):
        return True, True, False
    trois = (r > 50) if hausse else (r < 50)
    return True, True, bool(trois)


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def wilson_bas(s, n, z=1.96):
    if n == 0:
        return 0.0
    p = s / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    e = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - e) / d


def juge(lot, sortie):
    v = [t.get(sortie) for t in lot]
    v = [x for x in v if isinstance(x, (int, float))]
    if not v:
        return 0, 0.0, 0.0, 0.0
    g = sum(1 for x in v if x > 0)
    return len(v), g / float(len(v)), wilson_bas(g, len(v)), mediane(v)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=DEFAUT)
    p.add_argument("--actif", default="US30")
    p.add_argument("--sortie", default="pnl_eur",
                   choices=("pnl_eur", "mfe_pts", "mae_pts"))
    p.add_argument("--mini", type=int, default=20)
    p.add_argument("--parts", type=int, default=2,
                   help="nombre de periodes egales. 2 = deux moities. 4 "
                        "separe un avantage constant d un avantage qui n a "
                        "vecu qu un seul quart.")
    p.add_argument("--seuil", type=float, default=5.0,
                   help="points minimum dans la PIRE moitie pour qu un "
                        "resultat soit retenu. Le seul critere du meme "
                        "signe est trop faible : sur du bruit, la moitie "
                        "des tests le passe deja.")
    a = p.parse_args()

    print(SEP)
    print("HYPOTHESES RAILS -- GELEES LE 20/08/2026, AVANT MESURE")
    print(SEP)
    print()
    print("  Lecture seule. Rien n est ecrit, rien n est envoye.")
    print()

    if not (os.path.isfile(a.fichier) or os.path.isfile(a.fichier + ".gz")):
        print("  FICHIER INTROUVABLE : %s" % a.fichier)
        print()
        print("  Le chemin est RELATIF au dossier courant, qui est :")
        print("    %s" % os.getcwd())
        print()
        print("  Place-toi dans le dossier de la stack, ou donne le chemin")
        print("  complet avec --fichier. Dire '0 ticket' au lieu de ca")
        print("  aura coute deux allers-retours : c est repare.")
        return

    tickets = lit(a.fichier, a.actif)
    tickets = [t for t in tickets
               if isinstance(t.get(a.sortie), (int, float))
               and isinstance(t.get("entry_ts"), str)]
    if len(tickets) < 4 * a.mini:
        print("  %d ticket(s) exploitables sur %s : trop peu."
              % (len(tickets), a.actif))
        return
    tickets.sort(key=lambda t: t["entry_ts"])
    k = max(2, a.parts)
    taille = len(tickets) // k
    parts = [tickets[i * taille:(i + 1) * taille if i < k - 1 else None]
             for i in range(k)]
    refs = [juge(p, a.sortie)[1] for p in parts]

    print("  %d ticket(s) %s, sortie jugee : %s"
          % (len(tickets), a.actif, a.sortie))
    for i, p in enumerate(parts):
        n, r, _w, m = juge(p, a.sortie)
        print("  periode %d : %s -> %s   n=%4d   %.1f %% gagnants"
              "   median %+.2f"
              % (i + 1, p[0]["entry_ts"][:10], p[-1]["entry_ts"][:10],
                 n, 100 * r, m))
    print()
    print("  Les ecarts sont toujours calcules contre la reference de LA")
    print("  MEME periode, jamais contre l ensemble.")
    if k > 2:
        print()
        print("  Avec %d periodes, un avantage n est RETENU que s il va" % k)
        print("  dans le meme sens dans TOUTES. Un avantage qui n a vecu")
        print("  qu une periode se voit alors, ce que deux moities ne")
        print("  savaient pas separer.")
    print()

    ac = a.actif
    tests = 0
    tenus = []

    for hausse, titre, enonce in (
            (False, "REVERSAL BAISSIER -- l enonce",
             "rails au-dessus de 50, RSI qui close dessous, puis sous 50"),
            (True, "REVERSAL HAUSSIER -- symetrique, gelee le meme jour",
             "rails sous 50, RSI qui close dessus, puis au-dessus de 50")):
        print(SEP)
        print(titre)
        print(SEP)
        print()
        print("  %s" % enonce)
        print()
        entete = "   unite  condition             "
        for i in range(k):
            entete += "  periode %d      " % (i + 1)
        print(entete + " verdict")
        print("   " + "-" * (44 + 17 * k))
        for tf in UNITES:
            for rang, nom in ((0, "rails seuls"),
                              (1, "+ RSI du bon cote"),
                              (2, "+ RSI franchit 50")):
                lots = [[t for t in p if marches(t, ac, tf, hausse)[rang]]
                        for p in parts]
                res = [juge(l, a.sortie) for l in lots]
                if any(r[0] < a.mini for r in res):
                    faibles = ", ".join("p%d n=%d" % (i + 1, r[0])
                                        for i, r in enumerate(res)
                                        if r[0] < a.mini)
                    print("   %-6s %-22s  sous le seuil de %d : %s"
                          % (tf, nom, a.mini, faibles))
                    continue
                tests += 1
                ecarts = [res[i][1] - refs[i] for i in range(k)]
                memes = all(e > 0 for e in ecarts) or all(e < 0 for e in ecarts)
                if memes:
                    pire = min(abs(e) for e in ecarts) * (1 if ecarts[0] > 0 else -1)
                    if abs(100 * pire) >= a.seuil:
                        verdict = "RETENU %+.1f" % (100 * pire)
                        tenus.append((abs(pire), tf, nom, titre[:17], pire,
                                      res[0][0], res[-1][0]))
                    else:
                        verdict = "meme sens, mais %+.1f seulement" % (100 * pire)
                else:
                    verdict = "ne tient pas"
                ligne = "   %-6s %-22s" % (tf, nom)
                for i in range(k):
                    ligne += " %4d %5.1f(%+5.1f)" % (res[i][0], 100 * res[i][1],
                                                     100 * ecarts[i])
                print(ligne + "  " + verdict)
            print()

    print(SEP)
    print("LE CONTROLE QUI TRANCHE -- contre le MEME SENS, pas contre tout")
    print(SEP)
    print()
    print("  La periode est une baisse de trois semaines. Un reversal")
    print("  baissier qui marche pendant que son miroir haussier echoue")
    print("  a une explication plus simple que la regle : VENDRE marchait,")
    print("  acheter non.")
    print()
    print("  Comparer la regle a TOUTES les entrees ne separe pas les deux.")
    print("  La seule comparaison honnete est contre les entrees DU MEME")
    print("  SENS sur la MEME moitie. Si les ventes ordinaires font deja")
    print("  autant, la regle n apporte rien -- elle detecte la tendance.")
    print()
    for sens in ("BUY", "SELL"):
        bases = [[t for t in p if t.get("dir") == sens] for p in parts]
        rb = [juge(b, a.sortie) for b in bases]
        ligne = "  REFERENCE %-5s ORDINAIRE " % sens
        for i in range(k):
            ligne += " %4d %5.1f %%    " % (rb[i][0], 100 * rb[i][1])
        print(ligne)
        for hausse, nom in ((False, "reversal baissier"),
                            (True, "reversal haussier")):
            for tf in UNITES:
                # la marche 1 (sans le franchissement de 50) : la mesure a
                # montre que la marche 2 n apporte rien et coute un tiers
                # de l effectif.
                lots = [[t for t in bases[i]
                         if marches(t, ac, tf, hausse)[1]] for i in range(k)]
                res = [juge(l, a.sortie) for l in lots]
                if any(r[0] < a.mini for r in res):
                    continue
                gains = [res[i][1] - rb[i][1] for i in range(k)]
                memes = all(g > 0 for g in gains) or all(g < 0 for g in gains)
                pire = min(abs(g) for g in gains) * (1 if gains[0] > 0 else -1)
                if memes and abs(100 * pire) >= a.seuil:
                    v = "APPORTE %+.1f" % (100 * pire)
                elif memes:
                    v = "meme sens, %+.1f seulement" % (100 * pire)
                else:
                    v = "n apporte rien"
                l2 = "    %-18s %-4s" % (nom, tf)
                for i in range(k):
                    l2 += " %4d %5.1f(%+5.1f)" % (res[i][0], 100 * res[i][1],
                                                  100 * gains[i])
                print(l2 + "  " + v)
        print()

    print(SEP)
    print("CE QUE CA VAUT")
    print(SEP)
    print()
    print("  %d test(s) reellement effectue(s), %d retenu(s) : meme sens"
          % (tests, len(tenus)))
    print("  dans les %d periodes ET au moins %.0f points dans la pire."
          % (k, a.seuil))
    print()
    print("  Le seul critere du meme signe serait trop faible : sur du")
    print("  bruit pur, la moitie des tests le passe deja. C est pourquoi")
    print("  le seuil existe -- et pourquoi la premiere version de ce")
    print("  script en retenait 17 sur 24.")
    print()
    if tenus:
        tenus.sort(reverse=True)
        print("  Le meilleur : %s sur %s, %+.1f points dans le pire des"
              % (tenus[0][2], tenus[0][1], 100 * tenus[0][4]))
        print("  deux, n=%d et n=%d." % (tenus[0][5], tenus[0][6]))
        print()
    print("  Avec %d tests, en attendre un ou deux qui passent par pure" % tests)
    print("  chance reste NORMAL. Les deux moities eliminent les accidents")
    print("  grossiers, pas la coincidence.")
    print()
    print("  Et rien de tout cela ne vaut si le tableau du CONTROLE")
    print("  ci-dessus dit que la regle n apporte rien contre son propre")
    print("  sens : ce serait alors la tendance qu on mesure.")
    print()
    print("  La lecture qui compte n est pas le meilleur chiffre : c est")
    print("  la PROGRESSION. Si, sur une unite donnee, les rails seuls")
    print("  sont plats, que le RSI du bon cote ameliore, et que le")
    print("  franchissement de 50 ameliore encore, alors l enonce decrit")
    print("  quelque chose de reel. Un seul chiffre isole, non.")
    print()
    print("  Et si l enonce ne tient pas : il est ABANDONNE. Pas etendu")
    print("  a une autre unite, pas assoupli sur le 50. Elargir apres")
    print("  avoir vu, c est choisir la reponse.")
    print()
    print(SEP)
    print("  Rien n a ete ecrit, rien n a ete envoye.")
    print(SEP)


if __name__ == "__main__":
    main()
