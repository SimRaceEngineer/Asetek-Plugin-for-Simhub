#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_miroir_v5.py -- corrige charge_jeu() dans miroir_papers.py

LE DEFAUT
    La v4 exigeait que _charge_modules() rende exactement DEUX objets,
    parce que papers(pe, pr) en prend deux. Il en rend un autre nombre.
    Resultat : "Aucun paper chargeable", et le miroir refuse d envoyer
    -- comportement correct, mais boucle arretee.

LA CORRECTION
    On n impose plus le nombre ni l ordre. Les deux modules utiles sont
    identifies par ce qu ils PORTENT : celui qui a CLES est pe, celui
    qui a REGLES est pr. Trois formes d appel sont tentees dans l ordre,
    et celle qui marche est annoncee.

    Ecrit un .bak avant de toucher au fichier. Refuse si l ancre n est
    pas trouvee, refuse si le correctif est deja pose.

    python patch_miroir_v5.py            applique
    python patch_miroir_v5.py --essai    montre sans ecrire
    python patch_miroir_v5.py --defaire  restaure le .bak
"""

import os
import shutil
import sys

CIBLE = "miroir_papers.py"

ANCRE = '''    try:
        mods = charge()
    except Exception as e:
        return None, None, None, ["_charge_modules a echoue : %s: %s"
                                  % (type(e).__name__, e)]
    if not isinstance(mods, (tuple, list)) or len(mods) != 2:
        return None, None, None, ["_charge_modules rend %r, deux modules "
                                  "attendus" % (type(mods).__name__,)]

    try:
        entrees = list(fabrique(mods[0], mods[1]))
    except Exception as e:
        return None, None, None, ["papers() a echoue : %s: %s"
                                  % (type(e).__name__, e)]
'''

REMPLACEMENT = '''    try:
        mods = charge()
    except Exception as e:
        return None, None, None, ["_charge_modules a echoue : %s: %s"
                                  % (type(e).__name__, e)]
    if not isinstance(mods, (tuple, list)):
        mods = (mods,)
    notes.append("_charge_modules rend %d objet(s)" % len(mods))

    # On identifie les deux modules par ce qu ils PORTENT, pas par leur
    # rang : papers() lit pe.CLES et pr.REGLES. Supposer l ordre ou le
    # nombre, c est ce qui a fait echouer la v4.
    pe = pr = None
    for m in mods:
        if pe is None and hasattr(m, "CLES"):
            pe = m
        if pr is None and hasattr(m, "REGLES"):
            pr = m

    essais = []
    if pe is not None and pr is not None:
        essais.append(("CLES + REGLES", (pe, pr)))
    if len(mods) >= 2:
        essais.append(("les deux premiers", (mods[0], mods[1])))
    essais.append(("tous", tuple(mods)))

    entrees, derniere = None, "aucun essai"
    for comment, args in essais:
        try:
            entrees = list(fabrique(*args))
            notes.append("papers() appele avec %s" % comment)
            break
        except Exception as e:
            derniere = "%s (%s: %s)" % (comment, type(e).__name__, e)
    if entrees is None:
        return None, None, None, ["papers() a echoue -- dernier essai : %s"
                                  % derniere,
                                  "_charge_modules a rendu %d objet(s) : %s"
                                  % (len(mods),
                                     ", ".join(getattr(m, "__name__", type(m).__name__)
                                               for m in mods))]
'''

TEMOIN = "On identifie les deux modules par ce qu ils PORTENT"


def main():
    args = sys.argv[1:]
    essai = "--essai" in args
    defaire = "--defaire" in args
    bak = CIBLE + ".bak"

    print("=" * 78)
    print("PATCH MIROIR v5 -- charge_jeu()")
    print("=" * 78)
    print()

    if defaire:
        if not os.path.isfile(bak):
            print("  pas de %s a restaurer." % bak)
            return
        shutil.copy2(bak, CIBLE)
        print("  %s restaure depuis %s" % (CIBLE, bak))
        return

    if not os.path.isfile(CIBLE):
        print("  %s introuvable. Place-toi dans le dossier de la stack." % CIBLE)
        return

    with open(CIBLE, encoding="utf-8") as f:
        s = f.read()

    if TEMOIN in s:
        print("  Le correctif est deja pose. Rien a faire.")
        return
    if ANCRE not in s:
        print("  Ancre introuvable : ce fichier n est pas la v4 attendue.")
        print("  Rien n a ete modifie. Recopie miroir_papers_v4.py depuis")
        print("  le Drive, puis relance ce patch.")
        return

    neuf = s.replace(ANCRE, REMPLACEMENT, 1)

    try:
        compile(neuf, CIBLE, "exec")
    except SyntaxError as e:
        print("  Le resultat ne compile pas (%s). Rien n a ete ecrit." % e)
        return

    if essai:
        print("  Ancre trouvee, resultat compile.")
        print("  %d octets -> %d octets" % (len(s), len(neuf)))
        print("  --essai : rien n a ete ecrit.")
        return

    shutil.copy2(CIBLE, bak)
    with open(CIBLE, "w", encoding="utf-8", newline="\n") as f:
        f.write(neuf)
    print("  sauvegarde : %s" % bak)
    print("  %s corrige (%d -> %d octets)" % (CIBLE, len(s), len(neuf)))
    print()
    print("  Relance :  python miroir_papers.py --armer")


if __name__ == "__main__":
    main()
