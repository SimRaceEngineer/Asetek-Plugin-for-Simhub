# -*- coding: utf-8 -*-
"""
surveiller_demarrage.py -- y a-t-il eu une rafale d ouvertures ?

  python surveiller_demarrage.py                 # les 10 dernieres minutes
  python surveiller_demarrage.py --minutes 60
  python surveiller_demarrage.py --apres "2026-08-13 19:35"

CE QU IL CHERCHE

    _armed part vide a chaque demarrage d un moteur. Une ignition en
    cours se lit alors comme FRAICHE, et toutes les cellules armables
    peuvent ouvrir dans la meme seconde -- sur un signal qui n existe
    pas. C est arrive au papier le 12/08 a 23:38:54 : huit positions
    d un coup, qui portaient ensuite la quasi-totalite des pertes
    attribuees a trois unites de temps.

    En passant de 19 a 37 cellules, on double la portee de cet effet.
    Ce script regarde le journal de decisions et repond a une seule
    question : les OPEN sont-ils etales, ou groupes sur une seconde ?

CE QU IL NE FAIT PAS

    Il LIT des fichiers .jsonl. Il n ouvre aucun socket, ne touche
    aucun processus, n envoie aucun ordre, et n ecrit rien. On peut le
    lancer autant de fois qu on veut, y compris pendant que les
    moteurs tournent.

COMMENT LIRE LE VERDICT

    Un demarrage sain etale ses ouvertures : les cellules s allument
    quand leur unite de temps bascule, donc a des secondes differentes.

    Une rafale, c est plusieurs OPEN a la MEME seconde, juste apres un
    demarrage. Si tu vois ca, il ne faut pas analyser : il faut couper.

    Le seuil est a 4 par defaut. Trois actifs peuvent legitimement
    s allumer ensemble sur une bascule commune ; au-dela, c est le
    demarrage qui parle, pas le marche.
"""
import argparse
import glob
import io
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

_ICI = os.path.dirname(os.path.abspath(__file__))
SEUIL = 4
LARG = 78


def _horo(s):
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(s)[:19], f)
        except (ValueError, TypeError):
            continue
    return None


def _journaux():
    """Tous les decisions.jsonl sous docs/, sans en deviner aucun."""
    return sorted(glob.glob(os.path.join(_ICI, "docs", "*", "decisions.jsonl")))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=int, default=10)
    p.add_argument("--apres", default=None,
                   help='"AAAA-MM-JJ HH:MM" -- prioritaire sur --minutes')
    p.add_argument("--seuil", type=int, default=SEUIL)
    a = p.parse_args()

    depuis = _horo(a.apres + ":00") if a.apres else (
        datetime.now() - timedelta(minutes=a.minutes))
    if depuis is None:
        print("KO : --apres attendu au format \"AAAA-MM-JJ HH:MM\".")
        return 1

    jx = _journaux()
    if not jx:
        print("KO : aucun docs/*/decisions.jsonl trouve a cote de ce script.")
        print("     Lance-le depuis le dossier de la stack.")
        return 1

    print("=" * LARG)
    print(" SURVEILLANCE DU DEMARRAGE -- rafale d ouvertures ?")
    print("=" * LARG)
    print("depuis : %s" % depuis.strftime("%Y-%m-%d %H:%M:%S"))
    print("seuil  : %d OPEN dans la meme seconde" % a.seuil)
    print()

    total = 0
    rafales = []
    for j in jx:
        nom = os.path.basename(os.path.dirname(j))
        par_sec = defaultdict(list)
        lus = ill = 0
        for ligne in io.open(j, encoding="utf-8", errors="replace"):
            b = ligne.strip()
            if not b or b[0] != "{":
                ill += 1
                continue
            try:
                e = json.loads(b)
            except ValueError:
                ill += 1
                continue
            t = _horo(e.get("iso"))
            if t is None or t < depuis:
                continue
            lus += 1
            if str(e.get("ev", "")).upper().startswith("OPEN") \
                    and "FAIL" not in str(e.get("ev", "")).upper():
                par_sec[t.strftime("%H:%M:%S")].append(e)

        n = sum(len(v) for v in par_sec.values())
        total += n
        print("-" * LARG)
        print("%-28s %d evenement(s) dans la fenetre, %d OPEN"
              % (nom, lus, n))
        if ill:
            print("  %d ligne(s) illisible(s), ignoree(s)." % ill)
        if not n:
            print("  Aucune ouverture. Rien a signaler ici.")
            continue

        pires = sorted(par_sec.items(), key=lambda kv: -len(kv[1]))[:5]
        print("  %-10s %6s   %s" % ("seconde", "OPEN", "magics"))
        for sec, evs in pires:
            mg = ", ".join(str(e.get("magic", "?")) for e in evs[:8])
            if len(evs) > 8:
                mg += ", ..."
            print("  %-10s %6d   %s" % (sec, len(evs), mg))
            if len(evs) >= a.seuil:
                rafales.append((nom, sec, len(evs)))

        # Les nouvelles unites se reconnaissent aux deux derniers
        # chiffres du magic. Utile pour savoir QUI a ouvert.
        neuves = [e for v in par_sec.values() for e in v
                  if str(e.get("magic", ""))[-2:] in ("10", "20", "30")]
        if neuves:
            print("  dont %d sur les nouvelles unites (M10/M20/M30)."
                  % len(neuves))

    print("-" * LARG)
    print()
    if rafales:
        print("!!! RAFALE DETECTEE !!!")
        for nom, sec, n in rafales:
            print("  %s : %d ouvertures a %s, dans la meme seconde."
                  % (nom, n, sec))
        print()
        print("C est le motif du demarrage a _armed vide : l allumage en")
        print("cours a ete lu comme frais par toutes les cellules a la fois.")
        print("Ces positions ne reposent sur aucun signal.")
        print()
        print("Il ne faut pas analyser, il faut couper -- et se souvenir")
        print("que ces tickets fausseront les statistiques de leur unite")
        print("de temps pendant des semaines si on les laisse dedans.")
        return 2

    if total:
        print("Aucune rafale : %d ouverture(s) sur la fenetre, toutes")
        print("etalees sous le seuil de %d par seconde." % a.seuil)
        print("C est le profil d un demarrage sain -- les cellules")
        print("s allument quand leur unite bascule, pas toutes ensemble.")
    else:
        print("Aucune ouverture du tout sur la fenetre.")
        print()
        print("Hors seance, c est le comportement attendu : la regle de")
        print("session empeche l entree, et c est precisement pourquoi on")
        print("redemarre a ce moment-la.")
        print("En seance, en revanche, une fenetre entierement vide veut")
        print("dire soit qu il ne s est rien passe, soit que le moteur")
        print("n ecrit pas -- verifie l horodatage du fichier avant de")
        print("conclure a la premiere hypothese.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
