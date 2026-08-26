#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""sonde_cliquet.py -- le stop peut-il encore revenir en arriere ?

  python sonde_cliquet.py
  python sonde_cliquet.py --racine "C:\SVPS\Scalp-EA-main"
  python sonde_cliquet.py --journal logs\trading_engine_20260826.log

CE QU ON CHERCHE
----------------
La demande est nette : une fois le stop pose, s il est deplace par le
BE ou le trail, il ne doit PLUS JAMAIS revenir au stop d origine.

sl_arbitre.py dit deja exactement cela -- "un stop ne recule jamais" --
et il est en mode BLOQUE depuis le 25/08 20:29:53. Si le probleme
persiste malgre lui, c est qu il existe un chemin qui ne passe pas par
lui. Avant de corriger quoi que ce soit, il faut savoir LEQUEL. Un
cliquet ne vaut rien s il reste une main sur le levier.

Cette sonde recense les chemins possibles. Il y en a six, et elles ne
se valent pas :

  1. L ARBITRE N EST PAS POSE, ou il est pose sur du vieux code.
     Le moteur charge Python en memoire au demarrage : un fichier
     parfait sur le disque ne change rien a un processus ne avant.
     On compare donc la naissance du processus a la date du fichier.

  2. LE STOP EST EFFACE PUIS REPOSE. C est le trou le plus serieux,
     et il est DANS l arbitre : _recule() renvoie False si le champ
     sl est vide ou nul, et False aussi si la position n a pas encore
     de stop. Donc "sl = 0" passe -- il n y a plus de stop -- puis la
     repose du stop d origine passe aussi, puisque la position est
     redevenue sans stop. Deux requetes anodines, un recul complet.
     La reference de l arbitre est le stop LU sur MT5 ; effacez-le et
     l arbitre a perdu la memoire.

  3. UN ECRIVAIN HORS DU PROCESSUS MOTEUR. L enveloppe ne vit que
     dans le processus ou install() a tourne. Un script lance a part
     -- une sonde, un gardien, un pont, un miroir -- garde le
     mt5.order_send d origine. Aucun arbitrage, aucun journal.

  4. from MetaTrader5 import order_send. Ce module-la a capture la
     fonction avant le remplacement et ne verra jamais l enveloppe.

  5. UN AUTRE PATCH DE order_send. Si un module sauve order_send puis
     le remplace a son tour, l ordre des poses decide qui gagne, et
     une enveloppe posee sur la fonction d ORIGINE court-circuite
     l arbitre.

  6. UNE ACTION AUTRE QUE SLTP qui porte quand meme un stop. L arbitre
     ne regarde que TRADE_ACTION_SLTP ; un DEAL avec sl, ou une
     fermeture-reouverture, sort de son champ.

CE QU ELLE FAIT
---------------
Elle LIT. Des fichiers, des journaux, la liste des processus. Elle
n ecrit rien, n envoie rien, ne touche pas a MT5. On peut la lancer
en pleine seance.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import time

RACINE_DEFAUT = r"C:\SVPS\Scalp-EA-main"

PS_LISTE = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
            "ForEach-Object { [string]$_.ProcessId + '|' + "
            "$_.CreationDate.ToString('yyyy-MM-dd HH:mm:ss') + '|' + "
            "[string]$_.CommandLine }")

# Dossiers qu on ne fouille pas : ils ne tournent pas.
IGNORE = ("__pycache__", ".git", "venv", ".venv", "site-packages",
          "archives", "archive", "sauvegardes", "backup", "backups",
          "node_modules", "cartes", "docs", "logs")

RE_ZERO = re.compile(r"""(?:["']sl["']\s*:|(?<![\w.])sl\s*=)\s*0(?:\.0*)?\s*(?:[,)}\]]|$)""")
RE_SLTP = re.compile(r"TRADE_ACTION_SLTP")
RE_SL_CHAMP = re.compile(r"""["']sl["']\s*:|(?<![\w.])sl\s*=""")
RE_IMPORT_DIRECT = re.compile(r"^\s*from\s+MetaTrader5\s+import\s+([^\n]+)", re.M)
RE_PATCH = re.compile(r"(?<![\w.])(?:mt5|_mt5\w*|\w*mt5\w*)\s*\.\s*order_send\s*=")
RE_RELOAD = re.compile(r"reload\s*\(\s*(?:mt5|MetaTrader5|_mt5\w*)")

