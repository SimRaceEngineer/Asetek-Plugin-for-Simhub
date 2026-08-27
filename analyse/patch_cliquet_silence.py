#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cliquet_silence.py -- le cliquet cesse de s empiler sur lui-meme

  python patch_cliquet_silence.py --appliquer

CE QUI S EST PASSE
    Journal du moteur, trois minutes apres le demarrage de 09:07 :

        09:07:42 [SL-CLIQUET] repose apres decrochage
        09:08:02 [SL-CLIQUET] repose apres decrochage
        09:08:22 [SL-CLIQUET] repose apres decrochage

    Une par cycle de veille. Quelque chose deloge l enveloppe en
    continu -- et c est exactement ce qui a tue sl_arbitre.

    Mais ma veille testait "suis-je en TETE de chaine". Or un gate qui
    nous ENVELOPPE nous ote la tete sans nous couper : on est toujours
    appele, a travers lui. Se reposer alors ajoute une couche a chaque
    cycle. Trois par minute, vingt-quatre en huit minutes, plusieurs
    centaines d ici l ouverture -- et au-dela du millier Python leve
    RecursionError, ce qui tuerait TOUT envoi d ordre, stops et entrees
    compris.

LE CORRECTIF
    Le critere devient la PRODUCTION et non la position : tant que nos
    enveloppes recoivent des appels, elles travaillent, quelle que soit
    leur place dans la chaine. On ne repose que sur un silence de 90 s
    avere, et un garde-fou a 40 reposes arrete l empilement en criant
    plutot qu en le poursuivant.

    C est la lecon du matin appliquee a mon propre code : verifier ce
    qui est produit, pas ce qui est en place.

Ne prend effet qu au redemarrage des processus concernes.
"""
import argparse
import io
import os
import shutil
import sys
import time

CIBLE = "sl_cliquet.py"
MARQUE = "SILENCE_SEC"

EDITS = [
    # (ancien, neuf) -- remplacements litteraux, un seul par occurrence
    ("VEILLE_SEC = 20         # cadence du fil qui verifie la pose\n",
     "VEILLE_SEC = 20         # cadence du fil qui verifie la pose\n"
     "SILENCE_SEC = 90        # au-dela, une enveloppe muette est jugee decrochee\n"
     "REPOSES_MAX = 40        # garde-fou : au-dela, on cesse et on crie\n"),
    ("_sale = [False]\n",
     "_sale = [False]\n"
     "_appels = [0]           # nombre d appels recus par NOS enveloppes\n"
     "_reposes = [0]\n"),
    ("    def envelope(req, *a, **k):\n        try:\n",
     "    def envelope(req, *a, **k):\n        _appels[0] += 1\n        try:\n"),
    ('''def _veille():
    dernier_ecrit = 0.0
    while True:
        try:
            time.sleep(VEILLE_SEC)
            _arme("repose apres decrochage")
            maintenant = time.time()
''',
     '''def _veille():
    """Repose l enveloppe -- mais seulement si elle ne recoit PLUS RIEN.

    27/08, en direct : la premiere version testait "suis-je en tete de
    chaine". Or un gate qui nous ENVELOPPE nous ote la tete sans nous
    couper : on est toujours appele, a travers lui. Se reposer dans ce
    cas ajoute une couche a chaque cycle -- trois par minute au
    demarrage du moteur -- et la chaine finit par depasser la limite de
    recursion de Python, ce qui tuerait tout envoi d ordre.

    Le bon critere n est pas la position mais la PRODUCTION : tant que
    nos enveloppes recoivent des appels, elles font leur travail, quelle
    que soit leur place. On ne repose que sur un silence avere.
    """
    dernier_ecrit = 0.0
    vus = _appels[0]
    depuis = time.time()
    while True:
        try:
            time.sleep(VEILLE_SEC)
            maintenant = time.time()
            en_tete = getattr(getattr(_mt5, "order_send", None),
                              "_sl_cliquet", None) == VERSION
            if _appels[0] != vus:
                vus, depuis = _appels[0], maintenant      # on travaille
            elif not en_tete and maintenant - depuis > SILENCE_SEC:
                if _reposes[0] < REPOSES_MAX:
                    _reposes[0] += 1
                    _arme("repose apres %ds de silence (%d/%d)"
                          % (SILENCE_SEC, _reposes[0], REPOSES_MAX))
                    depuis = maintenant
                elif _reposes[0] == REPOSES_MAX:
                    _reposes[0] += 1
                    _dire("warning",
                          "  [SL-CLIQUET] %d reposes atteintes, on cesse d empiler."
                          " Quelque chose reecrit order_send en boucle.",
                          REPOSES_MAX)
'''),
    ('''    _dire("warning", "  [SL-CLIQUET] memoire : %d ticket(s) relus, veille %d s",
          n, VEILLE_SEC)''',
     '''    _dire("warning",
          "  [SL-CLIQUET] memoire : %d ticket(s) relus, veille %d s,"
          " silence tolere %d s", n, VEILLE_SEC, SILENCE_SEC)'''),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(CIBLE):
        print("ABANDON : %s introuvable dans %s" % (CIBLE, os.getcwd()))
        return 2
    with io.open(CIBLE, encoding="utf-8", newline="") as f:
        texte = f.read()
    print("%s : %d octets" % (CIBLE, len(texte.encode("utf-8"))))
    if MARQUE in texte:
        print("DEJA PATCHE : %s est present. Rien a faire." % MARQUE)
        return 0

    neuf = texte
    for i, (vieux, remplace) in enumerate(EDITS, 1):
        n = neuf.count(vieux)
        if n != 1:
            print("ABANDON : l ancre %d apparait %d fois au lieu d une." % (i, n))
            print("  %s" % vieux.splitlines()[0][:70])
            return 2
        neuf = neuf.replace(vieux, remplace)
        print("  ancre %d : %s" % (i, vieux.splitlines()[0].strip()[:64]))

    print("")
    if not a.appliquer:
        print("SIMULATION -- rien n a ete ecrit. Relancer avec --appliquer.")
        return 0

    sauve = "%s.avant_silence_%s" % (CIBLE, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    with io.open(CIBLE, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    import py_compile
    try:
        py_compile.compile(CIBLE, doraise=True)
        ok = MARQUE in io.open(CIBLE, encoding="utf-8").read()
    except Exception as e:
        print("ECHEC DE COMPILATION : %s" % e)
        shutil.copy2(sauve, CIBLE)
        print("  sauvegarde restauree.")
        return 2
    print("sauvegarde   : %s" % sauve)
    print("ecart taille : %+d octets"
          % (len(neuf.encode("utf-8")) - len(texte.encode("utf-8"))))
    print("VERIFICATION : %s" % ("ok, et le fichier compile" if ok else "ECHEC"))
    print("")
    print("Sans effet tant que les processus n ont pas redemarre.")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
