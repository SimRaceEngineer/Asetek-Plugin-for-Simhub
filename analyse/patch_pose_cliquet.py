#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_pose_cliquet.py -- pose le cliquet dans chaque processus qui ecrit

  python patch_pose_cliquet.py               simulation
  python patch_pose_cliquet.py --appliquer

POURQUOI DANS CHACUN
    Une enveloppe sur mt5.order_send ne vit que dans le processus ou
    elle a ete posee. Le 26/08, quatre processus ecrivaient des stops
    sans le moindre controle : le moteur avait sl_arbitre -- decroche --
    et les trois autres n avaient rien du tout.

    La consigne est la meme sur les deux comptes : une fois le stop
    deplace dans le sens du gain, il ne revient pas. L envoyeur du pont
    ecrit sur 18**09, le moteur sur le compte principal ; les deux
    doivent porter le cliquet.

OU
    trading_engine.py   a cote de la pose de sl_arbitre, qui existe deja
    pont_miroirs.py     apres mt5.initialize(path=args.terminal)
    miroir_papers.py    apres mt5.initialize(path=_TERM_MOTEUR)
    price_action.py     apres son initialize, s il en a un

    Pour les trois derniers, l ancre est la ligne "if not mt5.initialize"
    et l insertion se fait apres la FIN de son bloc -- la premiere ligne
    dont l indentation revient au niveau du if. On ne compte pas les
    lignes du bloc, on lit l indentation : un bloc de deux ou de cinq
    lignes se traite pareil.

CE QU IL NE FAIT PAS
    Il ne retire pas sl_arbitre. Celui-ci reste, inoffensif : il observe
    ce qu il voit encore passer. Le cliquet se pose PAR-DESSUS et se
    repose tout seul quand un gate le decroche.

    Un fichier absent ou deja patche est saute sans faire echouer les
    autres -- chaque fichier est traite independamment.

