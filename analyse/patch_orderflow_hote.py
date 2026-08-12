# -*- coding: utf-8 -*-
"""
patch_orderflow_hote.py -- le 8097 ecoute enfin ailleurs que sur la boucle locale

  python patch_orderflow_hote.py --essai
  python patch_orderflow_hote.py

LE DEFAUT, MESURE ET PAS SUPPOSE

    Get-NetTCPConnection, 12/08/2026 22:39 :

        127.0.0.1   8097   7996     orderflow_panel
        0.0.0.0     8095   10704    price_action

    Et depuis le VPS lui-meme, par son nom externe :
    8097 : False, 8095 : True.

    orderflow_panel.py ligne 336 :

        HTTPServer(("127.0.0.1", a.port), H).serve_forever()

    L adresse est ecrite en dur. Un socket lie a 127.0.0.1 n accepte
    que les connexions venues de la machine elle-meme. AUCUNE regle de
    pare-feu ne peut y changer quoi que ce soit : le paquet arrive bien
    jusqu a la pile TCP, il n y a simplement pas de socket pour lui sur
    cette interface. C est pour ca que le navigateur voyait un timeout
    et pas un refus.

CE QUE LE PATCH CHANGE -- TROIS LIGNES

    1. un argument --hote, defaut 0.0.0.0 (toutes interfaces)
    2. le bind utilise a.hote au lieu de la constante
    3. le print de demarrage affiche l adresse reelle, pas localhost
       en dur -- sinon le journal continuerait a mentir sur ce qu il
       vient de faire

CE QU IL NE TOUCHE PAS

    Le reste du fichier, le port, les handlers, le wrapper. La boucle
    run_orderflow_loop.bat n a pas besoin d etre modifiee : elle lance
    le script sans --hote, donc elle prend le defaut.

EXPOSITION -- A LIRE UNE FOIS

    0.0.0.0 rend le panneau visible de tout Internet, sans mot de
    passe, comme l est deja le 8095. Ca n augmente pas l exposition du
    VPS, mais ca ne la reduit pas non plus.

    Pour restreindre a une seule adresse, lancer avec --hote <ip>, ou
    ajouter cet argument dans run_orderflow_loop.bat. Le patch rend ce
    choix possible ; il ne le fait pas a ta place.

    Cote pare-feu, la regle « Orderflow 8097 » creee le 12/08 devient
    utile a partir de maintenant. Avant ce patch elle ne servait a rien.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
PREND EFFET AU PROCHAIN DEMARRAGE DU 8097.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "orderflow_panel.py"
MARQUEUR = "--hote"

RE_ARG = re.compile(
    r'^([ \t]*)ap\.add_argument\("--port", type=int, default=8097\)[ \t]*$',
    re.M)

RE_PRINT = re.compile(
    r'^([ \t]*)print\("orderflow panel -> http://localhost:%d/" % a\.port\)'
    r'[ \t]*$', re.M)

RE_BIND = re.compile(
    r'^([ \t]*)HTTPServer\(\("127\.0\.0\.1", a\.port\), H\)\.serve_forever\(\)'
    r'[ \t]*$', re.M)

ARG_NEUF = (
    '%(i)s# 12/08/2026 : le panneau ecoutait sur 127.0.0.1 en dur -- donc\n'
    '%(i)s# injoignable depuis l exterieur, quelle que soit la regle de\n'
    '%(i)s# pare-feu, parce qu il n y avait aucun socket sur l interface\n'
    '%(i)s# publique. 0.0.0.0 = toutes interfaces ; --hote <ip> restreint.\n'
    '%(i)sap.add_argument("--hote", default="0.0.0.0")')


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

    ancres = (("l argument --port", RE_ARG),
              ("le print de demarrage", RE_PRINT),
              ("le bind 127.0.0.1", RE_BIND))
    for nom, rx in ancres:
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        print("  %-22s : %s" % (nom, rx.search(src).group(0).strip()))

    neuf = RE_ARG.sub(
        lambda m: m.group(0) + "\n" + ARG_NEUF % {"i": m.group(1)},
        src, count=1)

    neuf = RE_PRINT.sub(
        lambda m: (m.group(1)
                   + 'print("orderflow panel -> http://%s:%d/"'
                     ' % (a.hote, a.port))'),
        neuf, count=1)

    neuf = RE_BIND.sub(
        lambda m: m.group(1) + 'HTTPServer((a.hote, a.port), H).serve_forever()',
        neuf, count=1)

    if '"127.0.0.1"' in neuf.split("def main")[-1]:
        print("KO : il reste un 127.0.0.1 en dur apres substitution.")
        print("Rien n a ete ecrit.")
        return 1

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Trois lignes changees :")
    print("  + ap.add_argument(\"--hote\", default=\"0.0.0.0\")")
    print("  ~ print(... http://%s:%d/ ... % (a.hote, a.port))")
    print("  ~ HTTPServer((a.hote, a.port), H).serve_forever()")
    print()
    print("Le port, les handlers et le wrapper ne bougent pas.")
    print("run_orderflow_loop.bat lance sans --hote : il prend le defaut.")
    print()
    print("0.0.0.0 expose le panneau a tout Internet, sans mot de passe,")
    print("comme l est deja le 8095. Pour restreindre : --hote <ip>.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Redemarre le 8097 pour que ca prenne effet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
