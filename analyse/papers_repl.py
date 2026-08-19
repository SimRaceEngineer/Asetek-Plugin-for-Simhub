# -*- coding: utf-8 -*-
r"""
papers_repl.py -- trouver le REPL et le lire, sans rien deviner

  python papers_repl.py                     inventaire + contenu
  python papers_repl.py --inventaire        l inventaire seul
  python papers_repl.py --max 3000          plus de lignes par fichier

LECTEUR SEUL. N ECRIT RIEN, N IMPORTE RIEN, NE PREND AUCUN TRADE.

POURQUOI CE SCRIPT EXISTE

    Les regles 220001-220012 viennent du REPL. Le moteur papier ne les
    connait pas : il importe papers_encode (les cles de l export) et
    papers_regles (la serie 240000, mes regles). Les douze 220000 sont
    absentes.

    Je les avais declarees "bloquees par une cle non validee". C etait
    raisonner sur MA reconstitution alors que la definition existait
    ailleurs -- la meme faute que seau_churn et _sess le 18/08. Donc on
    lit d abord, on encode ensuite.

COMMENT IL CHERCHE, ET DANS QUEL ORDRE DE CONFIANCE

    1. LES NUMEROS. Un fichier qui contient "220001" ou "220007" DEFINIT
       ou CITE ces regles. C est le signal le plus sur, parce qu il ne
       depend d aucun nom de fichier ni d aucune convention.

    2. LE NOM. Tout fichier ou dossier dont le nom contient "repl".

    3. LE MOT. Toute source qui contient REPL en toutes lettres.

    Un fichier peut marquer aux trois : il monte alors en tete.

CE QU IL NE FAIT PAS

    Il ne conclut pas, ne resume pas et ne reformule pas. Il imprime le
    contenu tel quel, pour qu il soit encode sans etre paraphrase.

CE QU IL COUPE, IL LE DIT

    Chaque troncature est annoncee avec le nombre de lignes omises et
    la commande pour les obtenir. Un panneau qui coupe en silence se
    lit comme un panneau complet.
"""
import argparse
import io
import os
import re
import sys

# Les douze regles de la serie. Trouver l une d elles suffit a
# identifier le fichier.
NUMEROS = re.compile(r"\b2200(0[1-9]|1[0-2])\b")
NOM_REPL = re.compile(r"repl", re.I)
MOT_REPL = re.compile(r"\bREPL\b")

IGNORE_DOSSIERS = (".git", "__pycache__", "node_modules", "site-packages",
                   "AppData", ".venv", "venv", "dist", "build")
# On lit tout ce qui peut porter du texte. Le .html est inclus : le REPL
# est peut-etre un onglet genere plutot qu un source.
EXTENSIONS = (".py", ".json", ".jsonl", ".txt", ".md", ".html", ".htm",
              ".csv", ".yml", ".yaml", ".ini", ".cfg", ".pine", ".js")
TAILLE_MAX = 12 * 1024 * 1024          # au-dela, on n ouvre pas


def octets(n):
    for u in ("o", "Ko", "Mo"):
        if n < 1024 or u == "Mo":
            return "%.0f %s" % (n, u)
        n /= 1024.0


MOI = re.compile(r"^papers_\w+\.py$", re.I)


