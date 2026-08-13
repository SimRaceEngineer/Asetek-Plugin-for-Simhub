# -*- coding: utf-8 -*-
"""
patch_x60_reverse.py -- separer le x60 PREMIER ENTRE du x60 en REVERSE

  python patch_x60_reverse.py --essai
  python patch_x60_reverse.py

CE QUE LA SECTION AVEC/CONTRE A MONTRE, ET SON PIEGE

    Premiere lecture, le 13/08 a 11:52 :

        autre actif   AVEC     12   latent  +1.79   final  +8.78
        autre actif   CONTRE   18   latent +11.72   final +16.28
        meme actif    CONTRE   12   latent  -5.75   final  -8.55
        meme actif    AVEC      0   aucune presence

    Sur le meme actif, JAMAIS une tierce dans le sens du x60. Zero sur
    douze. Et les douze finissent a -8.55.

    Sauf que sur les 8 entrees x60, celles qui portent des tierces sont
    NAS100 08:59, NAS100 11:03 -- un REVERSE, sortie et re-entree a la
    meme seconde, MAE -47.82 -- et SPX500 09:23.

    Dans un reverse, toute position du meme actif est du mauvais cote
    ET en perte pour la MEME cause : le marche vient de se retourner.
    « Contre le x60 » et « perdante » ne sont alors pas deux faits,
    c est le meme dit deux fois. La correlation est garantie par
    construction, exactement comme l etait le gain des jambes
    PARTIEL70 ce matin.

    La seule entree franche du lot -- US30 08:00:17, premier entre --
    portait 0 tierce, donc n apporte rien a ce tableau.

CE QUE LE PATCH FAIT

    Une troisieme cle : PREMIER ou REVERSE.

      REVERSE   une SORTIE du MEME magic a moins de 60 s de l entree
      PREMIER   tout le reste

    La synthese affiche les deux lectures l une sous l autre : toutes
    entrees confondues, puis PREMIER seul. Si l ecart AVEC/CONTRE
    survit a la seconde, c est un signal. S il disparait, c etait le
    reflet du reverse dans son propre miroir.

    Limite affichee a l ecran : un x60 qui vivrait moins de 60 s serait
    classe REVERSE a tort. Aucun cas au 13/08.

TROIS ANCRES, verifiees uniques. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture, puis controle sur l arbre.

EXIGE patch_x60_avec_contre : ce patch modifie la section qu il pose.
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
MARQUEUR = "_origine"
REQUIS = "AVEC OU CONTRE LA DIRECTION"

A1 = '''    ac = defaultdict(lambda: {"n": 0, "lat": [], "fin": []})
    for e in entrees:
        sx = e.get("sens")
        if not sx:
            continue
        for a in e.get("plateau", []):
            if a["x60"]:
                continue
            k = ("meme actif" if a["actif"] == e.get("actif")
                 else "autre actif",
                 "AVEC" if a["sens"] == sx else "CONTRE")
            ac[k]["n"] += 1
            ac[k]["lat"].append(a["latent"])
            fin = (clotures.get(a["ticket"]) or {}).get("final")
            if fin is not None:
                ac[k]["fin"].append(fin)
'''

N1 = '''    # Un x60 qui SORT et RE-ENTRE dans la meme poignee de secondes est
    # un REVERSE : sa direction s inverse. Toute position du meme actif
    # est alors du mauvais cote ET en perte pour la MEME cause -- le
    # marche vient de se retourner. "Contre le x60" et "perdante" ne
    # sont plus deux faits, c est le meme dit deux fois, et la
    # correlation est garantie par construction. Seules les entrees
    # PREMIER portent une information.
    REV_S = 60

    def _horo(s):
        try:
            return datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            return None

    _sort_magic = defaultdict(list)
    for s in sorties:
        u = _horo(s.get("ts"))
        if u is not None:
            _sort_magic[s.get("magic")].append(u)

    def _origine(e):
        t = _horo(e.get("ts"))
        if t is None:
            return "PREMIER"
        for u in _sort_magic.get(e.get("magic"), []):
            if abs((t - u).total_seconds()) <= REV_S:
                return "REVERSE"
        return "PREMIER"

    ac = defaultdict(lambda: {"n": 0, "lat": [], "fin": []})
    for e in entrees:
        sx = e.get("sens")
        if not sx:
            continue
        org = _origine(e)
        for a in e.get("plateau", []):
            if a["x60"]:
                continue
            k = (org,
                 "meme actif" if a["actif"] == e.get("actif")
                 else "autre actif",
                 "AVEC" if a["sens"] == sx else "CONTRE")
            ac[k]["n"] += 1
            ac[k]["lat"].append(a["latent"])
            fin = (clotures.get(a["ticket"]) or {}).get("final")
            if fin is not None:
                ac[k]["fin"].append(fin)
'''

A2 = '''        def _resume(k):
            c = ac.get(k)
            if not c:
                return "aucune presence"
            nf, _s1, mf, _a1, _b1, _d1 = ratios(c["fin"])
            return ("%2d presences, issue moyenne %s"
                    % (c["n"], ("%+.2f EUR" % mf) if nf else "inconnue"))
        L.append("  D UN COUP D OEIL, sur le MEME actif :")
        L.append("    tierces AVEC   le x%s : %s"
                 % (SETUP, _resume(("meme actif", "AVEC"))))
        L.append("    tierces CONTRE le x%s : %s"
                 % (SETUP, _resume(("meme actif", "CONTRE"))))
        L.append("  Si CONTRE perd la ou AVEC passe, les regles V10/V11")
        L.append("  doivent respecter la priorite du x%s. Si les deux se"
                 % SETUP)
        L.append("  valent, la direction du x%s n est pas une consigne."
                 % SETUP)
        L.append("")
'''

N2 = '''        def _resume(org, sens):
            n, fin = 0, []
            for k, c in ac.items():
                if k[1] != "meme actif" or k[2] != sens:
                    continue
                if org is not None and k[0] != org:
                    continue
                n += c["n"]
                fin += c["fin"]
            if not n:
                return "aucune presence"
            nf, _s1, mf, _a1, _b1, _d1 = ratios(fin)
            return ("%2d presences, issue moyenne %s"
                    % (n, ("%+.2f EUR" % mf) if nf else "inconnue"))
        L.append("  D UN COUP D OEIL, sur le MEME actif -- TOUTES entrees :")
        L.append("    tierces AVEC   le x%s : %s"
                 % (SETUP, _resume(None, "AVEC")))
        L.append("    tierces CONTRE le x%s : %s"
                 % (SETUP, _resume(None, "CONTRE")))
        L.append("")
        L.append("  LES MEMES, x%s PREMIER ENTRES SEULEMENT -- les seuls a"
                 % SETUP)
        L.append("  porter une information :")
        L.append("    tierces AVEC   le x%s : %s"
                 % (SETUP, _resume("PREMIER", "AVEC")))
        L.append("    tierces CONTRE le x%s : %s"
                 % (SETUP, _resume("PREMIER", "CONTRE")))
        L.append("")
        L.append("  C est la SECONDE paire qui decide. Si l ecart y")
        L.append("  survit, la direction du x%s est une consigne et les"
                 % SETUP)
        L.append("  regles V10/V11 doivent respecter sa priorite. S il")
        L.append("  disparait, la premiere paire ne montrait qu un reverse")
        L.append("  se refletant dans son propre miroir : dans un reverse,")
        L.append("  etre contre le x%s et etre en perte ont la MEME cause."
                 % SETUP)
        L.append("")
'''

A3 = '''        L.append("%-13s %-8s %10s %14s %8s %13s"
                 % ("actif", "sens", "presences", "latent moyen",
                    "connus", "final moyen"))
        L.append("-" * LARG)
        for k in sorted(ac):
            c = ac[k]
            _nl, _sl, ml, _r1, _p1, _s1 = ratios(c["lat"])
            nf, _sf, mf, _r2, _p2, _s2 = ratios(c["fin"])
            L.append("%-13s %-8s %10d %14.2f %8d %13s"
                     % (k[0], k[1], c["n"], ml, nf,
                        ("%.2f" % mf) if nf else "-"))
        L.append("-" * LARG)
'''

N3 = '''        L.append("%-9s %-13s %-8s %10s %14s %8s %13s"
                 % ("entree", "actif", "sens", "presences", "latent moyen",
                    "connus", "final moyen"))
        L.append("-" * LARG)
        for k in sorted(ac):
            c = ac[k]
            _nl, _sl, ml, _r1, _p1, _s1 = ratios(c["lat"])
            nf, _sf, mf, _r2, _p2, _s2 = ratios(c["fin"])
            L.append("%-9s %-13s %-8s %10d %14.2f %8d %13s"
                     % (k[0], k[1], k[2], c["n"], ml, nf,
                        ("%.2f" % mf) if nf else "-"))
        L.append("-" * LARG)
        L.append("  'entree' : REVERSE = une SORTIE du MEME magic a moins")
        L.append("  de %d s -- la direction du x%s vient de s inverser."
                 % (REV_S, SETUP))
        L.append("  PREMIER = tout le reste. Un x%s qui vivrait moins de"
                 % SETUP)
        L.append("  %d s serait classe REVERSE a tort : aucun cas au 13/08."
                 % REV_S)
'''

REMPLACEMENTS = [
    ("le comptage des tierces", A1, N1),
    ("la synthese en tete de section", A2, N2),
    ("le tableau detaille", A3, N3),
]


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
        print("KO : patch_x60_avec_contre n est pas applique sur ce fichier.")
        print("     Ce patch modifie la section qu il pose. Applique-le")
        print("     d abord. Rien n a ete ecrit.")
        return 1

    for nom, anc, _n in REMPLACEMENTS:
        c = src.count(anc)
        if c != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (c, nom))
            print("Rien n a ete ecrit.")
            return 1
    print("Trois ancres, chacune unique.")

    neuf = src
    for _nom, anc, nou in REMPLACEMENTS:
        neuf = neuf.replace(anc, nou, 1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # ast.parse ne verrait pas _origine defini dans une autre fonction que
    # celle qui l appelle : ce serait un NameError a l execution, pas une
    # erreur de syntaxe, et il ne se manifesterait qu au prochain rapport.
    ok = False
    for f in ast.walk(arbre):
        if isinstance(f, ast.FunctionDef) and f.name == "rapport":
            d = ast.dump(f)
            ok = ("_origine" in d and "_sort_magic" in d
                  and "REVERSE" in d and "PREMIER" in d)
    if not ok:
        print("KO : _origine n est pas dans rapport(). Ce serait un")
        print("     NameError au prochain rapport, pas une erreur de")
        print("     syntaxe. Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : _origine et son index sont dans rapport().")

    print()
    print("La section distingue desormais PREMIER ENTRE et REVERSE.")
    print()
    print("Dans un reverse, toute position du meme actif est du mauvais")
    print("cote ET en perte pour la MEME cause -- le marche vient de se")
    print("retourner. La correlation y est garantie par construction,")
    print("comme l etait le gain des jambes PARTIEL70 ce matin.")
    print()
    print("La synthese donne les deux lectures l une sous l autre. C est")
    print("la seconde -- PREMIER seul -- qui decide si la direction du")
    print("x60 est une consigne pour V10/V11.")

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
