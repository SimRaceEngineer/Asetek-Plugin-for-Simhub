# -*- coding: utf-8 -*-
r"""
repl_fetch.py -- pourquoi la seconde reponse du REPL echoue

  python repl_fetch.py
  python repl_fetch.py --fichier repl_web.py      un fichier, sans balayage
  python repl_fetch.py --lignes repl_web.py:225-270    ces lignes exactement
  python repl_fetch.py --max 600                  plus de lignes
  python repl_fetch.py --inventaire               la liste seule

LECTEUR SEUL. N ECRIT RIEN, N APPELLE AUCUNE API, NE TOUCHE A RIEN.

CE QU IL CHERCHE

    "failed to fetch" n est pas un message de Python : c est le message
    du NAVIGATEUR quand une requete sortante echoue. Trois causes
    possibles, et elles ne se distinguent que par le code :

      1. le serveur du panneau a repondu une erreur (cle absente,
         quota, 401, 500) et la page n a affiche que l enveloppe ;
      2. la requete n a jamais abouti -- delai depasse, coupure ;
      3. la seconde requete part avant que la premiere soit finie, et
         quelque chose la rejette (session, verrou, meme identifiant).

    Ce script sort le code qui APPELLE les modeles et le code qui
    ATTRAPE les erreurs. C est la seule facon de savoir laquelle des
    trois on regarde, plutot que d en supposer une.

POURQUOI --lignes EXISTE

    Un extrait par motif montre ce qui RESSEMBLE a la reponse. Il ne
    montre pas ce qui la contredit : une ligne qui ne porte ni nom de
    modele, ni verbe de requete, ni mot d erreur reste invisible --
    et c est exactement le cas de l appel lui-meme. Quand on sait
    quelles lignes manquent, il faut pouvoir les demander par leur
    numero.

CE QU IL SORT

    1. les fichiers qui parlent des modeles (deepseek, REPL_MODELES,
       claude, openai, mistral) ou qui font une requete sortante ;
    2. leur code d appel : requete, delai, reprise, gestion d erreur ;
    3. les traces recentes -- toute ligne de log contenant fetch,
       timeout, 401, 429, 500, ou une exception.

LES SECRETS NE SORTENT PAS

    Toute ligne qui ressemble a une cle (KEY, TOKEN, SECRET, PASSWORD,
    Authorization, Bearer, sk-...) est imprimee AVEC SA VALEUR
    MASQUEE. La sortie de ce script est faite pour etre collee dans une
    conversation : elle ne doit jamais transporter un identifiant.
"""
import argparse
import io
import os
import re
import sys

MODELES = re.compile(
    r"deepseek|REPL_MODELES|repl_modeles|anthropic|openai|mistral"
    r"|gpt-4|claude-|llm_compare|reason_ab", re.I)

APPELS = re.compile(
    r"requests\.(post|get)|urlopen|http\.client|HTTPSConnection"
    r"|\bfetch\s*\(|aiohttp|httpx|XMLHttpRequest|axios", re.I)

ERREURS = re.compile(
    r"failed to fetch|timeout|timed out|ReadTimeout|ConnectionError"
    r"|\b401\b|\b403\b|\b429\b|\b500\b|\b502\b|\b504\b"
    r"|Traceback|Exception|except\s|retry|backoff", re.I)

# Ce qui ne doit JAMAIS sortir en clair.
SECRET = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|Authorization|Bearer|api_key)"
    r"\s*[:=]\s*(.+)", re.I)
SECRET_NU = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}")

IGNORE_DOSSIERS = (".git", "__pycache__", "node_modules", "site-packages",
                   "AppData", ".venv", "venv", "dist", "build")
EXT_CODE = (".py", ".js", ".html", ".htm", ".json", ".yml", ".yaml",
            ".ini", ".cfg", ".ps1", ".bat")
# .jsonl EXCLU volontairement : ce sont des donnees, pas des journaux.
# Le motif \b500\b matche n importe quel 500 dans un ticket, ce qui
# faisait exploser le comptage sur docs\ -- le script restait bloque.
EXT_LOG = (".log", ".txt", ".err", ".out")
TAILLE_MAX = 3 * 1024 * 1024
# On ne compte que sur le debut du fichier : un score n a pas besoin du
# fichier entier, et un gros fichier ne doit pas couter une minute.
TETE = 400 * 1024


def masque(l):
    """Rend la ligne sans sa valeur secrete. Une cle collee dans une
    conversation est une cle a revoquer."""
    l = SECRET_NU.sub("sk-***MASQUE***", l)
    m = SECRET.search(l)
    if m and m.group(2).strip() not in ("", '""', "''", "None"):
        l = l[:m.start(2)] + "***MASQUE*** (%d car.)" % len(m.group(2).strip())
    return l


