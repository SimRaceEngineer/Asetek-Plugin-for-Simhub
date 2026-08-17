# -*- coding: utf-8 -*-
r"""
cvd_journalier.py -- le desaccord des carnets est-il un fait de marche
ou un biais du fichier ?

  python cvd_journalier.py
  python cvd_journalier.py --date 2026-08-12

CE QU ON VIENT DE VOIR, ET POURQUOI IL FAUT LE VERIFIER

    Le 12/08, sur les 61 minutes autour de 14h30 :

        MES-continu   CVD de +23 a +1339, minimum +86   jamais negatif
        YM-continu    CVD de  -7 a  -195, maximum  -2   jamais positif

    Deux carnets qui ne sont pas une seule fois du meme cote de zero,
    pendant une heure. Lu comme un fait de marche, ca dit que le Dow
    est vendu pendant que le S&P est achete -- et en notionnel l ecart
    est encore plus net.

    Lu autrement, ca dit qu on a un BIAIS DE CLASSIFICATION. Le champ
    `delta` vient de BidVolume et AskVolume, calcules par SierraChart
    en comparant chaque transaction au bid et a l ask du moment. Si,
    sur un symbole peu liquide ou en flux differe, cette comparaison
    penche systematiquement d un cote, le CVD derive dans une direction
    TOUS LES JOURS, sans qu aucun acheteur ni vendeur n ait rien fait
    de particulier.

    Les deux lectures produisent exactement la meme sortie sur une
    journee. Elles ne produisent pas la meme sortie sur cent trente.

LE TEST

    Pour chaque symbole et chaque seance : le delta cumule du jour, son
    signe, le volume, et le rapport delta/volume.

        Si un symbole sort le MEME SIGNE presque tous les jours, son
        CVD ne mesure pas un desequilibre acheteur/vendeur : il mesure
        une constante du fichier. Le desaccord du 12/08 est alors la
        normale, pas un evenement.

        Si les signes alternent et que le 12/08 est marque, le
        desaccord est un fait de la journee.

    Le seuil de "presque tous les jours" n est pas invente : on le
    compare a ce que donnerait un tirage a pile ou face de meme
    effectif, ecart-type sqrt(n)/2. Un symbole a 65 jours positifs sur
    130 est indiscernable du hasard ; a 125 sur 130, il ne l est pas.

ET LA CONTINGENCE

    Un tableau 2x2 des signes joints MES x YM. Si le desaccord est un
    fait de marche, il doit y avoir des journees ou les deux montent
    ensemble et des journees ou les deux baissent ensemble. Si la case
    (MES+, YM-) contient presque tout, il n y a pas de desaccord : il y
    a deux fichiers qui derivent en sens contraire.

LECTEUR SEUL : lit cartes\scid\of_*.csv, n ecrit qu un panel texte.
"""
import argparse
import csv
import io
import math
import os
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "scid")
SORTIE = os.path.join("cartes", "panel_cvd.txt")
LARG = 100

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


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def charge(dossier):
    """Les series, les raccords ayant absorbe leurs echeances."""
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


