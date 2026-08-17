# -*- coding: utf-8 -*-
r"""
assembler_docs.py -- recoller les ajouts du 17/08 dans les trois
documents de reference, ou dire pourquoi il ne le fait pas

  python assembler_docs.py --montre
  python assembler_docs.py

TROIS FICHIERS, PAS SEPT

    La premiere version en attendait sept -- `mistakes_ajout_17-08_b`,
    `_c`, `_d`, `hypothese_H30`, `_annotation`, `H31`, plus le
    protocole. Sept pieces a emboiter dans le bon ordre pour trois
    documents, c est une source d embrouilles fabriquee de toutes
    pieces.

    La cause etait reelle -- le Drive refuse de remplacer un fichier,
    donc chaque ajout de la journee a du prendre un nom neuf -- mais
    elle n excusait pas de laisser l assemblage a la charge du
    lecteur. Les fragments sont desormais consolides a la source :

        mistakes_17-08.md      -> mistakes.md
        PROTOCOLE_17-08.md     -> PROTOCOLE.md
        HYPOTHESES_17-08.md    -> HYPOTHESES.md

    Les sept anciens fragments sont perimes. Ils restent sur le Drive
    parce qu on ne peut pas les effacer, pas parce qu ils servent.

IL CHERCHE LES CIBLES, IL NE LES DEVINE PAS

    `mistakes.md` n est pas forcement a cote du script. On descend donc
    l arborescence depuis `--racine` pour le trouver.

    ET S IL Y EN A DEUX, IL S ARRETE. Deux `mistakes.md` sur une
    machine, c est deja l historique coupe en deux ; choisir
    silencieusement l un des deux acheverait le travail. Les chemins
    sont affiches et c est a l humain de trancher, avec `--cible`.

IL NE PEUT PAS COLLER DEUX FOIS, NI A MOITIE

    Chaque fichier consolide porte plusieurs titres distinctifs. Avant
    d ecrire :

        tous les titres presents   -> deja colle, on saute
        aucun                      -> a coller
        certains seulement         -> COLLAGE PARTIEL ANTERIEUR, on
                                      refuse et on dit lesquels

    Le troisieme cas est le seul dangereux : recoller par-dessus
    dupliquerait la moitie du texte. On prefere s arreter.

IL NE CREE AUCUN FICHIER

    Si une cible est introuvable, il le dit et passe. Creer un second
    `mistakes.md` a cote du vrai couperait l historique sans que
    personne ne le voie.

LECTEUR SEUL SUR LE RESTE DE LA STACK. N ouvre en ecriture que les
trois cibles nommees ci-dessus.
"""
import argparse
import io
import os
import shutil
import sys

SOURCE = os.path.join("G:", os.sep, "My Drive", "ScalpEA")
RACINE = os.path.join("C:", os.sep, "Users", "Administrator")

# Dossiers ou il est inutile de descendre.
SAUTE = ("node_modules", ".git", "__pycache__", "AppData", "Windows",
         "Program Files", "Program Files (x86)", ".vs", "venv",
         "site-packages", "MarketDepthData", "ChartbookGroups")

# (fragment consolide, cible, titres qui prouvent qu il est colle)
PLAN = [
    ("mistakes_17-08.md", "mistakes.md",
     ["## 17/08/2026 — `c > 0`",
      "## 17/08/2026 — un résultat significatif",
      "## 17/08/2026 — j'ai lu une heure"]),
    ("PROTOCOLE_17-08.md", "PROTOCOLE.md",
     ["## 6 bis. La branche macro est CLOSE",
      "## 8. Ce que SierraChart donne"]),
    ("HYPOTHESES_17-08.md", "HYPOTHESES.md",
     ["## H30 — Le NFP pousse le Dow",
      "### H30 — ANNOTATION du 17/08/2026",
      "## H31 — Les prix bougent ensemble"]),
]


def cherche(nom, racine):
    """Tous les exemplaires de `nom` sous `racine`. TOUS, pas le
    premier : deux exemplaires est une information, pas un detail."""
    trouves = []
    for base, dossiers, fichiers in os.walk(racine):
        dossiers[:] = [d for d in dossiers
                       if d not in SAUTE and not d.startswith(".")]
        if nom in fichiers:
            trouves.append(os.path.join(base, nom))
        if len(trouves) > 8:
            break
    return trouves


