# -*- coding: utf-8 -*-
r"""
croise_sr.py -- H39 : un niveau S/R ne sur une bougie repere est-il
                plus souvent revu ?

  python croise_sr.py
  python croise_sr.py --csv volume_sr_levels.csv --mini-dims 2

CE QUI EST CROISE, ET POURQUOI AUCUN PRIX N INTERVIENT

  volume_sr_levels.csv porte, pour chaque niveau :

      bar_time      la MINUTE de la bougie qui l a cree
      touch_count   le nombre de fois ou il a ete revu

  Nos bougies reperes sont des minutes. La jointure se fait donc sur le
  TEMPS seul. C est ce qui elimine d un coup le probleme qui bloquait
  tout depuis ce matin : MES cote 7826 quand US500 cote 7757, et cet
  ecart bouge. Sur les instants, il n y a pas d echelle.

  US100 est ecarte : nous n avons d orderflow que pour MES et YM.
      US500 <-> MES-continu       US30 <-> YM-continu

LE FUSEAU, ET POURQUOI IL EST CALIBRE AVANT

  Le CSV vient de MT5, donc de l heure du serveur du courtier. Nos
  of_*.csv sont en UTC. Un decalage de deux ou trois heures ferait
  echouer la jointure EN SILENCE -- zero coincidence, et la conclusion
  "rien" alors qu on aurait compare 10:51 a 08:51.

  INTERDIT : retenir le decalage qui maximise les coincidences avec nos
  reperes. Ce serait choisir la reponse.

  IMPOSE : le decalage est estime sur le PROFIL D ACTIVITE HORAIRE des
  deux series -- nombre de niveaux crees par heure d un cote, somme des
  trades par heure de l autre. Signal independant de la question posee.
  Les 25 decalages sont IMPRIMES avec leur score, et le retenu est
  gele AVANT que le premier repere soit lu.

LE TEMOIN : PERMUTATION DANS LA CASE (JOUR x HEURE)

  H39 disait "a l interieur de chaque journee". C est renforce ici, et
  le renforcement est declare AVANT la mesure : la permutation se fait
  dans chaque case (jour x heure).

  Raison : 13:00 UTC porte 18,2 % des reperes de YM. Un niveau ne a
  l ouverture du cash a plus de chances d etre a la fois sur une minute
  repere ET beaucoup touche, sans qu aucun lien n existe entre les
  deux. Permuter dans l heure neutralise ca ; permuter dans la journee
  ne le neutralisait pas.

  Les deux sont calcules et imprimes. Le primaire est (jour x heure).

LA STATISTIQUE, ET PAS UNE MEDIANE

  touch_count prend de petites valeurs entieres. Une mediane y serait
  degeneree -- c est la faute de ce matin sur la survie en minutes. Le
  primaire est la difference des MOYENNES.

LE GARDE-FOU, declare avant

      moins de 20 % de niveaux avec touch_count >= 1,
      ou moins de 30 niveaux sur une minute repere
          -> SANS PUISSANCE. Le `p` n est ni calcule ni lu.

CE QUE CA NE DIRA PAS

  Qu un niveau soit revu ne dit pas qu il tient, ni qu il rapporte. Et
  un niveau ne dans un moment d activite est peut-etre simplement ne
  la ou le prix passait beaucoup.

LECTEUR SEUL.
"""
import argparse
import csv
import io
import os
import random
import sys
from datetime import datetime

import bougies_reperes as br

GRAINE = 20260818
PAIRES = [("US500", "MES-continu"), ("US30", "YM-continu")]


def moy(v):
    return (sum(v) / float(len(v))) if v else None


def correl(a, b):
    n = len(a)
    ma, mb = moy(a), moy(b)
    if ma is None or mb is None:
        return None
    sa = sum((x - ma) ** 2 for x in a) ** 0.5
    sb = sum((x - mb) ** 2 for x in b) ** 0.5
    if sa <= 0 or sb <= 0:
        return None
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (sa * sb)


def lit_csv(chemin):
    """Les niveaux du CSV. Rend (lignes, message)."""
    if not os.path.isfile(chemin):
        return None, "introuvable"
    out = []
    f = io.open(chemin, "r", encoding="utf-8", errors="replace", newline="")
    for r in csv.DictReader(f):
        bt = (r.get("bar_time") or "").strip()
        if len(bt) < 16:
            continue
        try:
            t = datetime.strptime(bt[:16], "%Y-%m-%d %H:%M")
            tc = int(float(r.get("touch_count") or 0))
        except ValueError:
            continue
        out.append({"t": t, "asset": (r.get("asset") or "").strip(),
                    "tc": tc, "type": (r.get("type") or "").strip()})
    f.close()
    return out, ""


def profil_niveaux(niv):
    """Nombre de niveaux crees par heure, en heure DU SERVEUR."""
    h = [0.0] * 24
    for x in niv:
        h[x["t"].hour] += 1.0
    return h


def profil_trades(jours):
    """Somme des trades par heure, en UTC."""
    h = [0.0] * 24
    for v in jours.values():
        for b in v:
            h[b["t"].hour] += float(b["n"])
    return h


