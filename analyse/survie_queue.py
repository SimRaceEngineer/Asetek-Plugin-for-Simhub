# -*- coding: utf-8 -*-
r"""
survie_queue.py -- H36 : a distance ANNULEE, un niveau de bougie repere
                   est-il moins souvent touche dans l heure qui suit ?

  python survie_queue.py
  python survie_queue.py --symbole YM-continu --mini-dims 3

CE QUI A CHANGE DEPUIS survie_niveaux.py, ET POURQUOI

  Le premier tour a rendu un resultat NEGATIF qui se conclut : sur MES,
  ou les deux groupes se trouvaient par chance a la meme distance du
  prix (0,75 contre 0,75), l ecart etait exactement nul. Sur YM, le
  seul ecart (+1 min, p = 0,037) arrivait avec une distance de 19
  contre 6. Le seul endroit ou une difference sortait etait le seul
  endroit ou l appariement etait desequilibre.

  Deux defauts ont ete nommes, puis GELES dans HYPOTHESES.md (H36)
  AVANT que cet outil soit ecrit. Les voici, appliques.

CORRECTION 1 -- LA DISTANCE N EST PLUS APPROCHEE, ELLE EST ANNULEE

  Apparier "au plus proche" laisserait un residu : si aucune bougie
  ordinaire de cette minute n atteint 19 points, l ecart persiste.
  On supprime le degre de liberte au lieu de le reduire.

      d              = distance du niveau repere a la cloture de SA
                       bougie
      niveau repere  = cloture_repere + d        (- d pour le bas)
      niveau temoin  = cloture_temoin + d        (- d pour le bas)

  Le niveau temoin n est plus un extreme de bougie : c est LE MEME
  ECART GEOMETRIQUE pose sur une bougie ordinaire. Les deux niveaux
  sont a distance identique par construction, et la sortie l imprime
  pour le prouver.

  Ce que ca isole : un niveau situe a d du prix est-il particulier
  parce qu une bougie repere l a produit, ou seulement parce qu il est
  a d ?

CORRECTION 2 -- UNE PROPORTION, PAS UNE MEDIANE

  La survie est un entier de minutes ; les medianes valaient 2 et 3.
  Une difference de medianes ne pouvait sortir que +0 ou +1. Et la
  mediane decrivait les trois premieres minutes -- le fait banal que
  le prix reste pres d ou il vient de passer, pas un support.

      NON TOUCHE A H = aucune barre de la meme seance ne contient le
                       niveau dans les H minutes qui suivent

  HORIZON PRIMAIRE : 60 MINUTES. Gele. 30 et 120 sont imprimes en
  robustesse et NE PORTENT AUCUN VERDICT -- sinon on paierait trois
  tests pour une question.

  CENSURE : une paire ne compte que si les DEUX seances ont encore au
  moins H minutes devant elles. Un niveau dont la seance s arrete
  avant l horizon n est pas survivant, il est inconnu.

LE TEMOIN RESTE APPARIE A LA MINUTE DE SEANCE

  13:00 UTC pese 18,2 % des reperes de YM. Un temoin tire au hasard
  dans la journee comparerait l ouverture du cash a des heures creuses
  et mesurerait l horloge.

LA REGLE DE DECISION, ECRITE AVANT LES CHIFFRES (H36)

  MES et YM tous deux p < 0,05, meme signe -> le repere ajoute quelque
                                              chose a geometrie egale.
  un seul des deux                         -> asymetrique, note tel
                                              quel.
  aucun des deux                           -> la question est CLOSE.

CE QUE CA NE DIRA PAS, MEME POSITIF

  Ni euro, ni sens, ni mecanisme. "Non touche pendant 60 minutes" ne
  dit pas qu il fallait s y opposer. Un niveau que personne ne regarde
  et un niveau defendu donnent la meme proportion.

LECTEUR SEUL.
"""
import argparse
import random
import sys

import bougies_reperes as br

GRAINE = 20260818
HORIZONS = (30, 60, 120)
PRIMAIRE = 60


def statut(jour, i0, niveau, H):
    """Rend True (non touche), False (touche), ou None (inconnu).

    None quand la seance s arrete avant l horizon : on ne compte pas un
    niveau comme survivant parce qu on a cesse de regarder."""
    t0 = jour[i0]["t"]
    if (jour[-1]["t"] - t0).total_seconds() / 60.0 < H:
        return None
    for j in range(i0 + 1, len(jour)):
        b = jour[j]
        if (b["t"] - t0).total_seconds() / 60.0 > H:
            break
        if b["b"] <= niveau <= b["h"]:
            return False
    return True


def moy(v):
    return (sum(v) / float(len(v))) if v else None


