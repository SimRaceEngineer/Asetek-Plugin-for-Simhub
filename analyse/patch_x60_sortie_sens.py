# -*- coding: utf-8 -*-
"""
patch_x60_sortie_sens.py -- AVEC ou CONTRE, mesure a la SORTIE

  python patch_x60_sortie_sens.py --essai
  python patch_x60_sortie_sens.py

POURQUOI LA MESURE A L ENTREE NE PEUT PAS REPONDRE

    Le 13/08 a 12:04, section AVEC/CONTRE, sur le meme actif :

        PREMIER   meme actif   AVEC       0 presence
        PREMIER   meme actif   CONTRE     8   final -4.90

    Zero presence « avec », dans les DEUX categories. Ce n est pas un
    echantillon maigre, c est une impossibilite : on photographie a
    l instant ou le x60 vient de basculer sur un allumage FRAIS. A
    cette seconde-la, les cellules courtes du meme actif tiennent
    encore la direction d avant. Elles sont « contre » par definition
    de l instant choisi.

    Le -4.90 n a donc aucun groupe temoin. Il ne compare rien.

CE QUE LA SORTIE CHANGE

    Entre l entree et la sortie d un x60 il se passe des heures --
    le 13/08, 76 minutes pour le US30 du matin. Les cellules courtes
    ont eu le temps de basculer plusieurs fois. A la sortie, il y a
    donc des « avec » ET des « contre » sur le meme actif : la
    comparaison existe.

    C est la meme donnee, deja enregistree : chaque X60_SORTIE porte
    son plateau complet. Il manquait seulement la direction du x60,
    qui n est ecrite que dans son ENTREE -- on la retrouve en joignant
    le ticket, identique des deux cotes.

FRANCHE OU REVERSE, la meme precaution qu a l entree

    Une sortie suivie d une re-entree du meme magic dans les 60 s est
    un REVERSE. A cet instant precis, le marche vient de se retourner
    et tout le monde est du mauvais cote pour la meme cause -- la
    correlation y est garantie par construction. Seules les sorties
    FRANCHES portent une information.

CE QUI RESTE VRAI QUOI QU IL ARRIVE

    5 sorties enregistrees au 13/08 midi, il en faudrait 8 pour que la
    section voisine s autorise a parler. Celle-ci DECRIT. Elle affiche
    ses effectifs et se tait sur le reste.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse, puis controle sur l ARBRE que la section est dans rapport()
et APRES la section d entree -- posee ailleurs elle compilerait aussi.

EXIGE patch_x60_avec_contre (et, si tu l as, patch_x60_reverse).
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "x60_onset.py"
MARQUEUR = "QUI ETAIT AVEC, QUI ETAIT CONTRE"
REQUIS = "AVEC OU CONTRE LA DIRECTION"

ANCRE = '''    # ------------------------------------------- qui accompagne un x60
'''

NEUF = '''    # --------------------------- avec ou contre, mesure a la SORTIE
    # A l ENTREE la comparaison n existe pas : le x60 vient de basculer
    # sur un allumage frais, donc les cellules courtes du meme actif
    # tiennent encore la direction d avant et sont "contre" par
    # definition de l instant choisi -- 0 presence AVEC sur 12, le
    # 13/08. Le chiffre obtenu la n a aucun groupe temoin.
    # A la SORTIE, des heures ont passe et elles ont bascule plusieurs
    # fois : il y a des deux cotes, donc une comparaison.
    L.append("=" * LARG)
    L.append("  A LA SORTIE DU x%s : QUI ETAIT AVEC, QUI ETAIT CONTRE"
             % SETUP)
    L.append("=" * LARG)
    # La direction du x60 n est ecrite que dans son ENTREE. On la
    # retrouve par le ticket, identique de l entree a la sortie.
    _sens_x = {}
    for e in entrees:
        if e.get("sens") and e.get("ticket") is not None:
            _sens_x[e["ticket"]] = e["sens"]
    # Une sortie suivie d une re-entree du meme magic dans les 60 s est
    # un reverse : a cet instant tout le monde est du mauvais cote pour
    # la meme cause. Meme precaution qu a l entree.
    _entr_magic = defaultdict(list)
    for e in entrees:
        u = _horo(e.get("ts"))
        if u is not None:
            _entr_magic[e.get("magic")].append(u)

    def _sortie_franche(e):
        t = _horo(e.get("ts"))
        if t is None:
            return "FRANCHE"
        for u in _entr_magic.get(e.get("magic"), []):
            if abs((t - u).total_seconds()) <= REV_S:
                return "REVERSE"
        return "FRANCHE"

    sc = defaultdict(lambda: {"n": 0, "lat": [], "fin": []})
    _sans = 0
    for e in sorties:
        sx = _sens_x.get(e.get("ticket"))
        if not sx:
            _sans += 1
            continue
        org = _sortie_franche(e)
        for a in e.get("plateau", []):
            if a["x60"]:
                continue
            k = (org,
                 "meme actif" if a["actif"] == e.get("actif")
                 else "autre actif",
                 "AVEC" if a["sens"] == sx else "CONTRE")
            sc[k]["n"] += 1
            sc[k]["lat"].append(a["latent"])
            fin = (clotures.get(a["ticket"]) or {}).get("final")
            if fin is not None:
                sc[k]["fin"].append(fin)

    if not sc:
        L.append("  Aucune sortie x%s exploitable pour l instant." % SETUP)
        if _sans:
            L.append("  %d sortie(s) sans entree correspondante : le x%s"
                     % (_sans, SETUP))
            L.append("  etait deja ouvert quand l observateur a demarre,")
            L.append("  sa direction n a donc jamais ete enregistree.")
    else:
        def _res(sens):
            n, fin = 0, []
            for k, c in sc.items():
                if k[0] != "FRANCHE" or k[1] != "meme actif":
                    continue
                if k[2] != sens:
                    continue
                n += c["n"]
                fin += c["fin"]
            if not n:
                return "aucune presence"
            nf, _s1, mf, _a1, _b1, _d1 = ratios(fin)
            return ("%2d presences, issue moyenne %s"
                    % (n, ("%+.2f EUR" % mf) if nf else "inconnue"))
        L.append("  D UN COUP D OEIL -- meme actif, sorties FRANCHES :")
        L.append("    tierces AVEC   le x%s : %s" % (SETUP, _res("AVEC")))
        L.append("    tierces CONTRE le x%s : %s" % (SETUP, _res("CONTRE")))
        L.append("  ICI la comparaison existe, contrairement a la section")
        L.append("  d entree ou le camp AVEC est vide par construction.")
        L.append("  Si CONTRE perd la ou AVEC passe, alors la direction du")
        L.append("  x%s est une consigne et V10/V11 doivent respecter sa"
                 % SETUP)
        L.append("  priorite. Si les deux se valent, elle n en est pas une.")
        L.append("")
        L.append("%-9s %-13s %-8s %10s %14s %8s %13s"
                 % ("sortie", "actif", "sens", "presences", "latent moyen",
                    "connus", "final moyen"))
        L.append("-" * LARG)
        for k in sorted(sc):
            c = sc[k]
            _nl, _sl, ml, _r1, _p1, _s1 = ratios(c["lat"])
            nf, _sf, mf, _r2, _p2, _s2 = ratios(c["fin"])
            L.append("%-9s %-13s %-8s %10d %14.2f %8d %13s"
                     % (k[0], k[1], k[2], c["n"], ml, nf,
                        ("%.2f" % mf) if nf else "-"))
        L.append("-" * LARG)
        L.append("  'latent moyen' = le P&L de la tierce a l instant ou le")
        L.append("  x%s SORT. 'final moyen' = son issue." % SETUP)
        L.append("  %d sortie(s) exploitee(s) sur %d."
                 % (len(sorties) - _sans, len(sorties)))
        if _sans:
            L.append("  %d ecartee(s) : le x%s etait deja ouvert au"
                     % (_sans, SETUP))
            L.append("  demarrage de l observateur, sa direction n a jamais")
            L.append("  ete enregistree. Les compter sans elle reviendrait a")
            L.append("  tirer AVEC ou CONTRE a pile ou face.")
        if len(sorties) < MINI:
            L.append("  MOINS DE %d SORTIES : cette section DECRIT, elle ne"
                     % MINI)
            L.append("  conclut pas. Laisse l observateur tourner.")
    L.append("")

    # ------------------------------------------- qui accompagne un x60
'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    if REQUIS not in src:
        print("KO : patch_x60_avec_contre n est pas applique.")
        print("     Cette section se pose apres la sienne. Rien n a ete"
              " ecrit.")
        return 1

    # _horo et REV_S viennent de patch_x60_reverse. Sans lui, la section
    # leverait un NameError au premier rapport -- pas a la compilation.
    for nom in ("_horo", "REV_S"):
        if nom not in src:
            print("KO : %s absent -- patch_x60_reverse n est pas applique."
                  % nom)
            print("     Cette section le reutilise pour distinguer une")
            print("     sortie franche d un reverse. Sans lui, NameError au")
            print("     premier rapport, pas a la compilation.")
            print("Rien n a ete ecrit.")
            return 1

    n = src.count(ANCRE)
    if n != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1." % n)
        print("Rien n a ete ecrit.")
        return 1

    neuf = src.replace(ANCRE, NEUF, 1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    dedans = apres = False
    for f in ast.walk(arbre):
        if not (isinstance(f, ast.FunctionDef) and f.name == "rapport"):
            continue
        d = ast.dump(f)
        dedans = MARQUEUR in d
        if dedans:
            apres = (d.index("AVEC OU CONTRE LA DIRECTION")
                     < d.index(MARQUEUR) < d.index("QUI EST LA QUAND UN x"))
    if not dedans:
        print("KO : la section n est pas dans rapport(). Rien n a ete ecrit.")
        return 1
    if not apres:
        print("KO : la section n est pas entre celle de l entree et")
        print("     'QUI EST LA QUAND UN x60'. Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : la section suit celle de l entree, dans"
          " rapport().")

    print()
    print("Nouvelle section : AVEC ou CONTRE mesure a la SORTIE du x60.")
    print()
    print("A l entree, le camp AVEC est vide PAR CONSTRUCTION -- le x60")
    print("vient de basculer, les cellules courtes du meme actif tiennent")
    print("encore la direction d avant. Le -4.90 mesure la n a donc aucun")
    print("groupe temoin, et ne compare rien.")
    print()
    print("A la sortie, des heures ont passe : les deux camps existent.")
    print("C est la seule facon de decider si la direction du x60 est une")
    print("consigne pour V10/V11.")
    print()
    print("Sorties franches et reverses restent separes, meme precaution")
    print("qu a l entree : dans un reverse tout le monde est du mauvais")
    print("cote pour la meme cause.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Le prochain --rapport l affiche.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
