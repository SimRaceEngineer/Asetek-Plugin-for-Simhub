# -*- coding: utf-8 -*-
"""
patch_trail_c14.py -- sortir le premier stop de la fenetre de veto de C14

  python patch_trail_c14.py            applique
  python patch_trail_c14.py --essai    montre ce qu il ferait, n ecrit rien

CE QU ON CORRIGE
    mfe_ticket_trail pose son premier stop (cran BE) a buffer_pts de
    l entree, soit 0,004 % du prix. buddha_clause_gate.C14 refuse tout
    resserrement qui atterrit a moins de 0,040 % (US500) ou 0,069 % (US100)
    de l entree. La fenetre est dix a dix-sept fois plus large que l endroit
    ou le cran BE pose son stop : il ne peut PAS en sortir, quel que soit le
    MFE, puisqu il vise toujours l entree.

    Mesure du 28/07 au 11/08 : 62 709 refus sur 62 732 tentatives. 149
    tickets sur 343 n ont jamais obtenu un seul deplacement de stop.

CE QU ON FAIT
    Quand le cran 1 se declenche, au lieu de viser l entree on pose le stop
    a 70 % du pic -- c est-a-dire qu on appelle le calcul du cran 3 -- et on
    n arme qu a partir de 0,12 % du prix.

        arme a  0,12 % du prix     (contre 0,08 % pour le BE)
        stop a  0,084 % du prix    (contre 0,004 %)

    Sur NAS100 a 29 200 : armer a 35 pts de MFE, stop a 24 pts de l entree,
    fenetre C14 a 20. Sur SPX500 a 7 415 : armer a 8,9, stop a 6,2,
    fenetre a 3.

CE QUE CE REGLAGE N EST PAS
    Pas une regle nouvelle. Le cran lock50 pose deja le stop a 0,080 % du
    prix et capture 57 % en production. Celui-ci le pose a 0,084 % -- le
    meme endroit -- simplement arme un quart plus tot. On avance dans le
    temps une regle dont on connait le comportement.

POURQUOI CE PATCH NE TOUCHE NI _determine_tier NI _compute_new_sl
    Il s insere au point d appel, apres le calcul de new_sl, sur quatre
    lignes lues dans le fichier. Il reutilise _compute_new_sl avec le cran 3
    plutot que de recopier sa formule.

    Et il ne PARIE pas sur ce que fait le cran 3. Il verifie le resultat :
    si la distance obtenue ne franchit pas la fenetre de C14, il ne fait
    rien. Donc si le cran 3 n est pas le verrou a 70 % que l en-tete
    annonce, le patch degrade vers le comportement actuel au lieu de poser
    un stop de travers. C est la seule facon honnete de modifier un chemin
    d ordres sans avoir lu chaque ligne du module.

CE QU IL NE FAIT PAS
    Il ne touche pas aux crans 2 et 3, qui continuent exactement comme
    avant. Il ne touche pas a C14 : la clause garde sa protection contre le
    break-even premature, on se contente de poser le stop hors de sa
    fenetre. Il ne fait pas remonter le stop entre 0,12 % et 0,32 % de pic :
    le stop pose au declenchement y reste jusqu au cran 3. C est un choix --
    moins de trafic d ordres, un comportement plus simple a juger apres
    quelques seances.

    Et il ne concerne AUCUN magic exclu : sur US30, 1 069 tickets sur 1 069
    portent un magic exclu, donc ce patch n y change rien. Il porte sur
    environ 725 tickets, soit 27 % de la stack.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
PREND EFFET AU PROCHAIN DEMARRAGE DU MOTEUR.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "mfe_ticket_trail.py"
MARQUEUR = "BE_ARME_PCT"

# Prix de reference de l en-tete du module, pour l affichage seulement.
REF = {"US30": 49700.0, "NAS100": 29200.0, "SPX500": 7415.0}
FENETRE = {"US30": 20.0, "NAS100": 20.0, "SPX500": 3.0}

RE_CONST = re.compile(r'^(BUFFER_PCT[ \t]*=[ \t]*[0-9.eE+-]+.*)$', re.M)

NEUF_CONST = '''

# 11/08/2026 -- LE CRAN 1 NE VISE PLUS L ENTREE
#
# Le cran BE posait le stop a BUFFER_PCT du prix, soit 0,004 %.
# buddha_clause_gate.C14 refuse tout resserrement a moins de 0,040 %
# (US500) ou 0,069 % (US100) de l entree, quand le biais Buddha est HOLD ou
# aligne avec la position. La fenetre est dix a dix-sept fois plus large que
# la cible du cran BE : aucun niveau de MFE ne pouvait l en sortir.
#
# Mesure sur mfe_trail_events.csv, 28/07 au 11/08 : 62 709 refus sur 62 732
# tentatives, et 149 tickets sur 343 sans un seul deplacement de stop.
#
# Le cran 1 arme donc a BE_ARME_PCT et pose le stop a 70 % du pic, comme le
# cran 3. Soit un stop a 0,084 % du prix, la ou le cran lock50 le pose deja
# a 0,080 % en capturant 57 %.
BE_ARME_PCT = 0.0012      # 0,12 % du prix -- armement du cran 1

# Distance minimale a l entree, en points, pour franchir la fenetre de C14.
# Recopiee de buddha_clause_gate.C14_BE_PROXIMITY (US30 20, US500 3,
# US100 20) avec 20 % de marge, et NON importee : importer
# buddha_clause_gate poserait son monkey-patch d order_send dans ce
# processus. A garder synchronise si la clause change. Un stop qui ne
# franchit pas cette distance n est pas pose du tout -- se faire refuser ne
# protege rien et remplit le journal.
C14_MARGE_PTS = {"US30": 24.0, "NAS100": 24.0, "SPX500": 3.6}'''

RE_CORPS = re.compile(
    r'^([ \t]*)new_sl = _compute_new_sl\(direction, p\.price_open, peak,'
    r'[ \t\r\n]*target_tier, cfg\["buffer_pts"\]\)[ \t]*\n'
    r'[ \t]*if new_sl is None:[ \t]*\n'
    r'[ \t]*return[ \t]*$',
    re.M)

NEUF_CORPS = '''
    # 11/08 : le cran 1 visait l entree, donc l interieur de la fenetre de
    # C14, donc un refus systematique. Il vise maintenant 70 % du pic, ce
    # que calcule deja le cran 3 -- on l appelle plutot que de recopier sa
    # formule.
    if target_tier == 1:
        if peak < p.price_open * BE_ARME_PCT:
            return
        _n = _compute_new_sl(direction, p.price_open, peak, 3,
                             cfg["buffer_pts"])
        # On ne parie pas sur ce que rend le cran 3 : on verifie que la
        # distance obtenue franchit la fenetre de C14. Sinon on ne fait
        # rien, ce qui est le comportement d avant ce patch.
        if _n is None or abs(_n - p.price_open) < C14_MARGE_PTS.get(asset, 0.0):
            return
        new_sl = _n'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def tableau():
    print()
    print("%-10s %9s %11s %11s %10s %9s"
          % ("actif", "prix ref", "arme a MFE", "stop a", "fenetre", "marge"))
    print("-" * 70)
    for a in ("US30", "NAS100", "SPX500"):
        px = REF[a]
        arme = px * 0.0012
        stop = arme * 0.70
        f = FENETRE[a]
        print("%-10s %9.0f %10.1f %10.1f %10.1f %8.0f%%"
              % (a, px, arme, stop, f, 100.0 * (stop - f) / f))
    print("-" * 70)
    print("Avant : arme a 0,08 % du prix, stop a 0,004 % -- toujours")
    print("dans la fenetre, donc toujours refuse.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true",
                   help="montre ce qui serait fait, n ecrit rien")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1

    src, enc = lire(a.fichier)
    print("%s : %d lignes, encodage %s"
          % (a.fichier, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Garde deja posee -- rien a faire.")
        return 0

    n_const = len(RE_CONST.findall(src))
    if n_const != 1:
        print("KO : %d ligne(s) 'BUFFER_PCT = ...', il en faut 1." % n_const)
        return 1

    trouve = RE_CORPS.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) du point d insertion, il en faut 1."
              % len(trouve))
        print("Attendu, a n importe quelle indentation :")
        print('    new_sl = _compute_new_sl(direction, p.price_open, peak,')
        print('                             target_tier, cfg["buffer_pts"])')
        print("    if new_sl is None:")
        print("        return")
        print("Rien n a ete ecrit.")
        return 1

    ind = trouve[0]
    print("point d insertion trouve : indentation %d espaces" % len(ind))
    corps = "\n".join(ind + l[4:] if l.startswith("    ") else (ind + l if l else "")
                      for l in NEUF_CORPS.split("\n"))

    neuf = RE_CONST.sub(lambda m: m.group(1) + NEUF_CONST, src, count=1)
    neuf = RE_CORPS.sub(lambda m: m.group(0) + corps, neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Le patch appelle asset, peak, direction, cfg et p : tous doivent
    # exister dans la fonction ou on s insere. On le verifie plutot que de
    # le supposer -- une NameError en seance coute plus cher qu un controle.
    fonc = None
    for n in ast.walk(ast.parse(neuf)):
        if isinstance(n, ast.FunctionDef) and any(
                isinstance(x, ast.Name) and x.id == MARQUEUR
                for x in ast.walk(n)):
            fonc = n
            break
    if fonc is None:
        print("KO : le bloc insere ne se retrouve dans aucune fonction.")
        return 1
    noms = set()
    for x in ast.walk(fonc):
        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
            noms.add(x.id)
        if isinstance(x, ast.arg):
            noms.add(x.arg)
    manque = [v for v in ("asset", "peak", "direction", "cfg") if v not in noms]
    if manque:
        print("KO : %s n est pas defini dans %s()."
              % (", ".join(manque), fonc.name))
        print("Le patch s inserait au mauvais endroit. Rien n a ete ecrit.")
        return 1
    print("contexte verifie dans %s() : asset, peak, direction, cfg presents"
          % fonc.name)

    tableau()

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DU MOTEUR -- pas avant.")
    print()
    print("Pour revenir en arriere : recopier la sauvegarde ci-dessus.")
    print()
    print("A verifier demain, apres une seance complete :")
    print("    python bande_morte.py --depuis %s"
          % datetime.now().strftime("%Y-%m-%d"))
    print()
    print("Ce qu on attend : le taux de reussite du cran 1 doit passer de")
    print("0 % a quelque chose. S il reste a 0, la fenetre de C14 n est")
    print("toujours pas franchie et il faut monter C14_MARGE_PTS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
