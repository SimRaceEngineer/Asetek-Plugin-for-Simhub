# -*- coding: utf-8 -*-
r"""
patch_repl_sortie.py -- le REPL cesse de dependre de qui l a lance

  python patch_repl_sortie.py --essai
  python patch_repl_sortie.py

L ERREUR, TOUS LES JOURS

    DEEPSEEK reasoner  7.8s  (vide / ValueError: I/O operation on closed file.)

    Ce n est pas DeepSeek. C est un `print` du processus 8095 qui ecrit
    sur une sortie standard morte, dans `council_shadow._call_model`,
    en aval de `cs._call_model(mk, messages, _mt)`. L appel API a bien
    eu lieu -- les 7,8 secondes sont reelles -- et il est tue au moment
    d ecrire. `_repl_txt` recoit l exception dans `err` et l affiche :
    le correctif du 12/08 fait son travail, il montre la cause.

LA CAUSE EST DANS LE LANCEUR, ET ELLE EST MESURABLE

    Trois lanceurs coexistent et ne lancent pas le 8095 pareil :

        Superviseur.ps1:203    -RedirectStandardOutput + -RedirectStandardError
        Gardien-Stack.ps1:258   AUCUNE redirection
        Redemarrer-Stack.ps1:164 AUCUNE redirection

    Sans redirection, le processus herite de la console de son parent.
    Le gardien est une tache planifiee `/SC MINUTE /MO 5` lancee
    `-WindowStyle Hidden` : un PowerShell cache nait, relance ce qui
    manque, puis MEURT. Sa console meurt avec lui, et le 8095 qu il
    vient de lancer garde un descripteur qui ne mene plus nulle part.

    Selon lequel des trois a relance le 8095 ce jour-la, le MEME code
    fonctionne ou non. Le gardien passe toutes les cinq minutes : c est
    presque toujours lui qui gagne apres un incident. D ou "tous les
    jours".

CE QUE FAIT CE CORRECTIF, ET CE QU IL NE FAIT PAS

    Il ne repare pas un `print`. Il y en a des centaines dans la stack
    et le 12/08 j en ai corrige un seul, dans `_ensure_init` -- la faute
    est ressortie ailleurs six jours plus tard, ce qui est la preuve que
    corriger les points d impact un par un ne termine jamais.

    Il pose, AU CHARGEMENT DE repl_web, une seule question :

        est-ce que sys.stdout accepte encore une ecriture ?

    Si oui, il ne touche a RIEN. Si non -- et seulement dans ce cas --
    il remplace sys.stdout et sys.stderr par un flux qui ne peut pas
    lever, adosse a un fichier journal. Un `print` d un module
    quelconque du processus cesse alors d etre une bombe.

    Portee : le processus, donc `council_shadow` compris, sans le
    modifier. Aucun `print` n est supprime : ils sont detournes vers
    `docs\repl_sortie.log` au lieu d etre perdus. On y gagne meme la
    visibilite qu on n avait pas.

CE QU IL NE REMPLACE PAS

    La redirection manquante dans Gardien-Stack.ps1 et
    Redemarrer-Stack.ps1 reste a poser : le 8095 n est pas le seul
    processus relance par le gardien, et les traders lances par lui ont
    exactement la meme sortie morte. C est une deuxieme etape, separee,
    parce qu elle touche le lancement des traders et que ca ne se fait
    pas dans la meme minute qu un correctif de REPL.

    Ce correctif-ci rend le REPL independant de la question. C est ce
    qui etait demande : il doit fonctionner tous les jours, quel que
    soit qui l a lance.

IL AFFICHE AUSSI REPL_MODELES

    Le "(non interroge -- voir REPL_MODELES)" du modele chat n est pas
    une panne : cette chaine n existe que si "deepseek" est absent de
    REPL_MODELES. Le patch lit la ligne dans le fichier et l affiche,
    pour que ce soit constate et non deduit.

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
MARQUEUR = "_sortie_sure"

# Ancre 1 : la constante posee par patch_repl_modeles le 12/08. Sa
# presence prouve que ce patch-la est applique -- ce que les messages
# observes dans le navigateur prouvaient deja. On insere AVANT elle,
# donc au niveau module : le garde s execute a l import de repl_web,
# bien avant la premiere question.
RE_TOKENS = re.compile(r'^REPL_MAX_TOKENS = \{', re.M)

# Ancre 2 : la definition de ask(). Deja utilisee le 12/08 et unique a
# l epoque. Le garde y est rappele -- il est memoise, donc gratuit --
# pour le cas ou la sortie mourrait APRES le chargement du module, ce
# qui est precisement ce qui arrive quand la console du gardien
# disparait quelques secondes apres le lancement.
RE_DEF = re.compile(r'^def ask\(question\):[ \t]*$', re.M)

RE_MODELES = re.compile(r'^REPL_MODELES = .*$', re.M)

TETE = '''# 17/08/2026 -- LE REPL NE DEPEND PLUS DE QUI L A LANCE
#
# `Gardien-Stack.ps1` lance le 8095 sans -RedirectStandardOutput, depuis
# une tache planifiee `-WindowStyle Hidden` qui meurt au bout de sa
# passe. La console du parent disparait, et la sortie standard du 8095
# devient un descripteur ferme : tout `print` du processus leve alors
#
#     ValueError: I/O operation on closed file.
#
# y compris ceux de `council_shadow._call_model`, qui tuaient la reponse
# du reasoner APRES un appel API reussi de 7,8 secondes.
#
# Le 12/08 j ai corrige UN print, dans `_ensure_init`. La faute est
# ressortie ailleurs six jours plus tard : corriger les points d impact
# un par un ne termine jamais. On corrige donc le flux, une fois, pour
# tout le processus.
#
# Ne s active QUE si la sortie est deja morte. Si elle est vivante,
# rien n est touche et rien n est detourne.
#
# CE BLOC N EMPRUNTE RIEN AU FICHIER HOTE. Il refait ses imports sous
# des noms prives. Une premiere version se servait des `io`, `os` et
# `datetime` supposes presents en tete de repl_web : au banc, l en-tete
# du journal n a pas ete ecrit -- NameError sur `datetime`, avale par
# le `except` de securite qui protege l ecriture. Un correctif qui
# depend des imports de sa cible echoue en silence sur une cible qu on
# ne peut pas lire.
import io as _io
import os as _os
import sys as _sys
from datetime import datetime as _dtn


class _SortieSure(object):
    """Un flux qui ne peut pas lever, adosse a un fichier si possible.

    Il ne supprime aucun `print` : il les detourne. Un diagnostic qui
    tue ce qu il diagnostique est la faute du 12/08 ; celui-ci ne peut
    rien tuer, chaque methode avale tout."""

    def __init__(self, fh):
        self._fh = fh
        self.encoding = "utf-8"
        self.errors = "replace"

    @property
    def closed(self):
        return False

    def write(self, s):
        try:
            if self._fh is not None:
                self._fh.write(s)
        except Exception:
            self._fh = None
        return len(s) if s else 0

    def writelines(self, lignes):
        for l in lignes:
            self.write(l)

    def flush(self):
        try:
            if self._fh is not None:
                self._fh.flush()
        except Exception:
            self._fh = None

    def isatty(self):
        return False

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

    def fileno(self):
        # _io.UnsupportedOperation, pas ValueError : c est la reponse
        # normale d un flux sans descripteur, et les bibliotheques qui
        # interrogent fileno() la reconnaissent.
        raise _io.UnsupportedOperation("fileno")

    def close(self):
        self.flush()


_sortie_faite = [False]


def _sortie_sure():
    """Rend la sortie du processus inoffensive SI elle est deja morte.

    Le test n est pas une supposition : on ECRIT une chaine vide et on
    vide le tampon. Un descripteur ferme leve ValueError a cet instant
    precis -- exactement l exception vue dans le navigateur.

    Rend une chaine decrivant ce qui a ete fait, pour que ce soit
    constate et pas suppose."""
    if _sortie_faite[0]:
        return "deja fait"
    _sortie_faite[0] = True

    morts = []
    for nom in ("stdout", "stderr"):
        f = getattr(_sys, nom, None)
        if f is None:
            morts.append(nom)
            continue
        try:
            f.write("")
            f.flush()
        except Exception:
            morts.append(nom)
    if not morts:
        return "sortie vivante -- rien n a ete touche"

    fh, ou = None, "aucun fichier (ecriture jetee)"
    for chemin in (_os.path.join("docs", "repl_sortie.log"),
                   "repl_sortie.log"):
        try:
            d = _os.path.dirname(chemin)
            if d and not _os.path.isdir(d):
                continue
            fh = _io.open(chemin, "a", encoding="utf-8",
                         errors="replace", buffering=1)
            ou = _os.path.abspath(chemin)
            break
        except Exception:
            fh = None
    sur = _SortieSure(fh)
    if fh is not None:
        try:
            fh.write("\\n=== %s  pid %s  sortie morte : %s ===\\n"
                     % (_dtn.now().strftime("%Y-%m-%d %H:%M:%S"),
                        _os.getpid(), ", ".join(morts)))
        except Exception:
            pass
    for nom in morts:
        setattr(_sys, nom, sur)
    return "sortie morte (%s) -> %s" % (", ".join(morts), ou)


_SORTIE_ETAT = _sortie_sure()


'''

NEUF_DEF = '''def ask(question):
    # La sortie peut mourir APRES le chargement du module : la console
    # du gardien disparait quelques secondes seulement apres avoir
    # lance le 8095. Ce rappel est memoise, il ne coute rien.
    _sortie_sure()'''


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
    print("%s : %d lignes, encodage %s"
          % (a.fichier, src.count("\n") + 1, enc))
    print()

    # Ce que le fichier dit de lui-meme, avant toute modification.
    m = RE_MODELES.search(src)
    if m:
        print("  %s" % m.group(0).strip())
        if '"deepseek"' not in m.group(0):
            print("  -> le modele chat n est PAS interroge, et c est un")
            print("     reglage, pas une panne. Le \"(non interroge)\" du")
            print("     navigateur est ce reglage qui se declare.")
            print("     Pour reinterroger les deux, remettre :")
            print("       REPL_MODELES = (\"deepseek\", \"deepseek_reasoner\")")
        else:
            print("  -> les deux modeles sont interroges.")
    else:
        print("  REPL_MODELES introuvable dans le fichier.")
    print()

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    if "REPL_MAX_TOKENS" not in src:
        print("KO : patch_repl_modeles.py n a pas ete applique sur ce")
        print("     fichier. Or les messages vus dans le navigateur --")
        print("     \"(non interroge)\" et \"(vide / ...)\" -- viennent de")
        print("     lui. Ce n est donc pas le bon repl_web.py, et c est")
        print("     en soi la reponse a \"le lanceur n execute pas le bon")
        print("     code\". Rien n a ete ecrit.")
        return 1

    for nom, rx in (("REPL_MAX_TOKENS = {", RE_TOKENS),
                    ("def ask(question):", RE_DEF)):
        vus = rx.findall(src)
        if len(vus) != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1."
                  % (len(vus), nom))
            print("Rien n a ete ecrit.")
            return 1
        print("  ancre OK : %s" % rx.search(src).group(0).strip()[:88])

    neuf = RE_TOKENS.sub(lambda m: TETE + m.group(0), src, count=1)
    neuf = RE_DEF.sub(lambda m: NEUF_DEF, neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Apres patch, au chargement de repl_web :")
    print("  sortie vivante  -> rien n est touche, rien n est detourne")
    print("  sortie morte    -> sys.stdout et sys.stderr deviennent un")
    print("                     flux qui ne peut pas lever, ecrit dans")
    print("                     docs\\repl_sortie.log")
    print()
    print("Le print de council_shadow qui tuait la reponse du reasoner")
    print("cesse d etre une bombe, SANS que council_shadow soit modifie.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier,
                           datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    print()
    print("IL FAUT REDEMARRER LE 8095 pour que ca prenne effet. Le")
    print("gardien le relance seul dans les cinq minutes si on le")
    print("laisse s arreter -- mais il le relancera SANS redirection,")
    print("donc avec une sortie qui mourra : c est precisement ce que")
    print("ce correctif rend inoffensif.")
    print()
    print("VERIFICATION, dans le navigateur : poser une question au")
    print("REPL. Le reasoner doit repondre du texte. S il affiche encore")
    print("(vide / ...), le message dira quoi -- completion=N/8000")
    print("PLAFOND ATTEINT est une autre cause, et une autre reponse.")
    print()
    print("ETAPE 2, SEPAREE : Gardien-Stack.ps1:258 et")
    print("Redemarrer-Stack.ps1:164 lancent TOUS les services sans")
    print("redirection, traders compris. Ils ont la meme sortie morte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