RE_ARB_POSE = re.compile(r"\[SL-ARBITRE\]\s+v(\S+)\s+pose sur mt5\.order_send\s+--\s+mode\s+(\w+)")
RE_ARB_RECUL = re.compile(
    r"\[SL-ARBITRE\]\s+(\S+)\.([A-Za-z_]\w*)\s+ticket\s+(\S+)\s+(BUY|SELL)\s+"
    r"([-\d.]+)\s*->\s*([-\d.]+)\s+RECUL\s+([-\d.]+)\s+pts(.*)$")
RE_HEURE = re.compile(r"(\d{2}:\d{2}:\d{2})")


# ------------------------------------------------------------------ outils

def lire(chemin):
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


def horo(chemin):
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S",
                             time.localtime(os.path.getmtime(chemin)))
    except Exception:
        return None


def titre(t):
    print("")
    print("=" * 72)
    print(t)
    print("=" * 72)


def puce(ok, texte):
    """ok vaut True, False, ou None quand on ne sait pas."""
    marque = "  OK  " if ok is True else (" TROU " if ok is False else "  ?   ")
    print("[%s] %s" % (marque, texte))


def processus():
    """[(pid, naissance, ligne de commande)] -- vide si PowerShell manque."""
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-Command", PS_LISTE],
                           capture_output=True, timeout=90)
    except Exception:
        return []
    txt = (p.stdout or b"").decode("utf-8", "replace")
    out = []
    for l in txt.splitlines():
        bouts = l.strip().split("|", 2)
        if len(bouts) == 3 and bouts[0].isdigit():
            out.append((int(bouts[0]), bouts[1], bouts[2]))
    return out


def fichiers_py(racine):
    for dossier, sous, noms in os.walk(racine):
        sous[:] = [d for d in sous if d.lower() not in IGNORE]
        for n in noms:
            if n.endswith(".py"):
                yield os.path.join(dossier, n)


# --------------------------------------------------- 1. l arbitre lui-meme

def valeur(txt, nom):
    m = re.search(r"^%s\s*=\s*([^\n#]+)" % nom, txt or "", re.M)
    return m.group(1).strip() if m else None


def section_arbitre(racine, procs):
    titre("1. L ARBITRE : pose, et sur du code a jour ?")
    arb = os.path.join(racine, "sl_arbitre.py")
    moteur = os.path.join(racine, "trading_engine.py")
    t_arb, t_mot = lire(arb), lire(moteur)

    if t_arb is None:
        puce(False, "sl_arbitre.py INTROUVABLE dans %s" % racine)
        return None
    puce(True, "sl_arbitre.py present  (modifie %s)" % horo(arb))

    bloque = valeur(t_arb, "BLOQUE")
    exempts = valeur(t_arb, "EXEMPTS")
    version = valeur(t_arb, "VERSION")
    puce(bloque == "True", "BLOQUE = %s   (False = il observe et laisse passer)"
         % bloque)
    puce(exempts in ("set()", "set([])"),
         "EXEMPTS = %s   (tout nom ici a le droit de reculer un stop)" % exempts)
    print("        VERSION = %s" % version)

    if t_mot is None:
        puce(None, "trading_engine.py illisible -- pose non verifiable")
    else:
        pose = "import sl_arbitre as _sl_arb" in t_mot
        puce(pose, "trading_engine.py %s l arbitre  (modifie %s)"
             % ("appelle" if pose else "N APPELLE PAS", horo(moteur)))

    # Le seul controle qui porte sur ce qui TOURNE.
    vivants = [p for p in procs if "trading_engine" in p[2]]
    if not vivants:
        puce(None, "aucun processus trading_engine.py vu -- moteur arrete ?")
        return None
    for pid, ne, _cmd in vivants:
        mt = max([x for x in (horo(arb), horo(moteur)) if x] or [""])
        puce(ne > mt,
             "moteur pid %d ne le %s ; dernier fichier modifie le %s"
             % (pid, ne, mt))
        if ne <= mt:
            print("        -> ce processus a charge l ANCIEN code. "
                  "Tout ce qui suit ne dit rien de ce qui tourne.")
    return vivants


