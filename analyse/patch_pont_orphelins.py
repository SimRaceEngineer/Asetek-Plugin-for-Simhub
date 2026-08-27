#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_pont_orphelins.py -- un trou nomme vaut mieux qu un trou muet.

CE QUI EST ARRIVE LE 27/08
--------------------------
La branche 6 a ouvert deux positions sur le magic 6240004 :

    15:24:15.916   M6240004 envoye, ticket 172794094  (trailing 0.50R)
    15:24:16.845   M6240004 envoye, ticket 172794099  (trailing 0.50R)

Le pont, lui, est ne a 15:25:33 (lecteur) et 15:25:45 (envoyeur) -- une
minute et quinze secondes trop tard. Au demarrage il fige les positions
vivantes comme simple reference et ne les copie pas : c est voulu, leur
prix d entree appartient au passe et les copier au marche donnerait une
entree fausse.

Mais rien ne le DIT. Le panneau affiche zero affaire pour 6240004, et
rien ne distingue "cette branche n a pas trade" de "ces trades existent
et personne ne les a copies". J ai redemarre le pont trois fois ce
jour-la.

CE QUE CE PATCH AJOUTE
----------------------
Au demarrage de l envoyeur, apres la prise de reference, les positions
ouvertes qui n ont PAS de lien -- donc celles que ce demarrage ne
copiera jamais -- sont comptees, nommees par magic, ecrites dans le
journal et deposees dans docs\pont_miroirs\orphelins.json.

Celles qui ONT un lien ne sont pas des orphelines : elles vivent deja
sur le compte dedie et leur lien continue de les suivre. C est
exactement la difference qu il fallait poser.

CE QU IL NE FAIT PAS
--------------------
Il ne les adopte pas. A froid, sans savoir a quel prix ni depuis quand,
une copie au marche serait une entree fausse -- c est la raison meme du
comportement d origine, et --reprendre existe deja pour qui veut le
contraire en connaissance de cause.

Il ne change rien a ce que le pont copie. Une seule chose change : le
trou a un nom, une taille et une date.

USAGE
-----
    python patch_pont_orphelins.py                 <- simulation
    python patch_pont_orphelins.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import time

CIBLE_DEFAUT = "pont_miroirs.py"
MARQUEUR = "[ORPHELINS-2708]"

# --- ancre 1 : le chemin du releve, a cote des autres ----------------
RE_LIENS = re.compile(r"^LIENS = os\.path\.join\(.*$", re.M)

DECL = '''
# Les positions vivantes qu un demarrage ne copiera jamais, relevees a
# chaque demarrage de l envoyeur.  [ORPHELINS-2708]
ORPHELINS = os.path.join(RACINE, "docs", "pont_miroirs", "orphelins.json")
SESSIONS_GARDEES = 40   # au-dela, on oublie les plus vieux demarrages'''

# --- ancre 2 : la fonction, juste avant l envoyeur -------------------
RE_ENVOYEUR = re.compile(r"^def envoyeur\(args\):", re.M)

