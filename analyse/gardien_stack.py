# -*- coding: utf-8 -*-
"""
gardien_stack.py -- la stack tourne quand elle doit, et seulement alors.

UN SEUL POINT D ENTREE. Peu importe comment la stack a ete demarree, ce
script verifie l ensemble complet et ne lance QUE ce qui manque. Il est
donc rejouable sans risque : deux passages d affilee ne creent jamais de
doublon, contrairement a un .bat qui relance tout aveuglement.

CE QU IL GARANTIT

    le moteur          trading_engine.py, via START_TRADING_STACK_V3.bat
    les observateurs   papier_tf, x60_onset, rafraichir_x60, panels_auto
    le miroir          miroir_papers.py

    Le miroir n a jamais figure dans demarrage_quotidien.cmd : il mourait
    a chaque redemarrage de 20:05 et ne revenait pas. C est pour ca qu il
    n avait plus rien ecrit depuis le 21/08.

LA FENETRE

    lundi 07:50  ->  vendredi 20:00, heure locale.

    En dehors, il ne lance rien : marches fermes, une relance ne produit
    que du bruit et de l electricite. --weekend arrete la stack et, si on
    le lui demande, met la machine en veille S3 -- l hibernation etant
    interdite ici par le service Guardian.

MODES

    (rien)        etat des lieux. Ne lance rien, n arrete rien.
    --agir        lance ce qui manque, si on est dans la fenetre.
    --weekend     arrete la stack (hors fenetre uniquement).
    --avec-veille  avec --weekend : met la machine en veille S3.
    --miroir-inerte  lance le miroir en --tourner au lieu de --armer.
    --hors-fenetre   force l action meme hors fenetre. A la main seulement.

LE MIROIR ENVOIE DE VRAIS ORDRES

    Par defaut le miroir est lance avec --armer : il passe des ordres
    reels avec les magics paper, pour mesurer ce que le papier ne peut
    pas voir -- latence, prix obtenu, spread paye, slippage. Sur un
    compte demo c est le but. --miroir-inerte le passe en --tourner :
    il journalise et n envoie rien, mais ne mesure alors plus rien de
    l execution.

CE QU IL NE FAIT JAMAIS

    Tuer python par son nom. Les arrets se font sur des PID identifies
    un par un, dont la ligne de commande correspond a un module connu.

Usage :
    python "G:\\Mon Drive\\ScalpEA\\gardien_stack.py" C:\\SVPS\\Scalp-EA-main
    python "G:\\Mon Drive\\ScalpEA\\gardien_stack.py" C:\\SVPS\\Scalp-EA-main --agir
    python "G:\\Mon Drive\\ScalpEA\\gardien_stack.py" C:\\SVPS\\Scalp-EA-main --weekend --avec-veille
"""

import os
import subprocess
import sys
import time

LANCEUR = "START_TRADING_STACK_V3.bat"
MOTEUR = "trading_engine.py"

# (etiquette, motif cherche dans la ligne de commande, arguments)
OBSERVATEURS = (
    ("papers",      "papier_tf.py",      ("-u", "papier_tf.py", "--loop")),
    ("x60",         "x60_onset.py",      ("-u", "x60_onset.py", "--loop")),
    ("x60 refresh", "rafraichir_x60.py", ("-u", "rafraichir_x60.py")),
    ("panneaux",    "panels_auto.py",    ("-u", "panels_auto.py",
                                          "--dest", "panels")),
)

MIROIR_MOTIF = "miroir_papers.py"

# Le moteur est considere en defaut si son journal du jour n a pas bouge
# depuis ce delai. Un processus vivant qui n ecrit plus est en panne.
SILENCE_MAX = 600.0     # 10 minutes

FENETRE = "lundi 07:50 -> vendredi 20:00"


