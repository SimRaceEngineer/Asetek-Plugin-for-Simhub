# -*- coding: utf-8 -*-
r"""
patch_doublons.py -- deux corrections a reaction_evenements.py

  python patch_doublons.py

CE QU IL CORRIGE, ET POURQUOI CE N EST PAS COSMETIQUE

1. LES MEMES BARRES COMPTEES TROIS FOIS

    Ta propre sortie l a dit avant moi :

        "ATTENTION avant de mesurer : le fichier continu ET les
         fichiers par echeance sont tous les deux dans cartes\scid\."

    of_MES-continu.csv contient DEJA les barres de of_MESM26-CME.csv et
    de of_MESU26-CME.csv. lis_barres() lit les trois fichiers, donc le
    tableau sort trois blocs dont deux sont des sous-ensembles du
    troisieme. Rien ne plante ; simplement, devant trois resultats, on
    finit par retenir celui qui parle le mieux. C est exactement la
    faute qu on essaie d empecher partout ailleurs.

    La correction ne deplace aucun fichier -- un deplacement se refait
    a l envers a la prochaine execution, et un `.gitignore` de plus
    n aiderait personne. Elle LIT la colonne `contrat` du raccord : les
    echeances qu il nomme sont celles qu il contient. Mesure, pas
    devine. Et elle AFFICHE ce qu elle ecarte : une exclusion
    silencieuse vaudrait l erreur qu elle corrige.

2. $TICK-NYSE MESURE EN POURCENT

        15min  -94 %    30min  +63 %    60min  -145 %    1j  -264 %

    Ces nombres n ont aucun sens, et la cause est double.

    D abord `lis_barres` filtrait `if t and c and c > 0` : toute valeur
    negative ou nulle etait jetee SANS UN MOT. Sur un prix ce filtre ne
    fait rien. Sur le TICK -- le nombre de valeurs NYSE en hausse moins
    celles en baisse -- il supprime la moitie de la serie et ne garde
    que les moments haussiers.

    Ensuite (p1-p0)/p0 suppose que p0 est une echelle. Le TICK oscille
    autour de zero : diviser par une base de +3 mesure la petitesse de
    la base, pas le mouvement.

    Le choix de l unite se decide donc SUR LA SERIE : si elle prend les
    deux signes, on mesure en points. Le test n est pas ecrit en dur
    pour un symbole nomme -- il vaudra pour le prochain oscillateur
    qu on ajoutera sans y penser.

CE QU IL NE FAIT PAS

    Il ne touche pas au filtre d occurrences. Les 22 evenements restent
    `EIA Crude Oil Stocks Change` et `Initial Jobless Claims` : deux
    series hebdomadaires, zero CPI, zero NFP, zero Fed. C est un autre
    probleme, et le melanger a celui-ci rendrait les deux illisibles.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "reaction_evenements.py"
MARQUE = "def ecarte_doublons("

# ---------------------------------------------------------------- 1
A1 = '''                t = horo(r.get("ts"))
                c = flt(r.get("close"))
                d = flt(r.get("delta"))
                if t and c and c > 0:
'''
B1 = '''                t = horo(r.get("ts"))
                c = flt(r.get("close"))
                d = flt(r.get("delta"))
                # `c > 0` ecartait SILENCIEUSEMENT toute valeur
                # negative ou nulle. Sur un prix, sans effet. Sur
                # $TICK-NYSE, qui oscille autour de zero, ca supprimait
                # la moitie des barres et ne gardait que les moments
                # haussiers -- d ou des pourcentages a -94, +63, -145,
                # -264 %. On garde tout ce qui est numerique ; c est
                # `unite()` qui decide ensuite comment le mesurer.
                if t and c is not None:
'''

# ---------------------------------------------------------------- 2
A2 = 'def prix_a(serie, cible, tolerance, rend_index=False):\n'
B2 = '''def ecarte_doublons(barres):
    """Un fichier continu contient DEJA les barres de ses echeances.

    contrat_continu.py ecrit of_MES-continu.csv avec une colonne
    `contrat` qui nomme, barre par barre, l echeance d origine. Si
    of_MESM26-CME.csv et of_MESU26-CME.csv sont restes dans le meme
    dossier, lis_barres() les lit AUSSI : les memes barres sont
    comptees deux fois, une fois seules et une fois dans le raccord.

    Rien ne plante. Le tableau sort trois blocs dont deux sont des
    sous-ensembles du troisieme -- et devant trois resultats on finit
    par retenir celui qui parle le mieux.

    On n ecarte rien sur un nom de fichier : on lit la colonne
    `contrat`. Les echeances qu un raccord nomme sont celles qu il
    contient. Un fichier produit par lire_scid.py n a pas cette
    colonne, donc il n absorbe personne.
    """
    absorbes = {}
    for sym, serie in barres.items():
        noms = set(x[3] for x in serie if len(x) > 3 and x[3])
        if not noms:
            continue                      # pas un raccord
        for n in noms:
            if n != sym and n in barres:
                absorbes[n] = sym
    if not absorbes:
        return barres
    for n in sorted(absorbes):
        _DOUBLONS.append("  of_%s.csv ECARTE : ses %d barres sont deja"
                         % (n, len(barres[n])))
        _DOUBLONS.append("  dans of_%s.csv, qui les nomme dans sa"
                         % absorbes[n])
        _DOUBLONS.append("  colonne `contrat`.")
    _DOUBLONS.append("")
    _DOUBLONS.append("  Sans cette exclusion les memes barres seraient")
    _DOUBLONS.append("  mesurees deux fois, et le tableau sortirait des")
    _DOUBLONS.append("  blocs dont certains sont des sous-ensembles des")
    _DOUBLONS.append("  autres. Aucun fichier n est deplace ni efface.")
    return dict((s, v) for s, v in barres.items() if s not in absorbes)


def unite(serie):
    """En pourcent ou en points ? La question se tranche sur la serie.

    Un rendement (p1-p0)/p0 suppose que p0 est une ECHELLE : passer de
    100 a 200, c est +100 %. $TICK-NYSE n est pas une echelle, c est un
    compteur signe -- valeurs NYSE en hausse moins celles en baisse --
    qui traverse zero plusieurs fois par heure. Diviser par une base de
    +3 ne mesure que la petitesse de la base.

    Le test : une serie strictement positive a une echelle, on mesure
    en pourcent. Sinon on mesure en points. Ecrit comme ca, il vaudra
    aussi pour le prochain oscillateur qu on ajoutera sans y penser --
    un delta, un spread, une difference d indices.
    """
    vmin = min(x[1] for x in serie)
    vmax = max(x[1] for x in serie)
    if vmin > 0:
        return True, ("serie strictement positive (min %.1f) : elle a "
                      "une echelle, le pourcentage a un sens" % vmin)
    return False, ("la serie traverse zero (min %.1f, max %.1f) : pas "
                   "d echelle, donc pas de pourcentage" % (vmin, vmax))


def prix_a(serie, cible, tolerance, rend_index=False):
'''

# ---------------------------------------------------------------- 3
A3 = 'def reaction(serie, t0, horizons_min, horizons_j, tol, jours=None):\n'
B3 = ('def reaction(serie, t0, horizons_min, horizons_j, tol, jours=None,\n'
      '             pourcent=True):\n')

# ---------------------------------------------------------------- 4
A4 = '        out[lab] = (serie[i1][1] - base) / base * 100.0\n'
B4 = '''        # En pourcent si la serie est un prix, en points si elle
        # traverse zero. Le choix vient de unite(), donc de la serie
        # elle-meme, et non d une liste de symboles ecrite a la main.
        if pourcent:
            out[lab] = (serie[i1][1] - base) / base * 100.0
        else:
            out[lab] = serie[i1][1] - base
'''

# ---------------------------------------------------------------- 5
A5 = '''_ECARTES_BASE = [0]
'''
B5 = '''_ECARTES_BASE = [0]

# Les exclusions de doublons, gardees pour etre affichees au moment ou
# le rapport commence -- lis_barres() tourne avant l en-tete.
_DOUBLONS = []
'''

# ---------------------------------------------------------------- 6
A6 = '    barres = lis_barres(a.scid)\n'
B6 = '''    barres = lis_barres(a.scid)
    barres = ecarte_doublons(barres)
'''

# ---------------------------------------------------------------- 7
A7 = '''    if barres:
        for nom, serie in sorted(barres.items())[:3]:
'''
B7 = '''    for s in _DOUBLONS:
        dis(s)
    if _DOUBLONS:
        dis()
    if barres:
        for nom, serie in sorted(barres.items())[:3]:
'''

# ---------------------------------------------------------------- 8
A8 = '''    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
'''
B8 = '''    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
    for s in _DOUBLONS:
        dis(s)
    if _DOUBLONS:
        dis()
'''

# ---------------------------------------------------------------- 9
A9 = '''            % (sym, len(serie), serie[0][0].strftime("%Y-%m-%d"),
               serie[-1][0].strftime("%Y-%m-%d")))
        dis("-" * LARG)
'''
B9 = '''            % (sym, len(serie), serie[0][0].strftime("%Y-%m-%d"),
               serie[-1][0].strftime("%Y-%m-%d")))
        dis("-" * LARG)
        pourcent, motif = unite(serie)
        dis("  Unite : %s -- %s"
            % ("POURCENT" if pourcent else "POINTS", motif))
'''

# --------------------------------------------------------------- 10
A10 = '''        dis("  PRIX -- en % depuis l instant de publication")
'''
B10 = '''        dis("  PRIX -- en %s depuis l instant de publication"
            % ("%" if pourcent else "points"))
'''

# --------------------------------------------------------------- 11
A11 = '''        r_ev = [reaction(serie, e["t"], MINUTES, JOURS, a.tolerance,
                         jours_b) for e in dans]
        r_tm = [reaction(serie, t, MINUTES, JOURS, a.tolerance,
                         jours_b) for t in temoins]
'''
B11 = '''        r_ev = [reaction(serie, e["t"], MINUTES, JOURS, a.tolerance,
                         jours_b, pourcent) for e in dans]
        r_tm = [reaction(serie, t, MINUTES, JOURS, a.tolerance,
                         jours_b, pourcent) for t in temoins]
'''

# --------------------------------------------------------------- 12
A12 = '''            dis("  %-8s %8d %9.3f%% %9.3f%% %9.3f%%"
                % (k, len(a1), m1, m2, m1 - m2))
'''
B12 = '''            if pourcent:
                dis("  %-8s %8d %9.3f%% %9.3f%% %9.3f%%"
                    % (k, len(a1), m1, m2, m1 - m2))
            else:
                dis("  %-8s %8d %9.1f  %9.1f  %9.1f"
                    % (k, len(a1), m1, m2, m1 - m2))
'''

REMPLACEMENTS = [
    ("filtre c > 0 dans lis_barres", A1, B1),
    ("fonctions ecarte_doublons() et unite()", A2, B2),
    ("signature de reaction()", A3, B3),
    ("calcul du rendement", A4, B4),
    ("liste _DOUBLONS", A5, B5),
    ("appel a ecarte_doublons() dans main", A6, B6),
    ("affichage des doublons dans --verifie", A7, B7),
    ("affichage des doublons dans l en-tete", A8, B8),
    ("unite affichee par symbole", A9, B9),
    ("titre de la table PRIX", A10, B10),
    ("passage de l unite a reaction()", A11, B11),
    ("format des lignes de la table PRIX", A12, B12),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable. Se placer dans analyse\\." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique : `%s` est present dans %s." % (MARQUE, CIBLE))
        print("Rien n a ete touche. Reappliquer un patch ancre deux fois")
        print("produit du code duplique qui compile -- c est la panne la")
        print("plus penible a lire ensuite.")
        return 0

    # On verifie TOUTES les ancres avant d en appliquer UNE SEULE.
    # Un patch a moitie applique laisse un fichier qui ne compile pas
    # et une sauvegarde qu on hesite a restaurer.
    manque = []
    for nom, a, _ in REMPLACEMENTS:
        n = src.count(a)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-46s %d occurrence(s), attendu 1" % (nom, n))
        print()
        print("Le fichier a change depuis que ce patch a ete ecrit.")
        return 1

    out = src
    for nom, a, b in REMPLACEMENTS:
        out = out.replace(a, b, 1)

    # Compiler AVANT de remplacer l original. Une erreur de syntaxe
    # decouverte apres l ecriture, c est une restauration a faire a la
    # main sur une machine qui tourne en production.
    try:
        compile(out, CIBLE, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1

    sauv = CIBLE + ".avant_doublons"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacements."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("Ce qui va changer dans la sortie :")
    print("  - les of_MESM26 / of_MESU26 disparaissent du rapport, avec")
    print("    la raison affichee. Aucun fichier n est deplace.")
    print("  - $TICK-NYSE est mesure en POINTS, et ses barres negatives")
    print("    ne sont plus jetees en silence.")
    print()
    print("Relancer : python reaction_evenements.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
