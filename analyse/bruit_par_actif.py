# -*- coding: utf-8 -*-
r"""
bruit_par_actif.py -- a quelle echelle chaque actif cesse d etre du bruit

  python bruit_par_actif.py
  python bruit_par_actif.py --actif US500

LA QUESTION, POSEE PAR L UTILISATEUR LE 17/08

    "L unite de bruit est-elle l unite avec le PLUS de bruit (le M1),
    ou bien l unite ou on commence a voir quelque chose en cas de
    reverse (le M2, et mieux encore le M5) ?"

    C est la bonne question, et elle a une reponse mesurable. On ne la
    choisit donc pas.

CE QU ON MESURE : LE RATIO DE VARIANCE

    Pour une marche au hasard, l ecart-type des rendements croit en
    RACINE du temps : doubler l horizon multiplie la dispersion par
    1,414. Le ratio de variance compare ce qu on observe a cette
    reference :

        VR(k) = Var(r_k) / (k * Var(r_1))

    ou r_1 est le rendement sur UN cycle (10 s ici) et r_k sur k
    cycles.

        VR < 1   les mouvements se DEFONT -- du bruit
        VR = 1   marche au hasard
        VR > 1   les mouvements PERSISTENT -- il se passe quelque chose

    L echelle ou VR franchit 1 est exactement "l unite ou on commence
    a voir quelque chose en cas de reverse". Elle n a aucune raison
    d etre la meme sur trois actifs qui n ont ni la meme volatilite en
    points, ni les memes volumes, ni la meme facon de faire des
    spikes.

CE QU ON EN FERA

    L unite de bruit d un actif servira de TAMPON pour la definition
    d une cassure : sortir d un range ne comptera que si le prix
    depasse le bord de plus de k fois le mouvement median a cette
    echelle. Aujourd hui le tampon est nul -- franchir d un centieme
    de point compte autant que franchir de dix. Sur l actif le plus
    agite en points, tout franchissement est du bruit ; sur le plus
    calme, aucun ne l est. La definition actuelle avantage donc
    mecaniquement les actifs calmes.

TROIS RESERVES, ECRITES AVANT LES CHIFFRES

    1. Les cycles sont des INSTANTANES a ~10 s, pas des barres. Le
       "rendement" est une difference d instantanes ; l echantillonnage
       lui-meme peut creer de la structure a tres court terme.

    2. Les rendements se CHEVAUCHENT (fenetre glissante). Ca gonfle le
       nombre de points sans ajouter d information : la dispersion de
       VR entre journees, affichee a cote, est le seul juge honnete de
       sa stabilite.

    3. Les nuits et les week-ends sont des trous. On calcule DANS
       chaque journee, jamais a cheval.

Lecteur SEUL : lit les CSV de cartes\cycles\, ecrit un .txt.
"""
import argparse
import csv
import io
import math
import os
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "cycles")
SORTIE = os.path.join("cartes", "panel_bruit.txt")
ACTIFS = ("US30", "US500", "US100")
MINUTES = (0.5, 1, 2, 3, 5, 10, 15, 30)
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
    jours = {}
    if not os.path.isdir(dossier):
        return jours
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("cycles_") or not nom.endswith(".csv"):
            continue
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            L = [r for r in csv.DictReader(f, delimiter=";")]
        if L:
            jours[nom[7:-4]] = L
    return jours


