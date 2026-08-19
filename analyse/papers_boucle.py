# -*- coding: utf-8 -*-
r"""
papers_boucle.py -- une passe papers complete, sans risque de recouvrement

  python papers_boucle.py          une passe : moteur puis rendu
  python papers_boucle.py --etat   ou en est la boucle, sans rien lancer

N ENVOIE AUCUN ORDRE. Il enchaine deux scripts qui n en envoient pas
non plus : papers_moteur.py (ingestion) puis papers_rendu.py (panneau).

POURQUOI UN VERROU

    Une tache toutes les cinq minutes finit toujours par se recouvrir :
    une passe plus lente que prevue, et deux instances ecrivent le meme
    journal et le meme fichier d etat en meme temps. papers_moteur
    tient un ensemble `vus` et des balances cumulees -- deux ecritures
    concurrentes donneraient des prises comptees deux fois et des
    balances fausses, sans que rien ne plante.

    Le verrou est un DOSSIER, pas un fichier : sous Windows, mkdir est
    atomique, alors que "tester puis creer" ne l est pas.

POURQUOI UN VERROU QUI EXPIRE

    Un verrou qui ne s efface jamais est pire que pas de verrou : si
    une passe meurt, la boucle s arrete pour toujours et rien ne le
    dit. Au-dela de PERIME secondes, le verrou est considere mort, et
    la passe le reprend EN LE DISANT.

CE QU IL ECRIT

    docs\papers_live\boucle.log -- une ligne par passe, horodatee, avec
    ce que le moteur a lu et pris. Le fichier est borne a MAX_LIGNES :
    un journal qui grossit sans fin sur une tache aux cinq minutes est
    un disque plein a echeance.

    Rien d autre. Le journal des papers et les panneaux sont ecrits par
    les deux scripts appeles, pas par celui-ci.
"""
import argparse
import datetime
import os
import subprocess
import sys

DOSSIER = os.path.join("docs", "papers_live")
VERROU = os.path.join(DOSSIER, "boucle.lock")
LOG = os.path.join(DOSSIER, "boucle.log")
PERIME = 900          # 15 min : trois fois la periode, large
MAX_LIGNES = 500
ETAPES = ("papers_moteur.py", "papers_rendu.py")

# Les lignes de sortie qui valent la peine d etre gardees : ce que le
# moteur a lu, ce qu il a pris, ce que le rendu a ecrit.
INTERESSANT = ("nouveaux :", "nouvelles prises", "deja vus :",
               "hors fenetre", "sans volume", "prises   :", "papers   :",
               "tickets  :", "KO :")


def maintenant():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def age_verrou():
    """Age du verrou en secondes, ou None s il n existe pas."""
    if not os.path.isdir(VERROU):
        return None
    try:
        import time
        return time.time() - os.path.getmtime(VERROU)
    except OSError:
        return None


def prend_verrou(add):
    age = age_verrou()
    if age is not None and age < PERIME:
        add("  OCCUPE : une passe tourne depuis %d s. Rien lance." % age)
        return False
    if age is not None:
        add("  Verrou perime (%d s > %d). Une passe precedente est morte"
            % (age, PERIME))
        add("  sans le liberer. Je le reprends, et je le dis.")
        try:
            os.rmdir(VERROU)
        except OSError as e:
            add("  Impossible de retirer le verrou : %s" % e)
            return False
    try:
        os.makedirs(VERROU)          # atomique : echoue si deja la
        return True
    except OSError as e:
        add("  Verrou pris par quelqu un d autre entre-temps : %s" % e)
        return False


def rend_verrou():
    try:
        os.rmdir(VERROU)
    except OSError:
        pass


def journalise(lignes):
    """Ajoute au log en le bornant. Un log non borne remplit le disque."""
    try:
        if not os.path.isdir(DOSSIER):
            os.makedirs(DOSSIER)
        vieilles = []
        if os.path.isfile(LOG):
            with open(LOG, "r", encoding="utf-8", errors="replace") as f:
                vieilles = f.read().split("\n")
        garde = (vieilles + lignes)[-MAX_LIGNES:]
        with open(LOG, "w", encoding="utf-8") as f:
            f.write("\n".join(garde))
    except OSError:
        pass          # un log qui echoue ne doit pas arreter la passe


def passe(add):
    ici = os.path.dirname(os.path.abspath(__file__)) or "."
    resume = []
    for script in ETAPES:
        che = os.path.join(ici, script)
        if not os.path.isfile(che):
            add("  ABSENT : %s -- passe interrompue." % script)
            resume.append("%s ABSENT %s" % (maintenant(), script))
            return resume
        try:
            r = subprocess.run([sys.executable, che], cwd=ici,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=600)
            sortie = r.stdout.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            add("  %s : plus de 600 s, abandonne." % script)
            resume.append("%s TIMEOUT %s" % (maintenant(), script))
            return resume
        except OSError as e:
            add("  %s : %s" % (script, e))
            resume.append("%s ERREUR %s %s" % (maintenant(), script, e))
            return resume
        retenu = [l.strip() for l in sortie.split("\n")
                  if any(m in l for m in INTERESSANT)]
        add("  %-20s code %d" % (script, r.returncode))
        for l in retenu[:6]:
            add("      %s" % l[:88])
        resume.append("%s  %-18s code=%d  %s"
                      % (maintenant(), script, r.returncode,
                         " | ".join(x[:40] for x in retenu[:3])))
    return resume


def montre_etat(add):
    age = age_verrou()
    add("  verrou : %s"
        % ("libre" if age is None
           else ("pris depuis %d s%s" % (age, " -- PERIME" if age >= PERIME
                                         else ""))))
    if os.path.isfile(LOG):
        try:
            with open(LOG, "r", encoding="utf-8", errors="replace") as f:
                lignes = [l for l in f.read().split("\n") if l.strip()]
            add("  journal de boucle : %d ligne(s), les 8 dernieres :"
                % len(lignes))
            for l in lignes[-8:]:
                add("    %s" % l[:104])
        except OSError as e:
            add("  journal illisible : %s" % e)
    else:
        add("  Aucune passe enregistree : la tache n a jamais tourne.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--etat", action="store_true",
                   help="montrer l etat sans rien lancer")
    a = p.parse_args()

    L = []
    add = L.append
    add("=" * 78)
    add("BOUCLE PAPERS -- %s" % maintenant())
    add("=" * 78)

    if a.etat:
        montre_etat(add)
        print("\n".join(L))
        return 0

    if not prend_verrou(add):
        print("\n".join(L))
        return 0
    try:
        resume = passe(add)
    finally:
        rend_verrou()          # meme si la passe leve : sinon la boucle
    journalise(resume)         # s arreterait pour de bon
    add("")
    add("  Verrou rendu. Aucun ordre envoye.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
