# -*- coding: utf-8 -*-
r"""
survie_niveaux.py -- un niveau de bougie repere tient-il plus longtemps
                     qu un niveau ordinaire ?

  python survie_niveaux.py
  python survie_niveaux.py --symbole YM-continu --mini-dims 3

LA QUESTION, ET POURQUOI ELLE A BESOIN D UN TEMOIN

    Sur le graphique, les niveaux laisses par les bougies reperes se
    font traverser. Mais les niveaux ORDINAIRES aussi -- le prix
    revient sur ses pas, c est ce qu il fait de plus banal.

    Sans second terme, on mesure "le prix revient", qui est vrai
    partout. Avec lui, on mesure ce que la bougie repere AJOUTE.

CE QUI EST MESURE

    Pour chaque bougie repere, DEUX niveaux : son plus haut et son plus
    bas. Pour chacun :

        SURVIE = nombre de minutes jusqu a la premiere barre ulterieure
                 de la MEME seance dont l intervalle [bas, haut]
                 contient ce niveau.

    Si aucune ne le contient avant la fin de seance, la survie est
    CENSUREE : on ne sait pas combien elle aurait dure, on sait
    seulement qu elle a depasse la seance. On les compte a part au lieu
    de leur inventer une valeur.

    AUCUN PARAMETRE LIBRE. Pas de tampon, pas de tolerance, pas de
    "touche a moins de N points". Le niveau est touche quand une barre
    le contient, point. Un seuil invente ici deciderait du resultat.

LE TEMOIN

    Pour chaque repere a la minute M de la seance J, on cherche une
    bougie ORDINAIRE -- repere sur aucune dimension -- a la MEME MINUTE
    DE SEANCE, sur une AUTRE journee. Meme symbole, meme minute
    d horloge, meme facon de mesurer.

    Pourquoi la meme minute : parce que 13:30 UTC pese 18 % des reperes
    de YM (l ouverture du cash). Un temoin tire au hasard dans la
    journee comparerait l ouverture a des heures creuses, et la
    difference mesurerait l horloge.

    C est la contrainte ecrite le 18/08 dans HYPOTHESES.md, appliquee.

CE QUI SERAIT UN RESULTAT

    Les niveaux reperes survivent PLUS LONGTEMPS que les temoins, avec
    un p par permutation des JOURNEES -- pas des niveaux : deux niveaux
    d une meme seance ne sont pas deux observations independantes.

    Et la part de CENSUREES doit etre lue avec : si les reperes
    survivent surtout parce qu ils sont plus loin du prix, ce n est pas
    une propriete du repere, c est une propriete de la distance. La
    sortie affiche donc aussi la distance mediane au prix a la creation.

CE QUE CA NE DIRA PAS

    Aucun euro. Une survie en minutes n est pas un PnL : il faudrait un
    sens, un stop et des frais.

    Aucune causalite. Un niveau qui tient parce que personne ne le
    regarde et un niveau que tout le monde defend donnent la meme
    survie.

    Et rien sur le futur : cette mesure est retrospective sur 133
    seances. Sa confirmation passe par la coupe du paragraphe 10 --
    exploration sur les 2/3 anciens, confirmation sur le tiers recent.

LECTEUR SEUL.
"""
import argparse
import os
import random
import sys

import bougies_reperes as br

GRAINE = 20260818


def survie(barres, i0, niveau, fin):
    """Minutes avant qu une barre ulterieure contienne `niveau`.

    Rend (minutes, censuree). Censuree = la seance s est terminee sans
    que le niveau soit touche : on ne lui invente pas de valeur."""
    t0 = barres[i0]["t"]
    for j in range(i0 + 1, fin):
        b = barres[j]
        if b["b"] <= niveau <= b["h"]:
            return (b["t"] - t0).total_seconds() / 60.0, False
    return (barres[fin - 1]["t"] - t0).total_seconds() / 60.0, True


