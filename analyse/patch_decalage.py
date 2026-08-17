# -*- coding: utf-8 -*-
r"""
patch_decalage.py -- le delta PRECEDE-t-il le prix, ou l accompagne-t-il ?

  python patch_decalage.py
  puis : python flux_contre_prix.py --bloc 60 --decalage 1

LA QUESTION QUI DECIDE DE TOUT

    Tout ce qui a ete mesure le 17/08 est SIMULTANE : le delta d un
    bloc et le rendement du MEME bloc.

        MES  rho 0.675   YM  rho 0.296   p = 0.0005

    Chaque sortie le repete deja : "un flux qui pousse le prix et un
    prix qui attire le flux donnent exactement la meme correlation".
    Une correlation simultanee est donc compatible avec ces deux
    lectures, et une seule des deux a une valeur operationnelle.

        Si le flux PRECEDE le prix, un flux live est un signal.
        Si le flux ACCOMPAGNE le prix, un flux live est un compte
        rendu -- exact, instructif, et sans avance sur le marche.

    On n a mesure ni l une ni l autre. Avant de payer un abonnement,
    de brancher un flux temps reel ou d en faire quoi que ce soit dans
    la stack, c est CETTE mesure qu il faut, et elle ne demande aucune
    donnee nouvelle.

CE QUE FAIT LE CORRECTIF

    `--decalage K` correle le delta du bloc N au rendement du bloc
    N+K, au lieu du bloc N.

    Le decalage ne franchit JAMAIS une journee : le bloc N+1 doit
    exister le meme jour. Sinon on correlerait la derniere heure d une
    seance a la premiere de la suivante, en enjambant la nuit, la
    reouverture et parfois un week-end.

    Avec `--bloc 0`, le decalage se fait de seance a seance
    consecutive, ce qui reste une question legitime : le flux d
    aujourd hui dit-il quelque chose du rendement de demain ?

COMMENT LIRE LE RESULTAT

    rho decale proche de ZERO
        Le flux ne precede pas le prix. Il le decrit. Un flux live n
        est alors pas un signal d entree -- ce qui ne le rend pas
        inutile, mais interdit de le vendre comme une avance.

    rho decale FRANCHEMENT POSITIF
        Le flux d une heure porte sur le rendement de la suivante.
        C est une avance mesurable, et tout le reste en decoule.

    rho decale NEGATIF
        Le mouvement se retourne apres coup -- signature d absorption
        ou d epuisement. Aussi exploitable que le cas positif, en sens
        inverse.

    Dans les trois cas la comparaison avec le rho SIMULTANE dit la
    part respective de l accompagnement et de l avance.

CE QUE CA NE DIRA TOUJOURS PAS

    Aucun euro. Une correlation de rang sur des blocs horaires n est
    pas un PnL : le passage a l euro exige des tickets, des frais et
    un spread, et il passe par churn_trades.jsonl.

    Et un rho de 0,2 sur 2500 blocs peut etre tres significatif sans
    etre exploitable une seule fois.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "flux_contre_prix.py"
MARQUE = "--decalage"

A1 = '''    p.add_argument("--bloc", type=int, default=0,
                   help="taille des blocs en minutes ; 0 = la seance")
'''
B1 = '''    p.add_argument("--bloc", type=int, default=0,
                   help="taille des blocs en minutes ; 0 = la seance")
    p.add_argument("--decalage", type=int, default=0,
                   help="correle le delta du bloc N au rendement du "
                        "bloc N+K ; 0 = simultane")
'''

A2 = '''    dis("  %-16s %8s %12s %10s %12s"
        % ("symbole", "n", "rho(d, r)", "p", "flux"))
    informatif = {}
    for sym in sorted(sc):
        js = sorted(sc[sym])
        r = [sc[sym][j][0] for j in js]
        d = [sc[sym][j][1] for j in js]
'''
B2 = '''    if a.decalage:
        dis()
        dis("  DECALAGE DE %d BLOC(S) : le delta du bloc N est correle"
            % a.decalage)
        dis("  au rendement du bloc N+%d. Le decalage ne franchit JAMAIS"
            % a.decalage)
        dis("  une journee -- sinon on correlerait la derniere heure")
        dis("  d une seance a la premiere de la suivante, en enjambant")
        dis("  la nuit et parfois un week-end.")
        dis()
        dis("  Une correlation SIMULTANEE est compatible avec `le flux")
        dis("  pousse le prix` ET avec `le prix attire le flux`. Une")
        dis("  correlation DECALEE ne l est qu avec la premiere. C est")
        dis("  la difference entre un signal et un compte rendu.")
        dis()
    dis("  %-16s %8s %12s %10s %12s"
        % ("symbole", "n", "rho(d, r)", "p", "flux"))
    informatif = {}
    for sym in sorted(sc):
        js = sorted(sc[sym])
        if a.decalage:
            js, r, d = decale(sc[sym], a.decalage, a.bloc > 0)
        else:
            r = [sc[sym][j][0] for j in js]
            d = [sc[sym][j][1] for j in js]
        if len(js) < 30:
            dis("  %-16s %8d   trop peu de paires apres decalage."
                % (sym, len(js)))
            informatif[sym] = False
            continue
'''

A3 = '''def rangs(v):
'''
B3 = '''def decale(sc, k, par_bloc):
    """Le delta du bloc N contre le rendement du bloc N+k.

    Le decalage ne franchit pas la journee. Avec des blocs, le voisin
    est (meme date, index + k) et il doit exister. Avec des seances,
    le voisin est la seance suivante dans l ordre -- une question
    differente mais legitime : le flux d aujourd hui dit-il quelque
    chose du rendement de demain ?

    Rend (cles, rendements decales, deltas) alignes."""
    cles, rr, dd = [], [], []
    if par_bloc:
        for (j, b) in sorted(sc):
            suiv = (j, b + k)
            if suiv in sc:
                cles.append((j, b))
                rr.append(sc[suiv][0])
                dd.append(sc[(j, b)][1])
    else:
        js = sorted(sc)
        for i in range(len(js) - k):
            cles.append(js[i])
            rr.append(sc[js[i + k]][0])
            dd.append(sc[js[i]][1])
    return cles, rr, dd


def rangs(v):
'''

A4 = '''        if a.bloc > 0:
            rho, pv = p_permutation_jour(js, d, r, a.tirages)
        else:
            rho, pv = p_permutation(d, r, a.tirages)
'''
B4 = '''        if a.bloc > 0:
            cles = js if a.decalage else [(x, 0) for x in js] \\
                if not isinstance(js[0], tuple) else js
            rho, pv = p_permutation_jour(cles, d, r, a.tirages)
        elif a.decalage:
            rho, pv = p_permutation_jour([(x, 0) for x in js], d, r,
                                         a.tirages)
        else:
            rho, pv = p_permutation(d, r, a.tirages)
'''

REMPLACEMENTS = [
    ("option --decalage", A1, B1),
    ("annonce et application du decalage", A2, B2),
    ("fonction decale()", A3, B3),
    ("permutation sur les cles decalees", A4, B4),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0

    if "def blocs(" not in src:
        print("KO : patch_echelle.py n a pas ete applique.")
        print("     Lancer d abord : python patch_echelle.py")
        return 1

    manque = []
    for nom, a, _ in REMPLACEMENTS:
        n = src.count(a)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-46s %d occurrence(s), attendu 1" % (nom, n))
        return 1

    out = src
    for nom, a, b in REMPLACEMENTS:
        out = out.replace(a, b, 1)

    try:
        compile(out, CIBLE, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1

    sauv = CIBLE + ".avant_decalage"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacements."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("A COMPARER, DEUX EXECUTIONS :")
    print()
    print("  python flux_contre_prix.py --bloc 60")
    print("  python flux_contre_prix.py --bloc 60 --decalage 1")
    print()
    print("  simultane   MES 0,675   YM 0,296   -- deja mesure")
    print("  decale      ?           ?          -- la question")
    print()
    print("Un rho decale proche de zero : le flux DECRIT le prix, il ne")
    print("le precede pas. Un flux live serait un compte rendu exact et")
    print("sans avance. Franchement non nul : c est une avance mesurable")
    print("et tout le reste en decoule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
