#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corrige_pont_amortisseur.py -- rc=10025, l oscillation, et l instantane
                                  du compte dedie pour cartes_live.

TROIS CORRECTIFS, UN SEUL ARRET
-------------------------------

1. rc=10025 -- MA COURSE CONTRE LE CACHE DE MT5

   `TRADE_RETCODE_NO_CHANGES` : le courtier repond "cette position a
   deja ce stop". Le controle d idempotence ajoute a 15h lit
   `mt5.positions_get(ticket=...)` et compare avant d envoyer -- s il a
   laisse passer l envoi, c est que la valeur relue n etait pas celle
   que la position portait vraiment. Le cache de positions du terminal
   retarde sur ce qu on vient d y ecrire.

   On tient donc un souvenir EN MEMOIRE du dernier couple (sl, tp)
   reellement accepte pour chaque ticket, et on le croit avant la
   relecture. Et un rc=10025 n est plus traite comme un echec : le
   courtier vient de nous dire que la valeur est en place, on
   l enregistre comme telle au lieu de la redemander.

2. L AMORTISSEUR -- CESSER DE SUIVRE UN STOP QUI FAIT L ALLER-RETOUR

   La source oscille vraiment, et pas de notre fait : le miroir remet
   le stop catastrophe (`SL_FIXE`) pendant qu un autre module le
   descend en profit, plusieurs fois par minute. Le pont recopiait
   fidelement -- donc il recopiait aussi le battement.

   Au-dela de FLAP_SEUIL changements en FLAP_FENETRE secondes sur un
   meme ticket, on gele ce ticket pour FLAP_REPOS secondes : on cesse
   d envoyer, on garde ce qui est en place, on le dit une fois. Au
   degel on se resynchronise sur la valeur courante de la source.

   Ce n est PAS un filtre sur les entrees ni sur les sorties : la copie
   reste conforme sur ce qui compte. C est un plafond de cadence sur
   une modification de stop, et il ne se declenche que sur un battement
   qui est deja une anomalie en amont.

3. L INSTANTANE DU COMPTE, POUR cartes_live

   L envoyeur est le seul processus connecte au terminal dedie -- un
   processus Python, un terminal MT5. Lui seul peut donc rendre compte
   du compte 182109. Il ecrit desormais, toutes les SNAP_PERIODE
   secondes, docs/cartes_live/compte.json : l etat du compte, les
   positions ouvertes, et les affaires closes du jour regroupees par
   position. `cartes_live.py` n a plus qu a le lire, sans jamais
   toucher au terminal.

USAGE
-----
    python corrige_pont_amortisseur.py                 <- simulation
    python corrige_pont_amortisseur.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\pont_miroirs.py"
SUFFIXE_BAK = ".bak_amortisseur"
MARQUEUR = "_DERNIER_STOP = {}"

R = []

# ---------------------------------------------------------------- 1 + 2
VIEUX_STOPS = '''def regler_stops(ticket, sl, tp, reel, etiquette=""):
    """N envoie QUE si notre stop differe deja de la cible.

    Comparer l etat precedent de la source a son etat courant ne suffit
    pas : si une modification echoue on ne la reessaie jamais, et si la
    source oscillait on la suivrait indefiniment. Le seul test qui tienne
    est celui de notre propre position.
    """
    if not reel:
        dire("envoyeur", "  [SIMULATION] %s #%s sl=%.2f tp=%.2f"
             % (etiquette, ticket, sl, tp))
        return True
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return True
    if abs(float(pos[0].sl) - sl) <= EPS and abs(float(pos[0].tp) - tp) <= EPS:
        return True                      # deja a la bonne valeur
    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                        "position": int(ticket), "sl": sl, "tp": tp})
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        dire("envoyeur", "  SL/TP REFUSE #%s rc=%s"
             % (ticket, getattr(r, "retcode", "?")))
        return False
    dire("envoyeur", "  STOPS %s #%s  %.2f -> %.2f"
         % (etiquette, ticket, float(pos[0].sl), sl))
    return True'''

