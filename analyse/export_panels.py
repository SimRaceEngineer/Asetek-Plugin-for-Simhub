# -*- coding: utf-8 -*-
"""
export_panels.py -- ecrire les panneaux en texte, la ou le REPL les lit

  python export_panels.py
  python export_panels.py --dest "G:\\My Drive\\ScalpEA\\panels"

POURQUOI
    Le REPL web ne lit aucun fichier aujourd hui. patch_repl_docs lui
    apprend a charger tout ce qui traine dans un dossier de panneaux --
    mais encore faut-il que quelqu un l y ecrive. C est ce script.

    Deposer un fichier dans ce dossier suffit desormais a le rendre
    lisible par DeepSeek. Pas de patch a rejouer.

CE QU IL EXPORTE
    rails trades   panneau 8095, rendu HTML -> texte
    orderflow      idem
    rails post 05/08  sortie console de rails_range.py
    rails 3 periodes  sortie console de rails_trois.py

    Les deux premiers sont des panneaux HTML : on les aplatit en texte,
    les lignes de tableau devenant des lignes, les cellules separees par
    des barres. Un modele lit ca sans peine ; il lirait mal du HTML brut,
    et surtout il paierait les balises au jeton.

CE QU IL NE FAIT PAS
    Il ne devine pas l API d un panneau. Pour chaque module il essaie une
    liste de noms de fonction connus et, s il n en trouve aucun, il le DIT
    au lieu d ecrire un fichier vide. Un panneau manquant se voit ; un
    panneau vide passerait inapercu et DeepSeek repondrait a cote sans
    que personne ne comprenne pourquoi.

    Il ne fait aucun appel MT5 de son propre chef. Les panneaux le font
    peut-etre au moment du rendu -- c est leur affaire, et c est la meme
    chose que quand tu ouvres la page.

A RELANCER quand tu veux rafraichir ce que voit le REPL. Le REPL, lui,
relit ces fichiers au demarrage du processus 8095, pas a chaque question.
"""
import argparse
import html as _html
import io
import os
import re
import subprocess
import sys
from datetime import datetime

DEST = r"G:\My Drive\ScalpEA\panels"
TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
NOMS = ("render_panel", "render", "build_panel", "panel_html", "main_html")

# (fichier de sortie, genre, cible)
TRAVAUX = [
    ("panel_rails_trades.txt", "module", "rails_trades_panel"),
    ("panel_orderflow.txt", "module", "orderflow_panel"),
    ("panel_rails_post0508.txt", "script",
     ["rails_range.py", "--fichier", TICKETS]),
    ("panel_rails_trois.txt", "script",
     ["rails_trois.py", "--fichier", TICKETS]),
]

RE_BLOC = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
RE_BALISE = re.compile(r"<[^>]+>")
RE_VIDE = re.compile(r"\n{3,}")


def aplatir(h):
    """HTML -> texte lisible. Les lignes de tableau restent des lignes."""
    t = RE_BLOC.sub(" ", h)
    t = re.sub(r"</t[dh]>", " | ", t, flags=re.I)
    t = re.sub(r"</(tr|h1|h2|h3|div|p|li)>", "\n", t, flags=re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = RE_BALISE.sub("", t)
    t = _html.unescape(t)
    t = "\n".join(l.rstrip(" |").strip() for l in t.split("\n"))
    return RE_VIDE.sub("\n\n", t).strip()


def par_module(nom):
    """(texte, explication). texte vide = echec, explication dit pourquoi.

    Le repertoire COURANT passe devant : ce script peut vivre dans
    analyse\\ alors que les panneaux sont a la racine de la stack. Python
    n ajoute que le dossier du script, pas le repertoire de travail."""
    _cwd = os.getcwd()
    if _cwd not in sys.path:
        sys.path.insert(0, _cwd)
    try:
        mod = __import__(nom)
    except Exception as e:
        return "", "import impossible : %s: %s" % (type(e).__name__, e)
    fn = None
    for n in NOMS:
        f = getattr(mod, n, None)
        if callable(f):
            fn = (n, f)
            break
    if fn is None:
        dispo = [n for n in dir(mod)
                 if callable(getattr(mod, n, None)) and not n.startswith("_")]
        return "", ("aucune fonction de rendu parmi %s. Disponibles : %s"
                    % (", ".join(NOMS), ", ".join(dispo[:12]) or "(aucune)"))
    try:
        brut = fn[1]()
    except Exception as e:
        return "", "%s() a leve %s: %s" % (fn[0], type(e).__name__, e)
    if not isinstance(brut, str):
        return "", "%s() ne rend pas du texte (%s)" % (fn[0], type(brut).__name__)
    return aplatir(brut), "via %s()" % fn[0]


def par_script(argv):
    if not os.path.isfile(argv[0]):
        return "", "%s introuvable" % argv[0]
    try:
        r = subprocess.run([sys.executable] + argv, capture_output=True,
                           text=True, timeout=300)
    except Exception as e:
        return "", "%s: %s" % (type(e).__name__, e)
    if r.returncode != 0:
        court = (r.stderr or r.stdout or "").strip().split("\n")[-1][:120]
        return "", "code %d : %s" % (r.returncode, court)
    return r.stdout.strip(), "via %s" % argv[0]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dest", default=DEST)
    p.add_argument("--seulement", nargs="*",
                   help="n exporter que ces fichiers de sortie")
    a = p.parse_args()

    try:
        os.makedirs(a.dest, exist_ok=True)
    except Exception as e:
        print("KO : impossible de creer %s : %s" % (a.dest, e))
        return 1

    print("=== SCALP-EA / EXPORT DES PANNEAUX ===")
    print("destination : %s" % a.dest)
    print()
    print("%-28s %9s  %s" % ("fichier", "octets", "resultat"))
    print("-" * 92)

    ok = rate = 0
    for sortie, genre, cible in TRAVAUX:
        if a.seulement and sortie not in a.seulement:
            continue
        texte, note = (par_module(cible) if genre == "module"
                       else par_script(cible))
        if not texte:
            print("%-28s %9s  ECHEC : %s" % (sortie, "-", note))
            rate += 1
            continue
        entete = ("# %s\n# exporte le %s\n# %s\n\n"
                  % (sortie, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), note))
        chemin = os.path.join(a.dest, sortie)
        try:
            io.open(chemin, "w", encoding="utf-8").write(entete + texte + "\n")
        except Exception as e:
            print("%-28s %9s  ECRITURE KO : %s" % (sortie, "-", e))
            rate += 1
            continue
        print("%-28s %9d  %s" % (sortie, len(texte), note))
        ok += 1

    print("-" * 92)
    print("%d exportes, %d en echec." % (ok, rate))
    if rate:
        print()
        print("Un echec n est pas anodin : le REPL lira ce dossier tel quel.")
        print("Un panneau absent, il n en parlera pas -- et personne ne saura")
        print("qu il lui manquait, sauf en relisant cette sortie.")
    print()
    print("Le REPL relit ce dossier au DEMARRAGE du processus 8095.")
    print("Un export fait apres coup n est visible qu au redemarrage suivant.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