# ----------------------------------------------------- 2. ce que dit le log

def choisit_journal(racine, impose):
    if impose:
        c = impose if os.path.isabs(impose) else os.path.join(racine, impose)
        return c if os.path.exists(c) else None
    d = os.path.join(racine, "logs")
    if not os.path.isdir(d):
        return None
    cands = [os.path.join(d, n) for n in os.listdir(d)
             if n.startswith("trading_engine_") and n.endswith(".log")]
    if not cands:
        return None
    return max(cands, key=lambda c: os.path.getmtime(c))


def section_journal(racine, impose):
    titre("2. CE QUE LE JOURNAL A VU DEPUIS LE DERNIER DEMARRAGE")
    jr = choisit_journal(racine, impose)
    if jr is None:
        puce(None, "aucun trading_engine_*.log dans logs\\")
        return
    print("journal : %s  (ecrit %s)" % (jr, horo(jr)))

    lignes = (lire(jr) or "").splitlines()
    # On ne garde que la vie en cours : tout ce qui suit la derniere pose.
    depart, mode, ver = 0, None, None
    for i, l in enumerate(lignes):
        m = RE_ARB_POSE.search(l)
        if m:
            depart, ver, mode = i, m.group(1), m.group(2)
    if mode is None:
        puce(False, "aucune ligne de pose [SL-ARBITRE] -- l arbitre "
                    "n a jamais demarre dans ce journal")
    else:
        h = RE_HEURE.search(lignes[depart])
        puce(mode == "BLOQUE",
             "pose v%s en mode %s a %s (ligne %d) -- on ne lit que la suite"
             % (ver, mode, h.group(1) if h else "?", depart + 1))

    par_module, refuses, observes, pts_r, pts_o = {}, 0, 0, 0.0, 0.0
    exemples = []
    for l in lignes[depart:]:
        m = RE_ARB_RECUL.search(l)
        if not m:
            continue
        mod, fn, tk, sens, av, ap, pts, fin = m.groups()
        refuse = "REFUSE" in fin
        s = par_module.setdefault(mod, [0, 0, 0.0, 0.0])
        if refuse:
            s[0] += 1
            s[2] += float(pts)
            refuses += 1
            pts_r += float(pts)
        else:
            s[1] += 1
            s[3] += float(pts)
            observes += 1
            pts_o += float(pts)
        if len(exemples) < 8:
            h = RE_HEURE.search(l)
            exemples.append("  %s %-26s %s %s %s -> %s  %s pts  %s"
                            % (h.group(1) if h else "??:??:??", mod + "." + fn,
                               tk, sens, av, ap, pts,
                               "REFUSE" if refuse else "observe"))

    print("")
    print("reculs refuses par l arbitre : %d  (%.1f points sauves)"
          % (refuses, pts_r))
    print("reculs laisses passer        : %d  (%.1f points rendus)"
          % (observes, pts_o))
    if observes:
        puce(False, "des reculs passent ENCORE -- soit EXEMPTS, soit mode "
                    "observation, soit ces lignes precedent la pose")
    if par_module:
        print("")
        print("  %-30s %8s %8s %10s" % ("module", "refuses", "passes", "points"))
        for mod in sorted(par_module, key=lambda k: -(par_module[k][0] + par_module[k][1])):
            a, b, pa, pb = par_module[mod]
            print("  %-30s %8d %8d %10.1f" % (mod[:30], a, b, pa + pb))
    if exemples:
        print("")
        print("derniers cas :")
        for e in exemples:
            print(e)
    if refuses == 0 and observes == 0:
        puce(None, "aucun recul detecte depuis la pose. Soit le cliquet tient, "
                   "soit les reculs empruntent un chemin que l arbitre ne voit "
                   "pas -- c est la section 3 qui tranche.")


# --------------------------------------- 3. les chemins qui evitent l arbitre

