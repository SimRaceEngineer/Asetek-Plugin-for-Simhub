# -*- coding: utf-8 -*-
r"""
papers_fenetre.py -- reparer les 15 cles : une lecture, une deduction

  python papers_fenetre.py
  python papers_fenetre.py --partie source     (le panneau seul)
  python papers_fenetre.py --partie donnees    (la fenetre seule)

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

POURQUOI DEUX PARTIES ET PAS UN REGLAGE

    Sur 36 cles, 16 tombent EXACTEMENT sur leur effectif annonce, 5 ne
    sont pas encodees, 15 ratent. Ces 15 ne ratent pas de la meme
    facon, et la difference decide de la reparation :

      -- certaines ratent PAR DEFAUT (-1 a -9). Il en manque quelques
         unes. Une coupure placee un peu plus tard les rendrait. C est
         un probleme de PARAMETRE.

      -- d autres ratent PAR EXCES (+24, +50, +20). Il y en a trop.
         Aucune coupure plus tardive ne peut en enlever : allonger la
         periode ne fait qu ajouter. C est un probleme de PREDICAT.

    Et les deux ne peuvent pas etre vrais ensemble. Une coupure plus
    tardive casserait les 16 qui tombent juste aujourd hui. Donc le
    parametre ne peut pas tout expliquer, et la question n est pas
    "quelle coupure choisir" mais "quelles cles sont compatibles avec
    UNE SEULE coupure".

PARTIE DONNEES -- LA DEDUCTION

    Pour chaque cle, sur le fichier ENTIER, on releve l horodatage du
    N-ieme ticket qui la verifie et celui du SUIVANT. Entre les deux,
    n importe quelle coupure donne exactement N. C est la FENETRE de
    la cle -- elle n est pas choisie, elle est lue.

    Une coupure unique existe si et seulement si toutes les fenetres
    se recoupent. Un parametre, 31 contraintes. Si un seul instant en
    satisfait 25, ce n est pas un ajustement, c est une mesure. S il
    en faut un par cle, c est un ajustement -- et alors ce sont les
    predicats qui sont faux, pas la coupure.

    Trois verdicts possibles, aucun negociable :
      DEFICIT   la cle n atteint jamais N, meme sur le fichier entier.
                Aucune coupure ne peut la sauver. Predicat trop etroit.
      TARD      sa fenetre est APRES la coupure : il lui en manque.
      TOT       sa fenetre est AVANT : elle en a trop.

PARTIE SOURCE -- LA LECTURE

    Les cles en exces disent BEAR, BULL, bull. Je les avais lues comme
    dir==SELL, dir==BUY, maj_dir==BULL. Ces lectures sont des
    suppositions. Le panneau, lui, contient la definition -- c est lui
    qui a produit l export.

    Cette partie sort, TEL QUEL, le code de rails_trades_panel.py
    autour de BEAR, BULL, du nest YES/NO, et de toute fonction dont le
    nom contient "section". Elle ne conclut pas : elle imprime a lire.

    C est la lecon du 18/08, appliquee avant et non apres : huit heures
    de retro-ingenierie sur ce qui etait ecrit dans un fichier deja en
    main. seau_churn faisait neuf lignes. _sess en faisait sept.
"""
import argparse
import io
import json
import os
import re
import sys

NOMS = ["rails_trades_panel.py"]

# Les mots de l export dont la definition manque. BEAR et BULL sont
# cherches en mot entier : ALIGNED_BULL ne matche pas \bBULL\b, et
# c est voulu -- les deux vocabulaires sont peut-etre distincts.
JETONS = [
    ("BEAR",  re.compile(r"\bBEAR\b")),
    ("BULL",  re.compile(r"\bBULL\b")),
    ("nest",  re.compile(r"\bnest\b")),
    ("YES",   re.compile(r"[\"']YES[\"']")),
    ("NO",    re.compile(r"[\"']NO[\"']")),
]

# Les fonctions dont le NOM annonce qu elles fabriquent une section de
# l export.
NOMS_FN = re.compile(r"^\s*def\s+(\w*section\w*|\w*_bull\w*|\w*_bear\w*"
                     r"|\w*nest\w*|\w*_sens\w*|\w*_dir_\w*)\s*\(")

# Les familles suffixees, montrees en comptes seulement : leurs lignes
# sont trop nombreuses pour un corps complet, mais leur PRESENCE dit ou
# le vocabulaire est fabrique.
SUFFIXES = re.compile(r"\b(ALIGNED_BULL|ALIGNED_BEAR|MAJ_BULL|MAJ_BEAR"
                      r"|BULLISH|BEARISH|bull|bear)\b")