def octets(n):
    for u in ("o", "Ko", "Mo"):
        if n < 1024 or u == "Mo":
            return "%.0f %s" % (n, u)
        n /= 1024.0


MOI = re.compile(r"^papers_\w+\.py$", re.I)


def balaye(racines):
    """Rend deux listes : (code, logs), chacune de (score, chemin, ...).

    Ce script s exclut lui-meme et ecarte mes propres papers_*.py : ils
    citent les memes mots et mangeraient tout le budget de lecture sans
    rien apprendre sur le REPL.
    """
    moi = os.path.normcase(os.path.abspath(__file__))
    vus, code, logs = set(), [], []
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        for dossier, sous, fichiers in os.walk(racine):
            sous[:] = [d for d in sous if d not in IGNORE_DOSSIERS]
            for f in fichiers:
                che = os.path.join(dossier, f)
                cle = os.path.normcase(os.path.abspath(che))
                if cle in vus or cle == moi or MOI.match(f):
                    continue
                vus.add(cle)
                ext = os.path.splitext(f)[1].lower()
                if ext not in EXT_CODE and ext not in EXT_LOG:
                    continue
                try:
                    taille = os.path.getsize(che)
                    if taille > TAILLE_MAX:
                        continue
                    src = io.open(che, encoding="utf-8",
                                  errors="replace").read()
                except (IOError, OSError):
                    continue
                lignes = src.split("\n")
                tete = src[:TETE]
                n_mod = len(MODELES.findall(tete))
                n_app = len(APPELS.findall(tete))
                n_err = len(ERREURS.findall(tete))
                if ext in EXT_CODE:
                    score = n_mod * 5 + n_app * 8
                    if score:
                        code.append((score, che, taille, len(lignes),
                                     n_mod, n_app, n_err))
                else:
                    # un log ne vaut que par ses erreurs
                    if n_err and (n_mod or "fetch" in src.lower()):
                        logs.append((n_err, che, taille, len(lignes),
                                     n_mod, 0, n_err))
    code.sort(key=lambda x: (-x[0], x[1]))
    logs.sort(key=lambda x: (-x[0], x[1]))
    return code, logs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", action="append", default=None,
                   help="defaut : le dossier courant seul")
    p.add_argument("--fichier", action="append", default=None,
                   help="lire CE fichier et rien d autre ; repetable. "
                        "Aucun balayage : instantane.")
    p.add_argument("--lignes", action="append", default=None,
                   help="FICHIER:DEBUT-FIN, repetable. Imprime CES lignes "
                        "telles quelles, sans filtre ni contexte. Pour les "
                        "lignes qu un extrait par motif a sautees.")
    p.add_argument("--inventaire", action="store_true")
    p.add_argument("--max", type=int, default=400,
                   help="lignes de contexte par fichier (defaut 400)")
    p.add_argument("--fichiers", type=int, default=10)
    p.add_argument("--traces", type=int, default=120,
                   help="lignes de log retenues par fichier")
    a = p.parse_args()

    racines = a.racine or ["."]
    L = []
    add = L.append
    add("=" * 100)
    add("REPL -- POURQUOI LA SECONDE REPONSE ECHOUE")
    add("=" * 100)
    add("")
    add("  Lecteur seul : aucune API appelee, aucun fichier ecrit.")
    add("  Les cles et jetons sont MASQUES -- cette sortie est faite")
    add("  pour etre collee dans une conversation.")
    add("  Racines : %s" % ", ".join(racines))
    add("")

    # --- plages explicites : ce qu aucun motif n a fait sortir
    if a.lignes:
        for spec in a.lignes:
            try:
                che, plage = spec.rsplit(":", 1)
                d, f = plage.split("-")
                d, f = int(d), int(f)
            except ValueError:
                add("  PLAGE MAL ECRITE : %s  (attendu FICHIER:DEBUT-FIN)"
                    % spec)
                continue
            if not os.path.isfile(che):
                add("  INTROUVABLE : %s" % che)
                continue
            lg = io.open(che, encoding="utf-8",
                         errors="replace").read().split("\n")
            add("=" * 100)
            add("%s   lignes %d a %d  (fichier : %d lignes)"
                % (che, d, f, len(lg)))
            add("=" * 100)
            for i in range(max(1, d), min(len(lg), f) + 1):
                add("  %5d  %s" % (i, masque(lg[i - 1].rstrip())[:220]))
            add("")
        if not a.fichier:
            add("=" * 100)
            add("  Ce script n a rien ecrit, n a appele aucune API, et a")
            add("  masque toute valeur ressemblant a une cle.")
            add("=" * 100)
            print("\n".join(L))
            return 0

    if a.fichier:
        code, logs = [], []
        for che in a.fichier:
            if not os.path.isfile(che):
                add("  INTROUVABLE : %s" % che)
                continue
            try:
                src = io.open(che, encoding="utf-8",
                              errors="replace").read()
            except (IOError, OSError):
                add("  ILLISIBLE : %s" % che)
                continue
            n = len(src.split("\n"))
            t = os.path.getsize(che)
            ext = os.path.splitext(che)[1].lower()
            ligne = (999, che, t, n, len(MODELES.findall(src[:TETE])),
                     len(APPELS.findall(src[:TETE])),
                     len(ERREURS.findall(src[:TETE])))
            (logs if ext in EXT_LOG else code).append(ligne)
    else:
        code, logs = balaye(racines)
    if not code and not logs:
        add("  RIEN TROUVE. Aucun fichier ne parle des modeles ni ne fait")
        add("  de requete sortante dans ces racines.")
        add("  -> relance avec --racine CHEMIN")
        print("\n".join(L))
        return 1

    add("=" * 100)
    add("INVENTAIRE -- code (%d) et journaux (%d)" % (len(code), len(logs)))
    add("=" * 100)
    add("  %-6s %-56s %8s %6s %5s %5s %5s"
        % ("SCORE", "FICHIER", "TAILLE", "LIGNES", "MODEL", "APPEL", "ERR"))
    add("  " + "-" * 94)
    for sc, che, ta, nl, nm, na, ne in code[:40]:
        add("  %-6d %-56s %8s %6d %5d %5d %5d"
            % (sc, che[-56:], octets(ta), nl, nm, na, ne))
    if logs:
        add("")
        add("  JOURNAUX")
        for sc, che, ta, nl, nm, na, ne in logs[:20]:
            add("  %-6d %-56s %8s %6d %5d %5s %5d"
                % (sc, che[-56:], octets(ta), nl, nm, "-", ne))
    add("")

    if a.inventaire:
        print("\n".join(L))
        return 0

    # --- le code d appel
    add("=" * 100)
    add("LE CODE QUI APPELLE LES MODELES")
    add("=" * 100)
    for sc, che, ta, nl, nm, na, ne in code[:a.fichiers]:
        try:
            lignes = io.open(che, encoding="utf-8",
                             errors="replace").read().split("\n")
        except (IOError, OSError):
            continue
        interessantes = [i for i, l in enumerate(lignes)
                         if MODELES.search(l) or APPELS.search(l)
                         or ERREURS.search(l)]
        if not interessantes:
            continue
        add("")
        add("-" * 100)
        add("%s   (score %d, %d lignes)" % (che, sc, nl))
        add("-" * 100)
        # on montre chaque zone interessante avec 6 lignes de contexte
        montre, dernier, budget = set(), -99, a.max
        for i in interessantes:
            for j in range(max(0, i - 6), min(len(lignes), i + 7)):
                montre.add(j)
        for j in sorted(montre):
            if budget <= 0:
                add("     ... %d ligne(s) de plus non montrees. Pour les"
                    " avoir : --max %d" % (len(montre) - a.max, a.max * 3))
                break
            if j > dernier + 1:
                add("     ---")
            add("  %5d  %s" % (j + 1, masque(lignes[j].rstrip())[:200]))
            dernier = j
            budget -= 1

    # --- les traces
    if logs:
        add("")
        add("=" * 100)
        add("LES TRACES -- lignes d erreur des journaux, les plus recentes")
        add("=" * 100)
        for sc, che, ta, nl, nm, na, ne in logs[:6]:
            try:
                lignes = io.open(che, encoding="utf-8",
                                 errors="replace").read().split("\n")
            except (IOError, OSError):
                continue
            hits = [(i + 1, l) for i, l in enumerate(lignes)
                    if ERREURS.search(l)]
            add("")
            add("-" * 100)
            add("%s   (%d ligne(s) d erreur sur %d)" % (che, len(hits), nl))
            add("-" * 100)
            for n, l in hits[-a.traces:]:
                add("  %6d  %s" % (n, masque(l.rstrip())[:200]))
            if len(hits) > a.traces:
                add("  ... %d ligne(s) d erreur plus anciennes non montrees."
                    % (len(hits) - a.traces))
                add("  Pour les avoir : --traces %d" % (len(hits) + 50))

    add("")
    add("=" * 100)
    add("  Ce script n a rien ecrit, n a appele aucune API, et a masque")
    add("  toute valeur ressemblant a une cle.")
    add("=" * 100)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