def analyse_fichier(chemin):
    """Ce que ce fichier fait subir aux stops. Heuristique de texte, assumee.

    On lit une fenetre autour de chaque order_send plutot que l arbre
    syntaxique : les requetes sont montees par bouts sur vingt lignes, un
    ast.Call ne dirait pas ce que contient le dict au moment de l appel.
    """
    txt = lire(chemin)
    if not txt or "order_send" not in txt:
        return None
    lignes = txt.splitlines()
    r = {"appels": 0, "sltp": 0, "sl": 0, "zero": [], "autonome": False,
         "import_direct": None, "patch": [], "reload": False}
    r["autonome"] = "__main__" in txt
    m = RE_IMPORT_DIRECT.search(txt)
    if m and "order_send" in m.group(1):
        r["import_direct"] = m.group(1).strip()
    r["reload"] = bool(RE_RELOAD.search(txt))
    for i, l in enumerate(lignes):
        if RE_PATCH.search(l) and "sl_arbitre" not in chemin:
            r["patch"].append((i + 1, l.strip()[:70]))
        if "order_send(" not in l:
            continue
        r["appels"] += 1
        deb, fin = max(0, i - 30), min(len(lignes), i + 6)
        fen = "\n".join(lignes[deb:fin])
        if RE_SLTP.search(fen):
            r["sltp"] += 1
        if RE_SL_CHAMP.search(fen):
            r["sl"] += 1
        for j in range(deb, fin):
            if RE_ZERO.search(lignes[j]) and "sl" in lignes[j]:
                r["zero"].append((j + 1, lignes[j].strip()[:70]))
    return r


def section_chemins(racine, procs):
    titre("3. LES CHEMINS QUI N ONT AUCUN ARBITRE")
    fiches = {}
    for f in fichiers_py(racine):
        if os.path.basename(f) == "sl_arbitre.py":
            continue                        # c est l arbitre, pas un suspect
        a = analyse_fichier(f)
        if a and (a["appels"] or a["patch"] or a["import_direct"]):
            fiches[f] = a

    ecrivains = dict((f, a) for f, a in fiches.items() if a["sl"] or a["sltp"])
    print("fichiers qui touchent a order_send           : %d" % len(fiches))
    print("dont ceux qui portent un stop dans la requete: %d" % len(ecrivains))

    # -- 4. la capture directe
    print("")
    directs = [(f, a) for f, a in fiches.items() if a["import_direct"]]
    puce(not directs, "from MetaTrader5 import order_send : %d fichier(s)"
         % len(directs))
    for f, a in directs:
        print("        %s  ->  %s" % (os.path.basename(f), a["import_direct"]))

    # -- 5. un autre patch de order_send
    print("")
    patchs = [(f, a) for f, a in fiches.items() if a["patch"]]
    puce(not patchs, "autres remplacements de order_send : %d fichier(s)"
         % len(patchs))
    for f, a in patchs:
        for no, l in a["patch"]:
            print("        %s:%d  %s" % (os.path.basename(f), no, l))
    reloads = [f for f, a in fiches.items() if a["reload"]]
    if reloads:
        puce(False, "reload() de MetaTrader5 : %s -- un reload REMET la "
                    "fonction d origine et decroche l arbitre"
             % ", ".join(os.path.basename(x) for x in reloads))

    # -- 2. l effacement du stop
    print("")
    zeros = [(f, a) for f, a in ecrivains.items() if a["zero"]]
    puce(not zeros, "requetes qui mettent le stop a ZERO : %d fichier(s)"
         % len(zeros))
    if zeros:
        print("        Un sl a 0 EFFACE le stop, et l arbitre le laisse passer")
        print("        (_recule renvoie False si le champ sl est vide ou nul).")
        print("        La position redevient sans stop ; la repose du stop")
        print("        d origine passe alors elle aussi. Recul complet en deux")
        print("        requetes qu aucune ligne de journal ne signale.")
        for f, a in zeros:
            for no, l in a["zero"][:3]:
                print("        %s:%d  %s" % (os.path.basename(f), no, l))

    # -- 6. un stop porte par une action autre que SLTP
    print("")
    hors_sltp = [(f, a) for f, a in ecrivains.items() if a["sl"] and not a["sltp"]]
    puce(not hors_sltp,
         "stops ecrits sans TRADE_ACTION_SLTP visible : %d fichier(s)"
         % len(hors_sltp))
    for f, a in hors_sltp[:12]:
        print("        %s  (%d appel(s))" % (os.path.basename(f), a["appels"]))
    if len(hors_sltp) > 12:
        print("        ... et %d autres" % (len(hors_sltp) - 12))

    # -- 3. LE point : qui ecrit des stops en dehors du moteur, EN CE MOMENT
    titre("4. LES MAINS SUR LE LEVIER, HORS DU PROCESSUS MOTEUR")
    print("L enveloppe ne vit que dans le processus ou install() a tourne.")
    print("Tout autre processus garde le mt5.order_send d origine.")
    print("")
    dehors = []
    for pid, ne, cmd in procs:
        if "trading_engine" in cmd:
            continue
        for f, a in ecrivains.items():
            base = os.path.basename(f)
            if base in cmd:
                dehors.append((pid, ne, base, a))
                break
    if not dehors:
        puce(True, "aucun processus vivant hors moteur n ecrit de stop")
    else:
        puce(False, "%d processus vivant(s) ecrivent des stops sans arbitre :"
             % len(dehors))
        for pid, ne, base, a in dehors:
            print("        pid %-6d ne %s  %-28s %d appel(s), %d avec SLTP"
                  % (pid, ne, base, a["appels"], a["sltp"]))

    print("")
    print("Ecrivains de stop AUTONOMES (un __main__, donc lancables a part) --")
    print("ceux-la n ont d arbitre que s ils tournent dans le moteur :")
    autos = sorted(os.path.basename(f) for f, a in ecrivains.items()
                   if a["autonome"])
    for i in range(0, len(autos), 3):
        print("    " + "  ".join("%-24s" % x for x in autos[i:i + 3]))
    return ecrivains, zeros, dehors, directs, patchs


