# -*- coding: utf-8 -*-
r"""
breakout_qualifie.py -- quand un niveau cede, qu est-ce qui suit ?

  python breakout_qualifie.py --schema
  python breakout_qualifie.py
  python breakout_qualifie.py --tirages 1000

L EVENEMENT, DEFINI AVANT D AVOIR REGARDE QUOI QUE CE SOIT

    A chaque cycle, la stack publie pour chaque actif le niveau le plus
    proche au-dessus (`nearest_top`) et en dessous (`nearest_bot`),
    avec leur distance et leur nombre de TENUES.

    Une CASSURE HAUSSIERE au cycle i, c est :

        bid[i-1] <= haut_prix[i-1]   et   bid[i] > haut_prix[i-1]

    -- le prix passe au-dessus du niveau que la stack designait comme
    resistance au cycle precedent. Symetriquement pour la baisse.

    Le niveau est celui d AVANT le franchissement, jamais celui d
    apres : apres la cassure, `nearest_top` designe deja le niveau
    suivant. Utiliser celui d apres serait relire l evenement dans son
    propre miroir.

    On ne definit AUCUNE notion nouvelle : le range, le niveau et le
    compte de tenues sont ceux du moteur.

LA CONTINUATION

    A l horizon H cycles, la cassure a CONTINUE si le prix est encore
    au-dela du niveau franchi. Sinon elle a echoue -- le prix est
    revenu dans le range.

LE PIEGE QUE CE SCRIPT EXISTE POUR EVITER

    "78 % des cassures continuent a 20 cycles" ne veut rien dire tant
    qu on ne sait pas ce que vaut ce chiffre SANS cassure. Un prix qui
    vient de monter a une probabilite non triviale d etre encore haut
    vingt cycles plus tard, par simple persistance.

    On calcule donc un TEMOIN APPARIE : les cycles ou le prix est
    PROCHE du niveau (a moins de --proche fois la distance mediane)
    mais ne le franchit PAS. Meme actif, meme journee, meme voisinage
    du niveau. La difference entre les deux taux est la seule chose
    qui parle.

L ENUMERATION EST CALIBREE PAR PERMUTATION

    On regarde 3 horizons x 3 tranches de tenues x 2 sens x 4 actifs
    = 72 cellules. Le maximum de 72 differences est grand meme sans
    aucun effet. On rebat donc les JOURNEES en bloc -- les cycles d une
    meme journee ne sont pas independants -- on refait toute la
    recherche, --tirages fois, et la p-valeur porte sur le MAXIMUM.

    C est la methode validee le 15/08 par cassure_par_actif.py : sur
    des donnees sans rupture, le maximum d une recherche vaut deja 1,5
    a 3.

LES DEUX QUESTIONS QUI JUSTIFIENT LE SCRIPT

    1. `fake_breakout_trap` s allume-t-il avant les cassures qui
       echouent ? La stack a un detecteur de fausse cassure ; personne
       n a jamais compte s il avait raison.

    2. Une cassure SEULE (un actif franchit, les deux autres non) se
       comporte-t-elle autrement qu une cassure conjointe ? C est la
       forme mesurable de "le Nasdaq tient pendant que les deux autres
       rendent".

Lecteur SEUL : lit les CSV de cartes\cycles\, ecrit un .txt. Aucun
ordre, aucun collecteur, aucun etat modifie.
"""
import argparse
import csv
import io
import math
import os
import random
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "cycles")
SORTIE = os.path.join("cartes", "panel_breakout.txt")
ACTIFS = ("US30", "US500", "US100")
HORIZONS = (20, 60, 180)
TENUES = ((0, 5, "0-4"), (5, 20, "5-19"), (20, 10 ** 9, "20+"))
TIRAGES = 300
GRAINE = 12345
LARG = 100

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def charge(dossier):
    """Les cycles, par journee, dans l ordre. On garde la journee comme
    unite : un evenement de fin de journee ne doit pas chercher sa
    continuation dans la journee suivante, il y a un trou de plusieurs
    heures au milieu."""
    jours = {}
    if not os.path.isdir(dossier):
        return jours
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("cycles_") or not nom.endswith(".csv"):
            continue
        j = nom[7:-4]
        lignes = []
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            for r in csv.DictReader(f, delimiter=";"):
                lignes.append(r)
        if lignes:
            jours[j] = lignes
    return jours


