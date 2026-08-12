# -*- coding: utf-8 -*-
"""
patch_repl_frais.py -- le REPL relit ses documents quand ils changent

  python patch_repl_frais.py --essai
  python patch_repl_frais.py

LE PROBLEME

    _ensure_init() charge les documents UNE FOIS, au premier appel, puis
    pose _inited = True. Un export fait apres coup n est donc visible
    qu au redemarrage du processus 8095.

    Consequence concrete : on ne peut pas discuter avec le REPL de la
    seance en cours. Il repond sur l export du matin, avec assurance, et
    rien n indique que ses chiffres ont quatre heures.

CE QUE FAIT CE PATCH

    Avant chaque question, on calcule une signature des sources --
    (chemin, date de modification, taille) pour chaque fichier. Si elle
    a change depuis le dernier chargement, on remet _inited a False :
    _ensure_init() rechargera tout, une fois, a la question suivante.

    Cout : quelques appels os.stat par question, soit moins d une
    milliseconde. Rien de comparable aux 40 000 jetons qu on envoie deja.

POURQUOI UNE LISTE A PART, ET POURQUOI CE N EST PAS GRAVE

    La liste des sources vit DANS _ensure_init, en variable locale. On
    ne peut pas la lire de l exterieur sans reecrire la fonction, ce qui
    serait un patch autrement plus risque.

    Ce patch redeclare donc les memes trois sources au niveau du module,
    pour la seule surveillance. C est une duplication, et je l ecris
    plutot que de la cacher.

    Le mode de defaillance est benin : si les deux listes divergeaient un
    jour, on raterait un rechargement -- le REPL serait en retard, comme
    aujourd hui. Jamais l inverse. Une duplication qui ne peut produire
    que l ancien comportement est acceptable ; l inverse ne le serait
    pas.

CE QUE CA NE FAIT PAS

    Ca ne relance pas l export. Les fichiers ne se mettent a jour que si
    quelqu un ecrit dedans -- c est le role de panels_auto.py, qui tourne
    a cote et relance rails_join puis export_panels toutes les N minutes.

    Les deux sont necessaires : celui-ci rend la lecture fraiche, l autre
    rend les donnees fraiches.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
Le patch IMPRIME la ligne qu il a reconnue avant d ecrire.
PREND EFFET AU PROCHAIN DEMARRAGE DU 8095 -- une derniere fois.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "repl_web.py"
MARQUEUR = "_signature_docs"

RE_ANCRE = re.compile(
    r'^([ \t]*)return \{"ok": False, "error": "question vide"\}[ \t]*\n'
    r'([ \t]*)_ensure_init\(\)[ \t]*$', re.M)

TETE = '''# 12/08/2026 -- LE REPL RELIT SES DOCUMENTS QUAND ILS CHANGENT
#
# _ensure_init() ne chargeait qu une fois. Un export fait apres coup
# n etait visible qu au redemarrage du 8095, donc on ne pouvait pas
# discuter de la seance en cours : le REPL repondait sur l export du
# matin, avec assurance, sans que rien n indique l age des chiffres.
#
# Duplication assumee : la liste des sources vit en local dans
# _ensure_init et n est pas lisible d ici. On la redeclare pour la
# SEULE surveillance. Si les deux divergeaient, on raterait un
# rechargement -- jamais on ne lirait de fausses donnees.
import os as _os_frais

_DOCS_SURVEILLES = [
    _os_frais.path.join(_os_frais.path.dirname(_os_frais.path.abspath(__file__)),
                        "notes"),
    _os_frais.path.join(_os_frais.path.dirname(_os_frais.path.abspath(__file__)),
                        "docs", "JOURNAL.md"),
    _os_frais.path.join(_os_frais.path.dirname(_os_frais.path.abspath(__file__)),
                        "panels"),
]
_sig_docs = None


def _signature_docs():
    """(chemin, date, taille) de chaque source. Quelques os.stat."""
    out = []
    for _d in _DOCS_SURVEILLES:
        try:
            if _os_frais.path.isdir(_d):
                for _n in sorted(_os_frais.listdir(_d)):
                    if _n.lower().endswith((".md", ".txt")):
                        _p = _os_frais.path.join(_d, _n)
                        _s = _os_frais.stat(_p)
                        out.append((_n, int(_s.st_mtime), _s.st_size))
            elif _os_frais.path.isfile(_d):
                _s = _os_frais.stat(_d)
                out.append((_os_frais.path.basename(_d), int(_s.st_mtime),
                            _s.st_size))
        except Exception:
            continue          # une source illisible ne doit pas bloquer
    return tuple(out)


def _relire_si_change():
    """Remet _inited a False si une source a bouge. Ne leve jamais."""
    global _sig_docs, _inited
    try:
        s = _signature_docs()
    except Exception:
        return
    if _sig_docs is not None and s != _sig_docs:
        _inited = False
        try:
            print("[repl_web] documents modifies -> rechargement")
        except Exception:
            pass
    _sig_docs = s


'''


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

    trouve = RE_ANCRE.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1." % len(trouve))
        print("Attendu, dans ask() :")
        print('    return {"ok": False, "error": "question vide"}')
        print("    _ensure_init()")
        print("Rien n a ete ecrit.")
        return 1

    m = RE_ANCRE.search(src)
    print("  ancre OK : %s" % m.group(0).strip().replace("\n", " / ")[:88])

    ind = trouve[0][1]
    neuf = RE_ANCRE.sub(
        lambda mm: (mm.group(0).split("\n")[0] + "\n"
                    + ind + "_relire_si_change()\n"
                    + ind + "_ensure_init()"),
        src, count=1)

    # La tete va juste avant def ask(question):
    rd = re.compile(r'^def ask\(question\):[ \t]*$', re.M)
    if len(rd.findall(neuf)) != 1:
        print("KO : def ask(question): introuvable ou multiple.")
        print("Rien n a ete ecrit.")
        return 1
    neuf = rd.sub(lambda mm: TETE + mm.group(0), neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Apres patch, a chaque question :")
    print("  signature des sources -> si elle a change, _inited = False")
    print("  -> _ensure_init() recharge tout, une fois")
    print()
    print("Sources surveillees : notes\\, docs\\JOURNAL.md, panels\\")
    print("Cout : quelques os.stat par question.")
    print()
    print("Il faut AUSSI que quelqu un rafraichisse les fichiers :")
    print("    python panels_auto.py")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Redemarre le 8095 -- une derniere fois.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
