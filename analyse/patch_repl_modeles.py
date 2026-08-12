# -*- coding: utf-8 -*-
"""
patch_repl_modeles.py -- le reasoner seul, avec de la place, et un
                         (vide) qui dit pourquoi

  python patch_repl_modeles.py --essai
  python patch_repl_modeles.py

CE QU ON A ETABLI

    repl_web.ask() lance deux modeles en parallele :

        txt, usage, el, to, err = cs._call_model(mk, messages, 3000)
        out[mk] = {"text": (txt or "").strip() or f"(vide...)"}
        ths = [... for m in ("deepseek", "deepseek_reasoner")]

    Le "(vide)" observe sur le reasoner arrive SANS message d erreur
    derriere -- donc l appel a reussi et le modele a rendu un texte vide.
    Ni timeout (120 s, il repond en 20-30 s), ni exception.

    council_shadow porte deja le meme piege, documente, sur un autre
    modele :

        # 2.5-flash est un modele thinking : sans ca il brule le budget
        # en reflexion et rend vide.

    Meme cause ici : 3000 jetons de sortie pour un modele qui raisonne
    sur 40 000 jetons de documents. Et _call_model ne lit que
    message.content -- correct pour DeepSeek, dont la reponse finale est
    bien la, mais un modele coupe pendant sa reflexion rend content vide
    sans lever.

CE QUE FAIT CE PATCH

    1. UN PLAFOND PAR MODELE.
           REPL_MAX_TOKENS = {"deepseek": 3000, "deepseek_reasoner": 8000}
       8000 est la valeur de COUNCIL_MAX_TOKENS du module -- on revient
       simplement au defaut pour celui qui en a besoin. Le chat garde
       3000, il n en a jamais utilise le quart.

    2. LE CHOIX DES MODELES EN UNE CONSTANTE.
           REPL_MODELES = ("deepseek", "deepseek_reasoner")
       Mettre ("deepseek_reasoner",) interroge le reasoner seul et divise
       par deux la facture en jetons. Le modele non interroge affiche
       "(non interroge)" et non "(pas de reponse)" -- on ne fait pas dire
       a un silence volontaire qu il est un echec.

    3. UN (VIDE) QUI PARLE.
       Quand le texte revient vide, on ecrit ce qu on sait : l erreur,
       le timeout, et surtout completion=N/PLAFOND avec la mention
       PLAFOND ATTEINT quand c est le cas. Un silence muet a coute une
       heure aujourd hui ; c est la troisieme fois de la journee qu on
       corrige la meme faute -- du code qui jette une information sans
       le dire.

CE QUE CA NE TOUCHE PAS

    Rien hors de repl_web.ask(). _call_model, le closer, les traders et
    council_shadow restent inchanges. Le plafond de 1500 du closer n a
    jamais ete en cause -- j avais d abord accuse cette ligne, a tort.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
PREND EFFET AU PROCHAIN DEMARRAGE DU 8095.
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
MARQUEUR = "REPL_MAX_TOKENS"

RE_DEF = re.compile(r'^def ask\(question\):[ \t]*$', re.M)

RE_APPEL = re.compile(
    r'^([ \t]*)txt, usage, el, to, err = cs\._call_model\('
    r'mk, messages, 3000\)[ \t]*$', re.M)

RE_THS = re.compile(
    r'^([ \t]*)ths = \[threading\.Thread\(target=_run, args=\(m,\)\) for m in '
    r'\("deepseek", "deepseek_reasoner"\)\][ \t]*$', re.M)

# Deux ancres separees, pas un bloc : la v1 exigeait que les deux lignes
# soient adjacentes. Elles le sont, mais la v2 -- qui ne l exigeait plus
# -- a quand meme echoue sur g1. Le fichier differe donc de ce que la
# console affiche par un detail invisible : espace insecable, espace de
# fin, quelque chose.
#
# On cesse de deviner. L ancre ne retient que le DEBUT de la ligne, qui
# est identifiant a lui seul, et la ligne entiere est remplacee. C est
# le principe general : une ancre doit tenir au strict necessaire.
RE_G = re.compile(r'^([ \t]*)g = out\.get\("deepseek"\).*$', re.M)

RE_G1 = re.compile(r'^([ \t]*)g1 = out\.get\("deepseek_reasoner"\).*$', re.M)

TETE = '''# 12/08/2026 -- CE QUE LE REPL INTERROGE, ET AVEC QUEL BUDGET
#
# Mettre ("deepseek_reasoner",) interroge le reasoner seul : deux fois
# moins de jetons, et tout le budget pour celui qui raisonne.
REPL_MODELES = ("deepseek", "deepseek_reasoner")

# 3000 suffisent dix fois au chat. Le reasoner, lui, consomme son budget
# en reflexion avant d ecrire : a 3000 il rendait un texte VIDE, sans
# erreur. council_shadow documente deja le meme piege sur Gemini
# 2.5-flash -- "brule le budget en reflexion et rend vide". 8000 est la
# valeur de COUNCIL_MAX_TOKENS ; on revient simplement au defaut.
REPL_MAX_TOKENS = {"deepseek": 3000, "deepseek_reasoner": 8000}


def _repl_txt(txt, usage, err, timeout, plafond):
    """Le texte, ou un (vide) qui DIT pourquoi il est vide.

    Un silence muet a coute une heure le 12/08 : l appel reussissait, le
    modele rendait une chaine vide, et rien nulle part ne disait qu il
    avait ete coupe."""
    t = (txt or "").strip()
    if t:
        return t
    d = []
    if err:
        d.append(str(err))
    if timeout:
        d.append("timeout")
    c = (usage or {}).get("completion_tokens")
    if c is not None:
        d.append("completion=%s/%s%s"
                 % (c, plafond, " PLAFOND ATTEINT" if c >= plafond else ""))
    p = (usage or {}).get("prompt_tokens")
    if p is not None:
        d.append("prompt=%s" % p)
    return ("(vide / %s)" % " | ".join(d)) if d else "(vide / aucune info)"


'''

NEUF_APPEL = '''    _mt = REPL_MAX_TOKENS.get(mk, 3000)
    txt, usage, el, to, err = cs._call_model(mk, messages, _mt)
    txt = _repl_txt(txt, usage, err, to, _mt)'''

NEUF_G = '''    # (non interroge) et non (pas de reponse) : on ne fait pas dire a un
    # silence volontaire qu il est un echec. Voir REPL_MODELES.
    _absent = {"text": "(non interroge -- voir REPL_MODELES)", "elapsed": 0}
    g = out.get("deepseek") or _absent'''

NEUF_G1 = '''    g1 = out.get("deepseek_reasoner") or _absent'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def cale(bloc, ind):
    return "\n".join(ind + l[4:] if l.startswith("    ") else (ind + l if l else "")
                     for l in bloc.split("\n"))


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

    for nom, rx in (("def ask(question):", RE_DEF),
                    ("l appel a _call_model(mk, messages, 3000)", RE_APPEL),
                    ("la liste des threads", RE_THS),
                    ("le repli g (pas de reponse)", RE_G),
                    ("le repli g1 (pas de reponse)", RE_G1)):
        vus = rx.findall(src)
        if len(vus) != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (len(vus), nom))
            print("Rien n a ete ecrit.")
            return 1
        # On montre ce qu on a reconnu : une ancre qui matche la mauvaise
        # ligne est pire qu une ancre qui ne matche rien.
        m = rx.search(src)
        print("  ancre OK : %s" % m.group(0).strip()[:88])

    neuf = RE_DEF.sub(lambda m: TETE + m.group(0), src, count=1)
    neuf = RE_APPEL.sub(lambda m: cale(NEUF_APPEL, m.group(1)), neuf, count=1)
    neuf = RE_THS.sub(
        lambda m: m.group(1) + "ths = [threading.Thread(target=_run, "
                               "args=(m,)) for m in REPL_MODELES]",
        neuf, count=1)
    neuf = RE_G.sub(lambda m: cale(NEUF_G, m.group(1)), neuf, count=1)
    neuf = RE_G1.sub(lambda m: cale(NEUF_G1, m.group(1)), neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print("les cinq ancres sont uniques.")
    print()
    print("Apres patch :")
    print("  REPL_MODELES    = (\"deepseek\", \"deepseek_reasoner\")")
    print("  REPL_MAX_TOKENS = deepseek 3000, deepseek_reasoner 8000")
    print()
    print("Pour n interroger que le reasoner, edite REPL_MODELES :")
    print("      REPL_MODELES = (\"deepseek_reasoner\",)")
    print("  puis redemarre le 8095. Deux fois moins de jetons.")
    print()
    print("Et un texte vide affichera desormais completion=N/PLAFOND,")
    print("donc on saura tout de suite s il a ete coupe.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Redemarre le 8095.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
