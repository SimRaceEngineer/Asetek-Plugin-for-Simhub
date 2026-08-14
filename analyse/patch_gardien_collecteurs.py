# -*- coding: utf-8 -*-
"""
patch_gardien_collecteurs.py -- le gardien doit garder ce qui collecte

  python patch_gardien_collecteurs.py --essai
  python patch_gardien_collecteurs.py

CE QUI S EST PASSE, ET POURQUOI UN GARDIEN EXISTAIT DEJA SANS SERVIR

    Le 14/08 au matin, CINQ processus etaient morts depuis la veille
    20:04 : papier_tf, x60_onset, rafraichir_x60, panels_auto et
    rafraichir_orderflow. Douze heures sans un releve, et rien pour le
    dire -- on ne l a su qu en posant une question au REPL.

    Gardien-Stack.ps1 existe pourtant, et son principe est le bon :
    une passe compte les instances de chaque service et ramene ce
    compte a UN. Zero, on lance ; une, on ne touche a rien ; plus
    d une, on supprime les surnumeraires.

    Mais sa liste $SERVICES ne contenait QUE cinq entrees, dont aucun
    des collecteurs. Le gardien gardait les panneaux et laissait mourir
    ce qui produit la donnee.

LE PIEGE, ET IL FAUT LE DIRE AVANT LE RESTE

    L entree "8095" lance `price_action.py` avec Args = "" et
    FilePath = "python", sans variable d environnement.

    Or price_action.py a DEUX roles. Lance sans PA_ROLE=panel il
    demarre en role MOTEUR et passe de VRAIS ORDRES. Un gardien
    installe en tache planifiee et lance depuis un environnement ou
    PA_ROLE n est pas pose ferait donc exactement ca, toutes les cinq
    minutes, sans que personne ne l ait demande.

    Installer ce gardien tel quel aurait ete plus dangereux que de ne
    pas l installer. Le patch pose donc le role explicitement, juste
    avant le lancement, et le retire juste apres.

CE QUE LE PATCH FAIT -- TROIS CHOSES

    1. QUATRE services ajoutes a $SERVICES : papier_tf --loop,
       x60_onset --loop, rafraichir_x60, rafraichir_orderflow.
       Les DEUX --loop comptent : lances sans, ces scripts impriment
       leur rapport et s arretent aussitot. C est l erreur que j ai
       commise ce matin en les relancant a la main, et un gardien qui
       la repeterait toutes les cinq minutes relancerait sans fin des
       processus qui meurent aussitot.

    2. Un champ Env par service, et PA_ROLE=panel sur price_action.
       Pose avant Start-Process, retire apres -- pour que le role ne
       fuite pas vers les autres lancements de la meme passe.

    3. L interpreteur EPINGLE, le meme que demarrage_quotidien.cmd.
       "python" tout court depend du PATH, et une tache planifiee n a
       pas le PATH d un shell ouvert : un gardien qui lance le mauvais
       python relance des processus qui ne trouvent pas MetaTrader5 et
       meurent -- en boucle, toutes les cinq minutes, silencieusement.
       Repli sur "python" si le chemin epingle n existe pas.

CE QU IL NE TOUCHE PAS

    Ni trading_engine, ni terminal64, ni la logique de comptage, ni la
    branche qui supprime les doublons, ni les cinq services d origine
    hormis l ajout du role sur price_action.

TROIS ANCRES, chacune verifiee unique. IDEMPOTENT. Sauvegarde
horodatee. Le fichier est du PowerShell : pas d ast.parse possible
ici, donc les controles portent sur la STRUCTURE -- neuf entrees de
service la ou il y en avait cinq, accolades et parentheses
equilibrees dans le bloc $SERVICES, deux --loop, un PA_ROLE.
La verification de syntaxe reelle se fait sur la machine, avec
[ScriptBlock]::Create, AVANT d installer quoi que ce soit.
"""
import argparse
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "Gardien-Stack.ps1"
MARQUEUR = "papier_tf.py"

A1 = '''$STACK   = "C:\\Users\\Administrator\\Downloads\\Scalp-EA-main\\Scalp-EA-main"
'''
N1 = '''$STACK   = "C:\\Users\\Administrator\\Downloads\\Scalp-EA-main\\Scalp-EA-main"
# Le MEME interpreteur que demarrage_quotidien.cmd (%PY%), ajoute le
# 14/08. "python" tout court depend du PATH, et une tache planifiee n a
# pas le PATH d un shell ouvert : un gardien qui lance le mauvais
# python relance des processus qui ne trouvent pas MetaTrader5 et
# meurent aussitot -- en boucle, toutes les cinq minutes, sans un mot.
$PY = "C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe"
if (-not (Test-Path $PY)) { $PY = "python" }
'''

A2 = '''    @{ Nom = "sarkeep_m5";  Motif = "sarkeep_m5.py";     Script = "sarkeep_m5.py";     Args = "";              Port = 0 }
)
'''
N2 = '''    @{ Nom = "sarkeep_m5";  Motif = "sarkeep_m5.py";     Script = "sarkeep_m5.py";     Args = "";              Port = 0 },
    # --- LES COLLECTEURS, ajoutes le 14/08 -----------------------------
    # Le 13/08 a 20:04 ces quatre-la sont morts avec panels_auto et ne
    # sont pas revenus. Douze heures sans un releve, decouvertes en
    # posant une question au REPL. Le gardien gardait les panneaux et
    # laissait mourir ce qui produit la donnee.
    #
    # Les DEUX --loop ne sont pas decoratifs : lances sans, papier_tf
    # et x60_onset impriment leur rapport et s arretent. Un gardien qui
    # les relancerait sans --loop redemarrerait sans fin des processus
    # qui meurent aussitot, et le compte ne tiendrait jamais.
    @{ Nom = "papier_tf";   Motif = "papier_tf.py";      Script = "papier_tf.py";      Args = "--loop";        Port = 0 },
    @{ Nom = "x60_onset";   Motif = "x60_onset.py";      Script = "x60_onset.py";      Args = "--loop";        Port = 0 },
    @{ Nom = "raf_x60";     Motif = "rafraichir_x60.py"; Script = "rafraichir_x60.py"; Args = "";              Port = 0 },
    @{ Nom = "raf_of";      Motif = "rafraichir_orderflow.py"; Script = "rafraichir_orderflow.py"; Args = ""; Port = 0 }
)
'''

