# -*- coding: utf-8 -*-
"""
patch_miroir_v7.py -- passe miroir_papers.py de la v6 a la v7.

  python patch_miroir_v7.py

CE QUE LA v7 AJOUTE, ET POURQUOI

  1. RELECTURE DE open_state.json AVEC REESSAI
     churn_trade_logger remplace ce fichier par os.replace. Sous
     Windows une lecture qui tombe pendant le remplacement est refusee.
     Dans la nuit du 21/08 le log du miroir n a contenu que ca, de
     02h20 a 07h19. La v7 reessaie quatre fois a 50 ms avant
     d abandonner, au lieu de perdre un tour de boucle a chaque
     collision.

  2. BATTEMENT DE COEUR
     Le 21/08 la boucle a tourne six heures sans ecrire une ligne :
     rien ne permettait de distinguer  vivante et sans rien a faire
     de  bloquee . La v7 ecrit une ligne par minute avec le nombre de
     tours, de parents lies, de miroirs, et l age du fichier d etat.

  3. CHIEN DE GARDE
     Un appel MT5 bloquant ne leve aucune exception : la boucle a l air
     vivante et n ecrit plus rien. Un fil separe signale tout tour qui
     depasse 30 s. Il ne tue rien, il nomme.

  4. PLANCHER DE NIVEAU DE MARGE  --  NIVEAU_MINI = 300 %
     La regle des 25 % de marge libre ne bornait pas le cumul : un
     miroir US30 a 0,86 lot coute environ 220 EUR quand la marge libre
     en fait 15 000, donc elle ne mordait jamais et laissait ouvrir les
     60 miroirs. A 60 miroirs le niveau de marge tombe vers 130 %.
     Le plancher refuse tout ordre dont le niveau PROJETE passerait
     sous 300 %, ce qui plafonne en pratique vers 25 miroirs.

Le script verifie l ancienne version avant d ecrire, garde une copie
sous miroir_papers.v6.py, et relit le resultat avec ast.parse. Si une
seule ancre manque, il n ecrit rien du tout.
"""
import ast
import io
import os
import shutil
import sys

CIBLE = "miroir_papers.py"

PAIRES = []


def paire(avant, apres):
    PAIRES.append((avant, apres))


# -- 1. threading ---------------------------------------------------------
paire("""import sys
import time
""", """import sys
import threading
import time
""")

# -- 2. plancher de niveau de marge --------------------------------------
paire("""MARGE_MAXI = 0.25
""", """MARGE_MAXI = 0.25

# Plancher de NIVEAU de marge, verifie sur la position PROJETEE.
# MARGE_MAXI seul ne borne pas le cumul : chaque ordre du miroir ne
# coute que ~220 EUR quand la marge libre en fait 15 000, donc la regle
# des 25 % ne mord jamais et laisse ouvrir les 60 miroirs. Soixante
# miroirs au lot du parent, c est le niveau de marge qui s effondre
# vers 130 %, pas la marge libre qui manque. Ce plancher-ci mord.
NIVEAU_MINI = 300.0     # en %, 0 pour desactiver
""")

# -- 3. constantes de surveillance ---------------------------------------
paire("""MAX_MIROIRS = 60
POLL_SEC = 0.5
""", """MAX_MIROIRS = 60
POLL_SEC = 0.5

# Surveillance. Le 21/08 la boucle a tourne six heures sans ecrire une
# ligne : impossible de distinguer  vivante et sans rien a faire  de
# bloquee dans un appel MT5. Un battement periodique tranche, et le
# chien de garde nomme le blocage au lieu de laisser un silence.
BATTEMENT_SEC = 60.0    # une ligne de vie, meme quand rien ne bouge
TOUR_LENT = 2.0         # au-dela, le tour est signale
TOUR_BLOQUE = 30.0      # au-dela, l appel en cours ne rend pas la main
RELIRE_ESSAIS = 4       # open_state.json est remplace atomiquement
RELIRE_PAUSE = 0.05     # par l ecrivain : une lecture peut tomber dessus
""")

