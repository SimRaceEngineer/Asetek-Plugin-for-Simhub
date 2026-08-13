# -*- coding: utf-8 -*-
"""
patch_panel_v4pro.py -- le REPL du 8095 parle a DeepSeek V4 Pro

  python patch_panel_v4pro.py --essai
  python patch_panel_v4pro.py

CE QU IL AJOUTE -- DEUX LIGNES

    Dans run_panel_loop.bat, juste apres `set PA_ROLE=panel` :

        set COUNCIL_DEEPSEEK_REASONER_MODEL=deepseek-v4-pro
        set COUNCIL_DEEPSEEK_MODEL=deepseek-v4-flash

    Et rien d autre. Ni le garde-fou anti-doublon, ni PA_ROLE, ni la
    boucle de relance. Ce fichier porte la variable la plus dangereuse
    de la stack : sans PA_ROLE=panel, price_action demarre en role
    moteur et envoie de vrais ordres.

POURQUOI CES NOMS DE VARIABLES

    Il a fallu trois fichiers pour les trouver, et les deux premiers
    etaient des fausses pistes :

      llm_client.py     lit DEEPSEEK_MODEL -- le REPL ne l utilise pas
      repl_web.py       delegue a council_shadow._call_model()
      council_shadow.py ligne 93, la vraie variable

    Trois essais avec DEEPSEEK_MODEL, dont un avec un nom de modele
    inexistant, ont tous donne le meme resultat : la variable n etait
    pas lue. C est ce qui a mis sur la piste.

    Le routage se fait par PREFIXE d identifiant (council_shadow
    lignes 90-91) : ce qui commence par "deepseek" part sur
    DEEPSEEK_BASE_URL. deepseek-v4-pro est donc route sans rien
    d autre a changer.

MESURE AVANT / APRES, la meme question "Reponds juste OK"

    deepseek-reasoner   'OK'    9.4 / 10.1 / 11.9 / 12.3 s
    deepseek-v4-pro     'OK.'  21.2 / 17.2 s

    Le texte change -- "OK." avec un point -- et la latence double.
    Deux signes concordants que la bascule prend effet, la ou les
    essais precedents ne changeaient rien.

    120 s de COUNCIL_TIMEOUT : il reste cinq fois la marge. Mais sur
    une vraie question avec 175 000 caracteres de contexte, ce sera
    plus long que 20 s. A surveiller.

POURQUOI CHANGER AUSSI LA VOIE "chat"

    L API ne liste plus que deepseek-v4-flash et deepseek-v4-pro.
    deepseek-chat et deepseek-reasoner repondent encore comme alias,
    mais ils ont disparu du catalogue. Le jour ou ils tomberont,
    l echec sera SILENCIEUX -- c est exactement l incident de juillet
    documente dans llm_client.py ligne 35, ou un modele inexistant a
    renvoye du vide pendant deux semaines.

QUAND CA PREND EFFET -- PAS TOUT SEUL. LIRE CECI.

    Le `.bat` est structure ainsi :

        set PA_ROLE=panel        <- les deux lignes se posent ici
        set PY_PANEL=...
        :loop
          "%PY_PANEL%" price_action.py
          timeout /t 2
        goto loop

    Les `set` sont AVANT `:loop`. Le cmd.exe qui tourne les a executes
    une fois, au demarrage ; sa boucle ne repasse jamais dessus. Le
    wrapper relance bien price_action toutes les ~40 minutes, mais
    avec SON PROPRE environnement, fige a son lancement.

    Donc : tuer le python du panneau ne suffit PAS. Il faut arreter le
    cmd.exe qui porte run_panel_loop.bat, puis son python, puis
    relancer le .bat. Sinon le panneau redemarre sans les variables et
    rien ne le signale -- il continue de parler a deepseek-reasoner.

    (Cette note corrige ce que ce fichier affirmait le 13/08 au matin :
    "les variables seront prises au prochain cycle, sans rien faire".
    C etait faux, et le genre de faux qui ne se voit pas : le panneau
    repond, le REPL repond, seule l identite du modele est autre.)

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
Le fichier n est PAS execute par ce script.
"""
import argparse
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "run_panel_loop.bat"
MARQUEUR = "COUNCIL_DEEPSEEK_REASONER_MODEL"

