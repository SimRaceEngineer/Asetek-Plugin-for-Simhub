#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""sonde_miroir5.py -- la branche 5 va-t-elle vraiment s armer a 14 h ?

  python sonde_miroir5.py
  python sonde_miroir5.py --avec-mt5

CE QU ELLE VERIFIE, ET POURQUOI CHAQUE POINT PEUT TOUT ANNULER
--------------------------------------------------------------
Six conditions doivent tenir ENSEMBLE. Il suffit qu une seule manque
pour que la journee de mesure soit perdue, et perdue en silence : la
branche 5 ne se plaindra pas, elle n existera simplement pas.

  1. miroir_papers.py porte MIROIR5, magic_cvd et cvd_autorise.
     Sans eux, aucun ordre 5xxxxxx n est jamais envoye.

  2. MAX_MIROIRS compte des BRANCHES et non des parents. Passer de
     deux a trois branches par parent augmente le compte de moitie :
     un plafond laisse a 60 couperait la branche 5 en cours de
     seance, et seulement les jours charges. Le pire des defauts --
     celui qui ne se voit que quand ca compte.

  3. papers_exempt connait la plage 5220000. Ce fichier est lu par
     les modules de SORTIE, qui vivent dans le moteur. Sans lui la
     branche 5 sortirait comme le miroir 2, et l ecart 1 contre 5 ne
     mesurerait plus le filtre d entree mais un melange des deux.

  4. pont_miroirs connait la meme plage, sinon les ordres de la
     branche 5 ne franchissent pas le pont : ils existeraient sur le
     compte principal et seraient invisibles sur le compte dedie.

  5. cartes_live reconnait la branche 5, faute de quoi elle serait
     mesuree mais jamais affichee.

  6. LE PLUS IMPORTANT, ET LE PLUS FACILE A OUBLIER : le processus
     miroir doit etre NE APRES la derniere modification du fichier.
     Python charge le code en memoire au demarrage. Un fichier
     parfait sur le disque ne change rien a un processus lance avant
     -- c est la lecon du pont du 25/08, qui a tourne une heure avec
     l ancien code sous les yeux de tout le monde.

     Cette sonde compare donc l heure de naissance du processus a la
     date du fichier. C est le seul controle qui porte sur ce qui
     TOURNE et non sur ce qui est ecrit.

--avec-mt5 ajoute un essai a blanc : les deltas CVD des trois actifs
en ce moment, et si un achat ou une vente passerait le filtre. Il
n envoie rien, il ne fait que lire. Il est optionnel parce que
mt5.initialize() peut mettre une minute a s attacher.

Cette sonde ne modifie RIEN. Elle lit des fichiers et interroge le
gestionnaire de taches.
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


def lire(chemin):
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            return f.read()
    except (IOError, OSError):
        return None


def dit(ok, titre, detail=""):
    marque = "OK  " if ok else "NON "
    print("  %s %-38s %s" % (marque, titre, detail))
    return bool(ok)


def processus():
    try:
        s = subprocess.run(["powershell", "-NoProfile", "-Command", PS_LISTE],
                           capture_output=True, text=True, timeout=90).stdout
    except Exception as e:
        print("  inventaire impossible : %s" % e)
        return None
    out = []
    for l in s.splitlines():
        p = l.strip().split("|", 2)
        if len(p) == 3 and p[0].isdigit():
            out.append((int(p[0]), p[1], p[2]))
    return out


