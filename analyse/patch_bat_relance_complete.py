#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_bat_relance_complete.py -- un bouton qui relance VRAIMENT tout.

CE QUE LE .BAT FAIT, ET CE QU IL NE FAIT PAS
--------------------------------------------
START_TRADING_STACK_V3.bat, 497 lignes, releve le 25/08 :

    [0/7]  elevation UAC, verrou anti-double-lancement, fermeture des
           fenetres Stack V3 precedentes, fermeture du terminal FTMO
    [1/5]  taskkill /F /T /IM python.exe   <-- GLOBAL, tue TOUT python
           puis ~40 taskkill par titre, ports 8081-8100, verrous,
           __pycache__, et les .dat perimes dans les 4 dossiers MT5
    [2/5]  MT5 T1/T2/T3 + FTMO, 15 s d attente
    [3/5]  controle des fichiers de pont, ea_autonomy_mode.flag
    [4/5]  PA_ROLE=engine puis trading_engine.py, 20 s d attente,
           puis run_panel_loop / run_latent_loop / run_orderflow_loop /
           run_jauge_loop / run_monitor_loop, ftmo_target_publisher,
           trade_copier_ftmo, leg_state, leg_llm_shadow,
           futures_watchdog, spx_onset_logger
    fin    40 s d attente puis verify_stack.py

Le meme jour, la machine portait vingt et un python. HUIT n etaient
lances par personne :

    papier_tf.py --loop                     24/08 17:33
    x60_onset.py --loop                     24/08 17:33
    rafraichir_x60.py                       24/08 17:33
    panels_auto.py --dest panels            24/08 17:33
    miroir_papers.py --armer                24/08 18:40   (a la main)
    pont_miroirs.py --lecteur               25/08 16:03
    pont_miroirs.py --envoyeur ...          25/08 16:03
    gardien_stack.py                        JAMAIS

Le [1/5] les tue tous. Le reste du fichier n en relance aucun. C est
pour ca qu apres chaque relance il fallait finir a la main -- et que le
gardien, lui, n a jamais tourne du tout.

POURQUOI LE BLOC EST POSE A LA FIN, ET PAS AILLEURS
    Deux contraintes, une seule place possible.

    Apres le [1/5], sinon le taskkill global tue ce qu on vient de
    lancer.

    Apres le moteur, et la ce n est pas du confort : papers_exempt.PLAGES
    est lu par les modules de sortie, qui vivent DANS trading_engine.
    Un miroir arme avant le moteur verrait la branche 5 sortir comme le
    miroir 2. La comparaison 1 contre 5 ne mesurerait plus le filtre
    CVD -- elle ne mesurerait plus rien.

PA_ROLE EST VIDE EN ENTREE DE BLOC
    Le [4/5] fait "set PA_ROLE=engine" et ne l efface jamais. Tout ce
    qui demarre apres en herite. On le vide avant de lancer quoi que ce
    soit : c est exactement le genre d heritage silencieux qui fait
    demarrer un panneau dans le mauvais role.

CE QUE CE PATCH NE TOUCHE PAS
    Il INSERE, il ne recrit rien. Les lignes de configuration -- dont
    celles qui portent un identifiant de messagerie -- ne sont ni lues
    ni deplacees ni reecrites. Le fichier est traite en latin-1, qui
    fait un aller-retour octet pour octet : aucun accent ne peut se
    transformer en chemin.

CE QUI RESTE UN TROU, ET QUI EST SIGNALE SANS ETRE COMBLE
    data_node.py tourne depuis C:\data_node\, hors de la stack. Le
    taskkill global le tue lui aussi, et rien ne le relance. Je ne le
    lance PAS ici : je ne connais pas sa ligne de commande, et lancer
    un processus avec les mauvais arguments est pire que ne pas le
    lancer. Le bloc le SIGNALE en fin de course. Donne-moi sa ligne de
    commande complete et je l ajoute.

USAGE
-----
    python patch_bat_relance_complete.py                <- simulation
    python patch_bat_relance_complete.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\START_TRADING_STACK_V3.bat"
SUFFIXE_BAK = ".bak_relance"
MARQUEUR = "RELANCE_COMPLETE"

