# -*- coding: utf-8 -*-
"""
sauvegarde_github.py -- pousser le code du VPS vers scalpea-vps, tout seul

  python sauvegarde_github.py                 # sauvegarde
  python sauvegarde_github.py --essai         # dit ce qu il ferait, n ecrit rien
  python sauvegarde_github.py --installer     # imprime la tache planifiee horaire

CE QU IL SAUVEGARDE
    Le CODE, et rien d autre. Le .gitignore du depot fonctionne en liste
    blanche -- tout est ignore, seules certaines extensions sont
    reautorisees -- et c est la bonne facon de faire ici : docs/ pese
    7 324 Mo et logs/ 1 526 Mo, contre 15,7 Mo de Python. Un depot qui les
    avalerait serait impossible a cloner et le push echouerait.

LES CLES API SONT SAUVEGARDEES, ET C EST VOULU
    Le .gitignore contient, sous la section "secrets" :

        !deepseek_api_key.txt
        !nvidia_api_key.txt
        ...

    En syntaxe gitignore, "!" ANNULE l ignorance : ces lignes font ENTRER
    les cles dans le depot. J avais d abord lu ca comme une inversion de
    logique. C est un choix delibere : a la mort de msitrident1, disposer
    des cles dans la copie a permis de tout relancer. Une sauvegarde qui
    exclut ce qu il faut pour redemarrer n en est pas une.

    Ce script ne touche donc PAS au .gitignore, et ne bloque pas sur la
    presence des cles. Il se contente de la journaliser a chaque passage,
    pour que ce soit un fait connu et non un oubli.

    LA CONDITION, ET ELLE EST LA SEULE : le depot doit rester PRIVE. A
    verifier une fois, en anonyme -- 404 signifie prive :

        Invoke-RestMethod "https://api.github.com/repos/SimRaceEngineer/scalpea-vps"

CE QU IL REFUSE, EN REVANCHE
    Que docs/, logs/ ou __pycache__/ se retrouvent indexes. Si ca arrive,
    le .gitignore ne joue plus son role, et pousser 7 Go casserait le depot
    pour de bon. Dans ce cas il annule l indexation et s arrete.

L ECHEC DU 04/08, ET POURQUOI ON REESSAIE
    "short read while indexing" : git lisait un fichier pendant que le
    moteur l ecrivait, et il abandonne TOUT au premier fichier de ce type.
    La liste blanche a supprime la cause principale -- les fichiers d etat
    vivants sont en .json, donc ignores -- mais un .py peut encore etre
    reecrit par un patch au mauvais moment. D ou trois tentatives espacees.

CE QU IL NE FAIT JAMAIS
    Pas de --force, pas de reecriture d historique, pas de suppression.
    En cas de doute il s arrete et le dit dans le journal.
"""
import argparse
import io
import os
import subprocess
import sys
import time
from datetime import datetime

JOURNAL = "sauvegarde_github.log"
# Chemins qui ne doivent JAMAIS etre indexes. Si l un apparait, le
# .gitignore a ete casse et on prefere ne rien pousser.
INTERDITS = ("docs/", "logs/", "__pycache__/", "regime_events_logs/",
             "Common/Files/", "claude_backup/", "OrderflowExport/",
             "ScalpExport/", ".venv/", "venv/", "narratives_logs/")
ESSAIS_ADD = 3
ATTENTES_PUSH = (2, 4, 8, 16)
# Au-dela, quelque chose ne va pas : on prefere le signaler que pousser
# des milliers de fichiers sans savoir pourquoi.
ALERTE_NB = 400


def dire(msg):
    ligne = "%s  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(ligne, flush=True)
    try:
        with io.open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except Exception:
        pass


