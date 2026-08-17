# -*- coding: utf-8 -*-
r"""
assembler_docs.py -- recoller les ajouts du 17/08 dans les trois
documents de reference

  python assembler_docs.py --montre
  python assembler_docs.py

CE QU IL FAIT

    La journee a produit six fragments a concatener :

        mistakes_ajout_17-08_b.md          -> mistakes.md
        mistakes_ajout_17-08_c.md          -> mistakes.md
        mistakes_ajout_17-08_d.md          -> mistakes.md
        PROTOCOLE_ajout_17-08.md           -> PROTOCOLE.md
        hypothese_H30.md                   -> HYPOTHESES.md
        hypothese_H30_annotation.md        -> HYPOTHESES.md
        hypothese_H31.md                   -> HYPOTHESES.md

    Les faire a la main, c est six occasions de se tromper d ordre, d
    en oublier un, ou de coller deux fois le meme. C est precisement le
    geste manuel qu on s interdit depuis ce matin.

L ORDRE COMPTE

    `hypothese_H30_annotation.md` n a de sens qu apres `hypothese_H30`,
    et `hypothese_H31.md` contient la RESOLUTION de cette annotation
    avant d introduire H31. L ordre est donc fixe dans ce fichier, pas
    laisse au tri alphabetique.

IL NE PEUT PAS COLLER DEUX FOIS

    Chaque fragment porte un titre distinctif. Avant d ecrire, on
    cherche ce titre dans la cible : s il y est deja, le fragment est
    saute et c est dit. Relancer l assembleur autant de fois qu on veut
    ne change rien.

IL NE CREE AUCUN FICHIER

    Si `mistakes.md` est introuvable, il ne le cree pas : il le
    signale. Creer un second `mistakes.md` a cote du vrai couperait
    l historique en deux sans que personne ne le voie -- et un
    historique coupe en silence est pire que pas d historique.

    Les trois cibles sont cherchees dans le dossier courant puis dans
    `analyse\`. Aucun autre fichier n est touche.

SAUVEGARDE

    Chaque cible modifiee est copiee en `<nom>.avant_17-08` avant
    ecriture, une seule fois.

LECTEUR SEUL SUR LE RESTE DE LA STACK. N ouvre en ecriture que
mistakes.md, PROTOCOLE.md et HYPOTHESES.md.
"""
import argparse
import io
import os
import shutil
import sys

SOURCE = os.path.join("G:", os.sep, "My Drive", "ScalpEA")

# (fragment, cible, titre qui prouve qu il est deja colle)
# L ORDRE DE CETTE LISTE EST L ORDRE DE COLLAGE. Ne pas trier.
PLAN = [
    ("mistakes_ajout_17-08_b.md", "mistakes.md",
     "## 17/08/2026 — `c > 0`"),
    ("mistakes_ajout_17-08_c.md", "mistakes.md",
     "## 17/08/2026 — un résultat significatif"),
    ("mistakes_ajout_17-08_d.md", "mistakes.md",
     "## 17/08/2026 — j'ai lu une heure"),
    ("PROTOCOLE_ajout_17-08.md", "PROTOCOLE.md",
     "## 6 bis. La branche macro est CLOSE"),
    ("hypothese_H30.md", "HYPOTHESES.md",
     "## H30 — Le NFP pousse le Dow"),
    ("hypothese_H30_annotation.md", "HYPOTHESES.md",
     "### H30 — ANNOTATION du 17/08/2026"),
    ("hypothese_H31.md", "HYPOTHESES.md",
     "## H31 — Les prix bougent ensemble"),
]

CIBLES = ("mistakes.md", "PROTOCOLE.md", "HYPOTHESES.md")


def trouve_cible(nom, dossiers):
    for d in dossiers:
        c = os.path.join(d, nom) if d else nom
        if os.path.isfile(c):
            return c
    return None


def lis(chemin):
    return io.open(chemin, encoding="utf-8", errors="replace").read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=SOURCE,
                   help="dossier des fragments")
    p.add_argument("--montre", action="store_true",
                   help="dit ce qu il ferait et n ecrit rien")
    a = p.parse_args()

    dossiers = ["", "analyse", os.path.join("..", "analyse")]
    ou = {}
    print("=" * 78)
    print("ASSEMBLAGE DES AJOUTS DU 17/08")
    print("=" * 78)
    print("  source des fragments : %s" % a.source)
    print()
    for nom in CIBLES:
        c = trouve_cible(nom, dossiers)
        ou[nom] = c
        print("  %-16s %s" % (nom, c if c else "INTROUVABLE"))
    manquantes = [n for n in CIBLES if not ou[n]]
    if manquantes:
        print()
        print("  Ces cibles sont introuvables : %s" % ", ".join(manquantes))
        print("  Elles ne seront PAS creees. Creer un second fichier a")
        print("  cote du vrai couperait l historique en deux sans que")
        print("  personne ne le voie.")
    print()

    # --- inventaire ------------------------------------------------
    print("-" * 78)
    print("  %-34s %-16s %s" % ("fragment", "cible", "etat"))
    print("-" * 78)
    a_faire = []
    for frag, cible, titre in PLAN:
        src = os.path.join(a.source, frag)
        dst = ou.get(cible)
        if not os.path.isfile(src):
            etat = "fragment absent"
        elif not dst:
            etat = "cible introuvable"
        elif titre in lis(dst):
            etat = "deja colle"
        else:
            etat = "A COLLER (%d octets)" % os.path.getsize(src)
            a_faire.append((src, dst, frag))
        print("  %-34s %-16s %s" % (frag[:34], cible, etat))
    print("-" * 78)
    print()

    if not a_faire:
        print("  Rien a faire : tout est deja en place, ou les fragments")
        print("  ne sont pas la. Relancer ce script ne change rien --")
        print("  c est voulu.")
        return 0

    if a.montre:
        print("  %d fragment(s) seraient colles. Rien n a ete ecrit."
              % len(a_faire))
        print("  Relancer sans --montre pour ecrire.")
        return 0

    # --- collage ---------------------------------------------------
    sauvees = set()
    for src, dst, frag in a_faire:
        if dst not in sauvees:
            sauv = dst + ".avant_17-08"
            if not os.path.isfile(sauv):
                shutil.copy2(dst, sauv)
                print("  sauvegarde : %s" % sauv)
            sauvees.add(dst)
        texte = lis(src)
        avant = os.path.getsize(dst)
        with io.open(dst, "a", encoding="utf-8") as f:
            if not lis(dst).endswith("\n"):
                f.write("\n")
            f.write("\n" + texte.rstrip() + "\n")
        print("  %-34s -> %s (%d -> %d octets)"
              % (frag[:34], dst, avant, os.path.getsize(dst)))

    print()
    print("%d fragment(s) colles." % len(a_faire))
    print()
    print("A VERIFIER, ET C EST RAPIDE :")
    print("  - la fin de HYPOTHESES.md doit contenir H30, puis son")
    print("    ANNOTATION, puis sa RESOLUTION, puis H31 -- dans cet")
    print("    ordre. Si l ordre est autre, un fragment avait deja ete")
    print("    colle a la main auparavant.")
    print("  - mistakes.md doit finir sur `le verdict contredit sa")
    print("    table, deuxieme fois dans la journee`.")
    print()
    print("Relancer ce script est sans effet : chaque fragment est")
    print("reconnu a son titre et saute s il est deja present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
