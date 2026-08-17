# -*- coding: utf-8 -*-
r"""
flux_contre_prix.py -- le delta explique-t-il le prix, et les deux
carnets divergent-ils vraiment ?

  python flux_contre_prix.py
  python flux_contre_prix.py --tirages 5000

LES DEUX QUESTIONS QU ON N AVAIT PAS POSEES

    Toute la journee du 17/08 a porte sur des evenements macro : trois
    CPI, trois NFP, six ISM. Aucun effectif exploitable, et quatre
    resultats prometteurs morts un par un.

    Pendant ce temps, deux questions bien plus fondamentales attendaient
    avec 110 et 133 observations :

    1. LE DELTA EXPLIQUE-T-IL LE PRIX ?

       Le delta cumule d une seance -- contrats a l achat moins a la
       vente -- a-t-il un rapport avec le mouvement de prix de cette
       seance ? Si non, tout le CVD est un compteur decoratif et il
       faut le dire. Si oui, les divergences entre carnets deviennent
       le sujet.

       Personne n a verifie. On a construit six outils dessus.

    2. LES DEUX CARNETS DIVERGENT-ILS VRAIMENT ?

       Le tableau de contingence du 17/08 donne 32 / 21 / 34 / 23 :
       meme signe une seance sur deux, soit l independance parfaite.

       Or les PRIX du S&P et du Dow montent et descendent ensemble.
       Si leurs rendements sont fortement correles et leurs deltas pas
       du tout, alors les prix bougent de concert pendant que les flux
       divergent -- ce qui est precisement la rotation cherchee depuis
       le debut, invisible dans les prix et lisible dans les carnets.

       C est une DISSOCIATION, et elle se mesure sur 110 seances.

COMMENT

    Par seance et par symbole : le rendement (derniere cloture sur
    premiere, en %) et le delta cumule.

    Puis des correlations de RANG (Spearman). Pas de Pearson : une
    seule seance extreme -- et il y en a, on en a vu a 48 fois le
    volume median -- suffit a porter un coefficient de Pearson a elle
    seule. Le rang ne s en laisse pas conter.

    Chaque correlation vient avec une p-value par PERMUTATION des
    seances, graine fixe. Une correlation sans effectif ni p ne veut
    rien dire, et on en a assez vu aujourd hui.

CE QUE CA NE DIRA PAS

    Aucune causalite. Une correlation entre delta et rendement ne dit
    pas si le flux pousse le prix ou si le prix attire le flux ; les
    deux se produisent, et les separer demande une mesure intra-seance
    que ce fichier ne fait pas.

    Aucun euro.

LECTEUR SEUL : lit cartes\scid\of_*.csv.
"""
import argparse
import csv
import io
import os
import random
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "scid")
SORTIE = os.path.join("cartes", "panel_flux_prix.txt")
LARG = 100
SEUIL_Z = 8.0

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(s):
    if not s:
        return None
    s = s.strip().replace("T", " ")
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s[:19], f)
        except ValueError:
            continue
    return None


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def charge(dossier):
    out = {}
    if not os.path.isdir(dossier):
        return out, []
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("of_") or not nom.endswith(".csv"):
            continue
        serie = []
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            for r in csv.DictReader(f, delimiter=";"):
                t = horo(r.get("ts"))
                c = flt(r.get("close"))
                if t is None or c is None:
                    continue
                serie.append((t, c, flt(r.get("delta")) or 0.0,
                              flt(r.get("volume")) or 0.0,
                              (r.get("contrat") or "").strip()))
        if len(serie) > 100:
            serie.sort(key=lambda x: x[0])
            out[nom[3:-4]] = serie
    absorbes = {}
    for sym, serie in out.items():
        for n in set(x[4] for x in serie if x[4]):
            if n != sym and n in out:
                absorbes[n] = sym
    msg = ["  of_%s.csv ecarte : deja dans of_%s.csv (colonne `contrat`)"
           % (n, s) for n, s in sorted(absorbes.items())]
    return dict((s, v) for s, v in out.items() if s not in absorbes), msg