NEUF_STOPS = '''# Le dernier couple (sl, tp) REELLEMENT accepte, par ticket. Il est cru
# avant la relecture : `positions_get` sert un cache qui retarde sur ce
# qu on vient d ecrire, et c est ce retard qui produisait les rc=10025.
_DERNIER_STOP = {}

# Les cibles recentes, par ticket, pour mesurer le battement.
_BATTEMENTS = {}
_GELES = {}

FLAP_FENETRE = 30.0      # s observees
FLAP_SEUIL = 6           # changements de cible au-dela desquels on gele
FLAP_REPOS = 120.0       # s de gel
RC_SANS_CHANGEMENT = 10025


def oublier_stop(ticket):
    """A la fermeture. Le courtier reattribue les numeros de ticket ;
    un souvenir survivant a sa position mentirait sur la suivante."""
    for d in (_DERNIER_STOP, _BATTEMENTS, _GELES):
        d.pop(int(ticket), None)


def bat_trop(ticket, sl, maintenant):
    """Vrai si la cible de ce ticket fait l aller-retour.

    On compte les CHANGEMENTS de cible sur une fenetre glissante. Un
    stop qui progresse normalement en produit quelques-uns par minute ;
    celui qui est dispute par deux modules en produit un par seconde.
    """
    h = [x for x in _BATTEMENTS.get(ticket, [])
         if maintenant - x[0] <= FLAP_FENETRE]
    if not h or abs(h[-1][1] - sl) > EPS:
        h.append((maintenant, sl))
    _BATTEMENTS[ticket] = h
    if len(h) < FLAP_SEUIL:
        return False
    # Un aller-retour, c est peu de valeurs distinctes pour beaucoup de
    # changements. Une progression reguliere en a autant que de pas.
    return len(set(round(x[1], 2) for x in h)) <= 3


def regler_stops(ticket, sl, tp, reel, etiquette=""):
    """N envoie QUE si notre stop differe deja de la cible, et pas plus
    souvent que l amortisseur ne l autorise.

    Trois lignes de defense, dans cet ordre :
      1. le souvenir en memoire de ce qu on a envoye et qui a ete
         accepte -- il ne retarde pas, lui ;
      2. l amortisseur, qui gele un ticket dont la cible bat ;
      3. la relecture de notre position, qui reste utile au demarrage
         et apres un gel, quand le souvenir est vide.
    """
    ticket = int(ticket)
    if not reel:
        dire("envoyeur", "  [SIMULATION] %s #%s sl=%.2f tp=%.2f"
             % (etiquette, ticket, sl, tp))
        return True

    maintenant = time.time()
    fin = _GELES.get(ticket)
    if fin is not None:
        if maintenant < fin:
            return True                  # gele : on ne dit rien de plus
        _GELES.pop(ticket, None)
        _BATTEMENTS.pop(ticket, None)
        dire("envoyeur", "  DEGEL %s #%s : je resynchronise sur %.2f"
             % (etiquette, ticket, sl))

    memo = _DERNIER_STOP.get(ticket)
    if memo is not None and abs(memo[0] - sl) <= EPS \\
            and abs(memo[1] - tp) <= EPS:
        return True                      # deja envoye et accepte

    if bat_trop(ticket, sl, maintenant):
        _GELES[ticket] = maintenant + FLAP_REPOS
        vals = sorted(set(round(x[1], 2) for x in _BATTEMENTS[ticket]))
        dire("envoyeur", "  GEL %s #%s : la source bat entre %s"
             % (etiquette, ticket, " et ".join("%.2f" % v for v in vals)))
        dire("envoyeur", "      %d changements en %.0f s -- je cesse de"
             " suivre pendant %.0f s." % (len(_BATTEMENTS[ticket]),
                                          FLAP_FENETRE, FLAP_REPOS))
        return True

    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        oublier_stop(ticket)
        return True
    avant = float(pos[0].sl)
    if memo is None and abs(avant - sl) <= EPS \\
            and abs(float(pos[0].tp) - tp) <= EPS:
        _DERNIER_STOP[ticket] = (sl, tp)
        return True

    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                        "position": ticket, "sl": sl, "tp": tp})
    rc = getattr(r, "retcode", None)
    if rc == RC_SANS_CHANGEMENT:
        # Le courtier vient de nous dire que la valeur est en place.
        # C est une confirmation, pas un echec.
        _DERNIER_STOP[ticket] = (sl, tp)
        return True
    if r is None or rc != mt5.TRADE_RETCODE_DONE:
        dire("envoyeur", "  SL/TP REFUSE #%s rc=%s" % (ticket, rc))
        return False
    _DERNIER_STOP[ticket] = (sl, tp)
    dire("envoyeur", "  STOPS %s #%s  %.2f -> %.2f"
         % (etiquette, ticket, avant, sl))
    return True'''

