# -*- coding: utf-8 -*-
"""
patch_papier_frequence.py -- combien de fois chaque unite s allume, pas seulement quand elle trade

  python patch_papier_frequence.py --essai
  python patch_papier_frequence.py

CE QU ON NE SAIT PAS ENCORE

    --etat du 13/08 10:13 : 18 cellules sur 18 saines, 200 barres
    partout, et ZERO ignition sur les six cellules M10 et M20 pendant
    que six cellules M30 et plus etaient allumees.

    C est une photo. Elle ne dit pas si les courtes sont entre deux
    signaux ou si elles ne s allument jamais. Et papier_tf n enregistre
    que les ENTREES : une unite qui s allume dix fois sans jamais
    changer de direction ne laisse aucune trace, alors que ce serait la
    reponse.

CE QUE LE PATCH AJOUTE

    L evenement VEILLE, ecrit toutes les 10 minutes, porte desormais
    l etat de chaque cellule sous forme compacte :

        "cel": {"1_10": "b", "1_60": "B", "3_30": "S", ...}

        cle    actif_duree     B/S = ignition ALLUMEE, bull ou bear
                               b/s = eteinte, direction courante
                               -   = cellule illisible a cet instant

    Une lettre par cellule, dix-huit par ligne, toutes les dix minutes :
    quelques kilo-octets par jour. Le cout est nul devant ce qu on
    ignore aujourd hui.

    Et le rapport gagne une section : par duree, la part du temps ou
    l ignition est allumee, le nombre de basculements de direction, et
    le nombre d entrees. Trois colonnes qui separent enfin :

      s allume souvent et trade     -> l unite fonctionne
      s allume souvent, ne trade pas-> la direction ne bascule jamais,
                                       donc « frais » n arrive pas
      ne s allume jamais            -> l unite est morte pour le signal

    Le troisieme cas est un resultat publiable. Les deux premiers
    demandent des actions opposees. Sans cette mesure ils sont
    indiscernables, et c est exactement la ou on en est ce matin.

CE QU IL NE CHANGE PAS

    Ni la regle d entree, ni les sorties, ni les horaires. Il ajoute
    dix-huit lectures toutes les dix minutes -- _analyze sur 200 barres,
    de l ordre du milliseconde -- et un champ dans un journal.

    Les VEILLE deja ecrites n ont pas ce champ. Le rapport les ignore
    pour cette section et le dit, plutot que de les compter comme des
    cellules eteintes.

TROIS ANCRES, verifiees uniques. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture. PREND EFFET AU REDEMARRAGE DE L OBSERVATEUR.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "papier_tf.py"
MARQUEUR = '"cel"'

RE_VEILLE = re.compile(
    r'^([ \t]*)ecrire_trade\(\{"quoi": "VEILLE", "ts": maintenant\(\),\n'
    r'[ \t]*"creneau": creneau\(\), "ouvertes": len\(ouvertes\),\n'
    r'[ \t]*"cellules": len\(grille\)\}\)$', re.M)

RE_RAPPORT = re.compile(r'^def rapport\(\):$', re.M)

RE_SECTION = re.compile(
    r'^([ \t]*)L\.append\("=" \* LARG\)\n'
    r'[ \t]*L\.append\("  PAR HEURE D ENTREE -- horloge de cette machine"\)$',
    re.M)

VEILLE = '''@I@# L etat de CHAQUE cellule, pas seulement le compte des ouvertes.
@I@# Sans lui, une unite qui s allume dix fois sans jamais changer de
@I@# direction ne laisse aucune trace -- et c est justement la question
@I@# posee par les M10 muettes du 13/08.
@I@ecrire_trade({"quoi": "VEILLE", "ts": maintenant(),
@I@              "creneau": creneau(), "ouvertes": len(ouvertes),
@I@              "cellules": len(grille), "cel": photo(grille)})'''

PHOTO = '''def photo(grille):
    """Une lettre par cellule : B/S ignition allumee, b/s eteinte, - illisible.

    Deduplique par (symbole, duree) : les bras 206 et 207 partagent
    exactement la meme cellule, la calculer deux fois donnerait le meme
    resultat pour le double du travail."""
    out, vus = {}, {}
    for c in grille:
        cl = "%s_%d" % (c["actif"], c["mn"])
        if cl in out:
            continue
        cel = cellule(c["sym"], c["tf"])
        if cel is None:
            out[cl] = "-"
            continue
        d = cel.get("dir")
        lettre = "B" if d == "BULL" else ("S" if d == "BEAR" else "-")
        out[cl] = lettre if cel.get("ignition") else lettre.lower()
    return out


'''

SECTION = '''@I@L.append("=" * LARG)
@I@L.append("  ALLUMAGE CONTRE ENTREES -- une unite muette ou bloquee ?")
@I@L.append("=" * LARG)
@I@av = [e for e in veilles if isinstance(e.get("cel"), dict)]
@I@if not av:
@I@    L.append("  Aucune veille ne porte l etat des cellules. Le releve")
@I@    L.append("  date d avant l ajout de ce champ ; il se remplira des")
@I@    L.append("  le prochain redemarrage de l observateur.")
@I@else:
@I@    L.append("%-8s %9s %10s %11s %9s   %s"
@I@             % ("duree", "releves", "allumee", "bascule", "entrees",
@I@                "lecture"))
@I@    L.append("-" * LARG)
@I@    for mn in DUREES:
@I@        n_rel = n_on = n_bas = 0
@I@        for actif, _code, _sym in ACTIFS:
@I@            cl = "%s_%d" % (actif, mn)
@I@            prec = None
@I@            for e in av:
@I@                v = e["cel"].get(cl)
@I@                if not v or v == "-":
@I@                    continue
@I@                n_rel += 1
@I@                if v.isupper():
@I@                    n_on += 1
@I@                haut = v.upper()
@I@                if prec is not None and haut != prec:
@I@                    n_bas += 1
@I@                prec = haut
@I@        n_ent = len([e for e in entrees if e["mn"] == mn])
@I@        part = (100.0 * n_on / n_rel) if n_rel else None
@I@        if not n_rel:
@I@            note = "jamais lue"
@I@        elif n_on == 0:
@I@            note = "MUETTE : le signal ne s allume jamais"
@I@        elif n_ent == 0 and n_bas == 0:
@I@            note = "BLOQUEE : allumee, mais la direction ne bascule pas"
@I@        elif n_ent == 0:
@I@            note = "bascule mais n entre pas -- filtre RSI M3 ?"
@I@        else:
@I@            note = ""
@I@        L.append("%-8s %9d %9s%% %11d %9d   %s"
@I@                 % (libelle(mn), n_rel, f(part, 0), n_bas, n_ent, note))
@I@    L.append("-" * LARG)
@I@    L.append("  'allumee' = part des releves ou churn signalait une")
@I@    L.append("  ignition. 'bascule' = changements de direction, la")
@I@    L.append("  condition d une entree FRAICHE. Une unite peut donc")
@I@    L.append("  etre allumee en permanence et n entrer jamais.")
@I@    L.append("")
@I@    L.append("  Trois cas, trois suites differentes. MUETTE est un")
@I@    L.append("  resultat : cette echelle ne porte pas le signal.")
@I@    L.append("  BLOQUEE veut dire que l ignition est un etat continu")
@I@    L.append("  a cette echelle et pas un evenement -- il faudrait")
@I@    L.append("  alors entrer autrement, pas attendre un basculement.")
@I@    L.append("  Le dernier cas envoie vers le filtre RSI M3, qui")
@I@    L.append("  refuse les entrees contre son niveau 50.")
@I@    L.append("")
@I@    L.append("  Les releves sont espaces de %d minutes : une ignition"
@I@             % VEILLE_MIN)
@I@    L.append("  plus courte que ca peut passer entre deux photos. Ce")
@I@    L.append("  tableau minore donc l allumage des unites rapides --")
@I@    L.append("  dans le sens qui ACCUSE M10, pas qui l innocente.")
@I@    L.append("")

@I@L.append("=" * LARG)
@I@L.append("  PAR HEURE D ENTREE -- horloge de cette machine")'''


def pose(gabarit, indent):
    return gabarit.replace("@I@", indent)


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

    for nom, rx in (("l ecriture de la VEILLE", RE_VEILLE),
                    ("def rapport()", RE_RAPPORT),
                    ("la section PAR HEURE", RE_SECTION)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1

    neuf = RE_VEILLE.sub(lambda m: pose(VEILLE, m.group(1)), src, count=1)
    m = RE_RAPPORT.search(neuf)
    neuf = neuf[:m.start()] + PHOTO + neuf[m.start():]
    neuf = RE_SECTION.sub(lambda mo: pose(SECTION, mo.group(1)),
                          neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Chaque VEILLE portera l etat des 18 cellules -- une lettre")
    print("chacune, toutes les 10 minutes. Et le rapport gagne un")
    print("tableau ALLUMAGE CONTRE ENTREES qui separe une unite MUETTE")
    print("d une unite BLOQUEE : deux diagnostics opposes, aujourd hui")
    print("indiscernables.")
    print()
    print("PREND EFFET AU REDEMARRAGE de l observateur -- c est la boucle")
    print("qui ecrit les veilles. L amorcage rend ce redemarrage gratuit.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Redemarre papier_tf.py pour que les veilles portent")
    print("l etat des cellules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