def decalage(p_niv, p_tr):
    """Le decalage horaire serveur -> UTC, estime sur les profils.

    L heure serveur H correspond a l heure UTC (H - d). On cherche le d
    qui aligne le mieux les deux profils. AUCUN repere n intervient."""
    scores = []
    for d in range(-12, 13):
        b = [p_tr[(H - d) % 24] for H in range(24)]
        c = correl(p_niv, b)
        if c is not None:
            scores.append((c, d))
    if not scores:
        return None, []
    scores.sort(reverse=True)
    return scores[0][1], scores


def p_permutation(cles, va, vb, tirages, graine=GRAINE):
    """p bilaterale sur la difference des MOYENNES, en permutant
    l etiquette a l interieur de chaque case `cles`."""
    obs = None
    if va and vb:
        obs = moy(va) - moy(vb)
    if obs is None:
        return None, None
    cases = set(cles[0]) | set(cles[1])
    if len(cases) < 8:
        return obs, None
    al = random.Random(graine)
    parc = {}
    for c, x, g in ([(c, x, 0) for c, x in zip(cles[0], va)]
                    + [(c, x, 1) for c, x in zip(cles[1], vb)]):
        parc.setdefault(c, []).append((x, g))
    pires = 0
    for _ in range(tirages):
        a2, b2 = [], []
        for c in parc:
            v = parc[c]
            et = [g for _, g in v]
            al.shuffle(et)
            for (x, _), g in zip(v, et):
                (a2 if g == 0 else b2).append(x)
        if a2 and b2:
            e = moy(a2) - moy(b2)
            if abs(e) >= abs(obs):
                pires += 1
    return obs, (1.0 + pires) / (1.0 + tirages)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dossier", default=br.DOSSIER)
    p.add_argument("--csv", default="volume_sr_levels.csv")
    p.add_argument("--centile", type=float, default=99.5)
    p.add_argument("--mini-dims", type=int, default=2)
    p.add_argument("--tirages", type=int, default=2000)
    a = p.parse_args()

    print("=" * 78)
    print("H39 -- LE NIVEAU S/R NE SUR UNE BOUGIE REPERE EST-IL PLUS REVU")
    print("=" * 78)
    print("  Jointure sur le TEMPS seul : bar_time du CSV contre la minute")
    print("  de la bougie repere. Aucun prix n intervient, donc aucun")
    print("  probleme de base future/CFD.")
    print()

    manque = [n for n in ("bornes", "dimensions", "charge", "med",
                          "sans_carnet", "DIMS") if not hasattr(br, n)]
    if manque:
        print("KO : bougies_reperes.py n expose pas %s." % ", ".join(manque))
        return 1

    niv, msg = lit_csv(a.csv)
    if niv is None:
        print("KO : %s %s." % (a.csv, msg))
        return 1
    if not niv:
        print("KO : aucun niveau exploitable dans %s." % a.csv)
        return 1
    tt = sorted(x["t"] for x in niv)
    print("  %s : %d niveau(x), du %s au %s"
          % (a.csv, len(niv), tt[0], tt[-1]))
    par_asset = {}
    for x in niv:
        par_asset.setdefault(x["asset"], []).append(x)
    for k in sorted(par_asset):
        v = par_asset[k]
        touches = len([y for y in v if y["tc"] >= 1])
        print("    %-8s %5d niveau(x), %5d touche(s) au moins une fois "
              "(%.0f %%)" % (k, len(v), touches,
                             100.0 * touches / max(1, len(v))))
    print()

    barres, m2 = br.charge(a.dossier)
    for m in m2:
        print(m)
    print()

    for asset, sym in PAIRES:
        print("-" * 78)
        print("  %s  <->  %s" % (asset, sym))
        print("-" * 78)
        lv = par_asset.get(asset) or []
        if sym not in barres:
            print("    %s absent des donnees orderflow. Ecarte." % sym)
            print()
            continue
        if len(lv) < 30:
            print("    %d niveau(x) seulement pour %s : rien n est teste."
                  % (len(lv), asset))
            print()
            continue

        jours = {}
        for b in barres[sym]:
            jours.setdefault(b["t"].date(), []).append(b)

        # --- LE FUSEAU, avant tout repere ---------------------------
        d, scores = decalage(profil_niveaux(lv), profil_trades(jours))
        if d is None:
            print("    profils plats : fuseau indeterminable. On s arrete.")
            print()
            continue
        print("    FUSEAU, estime sur les profils d activite horaire")
        print("    (aucun repere n intervient dans ce choix) :")
        for c, dd in scores[:4]:
            print("       decalage %+3d h   correlation %+.3f%s"
                  % (dd, c, "   <-- retenu" if dd == d else ""))
        marge = scores[0][0] - scores[1][0] if len(scores) > 1 else 0.0
        print("    marge sur le suivant : %+.3f" % marge)
        if scores[0][0] < 0.5 or marge < 0.05:
            print()
            print("    ALIGNEMENT TROP FAIBLE. Une jointure temporelle sur")
            print("    un fuseau incertain ne vaut rien : on s arrete ici")
            print("    pour %s." % asset)
            print()
            continue
        print()

        # --- les minutes reperes, en UTC -----------------------------
        cpt = sorted(len(v) for v in jours.values())
        seuil_j = max(30, (cpt[len(cpt) // 2] if cpt else 0) // 2)
        mtr = [br.med([x["n"] for x in v]) or 0.0 for v in jours.values()]
        seuil_tr = (br.med(mtr) or 0.0) / 2.0
        rep = set()
        for jour in sorted(jours):
            j = sorted(jours[jour], key=lambda x: x["t"])
            if len(j) < seuil_j:
                continue
            if (br.med([x["n"] for x in j]) or 0.0) < seuil_tr:
                continue
            br.dimensions(j)
            res = br.bornes(j, a.centile)
            haut, bas = res[0], res[1]
            for b in j:
                q = 0
                for dim in br.DIMS:
                    if haut[dim] is not None and b[dim] >= haut[dim]:
                        q += 1
                    elif bas[dim] is not None and b[dim] <= bas[dim]:
                        q += 1
                if q >= a.mini_dims:
                    rep.add(b["t"].replace(second=0, microsecond=0))

        # --- le croisement -------------------------------------------
        from datetime import timedelta
        sur, hors = [], []
        cj_sur, cj_hors, ch_sur, ch_hors = [], [], [], []
        hors_periode = 0
        t0 = min(b["t"] for v in jours.values() for b in v)
        t1 = max(b["t"] for v in jours.values() for b in v)
        for x in lv:
            u = x["t"] - timedelta(hours=d)
            if u < t0 or u > t1:
                hors_periode += 1
                continue
            cle_j = str(u.date())
            cle_h = "%s %02d" % (u.date(), u.hour)
            if u in rep:
                sur.append(float(x["tc"]))
                cj_sur.append(cle_j)
                ch_sur.append(cle_h)
            else:
                hors.append(float(x["tc"]))
                cj_hors.append(cle_j)
                ch_hors.append(cle_h)

        print("    niveaux hors periode orderflow, ecartes : %d" % hors_periode)
        print("    %-28s %8s %8s" % ("", "REPERE", "ORDINAIRE"))
        print("    %-28s %8d %8d" % ("niveaux", len(sur), len(hors)))
        if sur and hors:
            print("    %-28s %8.2f %8.2f"
                  % ("touch_count moyen", moy(sur), moy(hors)))
            t_sur = len([x for x in sur if x >= 1])
            t_hors = len([x for x in hors if x >= 1])
            print("    %-28s %7.0f%% %7.0f%%"
                  % ("touche au moins une fois",
                     100.0 * t_sur / len(sur), 100.0 * t_hors / len(hors)))
        print()

        # --- le garde-fou --------------------------------------------
        tous = sur + hors
        part = (len([x for x in tous if x >= 1]) / float(len(tous))
                if tous else 0.0)
        if len(sur) < 30 or part < 0.20:
            print("    SANS PUISSANCE -- garde-fou declare avant la mesure :")
            print("      %d niveau(x) sur une minute repere (30 minimum)"
                  % len(sur))
            print("      %.0f %% de niveaux touches au moins une fois "
                  "(20 %% minimum)" % (100.0 * part))
            print("    Le p n est NI CALCULE NI LU. On attend que le CSV")
            print("    grandisse -- il couvre trois semaines aujourd hui.")
            print()
            continue

        e1, p1 = p_permutation((ch_sur, ch_hors), sur, hors, a.tirages)
        e2, p2 = p_permutation((cj_sur, cj_hors), sur, hors, a.tirages)
        print("    ecart des moyennes : %+.2f touche(s)" % (e1 or 0.0))
        print("      permutation dans (jour x heure)  p = %s   <-- primaire"
              % (("%.4f" % p1) if p1 is not None else "non teste"))
        print("      permutation dans la journee      p = %s"
              % (("%.4f" % p2) if p2 is not None else "non teste"))
        print()
        if p1 is None:
            print("    Moins de huit cases melangeables : pas de test.")
        elif p1 >= 0.05:
            print("    RIEN sur %s. Un niveau ne sur une minute repere n est"
                  % asset)
            print("    pas plus revu qu un autre, a heure de journee egale.")
        elif (e1 or 0) > 0:
            print("    Le niveau ne sur une minute repere est PLUS revu.")
            print("    Il faut les DEUX actifs, meme signe (regle H39).")
            print("    Et lire l ecart entre les deux permutations : si le")
            print("    (jour x heure) est bien plus faible que le (jour),")
            print("    une part de l effet etait l horloge.")
        else:
            print("    Le niveau ne sur une minute repere est MOINS revu.")
            print("    Signe oppose a l enonce : pas une confirmation.")
        print()

    print("=" * 78)
    print("  Ni euro, ni sens. Qu un niveau soit revu ne dit pas qu il")
    print("  tient. Et un niveau ne dans un moment d activite est peut-")
    print("  etre simplement ne la ou le prix passait beaucoup.")
    print()
    print("  Confirmation datee : 20/10/2026, sur les niveaux crees apres")
    print("  le 18/08/2026. Le CSV grandit seul.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
