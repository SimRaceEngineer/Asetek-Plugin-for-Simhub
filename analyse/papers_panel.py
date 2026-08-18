# -*- coding: utf-8 -*-
r"""
papers_panel.py -- LIRE le panneau rails_trades au lieu de le deviner

  python papers_panel.py
  python papers_panel.py --racine C:\Users\Administrator

LECTEUR SEUL. N ECRIT RIEN, N EXECUTE RIEN.

    Il ouvre des .py en lecture et imprime des lignes. Il n importe
    aucun module, donc il ne peut declencher aucun effet de bord.

POURQUOI CE LECTEUR EXISTE, ET CE QU IL DIT DE MA METHODE

    J ai passe le 18/08 a faire de la retro-ingenierie sur les SORTIES
    du panneau rails_trades : chasse aux jetons, empreinte sur les
    effectifs, sept lectures candidates du regime, un ecart de 494.

    La reponse etait dans analyse/matrice_croisement.py, neuf lignes :

        def seau_churn(v):
            if v in ("CLEAN", "OK", "TRADE"): return "CLEAN"
            if v in ("CHURN", "NOISE", "NO"): return "CHURN"
            if v: return "MIXED"

    Le meme fichier a un --schema qui fait ce que papers_vocab.py a
    refait ce matin. C est la deuxieme fois cette semaine que j ecris
    un outil a cote d un outil correct qui existait deja -- la
    premiere etait onglets() dans carte_html.py, le 14/08.

    Le module qui PRODUIT le tableau s appelle rails_trades_panel.py.
    Il n est pas dans le depot ; il est sur la machine. Il detient les
    definitions que je n ai pas su reconstituer : le T/S, l etoile, le
    with/against, les pentes, et le decoupage exact des sections.

CE QU IL IMPRIME

    1. Ou il a trouve les modules du panneau.
    2. Leurs fonctions, avec la premiere ligne de leur docstring.
    3. Toute ligne qui DEFINIT un des vocabulaires cherches -- une
       comparaison ou une appartenance portant sur CLEAN, WIDENING,
       ALIGNED, leader, WITH, l etoile, T/S, les pentes.

    Pas le fichier entier : les lignes qui decident.

CE QU IL NE FAIT PAS

    Il ne conclut pas. Il rapporte des lignes de code, et c est en les
    lisant qu on saura ce que "M5 T / CLEAN" veut dire -- sans
    empreinte, sans lecture candidate, sans ecart de 494.
"""
import argparse
import io
import os
import re
import sys

# Les modules cherches, par ordre d interet.
NOMS = ["rails_trades_panel.py", "rails_trades.py", "matrice_croisement.py",
        "profils_croises.py", "magic_section.py", "churn_regime.py",
        "hlc_churn.py", "rails_panel.py"]

# Les vocabulaires dont on cherche la DEFINITION, pas l usage.
CIBLES = [
    ("regime",        r"CLEAN|MIXED|CHURN|NOISE|\bOK\b|TRADE|NEUTRAL"),
    ("largeur",       r"WIDENING|NARROWING|STEADY"),
    ("alignement",    r"ALIGNED|SPLIT|SCATTER"),
    ("convergence",   r"CONVERGING|DIVERGING|STABLE"),
    ("leader",        r"leader|laggard|divergent"),
    ("with/against",  r"WITH|AGAINST|ACCORD|CONFLIT"),
    ("etoile",        r"etoile|star|\betoi|\*\s*(YES|NO)|'\*'|\"\*\""),
    ("T / S",         r"[\"']T[\"']|[\"']S[\"']|tendance|scalp"),
    ("pentes",        r"bull\+|bull=|flat\+|flat=|flat-|bear=|bear-|pente"),
    ("ecartement",    r"TIGHT_CROSS|rails_setup"),
    ("horaire",       r"15:30|19:30|14:00|seance|session"),
]

# Une ligne DEFINIT si elle compare, teste l appartenance, ou assigne.
DEFINIT = re.compile(r"==|!=|\bin\b|\breturn\b|=[^=]|startswith|\bif\b")


