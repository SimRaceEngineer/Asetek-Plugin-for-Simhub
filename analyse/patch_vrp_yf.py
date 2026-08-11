#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_vrp_yf.py -- un seul fetch Yahoo vivant a la fois dans vrp_monitor

CE QU ON A ETABLI LE 11/08, py-spy a l appui
    Le moteur s est fige seize minutes en pleine seance, positions ouvertes.
    Le dump de sa pile montre des DIZAINES de threads arretes au meme
    endroit :

        __enter__ (warnings.py:81)
        _add_filter (_py_warnings.py:321)
        simplefilter (_py_warnings.py:310)
           ...
        _run (vrp_monitor.py:765)

    yfinance appelle warnings.simplefilter a chaque requete. En Python 3.14
    la liste globale des filtres est protegee par un verrou. Quinze threads
    qui le demandent en meme temps serialisent tout le processus -- y
    compris les threads de trading, qui n ont rien demande.

LA CAUSE EXACTE, ET ELLE EST SUBTILE
        th = threading.Thread(target=_run, daemon=True, name=f"yf_{symbol}")
        th.start()
        th.join(8.0)
        return box["v"]   # None si le thread n a pas fini -> degrade propre

    join(8.0) n arrete PAS le thread. Il arrete l ATTENTE. Python ne sait
    pas tuer un thread. Chaque appel qui expire laisse donc derriere lui un
    thread bien vivant, bloque dans yfinance, qui tiendra le verrou des
    warnings jusqu a la fin du processus.

    Et ca s auto-alimente : plus il y a de threads bloques, plus la
    contention est forte, plus les appels suivants expirent, plus il fuit
    de threads. C est pour ca que le blocage a dure 105 secondes a 14:52 et
    seize minutes a 15:16 -- ca empire avec la seance. Le 02/08, la pile n a
    jamais cesse de croitre : seize heures de blocage continu.

    Cadence : get_term_structure() appelle _yf_fetch deux fois (^VIX9D et
    ^VIX3M) toutes les 60 secondes. Cent vingt threads par heure.

CE QUE FAIT CE PATCH
    Avant de lancer un thread, on regarde si le PRECEDENT tourne encore.
    S il tourne, on ne lance rien et on rend la derniere valeur connue.

    Consequence : au plus UN thread Yahoo vivant par symbole, jamais deux.
    Si l un se bloque pour de bon, il reste bloque -- Python ne permet pas
    de le tuer -- mais il sera SEUL. La boucle d amplification disparait, et
    c est elle le probleme, pas le thread isole.

CE QU IL AMELIORE AU PASSAGE
    L original rendait None quand le fetch expirait. Ici on rend la
    derniere valeur connue. Une structure par terme vieille d une minute
    vaut mieux qu une absence de structure par terme -- et le champ est
    declare non critique par le module lui-meme.

CE QU IL NE FAIT PAS
    Il ne touche ni au delai de 8 secondes, ni au timeout=6 de yfinance, ni
    au TTL de 60 secondes. Ce sont des choix documentes, et le probleme
    n etait aucun des trois.

    Il ne deplace pas vrp_monitor hors du processus moteur. C est la vraie
    reponse de fond -- rien qui parle a un service externe lent ne devrait
    vivre dans le processus qui gere les positions -- mais c est un chantier,
    et celui-ci arrete l hemorragie ce soir.

IDEMPOTENT. Prend effet au prochain demarrage du moteur.

POURQUOI L ANCRE EST UNE EXPRESSION ET NON UNE CHAINE
    Premier jet : ancre litterale incluant le commentaire de fin de ligne,
    que j avais recopie "n a pas fini" alors que le fichier ecrit "n'a pas
    fini". Zero occurrence, patch refuse. Un commentaire est du texte libre
    -- il change au fil des relectures et supporte les apostrophes. On
    ancre sur le CODE, et on laisse la fin de ligne libre.