# -- 4. lecture avec reessai, battement, chien de garde ------------------
paire('''def lit_open(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            d = json.load(f)
        return {int(k): v for k, v in d.items()}, None
    except FileNotFoundError:
        return {}, None
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
''', '''def lit_open(chemin):
    """Lit l etat des trades ouverts, en reessayant.

    L ecrivain (churn_trade_logger._save_open) remplace ce fichier par
    os.replace. Sous Windows une lecture qui tombe pendant le
    remplacement est refusee -- PermissionError -- et une lecture qui
    tombe pendant l ecriture du temporaire voit un JSON tronque. Les
    deux sont normales et durent quelques millisecondes. Les traiter
    comme des pannes coutait un tour de boucle a chaque collision :
    dans la nuit du 21/08 le log n a rien contenu d autre.
    """
    dernier = None
    for _ in range(RELIRE_ESSAIS):
        try:
            with open(chemin, encoding="utf-8") as f:
                d = json.load(f)
            return {int(k): v for k, v in d.items()}, None
        except FileNotFoundError:
            return {}, None
        except (PermissionError, OSError, ValueError) as e:
            dernier = e
            time.sleep(RELIRE_PAUSE)
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)
    return None, "%s apres %d essais : %s" % (type(dernier).__name__,
                                              RELIRE_ESSAIS, dernier)


# -- surveillance de la boucle -------------------------------------------
VEILLE = {"debut": None}


def demarre_chien():
    """Signale un tour qui ne rend pas la main. Il ne tue rien.

    Un appel MT5 bloquant ne leve aucune exception : la boucle a l air
    vivante et n ecrit plus rien. Ce fil le nomme.
    """
    def boucle():
        while True:
            time.sleep(5.0)
            t = VEILLE.get("debut")
            if t is not None and (time.time() - t) > TOUR_BLOQUE:
                dit("  TOUR BLOQUE depuis %.0f s -- appel qui ne rend pas"
                    " la main (MT5 ? fichier ?)" % (time.time() - t))
                VEILLE["debut"] = time.time()
    threading.Thread(target=boucle, daemon=True).start()


def battement(m, n_tours, secondes):
    """Une ligne qui prouve que la boucle tourne, meme sans rien a faire."""
    miroirs = sum(len(v) for v in getattr(m, "liens", {}).values())
    try:
        age = time.time() - os.path.getmtime(m.chemin)
        vieux = "%.0f s" % age
    except OSError:
        vieux = "?"
    return ("battement : %d tour(s) en %.0f s, %d parent(s) lie(s),"
            " %d miroir(s), etat vieux de %s"
            % (n_tours, secondes, len(getattr(m, "liens", {})),
               miroirs, vieux))
''')

# -- 5. le plancher dans le controle de marge ----------------------------
paire('''    if besoin > libre * MARGE_MAXI:
        return False, ("besoin %.2f > %.0f %% de %.2f libre"
                       % (besoin, MARGE_MAXI * 100, libre))
    return True, None''', '''    if besoin > libre * MARGE_MAXI:
        return False, ("besoin %.2f > %.0f %% de %.2f libre"
                       % (besoin, MARGE_MAXI * 100, libre))
    if NIVEAU_MINI:
        equite = float(getattr(ai, "equity", 0) or 0)
        marge = float(getattr(ai, "margin", 0) or 0)
        if equite and (marge + besoin) > 0:
            projete = 100.0 * equite / (marge + besoin)
            if projete < NIVEAU_MINI:
                return False, ("niveau de marge projete %.0f %% < %.0f %%"
                               % (projete, NIVEAU_MINI))
    return True, None''')

# -- 6. la boucle : minuterie, battement, chien --------------------------
paire(r'''            while True:
                try:
                    m.tour()
                except Exception:
                    dit("  tour en erreur :\n%s" % traceback.format_exc())
                taille_journal()
                time.sleep(POLL_SEC)''', r'''            demarre_chien()
            n_tours = 0
            t_battement = time.time()
            while True:
                t0 = time.time()
                VEILLE["debut"] = t0
                try:
                    m.tour()
                except Exception:
                    dit("  tour en erreur :\n%s" % traceback.format_exc())
                VEILLE["debut"] = None
                duree = time.time() - t0
                n_tours += 1
                if duree > TOUR_LENT:
                    dit("  tour lent : %.1f s" % duree)
                ecoule = time.time() - t_battement
                if ecoule >= BATTEMENT_SEC:
                    dit(battement(m, n_tours, ecoule))
                    n_tours = 0
                    t_battement = time.time()
                taille_journal()
                time.sleep(POLL_SEC)''')

# -- 7. le rappel affiche a l armement ------------------------------------
paire('''    print("  refus au-dela de %.0f %% de la marge libre, avant chaque ordre."
          % (MARGE_MAXI * 100))''', '''    print("  refus au-dela de %.0f %% de la marge libre, avant chaque ordre."
          % (MARGE_MAXI * 100))
    if NIVEAU_MINI:
        print("  refus si le niveau de marge projete tombe sous %.0f %%."
              % NIVEAU_MINI)''')


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        print("Repertoire courant : %s" % os.getcwd())
        return 1
    s = io.open(CIBLE, encoding="utf-8").read()
    if "NIVEAU_MINI" in s and "demarre_chien" in s:
        print("Deja en v7 -- rien a faire.")
        return 0
    manque = [i for i, (av, _ap) in enumerate(PAIRES, 1) if s.count(av) != 1]
    if manque:
        print("KO : %d ancre(s) introuvable(s) ou ambigue(s) : %s"
              % (len(manque), ", ".join(str(i) for i in manque)))
        print("Le fichier n est pas la v6 attendue. RIEN n a ete ecrit.")
        print("Reprends miroir_papers_v6.py sur le Drive avant de patcher.")
        return 1
    for av, ap in PAIRES:
        s = s.replace(av, ap, 1)
    try:
        ast.parse(s)
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (%s). RIEN n a ete ecrit." % e)
        return 1
    shutil.copy2(CIBLE, "miroir_papers.v6.py")
    io.open(CIBLE, "w", encoding="utf-8", newline="\n").write(s)
    print("v7 ecrite : %d octets, %d hunk(s) appliques."
          % (len(s.encode("utf-8")), len(PAIRES)))
    print("Copie de secours : miroir_papers.v6.py")
    print("")
    print("Il reste a RELANCER le miroir pour que la v7 prenne effet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
