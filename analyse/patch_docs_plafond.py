# -*- coding: utf-8 -*-
"""
patch_docs_plafond.py -- que le REPL lise TOUT, rails trades compris

  python patch_docs_plafond.py --essai
  python patch_docs_plafond.py
  python patch_docs_plafond.py --total 400000 --un 200000

POURQUOI

    panel_rails_trades.txt (102 450 caracteres) n a JAMAIS ete lu par
    le REPL. Personne ne l a exclu : _DOCS_REPL scanne le dossier
    panels par ordre ALPHABETIQUE et empile jusqu a _DOCS_MAX, puis
    fait break. Quand le parcours l atteint, 181 051 caracteres sont
    deja consommes sur 200 000. Il ne rentre pas, et tout ce qui le
    suit alphabetiquement tombe avec lui.

    Le critere de priorite du REPL est donc le NOM DU FICHIER. Pas son
    importance.

    Or ce panneau vient de confirmer H9 par un instrument totalement
    independant du mien -- autre classifieur, autre agregation, autre
    frontiere horaire (14h au lieu de 15h30) -- avec t ~ 7 sur 3 714
    trades. C est le document le plus utile du dossier, et le seul que
    le REPL n avait jamais vu.

DEUX PLAFONDS, PAS UN -- ET C EST LE PIEGE

    _DOCS_MAX     = 200000   caracteres au TOTAL
    _DOCS_MAX_UN  = 100000   caracteres pour UN SEUL document

    Rails trades fait 102 450. Meme avec un total illimite, il serait
    TRONQUE a 100 000 par le second plafond : c est la queue du
    fichier qui sauterait. Lever un seul des deux ne sert a rien.

    La troncature n est PAS silencieuse -- repl_web.py ligne 181 ecrit
    "[... tronque ...]" a l endroit de la coupe. Le modele voit donc
    qu il lui manque quelque chose. Corrige ici : j avais ecrit deux
    fois le contraire.

CE QUE CA COUTE

    Le patch ne devine pas : il SIMULE le parcours de _DOCS_REPL sur
    les fichiers reellement presents, avant et apres, et affiche les
    deux totaux ainsi que les documents qui passent de invisible a
    lu. Le chiffre imprime est donc mesure sur ce disque, pas repris
    d une note.

    C est deja la taille du prompt qui fait tronquer les reponses. Il
    y a donc trois issues possibles, et il faut les connaitre AVANT :

      1. ca passe -- le REPL lit tout, les reponses restent completes ;
      2. les reponses se tronquent plus tot -- prompt + completion ne
         tiennent plus dans la fenetre ;
      3. l API REFUSE l appel avec une erreur de contexte.

    Dans les cas 2 et 3 :  --total 200000 --un 100000  restaure l etat
    d aujourd hui. Cette marche arriere FONCTIONNE : les ancres sont
    reperees par le NOM de la constante, pas par sa valeur, donc le
    patch se rejoue dans les deux sens autant de fois qu on veut.
    (Version precedente : les ancres portaient la valeur 200000/100000
    en dur, si bien que le patch refusait de se rejouer une fois
    applique -- la marche arriere documentee etait morte. Corrige.)

CE QUI NE SERT A RIEN DE PLUS

    panel_quadruple.txt contient une COPIE integrale de
    panel_x60_onset.txt (patch --joindre du 14/08, pour que le panneau
    soit lisible en un seul onglet). Le REPL charge donc deux fois le
    meme contenu : ~28 756 caracteres, soit ~8 000 jetons, pour zero
    information.

    Ce patch NE corrige PAS ca -- ce serait un autre arbitrage, entre
    ta lisibilite et le budget du modele. C est signale ici pour que
    le choix soit conscient.

DEUX ANCRES, verifiees uniques. REJOUABLE DANS LES DEUX SENS.
Sauvegarde horodatee. ast.parse. Le patch mesure les documents reels
et dit si les valeurs demandees suffisent -- plutot que de te laisser
le decouvrir a la prochaine question.

Ce patch ne touche qu un LECTEUR. Aucun ordre, aucun collecteur.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "repl_web.py"
# Reperees par le NOM, pas par la valeur : c est ce qui rend le patch
# rejouable dans les deux sens.
#
# Trois pieges, tous rencontres pour de vrai :
#   - les constantes sont INDENTEES de 8 espaces (elles vivent dans un
#     bloc, pas au module) -- d ou le groupe 1 qui capture et restitue
#     l indentation telle quelle ;
#   - elles portent un COMMENTAIRE en bout de ligne -- d ou le groupe 3,
#     preserve tel quel. Une premiere version exigeait la fin de ligne
#     juste apres le nombre et trouvait 0 occurrence ;
#   - \b apres MAX empeche _DOCS_MAX d attraper _DOCS_MAX_UN ;
#   - [ \t] et non \s : \s mange le retour a la ligne et souderait
#     deux lignes -- attrape par le garde-fou du nombre de lignes.
R_TOT = re.compile(
    r"^([ \t]*_DOCS_MAX\b[ \t]*=[ \t]*)(\d+)([ \t]*(?:#[^\r\n]*)?)$", re.M)
R_UN = re.compile(
    r"^([ \t]*_DOCS_MAX_UN\b[ \t]*=[ \t]*)(\d+)([ \t]*(?:#[^\r\n]*)?)$", re.M)


def pose(r, valeur, texte):
    """Remplace le nombre en gardant l indentation et le commentaire."""
    return r.sub(lambda m: m.group(1) + str(valeur) + m.group(3),
                 texte, count=1)


def poids():
    """Les documents que _DOCS_REPL parcourt, dans SON ordre : les
    journaux nommes, puis panel_x60_onset nomme, puis le dossier
    panels par ordre alphabetique, puis notes."""
    lot = []
    for c in (os.path.join("docs", "JOURNAL.md"),
              os.path.join("docs", "JOURNAL_14_08.md"),
              os.path.join("panels", "panel_x60_onset.txt")):
        if os.path.isfile(c):
            lot.append(c)
    for d in ("panels", "notes"):
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if not n.lower().endswith((".md", ".txt")):
                continue
            c = os.path.join(d, n)
            if c not in lot:
                lot.append(c)
    return [(c, os.path.getsize(c)) for c in lot]


def simule(lot, tot_max, un_max):
    """Rejoue le parcours du REPL : chaque document est tronque a
    un_max, on empile jusqu a tot_max puis on s arrete. Rend les
    documents LUS, ceux TRONQUES, ceux JAMAIS ATTEINTS, et le total."""
    lus, tronques, jamais = [], [], []
    cum = 0
    stop = False
    for c, t in lot:
        if stop:
            jamais.append(c)
            continue
        pris = min(t, un_max)
        if pris < t:
            tronques.append((c, t, pris))
        if cum + pris > tot_max:
            jamais.append(c)
            stop = True
            continue
        cum += pris
        lus.append(c)
    return lus, tronques, jamais, cum


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--total", type=int, default=400000)
    p.add_argument("--un", type=int, default=200000)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    for r, nom in ((R_TOT, "_DOCS_MAX"), (R_UN, "_DOCS_MAX_UN")):
        n = len(r.findall(src))
        if n != 1:
            print("KO : %d ligne(s) '%s = <entier>' (indentation et"
                  % (n, nom))
            print("     commentaire de fin admis), il en faut 1.")
            print("Rien n a ete ecrit.")
            return 1
    tot_av = int(R_TOT.search(src).group(2))
    un_av = int(R_UN.search(src).group(2))
    print("Valeurs actuelles : _DOCS_MAX = %d, _DOCS_MAX_UN = %d"
          % (tot_av, un_av))

    lot = poids()
    if not lot:
        print()
        print("AVERTISSEMENT : aucun document trouve. Le patch ecrira")
        print("les plafonds quand meme, mais il ne peut rien mesurer --")
        print("es-tu bien dans le dossier de la stack ?")
    tot = sum(t for _, t in lot)
    gros = max(lot, key=lambda x: x[1]) if lot else ("(aucun)", 0)

    av = simule(lot, tot_av, un_av)
    ap = simule(lot, a.total, a.un)
    print()
    print("Documents reels : %d fichiers, %d caracteres au total."
          % (len(lot), tot))
    print("Le plus gros : %s, %d caracteres." % (gros[0], gros[1]))
    print()
    print("  AVANT : %d lus, %d caracteres" % (len(av[0]), av[3]))
    print("  APRES : %d lus, %d caracteres" % (len(ap[0]), ap[3]))
    gagnes = [c for c in ap[0] if c not in av[0]]
    perdus = [c for c in av[0] if c not in ap[0]]
    for c in gagnes:
        print("    + %s  (invisible jusqu ici)" % c)
    for c in perdus:
        print("    - %s  (PERDU par ce reglage)" % c)
    for c, t, pris in ap[1]:
        print("    ! %s tronque a %d sur %d (marque dans le texte)"
              % (c, pris, t))
    for c in ap[2]:
        if c not in [x[0] for x in ap[1]]:
            print("    x %s jamais atteint" % c)

    if lot and a.total < tot:
        print()
        print("AVERTISSEMENT : --total %d < %d caracteres reels."
              % (a.total, tot))
        print("Le break tombe encore. Il en faudrait au moins %d." % tot)
    if lot and a.un < gros[1]:
        print()
        print("AVERTISSEMENT : --un %d < %d, le plus gros document"
              % (a.un, gros[1]))
        print("est TRONQUE (marque '[... tronque ...]' a la coupe).")
        print("Il en faudrait au moins %d." % gros[1])

    if (tot_av, un_av) == (a.total, a.un):
        print()
        print("Deja aux valeurs demandees. Rien n a ete ecrit.")
        return 0

    neuf = pose(R_TOT, a.total, src)
    neuf = pose(R_UN, a.un, neuf)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1
    # Verification au niveau de l AST : les deux constantes valent
    # bien ce qui a ete demande, et RIEN d autre n a change de valeur.
    vus = {}
    for n in ast.walk(ast.parse(neuf)):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id in ("_DOCS_MAX", "_DOCS_MAX_UN")
                and isinstance(n.value, ast.Constant)):
            vus[n.targets[0].id] = n.value.value
    if vus != {"_DOCS_MAX": a.total, "_DOCS_MAX_UN": a.un}:
        print("KO : verification AST -- les constantes valent %r." % vus)
        print("Rien n a ete ecrit.")
        return 1
    if neuf.count("_DOCS_REPL") != src.count("_DOCS_REPL"):
        print("KO : _DOCS_REPL a bouge, ce n etait pas demande.")
        print("Rien n a ete ecrit.")
        return 1
    if len(neuf.split("\n")) != len(src.split("\n")):
        print("KO : le nombre de lignes a change.")
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("  _DOCS_MAX     %d -> %d" % (tot_av, a.total))
    print("  _DOCS_MAX_UN  %d -> %d" % (un_av, a.un))
    ecart = ap[3] - av[3]
    print("  soit %+d caracteres charges, environ %+d jetons."
          % (ecart, int(ecart / 3.6)))
    print()
    print("Trois issues possibles, a surveiller a la prochaine question :")
    print("  1. ca passe, le REPL lit tout")
    print("  2. les reponses se tronquent plus tot qu avant")
    print("  3. l API refuse l appel avec une erreur de contexte")
    print("Marche arriere : --total %d --un %d" % (tot_av, un_av))
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py.")
    print("NE JAMAIS le lancer a la main sans PA_ROLE=panel : sans")
    print("elle, _run_trading est vrai et de vrais ordres partent.")
    print("run_panel_loop.bat la pose et gagne la course.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