"""
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "vrp_monitor.py"
MARQUEUR = "_yf_en_vol"

ANCRE_ETAT = "def _yf_fetch(symbol):"
NEUF_ETAT = '''# 11/08 : un seul fetch Yahoo vivant a la fois, par symbole.
# join(8.0) n arrete pas le thread, il arrete l attente -- chaque appel
# qui expirait laissait un thread bloque dans warnings.simplefilter, et
# chaque thread de plus aggravait la contention qui faisait expirer les
# suivants. py-spy a montre des dizaines de ces threads le 11/08, pendant
# que le moteur restait fige seize minutes avec des positions ouvertes.
_yf_verrou = threading.Lock()
_yf_en_vol = {}      # symbole -> Thread encore vivant, ou absent
_yf_dernier = {}     # symbole -> derniere valeur connue


def _yf_fetch(symbol):'''

# Ancre par expression : les quatre lignes de code, indentation capturee,
# et la fin de la derniere ligne laissee libre -- c est la que vit le
# commentaire, et un commentaire n est pas un point d ancrage fiable.
RE_CORPS = re.compile(
    r'^([ \t]*)th = threading\.Thread\(target=_run, daemon=True, '
    r'name=f"yf_\{symbol\}"\)[ \t]*\n'
    r'[ \t]*th\.start\(\)[ \t]*\n'
    r'[ \t]*th\.join\(8\.0\)[ \t]*\n'
    r'[ \t]*return box\["v"\].*$',
    re.M)

NEUF_CORPS = '''    # Le precedent tourne-t-il encore ? Si oui, en lancer un second
    # aggraverait exactement ce qu on veut eviter.
    with _yf_verrou:
        vieux = _yf_en_vol.get(symbol)
        if vieux is not None and vieux.is_alive():
            return _yf_dernier.get(symbol)

    th = threading.Thread(target=_run, daemon=True, name=f"yf_{symbol}")
    with _yf_verrou:
        _yf_en_vol[symbol] = th
    th.start()
    th.join(8.0)

    if box["v"] is not None:
        with _yf_verrou:
            _yf_dernier[symbol] = box["v"]
        return box["v"]
    # Expire : le thread vit encore, on ne le relancera pas tant qu il
    # n aura pas fini. On rend la derniere valeur connue plutot que None --
    # une structure par terme d il y a une minute vaut mieux que rien.
    return _yf_dernier.get(symbol)'''


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

    if "import threading" not in src:
        print("KO : vrp_monitor.py n importe pas threading, ce qui est")
        print("impossible puisqu il cree des Thread. Le fichier n est pas")
        print("celui que j attends -- rien n a ete ecrit.")
        return 1

    if src.count(ANCRE_ETAT) != 1:
        print("KO : %d occurrence(s) de 'def _yf_fetch(symbol):', il en faut 1."
              % src.count(ANCRE_ETAT))
        return 1

    trouve = RE_CORPS.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) du corps de _yf_fetch, il en faut 1."
              % len(trouve))
        print("Attendu, a n importe quelle indentation, le commentaire de")
        print("fin de derniere ligne pouvant etre quelconque :")
        print('    th = threading.Thread(target=_run, daemon=True, '
              'name=f"yf_{symbol}")')
        print("    th.start()")
        print("    th.join(8.0)")
        print('    return box["v"]')
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
    print("Au plus un thread Yahoo vivant par symbole, desormais.")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DU MOTEUR -- pas avant.")
    print("Ne redemarre pas en seance avec des positions ouvertes : c est")
    print("ce qui a coute cher le 10/08.")
    print()
    print("Apres le redemarrage, pour verifier que la fuite est bouchee :")
    print("    py-spy dump --pid PID_DU_MOTEUR > logs\\pyspy_apres.txt")
    print("    (Select-String -Path logs\\pyspy_apres.txt -Pattern 'yf_').Count")
    print()
    print("Ce compte doit rester a un ou deux. Avant le patch, py-spy en")
    print("montrait des dizaines.")
    print()
    print("A verifier aussi : macro_feed.py fait-il la meme chose ?")
    print("    Select-String -Path macro_feed.py -Pattern 'join\\(' -Context 3,3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