IDEMPOTENT. Sauvegarde horodatee, relecture, ecart de taille verifie.
"""
import argparse
import io
import os
import shutil
import sys
import time

MARQUE = "sl_cliquet"

BLOC_MOTEUR_IMPORT = ["import sl_cliquet as _sl_cli"]
BLOC_MOTEUR_POSE = ["_sl_cli.install(mt5, globals().get(\"log\"))"]

BLOC_APRES_INIT = [
    "",
    "# 27/08 : le cliquet des stops. Un stop deplace dans le sens du gain",
    "# ne revient jamais, sur ce compte comme sur l autre. Il garde sa",
    "# propre memoire du meilleur stop par ticket, donc un effacement",
    "# chez le courtier ne l amnesie pas, et un fil de veille le repose",
    "# si une enveloppe de gate le decroche.",
    "try:",
    "    import sl_cliquet as _sl_cli",
    "    _sl_cli.install(mt5, None)",
    "except Exception:",
    "    pass",
]

CIBLES = [
    # (fichier, mode, ancre)
    ("trading_engine.py", "moteur", None),
    ("pont_miroirs.py", "init", "if not mt5.initialize(path=args.terminal):"),
    ("miroir_papers.py", "init", "if not mt5.initialize(path=_TERM_MOTEUR):"),
    ("price_action.py", "init", None),
]


def charge(c):
    with io.open(c, encoding="latin-1", newline="") as f:
        return f.read()


def creux_de(ligne):
    corps = ligne.rstrip("\r")
    return corps[:len(corps) - len(corps.lstrip())]


def insere(lignes, i, bloc, creux):
    fin = "\r" if lignes[i].endswith("\r") else ""
    lignes[i + 1:i + 1] = [(creux + x if x else "") + fin for x in bloc]
    return len(bloc)


def trouve_unique(lignes, cible):
    vus = [i for i, l in enumerate(lignes) if l.rstrip("\r").strip() == cible]
    return vus[0] if len(vus) == 1 else -1


def trouve_inits(lignes):
    """TOUS les appels a mt5.initialize, du dernier au premier.

    27/08 : la premiere version exigeait un appel UNIQUE et sautait donc
    pont_miroirs.py, qui en a deux -- un par role, lecteur et envoyeur --
    et price_action.py, qui appelle sans "if not". Or c est justement
    l envoyeur du pont qui ecrit les stops sur le compte dedie. On pose
    donc apres CHAQUE appel, et on parcourt a l envers pour que les
    insertions ne decalent pas les indices restants.
    """
    vus = []
    for i, l in enumerate(lignes):
        s = l.rstrip("\r").strip()
        if "mt5.initialize(" in s and not s.startswith("#"):
            vus.append(i)
    return list(reversed(vus))


def fin_de_bloc(lignes, i):
    """La premiere ligne apres le bloc du if : indentation revenue au niveau."""
    creux = creux_de(lignes[i])
    j = i + 1
    while j < len(lignes):
        l = lignes[j].rstrip("\r")
        if l.strip() and creux_de(lignes[j]) <= creux:
            return j - 1        # on insere APRES la derniere ligne du bloc
        j += 1
    return len(lignes) - 1


def traite(fichier, mode, ancre, appliquer):
    if not os.path.exists(fichier):
        print("  %-22s absent, saute" % fichier)
        return None
    texte = charge(fichier)
    if MARQUE in texte:
        print("  %-22s DEJA PATCHE" % fichier)
        return None
    lignes = texte.split("\n")

    if mode == "moteur":
        i = trouve_unique(lignes, "import sl_arbitre as _sl_arb")
        j = trouve_unique(lignes, '_sl_arb.install(mt5, globals().get("log"))')
        if i < 0 or j < 0:
            print("  %-22s ANCRE sl_arbitre introuvable ou multiple" % fichier)
            return False
        # on insere d abord la POSE (indice le plus grand), sinon l autre
        # insertion decalerait cet indice-la.
        insere(lignes, j, BLOC_MOTEUR_POSE, creux_de(lignes[j]))
        insere(lignes, i, BLOC_MOTEUR_IMPORT, creux_de(lignes[i]))
        print("  %-22s pose apres la ligne %d, import apres la ligne %d"
              % (fichier, j + 1, i + 1))
    else:
        inits = trouve_inits(lignes)
        if not inits:
            print("  %-22s aucun appel a mt5.initialize, saute" % fichier)
            return None
        for i in inits:
            f = fin_de_bloc(lignes, i)
            insere(lignes, f, BLOC_APRES_INIT, creux_de(lignes[i]))
            print("  %-22s pose apres la ligne %d (initialize ligne %d)"
                  % (fichier, f + 1, i + 1))

    neuf = "\n".join(lignes)
    if not appliquer:
        return True
    sauve = "%s.avant_cliquet_%s" % (fichier, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(fichier, sauve)
    with io.open(fichier, "w", encoding="latin-1", newline="") as f2:
        f2.write(neuf)
    relu = charge(fichier)
    ok = relu == neuf and MARQUE in relu
    print("      sauvegarde %s  ecart %+d octets  %s"
          % (sauve, len(relu.encode("latin-1")) - len(texte.encode("latin-1")),
             "ok" if ok else "ECHEC -- restaurer"))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if not os.path.exists("sl_cliquet.py"):
        print("ABANDON : sl_cliquet.py doit etre a cote des fichiers a patcher.")
        return 2

    print("pose du cliquet -- %s" % ("ECRITURE" if a.appliquer else "SIMULATION"))
    print("")
    res = [traite(f, m, an, a.appliquer) for f, m, an in CIBLES]
    faits = [x for x in res if x is not None]
    print("")
    if False in faits:
        print("Au moins un fichier a echoue : voir ci-dessus.")
        return 2
    if not faits:
        print("Rien a faire : tout est deja pose, ou les fichiers sont absents.")
        return 0
    if not a.appliquer:
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer pour ecrire.")
        return 0
    print("Chaque processus touche doit REDEMARRER pour poser le cliquet :")
    print("  un processus Python ne relit pas son fichier apres son demarrage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