# ---------------------------------------------------------------------
#  Le bloc. Ecrit en ASCII pur : le .bat vit dans une console OEM, un
#  accent y devient un caractere de dessin.
#  Les fins de ligne sont posees par le script, pas ici.
# ---------------------------------------------------------------------
BLOC = r"""
echo.
echo =====================================================================
echo  [5/5] RELANCE_COMPLETE -- ce que ce fichier ne relancait pas
echo =====================================================================
rem ---------------------------------------------------------------------
rem  Pose le 25/08/2026.
rem
rem  Le [1/5] fait un taskkill global sur python.exe. Il tue tout, y
rem  compris les huit processus ci-dessous, qu aucune ligne de ce
rem  fichier ne relancait. Ils repartaient a la main -- ou pas du tout,
rem  comme le gardien.
rem
rem  Ce bloc est APRES le moteur, et c est obligatoire pour le miroir :
rem  papers_exempt.PLAGES est lu par les modules de sortie, qui vivent
rem  dans trading_engine. Un miroir arme avant le moteur verrait la
rem  branche 5 sortir comme le miroir 2, et la mesure du filtre CVD ne
rem  voudrait plus rien dire.
rem ---------------------------------------------------------------------

rem PA_ROLE vaut encore "engine" ici : pose au [4/5], jamais efface.
rem Tout ce qui demarre ensuite en heriterait.
set "PA_ROLE="

cd /d "%PROJ%"

rem --------------------------------------------------------- panneaux
if exist "%PROJ%papier_tf.py" (
    echo   + papier_tf --loop
    start "Papier TF" /MIN cmd /c %PY% "%PROJ%papier_tf.py" --loop
) else ( echo   ! papier_tf.py ABSENT )
timeout /t 2 /nobreak >nul 2>&1

if exist "%PROJ%x60_onset.py" (
    echo   + x60_onset --loop
    start "X60 Onset" /MIN cmd /c %PY% "%PROJ%x60_onset.py" --loop
) else ( echo   ! x60_onset.py ABSENT )
timeout /t 2 /nobreak >nul 2>&1

if exist "%PROJ%rafraichir_x60.py" (
    echo   + rafraichir_x60
    start "Rafraichir X60" /MIN cmd /c %PY% "%PROJ%rafraichir_x60.py"
) else ( echo   ! rafraichir_x60.py ABSENT )
timeout /t 2 /nobreak >nul 2>&1

if exist "%PROJ%panels_auto.py" (
    echo   + panels_auto --dest panels
    start "Panels Auto" /MIN cmd /c %PY% "%PROJ%panels_auto.py" --dest panels
) else ( echo   ! panels_auto.py ABSENT )
timeout /t 3 /nobreak >nul 2>&1

rem ------------------------------------------- miroir, branches 1/2/5
rem La branche 5 n existe que si papers_exempt connait la plage 5220000.
rem Sans elle le miroir arme quand meme -- les branches 1 et 2 sont
rem intactes -- mais la branche 5 sortirait comme le miroir 2 et la
rem comparaison serait fausse. On le dit fort plutot que de la laisser
rem mentir en silence.
if exist "%PROJ%papers_exempt.py" (
    findstr /c:"5220000" "%PROJ%papers_exempt.py" >nul 2>&1
    if errorlevel 1 (
        echo   ! papers_exempt SANS la plage 5220000 : la branche 5
        echo   ! sortirait comme le miroir 2. Mesure 1 contre 5 a jeter.
    ) else (
        echo   . papers_exempt : plage 5220000 presente
    )
) else ( echo   ! papers_exempt.py ABSENT )

if exist "%PROJ%miroir_papers.py" (
    echo   + miroir_papers --armer   ^(branches 1, 2 et 5^)
    start "Miroir Papers" /MIN cmd /c %PY% "%PROJ%miroir_papers.py" --armer
) else ( echo   ! miroir_papers.py ABSENT )
timeout /t 5 /nobreak >nul 2>&1

rem --------------------------------------- pont vers le compte miroir
rem Si le lanceur dedie existe on le prefere : il connait les reglages
rem du pont mieux que ce fichier. Sinon on pose les deux roles a la
rem main, dans l ordre lecteur puis envoyeur -- l envoyeur consomme ce
rem que le lecteur produit.
if exist "%PROJ%PONT_MIROIRS.cmd" (
    echo   + PONT_MIROIRS.cmd
    start "Pont Miroirs" /MIN cmd /c "%PROJ%PONT_MIROIRS.cmd"
) else (
    if exist "%PROJ%pont_miroirs.py" (
        echo   + pont_miroirs --lecteur
        start "Pont Lecteur" /MIN cmd /c %PY% "%PROJ%pont_miroirs.py" --lecteur
        timeout /t 3 /nobreak >nul 2>&1
        echo   + pont_miroirs --envoyeur --compte %CPT_MIROIR% --reel
        start "Pont Envoyeur" /MIN cmd /c %PY% "%PROJ%pont_miroirs.py" --envoyeur --compte %CPT_MIROIR% --reel
    ) else ( echo   ! pont_miroirs.py ABSENT )
)
timeout /t 5 /nobreak >nul 2>&1

rem ------------------------------------------------------ le gardien
rem En dernier, et c est voulu : il inventorie ce qui tourne et relance
rem ce qui manque. Lance plus tot, il verrait un demarrage en cours et
rem doublerait des processus.
if exist "%PROJ%gardien_stack.py" (
    echo   + gardien_stack
    start "Gardien Stack" /MIN cmd /c %PY% "%PROJ%gardien_stack.py"
) else ( echo   ! gardien_stack.py ABSENT )
timeout /t 3 /nobreak >nul 2>&1

rem -------------------------------------------------- le trou signale
if exist "C:\data_node\data_node.py" (
    echo.
    echo   ATTENTION : C:\data_node\data_node.py existe.
    echo   Le taskkill du [1/5] le tue, et rien ici ne le relance --
    echo   sa ligne de commande n est pas connue de ce fichier. A
    echo   relancer par son propre lanceur.
)

echo.
echo   RELANCE_COMPLETE terminee. Controle attendu apres redemarrage :
echo     - sl_arbitre annonce BLOQUE, et non OBSERVATION
echo     - le miroir ecrit des lignes M5xxxxxx CVD ok / CVD REFUSE
echo     - le 8095 sert /cartes avec son style et sa barre
echo.
"""

