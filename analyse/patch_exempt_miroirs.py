# -*- coding: utf-8 -*-
"""
patch_exempt_miroirs.py -- les miroirs paper ne sortent que par leur parent.

  python patch_exempt_miroirs.py --essai       (n ecrit rien, montre tout)
  python patch_exempt_miroirs.py

CE QUE CA CHANGE

  Trois modules ferment aujourd hui des positions qui ne leur
  appartiennent pas. Le 21/08, sur 59 miroirs soldes :

      M154_FOLLOW_*  30   m154_leader_gate.py
      IGN_COVER      18   short_cover.py
      PREOPEN_75      1   preopen_protect.py

  Les trois qui ferment 80 % des PARENTS -- IGNT_REVERSE, IGN_REVERSE,
  IGNT_TRAIL70 -- n ont jamais touche un miroir. Comparer les P&L des
  deux populations ne mesurait donc rien du tout.

CE QUE CA NE CHANGE PAS

  Aucune sortie de parent. On n enleve rien a personne : on ajoute une
  plage de magics qui n a jamais appartenu qu aux miroirs. Le magic le
  plus haut de la stack reelle est 208303 ; 251xxx, 300000-460000,
  2000815 et 20001711 sont hors de la fenetre 220000-249999.

SURETE

  Chaque greffe importe papers_exempt DANS UN try, avec une repli en
  dur si le module manque. Un import rate ne peut donc pas casser une
  boucle vivante -- c est la seule facon d y toucher sans risquer de
  modifier, par accident, le sort des parents.

  Le script verifie chaque ancre, garde une copie .avant-miroirs de
  chaque fichier, relit le resultat avec ast.parse, et traite les
  fichiers un par un : si l un echoue, les autres restent valides.

APRES

  trading_engine.py charge ces trois modules par _start_module. Rien
  ne prend effet avant qu il ne les relise, c est-a-dire au prochain
  demarrage du moteur.
"""
import argparse
import ast
import io
import os
import shutil
import sys

MARQUE = "_est_miroir_paper"

IMPORT = '''# 2026-08-21 (user) : les miroirs paper sortent UNIQUEMENT par leur
# parent. Import protege : si papers_exempt manque, le repli en dur
# prend le relais et cette boucle ne peut pas casser.
try:
    from papers_exempt import est_miroir as _est_miroir_paper
except Exception:
    def _est_miroir_paper(magic):
        try:
            return 220000 <= int(magic) < 250000
        except Exception:
            return False


'''

TRAVAUX = [
    ("m154_leader_gate.py", [
        ("def _convoi_exempt(magic):",
         IMPORT + "def _convoi_exempt(magic):"),
        ("        if magic == 0 or magic in EXEMPT_MAGICS or magic in"
         " _LEADER_SET or _convoi_exempt(magic):\n"
         "            continue\n",
         "        if (magic == 0 or magic in EXEMPT_MAGICS"
         " or magic in _LEADER_SET\n"
         "                or _convoi_exempt(magic)"
         " or _est_miroir_paper(magic)):\n"
         "            continue\n"),
    ]),
    ("short_cover.py", [
        ("def _is_cover_full_exempt(magic):",
         IMPORT + "def _is_cover_full_exempt(magic):"),
        ("    if (m // 1000) in (206, 207, 208):\n"
         "        return True\n",
         "    if (m // 1000) in (206, 207, 208):\n"
         "        return True\n"
         "    if _est_miroir_paper(m):\n"
         "        return True\n"),
    ]),
    ("preopen_protect.py", [
        ("def _close_partial(p, vol):\n    try:\n",
         IMPORT + "def _close_partial(p, vol):\n"
         "    if _est_miroir_paper(p.magic):\n"
         "        return False\n"
         "    try:\n"),
        ("def _move_be(p):\n", "def _move_be(p):\n"
         "    if _est_miroir_paper(p.magic):\n"
         "        return False\n"),
    ]),
]


def traite(nom, paires, essai):
    if not os.path.isfile(nom):
        return nom, "ABSENT", "fichier introuvable"
    s = io.open(nom, encoding="utf-8", errors="strict").read()
    if MARQUE in s:
        return nom, "DEJA", "greffe deja presente"
    for i, (av, _ap) in enumerate(paires, 1):
        n = s.count(av)
        if n != 1:
            return nom, "ANCRE", "ancre %d trouvee %d fois" % (i, n)
    neuf = s
    for av, ap in paires:
        neuf = neuf.replace(av, ap, 1)
    try:
        ast.parse(neuf)
    except SyntaxError as e:
        return nom, "SYNTAXE", str(e)
    if essai:
        return nom, "PRET", "%d -> %d octets" % (len(s.encode()),
                                                 len(neuf.encode()))
    shutil.copy2(nom, nom + ".avant-miroirs")
    io.open(nom, "w", encoding="utf-8", newline="\n").write(neuf)
    return nom, "ECRIT", "%d -> %d octets, copie en %s.avant-miroirs" % (
        len(s.encode()), len(neuf.encode()), nom)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--essai", action="store_true",
                   help="verifie tout et n ecrit rien")
    a = p.parse_args()

    if not os.path.isfile("papers_exempt.py"):
        print("KO : papers_exempt.py doit etre a cote (source unique des")
        print("     plages). Recopie-le du Drive avant de patcher.")
        print("Repertoire courant : %s" % os.getcwd())
        return 1

    print("EXEMPTION DES MIROIRS PAPER%s" % ("  --  ESSAI, rien n est ecrit"
                                             if a.essai else ""))
    print("=" * 70)
    dur = 0
    for nom, paires in TRAVAUX:
        f, etat, note = traite(nom, paires, a.essai)
        print("  %-24s %-8s %s" % (f, etat, note))
        if etat in ("ANCRE", "SYNTAXE", "ABSENT"):
            dur += 1
    print("=" * 70)
    if dur:
        print("  %d fichier(s) NON traite(s). Les autres sont intacts et" % dur)
        print("  coherents : rien n est a moitie ecrit.")
    if a.essai:
        print("  Essai seulement. Relance sans --essai pour ecrire.")
    else:
        print("  Rien ne prend effet avant le prochain demarrage de")
        print("  trading_engine.py : c est lui qui charge ces modules.")
    return 1 if dur else 0


if __name__ == "__main__":
    sys.exit(main())
