# -*- coding: utf-8 -*-
"""
rafraichir_orderflow.py -- l export SierraChart en continu, et son retard

  python rafraichir_orderflow.py
  python rafraichir_orderflow.py --pas 30 --jours 1

POURQUOI

    Le 13/08, l export de C:\\OrderflowExport datait de vingt minutes.
    Trois causes se sont revelees en cascade, et une seule etait la
    bonne :

      1. Aucune boucle ne lance scid_orderflow.py. Il tourne a la main
         ou par tache, republie tout, et se termine. Entre deux passes,
         plus rien ne bouge -- dix minutes de gigue.
      2. --days vaut 14 par defaut : quatorze jours de ticks relus a
         chaque passe. Mesure : --days 1 coute 3,8 secondes.
      3. Et le reste -- exactement 10 min 10 s -- vient du FLUX. Sierra
         l affiche dans l en-tete du graphique : DD: 00:10:10 (delayed).
         Aucun reglage ne le rattrape ; c est l abonnement bourse.

    Cette boucle traite les deux premieres. La troisieme ne se corrige
    pas en Python, mais elle se SURVEILLE -- et c est la seconde raison
    d etre de ce script.

CE QU IL FAIT

    Appelle `scid_orderflow.py --days N` toutes les --pas secondes.
    Rien d autre. Aucun ordre, aucun port, un seul dossier ecrit.

    Puis il lit la derniere barre produite et calcule le RETARD reel,
    en comparant son epoch_utc a l heure courante. Pas de piege de
    fuseau : les deux sont en UTC.

POURQUOI SURVEILLER LE RETARD PLUTOT QUE DE LE SUPPOSER

    Le retard est aujourd hui de ~10 minutes, et c est une donnee
    differee. Trois choses peuvent le changer sans prevenir :

      - un abonnement bourse activé  -> il tombe a quelques secondes,
        et il faut le SAVOIR, parce que tout ce qui etait inexploitable
        devient exploitable ce jour-la ;
      - SierraChart ferme ou deconnecte -> il grandit sans fin, et le
        panneau 8097 continue d afficher des chiffres, simplement de
        plus en plus vieux ;
      - un changement de contrat (YMU26 -> YMZ26) -> le fichier du jour
        reste vide et le retard devient infini.

    Dans les trois cas, rien d autre ne le signalerait. Un panneau qui
    affiche de vieilles donnees ressemble exactement a un panneau qui
    affiche des donnees.

A LANCER en fenetre cachee. Ctrl+C pour arreter.
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
PAS = 30
JOURS = 1
LENT = 15.0          # secondes au-dela desquelles une passe est lente
OUT = r"C:\OrderflowExport"
ACTIF = "US30"       # celui dont on lit le retard
BANDE = 120.0        # variation de retard, en s, au-dela de laquelle on parle


def maintenant():
    return datetime.now().strftime("%H:%M:%S")


def dernier_retard(dossier, actif):
    """(retard en secondes, horodatage de la barre) ou (None, raison).

    Le retard se calcule sur epoch_utc, pas sur `ts` : les deux champs
    coexistent dans le fichier, `ts` est en heure locale et epoch_utc
    en UTC. Comparer `ts` a l heure locale marcherait aujourd hui et
    casserait au changement d heure -- deux fois par an, silencieusement.
    """
    nom = "of_%s_%s.jsonl" % (actif, datetime.now().strftime("%Y-%m-%d"))
    chemin = os.path.join(dossier, nom)
    if not os.path.isfile(chemin):
        return None, "%s absent" % nom
    derniere = None
    try:
        for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
            b = ligne.strip()
            if b.startswith("{"):
                derniere = b
    except IOError as e:
        return None, "illisible : %s" % e
    if derniere is None:
        return None, "%s vide" % nom
    try:
        e = json.loads(derniere)
    except ValueError:
        return None, "derniere ligne illisible"
    ep = e.get("epoch_utc")
    if not ep:
        return None, "pas d epoch_utc"
    # +60 : `ts` est l OUVERTURE de la barre d une minute, elle se ferme
    # une minute plus tard. Sans ca on annonce une minute de retard de
    # moins que la realite.
    return time.time() - float(ep) - 60.0, e.get("ts")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pas", type=int, default=PAS)
    p.add_argument("--jours", type=int, default=JOURS)
    p.add_argument("--dossier", default=OUT)
    p.add_argument("--actif", default=ACTIF)
    a = p.parse_args()

    cible = os.path.join(_ICI, "scid_orderflow.py")
    if not os.path.isfile(cible):
        print("KO : scid_orderflow.py introuvable a cote de ce script.")
        return 1

    print("=" * 72)
    print(" RAFRAICHISSEMENT DE L EXPORT ORDERFLOW")
    print("=" * 72)
    print("intervalle : %d s" % a.pas)
    print("appelle    : scid_orderflow.py --days %d" % a.jours)
    print("ecrit      : %s" % a.dossier)
    print("surveille  : le retard de la derniere barre %s" % a.actif)
    print()
    print("Le retard attendu au 13/08 est de ~10 min : la donnee est")
    print("DIFFEREE (Sierra l affiche, DD: 00:10:10 delayed). Cette")
    print("boucle ne le corrige pas -- elle supprime la gigue des dix")
    print("minutes entre deux passes, et signale si le retard change.")
    print("Aucun ordre. Ctrl+C pour arreter.")
    print()

    n = lents = echecs = 0
    ref = None
    try:
        while True:
            n += 1
            t0 = time.time()
            try:
                r = subprocess.run(
                    [sys.executable, cible, "--days", str(a.jours),
                     "--out-dir", a.dossier],
                    capture_output=True, text=True,
                    timeout=max(120, a.pas * 4), cwd=_ICI)
                code = r.returncode
                fin = (r.stderr or r.stdout or "").strip().split("\n")[-1]
            except subprocess.TimeoutExpired:
                code, fin = -1, "delai depasse"
            except Exception as e:
                code, fin = -2, "%s: %s" % (type(e).__name__, e)
            d = time.time() - t0

            ret, quoi = dernier_retard(a.dossier, a.actif)

            if code != 0:
                echecs += 1
                print("[%s] passe %d ECHEC (code %s) : %s"
                      % (maintenant(), n, code, fin[:120]), flush=True)
            elif ret is None:
                echecs += 1
                print("[%s] passe %d : pas de retard lisible -- %s"
                      % (maintenant(), n, quoi), flush=True)
            else:
                # On ne parle que si le retard BOUGE. Une ligne par passe
                # noierait le seul evenement qui compte.
                if ref is None:
                    ref = ret
                    print("[%s] retard de reference : %.0f s (barre %s)"
                          % (maintenant(), ret, quoi), flush=True)
                    if ret < 120:
                        print("       -- moins de deux minutes : la donnee"
                              " n est PLUS differee.", flush=True)
                elif abs(ret - ref) > BANDE:
                    sens = "TOMBE" if ret < ref else "GRANDI"
                    print("[%s] le retard a %s : %.0f s -> %.0f s"
                          " (barre %s)"
                          % (maintenant(), sens, ref, ret, quoi), flush=True)
                    if ret < 120 <= ref:
                        print("       L ABONNEMENT EST ACTIF. Ce qui etait"
                              " inexploitable devient exploitable :", flush=True)
                        print("       relire regles_gelees_v9 l.178-185,"
                              " la piste US30.", flush=True)
                    ref = ret
                elif d > LENT:
                    lents += 1
                    print("[%s] passe %d lente : %.1f s -- l intervalle de"
                          " %d s deviendra trop court"
                          % (maintenant(), n, d, a.pas), flush=True)
                elif n % 120 == 1:
                    # Une ligne par heure : assez pour prouver qu il vit.
                    print("[%s] passe %d : %.1f s, retard %.0f s"
                          "  (%d echec(s), %d lente(s))"
                          % (maintenant(), n, d, ret, echecs, lents),
                          flush=True)

            reste = a.pas - (time.time() - t0)
            if reste > 0:
                time.sleep(reste)
    except KeyboardInterrupt:
        print()
        print("Arret apres %d passe(s), %d echec(s), %d lente(s)."
              % (n, echecs, lents))
    return 0


if __name__ == "__main__":
    sys.exit(main())
