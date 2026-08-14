# -*- coding: utf-8 -*-
"""
patch_section_duree.py -- combien de temps vit une position, et
                          combien on n en sait rien

  python patch_section_duree.py --essai
  python patch_section_duree.py
  python patch_section_duree.py --annuler

D OU VIENT LA DEMANDE

    La section 5 affiche "age median des accompagnants" :

        x10 1.9 h/78   x20 0.7 h/83   x30 0.5 h/50   x60 0.6 h/110

    et se lit spontanement comme "les mouvements x10 durent
    longtemps". Elle ne dit pas ca. Elle parcourt les ALLUMAGES et,
    pour chacun, l age des positions deja ouvertes. Une position
    fermee en cinq minutes n apparait dans presque aucun plateau ;
    une qui dure quatre heures apparait dans tous les allumages de
    ces quatre heures. Le tableau compte des PRESENCES et surechan-
    tillonne mecaniquement les longues -- c est le paradoxe de
    l inspection. Et l ordre n y est meme pas decroissant : le x30
    (0,5 h) est plus court que le x60 (0,6 h).

    D ou cette section : une ligne par POSITION, pas par presence.

LE PIEGE QU IL FAUT MONTRER, PAS CONTOURNER

    Ne mesurer que les positions FERMEES donnerait un chiffre faux
    dans une direction connue : le bras 206 tient jusqu au reverse,
    le 207 sort a son partiel. Tot dans la collecte, l ensemble des
    fermees est presque entierement du 207. Au 14/08, AUCUN
    x10/x20/x30 du bras 206 n a de ligne CLOTURE.

    Une moyenne sur cet ensemble ne dit pas "duree d un x10", elle
    dit "duree d un x10 du bras 207". C est de la donnee CENSUREE.

    Le traitement honnete n est pas de renoncer -- c est d afficher
    la censure a cote de la moyenne. L age courant d une position
    encore ouverte est une BORNE INFERIEURE de sa duree finale : si
    neuf x10 sont ouverts et que le plus vieux a deja 6 h, on sait
    que la moyenne des fermees sous-estime, et de combien au moins.

CE QUE LA SECTION AFFICHE

                    fermees                    encore ouvertes
                n    moy     med    e-type     n   max age   censure
      x10 206   0      -       -        -      9     6.2 h     100 %
      x10 207  12   41 min  38 min   18 min    2     0.5 h      14 %
      x10 tous 12   41 min  38 min   18 min   11     6.2 h      48 %

    censure = ouvertes / (fermees + ouvertes). A 100 %, la ligne des
    fermees est vide et rien n est mesure. Au-dessus de 50 %, la
    moyenne est une borne basse, pas une estimation.

    L instantane des ouvertes vient du dernier allumage enregistre ;
    son horodatage est imprime, parce qu un instantane sans heure ne
    vaut rien.

UNE ANCRE (la fin de la section 5), verifiee unique. La section
s insere en "5 bis" pour ne rien renumeroter -- une renumerotation
casserait les reperes de tous les autres patches et du journal.

ast.parse et controle AST. Sauvegarde horodatee, suffixee si
collision. Ne touche qu un LECTEUR.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "panel_quadruple.py"
MARQUE = "5 bis. DUREE DE VIE"

ANCRE = ('    for k, v in sorted(voie.items()):\n'
         '        dis("    %-20s %6d" % (k, v))')

BLOC = r'''

    # ------------------------------------------------------------------
    bloc("5 bis. DUREE DE VIE, une ligne par POSITION",
         ["La section 5 ci-dessus compte des PRESENCES : une position",
          "longue y figure une fois par allumage qu elle traverse, une",
          "position courte presque jamais. Elle surechantillonne donc",
          "les longues par construction. Ici, une ligne par position.",
          "",
          "CENSURE. Le bras 206 tient jusqu au reverse, le 207 sort a",
          "son partiel : lire les fermees en debut de collecte revient",
          "a lire surtout du 207. La colonne `cens` donne la part des",
          "positions encore ouvertes. A 100 %, rien n est mesure. Au-",
          "dessus de 50 %, la moyenne est une BORNE BASSE.",
          "",
          "L age d une position encore ouverte est une borne inferieure",
          "de sa duree finale : `max age` dit de combien la moyenne des",
          "fermees sous-estime, au minimum."])

    def _duree(h):
        if h is None:
            return "-"
        return ("%.0f min" % (h * 60)) if h < 2 else ("%.1f h" % h)

    _ferm = collections.defaultdict(list)
    _neg = 0
    for e in ev:
        if e.get("quoi") != "CLOTURE" or not garde(e.get("ts")):
            continue
        _s = setup_de(e.get("magic"))
        _b = bras_de(e.get("magic")) or "?"
        _t0, _t1 = horo(e.get("ouvert")), horo(e.get("ts"))
        if _s is None or _t0 is None or _t1 is None:
            continue
        _d = (_t1 - _t0).total_seconds() / 3600.0
        if _d < 0:
            # `ouvert` porte une date complete dans les CLOTURE : un
            # negatif ici n est pas le bug du plateau, c est une
            # anomalie. On la compte, on ne la devine pas.
            _neg += 1
            continue
        _ferm[(_s, _b)].append(_d)
        _ferm[(_s, "tous")].append(_d)

    _ouv = collections.defaultdict(list)
    _snap = None
    for e in ev:
        if e.get("quoi") not in ("X_ENTREE", "X60_ENTREE"):
            continue
        if not garde(e.get("ts")) or not e.get("plateau"):
            continue
        _snap = e
    if _snap is not None:
        for m in (_snap.get("plateau") or []):
            if m.get("ticket") in clot:
                continue
            _s = setup_de(m.get("magic"))
            _b = bras_de(m.get("magic")) or "?"
            _v = m.get("age_s")
            if _s is None or _v is None:
                continue
            if _v < 0:
                _v += 86400
            _ouv[(_s, _b)].append(_v / 3600.0)
            _ouv[(_s, "tous")].append(_v / 3600.0)

    dis()
    dis("  %-9s %4s %8s %8s %8s   %4s %8s %6s"
        % ("", "n", "moy", "med", "e-type", "n", "max age", "cens"))
    dis("  %-9s %s" % ("", "fermees" + " " * 24 + "encore ouvertes"))
    dis("  " + "-" * 62)
    for _s in QUATRE:
        for _b in ("206", "207", "tous"):
            _f = sorted(_ferm.get((_s, _b), []))
            _o = sorted(_ouv.get((_s, _b), []))
            if not _f and not _o:
                continue
            if _f:
                _m = sum(_f) / len(_f)
                _md = _f[len(_f) // 2]
                _et = (sum((x - _m) ** 2 for x in _f) / len(_f)) ** 0.5
                _c1 = ("%4d %8s %8s %8s"
                       % (len(_f), _duree(_m), _duree(_md), _duree(_et)))
            else:
                _c1 = "%4d %8s %8s %8s" % (0, "-", "-", "-")
            if _o:
                _c2 = "%4d %8s" % (len(_o), _duree(_o[-1]))
            else:
                _c2 = "%4d %8s" % (0, "-")
            _tot = len(_f) + len(_o)
            _cn = ("%5.0f %%" % (100.0 * len(_o) / _tot)) if _tot else "    -"
            dis("  x%-2s %-5s %s   %s %s" % (_s, _b, _c1, _c2, _cn))
    dis()
    if _snap is not None:
        dis("  instantane des ouvertes : %s (dernier allumage)"
            % (_snap.get("ts") or "?"))
    else:
        dis("  aucun allumage avec plateau : colonne ouvertes vide.")
    if _neg:
        dis("  %d cloture(s) de duree negative, ecartees sans etre"
            % _neg)
        dis("  devinees -- a regarder si le nombre grandit.")
    dis("  Rappel : x10/x20/x30 tournent depuis le 13/08 13:10.")
'''


def lire(c):
    return io.open(c, encoding="utf-8", errors="replace").read()


def sauver(c, t):
    base = "%s.bak-%s" % (c, datetime.now().strftime("%Y%m%d-%H%M%S"))
    s, k = base, 1
    while os.path.exists(s):
        s = "%s-%d" % (base, k)
        k += 1
    shutil.copy2(c, s)
    io.open(c, "w", encoding="utf-8").write(t)
    print("Sauvegarde : %s" % s)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--annuler", action="store_true")
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = lire(a.fichier)
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    deja = MARQUE in src
    print("  etat actuel : section 5 bis %s"
          % ("presente" if deja else "absente"))
    if deja == (not a.annuler):
        print()
        print("Rien a faire -- deja dans l etat demande.")
        return 0

    if a.annuler:
        r = re.compile(
            r"\n\n    # -+\n    bloc\(\"5 bis\. DUREE DE VIE.*?"
            r'(?=\n\n    # -+\n    # -+\n    # 6 a 9 )', re.S)
        if len(r.findall(src)) != 1:
            print("KO : %d bloc(s) 5 bis reperes, il en faut 1."
                  % len(r.findall(src)))
            print("Rien n a ete ecrit.")
            return 1
        neuf = r.sub("", src, count=1)
    else:
        n = src.count(ANCRE)
        if n != 1:
            print("KO : %d occurrence(s) de la fin de la section 5,"
                  " il en faut 1." % n)
            print("Rien n a ete ecrit.")
            return 1
        # Ce dont le bloc a besoin et qui doit deja exister.
        for t in ("def setup_de(", "def bras_de(", "def horo(", "def bloc(",
                  "clot = {}", "QUATRE = ", "collections."):
            if t not in src:
                print("KO : %s absent du fichier -- le bloc s appuie"
                      " dessus." % t)
                print("Rien n a ete ecrit.")
                return 1
        # BLOC.rstrip : sans ca l insertion ajoute un saut de
        # ligne que --annuler ne rend pas, et le fichier
        # restaure differe de l original d un octet.
        neuf = src.replace(ANCRE, ANCRE + BLOC.rstrip("\n"), 1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # On n a touche a RIEN d autre.
    for t in ('bloc("6.', 'bloc("9. SEANCE US', 'bloc("10. RAPPELS',
              "def table4(", "def main(", "SEUIL = 54", "a.joindre",
              'e.get("quoi") != "CLOTURE"'):
        av, ap = src.count(t), neuf.count(t)
        att = av + (1 if (t == 'e.get("quoi") != "CLOTURE"'
                          and not a.annuler) else 0)
        att = att - (1 if (t == 'e.get("quoi") != "CLOTURE"'
                           and a.annuler) else 0)
        if ap != att:
            print("KO : %s apparait %d fois, attendu %d." % (t, ap, att))
            print("Rien n a ete ecrit.")
            return 1
    if (MARQUE in neuf) == a.annuler:
        print("KO : l etat obtenu n est pas celui demande.")
        print("Rien n a ete ecrit.")
        return 1

    print()
    if a.annuler:
        print("  section 5 bis retiree.")
    else:
        print("  section 5 bis ajoutee, %d lignes." % BLOC.count("\n"))
        print("  Une ligne par POSITION, huit a douze lignes selon les")
        print("  bras presents, avec la colonne `cens`.")
        print()
        print("  A lire en premier : la colonne cens. A 100 %, la ligne")
        print("  ne mesure rien -- c est le cas attendu pour les bras")
        print("  206 des x10/x20/x30, qui n ont encore rien cloture.")
    print("Marche arriere : %s"
          % ("python %s" % os.path.basename(__file__) if a.annuler
             else "python %s --annuler" % os.path.basename(__file__)))
    print()
    print("PREND EFFET A LA PROCHAINE REGENERATION DU PANNEAU (5 min),")
    print("ou tout de suite : python panel_quadruple.py")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauver(a.fichier, neuf)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