def p_permutation_jour(cles, va, vb, tirages, graine=GRAINE):
    """p bilaterale sur la difference des PROPORTIONS, en permutant
    l etiquette repere/temoin A L INTERIEUR de chaque journee : l effet
    de journee ne peut pas fabriquer l ecart."""
    def ecart(a, b):
        ma, mb = moy(a), moy(b)
        if ma is None or mb is None:
            return None
        return ma - mb
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
    a = p.parse_args()

    print("=" * 78)
    print("H36 -- NIVEAU DE REPERE, A DISTANCE ANNULEE, MESURE EN QUEUE")
    print("=" * 78)
    print("  Les deux corrections sont GELEES dans HYPOTHESES.md AVANT")
    print("  cette execution. Horizon primaire 60 min ; 30 et 120 sont")
    print("  imprimes en robustesse et ne portent aucun verdict.")
    print()
    print("  Le niveau temoin est pose au MEME ecart geometrique sur une")
    print("  bougie ordinaire de la meme minute de seance, un autre jour.")
    print("  Les deux distances sont donc identiques par construction --")
    print("  la ligne DISTANCE ci-dessous doit le montrer.")
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

        al = random.Random(GRAINE)
        cles = {H: [] for H in HORIZONS}
        SR = {H: [] for H in HORIZONS}
        ST = {H: [] for H in HORIZONS}
        dist_r, dist_t = [], []
        agit_r, agit_t = [], []
        sans_temoin = 0
        for jour, i, j, mn in reperes:
            cand = [x for x in ordinaires.get(mn, []) if x[0] != jour]
            if not cand:
                sans_temoin += 1
                continue
            _jt, it, jt = cand[al.randrange(len(cand))]
            br_ = j[i]
            bt_ = jt[it]
            # DESCRIPTIF, hors verdict : l agitation des 60 minutes qui
            # suivent, de chaque cote. Un niveau tient moins bien quand
            # ca bouge plus -- cette ligne dit COMMENT, pas SI. Le banc
            # a montre qu une difference de population de journees
            # fabrique a elle seule un p de 0,001 ; on la rend visible.
            agit_r.append(br.med([x["h"] - x["b"] for x in
                                  j[i + 1:i + 1 + PRIMAIRE]]) or 0.0)
            agit_t.append(br.med([x["h"] - x["b"] for x in
                                  jt[it + 1:it + 1 + PRIMAIRE]]) or 0.0)
            for signe in (+1, -1):
                # d = ecart du niveau repere a SA propre cloture ; le
                # meme d est pose sur la cloture du temoin. Distances
                # identiques par construction.
                d = (br_["h"] - br_["c"]) if signe > 0 else (br_["c"] - br_["b"])
                if d < 0:
                    continue
                niv_r = br_["c"] + signe * d
                niv_t = bt_["c"] + signe * d
                dist_r.append(abs(niv_r - br_["c"]))
                dist_t.append(abs(niv_t - bt_["c"]))
                for H in HORIZONS:
                    s1 = statut(j, i, niv_r, H)
                    s2 = statut(jt, it, niv_t, H)
                    if s1 is None or s2 is None:
                        continue
                    cles[H].append(jour)
                    SR[H].append(1.0 if s1 else 0.0)
                    ST[H].append(1.0 if s2 else 0.0)

        if sans_temoin:
            print("  %-16s %d repere(s) sans temoin a la meme minute, "
                  "ecarte(s)" % ("", sans_temoin))
        n = len(SR[PRIMAIRE])
        if n < 60:
            print("  %-16s %d paire(s) exploitables a %d min : rien n est "
                  "teste." % ("", n, PRIMAIRE))
            print()
            continue

        print()
        print("    %-26s %10s %10s" % ("", "REPERE", "TEMOIN"))
        print("    %-26s %10.2f %10.2f"
              % ("DISTANCE mediane au prix", br.med(dist_r) or 0,
                 br.med(dist_t) or 0))
        print("    %-26s %10.2f %10.2f"
              % ("agitation 60 min (desc.)", br.med(agit_r) or 0,
                 br.med(agit_t) or 0))
        for H in HORIZONS:
            nH = len(SR[H])
            if nH == 0:
                continue
            etoile = "  <-- primaire" if H == PRIMAIRE else ""
            print("    non touche a %3d min (n=%5d) %8.1f%% %9.1f%%%s"
                  % (H, nH, 100.0 * (moy(SR[H]) or 0),
                     100.0 * (moy(ST[H]) or 0), etoile))
        print()

        e, pv = p_permutation_jour(cles[PRIMAIRE], SR[PRIMAIRE],
                                   ST[PRIMAIRE], a.tirages)
        print("    ecart a %d min : %+.1f point(s) de pourcentage   p = %s"
              % (PRIMAIRE, 100.0 * (e or 0.0),
                 ("%.4f" % pv) if pv is not None else "non teste"))
        print()
        dr, dt = br.med(dist_r) or 0.0, br.med(dist_t) or 0.0
        if abs(dr - dt) > 1e-9:
            print("    ANOMALIE : les distances devaient etre identiques par")
            print("    construction et ne le sont pas. Ne pas lire le")
            print("    resultat ci-dessus avant d avoir compris pourquoi.")
        elif pv is None:
            print("    Moins de dix journees melangeables : pas de test.")
        elif pv >= 0.05:
            print("    RIEN sur %s. A geometrie egale, un niveau de bougie"
                  % sym)
            print("    repere n est pas moins souvent touche dans l heure.")
        elif (e or 0) > 0:
            print("    Le niveau repere tient PLUS SOUVENT que le temoin,")
            print("    a distance identique. Verdict d ensemble : voir la")
            print("    regle H36 -- il faut les DEUX symboles, meme signe.")
        else:
            print("    Le niveau repere tient MOINS souvent. Signe oppose a")
            print("    l enonce : ce n est pas une confirmation.")
        print()

    print("=" * 78)
    print("RAPPEL DE LA REGLE H36, ECRITE AVANT CETTE EXECUTION")
    print("=" * 78)
    print("  MES et YM tous deux p < 0,05, meme signe -> le repere ajoute")
    print("     quelque chose a geometrie egale.")
    print("  un seul des deux -> asymetrique, note tel quel.")
    print("  aucun des deux   -> la question est CLOSE : ni troisieme")
    print("     horizon, ni autre seuil de dimensions, ni autre decoupage.")
    print()
    print("  Ce tour consomme l integralite de l echantillon. Un positif")
    print("  se confirme le 20/10/2026 sur les seances posterieures au")
    print("  18/08/2026, memes parametres, une seule passe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
