# -*- coding: utf-8 -*-
r"""
papers_extrait.py -- sortir TELLES QUELLES les fonctions qui decident

  python papers_extrait.py
  python papers_extrait.py --fonction _tf_tight --fonction _sess

LECTEUR SEUL. N ECRIT RIEN, N IMPORTE RIEN.

CE QU IL FAIT

    papers_panel.py a montre OU sont les definitions. Celui-ci les
    SORT, corps complet, pour qu elles soient recopiees sans etre
    reformulees. Une definition paraphrasee est une definition
    devinee.

CE QUI EST CHERCHE, ET POURQUOI

    _tf_tight     le T / S / W. Ligne 184-185 de rails_trades_panel :
                  S = rails a cheval sur 50, sinon T ou W selon le
                  spread. Il manque la valeur de TIGHT_SPREAD.

    _vs_pack      le WITH / AGAINST. Ligne 801 : WITH si le sens du
                  trade egale le maj_dir du consensus. Le champ
                  maj_dir est dans les tickets, donc c est calculable.

    _sess         EUR / US, coupe a 14h Paris. C est la dimension qui
                  manquait a mon empreinte : je comptais sur ALL, l
                  export donne une colonne de session.

    _tf_sig       la signature 'M1+M3' des accords multi-unites.

    _leader_sig   la config leader a l entree.

    Plus toute constante en MAJUSCULES du genre TIGHT_SPREAD, dont la
    VALEUR decide du T contre le W.

CE QU IL NE FAIT PAS

    Il ne conclut pas et ne recopie pas dans un autre fichier. Il
    imprime du code source, a lire.
"""
import argparse
import io
import os
import re
import sys

NOMS = ["rails_trades_panel.py", "matrice_croisement.py", "profils_croises.py",
        "magic_section.py", "churn_regime.py"]

# Les fonctions dont le CORPS decide d un vocabulaire de l export.
DEFAUT = ["_tf_tight", "_tf_sig", "_vs_pack", "_sess", "_leader_sig",
          "_bucket", "_aligned", "_spxled", "_tdir", "seau_churn"]

# Les constantes dont la VALEUR decide. Un seuil non lu est un seuil
# invente.
CONSTANTES = re.compile(
    r"^\s*(TIGHT_SPREAD|WT_SLOPE_MIN|WT_FLAT|SLOPE_K|NOISE_CROSS|AMP_MIN"
    r"|WHIP_MIN|WINDOW_N|RS_WINDOW|RS_RECENT|MA_SLOPE_K|_SETUP_ORDER"
    r"|_HC_CONS_ORDER|_MOM_ORDER|_TSW_COL|SETUPS|TFS)\s*=")


def trouve(racines):
    vus, sortie = set(), []
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        for dossier, sous, fichiers in os.walk(racine):
            sous[:] = [d for d in sous if d not in
                       (".git", "__pycache__", "node_modules",
                        "site-packages", "AppData")]
            for f in fichiers:
                if f in NOMS:
                    c = os.path.join(dossier, f)
                    r = os.path.normcase(os.path.abspath(c))
                    if r not in vus:
                        vus.add(r)
                        sortie.append(c)
    return sortie


def corps(lignes, i):
    """Rend le corps de la fonction qui commence a la ligne i.

    On s arrete a la premiere ligne non vide dont l indentation est
    inferieure ou egale a celle du `def` -- c est la fin du bloc en
    Python, sans avoir a analyser la syntaxe.
    """
    base = len(lignes[i]) - len(lignes[i].lstrip())
    out = [lignes[i]]
    for j in range(i + 1, len(lignes)):
        l = lignes[j]
        if not l.strip():
            out.append(l)
            continue
        ind = len(l) - len(l.lstrip())
        if ind <= base:
            break
        out.append(l)
    # On rogne les lignes vides de fin
    while out and not out[-1].strip():
        out.pop()
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", action="append", default=None)
    p.add_argument("--fonction", action="append", default=None,
                   help="nom exact ; repetable. Defaut : la liste utile")
    p.add_argument("--max", type=int, default=60,
                   help="lignes montrees par fonction")
    a = p.parse_args()

    racines = a.racine or [".", "..", os.path.join("..", "..")]
    voulues = a.fonction or DEFAUT

    L = []
    add = L.append
    add("=" * 78)
    add("EXTRAIT DES FONCTIONS QUI DECIDENT")
    add("=" * 78)
    add("")
    add("  Lecteur seul. Le code est imprime tel quel, sans reformulation")
    add("  -- une definition paraphrasee est une definition devinee.")
    add("")

    chemins = trouve(racines)
    if not chemins:
        add("  Aucun module trouve. Relance avec --racine CHEMIN.")
        print("\n".join(L))
        return 1

    manquantes = list(voulues)
    for c in chemins:
        try:
            src = io.open(c, encoding="utf-8", errors="replace").read()
        except (IOError, OSError):
            continue
        lignes = src.split("\n")

        # --- les constantes d abord : leur valeur decide
        consts = [(i + 1, l.rstrip()) for i, l in enumerate(lignes)
                  if CONSTANTES.match(l)]
        trouvees_ici = []
        for i, l in enumerate(lignes):
            m = re.match(r"\s*def\s+(\w+)\s*\(", l)
            if m and m.group(1) in voulues:
                trouvees_ici.append((m.group(1), i))

        if not consts and not trouvees_ici:
            continue

        add("=" * 78)
        add("%s" % c)
        add("=" * 78)

        if consts:
            add("  CONSTANTES QUI DECIDENT")
            for n, l in consts:
                add("    %5d  %s" % (n, l.strip()[:92]))
            add("")

        for nom, i in trouvees_ici:
            if nom in manquantes:
                manquantes.remove(nom)
            bloc = corps(lignes, i)
            add("  --- %s  (ligne %d, %d lignes)" % (nom, i + 1, len(bloc)))
            for k, l in enumerate(bloc[:a.max]):
                add("    %5d  %s" % (i + 1 + k, l.rstrip()[:100]))
            if len(bloc) > a.max:
                add("    ... %d lignes de plus" % (len(bloc) - a.max))
            add("")

    if manquantes:
        add("=" * 78)
        add("  NON TROUVEES : %s" % ", ".join(manquantes))
        add("  Elles portent peut-etre un autre nom. Relance avec")
        add("  --fonction NOM pour en cibler d autres.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