def evenements(jours, actif, proche):
    """Les cassures et les temoins, pour un actif.

    Rend deux listes de dictionnaires. Un evenement porte son jour, son
    indice dans la journee, le sens, le niveau franchi, ses tenues, et
    l etat du detecteur de fausse cassure AU MOMENT du franchissement.
    """
    p = "%s_" % actif
    cass, temo = [], []
    for j, L in jours.items():
        n = len(L)
        # la distance mediane au niveau, pour definir "proche" sur cet
        # actif et cette journee -- un seuil en points serait absurde
        # entre un indice a 7 800 et un autre a 53 700.
        ds = [flt(r.get(p + "haut_dist")) for r in L]
        ds = sorted(x for x in ds if x is not None and x > 0)
        med = ds[len(ds) // 2] if ds else None
        if not med:
            continue
        for i in range(1, n):
            av, ap = L[i - 1], L[i]
            b0, b1 = flt(av.get(p + "bid")), flt(ap.get(p + "bid"))
            if b0 is None or b1 is None:
                continue
            for sens, cle, cmp0, cmp1 in (
                    ("HAUT", "haut", lambda b, v: b <= v,
                     lambda b, v: b > v),
                    ("BAS", "bas", lambda b, v: b >= v,
                     lambda b, v: b < v)):
                niv = flt(av.get(p + cle + "_prix"))
                if niv is None or niv <= 0:
                    continue
                ten = flt(av.get(p + cle + "_tenues")) or 0
                base = {"jour": j, "i": i, "sens": sens, "niveau": niv,
                        "tenues": int(ten),
                        "piege": (av.get(p + "piege_niv") or "").strip(),
                        "canal": (av.get(p + "fr_canal") or "").strip(),
                        "align": (av.get("alignment") or "").strip()}
                if cmp0(b0, niv) and cmp1(b1, niv):
                    cass.append(base)
                elif abs(b0 - niv) <= proche * med and cmp0(b0, niv):
                    temo.append(base)
    return cass, temo


def continue_(jours, actif, ev, h):
    """Le prix est-il encore au-dela du niveau, h cycles plus tard ?
    Rend None si la journee s arrete avant -- un evenement tronque ne
    compte ni en reussite ni en echec."""
    L = jours[ev["jour"]]
    k = ev["i"] + h
    if k >= len(L):
        return None
    b = flt(L[k].get("%s_bid" % actif))
    if b is None:
        return None
    return (b > ev["niveau"]) if ev["sens"] == "HAUT" else (b < ev["niveau"])


def taux(jours, actif, lot, h):
    ok = tot = 0
    for ev in lot:
        r = continue_(jours, actif, ev, h)
        if r is None:
            continue
        tot += 1
        ok += 1 if r else 0
    return (ok, tot, (100.0 * ok / tot) if tot else None)


def grille(jours, actifs, cass, temo, a):
    """Le tableau principal : par actif, sens, tranche de tenues et
    horizon -- le taux de continuation, celui du temoin, et l ecart."""
    out = []
    for actif in actifs:
        for sens in ("HAUT", "BAS"):
            for lo, hi, eti in TENUES:
                c = [e for e in cass[actif]
                     if e["sens"] == sens and lo <= e["tenues"] < hi]
                t = [e for e in temo[actif]
                     if e["sens"] == sens and lo <= e["tenues"] < hi]
                for h in HORIZONS:
                    ok, n, tc = taux(jours, actif, c, h)
                    ok2, n2, tt = taux(jours, actif, t, h)
                    if tc is None or tt is None:
                        continue
                    if n < a.min_n or n2 < a.min_n:
                        continue
                    out.append({"actif": actif, "sens": sens, "ten": eti,
                                "h": h, "n": n, "taux": tc, "n_t": n2,
                                "temoin": tt, "ecart": tc - tt})
    return out


def permute(jours, actifs, a, alea):
    """La distribution du maximum d ecart SOUS L HYPOTHESE QU UNE
    CASSURE NE CHANGE RIEN.

    On rebat l ordre des JOURNEES et on refait toute la recherche. Les
    evenements gardent leur structure interne ; ce qui change, c est la
    journee dans laquelle on va chercher la continuation."""
    noms = list(jours.keys())
    maxs = []
    for _ in range(a.tirages):
        melange = list(noms)
        alea.shuffle(melange)
        corr = dict((noms[k], jours[melange[k]]) for k in range(len(noms)))
        cass, temo = {}, {}
        for actif in ACTIFS:
            c, t = evenements(jours, actif, a.proche)
            # on garde les evenements, mais on va chercher la suite
            # dans une AUTRE journee : c est ca, l hypothese nulle.
            cass[actif], temo[actif] = c, t
        g = grille(corr, ACTIFS, cass, temo, a)
        maxs.append(max((abs(x["ecart"]) for x in g), default=0.0))
    return sorted(maxs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--proche", type=float, default=1.0,
                   help="temoin : distance au niveau, en medianes")
    p.add_argument("--min-n", type=int, default=30, dest="min_n")
    p.add_argument("--tirages", type=int, default=TIRAGES)
    p.add_argument("--graine", type=int, default=GRAINE)
    p.add_argument("--schema", action="store_true")
    a = p.parse_args()

    jours = charge(a.entree)
    if not jours:
        print("KO : aucun CSV dans %s." % a.entree)
        print("     Lance d abord : python extraire_cycles.py")
        return 1
    ncyc = sum(len(v) for v in jours.values())

    # le pas de temps reel, pour que les horizons soient lisibles
    pas = []
    for L in jours.values():
        for k in range(1, min(len(L), 200)):
            try:
                t0 = dt.datetime.strptime(L[k - 1]["ts"][:19],
                                          "%Y-%m-%d %H:%M:%S")
                t1 = dt.datetime.strptime(L[k]["ts"][:19],
                                          "%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError, TypeError):
                continue
            d = (t1 - t0).total_seconds()
            if 0 < d < 600:
                pas.append(d)
    pas.sort()
    med_pas = pas[len(pas) // 2] if pas else 0.0

    alea = random.Random(a.graine)
    cass, temo = {}, {}
    for actif in ACTIFS:
        cass[actif], temo[actif] = evenements(jours, actif, a.proche)

    if a.schema:
        print("%d journees, %d cycles." % (len(jours), ncyc))
        print("pas median : %.0f s -> horizons %s cycles = %s"
              % (med_pas, list(HORIZONS),
                 ", ".join("%.0f min" % (h * med_pas / 60.0)
                           for h in HORIZONS)))
        for actif in ACTIFS:
            h = sum(1 for e in cass[actif] if e["sens"] == "HAUT")
            b = len(cass[actif]) - h
            print("  %-6s %5d cassures (%d haut, %d bas), %5d temoins"
                  % (actif, len(cass[actif]), h, b, len(temo[actif])))
        return 0

    dis("=" * LARG)
    dis("QUAND UN NIVEAU CEDE, QU EST-CE QUI SUIT ?")
    dis("=" * LARG)
    dis("  %d journees, %d cycles, pas median %.0f s."
        % (len(jours), ncyc, med_pas))
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
    dis("  CASSURE : le prix franchit le niveau que la stack designait")
    dis("  comme le plus proche AU CYCLE PRECEDENT. Le niveau d apres")
    dis("  serait deja le suivant -- le relire serait circulaire.")
    dis()
    dis("  TEMOIN : les cycles ou le prix est a moins de %.1f distance"
        % a.proche)
    dis("  mediane du niveau et ne le franchit PAS. Meme actif, meme")
    dis("  journee, meme voisinage. Sans lui, on mesurerait la simple")
    dis("  persistance du prix et on l appellerait continuation.")
    dis()
    dis("  Horizons : %s cycles, soit %s."
        % (", ".join(str(h) for h in HORIZONS),
           ", ".join("%.0f min" % (h * med_pas / 60.0) for h in HORIZONS)))
    dis("=" * LARG)

    for actif in ACTIFS:
        h = sum(1 for e in cass[actif] if e["sens"] == "HAUT")
        dis("  %-6s %5d cassures (%d haut, %d bas), %5d temoins"
            % (actif, len(cass[actif]), h, len(cass[actif]) - h,
               len(temo[actif])))

    g = grille(jours, ACTIFS, cass, temo, a)
    if not g:
        dis()
        dis("  Aucune cellule n atteint %d evenements. Rien n est"
            " mesurable." % a.min_n)
        io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO))
        return 0

    dis()
    dis("-" * LARG)
    dis("  %-6s %-4s %-6s %4s  %6s %7s  %6s %7s  %8s"
        % ("actif", "sens", "tenues", "h", "n", "continue", "n tem",
           "temoin", "ecart"))
    dis("-" * LARG)
    for x in sorted(g, key=lambda y: -y["ecart"]):
        dis("  %-6s %-4s %-6s %4d  %6d %6.1f%%  %6d %6.1f%%  %+7.1f pts"
            % (x["actif"], x["sens"], x["ten"], x["h"], x["n"], x["taux"],
               x["n_t"], x["temoin"], x["ecart"]))

    obs = max(abs(x["ecart"]) for x in g)
    dis()
    dis("  Permutation : %d tirages, journees rebattues en bloc."
        % a.tirages)
    nul = permute(jours, ACTIFS, a, alea)
    au = sum(1 for x in nul if x >= obs - 1e-12)
    pv = (au + 1.0) / (a.tirages + 1.0)
    dis("    ecart maximum observe   : %.1f points" % obs)
    dis("    maximum median sous H0  : %.1f points" % nul[len(nul) // 2])
    dis("    seuil 95%% sous H0       : %.1f points"
        % nul[int(0.95 * len(nul))])
    dis("    p-valeur                : %.3f" % pv)
    dis()
    if pv <= 0.05:
        dis("  => Le meilleur ecart depasse ce qu on obtient en cherchant")
        dis("     dans du bruit de meme structure (p = %.3f)." % pv)
        dis("     C est un CANDIDAT a ecrire dans HYPOTHESES.md, pas une")
        dis("     regle : la cellule a ete choisie parmi %d." % len(g))
    else:
        dis("  => RIEN NE SE DETACHE (p = %.3f). Le meilleur ecart est du"
            % pv)
        dis("     meme ordre que celui qu on trouve en rebattant les")
        dis("     journees. Une cassure, telle qu on vient de la definir,")
        dis("     ne dit rien de plus sur la suite que la simple presence")
        dis("     du prix au voisinage du niveau.")

    # --- le detecteur de fausse cassure de la stack -------------------
    dis()
    dis("=" * LARG)
    dis("LE DETECTEUR DE FAUSSE CASSURE AVAIT-IL RAISON ?")
    dis("=" * LARG)
    dis("  `fake_breakout_trap.level` au moment du franchissement, croise")
    dis("  avec ce qui a suivi. La stack calcule ce champ depuis des")
    dis("  mois ; c est la premiere fois qu on le compte.")
    dis()
    niveaux = sorted(set(e["piege"] for actif in ACTIFS
                         for e in cass[actif] if e["piege"]))
    dis("  %-8s %-10s %6s %8s" % ("piege", "horizon", "n", "continue"))
    for niv in niveaux:
        for h in HORIZONS:
            lot = [(actif, e) for actif in ACTIFS
                   for e in cass[actif] if e["piege"] == niv]
            ok = tot = 0
            for actif, e in lot:
                r = continue_(jours, actif, e, h)
                if r is None:
                    continue
                tot += 1
                ok += 1 if r else 0
            if tot >= a.min_n:
                dis("  %-8s %-10d %6d %7.1f%%"
                    % (niv, h, tot, 100.0 * ok / tot))
    dis()
    dis("  Si les taux sont les memes quel que soit le niveau du piege,")
    dis("  le detecteur n apporte rien a cette question-la. Ce ne serait")
    dis("  pas un defaut du detecteur : il a peut-etre ete concu pour")
    dis("  autre chose que predire la continuation d une cassure de")
    dis("  `nearest_top`. Le dire, et ne pas conclure au-dela.")

    # --- cassure seule contre cassure conjointe -----------------------
    dis()
    dis("=" * LARG)
    dis("UNE CASSURE SEULE VAUT-ELLE UNE CASSURE CONJOINTE ?")
    dis("=" * LARG)
    dis("  Un actif franchit son niveau. Au meme cycle, combien des deux")
    dis("  autres franchissent aussi le leur ? C est la forme mesurable")
    dis("  de \"le Nasdaq tient pendant que les deux autres rendent\".")
    dis()
    index = {}
    for actif in ACTIFS:
        for e in cass[actif]:
            index.setdefault((e["jour"], e["i"], e["sens"]), set()).add(actif)
    dis("  %-8s %-10s %6s %8s" % ("compagnie", "horizon", "n", "continue"))
    for combien, eti in ((1, "seule"), (2, "a deux"), (3, "les trois")):
        for h in HORIZONS:
            ok = tot = 0
            for actif in ACTIFS:
                for e in cass[actif]:
                    cle = (e["jour"], e["i"], e["sens"])
                    if len(index.get(cle, ())) != combien:
                        continue
                    r = continue_(jours, actif, e, h)
                    if r is None:
                        continue
                    tot += 1
                    ok += 1 if r else 0
            if tot >= a.min_n:
                dis("  %-8s %-10d %6d %7.1f%%"
                    % (eti, h, tot, 100.0 * ok / tot))
    dis()
    dis("  ATTENTION : \"au meme cycle\" est une coincidence a 17 secondes")
    dis("  pres, pas une simultaneite economique. Deux actifs qui cassent")
    dis("  a une minute d intervalle comptent ici comme separes. C est")
    dis("  une definition parmi d autres, et elle est ecrite ici pour")
    dis("  pouvoir etre changee en connaissance de cause.")

    dis()
    dis("=" * LARG)
    dis("  Tout ce tableau a ete ENUMERE, pas annonce d avance. Une")
    dis("  cellule qui se detache est un candidat a pre-enregistrer et a")
    dis("  mesurer sur des journees neuves -- jamais une regle.")
    dis("  Et rien ici ne dit quoi acheter : il n y a aucune direction")
    dis("  dans ces colonnes, seulement des taux de continuation.")

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (a.sortie, os.path.getsize(a.sortie)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
