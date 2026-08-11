# -*- coding: utf-8 -*-
"""
patch_us30_trail.py -- rendre a US30 le trailing que NAS100 et SPX500 ont deja

  python patch_us30_trail.py --essai    montre, n ecrit rien
  python patch_us30_trail.py            applique

CE QU ON CORRIGE, ET CE N EST PAS CE QU ON CROIT
    Le journal du trail ne contient aucune ligne US30 du 28/07 au 11/08.
    Cause : 1 069 tickets US30 sur 1 069 portent un magic exclu.

    Mais l exclusion n est pas une politique coherente qu on irait
    contredire. C est une ASYMETRIE entre actifs :

        famille        US30        NAS100          SPX500
        207xxx         exclu       autorise        autorise
        206xxx         exclu       exclu           exclu
        208xxx         exclu       exclu           exclu

    Les memes strategies 207 sont trailees sur NAS100 et SPX500 (207302,
    207305, 207202, 207205, 207260 y passent) et exclues sur US30. Ce patch
    retire donc la seule plage 207000-207999 de la liste US30. Il ne touche
    ni a 206xxx, ni a 208xxx, ni a 24xx, exclus sur les trois actifs -- la,
    la decision est coherente et on la respecte.

CE QUE CA REPRESENTE
        207101   293 tickets   -36 EUR    MFE 10 358    capture  -0 %
        207102   211           -660       MFE  8 703            -8 %
        207105   121         -1 631       MFE  5 628           -29 %
        207160    26           +920       MFE  2 036           +45 %

    651 tickets, 26 725 EUR de MFE atteint, 1 407 EUR rendus en negatif.

CE QUE CE PATCH NE PROMET PAS
    Rendre ces familles eligibles ne leur pose pas un stop pour autant. Il
    faut encore que patch_trail_c14 soit applique -- sans lui, elles
    demanderont un stop au break-even qui sera refuse par C14 comme les
    autres, et on aura seulement remplace un silence par du bruit.

    Le module ne pose son stop QUE s il est plus serre que celui deja en
    place (_is_tighter). Une famille qui gere deja un trail serre ne sera
    donc pas derangee : le calcul rendra une valeur plus lache et rien ne
    partira. Le trail ne mord que la ou le stop existant est plus loin.

VERIFICATION APRES ECRITURE
    Le patch relit le fichier modifie et verifie, en evaluant reellement les
    trois ensembles :
      - US30 perd exactement les 1 000 magics de 207000 a 207999
      - US30 ne perd rien d autre
      - NAS100 et SPX500 sont inchanges, au magic pres
    Si l une des trois echoue, la sauvegarde est restauree.

IDEMPOTENT. Sauvegarde horodatee. PREND EFFET AU PROCHAIN DEMARRAGE.
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
MARQUEUR = "11/08/2026 -- plage 207xxx rendue a US30"
DEBUT, FIN = 207000, 208000

# La plage, avec ou sans espaces, precedee de son operateur d union.
RE_PLAGE = re.compile(r"[ \t]*\|[ \t]*set\(range\(%d,[ \t]*%d\)\)"
                      % (DEBUT, FIN))
RE_DICT = re.compile(r"^(EXCLUDED_MAGICS[ \t]*=[ \t]*\{)", re.M)

NEUF_MARQUE = '''# 11/08/2026 -- plage 207xxx rendue a US30
# Les familles 207 sont trailees sur NAS100 et SPX500 (207302, 207305,
# 207202, 207205, 207260 y passent) et etaient exclues sur US30 seul. Cette
# asymetrie coutait : 651 tickets US30, 26 725 EUR de MFE atteint, 1 407 EUR
# rendus en negatif -- capture -5 %.
# 206xxx, 208xxx et 24xx restent exclus sur les trois actifs : la, la
# decision est coherente entre actifs et on n y touche pas.
'''


class Refus(Exception):
    pass


def _ev(n):
    if isinstance(n, ast.Set):
        return set(ast.literal_eval(e) for e in n.elts)
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
        return _ev(n.left) | _ev(n.right)
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        if n.func.id in ("set", "frozenset") and len(n.args) == 1:
            return _ev(n.args[0])
        if n.func.id == "range":
            return set(range(*[ast.literal_eval(x) for x in n.args]))
    raise Refus("expression non prevue : %s" % type(n).__name__)


def ensembles(src):
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "EXCLUDED_MAGICS"
                for t in n.targets):
            if not isinstance(n.value, ast.Dict):
                raise Refus("EXCLUDED_MAGICS n est pas un dictionnaire")
            return {str(ast.literal_eval(k)): _ev(v)
                    for k, v in zip(n.value.keys, n.value.values)}
    raise Refus("EXCLUDED_MAGICS introuvable")


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1

    src, enc = lire(a.fichier)
    print("%s : %d lignes, encodage %s" % (a.fichier, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    try:
        avant = ensembles(src)
    except (Refus, SyntaxError) as e:
        print("KO : lecture de EXCLUDED_MAGICS impossible : %s" % e)
        return 1

    for k in ("US30", "NAS100", "SPX500"):
        if k not in avant:
            print("KO : la cle %s manque dans EXCLUDED_MAGICS." % k)
            return 1

    vise = set(range(DEBUT, FIN))
    dedans = {k: len(avant[k] & vise) for k in avant}
    print()
    print("%-10s %16s %14s" % ("actif", "magics exclus", "dont 207xxx"))
    print("-" * 46)
    for k in sorted(avant):
        print("%-10s %16d %14d" % (k, len(avant[k]), dedans[k]))
    print("-" * 46)

    if dedans["US30"] == 0:
        print("US30 ne contient aucun magic 207xxx -- rien a retirer.")
        return 0
    if dedans["NAS100"] or dedans["SPX500"]:
        print("KO : NAS100 ou SPX500 contient aussi du 207xxx. L asymetrie")
        print("sur laquelle repose ce patch n existe pas. Rien n a ete ecrit.")
        return 1

    n = len(RE_PLAGE.findall(src))
    if n != 1:
        print("KO : %d occurrence(s) de '| set(range(%d, %d))', il en faut 1."
              % (n, DEBUT, FIN))
        print("Rien n a ete ecrit.")
        return 1

    neuf = RE_PLAGE.sub("", src, count=1)
    neuf = RE_DICT.sub(lambda m: NEUF_MARQUE + m.group(1), neuf, count=1)

    try:
        ast.parse(neuf)
        apres = ensembles(neuf)
    except (Refus, SyntaxError) as e:
        print("KO : le resultat ne tient pas debout : %s" % e)
        print("Rien n a ete ecrit.")
        return 1

    # Les trois post-conditions. Elles sont le coeur de ce patch : retirer
    # du texte d une expression de deux mille caracteres sans les verifier
    # serait de la superstition.
    perdus = avant["US30"] - apres["US30"]
    ennuis = []
    if perdus != vise:
        ennuis.append("US30 perd %d magics au lieu des 1 000 attendus"
                      % len(perdus))
    if apres["US30"] - avant["US30"]:
        ennuis.append("US30 GAGNE des magics, ce qui n a aucun sens")
    for k in ("NAS100", "SPX500"):
        if apres[k] != avant[k]:
            ennuis.append("%s a change alors qu on n y touchait pas" % k)
    if ennuis:
        print("KO :")
        for e in ennuis:
            print("  - %s" % e)
        print("Rien n a ete ecrit.")
        return 1

    print("verifie : US30 perd exactement les 1 000 magics 207000-207999,")
    print("          NAS100 et SPX500 inchanges au magic pres.")

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
    if "BE_ARME_PCT" not in neuf:
        print("ATTENTION : patch_trail_c14 n est PAS applique sur ce fichier.")
        print("Sans lui, les familles 207 d US30 demanderont un stop au")
        print("break-even que C14 refusera, exactement comme les autres.")
        print("On aurait remplace un silence par du bruit. Applique-le.")
        print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DU MOTEUR.")
    print()
    print("A verifier apres une seance complete :")
    print("    python bande_morte.py --depuis %s"
          % datetime.now().strftime("%Y-%m-%d"))
    print("Des lignes US30 doivent apparaitre dans le journal du trail.")
    print("S il n en apparait aucune, l exclusion n etait pas la seule")
    print("raison du silence et il faut chercher ailleurs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