RE_ANCRE = re.compile(r'^(set PA_ROLE=panel)[ \t]*\r?$', re.M)

NEUF = '''
REM --- 2026-08-13 : le REPL du 8095 passe a DeepSeek V4 Pro. ---
REM La variable est lue par council_shadow.py ligne 93, PAS par
REM llm_client (qui lit DEEPSEEK_MODEL et que le REPL n utilise pas).
REM Mesure avant/apres sur "Reponds juste OK" : deepseek-reasoner
REM repondait 'OK' en 9-12 s, deepseek-v4-pro repond 'OK.' en 17-21 s.
REM Le routage se fait par prefixe d identifiant : "deepseek*" part
REM sur DEEPSEEK_BASE_URL, rien d autre a changer.
REM La voie chat bascule aussi : l API ne liste plus deepseek-chat ni
REM deepseek-reasoner, qui ne survivent que comme alias. Le jour ou ils
REM tomberont l echec sera SILENCIEUX -- un modele inconnu renvoie du
REM vide, pas une erreur (incident de juillet, llm_client.py l.35).
set COUNCIL_DEEPSEEK_REASONER_MODEL=deepseek-v4-pro
set COUNCIL_DEEPSEEK_MODEL=deepseek-v4-flash'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1

    src = enc = None
    for e in ("cp1252", "utf-8", "utf-8-sig"):
        try:
            src = io.open(a.fichier, encoding=e, newline="").read()
            enc = e
            break
        except (UnicodeDecodeError, ValueError):
            continue
    if src is None:
        print("KO : encodage non reconnu pour %s" % a.fichier)
        return 1
    print("%s : %d lignes, encodage %s" % (a.fichier, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    n = len(RE_ANCRE.findall(src))
    if n != 1:
        print("KO : %d occurrence(s) de `set PA_ROLE=panel`, il en faut 1."
              % n)
        print("Ce fichier porte la variable la plus dangereuse de la stack.")
        print("Rien n a ete ecrit.")
        return 1

    # Le retour a la ligne du fichier, pour ne pas melanger CRLF et LF
    # dans un .bat -- cmd.exe tolere, mais un diff futur serait illisible.
    fin = "\r\n" if "\r\n" in src else "\n"
    bloc = NEUF.replace("\n", fin)
    # L ancre consomme le \r de sa ligne (\r? avant $). Sans le remettre
    # a la fin du bloc, le \n d origine se retrouve seul et le fichier
    # devient mixte CRLF/LF -- cmd.exe tolere, un diff futur non.
    queue = "\r" if fin == "\r\n" else ""
    neuf = RE_ANCRE.sub(lambda m: m.group(1) + bloc + queue, src, count=1)

    if "set PA_ROLE=panel" not in neuf:
        print("KO : PA_ROLE a disparu de la substitution. Rien n a ete ecrit.")
        return 1

    print()
    print("Deux lignes ajoutees juste apres `set PA_ROLE=panel` :")
    print("  set COUNCIL_DEEPSEEK_REASONER_MODEL=deepseek-v4-pro")
    print("  set COUNCIL_DEEPSEEK_MODEL=deepseek-v4-flash")
    print()
    print("Rien d autre n est touche : ni PA_ROLE, ni le garde-fou")
    print("anti-doublon, ni la boucle de relance.")
    print()
    print("ATTENTION : ca ne prend PAS effet tout seul. Les `set` sont")
    print("avant `:loop` -- le cmd.exe qui tourne les a deja executes et")
    print("sa boucle ne repasse pas dessus. Relancer le python du panneau")
    print("le redemarrerait avec l ancien environnement, sans que rien ne")
    print("le signale : il repondrait toujours, mais a deepseek-reasoner.")
    print()
    print("Il faut arreter le cmd.exe qui porte run_panel_loop.bat, puis")
    print("son python, puis relancer le .bat.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc, newline="").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Rollback : copier le .bak par-dessus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
