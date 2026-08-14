# -*- coding: utf-8 -*-
"""
patch_council_plafond.py -- 8000 jetons ne suffisent pas a un modele
                            qui reflechit avant de repondre

  python patch_council_plafond.py --essai
  python patch_council_plafond.py --jetons 30000

CE QUI S EST PASSE LE 14/08 A 12:30

    Question en sept volets posee au REPL. Reponse :

        (vide / completion=8000/8000 PLAFOND ATTEINT | prompt=153495)

    146 secondes de calcul, zero caractere ecrit.

    Sur un modele de raisonnement, `max_tokens` couvre le RAISONNEMENT
    ET la reponse dans la meme enveloppe. Les 8000 sont partis
    integralement dans la reflexion ; il ne restait rien pour ecrire.
    Ce n est pas une troncature de la reponse -- c est une reponse qui
    n a jamais commence.

    Le meme piege, a une autre echelle, que le test a max_tokens=5 du
    matin : un contenu vide garanti par le parametre, pas par le
    modele.

POURQUOI CHANGER LE DEFAUT PLUTOT QUE POSER LA VARIABLE

    council_shadow lit deja COUNCIL_SHADOW_MAX_TOKENS ; le 8000 n est
    que son defaut. Poser la variable dans un shell ne servirait a rien
    : depuis le 14/08, c est Gardien-Stack qui relance price_action --
    le processus qui sert le REPL -- et il ne pose que PA_ROLE. Au
    prochain redemarrage, le defaut reprendrait la main.

    On change donc le DEFAUT. La variable d environnement continue de
    le surcharger pour qui veut essayer autre chose sans toucher au
    fichier.

CE QUE LE PATCH NE CHANGE PAS

    Le `max_tokens=1500` code en dur a la ligne 771 appartient a un
    AUTRE appel -- une sortie courte, pas le REPL. Le toucher sans
    savoir ce qu il alimente changerait un comportement qu on n a pas
    mesure. Il reste tel quel, et c est delibere.

CE QU IL FAUT SAVOIR AVANT DE MONTER TRES HAUT

    1. Le raisonnement est FACTURE comme le reste. Une question
       complexe a 30000 jetons peut couter dix fois une question
       simple.
    2. Le prompt faisait 153 495 jetons. Prompt + completion doivent
       tenir dans la fenetre du modele : si la somme depasse, l API
       refuse l appel au lieu de tronquer. Si une erreur apparait apres
       ce patch, c est la premiere piste -- et la vraie reponse est
       alors de reduire le PROMPT, pas le plafond.
    3. _DOCS_REPL charge les documents jusqu a un plafond total, avec
       un `break` : tout ce qui vient apres n est pas charge DU TOUT.
       Plus on ajoute de panneaux, plus le risque qu un document
       important tombe hors contexte augmente -- silencieusement.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse, puis controle que la nouvelle valeur est bien celle
demandee et que le nom de la variable d environnement n a pas bouge --
sans quoi la surcharge cesserait de fonctionner sans prevenir.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "council_shadow.py"
VAR = "COUNCIL_SHADOW_MAX_TOKENS"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--jetons", type=int, default=30000)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if a.jetons < 8000:
        print("KO : %d jetons, c est moins que le defaut actuel." % a.jetons)
        return 1

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    # L ancre est ecrite en morceaux pour ne pas dependre de l espacement
    # exact autour du signe egal.
    motif = re.compile(
        r'COUNCIL_MAX_TOKENS\s*=\s*int\(os\.environ\.get\(\s*"'
        + VAR + r'"\s*,\s*"(\d+)"\s*\)\)')
    trouves = motif.findall(src)
    if len(trouves) != 1:
        print("KO : %d occurrence(s) de COUNCIL_MAX_TOKENS, il en faut 1."
              % len(trouves))
        print("Rien n a ete ecrit.")
        return 1
    actuel = int(trouves[0])
    print("plafond actuel : %d jetons" % actuel)
    if actuel == a.jetons:
        print("Deja a la valeur demandee -- rien a faire.")
        return 0

    neuf = motif.sub(
        'COUNCIL_MAX_TOKENS = int(os.environ.get("%s", "%d"))'
        % (VAR, a.jetons), src, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Le nom de la variable d environnement doit survivre : c est lui qui
    # permet de surcharger sans repatcher. S il disparaissait, on
    # perdrait le reglage sans que rien ne le dise.
    if neuf.count(VAR) != src.count(VAR):
        print("KO : %s n apparait plus le meme nombre de fois." % VAR)
        print("Rien n a ete ecrit.")
        return 1
    if len(motif.findall(neuf)) != 1 or int(motif.findall(neuf)[0]) != a.jetons:
        print("KO : la nouvelle valeur ne se relit pas.")
        print("Rien n a ete ecrit.")
        return 1

    # Le 1500 code en dur ailleurs ne doit pas bouger.
    if src.count("max_tokens=1500") != neuf.count("max_tokens=1500"):
        print("KO : l appel a 1500 jetons a ete touche.")
        print("Rien n a ete ecrit.")
        return 1

    print("nouveau plafond : %d jetons  (%s surcharge toujours)"
          % (a.jetons, VAR))
    print("l appel a max_tokens=1500 de la l.771 est intact.")
    print()
    print("Sur un modele de raisonnement, ce plafond couvre le")
    print("RAISONNEMENT ET la reponse. Le 14/08, les 8000 sont partis")
    print("entierement dans la reflexion : 146 s de calcul, zero")
    print("caractere ecrit.")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py.")
    print("Le gardien le relancera avec PA_ROLE=panel et lira ce")
    print("nouveau defaut -- il n a pas besoin de connaitre la")
    print("variable d environnement.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