def trouve(racines):
    """Rend les chemins reels des modules cherches, sans doublon."""
    vus, sortie = set(), []
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        for dossier, sousdossiers, fichiers in os.walk(racine):
            # On ne descend pas dans les dossiers qui n ont pas de code
            sousdossiers[:] = [d for d in sousdossiers
                               if d not in (".git", "__pycache__", "node_modules",
                                            "site-packages", "AppData")]
            for f in fichiers:
                if f in NOMS:
                    c = os.path.join(dossier, f)
                    r = os.path.normcase(os.path.abspath(c))
                    if r not in vus:
                        vus.add(r)
                        sortie.append(c)
    return sortie


def lire(chemin):
    try:
        return io.open(chemin, encoding="utf-8", errors="replace").read()
    except (IOError, OSError):
        return None


def fonctions(src):
    """Rend (nom, premiere ligne de docstring) pour chaque def."""
    L, lignes = [], src.split("\n")
    for i, l in enumerate(lignes):
        m = re.match(r"\s*def\s+(\w+)\s*\(", l)
        if not m:
            continue
        doc = ""
        for j in range(i + 1, min(i + 3, len(lignes))):
            s = lignes[j].strip()
            if s.startswith(('"""', "r\"\"\"", "'''")):
                doc = s.strip('"\'r ').split(".")[0][:56]
                break
        L.append((m.group(1), doc))
    return L


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", action="append", default=None,
                   help="dossier ou chercher ; repetable")
    p.add_argument("--lignes", type=int, default=8,
                   help="lignes definissantes montrees par cible")
    a = p.parse_args()

    racines = a.racine or [".", "..", os.path.join("..", "..")]

    L = []
    add = L.append
    add("=" * 78)
    add("LIRE LE PANNEAU PLUTOT QUE LE DEVINER")
    add("=" * 78)
    add("")
    add("  Lecteur seul : il ouvre des .py et imprime. Aucun import,")
    add("  aucune ecriture, aucun effet de bord possible.")
    add("")

    chemins = trouve(racines)
    if not chemins:
        add("  AUCUN module trouve. Cherches :")
        for n in NOMS:
            add("    %s" % n)
        add("")
        add("  Racines explorees : %s" % ", ".join(racines))
        add("  Relance avec --racine CHEMIN si le panneau est ailleurs.")
        print("\n".join(L))
        return 1

    add("MODULES TROUVES")
    for c in chemins:
        try:
            add("  %-58s %8d o" % (c[:58], os.path.getsize(c)))
        except OSError:
            pass
    add("")

    for c in chemins:
        src = lire(c)
        if src is None:
            add("  (illisible) %s" % c)
            continue
        add("=" * 78)
        add("%s" % c)
        add("=" * 78)

        fs = fonctions(src)
        add("  %d fonction(s) :" % len(fs))
        for nom, doc in fs[:40]:
            add("    %-28s %s" % (nom[:28], doc))
        if len(fs) > 40:
            add("    ... et %d autres" % (len(fs) - 40))
        add("")

        lignes = src.split("\n")
        for etiquette, motif in CIBLES:
            rx = re.compile(motif)
            trouvees = []
            for i, l in enumerate(lignes):
                s = l.strip()
                if not s or s.startswith("#"):
                    continue
                if rx.search(l) and DEFINIT.search(l):
                    trouvees.append((i + 1, s[:96]))
            if not trouvees:
                continue
            add("  --- %s : %d ligne(s) definissante(s)"
                % (etiquette, len(trouvees)))
            for n, s in trouvees[:a.lignes]:
                add("      %5d  %s" % (n, s))
            if len(trouvees) > a.lignes:
                add("      ... %d autres" % (len(trouvees) - a.lignes))
        add("")

    add("=" * 78)
    add("  Ce lecteur ne conclut rien. Il rapporte les lignes qui")
    add("  DECIDENT, pour que le T/S, l etoile et le with/against soient")
    add("  LUS et non reconstitues. Une definition lue vaut mieux qu une")
    add("  empreinte a 494 d ecart.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