def scanne(racines):
    """Rend [(score, chemin, taille, numeros, n_mot, lignes, mien)].

    Mes propres scripts d analyse citent les numeros 220000 : ce sont
    MES reconstitutions, pas la source. Ils restent listes -- les
    cacher serait un tri silencieux -- mais leur score est efface pour
    qu ils ne mangent pas le budget de lecture.
    """
    moi = os.path.normcase(os.path.abspath(__file__))
    vus, out = set(), []
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        for dossier, sous, fichiers in os.walk(racine):
            sous[:] = [d for d in sous if d not in IGNORE_DOSSIERS]
            dossier_repl = bool(NOM_REPL.search(os.path.basename(dossier)))
            for f in fichiers:
                che = os.path.join(dossier, f)
                cle = os.path.normcase(os.path.abspath(che))
                if cle in vus or cle == moi:
                    continue
                vus.add(cle)
                if os.path.splitext(f)[1].lower() not in EXTENSIONS:
                    continue
                try:
                    taille = os.path.getsize(che)
                except OSError:
                    continue
                if taille > TAILLE_MAX:
                    continue
                try:
                    src = io.open(che, encoding="utf-8",
                                  errors="replace").read()
                except (IOError, OSError):
                    continue

                lignes = src.split("\n")
                nums = set()
                ou_nums = []
                for i, l in enumerate(lignes):
                    for m in NUMEROS.finditer(l):
                        nums.add(m.group(0))
                        if len(ou_nums) < 400:
                            ou_nums.append((i + 1, l.rstrip()))
                n_mot = len(MOT_REPL.findall(src))
                nom_ok = bool(NOM_REPL.search(f)) or dossier_repl

                score = 0
                if nums:
                    score += 100 + len(nums) * 10
                if nom_ok:
                    score += 40
                if n_mot:
                    score += min(20, n_mot)
                mien = bool(MOI.match(f))
                if mien:
                    score = 1
                if score:
                    out.append((score, che, taille, sorted(nums), n_mot,
                                ou_nums, len(lignes), mien))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", action="append", default=None)
    p.add_argument("--inventaire", action="store_true",
                   help="l inventaire seul, sans le contenu")
    p.add_argument("--max", type=int, default=3000,
                   help="lignes imprimees par fichier (defaut 3000)")
    p.add_argument("--total", type=int, default=16000,
                   help="lignes imprimees en tout (defaut 16000)")
    p.add_argument("--fichiers", type=int, default=16,
                   help="nombre de fichiers dont le contenu est imprime")
    p.add_argument("--seuil", type=int, default=100,
                   help="score minimal pour imprimer le contenu")
    a = p.parse_args()

    racines = a.racine or [".", "..", os.path.join("..", "..")]
    L = []
    add = L.append
    add("=" * 100)
    add("LE REPL -- inventaire et lecture")
    add("=" * 100)
    add("")
    add("  Lecteur seul. Rien n est ecrit, rien n est importe.")
    add("  Racines explorees : %s" % ", ".join(racines))
    add("")

    trouves = scanne(racines)
    if not trouves:
        add("  RIEN TROUVE.")
        add("")
        add("  Aucun fichier ne contient 220001..220012, ne s appelle")
        add("  *repl*, ni ne cite REPL. Trois explications possibles :")
        add("    - le REPL vit hors des racines explorees")
        add("      -> relance avec --racine CHEMIN")
        add("    - il porte une extension non lue (%s)" % ", ".join(EXTENSIONS))
        add("    - c est un onglet calcule a la volee, sans fichier.")
        print("\n".join(L))
        return 1

    # ---------------------------------------------------------------
    add("=" * 100)
    add("INVENTAIRE -- %d fichier(s), du plus probable au moins probable"
        % len(trouves))
    add("=" * 100)
    add("  score  numeros 220000 trouves = +100 et +10 par numero")
    add("         nom contenant 'repl'   = +40")
    add("         mot REPL dans le texte = +1 par occurrence, max 20")
    add("")
    add("  %-6s %-58s %9s %6s %s"
        % ("SCORE", "FICHIER", "TAILLE", "LIGNES", "NUMEROS 220000"))
    add("  " + "-" * 96)
    for score, che, taille, nums, n_mot, _ou, n_lignes, mien in trouves:
        add("  %-6d %-58s %9s %6d %s%s"
            % (score, che[-58:], octets(taille), n_lignes,
               ", ".join(nums) if nums else
               ("REPL x%d" % n_mot if n_mot else "nom seul"),
               "   [MON script, pas la source]" if mien else ""))
    add("")

    porteurs = [t for t in trouves if t[3]]
    if porteurs:
        add("  %d fichier(s) portent des numeros 220000. C est la piste"
            % len(porteurs))
        add("  sure : ces numeros ne dependent d aucune convention de nom.")
    else:
        add("  AUCUN fichier ne porte de numero 220000. Les regles ne sont")
        add("  donc pas ecrites la ou je cherche -- l inventaire ci-dessus")
        add("  ne vaut que par le nom ou par le mot.")
    add("")

    if a.inventaire:
        print("\n".join(L))
        return 0

    # ---------------------------------------------------------------
    add("=" * 100)
    add("CONTENU -- tel quel, sans reformulation")
    add("=" * 100)
    add("")

    budget = a.total
    imprimes = 0
    omis_fichiers = []
    for score, che, taille, nums, n_mot, ou_nums, n_lignes, mien in trouves:
        if imprimes >= a.fichiers or score < a.seuil or budget <= 0:
            if score >= a.seuil:
                omis_fichiers.append((che, n_lignes, score))
            continue
        imprimes += 1
        try:
            src = io.open(che, encoding="utf-8", errors="replace").read()
        except (IOError, OSError):
            continue
        lignes = src.split("\n")
        add("=" * 100)
        add("%s   (score %d, %s, %d lignes)"
            % (che, score, octets(taille), len(lignes)))
        if nums:
            add("   numeros presents : %s" % ", ".join(nums))
        add("=" * 100)
        combien = min(a.max, budget, len(lignes))
        for i in range(combien):
            add("  %5d  %s" % (i + 1, lignes[i].rstrip()[:200]))
        budget -= combien
        if combien < len(lignes):
            add("")
            add("  ... %d LIGNE(S) NON IMPRIMEE(S) sur %d."
                % (len(lignes) - combien, len(lignes)))
            add("  Pour les avoir :")
            add("      python papers_repl.py --max %d --total %d"
                % (len(lignes) + 100, a.total + len(lignes) + 100))
        add("")

    if omis_fichiers:
        add("=" * 100)
        add("FICHIERS NON IMPRIMES -- ils passaient le seuil mais pas la")
        add("limite. Rien n est coupe en silence :")
        for che, n, sc in omis_fichiers:
            add("  score %-5d %-64s %d lignes" % (sc, che[-64:], n))
        add("")
        add("  Pour les avoir : python papers_repl.py --fichiers %d"
            % (imprimes + len(omis_fichiers)))
        add("")

    add("=" * 100)
    add("  %d fichier(s) imprime(s), %d ligne(s) sur un budget de %d."
        % (imprimes, a.total - budget, a.total))
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 100)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