# ======================================================================
# PARTIE SOURCE
# ======================================================================
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
    """Le bloc qui commence a la ligne i, borne par l indentation.

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
        if len(l) - len(l.lstrip()) <= base:
            break
        out.append(l)
    while out and not out[-1].strip():
        out.pop()
    return out


def enclosante(lignes, k):
    """Indice du `def` qui contient la ligne k, ou None si module."""
    ind_k = len(lignes[k]) - len(lignes[k].lstrip())
    for j in range(k, -1, -1):
        l = lignes[j]
        if not l.strip():
            continue
        m = re.match(r"(\s*)def\s+\w+\s*\(", l)
        if m and len(m.group(1)) < ind_k:
            return j
    return None


def partie_source(add, racines, maxl):
    add("=" * 78)
    add("PARTIE 1 -- CE QUE LE PANNEAU DIT DE BEAR, BULL ET DU NEST")
    add("=" * 78)
    add("")
    add("  Code imprime tel quel. Une definition paraphrasee est une")
    add("  definition devinee.")
    add("")

    chemins = trouve(racines)
    if not chemins:
        add("  rails_trades_panel.py introuvable. Relance avec")
        add("  --racine CHEMIN.")
        return

    for c in chemins:
        try:
            src = io.open(c, encoding="utf-8", errors="replace").read()
        except (IOError, OSError):
            continue
        lignes = src.split("\n")
        add("=" * 78)
        add("%s  (%d lignes)" % (c, len(lignes)))
        add("=" * 78)
        add("")

        # --- 1a. ou les mots apparaissent, et combien de fois
        add("  OU LES MOTS APPARAISSENT")
        for nom, rx in JETONS:
            hits = [i + 1 for i, l in enumerate(lignes) if rx.search(l)]
            if hits:
                apercu = ", ".join(str(h) for h in hits[:18])
                if len(hits) > 18:
                    apercu += ", ... (%d au total)" % len(hits)
                add("    %-6s %3d occurrence(s) : lignes %s"
                    % (nom, len(hits), apercu))
            else:
                add("    %-6s ABSENT du fichier" % nom)
        sfx = {}
        for i, l in enumerate(lignes):
            for m in SUFFIXES.finditer(l):
                sfx.setdefault(m.group(1), []).append(i + 1)
        if sfx:
            add("")
            add("  FAMILLES SUFFIXEES (comptes seuls)")
            for k in sorted(sfx):
                v = sfx[k]
                add("    %-14s %3d fois, 1re ligne %d" % (k, len(v), v[0]))
        add("")

        # --- 1b. les fonctions dont le NOM annonce une section
        par_nom = []
        for i, l in enumerate(lignes):
            m = NOMS_FN.match(l)
            if m:
                par_nom.append((m.group(1), i))

        # --- 1c. les fonctions qui CONTIENNENT un des mots
        par_mot = {}
        for i, l in enumerate(lignes):
            if not any(rx.search(l) for _, rx in JETONS):
                continue
            j = enclosante(lignes, i)
            if j is None:
                par_mot.setdefault(("<module>", i), []).append(i + 1)
            else:
                nom = re.match(r"\s*def\s+(\w+)", lignes[j]).group(1)
                par_mot.setdefault((nom, j), []).append(i + 1)

        vus = set()
        blocs = []
        for nom, i in par_nom:
            if i not in vus:
                vus.add(i)
                blocs.append((nom, i, []))
        for (nom, i), ou in sorted(par_mot.items(), key=lambda x: x[0][1]):
            if nom == "<module>":
                continue
            if i not in vus:
                vus.add(i)
                blocs.append((nom, i, ou))

        if not blocs:
            add("  Aucune fonction ne porte ni ne contient ces mots.")
            add("")
            continue

        add("  LES FONCTIONS, CORPS COMPLET")
        add("")
        for nom, i, ou in sorted(blocs, key=lambda x: x[1]):
            b = corps(lignes, i)
            marque = ""
            if ou:
                marque = "  [mot aux lignes %s]" % ", ".join(
                    str(x) for x in ou[:10])
            add("  --- %s  (ligne %d, %d lignes)%s"
                % (nom, i + 1, len(b), marque))
            for k, l in enumerate(b[:maxl]):
                add("    %5d  %s" % (i + 1 + k, l.rstrip()[:104]))
            if len(b) > maxl:
                add("    ... %d lignes de plus" % (len(b) - maxl))
            add("")

        # --- 1d. les occurrences hors fonction
        hors = [ou for (nom, i), ou in par_mot.items() if nom == "<module>"]
        if hors:
            plat = sorted(set(x for sub in hors for x in sub))
            add("  HORS FONCTION (constantes, tables) : lignes %s"
                % ", ".join(str(x) for x in plat[:24]))
            for n in plat[:24]:
                add("    %5d  %s" % (n, lignes[n - 1].rstrip()[:104]))
            add("")


# ======================================================================
# PARTIE DONNEES
# ======================================================================
def sur(pred, t):
    """Un predicat qui leve sur un ticket malforme ne doit pas tuer la
    mesure des 30 autres."""
    try:
        return bool(pred(t))
    except Exception:
        return False


def fenetre_cle(tickets, pred, n, colonne, PE):
    """Rend (m, lo, hi) : total de verifiants, horodatage du N-ieme,
    horodatage du suivant. Rien n est choisi ici -- tout est lu."""
    ts = sorted(t["entry_ts"] for t in tickets
                if isinstance(t.get("entry_ts"), str)
                and (colonne == "ALL" or PE._sess(t) == colonne)
                and sur(pred, t))
    m = len(ts)
    if m < n:
        return m, None, None
    return m, ts[n - 1], (ts[n] if m > n else None)


def compte_a(tickets, pred, colonne, coupure, PE):
    c = 0
    for t in tickets:
        e = t.get("entry_ts")
        if not isinstance(e, str) or e > coupure:
            continue
        if colonne != "ALL" and PE._sess(t) != colonne:
            continue
        if sur(pred, t):
            c += 1
    return c


def partie_donnees(add, fichier, colonne, coupure_arg, PE):
    add("=" * 78)
    add("PARTIE 2 -- UNE COUPURE, TRENTE ET UNE CONTRAINTES")
    add("=" * 78)
    add("")

    if not os.path.isfile(fichier):
        add("  Fichier introuvable : %s" % fichier)
        add("  Relance avec --fichier CHEMIN.")
        return

    tickets, ko = PE.charge(fichier)
    add("  %s : %d tickets lus, %d lignes illisibles"
        % (fichier, len(tickets), ko))

    coupure = coupure_arg or PE.coupure_deduite(tickets)
    if not coupure:
        add("  Coupure non deductible sur ce fichier. Relance avec")
        add("  --coupure 'AAAA-MM-JJ HH:MM:SS'.")
        return
    add("  Coupure de reference : %s%s"
        % (coupure, "  (donnee)" if coupure_arg else "  (deduite)"))
    add("  Colonne de session   : %s" % colonne)
    add("")

    encodees = [(c, lib, n, p) for c, lib, n, p, _ in PE.CLES if p is not None]
    add("  %d cles encodees. Pour chacune : le compte a la coupure, puis"
        % len(encodees))
    add("  la fenetre dans laquelle une coupure donnerait exactement N.")
    add("")

    lignes = []
    for cle, lib, n, pred in encodees:
        m, lo, hi = fenetre_cle(tickets, pred, n, colonne, PE)
        obt = compte_a(tickets, pred, colonne, coupure, PE)
        if lo is None:
            etat = "DEFICIT"
        elif lo > coupure:
            etat = "TARD"
        elif hi is not None and hi <= coupure:
            etat = "TOT"
        else:
            etat = "OK"
        lignes.append((cle, lib, n, obt, m, lo, hi, etat))

    add("  %-13s %5s %5s %6s  %-8s %-19s %-19s"
        % ("CLE", "N", "obt.", "ecart", "etat", "fenetre debut", "fenetre fin"))
    add("  " + "-" * 76)
    for cle, lib, n, obt, m, lo, hi, etat in lignes:
        add("  %-13s %5d %5d %+6d  %-8s %-19s %-19s"
            % (cle, n, obt, obt - n, etat,
               lo or ("total %d" % m), hi or "(fin du fichier)"))
    add("")

    # --- l intersection des cles qui tombent juste
    ok = [x for x in lignes if x[7] == "OK"]
    if ok:
        B = max(x[5] for x in ok)
        H = min([x[6] for x in ok if x[6]] or ["9999"])
        add("  LES %d CLES QUI TOMBENT JUSTE EPINGLENT LA COUPURE" % len(ok))
        add("    toute coupure dans [ %s , %s ) les rend TOUTES." % (B, H))
        add("    C est un intervalle lu, pas un reglage : il est impose")
        add("    par %d effectifs que nous n avons pas choisis." % len(ok))
        add("")
    else:
        B, H = None, None

    tard = [x for x in lignes if x[7] == "TARD"]
    tot = [x for x in lignes if x[7] == "TOT"]
    defi = [x for x in lignes if x[7] == "DEFICIT"]

    if tard:
        add("  RATENT PAR DEFAUT -- reparables par la coupure ?")
        for cle, lib, n, obt, m, lo, hi, _ in tard:
            if B is None:
                add("    %-13s manque %d. Sa fenetre ouvre a %s"
                    % (cle, n - obt, lo))
                continue
            dedans = (H is None or lo < H)
            add("    %-13s manque %d. Sa fenetre ouvre a %s -- %s"
                % (cle, n - obt, lo,
                   "DANS l intervalle des justes" if dedans
                   else "APRES : incompatible avec les %d justes" % len(ok)))
        add("")

    if tot:
        add("  RATENT PAR EXCES -- la coupure n y peut rien")
        add("    Allonger la periode ne fait qu ajouter des tickets.")
        add("    Une cle qui en a deja trop a un PREDICAT faux.")
        for cle, lib, n, obt, m, lo, hi, _ in tot:
            add("    %-13s %+d de trop. %s" % (cle, obt - n, lib))
        add("")

    if defi:
        add("  DEFICIT -- N jamais atteint, meme sur le fichier entier")
        add("    Aucune coupure ne peut les sauver : le predicat est")
        add("    trop etroit, ou la colonne de session est la mauvaise.")
        for cle, lib, n, obt, m, lo, hi, _ in defi:
            add("    %-13s N=%d, total possible %d (manque %d). %s"
                % (cle, n, m, n - m, lib))
        add("")

    # --- quel instant satisfait le plus de cles
    cands = sorted(set(x[5] for x in lignes if x[5]))
    if cands:
        score = []
        for c in cands:
            k = sum(1 for x in lignes
                    if x[5] and x[5] <= c and (x[6] is None or c < x[6]))
            score.append((k, c))
        score.sort(reverse=True)
        best = score[0][0]
        add("  L INSTANT QUI SATISFAIT LE PLUS DE CLES")
        for k, c in score[:5]:
            add("    %s  ->  %d cles sur %d" % (c, k, len(lignes)))
        add("")
        add("    Un parametre, %d contraintes, %d satisfaites au mieux."
            % (len(lignes), best))
        if best * 3 >= len(lignes) * 2:
            add("    Un seul scalaire qui rend %d effectifs que nous n" % best)
            add("    avons pas choisis n est pas un reglage : c est une")
            add("    mesure. Les %d restantes ne sont donc pas mal coupees,"
                % (len(lignes) - best))
            add("    elles sont mal ecrites -- et la partie 1 dit ou lire")
            add("    leur vraie definition.")
        else:
            add("    Trop peu pour qu une coupure explique quoi que ce")
            add("    soit. Ce ne sont pas les dates qui sont fausses, ce")
            add("    sont les predicats -- ou la colonne de session.")
        add("")

    # --- controle de colonne : une cle peut tomber juste ailleurs
    autres = [c for c in ("US", "EUR", "ALL") if c != colonne]
    suspects = []
    for cle, lib, n, obt, m, lo, hi, etat in lignes:
        if etat == "OK":
            continue
        pred = dict((c, p) for c, _l, _n, p in encodees)[cle]
        for col in autres:
            if compte_a(tickets, pred, col, coupure, PE) == n:
                suspects.append((cle, col))
                break
    if suspects:
        add("  CLES QUI TOMBENT JUSTE DANS UNE AUTRE COLONNE")
        add("    Le predicat serait bon, la session mal attribuee.")
        for cle, col in suspects:
            add("    %-13s exact sur la colonne %s" % (cle, col))
        add("")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--partie", choices=["source", "donnees", "tout"],
                   default="tout")
    p.add_argument("--racine", action="append", default=None)
    p.add_argument("--fichier", default=None)
    p.add_argument("--colonne", default="US", choices=["US", "EUR", "ALL"])
    p.add_argument("--coupure", default=None)
    p.add_argument("--max", type=int, default=70)
    a = p.parse_args()

    L = []
    add = L.append
    add("=" * 78)
    add("REPARATION DES 15 CLES -- lecture d abord, deduction ensuite")
    add("=" * 78)
    add("")

    if a.partie in ("source", "tout"):
        racines = a.racine or [".", "..", os.path.join("..", "..")]
        partie_source(add, racines, a.max)

    if a.partie in ("donnees", "tout"):
        try:
            import papers_encode as PE
        except ImportError:
            add("=" * 78)
            add("  papers_encode.py doit etre dans le meme dossier.")
            add("  Les 36 predicats y sont definis une seule fois -- une")
            add("  copie de plus serait une source de verite de plus a")
            add("  maintenir, et c est exactement ce qui a produit les")
            add("  deux TIGHT_SPREAD du 18/08.")
            print("\n".join(L))
            return 1
        partie_donnees(add, a.fichier or PE.CIBLE, a.colonne, a.coupure, PE)

    add("=" * 78)
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 78)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