def horodate(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=RACINE_DEFAUT)
    ap.add_argument("--avec-mt5", action="store_true")
    a = ap.parse_args()
    R = a.racine

    print("=" * 70)
    print("sonde_miroir5 -- la branche 5 va-t-elle s armer ?")
    print("=" * 70)
    print("racine : %s" % R)
    print("")

    tout = True

    # ---------------------------------------------------- 1 et 2
    mp = os.path.join(R, "miroir_papers.py")
    s = lire(mp)
    if s is None:
        dit(False, "miroir_papers.py", "INTROUVABLE")
        return 2
    tout &= dit("MIROIR5 = True" in s, "MIROIR5 = True")
    tout &= dit("def magic_cvd(" in s, "magic_cvd()")
    tout &= dit("def cvd_autorise(" in s, "cvd_autorise()")
    # Deux expressions regulieres, DEUX noms. La premiere version les
    # appelait toutes les deux "m" : au moment de l essai a blanc, m ne
    # portait plus CVD_PAS mais MAX_MIROIRS, et le filtre etait teste
    # avec un pas de 90 points au lieu de 1. Les trois actifs
    # ressortaient "bloque" -- un resultat faux et alarmant.
    m_pas = re.search(r"^CVD_PAS\s*=\s*([0-9.]+)", s, re.M)
    dit(m_pas is not None, "CVD_PAS",
        ("pas de %s point(s) de delta" % m_pas.group(1)) if m_pas
        else "absent")
    m_max = re.search(r"^MAX_MIROIRS\s*=\s*(\d+)", s, re.M)
    if m_max:
        v = int(m_max.group(1))
        tout &= dit(v >= 90, "MAX_MIROIRS = %d" % v,
                    "compte des BRANCHES ; sous 90 la 5 saute les jours"
                    " charges" if v < 90 else "trois branches par parent")
    else:
        tout &= dit(False, "MAX_MIROIRS", "introuvable")

    # ------------------------------------------------------ 3, 4, 5
    for fichier, motif, quoi, pourquoi in (
            ("papers_exempt.py", "5220000", "papers_exempt : plage 5220000",
             "sans elle la branche 5 sort comme le miroir 2"),
            ("pont_miroirs.py", "5220000", "pont_miroirs : plage 5220000",
             "sans elle les ordres 5 ne franchissent pas le pont"),
            ("cartes_live.py", "5220000", "cartes_live : branche 5",
             "sans elle la branche 5 est mesuree mais jamais affichee")):
        c = lire(os.path.join(R, fichier))
        if c is None:
            tout &= dit(False, quoi, "FICHIER INTROUVABLE")
        else:
            tout &= dit(motif in c, quoi, "" if motif in c else pourquoi)

    # ---------------------------------------------------------- 6
    print("")
    print("  LE CONTROLE QUI PORTE SUR CE QUI TOURNE")
    procs = processus()
    if procs is None:
        tout = False
    else:
        vus = [(p, d, c) for p, d, c in procs if "miroir_papers.py" in c]
        if not vus:
            tout &= dit(False, "miroir_papers en cours",
                        "AUCUN PROCESSUS -- la branche 5 n existera pas")
        else:
            mtime = os.path.getmtime(mp)
            for p, d, c in vus:
                arme = "--armer" in c
                try:
                    ne = time.mktime(time.strptime(d, "%Y-%m-%d %H:%M:%S"))
                except ValueError:
                    ne = 0
                frais = ne > mtime
                dit(True, "pid %d" % p, "ne le %s" % d)
                tout &= dit(arme, "   lance avec --armer",
                            "" if arme else "en --tourner : il n envoie RIEN")
                tout &= dit(frais, "   ne APRES la derniere edition",
                            "fichier modifie le %s -- ce processus porte"
                            " l ANCIEN code, il faut le relancer"
                            % horodate(mtime) if not frais
                            else "fichier du %s" % horodate(mtime))
            if len(vus) > 1:
                tout &= dit(False, "un seul miroir",
                            "%d processus : ils enverraient des ordres"
                            " en double" % len(vus))

    # ---------------------------------------------------------- mt5
    if a.avec_mt5:
        print("")
        print("  ESSAI A BLANC -- lecture seule, aucun ordre")
        try:
            import MetaTrader5 as mt5
        except Exception as e:
            dit(False, "MetaTrader5", str(e))
            mt5 = None
        if mt5 is not None:
            if not mt5.initialize():
                dit(False, "initialize", str(mt5.last_error()))
            else:
                pas = float(m_pas.group(1)) if m_pas else 1.0
                for sym in ("US30", "US500", "US100", "NAS100", "SPX500"):
                    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
                    if r is None or len(r) < 2:
                        continue
                    d = []
                    for b in r:
                        vol = (float(b["real_volume"])
                               if float(b["real_volume"]) > 0
                               else float(b["tick_volume"]))
                        o, h, l, c = (float(b["open"]), float(b["high"]),
                                      float(b["low"]), float(b["close"]))
                        et = h - l
                        d.append(0.0 if (et <= 0 or vol <= 0) else
                                 vol * (abs(c - o) / et) *
                                 (1.0 if c >= o else -1.0))
                    prec, cour = d[0], d[1]
                    achat = cour >= prec + pas
                    vente = cour <= prec - pas
                    print("     %-8s precedente %+9.1f  en cours %+9.1f"
                          "   achat %s   vente %s"
                          % (sym, prec, cour,
                             "PASSE" if achat else "bloque",
                             "PASSE" if vente else "bloque"))
                mt5.shutdown()

    print("")
    print("=" * 70)
    if tout:
        print("TOUT EST EN PLACE. La branche 5 s armera a la premiere")
        print("ouverture de parent. Son premier signe de vie sera une ligne")
        print("M5xxxxxx CVD ok ou CVD REFUSE dans le journal du miroir.")
    else:
        print("AU MOINS UN POINT MANQUE. Corriger AVANT 14 h : une journee")
        print("de mesure perdue ne se rattrape pas, et la branche 5 ne se")
        print("plaindra pas -- elle n existera simplement pas.")
    print("=" * 70)
    return 0 if tout else 1


if __name__ == "__main__":
    sys.exit(main())