def journalise(racine, texte):
    """Ecrit dans logs\\gardien.log. Une action non tracee n a pas eu lieu."""
    ligne = "%s | %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), texte)
    print(ligne)
    d = os.path.join(racine, "logs")
    try:
        if not os.path.isdir(d):
            os.makedirs(d)
        with open(os.path.join(d, "gardien.log"), "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except OSError:
        pass


def processus():
    """[(pid, ligne_de_commande)] des python en cours, ou None si inconnu."""
    cmd = [
        "powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process -Filter "
        "\"Name='python.exe' OR Name='pythonw.exe'\" | "
        "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=90)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    res = []
    for l in (out.stdout or b"").decode("utf-8", "replace").splitlines():
        if "\t" in l:
            pid, _s, cl = l.partition("\t")
            try:
                res.append((int(pid.strip()), cl.strip()))
            except ValueError:
                pass
    return res


def trouve(procs, motif):
    m = motif.lower()
    return [(p, c) for p, c in procs if m in c.lower()]


def dans_la_fenetre(t=None):
    """lundi 07:50 -> vendredi 20:00. Renvoie (bool, explication)."""
    t = t or time.localtime()
    jour = t.tm_wday            # 0 = lundi
    minutes = t.tm_hour * 60 + t.tm_min
    if jour == 0:
        ok = minutes >= 7 * 60 + 50
        return ok, ("lundi, apres 07:50" if ok else "lundi, avant 07:50")
    if 1 <= jour <= 3:
        return True, "mardi a jeudi"
    if jour == 4:
        ok = minutes < 20 * 60
        return ok, ("vendredi, avant 20:00" if ok else "vendredi, apres 20:00")
    return False, "week-end"


def age_journal(racine):
    """Age en secondes du journal du moteur, ou None s il n existe pas."""
    nom = "trading_engine_%s.log" % time.strftime("%Y%m%d")
    p = os.path.join(racine, "logs", nom)
    try:
        return time.time() - os.path.getmtime(p)
    except OSError:
        return None


def demarre(racine, py, args, cache=True):
    """Lance un python detache. Renvoie le PID, ou None."""
    cmd = [py] + list(args)
    kw = {"cwd": racine, "close_fds": True}
    if os.name == "nt":
        kw["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0) |
                               getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        if cache:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0          # SW_HIDE
            kw["startupinfo"] = si
    try:
        p = subprocess.Popen(cmd, **kw)
        return p.pid
    except (OSError, ValueError) as e:
        return "erreur : %s" % e


def arrete(pids):
    """Arrete des PID nommement identifies. Jamais par nom d image."""
    if not pids:
        return True
    liste = ",".join(str(p) for p in pids)
    cmd = ["powershell", "-NoProfile", "-Command",
           "Stop-Process -Id %s -Force -ErrorAction SilentlyContinue" % liste]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def etat(racine, procs):
    """Rend la liste (etiquette, motif, [pids]) de tout ce qu on surveille."""
    lignes = []
    lignes.append(("moteur", MOTEUR,
                   [p for p, c in trouve(procs, MOTEUR)
                    if "stall_sniper" not in c.lower()]))
    for etiq, motif, _a in OBSERVATEURS:
        lignes.append((etiq, motif, [p for p, _c in trouve(procs, motif)]))
    lignes.append(("miroir", MIROIR_MOTIF,
                   [p for p, _c in trouve(procs, MIROIR_MOTIF)]))
    return lignes


def main():
    args = list(sys.argv[1:])
    agir = "--agir" in args
    weekend = "--weekend" in args
    veille = "--avec-veille" in args
    inerte = "--miroir-inerte" in args
    force = "--hors-fenetre" in args
    args = [a for a in args if not a.startswith("--")]
    racine = os.path.abspath(args[0]) if args else os.getcwd()

    if not os.path.isdir(racine):
        print("Ce chemin n est pas un dossier : %s" % racine)
        return 1
    if not os.path.isfile(os.path.join(racine, LANCEUR)):
        print("%s introuvable dans %s" % (LANCEUR, racine))
        print("Mauvaise racine ?")
        return 1

    py = os.path.abspath(sys.executable)
    ouvert, pourquoi = dans_la_fenetre()

    print("=" * 72)
    print("racine  : %s" % racine)
    print("heure   : %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("fenetre : %s  ->  %s (%s)"
          % (FENETRE, "OUVERTE" if ouvert else "FERMEE", pourquoi))
    print("=" * 72)
    print("")

    procs = processus()
    if procs is None:
        journalise(racine, "ABANDON : impossible de lister les processus.")
        print("Ne pas confondre avec 'rien ne tourne'. Aucune action prise.")
        return 1

    lignes = etat(racine, procs)
    silence = age_journal(racine)

    print("%-14s %-22s %s" % ("quoi", "module", "pid(s)"))
    print("-" * 72)
    for etiq, motif, pids in lignes:
        if not pids:
            v = "ABSENT"
        elif len(pids) > 1:
            v = "%s   DOUBLON x%d" % (", ".join(str(p) for p in pids), len(pids))
        else:
            v = str(pids[0])
        print("%-14s %-22s %s" % (etiq, motif, v))
    print("-" * 72)
    if silence is None:
        print("journal du moteur : absent")
    else:
        print("journal du moteur : ecrit il y a %d s" % int(silence))
    print("")

    manquants = [(e, m) for e, m, p in lignes if not p]
    doublons = [(e, p) for e, _m, p in lignes if len(p) > 1]
    moteur_pids = lignes[0][2]
    moteur_muet = (bool(moteur_pids) and silence is not None
                   and silence > SILENCE_MAX)

    if moteur_muet:
        print("Le moteur tourne mais son journal est muet depuis %d s."
              % int(silence))
        print("Un processus vivant qui n ecrit plus est en panne.")
        print("")

    # ---- week-end ---------------------------------------------------
    if weekend:
        if ouvert and not force:
            journalise(racine, "WEEK-END refuse : la fenetre est ouverte (%s)."
                       % pourquoi)
            print("Rien n a ete arrete. --hors-fenetre pour forcer.")
            return 0
        a_tuer = []
        for _e, _m, pids in lignes:
            a_tuer.extend(pids)
        if a_tuer:
            journalise(racine, "WEEK-END : arret de %d processus (%s)."
                       % (len(a_tuer), ",".join(str(p) for p in a_tuer)))
            arrete(a_tuer)
        else:
            journalise(racine, "WEEK-END : rien ne tournait.")
        if veille:
            # Veille S3 et non hibernation : sur cette machine le service
            # Guardian (securite par virtualisation) desactive la mise en
            # veille prolongee, et on ne desarme pas une protection
            # systeme pour economiser du courant. SetSuspendState bascule
            # en S3 des lors que l hibernation est indisponible, et les
            # minuteurs de reveil fonctionnent depuis S3.
            journalise(racine, "WEEK-END : mise en veille S3.")
            try:
                subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState",
                                "0,1,0"], timeout=60)
            except (OSError, subprocess.SubprocessError) as e:
                journalise(racine, "veille impossible : %s" % e)
        return 0

    # ---- etat seul --------------------------------------------------
    if not agir:
        if doublons:
            print("DOUBLONS a resoudre a la main :")
            for e, p in doublons:
                print("   %s : %s" % (e, ", ".join(str(x) for x in p)))
            print("")
        print("=" * 72)
        if manquants:
            print("MANQUE : %s" % ", ".join(e for e, _m in manquants))
        else:
            print("Tout est en place.")
        print("Etat des lieux seulement. Rien n a ete lance ni arrete.")
        print("Relancez avec --agir pour que le gardien intervienne.")
        print("=" * 72)
        return 0

    # ---- action -----------------------------------------------------
    if not ouvert and not force:
        journalise(racine, "AGIR refuse : hors fenetre (%s)." % pourquoi)
        print("Marches fermes. Relancer ne produirait que du bruit.")
        return 0

    fait = []

    # Le moteur passe par son propre lanceur : il porte le garde-fou
    # single-instance et toute la sequence de nettoyage. On ne
    # reimplemente pas ce qui existe.
    if not moteur_pids or moteur_muet:
        raison = "absent" if not moteur_pids else "muet depuis %ds" % int(silence)
        journalise(racine, "MOTEUR %s -> appel de %s" % (raison, LANCEUR))
        try:
            subprocess.Popen([os.path.join(racine, LANCEUR)],
                             cwd=racine, close_fds=True)
            fait.append("moteur relance par le lanceur")
        except OSError as e:
            journalise(racine, "echec du lanceur : %s" % e)
        # Le lanceur tue tous les python puis remonte la stack : inutile
        # de lancer les observateurs maintenant, ils seraient tues. Le
        # prochain passage du gardien s en chargera.
        print("")
        print("Le lanceur va tuer puis relancer les processus.")
        print("Les observateurs et le miroir seront verifies au prochain")
        print("passage du gardien, une fois le moteur remonte.")
        journalise(racine, "resultat : %s" % " ; ".join(fait or ["rien"]))
        return 0

    for etiq, motif, arguments in OBSERVATEURS:
        if trouve(procs, motif):
            continue
        pid = demarre(racine, py, arguments)
        journalise(racine, "%s absent -> lance (pid %s)" % (etiq, pid))
        fait.append("%s lance" % etiq)

    if not trouve(procs, MIROIR_MOTIF):
        mode = "--tourner" if inerte else "--armer"
        pid = demarre(racine, py, ("-u", "miroir_papers.py", mode))
        journalise(racine, "miroir absent -> lance en %s (pid %s)" % (mode, pid))
        fait.append("miroir lance en %s" % mode)

    print("")
    print("=" * 72)
    if fait:
        print("ACTIONS : %s" % " ; ".join(fait))
    else:
        print("Rien a faire, tout etait deja en place.")
    print("=" * 72)
    journalise(racine, "resultat : %s" % " ; ".join(fait or ["rien a faire"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
