#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_macro_yf.py -- meme garde que vrp_monitor, dans macro_feed

LE MEME BUG, ECRIT TROIS SEMAINES PLUS TOT
    macro_feed._fetch_ticker_bounded porte sa propre histoire :

        2026-07-21 : borne le fetch yfinance. yf.Ticker().history() n a PAS
        de timeout -> un hang reseau figeait la boucle macro_feed
        indefiniment (incident 20/07 : VIX/DXY morts 26h -> buddha gate sur
        du VIX perime). Thread daemon + join(timeout) : au-dela on rend 0.0
        et la boucle CONTINUE au lieu de geler.

    Exactement le meme remede que vrp_monitor le 12/06, et exactement le
    meme defaut : join(timeout) n arrete pas le thread, il arrete l attente.
    Le thread reste vivant, bloque dans yfinance -- et depuis le 11/08 on
    sait ou : dans warnings.simplefilter, dont Python 3.14 protege la liste
    globale par un verrou. Chaque thread de plus etrangle un peu plus le
    processus, y compris ses threads de trading.

    Deux modules, deux incidents, deux corrections justes dans l intention
    et identiques dans leur defaut. Ce n est pas une etourderie : c est le
    piege naturel de "borner une operation non interruptible" en Python.

CE QUE FAIT CE PATCH
    Avant de lancer un thread, on regarde si le precedent tourne encore.
    S il tourne, on rend 0.0 -- exactement ce que rend deja un timeout, et
    ce que l en-tete du module documente comme "pas de data ce cycle, on
    garde la derniere valeur". Le contrat d appel ne change pas d un iota.

    Au plus UN thread Yahoo vivant par symbole, jamais deux.

ET IL LEUR DONNE UN NOM
    _th.Thread(target=_run, daemon=True) -- sans nom. Ces threads
    apparaissaient donc en "Thread-N" dans py-spy, et mon comptage sur
    "yf_" ne les voyait pas. Ils s appelleront macro_yf_<symbole>, ce qui
    les rend comptables comme ceux de vrp_monitor.

CE QU IL NE FAIT PAS
    Il ne touche pas au timeout de 12 secondes, ni a la valeur 0.0 rendue
    en cas d echec, ni a la cadence de la boucle. Le probleme n etait aucun
    des trois.

IDEMPOTENT. Prend effet au prochain demarrage du moteur.
"""
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "macro_feed.py"
MARQUEUR = "_mf_en_vol"

ANCRE_ETAT = "def _fetch_ticker_bounded(symbol, timeout=12):"
NEUF_ETAT = '''# 11/08 : un seul fetch Yahoo vivant a la fois, par symbole.
# join(timeout) n arrete pas le thread, il arrete l attente. Chaque appel
# qui expirait laissait un thread bloque dans warnings.simplefilter, dont
# Python 3.14 protege la liste globale par un verrou -- et chaque thread de
# plus aggravait la contention qui faisait expirer les suivants. py-spy a
# montre des dizaines de ces threads le 11/08, pendant que le moteur
# restait fige seize minutes avec des positions ouvertes.
_mf_verrou = threading.Lock()
_mf_en_vol = {}      # symbole -> Thread encore vivant, ou absent


def _fetch_ticker_bounded(symbol, timeout=12):'''

# Ancre par expression, indentation capturee, fin de ligne libre : un
# commentaire de fin de ligne n est pas un point d ancrage fiable -- le
# premier jet du patch vrp a echoue sur une apostrophe recopiee de travers.
RE_CORPS = re.compile(
    r'^([ \t]*)t = _th\.Thread\(target=_run, daemon=True\)[ \t]*\n'
    r'[ \t]*t\.start\(\)[ \t]*\n'
    r'[ \t]*t\.join\(timeout\)[ \t]*\n'
    r'[ \t]*return result\[0\].*$',
    re.M)

NEUF_CORPS = '''    # Le precedent tourne-t-il encore ? Si oui, en lancer un second
    # aggraverait exactement ce qu on veut eviter. On rend 0.0, ce que
    # rend deja un timeout : pas de data ce cycle, la boucle continue.
    with _mf_verrou:
        vieux = _mf_en_vol.get(symbol)
        if vieux is not None and vieux.is_alive():
            return 0.0

    t = _th.Thread(target=_run, daemon=True, name=f"macro_yf_{symbol}")
    with _mf_verrou:
        _mf_en_vol[symbol] = t
    t.start()
    t.join(timeout)
    return result[0]'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % CIBLE)
        return 1

    src, enc = lire(CIBLE)
    print("%s : %d lignes, encodage %s" % (CIBLE, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Garde deja posee -- rien a faire.")
        return 0

    # Le verrou est pose au niveau module : il faut que threading y soit
    # importe. La fonction, elle, fait "import threading as _th" en local.
    if not re.search(r'^import threading\b', src, re.M):
        print("KO : macro_feed.py n a pas d 'import threading' au niveau")
        print("module -- le verrou pose par ce patch ne compilerait pas.")
        print("Rien n a ete ecrit.")
        return 1

    if src.count(ANCRE_ETAT) != 1:
        print("KO : %d occurrence(s) de la signature de _fetch_ticker_bounded,"
              " il en faut 1." % src.count(ANCRE_ETAT))
        return 1

    trouve = RE_CORPS.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) du corps, il en faut 1." % len(trouve))
        print("Attendu, a n importe quelle indentation, la fin de la")
        print("derniere ligne pouvant etre quelconque :")
        print("    t = _th.Thread(target=_run, daemon=True)")
        print("    t.start()")
        print("    t.join(timeout)")
        print("    return result[0]")
        return 1

    ind = trouve[0]
    print("corps trouve : indentation %d espaces" % len(ind))
    corps = "\n".join(ind + l[4:] if l.startswith("    ") else (ind + l if l else "")
                      for l in NEUF_CORPS.split("\n"))

    neuf = src.replace(ANCRE_ETAT, NEUF_ETAT, 1)
    neuf = RE_CORPS.sub(lambda m: corps, neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    sauve = "%s.bak-%s" % (CIBLE, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    io.open(CIBLE, "w", encoding=enc).write(neuf)
    print("Sauvegarde : %s" % sauve)
    print()
    print("Au plus un thread Yahoo vivant par symbole, et ils ont un nom.")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DU MOTEUR -- pas avant.")
    print()
    print("Verification, apres le redemarrage :")
    print("    py-spy dump --pid PID > logs\\pyspy_apres.txt")
    print("    (Select-String -Path logs\\pyspy_apres.txt")
    print("        -Pattern 'yf_|macro_yf_').Count")
    print()
    print("Deux mesures, une au demarrage et une en fin de seance. Si le")
    print("compte est stable entre les deux, la fuite est bouchee -- c est")
    print("la seule preuve qui vaille.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
