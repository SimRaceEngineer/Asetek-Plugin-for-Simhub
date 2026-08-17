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

    Elle n a aucune raison d etre la meme sur trois actifs qui n ont
    ni la meme volatilite en points, ni les memes volumes, ni la meme
    facon de faire des spikes.

DEUX GARDE-FOUS SUR LA LECTURE DE CETTE COURBE

    Le PLANCHER DE COTATION. Aux horizons les plus courts le prix n a
    bouge que d un tic ou de rien du tout : le mouvement median du
    US500 a 30 s vaut 0,25 point, c est-a-dire exactement un tic. La
    variance d une variable qui ne prend que deux valeurs ne mesure
    plus le marche, elle mesure l arrondi. Tout horizon dont le
    mouvement median tient en trois tics est marque `plancher` et
    EXCLU du verdict -- il reste affiche, parce qu on ne cache pas une
    ligne, mais il ne peut pas designer une echelle.

    UN SEUL POINT NE FAIT PAS UN REGIME. En balayant huit horizons on
    finit toujours par en trouver un a plus d une erreur type de 1 :
    c est ce que fait un balayage. On exige donc que l ecart soit
    CONFIRME par l horizon suivant, dans le meme sens.

CE QUE LE VERDICT DESIGNE

    Pas le premier franchissement -- il depend du plancher et du pas
    d echantillonnage. L horizon ou le RETOUR EN ARRIERE est le plus
    net : celui dont le VR s ecarte de 1 vers le bas du plus grand
    nombre d erreurs types. C est litteralement "l echelle ou on
    commence a voir quelque chose en cas de reverse", et la colonne
    `z` du tableau permet de verifier a l oeil que le verdict lit bien
    la meme chose que la table.

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