def par_seance(serie):
    """Delta cumule, volume et nombre de barres, par date.

    Une date n est retenue comme SEANCE que si elle porte au moins la
    moitie du nombre median de barres. Les reouvertures du dimanche
    soir n ont que quelques barres : leur CVD serait un bruit compte
    comme une journee."""
    par = {}
    for t, c, d, v, _ in serie:
        j = t.date()
        a = par.setdefault(j, [0.0, 0.0, 0])
        a[0] += d
        a[1] += v
        a[2] += 1
    cpt = sorted(x[2] for x in par.values())
    med = cpt[len(cpt) // 2] if cpt else 0
    seuil = max(1, med // 2)
    return (dict((j, x) for j, x in par.items() if x[2] >= seuil),
            med, seuil, len(par))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--date", default=None,
                   help="une journee a situer dans la distribution")
    a = p.parse_args()

    barres, msg = charge(a.entree)
    if not barres:
        print("KO : aucune serie dans %s." % a.entree)
        return 1

    dis("=" * LARG)
    dis("CVD PAR SEANCE -- fait de marche, ou biais du fichier ?")
    dis("=" * LARG)
    for m in msg:
        dis(m)
    if msg:
        dis()
    dis("  Un CVD qui ne change jamais de signe peut dire deux choses :")
    dis("  que le carnet penche vraiment toujours du meme cote, ou que")
    dis("  la classification bid/ask du fichier penche toute seule. Sur")
    dis("  une journee les deux lectures sont identiques. Sur cent")
    dis("  trente, non.")

    jour = None
    if a.date:
        try:
            jour = dt.datetime.strptime(a.date, "%Y-%m-%d").date()
        except ValueError:
            print("KO : --date AAAA-MM-JJ.")
            return 1

    dis()
    dis("-" * LARG)
    dis("%-16s %7s %8s %8s %10s %12s %10s"
        % ("symbole", "seances", "CVD>0", "CVD<0", "ecart z",
           "med CVD/jour", "med d/vol"))
    dis("-" * LARG)
    tables = {}
    for sym in sorted(barres):
        seances, med, seuil, brut = par_seance(barres[sym])
        if len(seances) < 10:
            dis("  %-16s moins de dix seances, rien a conclure." % sym)
            continue
        cv = [x[0] for x in seances.values()]
        # Une serie dont le delta est nul partout n a pas de signe a
        # compter. Lui donner un z de -7,7 parce que zero n est pas
        # strictement positif serait un chiffre juste et un sens faux.
        if not any(cv):
            dis("  %-16s %7d   aucun delta : ce symbole ne porte pas de"
                % (sym, len(cv)))
            dis("  %-16s           carnet, il est hors de ce test."
                % "")
            continue
        tables[sym] = seances
        pos = sum(1 for v in cv if v > 0)
        neg = sum(1 for v in cv if v < 0)
        n = len(cv)
        # Ecart au tirage a pile ou face : sous l hypothese "un jour sur
        # deux", l esperance est n/2 et l ecart-type sqrt(n)/2. On
        # affiche l ecart en nombre d ecarts-types, ce qui evite
        # d inventer un seuil.
        z = (pos - n / 2.0) / (math.sqrt(n) / 2.0) if n else 0.0
        rap = [x[0] / x[1] for x in seances.values() if x[1] > 0]
        dis("  %-16s %7d %8d %8d %+10.1f %12.0f %10.4f"
            % (sym, n, pos, neg, z, mediane(cv) or 0,
               mediane(rap) or 0))
    dis("-" * LARG)
    dis("  `ecart z` compare le compte de journees positives a ce que")
    dis("  donnerait un tirage a pile ou face de meme effectif. Au-dela")
    dis("  de +/-3, ce n est plus du hasard ; au-dela de +/-8, ce n est")
    dis("  plus un marche, c est une constante du fichier.")
    dis()
    dis("  `med d/vol` est le delta rapporte au volume du jour. Un biais")
    dis("  de classification donne un rapport STABLE ; un desequilibre")
    dis("  de marche varie d une seance a l autre.")

    # --- contingence 2x2 -------------------------------------------
    syms = sorted(tables)
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            sa, sb = syms[i], syms[j]
            communs = sorted(set(tables[sa]) & set(tables[sb]))
            if len(communs) < 10:
                continue
            dis()
            dis("=" * LARG)
            dis("SIGNES JOINTS -- %s x %s, %d seances communes"
                % (sa, sb, len(communs)))
            dis("=" * LARG)
            c = {}
            for d in communs:
                k = (tables[sa][d][0] > 0, tables[sb][d][0] > 0)
                c[k] = c.get(k, 0) + 1
            n = len(communs)
            dis("  %-22s %14s %14s" % ("", sb + " +", sb + " -"))
            for va, la in ((True, sa + " +"), (False, sa + " -")):
                dis("  %-22s %14d %14d"
                    % (la, c.get((va, True), 0), c.get((va, False), 0)))
            acc = c.get((True, True), 0) + c.get((False, False), 0)
            dis()
            dis("  Meme signe : %d seances sur %d, soit %.0f %%."
                % (acc, n, 100.0 * acc / n))
            dom = max(c.items(), key=lambda kv: kv[1])
            dis("  Case dominante : %s %s / %s %s, %d seances (%.0f %%)."
                % (sa, "+" if dom[0][0] else "-",
                   sb, "+" if dom[0][1] else "-", dom[1],
                   100.0 * dom[1] / n))
            if dom[1] > 0.85 * n:
                dis()
                dis("  UNE SEULE CASE PORTE PLUS DE 85 % DES SEANCES.")
                dis("  Il n y a pas de desaccord entre deux carnets : il y")
                dis("  a deux fichiers qui derivent en sens contraire tous")
                dis("  les jours. Le CVD de ces deux symboles n est pas")
                dis("  comparable en signe, et toute lecture du type `l un")
                dis("  est achete pendant que l autre est vendu` est un")
                dis("  artefact de classification.")
            else:
                dis()
                dis("  Les quatre cases sont peuplees : le signe du CVD")
                dis("  varie d une seance a l autre sur les deux symboles.")
                dis("  Un desaccord observe un jour donne est alors un")
                dis("  fait de cette journee-la, pas une constante.")

            if jour and jour in tables[sa] and jour in tables[sb]:
                dis()
                dis("  LA JOURNEE DEMANDEE -- %s" % jour)
                for s in (sa, sb):
                    cv = sorted(x[0] for x in tables[s].values())
                    v = tables[s][jour][0]
                    rang = sum(1 for x in cv if x < v)
                    dis("    %-16s CVD %+10.0f   centile %5.1f"
                        % (s, v, 100.0 * rang / len(cv)))
                dis("  Un centile proche de 50 dit une journee ordinaire")
                dis("  pour ce symbole, quel que soit le signe.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA NE DIT PAS")
    dis("=" * LARG)
    dis("  Ce test ne mesure pas le marche : il mesure si le FICHIER")
    dis("  permet de mesurer le marche. C est une verification de")
    dis("  source, a faire avant toute lecture de CVD -- et qui")
    dis("  manquait.")
    dis("  Il ne dit rien de l amplitude : un symbole peut avoir un")
    dis("  signe honnete et un delta trop faible pour etre lu.")
    dis("  Il ne compare pas les notionnels : 815 micro-S&P et 170")
    dis("  E-mini Dow ne pesent pas pareil, et c est une autre mesure.")
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