A3 = '''            $argus = $s.Script
            if ($s.Args -ne "") { $argus = $s.Script + " " + $s.Args }
            try {
                Start-Process -FilePath "python" -ArgumentList $argus `
                              -WorkingDirectory $STACK -WindowStyle Minimized
'''
N3 = '''            $argus = $s.Script
            if ($s.Args -ne "") { $argus = $s.Script + " " + $s.Args }
            try {
                # LE ROLE, pose juste avant et retire juste apres.
                # price_action.py lance sans PA_ROLE=panel demarre en
                # role MOTEUR et passe de VRAIS ORDRES. Un gardien qui
                # relancerait ce script sans role, toutes les cinq
                # minutes, serait plus dangereux que pas de gardien.
                # On retire la variable ensuite pour qu elle ne fuite
                # pas vers les autres lancements de la meme passe.
                $poses = @()
                if ($s.ContainsKey("Env")) {
                    foreach ($k in $s.Env.Keys) {
                        Set-Item -Path ("Env:" + $k) -Value $s.Env[$k]
                        $poses += $k
                    }
                }
                Start-Process -FilePath $PY -ArgumentList $argus `
                              -WorkingDirectory $STACK -WindowStyle Minimized
                foreach ($k in $poses) {
                    Remove-Item -Path ("Env:" + $k) -ErrorAction SilentlyContinue
                }
'''

A4 = '''    @{ Nom = "8095";        Motif = "price_action.py";   Script = "price_action.py";   Args = "";              Port = 8095 },
'''
N4 = '''    @{ Nom = "8095";        Motif = "price_action.py";   Script = "price_action.py";   Args = "";              Port = 8095; Env = @{ PA_ROLE = "panel" } },
'''

ANCRES = ((A1, N1, "la definition de $STACK"),
          (A4, N4, "l entree price_action"),
          (A2, N2, "la fin de la liste $SERVICES"),
          (A3, N3, "le bloc de lancement"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    neuf = src
    for anc, nouv, nom in ANCRES:
        n = neuf.count(anc)
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        neuf = neuf.replace(anc, nouv, 1)
    print("Quatre ancres, chacune unique.")

    # PowerShell : pas d ast.parse. On controle donc la STRUCTURE, et
    # la syntaxe reelle se verifiera sur la machine avec
    # [ScriptBlock]::Create avant toute installation.
    av = len(re.findall(r'@\{ Nom = ', src))
    ap = len(re.findall(r'@\{ Nom = ', neuf))
    if ap != av + 4:
        print("KO : %d services avant, %d apres -- il en faut 4 de plus."
              % (av, ap))
        print("Rien n a ete ecrit.")
        return 1
    print("Services : %d avant, %d apres." % (av, ap))

    bloc = neuf.split("$SERVICES = @(", 1)[1].split("\n)\n", 1)[0]
    if bloc.count("{") != bloc.count("}"):
        print("KO : accolades desequilibrees dans $SERVICES (%d / %d)."
              % (bloc.count("{"), bloc.count("}")))
        print("Rien n a ete ecrit.")
        return 1
    if bloc.count("(") != bloc.count(")"):
        print("KO : parentheses desequilibrees dans $SERVICES.")
        print("Rien n a ete ecrit.")
        return 1
    print("Bloc $SERVICES equilibre.")

    for quoi, combien in (('Args = "--loop"', 2), ('PA_ROLE = "panel"', 1),
                          ('-FilePath $PY', 1)):
        if neuf.count(quoi) != combien:
            print("KO : %s apparait %d fois, il en faut %d."
                  % (quoi, neuf.count(quoi), combien))
            print("Rien n a ete ecrit.")
            return 1
    print("Deux --loop, un PA_ROLE=panel, un interpreteur epingle.")

    for t in ('function Lister', 'trading_engine', '-Constat', '-Installer'):
        if src.count(t) != neuf.count(t):
            print("KO : %s n apparait plus le meme nombre de fois." % t)
            print("Rien n a ete ecrit.")
            return 1
    print("Intacts : le comptage, la suppression des doublons, -Constat")
    print("et -Installer.")

    print()
    print("Le gardien surveillera desormais NEUF services :")
    print("  price_action (avec PA_ROLE=panel), orderflow_panel,")
    print("  panels_auto, sarkeep_gel, sarkeep_m5,")
    print("  papier_tf --loop, x60_onset --loop, rafraichir_x60,")
    print("  rafraichir_orderflow.")
    print()
    print("ENSUITE, ET DANS CET ORDRE :")
    print("  1. verifier la syntaxe PowerShell")
    print("  2. .\\Gardien-Stack.ps1 -Constat   <- ne lance RIEN, dit")
    print("     seulement ce qu il ferait. A lire avant d installer.")
    print("  3. .\\Gardien-Stack.ps1 -Installer <- tache toutes les 5 mn")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. NE PAS installer avant d avoir lu -Constat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