def seances(serie):
    """Par date : rendement en %, delta cumule, volume, contrats.

    Une date n est retenue que si elle porte au moins la moitie du
    nombre median de barres, et si elle ne contient qu un seul contrat
    -- un jour de roulement melangerait deux niveaux de prix et
    produirait un rendement qui mesure la base."""
    par = {}
    for t, c, d, v, k in serie:
        j = t.date()
        a = par.setdefault(j, [c, c, 0.0, 0.0, 0, set()])
        a[1] = c
        a[2] += d
        a[3] += v
        a[4] += 1
        if k:
            a[5].add(k)
    cpt = sorted(x[4] for x in par.values())
    med = cpt[len(cpt) // 2] if cpt else 0
    seuil = max(1, med // 2)
    out = {}
    for j, a in par.items():
        if a[4] < seuil or len(a[5]) > 1 or a[0] <= 0:
            continue
        out[j] = ((a[1] - a[0]) / a[0] * 100.0, a[2], a[3])
    return out, med, seuil


def rangs(v):
    """Rangs moyens, ex aequo compris."""
    ordre = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(ordre):
        j = i
        while j + 1 < len(ordre) and v[ordre[j + 1]] == v[ordre[i]]:
            j += 1
        moy = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[ordre[k]] = moy
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    if n < 3:
        return None
    ma = sum(a) / n
    mb = sum(b) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((x - mb) ** 2 for x in b) ** 0.5
    if da == 0 or db == 0:
        return None
    return num / (da * db)


def spearman(a, b):
    return pearson(rangs(a), rangs(b))


def p_permutation(a, b, tirages, graine=20260817):
    """p bilaterale par permutation des seances.

    On permute UNE des deux series : sous l hypothese nulle, l
    appariement seance par seance ne porte aucune information. La
    graine est fixe -- une p-value qui change a chaque execution est
    une loterie qu on relance jusqu a ce qu elle plaise."""
    obs = spearman(a, b)
    if obs is None:
        return None, None
    ra, rb = rangs(a), rangs(b)
    al = random.Random(graine)
    pires = 0
    m = list(rb)
    for _ in range(tirages):
        al.shuffle(m)
        c = pearson(ra, m)
        if c is not None and abs(c) >= abs(obs):
            pires += 1
    return obs, (1.0 + pires) / (1.0 + tirages)


def signe_fige(sc):
    cv = [x[1] for x in sc.values()]
    n = len(cv)
    if n < 20:
        return False, 0.0
    pos = sum(1 for v in cv if v > 0)
    z = (pos - n / 2.0) / ((n ** 0.5) / 2.0)
    return abs(z) >= SEUIL_Z, z


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--tirages", type=int, default=2000)
    a = p.parse_args()

    barres, msg = charge(a.entree)
    if len(barres) < 2:
        print("KO : il faut au moins deux symboles dans %s." % a.entree)
        return 1

    dis("=" * LARG)
    dis("LE FLUX CONTRE LE PRIX -- deux questions a 110 observations")
    dis("=" * LARG)
    for m in msg:
        dis(m)
    if msg:
        dis()
    dis("  Toute la journee a porte sur trois CPI et trois NFP. Ces")
    dis("  deux questions-la attendaient avec 110 et 133 seances :")
    dis()
    dis("  1. le delta cumule d une seance explique-t-il le mouvement")
    dis("     de prix de cette seance ?")
    dis("  2. les deux carnets divergent-ils VRAIMENT, alors que les")
    dis("     prix, eux, bougent ensemble ?")
    dis()
    dis("  Correlations de RANG (Spearman) : une seule seance extreme")
    dis("  -- et il y en a a 48 fois le volume median -- suffirait a")
    dis("  porter un Pearson a elle seule.")

    sc, exclus = {}, []
    dis()
    dis("-" * LARG)
    dis("  %-16s %8s %8s %10s %12s"
        % ("symbole", "seances", "med/j", "z du signe", "retenu"))
    dis("-" * LARG)
    for sym in sorted(barres):
        s, med, seuil = seances(barres[sym])
        if len(s) < 30:
            dis("  %-16s %8d   moins de trente seances, ecarte."
                % (sym, len(s)))
            continue
        fige, z = signe_fige(s)
        dis("  %-16s %8d %8d %10.1f %12s"
            % (sym, len(s), med, z, "NON" if fige else "oui"))
        if fige:
            exclus.append(sym)
            continue
        sc[sym] = s
    dis("-" * LARG)
    if exclus:
        dis("  ECARTE(S) : %s -- signe de CVD fige, c est un compteur"
            % ", ".join(exclus))
        dis("  et non un desequilibre acheteur/vendeur.")
    if len(sc) < 2:
        dis()
        dis("  Moins de deux symboles exploitables.")
        ecrire(a.sortie)
        return 1

    # --- 1. le delta explique-t-il le prix, DANS un symbole ---------
    dis()
    dis("=" * LARG)
    dis("1. LE DELTA EXPLIQUE-T-IL LE PRIX ? -- au sein d un symbole")
    dis("=" * LARG)
    dis("  %-16s %8s %12s %10s" % ("symbole", "n", "rho(d, r)", "p"))
    for sym in sorted(sc):
        js = sorted(sc[sym])
        r = [sc[sym][j][0] for j in js]
        d = [sc[sym][j][1] for j in js]
        rho, pv = p_permutation(d, r, a.tirages)
        dis("  %-16s %8d %12.3f %10.4f" % (sym, len(js), rho, pv))
    dis()
    dis("  `rho(d, r)` lie le delta cumule du jour au rendement du")
    dis("  jour. Proche de zero : le CVD quotidien ne dit rien de la")
    dis("  direction, et six outils construits dessus mesurent un")
    dis("  compteur. Franchement positif : le flux et le prix vont")
    dis("  ensemble, et leurs desaccords deviennent interessants.")
    dis()
    dis("  Aucune causalite ici : un flux qui pousse le prix et un")
    dis("  prix qui attire le flux donnent la meme correlation.")

    # --- 2. la dissociation entre les deux carnets ------------------
    syms = sorted(sc)
    dis()
    dis("=" * LARG)
    dis("2. LES PRIX ENSEMBLE, LES FLUX SEPARES ?")
    dis("=" * LARG)
    dis("  %-24s %8s %12s %10s %12s %10s"
        % ("paire", "n", "rho PRIX", "p", "rho DELTA", "p"))
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            sa, sb = syms[i], syms[j]
            com = sorted(set(sc[sa]) & set(sc[sb]))
            if len(com) < 30:
                continue
            ra = [sc[sa][d][0] for d in com]
            rb = [sc[sb][d][0] for d in com]
            da = [sc[sa][d][1] for d in com]
            db = [sc[sb][d][1] for d in com]
            rp, pp = p_permutation(ra, rb, a.tirages)
            rd, pd = p_permutation(da, db, a.tirages)
            dis("  %-24s %8d %12.3f %10.4f %12.3f %10.4f"
                % ("%s / %s" % (sa[:10], sb[:10]), len(com),
                   rp, pp, rd, pd))
            dis()
            if rp is not None and rd is not None:
                dis("  Ecart entre les deux : %.3f contre %.3f."
                    % (rp, rd))
                if rp > 0.5 and abs(rd) < 0.25:
                    dis("  LES PRIX BOUGENT ENSEMBLE, LES FLUX NON. C est")
                    dis("  une dissociation : la rotation entre les deux")
                    dis("  actifs est invisible dans les prix et lisible")
                    dis("  dans les carnets. C est le seul endroit ou")
                    dis("  l orderflow apporte ce qu aucun prix ne donne.")
                elif abs(rd) >= 0.5:
                    dis("  Les flux vont ensemble autant que les prix :")
                    dis("  il n y a pas de rotation a lire, les deux")
                    dis("  carnets racontent la meme chose.")
                else:
                    dis("  Ni dissociation franche, ni accord franc. A")
                    dis("  cet effectif, c est une zone ou l on ne")
                    dis("  conclut pas.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA NE DIT PAS")
    dis("=" * LARG)
    dis("  Aucune causalite, et c est la limite principale : le flux")
    dis("  qui pousse le prix et le prix qui attire le flux produisent")
    dis("  exactement la meme correlation. Les separer demande une")
    dis("  mesure intra-seance -- qui precede l autre, minute par")
    dis("  minute -- et elle n est pas ici.")
    dis("  Aucun euro : ce sont des rendements et des contrats. Le lien")
    dis("  au PnL passe par churn_trades.jsonl.")
    dis("  Aucune journee particuliere : c est une mesure d ensemble.")
    dis("  Une correlation forte n empeche pas une seance de faire")
    dis("  exactement le contraire.")
    ecrire(a.sortie)
    return 0


def ecrire(chemin):
    d = os.path.dirname(chemin)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(chemin, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (chemin, os.path.getsize(chemin)))


if __name__ == "__main__":
    sys.exit(main())
