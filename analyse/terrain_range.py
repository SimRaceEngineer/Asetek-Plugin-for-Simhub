# -*- coding: utf-8 -*-
r"""
terrain_range.py -- H37 : une fois 50 % du range repris, va-t-on aux 100 % ?

  python terrain_range.py
  python terrain_range.py --confirmation
  python terrain_range.py --symbole YM-continu --mini-dims 3

L ENONCE, GELE DANS HYPOTHESES.md AVANT CET OUTIL

  A geometrie comparable, un range de bougie repere dont le prix a
  repris la MOITIE est plus souvent repris EN ENTIER qu un range de
  bougie ordinaire dans le meme cas.

      P( RETOUR >= 100 % | RETOUR >= 50 % )

CE QUI CHANGE PAR RAPPORT AUX MESURES DU 18/08

  1. L objet est un RANGE, pas un trait. [bas, haut] de la bougie,
     hauteur R.
  2. L horizon est de DIX JOURS DE BOURSE, pas la seance. Les deux
     outils precedents censuraient a la fin de seance : l objet etait
     invisible par construction.
  3. La mesure est CONDITIONNELLE. Ce n est pas "le range est-il
     revisite" -- il l est presque toujours -- c est "sachant qu il l a
     ete a moitie, l est-il en entier".

LES DEFINITIONS, SANS PARAMETRE LIBRE

  SORTIE   premiere barre posterieure dont la CLOTURE est hors du
           range. Une cloture est une valeur unique : le sens ne peut
           pas etre ambigu, contrairement a un test sur les meches.

  RETOUR   plus grande reprise du range apres la sortie, en fraction
           de R, mesuree depuis le bord de sortie :

             sortie par le HAUT : (haut - plus bas atteint) / R
             sortie par le BAS  : (plus haut atteint - bas) / R

           0 % = le prix n est pas revenu au bord. 100 % = il a
           traverse le range entier jusqu au bord oppose.

  Les deux seuils, 50 % et 100 %, sont ceux de l enonce de
  l utilisateur. Ils ne sont pas ajustes.

LE TEMOIN

  Bougie ORDINAIRE -- repere sur aucune dimension -- a la MEME MINUTE
  DE SEANCE, un autre jour, avec SON range. Meme procedure, meme
  horizon.

  La meme minute parce que 13:00 UTC pese 18,2 % des reperes de YM.
  Un temoin tire au hasard mesurerait l horloge.

  R MEDIAN EST IMPRIME DES DEUX COTES. Le range d un repere est plus
  grand que celui d une bougie ordinaire ; si le conditionnel du
  repere l emporte uniquement parce que R est grand, ce n est pas une
  propriete du repere. C est le piege qui a tue la mesure precedente.

LA CENSURE

  Une paire ne compte que si les DEUX bougies disposent de dix
  journees de bourse posterieures dans la serie. Sinon le RETOUR est
  inconnu, pas nul.

LA COUPE DU PARAGRAPHE 10, APPLIQUEE

  Par defaut : EXPLORATION sur les deux tiers les plus anciens.
  --confirmation : le tiers le plus recent, UNE SEULE PASSE.

  Cette question n a jamais ete posee aux donnees -- aucun outil n a
  touche a un conditionnel de retracement -- donc la coupe est encore
  disponible. Elle ne l etait plus pour H36.

CE QUE CA NE DIRA PAS

  Ni euro, ni stop, ni sens d entree. "Le range se complete" ne dit ni
  en combien de temps, ni ce que le prix a fait entre-temps -- or c est
  entre-temps qu un stop se prend.

LECTEUR SEUL.
"""
import argparse
import random
import sys

import bougies_reperes as br

GRAINE = 20260818
JOURS = 10
DECLENCHE = 0.50
ABOUTIT = 1.00


def retour(seq, i0, bas, haut, fin):
    """Plus grande reprise du range apres la sortie, en fraction de R.

    Rend None si le prix n est jamais sorti du range dans la fenetre :
    il n y a alors pas de retour a mesurer."""
    R = haut - bas
    if R <= 0:
        return None
    sens = 0
    j = i0 + 1
    while j < fin:
        c = seq[j]["c"]
        if c > haut:
            sens = 1
            break
        if c < bas:
            sens = -1
            break
        j += 1
    if sens == 0:
        return None
    if sens > 0:
        pire = min(seq[k]["b"] for k in range(j, fin))
        return (haut - pire) / R
    pire = max(seq[k]["h"] for k in range(j, fin))
    return (pire - bas) / R