def p_permutation_jour(cles, va, vb, tirages, graine=GRAINE):
    """p bilaterale sur la difference des medianes, en permutant les
    JOURNEES. Deux niveaux d une meme seance voient le meme marche."""
    def ecart(a, b):
        ma, mb = br.med(a), br.med(b)
        if ma is None or mb is None:
            return None
        return ma - mb
    obs = ecart(va, vb)
    if obs is None:
        return None, None
    jours = sorted(set(cles))
    if len(jours) < 10:
        return obs, None
    al = random.Random(graine)
    tous = [(c, x, 0) for c, x in zip(cles, va)] + \
           [(c, x, 1) for c, x in zip(cles, vb)]
    pires = 0
    for _ in range(tirages):
        # On permute l etiquette repere/temoin A L INTERIEUR de chaque
        # journee : l effet de journee ne peut pas fabriquer l ecart.
        parj = {}
        for c, x, g in tous:
            parj.setdefault(c, []).append((x, g))
        a2, b2 = [], []
        for c in parj:
            v = parj[c]
            et = [g for _, g in v]
            al.shuffle(et)
            for (x, _), g in zip(v, et):
                (a2 if g == 0 else b2).append(x)
        e = ecart(a2, b2)
        if e is not None and abs(e) >= abs(obs):
            pires += 1
    return obs, (1.0 + pires) / (1.0 + tirages)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dossier", default=br.DOSSIER)
    p.add_argument("--symbole", default=None,
                   help="par defaut : tous ceux qui ont un carnet")
    p.add_argument("--centile", type=float, default=99.5)
    p.add_argument("--mini-dims", type=int, default=2,
                   help="dimensions franchies au minimum pour qu une "
                        "bougie compte comme repere")
    p.add_argument("--tirages", type=int, default=2000)
    a = p.parse_args()

    print("=" * 78)
    print("SURVIE DES NIVEAUX -- repere contre temoin apparie")
    print("=" * 78)
    print("  Repere = bougie franchissant au moins %d dimension(s) au"
          % a.mini_dims)
    print("  centile %.1f de sa seance." % a.centile)
    print()
    print("  SURVIE = minutes avant qu une barre ulterieure de la MEME")
    print("  seance contienne le niveau. Aucun tampon, aucune tolerance :")
    print("  un seuil invente ici deciderait du resultat.")
    print()
    print("  TEMOIN = bougie ORDINAIRE, meme minute de seance, autre")
    print("  journee. La meme minute parce que 13:00 UTC pese 18 % des")
    print("  reperes de YM : un temoin tire au hasard comparerait")
    print("  l ouverture du cash a des heures creuses.")
    print()

    # DEPENDANCE DECLAREE, pas supposee. Cet outil appelle
    # br.bornes(), introduite par patch_queues.py. Sans elle il
    # plantait sur un AttributeError au milieu du traitement -- une
    # trace de pile au lieu d une phrase.
    manque = [n for n in ("bornes", "dimensions", "charge", "med",
                          "sans_carnet", "DIMS")
              if not hasattr(br, n)]
    if manque:
        print("KO : bougies_reperes.py n expose pas %s."
              % ", ".join(manque))
        print("     Il faut lui appliquer patch_queues.py, puis")
        print("     patch_bornes.py, avant d utiliser cet outil.")
        return 1

    barres, msg = br.charge(a.dossier)
    for m in msg:
        print(m)
    for sym, r in br.sans_carnet(barres):
        print("  %-16s ECARTE : %s" % (sym, r))
    syms = [a.symbole] if a.symbole else sorted(barres)
    for sym in syms:
        if sym not in barres:
            print("KO : %s absent." % sym)
            return 1
    print()

    for sym in syms:
        serie = barres[sym]
        jours = {}
        for b in serie:
            jours.setdefault(b["t"].date(), []).append(b)
        cpt = sorted(len(v) for v in jours.values())
        seuil_j = max(30, (cpt[len(cpt) // 2] if cpt else 0) // 2)
        mtr = [br.med([x["n"] for x in v]) or 0.0 for v in jours.values()]
        seuil_tr = (br.med(mtr) or 0.0) / 2.0

        # --- reperes et ordinaires, par minute d horloge -------------
        reperes, ordinaires, retenues = [], {}, 0
        for jour in sorted(jours):
            j = sorted(jours[jour], key=lambda x: x["t"])
            if len(j) < seuil_j:
                continue
            if (br.med([x["n"] for x in j]) or 0.0) < seuil_tr:
                continue
            retenues += 1
            br.dimensions(j)
            res = br.bornes(j, a.centile)
            haut, bas = res[0], res[1]
            for i, b in enumerate(j):
                q = 0
                for d in br.DIMS:
                    if haut[d] is not None and b[d] >= haut[d]:
                        q += 1
                    elif bas[d] is not None and b[d] <= bas[d]:
                        q += 1
                mn = b["t"].hour * 60 + b["t"].minute
                if q >= a.mini_dims:
                    reperes.append((jour, i, j, mn))
                elif q == 0:
                    ordinaires.setdefault(mn, []).append((jour, i, j))

        print("  %-16s %d seance(s), %d repere(s) a >= %d dimension(s)"
              % (sym, retenues, len(reperes), a.mini_dims))
        if len(reperes) < 40:
            print("  %-16s trop peu de reperes : rien n est teste." % "")
            print()
            continue

        # --- survies ------------------------------------------------
        al = random.Random(GRAINE)
        cles, sr, st = [], [], []
        cens_r = cens_t = 0
        dist_r, dist_t = [], []
        sans_temoin = 0
        for jour, i, j, mn in reperes:
            cand = [x for x in ordinaires.get(mn, []) if x[0] != jour]
            if not cand:
                sans_temoin += 1
                continue
            jt, it, jjt = cand[al.randrange(len(cand))]
            for niv, ref in (("h", j[i]["h"]), ("b", j[i]["b"])):
                s1, c1 = survie(j, i, ref, len(j))
                autre = jjt[it]["h"] if niv == "h" else jjt[it]["b"]
                s2, c2 = survie(jjt, it, autre, len(jjt))
                cles.append(jour)
                sr.append(s1)
                st.append(s2)
                cens_r += 1 if c1 else 0
                cens_t += 1 if c2 else 0
                dist_r.append(abs(ref - j[i]["c"]))
                dist_t.append(abs(autre - jjt[it]["c"]))

        if sans_temoin:
            print("  %-16s %d repere(s) sans temoin a la meme minute, "
                  "ecarte(s)" % ("", sans_temoin))
        n = len(sr)
        if n < 60:
            print("  %-16s %d paire(s) seulement : rien n est teste." % ("", n))
            print()
            continue

        e, pv = p_permutation_jour(cles, sr, st, a.tirages)
        print()
        print("    %-22s %10s %10s" % ("", "REPERE", "TEMOIN"))
        print("    %-22s %10d %10d" % ("niveaux", n, n))
        print("    %-22s %10.1f %10.1f" % ("survie mediane (min)",
                                           br.med(sr) or 0, br.med(st) or 0))
        print("    %-22s %9.1f%% %9.1f%%" % ("censures (fin de seance)",
                                             100.0 * cens_r / n,
                                             100.0 * cens_t / n))
        print("    %-22s %10.2f %10.2f" % ("distance mediane au prix",
                                           br.med(dist_r) or 0,
                                           br.med(dist_t) or 0))
        print()
        print("    ecart des medianes : %+.1f min   p = %s"
              % (e or 0.0, ("%.4f" % pv) if pv is not None else "non teste"))
        print()
        if pv is None:
            print("    Moins de dix journees melangeables : pas de test.")
        elif pv >= 0.05:
            print("    RIEN. Sur cette definition, un niveau de bougie")
            print("    repere ne tient pas plus longtemps qu un niveau")
            print("    ordinaire pris a la meme minute de seance.")
        elif (e or 0) > 0:
            print("    Les niveaux reperes tiennent PLUS longtemps.")
            print("    A LIRE AVEC LA DISTANCE : si elle est plus grande")
            print("    aussi, la survie mesure l eloignement, pas le")
            print("    repere. Et a confirmer sur la coupe du §10 avant")
            print("    d en faire quoi que ce soit.")
        else:
            print("    Les niveaux reperes tiennent MOINS longtemps.")
            print("    Resultat inhabituel : verifier avant d y croire.")
        print()

    print("=" * 78)
    print("CE QUE CA NE DIT PAS")
    print("=" * 78)
    print("  Aucun euro : une survie en minutes n est pas un PnL.")
    print("  Aucune causalite : un niveau que personne ne regarde et un")
    print("  niveau que tout le monde defend donnent la meme survie.")
    print("  Et c est retrospectif : la confirmation passe par la coupe")
    print("  exploration/confirmation du paragraphe 10 du protocole.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