def lis(chemin):
    return io.open(chemin, encoding="utf-8", errors="replace").read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=SOURCE)
    p.add_argument("--racine", default=RACINE,
                   help="ou chercher les documents cibles")
    p.add_argument("--cible", action="append", default=[],
                   help="chemin explicite d une cible, repetable ; "
                        "sert quand la recherche en trouve plusieurs")
    p.add_argument("--montre", action="store_true")
    a = p.parse_args()

    forces = {}
    for c in a.cible:
        forces[os.path.basename(c)] = c

    print("=" * 78)
    print("ASSEMBLAGE DES AJOUTS DU 17/08")
    print("=" * 78)
    print("  fragments : %s" % a.source)
    print("  recherche : %s" % a.racine)
    print()

    ou, ambigus = {}, []
    for _, cible, _ in PLAN:
        if cible in forces:
            ou[cible] = forces[cible]
            print("  %-16s %s   (impose)" % (cible, ou[cible]))
            continue
        t = cherche(cible, a.racine)
        if len(t) == 1:
            ou[cible] = t[0]
            print("  %-16s %s" % (cible, t[0]))
        elif not t:
            ou[cible] = None
            print("  %-16s INTROUVABLE sous %s" % (cible, a.racine))
        else:
            ou[cible] = None
            ambigus.append((cible, t))
            print("  %-16s %d EXEMPLAIRES :" % (cible, len(t)))
            for x in t:
                print("  %-16s   %s" % ("", x))

    if ambigus:
        print()
        print("  PLUSIEURS EXEMPLAIRES TROUVES. Rien ne sera ecrit sur")
        print("  ces cibles-la. Deux documents du meme nom sur une")
        print("  machine, c est deja un historique coupe en deux :")
        print("  choisir silencieusement l un des deux l acheverait.")
        print("  Designer le bon avec --cible \"chemin\\complet.md\".")

    print()
    print("-" * 78)
    print("  %-24s %-16s %s" % ("fragment", "cible", "etat"))
    print("-" * 78)
    a_faire, partiels = [], []
    for frag, cible, titres in PLAN:
        src = os.path.join(a.source, frag)
        dst = ou.get(cible)
        if not os.path.isfile(src):
            etat = "fragment absent"
        elif not dst:
            etat = "cible non resolue"
        else:
            t = lis(dst)
            presents = [x for x in titres if x in t]
            if len(presents) == len(titres):
                etat = "deja colle"
            elif presents:
                etat = "COLLAGE PARTIEL (%d/%d)" % (len(presents),
                                                    len(titres))
                partiels.append((frag, presents))
            else:
                etat = "A COLLER (%d octets)" % os.path.getsize(src)
                a_faire.append((src, dst, frag))
        print("  %-24s %-16s %s" % (frag[:24], cible, etat))
    print("-" * 78)

    if partiels:
        print()
        print("  COLLAGE PARTIEL DETECTE. Ces fragments sont deja la")
        print("  pour partie -- probablement colles a la main. Recoller")
        print("  par-dessus dupliquerait le reste du texte, donc on")
        print("  s arrete. Deja present :")
        for frag, presents in partiels:
            for x in presents:
                print("    %-24s %s" % (frag[:24], x))

    print()
    if not a_faire:
        print("  Rien a coller. Relancer ce script ne change rien.")
        return 0 if not (ambigus or partiels) else 1

    if a.montre:
        print("  %d fragment(s) seraient colles. Rien n a ete ecrit."
              % len(a_faire))
        print("  Relancer sans --montre pour ecrire.")
        return 0

    sauvees = set()
    for src, dst, frag in a_faire:
        if dst not in sauvees:
            sauv = dst + ".avant_17-08"
            if not os.path.isfile(sauv):
                shutil.copy2(dst, sauv)
                print("  sauvegarde : %s" % sauv)
            sauvees.add(dst)
        avant = os.path.getsize(dst)
        with io.open(dst, "a", encoding="utf-8") as f:
            if not lis(dst).endswith("\n"):
                f.write("\n")
            f.write("\n" + lis(src).rstrip() + "\n")
        print("  %-24s -> %s (%d -> %d octets)"
              % (frag[:24], dst, avant, os.path.getsize(dst)))

    print()
    print("%d fragment(s) colles." % len(a_faire))
    print()
    print("A VERIFIER :")
    print("  - HYPOTHESES.md doit finir sur H30, son ANNOTATION, sa")
    print("    RESOLUTION, puis H31 -- dans cet ordre.")
    print("  - mistakes.md doit finir sur `le verdict contredit sa")
    print("    table, deuxieme fois dans la journee`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