FONCTION = '''def noter_orphelins(precedent, liens):
    """Releve les positions vivantes que ce demarrage ne copiera pas.

    Une position deja ouverte et SANS lien ne sera jamais reproduite :
    le pont ne copie que les apparitions, et celle-la est apparue avant
    lui. Son resultat manquera donc au panneau, et rien ne distinguera
    "la branche n a pas trade" de "ses trades n ont pas ete copies".

    Une position ouverte AVEC un lien n est pas orpheline : elle vit
    deja sur le compte dedie et son lien continue de la suivre a travers
    le redemarrage.

    Rendre le releve, et l ecrire. Une ecriture qui echoue ne doit pas
    empecher le pont de partir : le releve est une trace, pas un organe.
    [ORPHELINS-2708]
    """
    absents = {}
    for tk, p in (precedent or {}).items():
        if tk in (liens or {}):
            continue
        absents[str(tk)] = {"magic": p.get("magic"),
                            "sym": p.get("sym"),
                            "sens": p.get("sens"),
                            "volume": p.get("volume")}
    if not absents:
        dire("envoyeur", "aucune orpheline : tout ce qui est ouvert a"
                         " deja son lien.")
        return {}

    dire("envoyeur", "%d POSITION(S) ORPHELINE(S)" % len(absents))
    dire("envoyeur", "  ouvertes avant ce demarrage et sans lien : elles ne")
    dire("envoyeur", "  seront jamais copiees, et leur resultat manquera au")
    dire("envoyeur", "  panneau. Ce n est pas une panne, c est le trou que")
    dire("envoyeur", "  tout redemarrage en seance creuse -- il est nomme ici")
    dire("envoyeur", "  pour qu on ne le prenne pas pour une absence de trade.")
    par = {}
    for d in absents.values():
        m = d.get("magic")
        par[m] = par.get(m, 0) + 1
    for m in sorted(par, key=lambda x: str(x)):
        dire("envoyeur", "    M%s : %d position(s)" % (m, par[m]))

    try:
        vieux = lire_json(ORPHELINS, essais=1) or {}
        sessions = vieux.get("sessions") or []
    except Exception:
        sessions = []
    sessions.append({"ts": time.time(),
                     "quand": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     "n": len(absents),
                     "positions": absents})
    if len(sessions) > SESSIONS_GARDEES:
        sessions = sessions[-SESSIONS_GARDEES:]
    try:
        ecrire_atomique(ORPHELINS, {"sessions": sessions})
        dire("envoyeur", "  releve depose : %s"
             % os.path.basename(ORPHELINS))
    except Exception as e:
        dire("envoyeur", "  releve NON depose : %s" % str(e)[:120])
    return absents


def envoyeur(args):'''

# --- ancre 3 : l appel, avant la mise en ecoute ----------------------
RE_ECOUTE = re.compile(
    r"(?P<i>[ \t]*)dire\(\"envoyeur\", \"en ecoute\.\"\)")

APPEL = '''{i}# Ce que ce demarrage ne copiera pas, dit avant d ecouter.
{i}# [ORPHELINS-2708]
{i}if not args.reprendre:
{i}    try:
{i}        noter_orphelins(precedent, liens)
{i}    except Exception as _e:
{i}        dire("envoyeur", "releve des orphelines en erreur : %s"
{i}             % str(_e)[:120])
{i}dire("envoyeur", "en ecoute.")'''


# Le nombre de marqueurs attendus se DEDUIT des blocs poses. L ecrire a
# la main, c est le voir deriver au premier ajout de commentaire -- ce
# qui vient d arriver, et la verification a eu raison de tout annuler.
ATTENDU = (DECL + FONCTION + APPEL).count(MARQUEUR)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.cible):
        print("ABANDON : %s introuvable." % a.cible)
        return 2
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    if MARQUEUR in src:
        print("DEJA POSE : %s est present dans %s." % (MARQUEUR, a.cible))
        return 0

    crlf = "\r\n" in src
    def n(s):
        return s.replace("\n", "\r\n") if crlf else s

    for nom, rx in (("1 (LIENS)", RE_LIENS),
                    ("2 (def envoyeur)", RE_ENVOYEUR),
                    ("3 (en ecoute)", RE_ECOUTE)):
        c = len(rx.findall(src))
        if c != 1:
            print("REFUS : ancre %s attendue 1 fois, trouvee %d." % (nom, c))
            return 3

    neuf = src
    # de la fin vers le debut : les positions restent valides
    m = RE_ECOUTE.search(neuf)
    neuf = neuf[:m.start()] + n(APPEL.format(i=m.group("i"))) + neuf[m.end():]
    m = RE_ENVOYEUR.search(neuf)
    neuf = neuf[:m.start()] + n(FONCTION) + neuf[m.end():]
    m = RE_LIENS.search(neuf)
    neuf = neuf[:m.end()] + n(DECL) + neuf[m.end():]

    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("3 ancres posees, resultat compile.")
    print("  %d -> %d octets  (+%d)" % (len(src), len(neuf),
                                        len(neuf) - len(src)))
    print("  fins de ligne : %s" % ("CRLF" if crlf else "LF"))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_orph_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        relu = f.read()
    nb = relu.count(MARQUEUR)
    ok = nb == ATTENDU
    print("")
    print("sauvegarde   : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s (%d marqueurs, %d attendus)"
          % ("ok" if ok else "ECHEC", nb, ATTENDU))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("Seul l ENVOYEUR porte cette fonction, et elle ne s execute qu au")
    print("demarrage : le releve apparaitra au prochain lancement du pont.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