R.append((VIEUX_STOPS, NEUF_STOPS, 1))

# ------------------------------------------------------------------- 3
VIEUX_SNAP = '''def envoyeur(args):'''

NEUF_SNAP = '''# L envoyeur est le SEUL processus connecte au terminal dedie -- un
# processus Python, un terminal MT5. Lui seul peut donc rendre compte du
# compte 182109. Il depose un instantane que cartes_live.py lit ; aucun
# autre processus n a besoin de toucher au terminal.
DOSSIER_LIVE = os.path.join(RACINE, "docs", "cartes_live")
COMPTE_JSON = os.path.join(DOSSIER_LIVE, "compte.json")
SNAP_PERIODE = 10.0


def affaires_du_jour():
    """Les affaires closes depuis minuit, regroupees par POSITION.

    Une position close produit plusieurs deals -- l entree, la sortie,
    parfois des partiels. Le resultat d une AFFAIRE est leur somme,
    commissions et swaps compris. Compter les deals compterait deux
    fois chaque trade et donnerait un taux de reussite faux.
    """
    debut = datetime.now().replace(hour=0, minute=0, second=0,
                                   microsecond=0)
    try:
        deals = mt5.history_deals_get(debut, datetime.now())
    except Exception:
        deals = None
    if not deals:
        return []
    par_pos = {}
    for d in deals:
        pid = int(getattr(d, "position_id", 0) or 0)
        if pid == 0:
            continue
        e = par_pos.setdefault(pid, {"position": pid, "magic": 0, "sym": "",
                                     "resultat": 0.0, "volume": 0.0,
                                     "ts": 0, "sorti": False})
        e["resultat"] += (float(getattr(d, "profit", 0.0))
                          + float(getattr(d, "commission", 0.0))
                          + float(getattr(d, "swap", 0.0)))
        m = int(getattr(d, "magic", 0) or 0)
        if m:
            e["magic"] = m
        s = getattr(d, "symbol", "") or ""
        if s:
            e["sym"] = s
        t = int(getattr(d, "time", 0) or 0)
        if t > e["ts"]:
            e["ts"] = t
        # entry 1 = OUT, 2 = INOUT, 3 = OUT_BY : l affaire est soldee.
        if int(getattr(d, "entry", 0) or 0) in (1, 2, 3):
            e["sorti"] = True
            e["volume"] += float(getattr(d, "volume", 0.0))
    return [v for v in par_pos.values() if v["sorti"]]


def ecrire_compte():
    """Depose l instantane du compte dedie. Jamais bloquant : une
    ecriture qui echoue ne doit pas interrompre la copie."""
    try:
        ai = mt5.account_info()
        if ai is None:
            return
        ouvertes = []
        for p in (mt5.positions_get() or []):
            ouvertes.append({
                "ticket": int(p.ticket), "magic": int(p.magic),
                "sym": p.symbol, "sens": int(p.type),
                "volume": float(p.volume), "prix": float(p.price_open),
                "sl": float(p.sl), "tp": float(p.tp),
                "latent": float(p.profit), "ts": int(p.time)})
        paquet = {"ts": time.time(),
                  "compte": {"login": int(ai.login), "serveur": ai.server,
                             "devise": ai.currency,
                             "solde": float(ai.balance),
                             "equite": float(ai.equity),
                             "marge": float(ai.margin),
                             "niveau": float(ai.margin_level or 0.0)},
                  "ouvertes": ouvertes,
                  "closes": affaires_du_jour()}
        if not os.path.isdir(DOSSIER_LIVE):
            os.makedirs(DOSSIER_LIVE)
        ecrire_atomique(COMPTE_JSON, paquet)
    except Exception:
        pass


def envoyeur(args):'''