def git(*args):
    """(code de retour, sortie). Jamais d exception : on veut le message."""
    try:
        p = subprocess.Popen(("git",) + args, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        out, _ = p.communicate()
        return p.returncode, out.decode("utf-8", "replace").strip()
    except OSError as e:
        return 127, "git introuvable : %s" % e


def cles_suivies():
    """Fichiers de cle suivis par git. Attendu et voulu -- on journalise."""
    code, out = git("ls-files")
    if code != 0:
        return None
    return [f.strip() for f in out.split("\n")
            if f.strip() and "api_key" in os.path.basename(f).lower()]


def indexe_interdit():
    """Chemins interdits presents dans l index. Vide = tout va bien."""
    code, out = git("diff", "--cached", "--name-only")
    if code != 0 or not out:
        return []
    mauvais = []
    for l in out.split("\n"):
        p = l.strip().replace("\\", "/")
        if any(p.startswith(x) or ("/" + x) in p for x in INTERDITS):
            mauvais.append(p)
    return mauvais


def ajouter():
    """git add -A, avec reprise sur l echec transitoire du 04/08."""
    for n in range(1, ESSAIS_ADD + 1):
        code, out = git("add", "-A")
        if code == 0:
            return True
        dire("  add tentative %d/%d : %s" % (n, ESSAIS_ADD, out.split("\n")[0]))
        if n < ESSAIS_ADD:
            time.sleep(3 * n)
    return False


def pousser(branche):
    dernier = ""
    for i, att in enumerate((0,) + ATTENTES_PUSH):
        if att:
            dire("  reprise du push dans %ds" % att)
            time.sleep(att)
        code, dernier = git("push", "-u", "origin", branche)
        if code == 0:
            return True, dernier
        # Un refus d authentification ou de droits ne se resout pas en
        # reessayant : on s arrete tout de suite plutot que d attendre 30s.
        for motif in ("403", "denied", "authentication", "not authorized",
                      "permission"):
            if motif in dernier.lower():
                return False, dernier
        dire("  push tentative %d : %s" % (i + 1, dernier.split("\n")[0]))
    return False, dernier


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--essai", action="store_true",
                   help="dit ce qu il ferait sans rien indexer ni pousser")
    p.add_argument("--installer", action="store_true",
                   help="imprime la tache planifiee horaire et sort")
    a = p.parse_args()

    if a.installer:
        return installer()

    dire("=" * 62)
    dire("SAUVEGARDE %s" % ("(essai)" if a.essai else ""))

    code, out = git("rev-parse", "--is-inside-work-tree")
    if code != 0 or out != "true":
        dire("KO : pas un depot git ici (%s)" % os.getcwd())
        return 1

    # symbolic-ref plutot que rev-parse HEAD : ce dernier echoue sur un
    # depot sans aucun commit, cas qu on rencontrera si la sauvegarde est
    # un jour installee sur une machine neuve.
    code, branche = git("symbolic-ref", "--short", "HEAD")
    if code != 0:
        code, branche = git("rev-parse", "--abbrev-ref", "HEAD")
    if code != 0 or not branche:
        dire("KO : branche courante illisible : %s" % branche.split("\n")[0])
        return 1
    dire("branche : %s" % branche)

    # ---- les cles : voulues, donc journalisees et non bloquantes
    cles = cles_suivies()
    if cles is None:
        dire("KO : git ls-files a echoue.")
        return 1
    if cles:
        dire("%d cle(s) API dans le depot, volontairement : %s"
             % (len(cles), ", ".join(os.path.basename(c) for c in cles)))
        dire("  suppose que scalpea-vps est PRIVE. A verifier une fois.")

    # ---- indexation
    if a.essai:
        code, out = git("status", "--short")
        lignes = [l for l in out.split("\n") if l.strip()] if out else []
        dire("%d fichier(s) modifie(s) ou non suivi(s)" % len(lignes))
        for l in lignes[:20]:
            dire("    %s" % l)
        if len(lignes) > 20:
            dire("    ... et %d de plus" % (len(lignes) - 20))
        dire("--essai : rien n a ete indexe, commite ni pousse.")
        return 0

    if not ajouter():
        dire("KO : git add a echoue %d fois. Rien n a ete commite." % ESSAIS_ADD)
        return 1

    mauvais = indexe_interdit()
    if mauvais:
        dire("*** ARRET : des chemins interdits sont indexes ***")
        for m in mauvais[:10]:
            dire("    %s" % m)
        if len(mauvais) > 10:
            dire("    ... et %d de plus" % (len(mauvais) - 10))
        dire("Le .gitignore ne joue plus son role. On ne pousse pas 7 Go.")
        git("reset")
        return 3

    code, out = git("diff", "--cached", "--name-only")
    fichiers = [l for l in out.split("\n") if l.strip()] if out else []
    if not fichiers:
        dire("rien de nouveau -- pas de commit.")
        return 0
    dire("%d fichier(s) a sauvegarder" % len(fichiers))
    if len(fichiers) > ALERTE_NB:
        dire("  (inhabituel : plus de %d fichiers. A regarder si ca se"
             " reproduit.)" % ALERTE_NB)

    msg = "sauvegarde VPS %s -- %d fichier(s)" % (
        datetime.now().strftime("%Y-%m-%d %H:%M"), len(fichiers))
    code, out = git("commit", "-m", msg)
    if code != 0:
        dire("KO : commit refuse : %s" % out.split("\n")[0])
        return 1
    code, court = git("rev-parse", "--short", "HEAD")
    dire("commit %s" % court)

    ok, out = pousser(branche)
    if not ok:
        dire("KO : push refuse.")
        for l in out.split("\n")[:6]:
            dire("    %s" % l)
        dire("Le commit local est fait : il partira au prochain passage.")
        return 4
    dire("pousse sur origin/%s -- sauvegarde faite." % branche)
    return 0


# -------------------------------------------------------- tache planifiee
def installer():
    """Imprime la commande. On ne cree pas la tache dans le dos de l usager."""
    ici = os.path.abspath(os.getcwd())
    py = sys.executable
    print("Pour une sauvegarde toutes les heures, colle ceci dans")
    print("PowerShell EN ADMINISTRATEUR :")
    print()
    print('$a = New-ScheduledTaskAction -Execute "%s" `' % py)
    print('       -Argument "sauvegarde_github.py" -WorkingDirectory "%s"' % ici)
    print('$t = New-ScheduledTaskTrigger -Once -At (Get-Date) `')
    print('       -RepetitionInterval (New-TimeSpan -Hours 1)')
    print('$s = New-ScheduledTaskSettingsSet -StartWhenAvailable `')
    print('       -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 20)')
    print('Register-ScheduledTask -TaskName "ScalpEA-sauvegarde-github" `')
    print('       -Action $a -Trigger $t -Settings $s -RunLevel Highest -Force')
    print()
    print("Pour verifier ensuite :")
    print('  Get-ScheduledTaskInfo -TaskName "ScalpEA-sauvegarde-github" |')
    print('    Select-Object LastRunTime, LastTaskResult, NextRunTime')
    print()
    print("LastTaskResult vaut 0 quand tout va bien.")
    print("  1 = probleme git    3 = le .gitignore ne joue plus son role")
    print("  4 = push refuse (le commit local est fait, il partira apres)")
    print()
    print("Le journal s ecrit dans %s" % os.path.join(ici, JOURNAL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