# La ligne qui pose le numero de compte du miroir, inseree en tete de
# bloc pour qu il soit visible et modifiable en un seul endroit.
DECL_COMPTE = 'set "CPT_MIROIR=182109"'


def fins_de_ligne(s):
    """Le style dominant du fichier. Un .bat mixte casse a la lecture."""
    crlf = s.count("\r\n")
    lf = s.count("\n") - crlf
    return "\r\n" if crlf >= lf else "\n"


def point_insertion(lignes):
    """(indice, erreur). On se pose AVANT l appel a verify_stack : le
    controle final doit voir ce qu on vient de lancer."""
    candidates = [i for i, l in enumerate(lignes) if "verify_stack" in l]
    if not candidates:
        return -1, "aucune ligne ne mentionne verify_stack"
    reels = []
    for i in candidates:
        nu = lignes[i].strip().lower()
        if nu.startswith("rem") or nu.startswith("echo") or nu.startswith("::"):
            continue
        reels.append(i)
    if not reels:
        return -1, ("verify_stack n apparait qu en commentaire ou en echo"
                    " (lignes %s)"
                    % ", ".join(str(i + 1) for i in candidates))
    i = reels[0]
    if lignes[i][:1] in (" ", "\t"):
        return -1, ("la ligne %d est indentee -- elle est probablement"
                    " dans un bloc entre parentheses, on n insere pas"
                    " la-dedans" % (i + 1))
    return i, ""


def applique(s):
    """(texte, erreur, indice)."""
    fin = fins_de_ligne(s)
    lignes = s.split(fin)
    i, err = point_insertion(lignes)
    if i < 0:
        return None, err, -1
    bloc = [DECL_COMPTE] + BLOC.replace("\r\n", "\n").split("\n")
    neuf = lignes[:i] + bloc + lignes[i:]
    return fin.join(neuf), "", i


def lire(chemin):
    # latin-1 : aller-retour octet pour octet, quelle que soit la page
    # de code reelle du fichier. Rien ne peut se corrompre.
    with io.open(chemin, encoding="latin-1", newline="") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_bat_relance_complete -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    fin = fins_de_ligne(s)
    print("cible  : %s" % a.cible)
    print("         %d lignes, %d octets, fins de ligne %s"
          % (s.count(fin) + 1, len(s), "CRLF" if fin == "\r\n" else "LF"))

    if MARQUEUR in s:
        print("")
        print("Deja pose : le bloc RELANCE_COMPLETE est dans le fichier.")
        return 0

    neuf, err, i = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        print("Me montrer la fin du fichier plutot que de me laisser")
        print("deviner : c est le bouton qui redemarre la machine.")
        return 1

    print("         ancre : ligne %d, juste avant verify_stack" % (i + 1))
    print("")
    print("a inserer, dans cet ordre :")
    for x in ("PA_ROLE vide (il vaut encore engine)",
              "papier_tf --loop",
              "x60_onset --loop",
              "rafraichir_x60",
              "panels_auto --dest panels",
              "controle papers_exempt / plage 5220000",
              "miroir_papers --armer   (branches 1, 2, 5)",
              "PONT_MIROIRS.cmd, sinon lecteur puis envoyeur",
              "gardien_stack",
              "signalement de data_node"):
        print("   + %s" % x)
    print("")
    print("       %d octets ajoutes, rien de recrit."
          % (len(neuf) - len(s)))

    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = a.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(a.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)
    with io.open(a.cible, "w", encoding="latin-1", newline="") as f:
        f.write(neuf)
    print("ecrit  : %s" % a.cible)

    relu = lire(a.cible)
    if relu != neuf:
        print("relu   : DIFFERENT de ce qui devait etre ecrit"
              " -- RESTAURER %s" % bak)
        return 1
    manques = [x for x in (MARQUEUR, "miroir_papers.py", "gardien_stack.py",
                           "CPT_MIROIR", "papers_exempt")
               if x not in relu]
    if manques:
        print("relu   : INCOMPLET, manque %s -- RESTAURER %s"
              % (", ".join(manques), bak))
        return 1
    print("relu   : identique a l octet pres, et les cinq marques y sont.")
    if relu.count(MARQUEUR) != 2:
        print("relu   : %d fois %s au lieu de 2 -- a regarder"
              % (relu.count(MARQUEUR), MARQUEUR))

    print("")
    print("-" * 68)
    print("Le fichier ne prend effet qu au prochain lancement du .bat.")
    print("Et ce lancement coupe TOUT : taskkill global sur python au")
    print("[1/5], fermeture des terminaux MT5 au [2/5]. A faire hors")
    print("seance, jamais sur des positions ouvertes non gerees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
