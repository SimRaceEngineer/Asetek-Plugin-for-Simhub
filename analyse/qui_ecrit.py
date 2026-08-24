# -*- coding: utf-8 -*-
"""
qui_ecrit.py -- qui tourne, et qui ecrit encore.

LECTURE SEULE. Il ne demarre rien, n arrete rien, n ecrit rien.
MetaTrader5 n est pas importe.

Deux questions, et il faut les deux : un processus peut tourner sans
plus rien ecrire (boucle bloquee, exception avalee), et un fichier peut
etre frais alors que son producteur vient de mourir. Croiser les deux
evite les deux erreurs.

  1. quels python tournent, avec leur ligne de commande complete ;
  2. quels fichiers de docs\\ et logs\\ ont ete ecrits recemment.

Usage :
    python "G:\\My Drive\\ScalpEA\\qui_ecrit.py"
    python "G:\\My Drive\\ScalpEA\\qui_ecrit.py" C:\\chemin\\de\\la\\stack
"""

import os
import subprocess
import sys
import time

MINUTE = 60.0

# Ce qu on s attend a voir tourner, et le fichier que chacun alimente.
# Le chemin est relatif a la racine de la stack. None = pas de fichier
# temoin connu : on ne juge alors que sur la presence du processus.
ATTENDUS = (
    ("trading_engine.py",  "le moteur",                None),
    ("papier_tf.py",       "les papers",               "docs/papier_tf/trades.jsonl"),
    ("x60_onset.py",       "x60",                      "docs/x60_onset/events.jsonl"),
    ("rafraichir_x60.py",  "rafraichissement x60",     None),
    ("panels_auto.py",     "les panneaux",             None),
    ("price_action.py",    "le panneau 8095",          None),
    ("sarkeep_gel.py",     "sarkeep M1",               None),
    ("sarkeep_m5.py",      "sarkeep M5",               None),
    ("miroir",             "le miroir",                "docs/miroir_papers.csv"),
    ("data_node_sync.py",  "la synchro du data node",  None),
)


def racine_stack(donne):
    if donne:
        return os.path.abspath(donne)
    cwd = os.getcwd()
    if os.path.basename(cwd).lower() == "docs":
        return os.path.dirname(cwd)
    if os.path.isdir(os.path.join(cwd, "docs")):
        return cwd
    d = os.path.join(os.path.expanduser("~"), "Downloads",
                     "Scalp-EA-main", "Scalp-EA-main")
    if os.path.isdir(os.path.join(d, "docs")):
        return d
    return None


def processus_python():
    """(pid, ligne_de_commande) de chaque python en cours.

    Passe par PowerShell : wmic n existe plus sur les Windows recents, et
    psutil n est pas garanti installe. Si la commande echoue on le dit,
    plutot que de rendre une liste vide qui se lirait comme "rien ne
    tourne" -- ce serait le pire des mensonges ici.
    """
    cmd = [
        "powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process -Filter "
        "\"Name='python.exe' OR Name='pythonw.exe'\" | "
        "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return None, "PowerShell injoignable : %s" % e
    if out.returncode != 0:
        err = (out.stderr or b"").decode("utf-8", "replace").strip()
        return None, "PowerShell a repondu %d : %s" % (out.returncode, err[:200])
    lignes = []
    txt = (out.stdout or b"").decode("utf-8", "replace")
    for l in txt.splitlines():
        l = l.rstrip()
        if not l.strip():
            continue
        if "\t" in l:
            pid, _sep, cl = l.partition("\t")
        else:
            pid, cl = "?", l
        lignes.append((pid.strip(), cl.strip()))
    return lignes, None


def age(sec):
    if sec < 90:
        return "%d s" % int(sec)
    if sec < 5400:
        return "%d min" % int(sec / MINUTE)
    if sec < 172800:
        return "%.1f h" % (sec / 3600.0)
    return "%.1f j" % (sec / 86400.0)


def recents(racines, combien=25):
    tous = []
    for r in racines:
        if not os.path.isdir(r):
            continue
        for base, _d, fics in os.walk(r):
            for f in fics:
                p = os.path.join(base, f)
                try:
                    tous.append((os.path.getmtime(p), p))
                except OSError:
                    pass
    tous.sort(reverse=True)
    return tous[:combien], len(tous)


def main():
    stack = racine_stack(sys.argv[1] if len(sys.argv) > 1 else None)
    if stack is None:
        print("Racine de la stack introuvable.")
        print("Relancez en donnant le chemin en argument.")
        return 1

    maintenant = time.time()
    docs = os.path.join(stack, "docs")
    logs = os.path.join(stack, "logs")

    print("=" * 72)
    print("stack : %s" % stack)
    print("heure : %s" % time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime(maintenant)))
    print("=" * 72)
    print("")

    # ---- 1. les processus -------------------------------------------
    procs, err = processus_python()
    print("-" * 72)
    print("PYTHON EN COURS")
    print("-" * 72)
    if err:
        print("IMPOSSIBLE DE SAVOIR : %s" % err)
        print("Ne lisez pas ce vide comme 'rien ne tourne'.")
        procs = []
    elif not procs:
        print("Aucun processus python. La stack est completement arretee.")
    else:
        for pid, cl in procs:
            court = cl
            if len(court) > 150:
                court = court[:147] + "..."
            print("  %-8s %s" % (pid, court))
    print("")

    joints = " ".join(cl for _p, cl in procs).lower() if procs else ""

    # ---- 2. les fichiers recents ------------------------------------
    tete, total = recents([docs, logs])
    print("-" * 72)
    print("DERNIERS FICHIERS ECRITS  (%d fichiers examines)" % total)
    print("-" * 72)
    if not tete:
        print("Aucun fichier lu. docs et logs sont-ils au bon endroit ?")
    else:
        print("%10s  %s" % ("age", "fichier"))
        for m, p in tete:
            try:
                rel = os.path.relpath(p, stack)
            except ValueError:
                rel = p
            print("%10s  %s" % (age(maintenant - m), rel))
    print("")

    # ---- 3. le croisement -------------------------------------------
    print("-" * 72)
    print("CE QUI DEVRAIT TOURNER")
    print("-" * 72)
    print("%-22s %-10s %-12s %s" % ("module", "processus", "son fichier", "verdict"))
    print("-" * 72)
    for motif, quoi, temoin in ATTENDUS:
        vivant = motif.lower() in joints
        if temoin:
            p = os.path.join(stack, *temoin.split("/"))
            if os.path.isfile(p):
                try:
                    a = maintenant - os.path.getmtime(p)
                    etat_f = age(a)
                    frais = a < 3600
                except OSError:
                    etat_f = "illisible"
                    frais = False
            else:
                etat_f = "absent"
                frais = False
        else:
            etat_f = "-"
            frais = None

        if err:
            verdict = "processus inconnu"
        elif vivant and (frais is None or frais):
            verdict = "OK"
        elif vivant and not frais:
            verdict = "TOURNE MAIS N ECRIT PLUS"
        elif not vivant and frais:
            verdict = "MORT, fichier encore frais"
        else:
            verdict = "ARRETE"
        print("%-22s %-10s %-12s %s"
              % (motif, "oui" if vivant else "non", etat_f, verdict))
    print("")
    print("Un fichier est dit frais s il a moins d une heure.")
    print("")
    print("=" * 72)
    print("Lecture seule. Rien n a ete demarre, arrete ni ecrit.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
