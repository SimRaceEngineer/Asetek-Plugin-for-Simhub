# -*- coding: utf-8 -*-
"""
patch_horloge_quorum.py -- le quorum de l horloge devient asymetrique

  python patch_horloge_quorum.py --essai
  python patch_horloge_quorum.py

CE QUE LA MESURE DU 12/08 A MONTRE, DANS L ORDRE

    Premiere regle : « tous les actifs CONNUS sont CHURN -> CARNAGE ».
    Defaut : un actif seul faisait l unanimite. On lisait PROPICE -- un
    feu VERT -- sur le seul US100, les deux autres muets.

    Correctif de midi : il faut 2 actifs connus pour nommer un regime.
    Defaut du correctif, visible des la premiere execution : la case
    INCONNU pese 176 minutes, 34 tickets et -538 EUR, soit -15,84 par
    ticket -- le meme tarif que CHURN. En detail, ces periodes sont
    presque toutes « US30 en CHURN, les deux autres muets » : 09h06,
    13h04, 14h09, 17h20, 18h25, 19h03.

    L information rouge etait donc la, et le quorum l a jetee.

L ERREUR, NOMMEE

    J ai traite les deux sens comme symetriques. Ils ne le sont pas.

        un faux ROUGE coute un trade manque
        un faux VERT coute un trade dans le hachoir

    Le meme seuil des deux cotes fait payer au rouge le prix qu on ne
    voulait payer qu au vert.

LA REGLE APRES CE PATCH

        aucun actif connu              -> INCONNU
        les 3 connus et tous CHURN     -> CARNAGE
        au moins 2/3 des connus CHURN  -> CHURN   (1 seul connu suffit)
        les 3 connus et tous PROPRE    -> PROPICE
        sinon                          -> DOUTEUX

    CARNAGE et PROPICE exigent desormais les TROIS actifs : ce sont les
    deux etats qui affirment quelque chose de fort. CHURN se contente de
    ce qu on sait, y compris d un seul actif. DOUTEUX absorbe le reste,
    dont « un seul actif connu, et il va bien » -- qui n est pas un feu
    vert.

CE QU IL FAUT REGARDER APRES

    La case INCONNU doit fondre. Si elle garde 30 tickets a -15 EUR,
    c est que le probleme n etait pas le quorum et il faudra chercher
    ailleurs. Et PROPICE restera probablement vide sur le 12/08 : ce
    jour-la, aucune minute n a eu les trois actifs propres en meme
    temps. Ce n est pas un defaut de l horloge, c est la journee.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
Le patch IMPRIME les lignes reconnues avant d ecrire.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "horloge_regime.py"
MARQUEUR = "MINI_ROUGE"

RE_CONST = re.compile(
    r'^MINI_CONNUS = 2 +# actifs connus exiges pour nommer un regime'
    r' global$', re.M)

RE_CORPS = re.compile(
    r'^    connus = \[e for e in par_actif\.values\(\) if e != "INCONNU"\]\n'
    r'    if len\(connus\) < MINI_CONNUS:\n'
    r'        return "INCONNU"\n'
    r'    ch = sum\(1 for e in connus if e == "CHURN"\)\n'
    r'    if ch == len\(connus\):\n'
    r'        return "CARNAGE"\n'
    r'    if float\(ch\) / len\(connus\) >= 2\.0 / 3\.0:\n'
    r'        return "CHURN"\n'
    r'    if all\(e == "PROPRE" for e in connus\):\n'
    r'        return "PROPICE"\n'
    r'    return "DOUTEUX"$', re.M)

RE_ENTETE = re.compile(
    r'^    L\.append\("etat global : il faut %d actifs connus, sinon'
    r' INCONNU ;"\n'
    r'             % MINI_CONNUS\)\n'
    r'    L\.append\("              tous CHURN -> CARNAGE, 2 sur 3 ->'
    r' CHURN,"\)\n'
    r'    L\.append\("              tous PROPRE -> PROPICE, sinon'
    r' DOUTEUX"\)$', re.M)

CONST = '''# Le quorum est ASYMETRIQUE, et c est le 12/08 qui l a impose. Avec le
# meme seuil des deux cotes, la case INCONNU pesait 34 tickets a -15,84
# EUR -- presque toutes des periodes « US30 en CHURN, les deux autres
# muets ». L information rouge etait la et le seuil la jetait.
#
#   un faux ROUGE coute un trade manque
#   un faux VERT coute un trade dans le hachoir
#
# On ne paie donc pas le meme prix des deux cotes.
MINI_ROUGE = 1        # actifs connus exiges pour nommer un etat rouge
MINI_VERT = 3         # ... et pour PROPICE ou CARNAGE, qui affirment fort'''

CORPS = '''    connus = [e for e in par_actif.values() if e != "INCONNU"]
    if len(connus) < MINI_ROUGE:
        return "INCONNU"
    ch = sum(1 for e in connus if e == "CHURN")
    # CARNAGE et PROPICE affirment quelque chose de fort : ils exigent les
    # trois actifs. CHURN se contente de ce qu on sait.
    if len(connus) >= MINI_VERT and ch == len(connus):
        return "CARNAGE"
    if float(ch) / len(connus) >= 2.0 / 3.0:
        return "CHURN"
    if len(connus) >= MINI_VERT and all(e == "PROPRE" for e in connus):
        return "PROPICE"
    return "DOUTEUX"'''

ENTETE = '''    L.append("etat global : %d actif connu suffit pour un etat rouge,"
             % MINI_ROUGE)
    L.append("              %d sont exiges pour CARNAGE et pour PROPICE ;"
             % MINI_VERT)
    L.append("              un faux rouge coute un trade manque, un faux")
    L.append("              vert coute un trade dans le hachoir")'''


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

    ancres = (("la constante MINI_CONNUS", RE_CONST),
              ("le corps de etat_global", RE_CORPS),
              ("les lignes de regle de l entete", RE_ENTETE))
    for nom, rx in ancres:
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Le fichier n est pas la version du 12/08 a midi.")
            print("Rien n a ete ecrit.")
            return 1
        print("  %-32s : %s"
              % (nom, rx.search(src).group(0).split("\n")[0].strip()[:56]))

    neuf = RE_CONST.sub(lambda m: CONST, src, count=1)
    neuf = RE_CORPS.sub(lambda m: CORPS, neuf, count=1)
    neuf = RE_ENTETE.sub(lambda m: ENTETE, neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Nouvelle regle :")
    print("  aucun actif connu              -> INCONNU")
    print("  les 3 connus et tous CHURN     -> CARNAGE")
    print("  au moins 2/3 des connus CHURN  -> CHURN   (1 seul suffit)")
    print("  les 3 connus et tous PROPRE    -> PROPICE")
    print("  sinon                          -> DOUTEUX")
    print()
    print("A regarder ensuite : la case INCONNU doit fondre. Si elle garde")
    print("30 tickets a -15 EUR, le probleme n etait pas le quorum.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