R.append((VIEUX_SNAP, NEUF_SNAP, 1))

# -- purge du souvenir a la fermeture
R.append(('''                        if fermer(_tk(lien), a["sym"], a["sens"], None,
                                  args.reel):
                            liens.pop(tk, None)
                            ecrire_atomique(LIENS, liens)''',
          '''                        if fermer(_tk(lien), a["sym"], a["sens"], None,
                                  args.reel):
                            oublier_stop(_tk(lien))
                            liens.pop(tk, None)
                            ecrire_atomique(LIENS, liens)''', 1))

# -- l instantane dans la boucle
# L ancre se pose sur le DEBUT DE BOUCLE, pas sur la ligne qui la
# precede. Le 25/08 ce motif exigeait `dernier_battement = time.time()`
# et `while True:` colles ; le fichier deploye porte une ligne
# `plainte = 0.0` entre les deux, et le correctif a refuse. Une ancre
# qui suppose son voisinage est une ancre qui casse.
R.append(('''        while True:
            time.sleep(PERIODE)
            paquet = lire_json(INSTANTANE)''',
          '''        dernier_instantane = 0.0
        ecrire_compte()
        while True:
            time.sleep(PERIODE)
            paquet = lire_json(INSTANTANE)''', 1))

R.append(('''            precedent = courant
            if time.time() - dernier_battement >= 300:''',
          '''            precedent = courant
            if time.time() - dernier_instantane >= SNAP_PERIODE:
                dernier_instantane = time.time()
                ecrire_compte()
            if time.time() - dernier_battement >= 300:''', 1))


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print("corrige_pont_amortisseur -- %s"
          % ("APPLIQUER" if args.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(args.cible):
        print("introuvable : %s" % args.cible)
        return 2
    s = lire(args.cible)
    print("cible : %s  (%d lignes)" % (args.cible, s.count("\n") + 1))

    if MARQUEUR in s:
        print("")
        print("Deja corrige : _DERNIER_STOP est present.")
        return 0
    if "def niveau_projete(" not in s:
        print("")
        print("REFUS : corrige_marge_pont n a pas ete applique avant.")
        return 1
    if "from datetime import datetime" not in s:
        print("")
        print("REFUS : datetime n est pas importe dans ce fichier.")
        print("L instantane en a besoin. Je ne l ajoute pas moi-meme :")
        print("un import pose au mauvais endroit est un defaut silencieux.")
        return 1

    for i, (vieux, _n, att) in enumerate(R, 1):
        c = s.count(vieux)
        if c != att:
            print("")
            print("REFUS : motif %d attendu %d fois, trouve %d." % (i, att, c))
            print("   %s..." % vieux.strip().split("\n")[0][:56])
            return 1
    print("        les %d motifs sont la, aux bons comptes." % len(R))
    print("")
    print("a faire :")
    print("   + _DERNIER_STOP : le souvenir de ce qui a ete accepte")
    print("   ~ rc=10025 lu comme une confirmation, plus comme un echec")
    print("   + amortisseur : gel %s s au-dela de %s changements en %s s"
          % (120, 6, 30))
    print("   + docs/cartes_live/compte.json, ecrit toutes les 10 s")

    if not args.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = args.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(args.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)

    for vieux, neuf, _a in R:
        s = s.replace(vieux, neuf, 1)
    with io.open(args.cible, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print("ecrit : %s" % args.cible)

    relu = lire(args.cible)
    manques = [x for x in (MARQUEUR, "def bat_trop(", "def ecrire_compte(",
                           "RC_SANS_CHANGEMENT", "oublier_stop(_tk(lien))",
                           "dernier_instantane")
               if x not in relu]
    if manques:
        print("relu   : INCOMPLET, manque %s -- restaurer %s"
              % (", ".join(manques), bak))
        return 1
    print("relu   : les six marques attendues sont presentes.")
    try:
        compile(relu, args.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1

    print("")
    print("-" * 66)
    print("Relancer le pont. Les positions ouvertes gardent leur lien.")
    print("Le journal doit devenir silencieux sur les stops : plus de")
    print("rc=10025, et une ligne GEL au lieu de cent lignes STOPS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