def cond(v):
    """P(aboutit | declenche) sur une liste de RETOUR."""
    d = [x for x in v if x >= DECLENCHE]
    if not d:
        return None, 0, 0
    a = len([x for x in d if x >= ABOUTIT])
    return float(a) / len(d), a, len(d)


def p_permutation_jour(cles, va, vb, tirages, graine=GRAINE):
    """Permutation de l etiquette repere/temoin A L INTERIEUR de chaque
    journee. Le conditionnement est recalcule APRES l echange : le
    statut declenche voyage avec l observation, pas avec l etiquette."""
    def ecart(a, b):
        ca = cond(a)[0]
        cb = cond(b)[0]
        if ca is None or cb is None:
            return None
        return ca - cb
    obs = ecart(va, vb)
    if obs is None:
        return None, None
    if len(set(cles)) < 10:
        return obs, None
    al = random.Random(graine)
    parj = {}
    for c, x, g in ([(c, x, 0) for c, x in zip(cles, va)]
                    + [(c, x, 1) for c, x in zip(cles, vb)]):
        parj.setdefault(c, []).append((x, g))
    pires = 0
    for _ in range(tirages):
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
    p.add_argument("--symbole", default=None)
    p.add_argument("--centile", type=float, default=99.5)
    p.add_argument("--mini-dims", type=int, default=2)
    p.add_argument("--tirages", type=int, default=2000)
    p.add_argument("--confirmation", action="store_true",
                   help="le tiers RECENT, une seule passe")
    a = p.parse_args()

    print("=" * 78)
    print("H37 -- LE RANGE DE LA BOUGIE REPERE COMME TERRAIN")
    print("=" * 78)
    print("  P( retour >= 100 %% | retour >= 50 %% ) sur %d jours de"
          % JOURS)
    print("  bourse, contre une bougie ordinaire de la meme minute de")
    print("  seance un autre jour, avec SON range.")
    print()
    if a.confirmation:
        print("  PHASE : CONFIRMATION -- le tiers RECENT, une seule passe.")
        print("  Ne relancer sous aucun pretexte avec d autres reglages.")
    else:
        print("  PHASE : EXPLORATION -- les deux tiers ANCIENS.")
        print("  Le tiers recent n est pas regarde.")
    print()

    manque = [n for n in ("bornes", "dimensions", "charge", "med",
                          "sans_carnet", "DIMS") if not hasattr(br, n)]
    if manque:
        print("KO : bougies_reperes.py n expose pas %s." % ", ".join(manque))
        print("     Applique patch_queues.py puis patch_bornes.py.")
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
        jours = {}
        for b in barres[sym]:
            jours.setdefault(b["t"].date(), []).append(b)
        cpt = sorted(len(v) for v in jours.values())
        seuil_j = max(30, (cpt[len(cpt) // 2] if cpt else 0) // 2)
        mtr = [br.med([x["n"] for x in v]) or 0.0 for v in jours.values()]
        seuil_tr = (br.med(mtr) or 0.0) / 2.0

        vivantes = []
        for d in sorted(jours):
            j = sorted(jours[d], key=lambda x: x["t"])
            if len(j) < seuil_j:
                continue
            if (br.med([x["n"] for x in j]) or 0.0) < seuil_tr:
                continue
            vivantes.append((d, j))

        # LA COUPE. Elle porte sur les seances RETENUES, pas sur les
        # dates du calendrier : deux tiers anciens, un tiers recent.
        coupe = (len(vivantes) * 2) // 3
        garde = vivantes[coupe:] if a.confirmation else vivantes[:coupe]
        print("  %-16s %d seance(s) vivante(s), coupe a %d -- %d retenue(s)"
              % (sym, len(vivantes), coupe, len(garde)))
        if len(garde) < 20:
            print("  %-16s trop peu de seances : rien n est teste." % "")
            print()
            continue

        # La fenetre de dix jours peut deborder de la phase : on la lit
        # dans la serie COMPLETE, sinon les dernieres seances de
        # l exploration seraient censurees pour une raison arbitraire.
        idx = {}
        for _i, (d, _j) in enumerate(vivantes):
            idx[d] = _i

        reperes, ordinaires = [], {}
        for d, j in garde:
            br.dimensions(j)
            res = br.bornes(j, a.centile)
            haut, bas = res[0], res[1]
            for i, b in enumerate(j):
                q = 0
                for dim in br.DIMS:
                    if haut[dim] is not None and b[dim] >= haut[dim]:
                        q += 1
                    elif bas[dim] is not None and b[dim] <= bas[dim]:
                        q += 1
                mn = b["t"].hour * 60 + b["t"].minute
                if q >= a.mini_dims:
                    reperes.append((d, i, mn))
                elif q == 0:
                    ordinaires.setdefault(mn, []).append((d, i))

        print("  %-16s %d repere(s) a >= %d dimension(s)"
              % ("", len(reperes), a.mini_dims))
        if len(reperes) < 40:
            print("  %-16s trop peu de reperes : rien n est teste." % "")
            print()
            continue

        def fenetre(d):
            """Les barres de la seance de d et des JOURS suivantes."""
            k = idx[d]
            if k + JOURS >= len(vivantes):
                return None
            seq = []
            for _k in range(k, k + JOURS + 1):
                seq.extend(vivantes[_k][1])
            return seq

        al = random.Random(GRAINE)
        cles, VR, VT, RR, RT = [], [], [], [], []
        sans_temoin = censure = 0
        for d, i, mn in reperes:
            cand = [x for x in ordinaires.get(mn, []) if x[0] != d]
            if not cand:
                sans_temoin += 1
                continue
            dt, it = cand[al.randrange(len(cand))]
            sr, st = fenetre(d), fenetre(dt)
            if sr is None or st is None:
                censure += 1
                continue
            br_ = sr[i]
            bt_ = st[it]
            x1 = retour(sr, i, br_["b"], br_["h"], len(sr))
            x2 = retour(st, it, bt_["b"], bt_["h"], len(st))
            if x1 is None or x2 is None:
                continue
            cles.append(d)
            VR.append(x1)
            VT.append(x2)
            RR.append(br_["h"] - br_["b"])
            RT.append(bt_["h"] - bt_["b"])

        if sans_temoin:
            print("  %-16s %d sans temoin a la meme minute" % ("", sans_temoin))
        if censure:
            print("  %-16s %d censure(s) : moins de %d jours devant"
                  % ("", censure, JOURS))
        n = len(VR)
        if n < 60:
            print("  %-16s %d paire(s) exploitables : rien n est teste."
                  % ("", n))
            print()
            continue

        cr, ar, dr = cond(VR)
        ct, at, dt2 = cond(VT)
        print()
        print("    %-26s %12s %12s" % ("", "REPERE", "TEMOIN"))
        print("    %-26s %12d %12d" % ("bougies sorties du range", n, n))
        print("    %-26s %12.2f %12.2f" % ("R median (points)",
                                           br.med(RR) or 0, br.med(RT) or 0))
        print("    %-26s %12d %12d" % ("declenchent (>= 50 %)", dr, dt2))
        print("    %-26s %12d %12d" % ("aboutissent (>= 100 %)", ar, at))
        print("    %-26s %11.1f%% %11.1f%%"
              % ("P(100 % | 50 %)", 100.0 * (cr or 0), 100.0 * (ct or 0)))
        print()
        e, pv = p_permutation_jour(cles, VR, VT, a.tirages)
        print("    ecart : %+.1f point(s) de pourcentage   p = %s"
              % (100.0 * (e or 0.0),
                 ("%.4f" % pv) if pv is not None else "non teste"))
        print()
        mr, mt = br.med(RR) or 0.0, br.med(RT) or 0.0
        if pv is None:
            print("    Moins de dix journees melangeables : pas de test.")
        elif pv >= 0.05:
            print("    RIEN sur %s. Un range de repere a moitie repris ne" % sym)
            print("    se complete pas plus souvent qu un range ordinaire.")
        elif (e or 0) > 0:
            print("    Le range du repere se complete PLUS souvent.")
            if mt > 0 and mr / mt > 1.5:
                print("    MAIS son R median vaut %.1f fois celui du temoin :"
                      % (mr / mt))
                print("    a lire comme un effet possible de taille, pas")
                print("    encore comme une propriete du repere.")
        else:
            print("    Le range du repere se complete MOINS souvent.")
            print("    Signe oppose a l enonce : pas une confirmation.")
        print()

    print("=" * 78)
    if a.confirmation:
        print("  Passe de CONFIRMATION effectuee. Quel qu en soit le")
        print("  resultat, il est definitif pour cet echantillon.")
    else:
        print("  Exploration seule. ECRIRE le resultat AVANT de lancer")
        print("  --confirmation, sans quoi la coupe ne sert a rien.")
    print("=" * 78)
    print("  Ni euro, ni stop, ni sens. Le range se complete ne dit pas")
    print("  ce que le prix a fait entre-temps -- or c est entre-temps")
    print("  qu un stop se prend.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