# --------------------------------------------------------------- conclusion

def section_verdict(res):
    titre("VERDICT -- par ou un stop peut encore revenir en arriere")
    if res is None:
        print("analyse statique non faite.")
        return
    ecrivains, zeros, dehors, directs, patchs = res
    n = 0
    if zeros:
        n += 1
        print("%d) L EFFACEMENT DU STOP. %d fichier(s) posent sl = 0. "
              "L arbitre" % (n, len(zeros)))
        print("   ne voit pas passer un effacement, et la repose qui suit")
        print("   arrive sur une position sans stop : elle est donc permise.")
        print("   C est le seul chemin qui reproduit exactement le symptome")
        print("   decrit -- le BE annule, le stop d origine de retour.")
    if dehors:
        n += 1
        print("%d) LES PROCESSUS HORS MOTEUR. %d tournent en ce moment."
              % (n, len(dehors)))
    if directs:
        n += 1
        print("%d) LA CAPTURE DIRECTE de order_send. %d fichier(s)."
              % (n, len(directs)))
    if patchs:
        n += 1
        print("%d) UN AUTRE PATCH de order_send. %d fichier(s)."
              % (n, len(patchs)))
    if n == 0:
        print("Aucun chemin de contournement trouve par cette sonde.")
        print("Si des reculs persistent malgre cela, ils sont dans le journal")
        print("de la section 2 -- et alors c est EXEMPTS ou le mode qu il faut")
        print("regarder, pas le code.")
    print("")
    print("Rien n a ete modifie. Cette sonde ne fait que lire.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--racine", default=RACINE_DEFAUT)
    ap.add_argument("--journal", default=None,
                    help="un trading_engine_*.log precis ; sinon le plus recent")
    a = ap.parse_args()
    racine = a.racine
    if not os.path.isdir(racine):
        print("racine introuvable : %s" % racine)
        return 2
    print("sonde_cliquet -- %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("racine : %s" % racine)
    procs = processus()
    print("processus python vus : %d" % len(procs))
    section_arbitre(racine, procs)
    section_journal(racine, a.journal)
    res = section_chemins(racine, procs)
    section_verdict(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