def pas_cotation(ecarts):
    """Le plus petit ecart de prix que l instrument sait exprimer.

    On ne le declare pas en dur : le CSV le contient. On compte tous
    les ecarts NON NULS d un cycle a l autre et on retient la plus
    petite valeur qui revient assez souvent pour ne pas etre un
    accident d arrondi (2 % des ecarts). Un minimum brut se ferait
    piloter par une seule ligne aberrante."""
    if not ecarts:
        return None
    compte = {}
    for d in ecarts:
        v = round(abs(d), 6)
        if v <= 0:
            continue
        compte[v] = compte.get(v, 0) + 1
    if not compte:
        return None
    total = sum(compte.values())
    for v in sorted(compte):
        if compte[v] >= total * 0.02:
            return v
    return min(compte)


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
    dis("  On ne retient PAS le premier franchissement de 1 : il depend")
    dis("  du plancher de cotation et du pas d echantillonnage, pas du")
    dis("  marche. On retient l horizon ou VR s ecarte le plus de 1 VERS")
    dis("  LE BAS -- l echelle ou le retour en arriere est le plus net,")
    dis("  c est-a-dire \"l unite ou on commence a voir quelque chose en")
    dis("  cas de reverse\". Elle n a aucune raison d etre la meme sur")
    dis("  trois actifs qui n ont ni la meme volatilite en points, ni")
    dis("  les memes volumes, ni la meme facon de faire des spikes.")
    dis()
    dis("  Deux exigences avant qu un horizon puisse etre retenu : son")
    dis("  mouvement median doit depasser trois tics (sinon VR mesure")
    dis("  l arrondi), et son ecart doit etre CONFIRME par l horizon")
    dis("  suivant (sinon un balayage de huit horizons finit toujours")
    dis("  par en trouver un).")
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
        dis("  %-9s %8s %10s %12s %8s %10s   %s"
            % ("horizon", "VR", "entre jours", "|move| med", "z",
               "cycles", "marque"))
        # variance de reference : un cycle, cumulee sur les journees
        par_jour = {}
        ecarts1 = []
        for j, L in jours.items():
            px = [flt(r.get("%s_bid" % actif)) for r in L]
            par_jour[j] = une_journee(px, [k for k, _ in ks] + [1])
            for i in range(len(px) - 1):
                x0, x1 = px[i], px[i + 1]
                if x0 is not None and x1 is not None:
                    ecarts1.append(x1 - x0)
        tic = pas_cotation(ecarts1)
        plancher = (tic or 0.0) * 3.0
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
            se = et / math.sqrt(max(1, len(par_jour)))
            z = (vr - 1.0) / se if se > 0 else 0.0
            au_plancher = plancher > 0 and (med or 0.0) <= plancher
            lignes.append((m, k, vr, et, med, npts, z, au_plancher))
            dis("  %6.1f min %8.2f %10.2f %12.2f %8.1f %10d   %s"
                % (m, vr, et, med or 0.0, z, npts,
                   "plancher" if au_plancher else ""))
        dis()
        dis("  pas de cotation lu dans les donnees : %s ; un horizon dont"
            % ("%.2f pt" % tic if tic else "indeterminable"))
        dis("  le mouvement median tient en trois tics (<= %.2f) est"
            % plancher)
        dis("  marque `plancher` : il mesure l arrondi, pas le marche.")
        # LE VERDICT. Quatrieme version de cette logique. Les trois
        # premieres affirmaient le contraire de leur propre tableau, et
        # c est la seule raison pour laquelle la colonne `z` existe
        # maintenant : un verdict doit pouvoir etre verifie a l oeil
        # sur la ligne qu il commente.
        #
        # v1 ne cherchait qu un franchissement VERS LE HAUT. Les trois
        # actifs descendent : aucun trouve, branche par defaut, verdict
        # "les mouvements persistent" sous une colonne allant de 1,06 a
        # 0,76.
        #
        # v2 exigeait un point significativement AU-DESSUS de 1 suivi
        # d un point significativement en dessous. Or les courbes
        # PARTENT de 1 : aucun couple ne passait, meme branche par
        # defaut, meme phrase fausse. Une condition plus stricte n est
        # pas une condition plus prudente.
        #
        # v3 prenait le PREMIER horizon a plus d une erreur type de 1.
        # Il tombait sur 0,5 min pour US30 et US500 -- ou le mouvement
        # median du US500 vaut 0,25 point, c est-a-dire UN TIC. Le
        # tampon propose valait donc un tic, et la reserve imprimee dix
        # lignes plus bas disait deja de ne pas lire cet horizon-la.
        #
        # v4 : on ecarte les horizons au plancher de cotation, on exige
        # que l ecart soit confirme par l horizon suivant, et on
        # designe non pas le premier ecart mais le PLUS GRAND vers le
        # bas -- l echelle ou le retour en arriere est le plus net.
        # Cout assume : le dernier horizon de la plage ne peut jamais
        # etre confirme, donc jamais retenu.
        util = [x for x in lignes if not x[7]]
        conf = None
        for i in range(len(util) - 1):
            x, y = util[i], util[i + 1]
            if x[6] <= -1.0 and y[6] <= -1.0:
                conf = (x, "DEFAIT")
                break
            if x[6] >= 1.0 and y[6] >= 1.0:
                conf = (x, "PERSISTE")
                break
        # le creux : l horizon le plus negatif, confirme par son voisin
        creux = None
        for i in range(len(util) - 1):
            x = util[i]
            if x[6] <= -1.0 and util[i + 1][6] <= -1.0:
                if creux is None or x[6] < creux[6]:
                    creux = x
        dis()
        # "Rien de mesurable" et "rien d ecarte" ne sont pas la meme
        # reponse. Sur le banc, un actif dont TOUS les horizons
        # tenaient sous trois tics recevait la phrase "VR reste a moins
        # d une erreur type de 1" au-dessus d une colonne allant de
        # 0,47 a 0,18. C est la quatrieme fois que ce fichier ecrit une
        # phrase que sa propre table contredit ; celle-la a ete
        # attrapee sur banc et pas en production.
        if len(util) < 2:
            dis("  => NON MESURABLE sur cette plage. %d horizon(s) sur %d"
                % (len(util), len(lignes)))
            dis("     seulement echappent au plancher de cotation : a")
            dis("     toutes les autres echelles le mouvement median tient")
            dis("     en trois tics de %.2f pt, donc VR y mesure l arrondi."
                % (tic or 0.0))
            dis("     Les valeurs de VR affichees ci-dessus sont reelles")
            dis("     mais ininterpretables ; il faut des horizons plus")
            dis("     longs pour cet actif, pas une autre statistique.")
        elif creux is not None:
            dis("  => Le retour en arriere est le plus net a %.1f min :"
                % creux[0])
            dis("     VR = %.2f, soit %.1f erreurs types SOUS 1. A cette"
                % (creux[2], creux[6]))
            dis("     echelle le prix DEFAIT ce qu il vient de faire.")
            dis("     Unite de bruit : %.1f min, mouvement median %.2f pts."
                % (creux[0], creux[4] or 0.0))
            if plancher > 0 and (creux[4] or 0.0) <= plancher + (tic or 0.0):
                dis("     ATTENTION : ce mouvement median n est qu a un tic")
                dis("     au-dessus du plancher (%.2f). Le verdict tient a"
                    % plancher)
                dis("     un cran de quantification. A ne pas transformer en")
                dis("     tampon sans l avoir revu sur des horizons plus")
                dis("     longs, ou sur des barres plutot que des cycles.")
            if conf and conf[0][0] != creux[0]:
                dis("     (Premier ecart confirme : %.1f min, z = %.1f,"
                    % (conf[0][0], conf[0][6]))
                dis("     %s. Ce n est pas lui qu on retient.)" % conf[1])
            resume[actif] = (creux[0], creux[4], "defait")
        elif conf and conf[1] == "PERSISTE":
            dis("  => Aucun horizon ne montre de retour en arriere")
            dis("     confirme. En revanche VR est au-dessus de 1 des")
            dis("     %.1f min (z = %.1f), confirme par l horizon suivant :"
                % (conf[0][0], conf[0][6]))
            dis("     les mouvements PERSISTENT. Ce n est pas une echelle")
            dis("     de bruit, c est son contraire -- aucun tampon n en")
            dis("     sort.")
        else:
            dis("  => VR reste a moins d une erreur type de 1, ou son")
            dis("     ecart n est jamais confirme par l horizon suivant,")
            dis("     sur toute la plage hors plancher : indiscernable")
            dis("     d une marche au hasard aux echelles regardees.")
            dis("     Aucune unite de bruit ne s en degage -- et c est une")
            dis("     reponse, pas un echec.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA DONNE COMME TAMPON")
    dis("=" * LARG)
    if not resume:
        dis("  Aucune echelle determinee -- pas de tampon a proposer.")
    else:
        dis("  %-8s %10s %14s %12s"
            % ("actif", "echelle", "|move| median", "regime"))
        for actif in actifs:
            if actif in resume:
                dis("  %-8s %8.1f min %12.2f pts %12s"
                    % (actif, resume[actif][0], resume[actif][1] or 0.0,
                       resume[actif][2]))
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
