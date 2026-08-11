#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_journal_v3.py -- ajoute les conclusions du 11/08 au journal d etude

CE QU IL FAIT
    Insere quatre entrees en tete de JOURNAL, passe VERSION de 2 a 3 et
    DATE_VERSION au 11/08. Il ne touche a aucune entree existante.

POURQUOI EN TETE, ET POURQUOI SANS RIEN EFFACER
    journal_pdf.py pose sa propre regle : "On ne reecrit pas l histoire.
    Une conclusion fausse n est pas effacee, elle est datee puis contredite
    par une entree ulterieure." La troisieme entree ajoutee ici ne fait que
    cela -- elle consigne quatre choses crues le matin du 11/08 et
    demontees l apres-midi. Elle compte autant que les autres : un journal
    qui ne garderait que les conclusions survivantes donnerait l illusion
    qu on avance en ligne droite.

CE QU IL NE FAIT PAS
    Il ne branche pas le journal sur notes/*.md, contrairement a ce que
    j avais propose. Le fichier argumente explicitement contre : "le
    contenu est une DONNEE dans ce fichier [...] il n y a jamais deux
    sources de verite". Le brancher sur les notes creerait exactement la
    seconde source qu il a ete concu pour eviter.

    Il ne calcule rien non plus. Tous les chiffres inseres viennent des
    scripts nommes dans le texte, et ont ete lus dans leur sortie.

IDEMPOTENT.
"""
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "journal_pdf.py"
MARQUEUR = "Le gel V9 a enfin pu tourner"
ANCRE_J = "JOURNAL = [\n"
ANCRE_V = "VERSION = 2"
NEUF_V = "VERSION = 3"
ANCRE_D = 'DATE_VERSION = "2026-08-10"'
NEUF_D = 'DATE_VERSION = "2026-08-11"'

ENTREES = '''    {
        "date": "2026-08-11",
        "titre": "Le gel V9 a enfin pu tourner, et les rails etaient sur le"
                 " disque depuis le debut",
        "corps": [
            "oos_v9 --champs annoncait une couverture famille X de 0 pour "
            "cent. J en avais conclu que le panel 8095 calculait ses rails a "
            "l affichage sans les persister, et donc que le verdict du 01/09 "
            "etait perdu. C etait faux. churn_trade_logger._write_series() "
            "ecrit rails_pos et rsi_pos, par actif ET par pas de temps, dans "
            "docs/rails_trades/series_DATE.jsonl. Les deux champs etaient la "
            "depuis le debut, dans une serie temporelle a cote du journal des "
            "tickets, et non dedans.",
            "rails_join.py joint chaque ticket au dernier instantane "
            "ANTERIEUR a son entree -- jamais posterieur, sans quoi le ticket "
            "porterait une information qu il n avait pas et le hors "
            "echantillon ne vaudrait plus rien. Sur 2 721 tickets : 93 pour "
            "cent renseignes aux quatre pas de temps, decalage median 17 "
            "secondes. Couverture X et Y a 93 pour cent, 100 pour cent sur la "
            "fenetre du gel. Aucune modification du moteur n a ete necessaire.",
            "Gel pose le 11/08 sur 2 555 tickets et 10 seances, du 29/07 au "
            "11/08. La tete X1, pas de trade contre le biais M1, sort avec ses "
            "trois colonnes au plancher : p seance 0,000, p signe 0,002, p "
            "heure 0,000. Sur dix seances 0,002 EST le minimum atteignable, "
            "donc X1 va dans le meme sens neuf ou dix fois sur dix. Le temoin "
            "X2 est nul a p signe 1,000 et le controle negatif X5 est negatif "
            "-- le dispositif de gel se comporte comme il doit. X1 ecarte 515 "
            "tickets qui valaient -16,46 EUR piece et fait passer le total de "
            "+1 209 a +9 684 EUR.",
            "Deux avertissements pour le 01/09. D abord ne pas empiler : X6 a "
            "un ecart plus gros que X1 mais son p signe passe de 0,002 a "
            "0,344, la moyenne monte et la regularite s effondre. Ensuite Y4, "
            "le controle negatif de Y1, devrait etre mauvais et fait +9,57 EUR "
            "par ticket a p seance 0,003. Lecture la plus probable : Y1 ne "
            "capte pas la capitulation mais le desaccord M1/M15 dans n importe "
            "quel sens. Y4 ne passe pas la regle des trois colonnes et n a que "
            "60 tickets, donc Y1 n est pas annulee -- mais elle sera jugee "
            "avec son miroir en regard, et si Y4 la depasse hors echantillon "
            "elle est refutee quels que soient ses propres p.",
            "Risque connu, ecrit avant le resultat : la fenetre in-sample "
            "enjambe les deux regimes et sort a +0,47 EUR par ticket en "
            "reference, alors que le range seul est a -8,87. Si le 12/08 au "
            "01/09 est integralement du range, X1 sera jugee dans des "
            "conditions qui n ont jamais existe isolement.",
        ],
    },
    {
        "date": "2026-08-11",
        "titre": "Les sorties : le stop du courtier gagne, le closer Python"
                 " detruit",
        "corps": [
            "close_reason est le DEAL_REASON de MT5 : 3 vaut EXPERT, une "
            "ligne de Python a ferme la position ; 4 vaut SL, le stop cote "
            "courtier a ete touche ; 5 vaut TP. Un SL a 91 pour cent de "
            "reussite n est pas un stop de perte : c est un trailing deja "
            "remonte en profit, que le prix vient toucher en retracant. MT5 le "
            "declare SL quand meme.",
            "Sur 2 720 tickets, mesure par sorties2.py : le motif 4 tient dans "
            "les deux regimes -- +39,79 puis +29,64 EUR par ticket, rendu 53 "
            "puis 58 pour cent du MFE atteint. Le motif 3 s effondre deux fois "
            ": il monte 36 pour cent moins haut (MFE 51,1 puis 32,6) ET rend "
            "163 pour cent au lieu de 103. Un ticket motif 3 du range monte a "
            "+32,6, rend 53 EUR, finit a -20. Sur 975 tickets. Les gagnants "
            "sont 20 pour cent moins frequents et 25 pour cent plus petits, ce "
            "qui est gerable ; le cout de chaque perdant a monte de 281 pour "
            "cent, ce qui ne l est pas. En ne corrigeant que ce dernier terme "
            ": +5 073 EUR au lieu de -11 918.",
            "405 tickets sont montes a +20 EUR ou plus et ont fini a zero ou "
            "en perte : 35 332 EUR laisses en route. Dans le range seul, 238 "
            "tickets et 19 981 EUR, soit 168 pour cent de la perte de la "
            "periode. S ils avaient simplement ete fermes a zero, le range "
            "serait positif.",
            "Le trou est le matin, et il ne depend pas du regime. Les sorties "
            "d avant 14h coutent 6 776 EUR en tendance -- pendant que la "
            "periode gagnait +12 164 -- et 7 281 EUR dans le range. Sur les "
            "onze seances : 14 057 EUR perdus avant 14h, 14 303 gagnes par "
            "tout le reste. Le decoupage par heure d ENTREE donne la meme "
            "reponse, -12 777 EUR, donc ce n est pas un artefact de l un ou de "
            "l autre. C est le meilleur candidat pour un gel V10, et il coche "
            "ce qui manquait a l amplitude : meme signe dans deux regimes "
            "opposes, 1 150 tickets, causal par construction puisque l heure "
            "est connue a l entree.",
            "Le verdict churn est le meilleur signal causal du dossier, et il "
            "est fige a l entree. CLEAN, MIXED, OK puis CHURN, dans cet ordre, "
            "monotone dans les DEUX regimes. CLEAN est le seul verdict positif "
            "dans le range (+3,26 EUR par ticket) et le seul dont le rendu "
            "passe sous 100 pour cent. OK n est pas CLEAN, c est demontre et "
            "non suppose : +3,26 contre -10,40. Consequence pour le gel V9 : "
            "sa regle Y1 selectionne MIXED, le milieu du gradient, pas le bon "
            "compartiment. Le fichier gele ne bouge pas, mais le verdict du "
            "01/09 se lira en le sachant.",
            "Enfin les jumeaux ne diversifient pas, ils doublent la taille. "
            "M206 est hold-until-reverse, M207 trail70+buffer -- un A/B "
            "delibere sur la sortie -- et 75 a 80 pour cent des tickets sont "
            "apparies a la minute, meme actif, meme sens, meme MFE au centime. "
            "Resultat +10,45 puis -10,31 EUR par ticket apparie : symetrique "
            "au dixieme pres, ce qui est la definition du levier. Le hold bat "
            "le trail de 3,73 EUR par ticket en tendance et l egale dans le "
            "range : l A/B a converge, il ne rend plus d information.",
        ],
    },
    {
        "date": "2026-08-11",
        "titre": "Quatre choses crues le matin, demontees l apres-midi",
        "corps": [
            "Cette entree existe parce que le journal l impose : une "
            "conclusion fausse n est pas effacee, elle est datee puis "
            "contredite. Sans elle, il ne resterait que les lectures "
            "survivantes, et on croirait avoir avance en ligne droite.",
            "L AMPLITUDE. Le matin, amplitude_pnl.py donnait un gradient net "
            "-- -4,21 puis -1,72 puis -0,39 EUR par trade des seances calmes "
            "aux agitees, et un WR monotone. Trois choses l ont demonte. M186 "
            "et M178, arretees fin juillet, portent 77 pour cent du tiers "
            "calme sur 14 pour cent de ses trades ; sans elles l ecart tombe "
            "de +3,83 a environ +0,76. La monotonie du WR etait un artefact de "
            "magic_daily_stats et disparait sur MT5 seul (49, 42, 52). Et sur "
            "les seize familles, neuf vont dans le bon sens et sept dans "
            "l autre : un tirage a pile ou face. Survit seulement le seuil des "
            "jumeaux, autour d une amplitude causale de 1,02, sur seize "
            "seances et avec un indicateur en retard de trois seances -- il "
            "annoncait encore agite les 5, 6 et 7 aout alors que le range "
            "avait commence.",
            "ER_5. Presente comme discriminant de regime, il est retire. Il "
            "MONTE en entrant dans le range (0,08 puis 0,54, 0,94, 0,76, 0,65 "
            "sur US500) parce que quand tout retrecit, la somme des variations "
            "quotidiennes s effondre plus vite que le deplacement net. Il "
            "mesure la regularite d une derive, pas une tendance. Le "
            "discriminant qui marche est deplacement net divise par largeur du "
            "canal.",
            "LE RANGE ACTUEL. Ecrit le matin que le range en cours nous "
            "coutait. Faux dans les proportions : sur 15/06 au 11/08, les 34 "
            "seances d avant le 31/07 ont coute 79 908 EUR contre 4 893 "
            "depuis. Le range de juin-juillet a coute seize fois plus. Et sept "
            "familles arretees depuis -- M186, M178, M354, M187, M201, M205, "
            "M203 -- additionnent 82 956 EUR de perte, soit PLUS que la perte "
            "totale de la periode : tout le reste du dispositif etait net "
            "positif. La bascule au 31/07 etait par ailleurs mal placee ; "
            "recalee au 05/08 elle donne -8,38 EUR par trade contre -2,22 "
            "avant, c est-a-dire que le range actuel est bien cher, mais pour "
            "une autre raison que celle avancee.",
            "PREOPEN_PROTECT ET 15h27. Presente comme la cause principale des "
            "reculs de stop apres les trois tickets du 10/08 -- 105,7 points "
            "rendus, verifies au centime. Le patch BE ou mieux reste juste, "
            "mais l heure de SORTIE le disculpe comme cause principale : 15h "
            "rend 86 pour cent du MFE en tendance et 131 dans le range, quand "
            "11h et 12h font 173 et 163. On a cherche au mauvais endroit "
            "pendant une journee parce que la premiere version de sorties.py "
            "groupait par heure d ENTREE.",
            "Deux defauts d outil dans la meme journee, pour memoire. "
            "churn_entry est un dictionnaire et non une chaine, ce qui a fait "
            "sortir un bloc en sept cents lignes illisibles et rendu inutile "
            "un premier patch de oos_v9. Et le marqueur d idempotence d un "
            "patch, isinstance(v, dict), existait deja ailleurs dans le "
            "fichier cible : le patch se croyait applique et ne faisait rien. "
            "Meme piege qu avec _sl_arb.install le matin meme.",
        ],
    },
    {
        "date": "2026-08-11",
        "titre": "La sauvegarde du VPS ne sauvegardait pas le code",
        "corps": [
            "Verification faite : Google Drive Desktop tourne, un lecteur G "
            "est monte, et quatre exports texte partent toutes les quinze "
            "minutes vers le dossier ScalpEA -- rails, contexte, orderflow, "
            "compte. Ca fonctionne depuis le 29/07 sans interruption. Mais ce "
            "sont des exports de panels : aucun fichier .py. Si le VPS "
            "disparaissait, les deux cents modules disparaissaient avec lui et "
            "il ne restait que des releves texte de ce qu ils affichaient.",
            "Le depot scalpea-vps existait pourtant deja, ses identifiants "
            "fonctionnent depuis le VPS, et son .gitignore en liste blanche "
            "est bien concu -- 13,16 Mio de pack pour 15,7 Mo de code, quand "
            "docs pese 7 324 Mo et logs 1 526. Il ne manquait que "
            "l automatisme. sauvegarde_github.py commite et pousse toutes les "
            "heures, refuse de tourner si docs ou logs se retrouvent indexes, "
            "et reprend trois fois sur l echec du 04/08 -- short read while "
            "indexing, git lisant un fichier pendant que le moteur l ecrit.",
            "Deux trous decouverts au passage. Les six lignes "
            "!xxx_api_key.txt du .gitignore protegent des fichiers qui "
            "n existent pas : la reprise apres la mort de msitrident1 ne s est "
            "donc pas faite depuis ce depot. Et les fichiers de gel, en .json, "
            "n etaient pas dans la liste blanche -- regles_gelees_v9.py etait "
            "sauvegarde, mais pas gel_v9_2026-08-11.json, c est-a-dire la "
            "reference in-sample contre laquelle le verdict du 01/09 doit etre "
            "compare. Corrige par une regle !gel_v*.json ; sept fichiers de "
            "gel sont partis au premier passage.",
        ],
    },
'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % CIBLE)
        return 1

    src, enc = lire(CIBLE)
    print("%s : %d lignes, encodage %s" % (CIBLE, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Entrees du 11/08 deja presentes -- rien a faire.")
        return 0

    for lab, ancre in (("JOURNAL = [", ANCRE_J), ("VERSION = 2", ANCRE_V),
                       ("DATE_VERSION", ANCRE_D)):
        if src.count(ancre) != 1:
            print("KO : %d occurrence(s) de l ancre %s, il en faut 1."
                  % (src.count(ancre), lab))
            return 1

    neuf = src.replace(ANCRE_J, ANCRE_J + ENTREES, 1)
    neuf = neuf.replace(ANCRE_V, NEUF_V, 1)
    neuf = neuf.replace(ANCRE_D, NEUF_D, 1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Verification de fond : le journal doit avoir gagne exactement quatre
    # entrees, et aucune ancienne ne doit avoir disparu. Un ast.parse
    # reussi ne dit que la syntaxe.
    def compte(a):
        for n in ast.walk(a):
            if isinstance(n, ast.Assign):
                for c in n.targets:
                    if isinstance(c, ast.Name) and c.id == "JOURNAL":
                        return len(n.value.elts)
        return -1

    avant, apres = compte(ast.parse(src)), compte(arbre)
    print("entrees du journal : %d -> %d" % (avant, apres))
    if apres != avant + 4:
        print("KO : quatre entrees attendues, %d ajoutee(s). Rien n a ete ecrit."
              % (apres - avant))
        return 1

    sauve = "%s.bak-%s" % (CIBLE, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    io.open(CIBLE, "w", encoding=enc).write(neuf)
    print("Sauvegarde : %s" % sauve)
    print("VERSION 2 -> 3, DATE_VERSION au 2026-08-11.")
    print()
    print("Regenere le PDF :")
    print("    python journal_pdf.py")
    print()
    print("Puis depose-le sur le Drive, dans le dossier ScalpEA. Le Drive")
    print("ne porte aujourd hui que journal_scalp_v1_20260810.pdf : la v2")
    print("existait dans le code et n y a jamais ete deposee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