def pas_median(jours):
    p = []
    for L in jours.values():
        for k in range(1, min(len(L), 300)):
            try:
                t0 = dt.datetime.strptime(L[k - 1]["ts"][:19],
                                          "%Y-%m-%d %H:%M:%S")
                t1 = dt.datetime.strptime(L[k]["ts"][:19],
                                          "%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError, TypeError):
                continue
            d = (t1 - t0).total_seconds()
            if 0 < d < 600:
                p.append(d)
    p.sort()
    return p[len(p) // 2] if p else 10.0


def variance(v):
    n = len(v)
    if n < 2:
        return None
    m = sum(v) / n
    return sum((x - m) ** 2 for x in v) / (n - 1)


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    return v[len(v) // 2]


def une_journee(px, ks):
    """Pour une journee et un actif : la variance des rendements a
    chaque horizon k, et le mouvement absolu median.

    Les rendements se chevauchent -- px[i+k] - px[i] pour tout i. Ca
    n ajoute pas d information independante, seulement de la
    stabilite ; c est pour ca que la dispersion ENTRE journees est
    affichee a cote du resultat."""
    out = {}
    n = len(px)
    for k in ks:
        d = []
        for i in range(0, n - k):
            a, b = px[i], px[i + k]
            if a is None or b is None:
                continue
            d.append(b - a)
        if len(d) < 30:
            continue
        out[k] = (variance(d), mediane([abs(x) for x in d]), len(d))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--actif", default=None)
    p.add_argument("--minutes", default=",".join(str(x) for x in MINUTES))
    a = p.parse_args()
    mins = [float(x) for x in a.minutes.split(",") if x.strip()]

    jours = charge(a.entree)
    if not jours:
        print("KO : aucun CSV dans %s." % a.entree)
        print("     Lance d abord : python extraire_cycles.py")
        return 1
    cyc = pas_median(jours)
    actifs = [a.actif] if a.actif else list(ACTIFS)
    ks = []
    for m in mins:
        k = int(round(m * 60.0 / cyc))
        if k >= 1 and k not in [x[0] for x in ks]:
            ks.append((k, m))

    dis("=" * LARG)
    dis("A QUELLE ECHELLE CHAQUE ACTIF CESSE D ETRE DU BRUIT")
    dis("=" * LARG)
    dis("  %d journees, pas median %.0f s." % (len(jours), cyc))
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
    dis("  VR(k) = Var(r_k) / (k x Var(r_1)), r_1 = un cycle de %.0f s."
        % cyc)
    dis()
    dis("    VR < 1   les mouvements se DEFONT       -- du bruit")
    dis("    VR = 1   marche au hasard")
    dis("    VR > 1   les mouvements PERSISTENT      -- il se passe")
    dis("             quelque chose")
    dis()
    dis("  L echelle ou VR franchit 1 est ce que l utilisateur appelle")
    dis("  \"l unite ou on commence a voir quelque chose en cas de")
    dis("  reverse\". Elle n a aucune raison d etre la meme sur trois")
    dis("  actifs qui n ont ni la meme volatilite en points, ni les")
    dis("  memes volumes, ni la meme facon de faire des spikes.")
    dis()
    dis("  Les rendements se chevauchent : la colonne `entre jours` est")
    dis("  le seul juge de la stabilite de VR, pas le nombre de points.")
    dis("=" * LARG)

    resume = {}
    for actif in actifs:
        dis()
        dis("-" * LARG)
        dis("ACTIF %s" % actif)
        dis("-" * LARG)
        dis("  %-9s %8s %10s %12s %14s"
            % ("horizon", "VR", "entre jours", "|move| med", "cycles"))
        # variance de reference : un cycle, cumulee sur les journees
        par_jour = {}
        for j, L in jours.items():
            px = [flt(r.get("%s_bid" % actif)) for r in L]
            par_jour[j] = une_journee(px, [k for k, _ in ks] + [1])
        base = [v[1][0] for v in par_jour.values()
                if 1 in v and v[1][0] and v[1][0] > 0]
        if not base:
            dis("  Aucune variance de reference calculable.")
            continue
        v1 = sum(base) / len(base)
        lignes = []
        for k, m in ks:
            vrs = []
            for j, d in par_jour.items():
                if k in d and 1 in d and d[1][0] and d[1][0] > 0:
                    vrs.append(d[k][0] / (k * d[1][0]))
            if len(vrs) < 3:
                continue
            vr = sum(vrs) / len(vrs)
            et = math.sqrt(variance(vrs) or 0.0)
            med = mediane([d[k][1] for d in par_jour.values() if k in d])
            npts = sum(d[k][2] for d in par_jour.values() if k in d)
            lignes.append((m, k, vr, et, med, npts))
            dis("  %6.1f min %8.2f %10.2f %12.2f %14d"
                % (m, vr, et, med or 0.0, npts))
        # Ou VR franchit 1 -- SI le franchissement survit a la
        # dispersion entre journees.
        #
        # En balayant huit horizons on finit toujours par trouver un
        # passage au-dessus de 1. Sur le banc, une marche au hasard
        # pure "franchissait" entre 15 et 30 min : VR allait de 0,95 a
        # 1,08 avec un ecart-type entre journees de 0,22 et 0,39. Un
        # franchissement noye dans sa propre dispersion n en est pas
        # un.
        #
        # On exige donc que le point AU-DESSUS soit au-dessus de 1 de
        # plus d une erreur type (ecart-type / racine du nombre de
        # journees), et que le point EN DESSOUS le soit en dessous de
        # la meme facon.
        # Le franchissement peut aller dans LES DEUX SENS, et c est
        # le sens qui porte le sens.
        #
        # Vers le HAUT : les mouvements cessent de se defaire, ils
        # commencent a persister. Vers le BAS : l inverse -- au-dela de
        # cette echelle le prix defait ce qu il vient de faire, c est
        # un regime de range.
        #
        # Une premiere version ne cherchait QUE le franchissement vers
        # le haut. Sur les donnees reelles, les trois actifs partent de
        # ~1,05 et descendent a ~0,75 : aucun franchissement montant,
        # donc elle se rabattait sur "VR >= 1 des le premier point, les
        # mouvements persistent" -- l exact contraire de ce que son
        # propre tableau affichait. Un verdict qui contredit sa table
        # est pire qu absent.
        nj = max(1, len(par_jour))
        seuil = sens = None
        for i in range(1, len(lignes)):
            av, ap = lignes[i - 1], lignes[i]
            se_av = av[3] / math.sqrt(nj)
            se_ap = ap[3] / math.sqrt(nj)
            if av[2] + se_av < 1.0 <= ap[2] - se_ap:
                seuil, sens = ap, "HAUT"
                break
            if av[2] - se_av > 1.0 >= ap[2] + se_ap:
                seuil, sens = ap, "BAS"
                break
        dis()
        if seuil and sens == "HAUT":
            dis("  => VR franchit 1 VERS LE HAUT entre %.1f et %.1f min."
                % (lignes[lignes.index(seuil) - 1][0], seuil[0]))
            dis("     Au-dela, les mouvements persistent. Unite de bruit")
            dis("     retenue : %.1f min, mouvement median %.2f points."
                % (seuil[0], seuil[4] or 0.0))
            resume[actif] = (seuil[0], seuil[4])
        elif seuil and sens == "BAS":
            dis("  => VR franchit 1 VERS LE BAS entre %.1f et %.1f min."
                % (lignes[lignes.index(seuil) - 1][0], seuil[0]))
            dis("     Au-dela de cette echelle le prix DEFAIT ce qu il")
            dis("     vient de faire : c est un regime de range, et il")
            dis("     s installe a partir de %.1f min." % seuil[0])
            dis("     Unite de bruit retenue : %.1f min, mouvement median"
                " %.2f points." % (seuil[0], seuil[4] or 0.0))
            resume[actif] = (seuil[0], seuil[4])
        elif lignes and all(abs(x[2] - 1.0) <= x[3] / math.sqrt(nj)
                            for x in lignes):
            dis("  => VR est indiscernable de 1 sur toute la plage : ce")
            dis("     prix se comporte comme une marche au hasard aux")
            dis("     echelles regardees. Aucune unite de bruit ne s en")
            dis("     degage -- et c est une reponse, pas un echec.")
        elif lignes and lignes[0][2] >= 1.0:
            dis("  => VR est deja >= 1 des %.1f min : aucune echelle de"
                % lignes[0][0])
            dis("     bruit detectable dans la plage examinee. Les")
            dis("     mouvements persistent des le premier cycle.")
            resume[actif] = (lignes[0][0], lignes[0][4])
        else:
            dis("  => VR reste < 1 sur toute la plage : les mouvements se")
            dis("     defont jusqu a %.0f min. L unite de bruit est"
                % lignes[-1][0] if lignes else 0)
            dis("     au-dela de ce qu on regarde ici.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA DONNE COMME TAMPON")
    dis("=" * LARG)
    if not resume:
        dis("  Aucune echelle determinee -- pas de tampon a proposer.")
    else:
        dis("  %-8s %10s %14s" % ("actif", "echelle", "|move| median"))
        for actif in actifs:
            if actif in resume:
                dis("  %-8s %8.1f min %12.2f pts"
                    % (actif, resume[actif][0], resume[actif][1] or 0.0))
        dis()
        dis("  Une cassure ne comptera que si le prix depasse le bord du")
        dis("  range de plus de k fois ce mouvement median, avec k")
        dis("  BALAYE (0 / 0,5 / 1 / 2) et non choisi. A k = 0 on")
        dis("  retrouve le comportement actuel, ce qui permet de voir")
        dis("  exactement ce que le tampon change.")
    dis()
    dis("  RESERVE : les cycles sont des instantanes a ~%.0f s, pas des"
        % cyc)
    dis("  barres. Une partie de ce qui apparait comme du bruit a tres")
    dis("  court terme peut venir de l echantillonnage lui-meme, pas du")
    dis("  marche. Ca ne change pas le classement entre actifs -- ils")
    dis("  sont echantillonnes pareil -- mais ca interdit de lire la")
    dis("  valeur absolue de VR a 0,5 min comme une propriete du prix.")

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (a.sortie, os.path.getsize(a.sortie)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
