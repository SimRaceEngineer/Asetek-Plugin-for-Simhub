#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bilan_c14.py -- ce que le veto C14 a coute, ou rapporte, en euros

  python bilan_c14.py --jours 5
  python bilan_c14.py --jour 2026-08-25
  python bilan_c14.py --jours 21 --actif US100

LA QUESTION
-----------
buddha_clause_gate refuse 99 % des deplacements de stop, et la totalite
des refus mesures portaient sur un stop qui VERROUILLAIT UN GAIN. Le
gate a une raison : ne pas mettre au breakeven trop tot, sous peine de
sortir a +0.3 pendant que la tendance continue. Cette raison peut etre
juste. Elle se mesure.

CE QU ON REJOUE
---------------
Pour chaque position dont un verrouillage a ete refuse, on reconstitue
la SUITE des niveaux que les modules ont reclames au fil de la vie de
la position, on la rend monotone -- un stop qui ne recule jamais, le
cliquet demande -- et on l applique barre M1 par barre M1, chaque
niveau ne prenant effet qu a partir de la barre SUIVANT l instant ou
il a ete demande.

Puis on compare la sortie obtenue a la sortie reelle.

CE QUI REND LA MESURE HONNETE
-----------------------------
Elle compte dans les DEUX SENS. Quand le verrou se declenche et que la
position finissait plus bas, il a sauve de l argent. Quand il se
declenche sur un repli passager d une position qui finissait plus
haut, il en a coute. Les deux entrent dans le total.

C est la difference avec une simulation par MFE, qui ne voit que les
economies et jamais les sorties prematurees. Ce matin cette confusion
m a fait annoncer +7 750 EUR sur un trail la ou le chemin reel disait
-7 408 : le signe lui-meme etait faux. On ne recommence pas.

CE QU ELLE NE MODELISE PAS, ET IL FAUT LE SAVOIR
------------------------------------------------
  - le spread : une sortie au stop se fait au bid pour un achat, on
    suppose l execution au niveau exact. Ecart optimiste de l ordre
    d un demi-point par trade.
  - le capital libere par une sortie anticipee, qui aurait pu
    reprendre une position ailleurs. Non compte, dans aucun sens.
  - les gaps : un stop peut etre execute plus bas que son niveau.
    Rare en seance sur ces trois actifs, reel a l ouverture.

Elle LIT l historique et les barres. Elle n envoie aucun ordre, ne
modifie aucune position, ne touche a aucun fichier du depot.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta

RACINE_DEFAUT = r"C:\SVPS\Scalp-EA-main"
SOUS_DOSSIER = os.path.join("docs", "buddha_clause_gate")

# Champs ou peut se cacher l horodatage d un blocage.
CLES_TS = ("ts", "time", "timestamp", "when", "dt", "date", "heure", "t")
DECALAGES = (7200, 3600, 0, 10800, -3600, -7200)

_dec_ok = [None]        # decalage de requete retenu, mesure une fois


# ------------------------------------------------------------------ outils

def titre(t):
    print("")
    print("=" * 74)
    print(t)
    print("=" * 74)


def epoch(v):
    """Un horodatage sous n importe quelle forme -> secondes, ou None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return x / 1000.0 if x > 1e11 else x      # millisecondes ?
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s) if s.replace(".", "", 1).isdigit() else None
    except Exception:
        pass
    for f in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
              "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
              "%Y/%m/%d %H:%M:%S", "%H:%M:%S"):
        try:
            d = datetime.strptime(s[:26], f)
            if f == "%H:%M:%S":
                return None                        # heure seule : inutilisable
            return time.mktime(d.timetuple())
        except Exception:
            continue
    return None


def cle_ts(rec):
    for k in CLES_TS:
        if k in rec and epoch(rec[k]) is not None:
            return k
    return None


# --------------------------------------------------------- lecture des blocs

def jours_dispo(racine):
    d = os.path.join(racine, SOUS_DOSSIER)
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d)
                  if os.path.isdir(os.path.join(d, n)) and n[:2] == "20")


def lit_blocs(racine, jours, actif=None):
    """{ticket: {...}} -- un enregistrement par position, niveaux agreges."""
    par_tk, nb, sans_ts, kts = {}, 0, 0, None
    for j in jours:
        chemin = os.path.join(racine, SOUS_DOSSIER, j, "blocks.jsonl")
        if not os.path.exists(chemin):
            continue
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    r = json.loads(ligne)
                except Exception:
                    continue
                if "C14" not in str(r.get("blocked_by", "")):
                    continue
                tk = r.get("ticket")
                sl = r.get("new_sl")
                if not tk or not sl:
                    continue
                if actif and str(r.get("asset")) != actif:
                    continue
                nb += 1
                if kts is None:
                    kts = cle_ts(r)
                ts = epoch(r.get(kts)) if kts else None
                if ts is None:
                    sans_ts += 1
                e = par_tk.setdefault(int(tk), {
                    "ticket": int(tk), "asset": r.get("asset"),
                    "magic": r.get("magic"), "pos_dir": r.get("pos_dir"),
                    "entry": float(r.get("entry") or 0.0),
                    "biais": {}, "niveaux": [], "jour": j, "refus": 0})
                e["refus"] += 1
                b = str(r.get("buddha_bias", "?"))
                e["biais"][b] = e["biais"].get(b, 0) + 1
                e["niveaux"].append((ts, float(sl)))
    return par_tk, nb, sans_ts, kts


def suite_monotone(niveaux, sens):
    """Les niveaux dans l ordre du temps, rendus monotones : le cliquet.

    Un niveau sans horodatage est place en tete : il ne peut alors
    s activer qu a partir de la premiere barre, ce qui est le choix
    le plus prudent qu on puisse faire sans savoir quand il fut demande.
    """
    avec = sorted([(t, v) for t, v in niveaux if t is not None])
    sans = [v for t, v in niveaux if t is None]
    out = []
    if sans:
        d = max(sans) if sens > 0 else min(sans)
        out.append((0.0, d))
    courant = None
    for t, v in avec:
        if courant is None:
            courant = v
        else:
            courant = max(courant, v) if sens > 0 else min(courant, v)
        if not out or out[-1][1] != courant:
            out.append((t, courant))
    return out


# ------------------------------------------------------------------ MT5

def deals_fenetre(mt5, t0, t1):
    """Tous les deals de la fenetre, regroupes par position. Un seul appel."""
    d0 = datetime.utcfromtimestamp(t0)
    d1 = datetime.utcfromtimestamp(t1)
    try:
        mt5.history_select(d0, d1)
    except Exception:
        pass
    lot = mt5.history_deals_get(d0, d1)
    if lot is None:
        return {}
    par_pos = {}
    for d in lot:
        par_pos.setdefault(int(d.position_id), []).append(d)
    return par_pos


def resume_position(mt5, deals):
    """(sens, entree, sortie, volume, profit, t_ouv, t_fer, symbole) ou None."""
    ins = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
    outs = [d for d in deals if d.entry in (mt5.DEAL_ENTRY_OUT,
                                            mt5.DEAL_ENTRY_OUT_BY)]
    if not ins or not outs:
        return None
    vin = sum(float(d.volume) for d in ins) or 1.0
    entree = sum(float(d.price) * float(d.volume) for d in ins) / vin
    vout = sum(float(d.volume) for d in outs) or 1.0
    sortie = sum(float(d.price) * float(d.volume) for d in outs) / vout
    profit = sum(float(d.profit) for d in outs)
    sens = 1 if ins[0].type == mt5.DEAL_TYPE_BUY else -1
    return (sens, entree, sortie, vout, profit,
            min(int(d.time) for d in ins), max(int(d.time) for d in outs),
            ins[0].symbol)


def barres(mt5, sym, t0, t1):
    """Les M1 couvrant [t0, t1]. Le decalage de requete est MESURE.

    Rappel du 25/08 : le decalage a appliquer a la REQUETE et la base des
    horodatages RENVOYES sont deux questions differentes. On essaie donc
    les decalages jusqu a en trouver un qui ramene des barres dont les
    horodatages recouvrent vraiment la fenetre demandee.
    """
    essais = ([_dec_ok[0]] if _dec_ok[0] is not None else []) + list(DECALAGES)
    for dec in essais:
        if dec is None:
            continue
        try:
            r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1,
                                     datetime.utcfromtimestamp(t0 - 120 + dec),
                                     datetime.utcfromtimestamp(t1 + 120 + dec))
        except Exception:
            continue
        if r is None or len(r) == 0:
            continue
        deb, fin = int(r[0]["time"]), int(r[-1]["time"])
        if fin >= t0 - 600 and deb <= t1 + 600:
            _dec_ok[0] = dec
            return [b for b in r if t0 - 120 <= int(b["time"]) <= t1 + 120]
    return []


def rejoue(bars, sens, suite):
    """(niveau touche, horodatage) ou (None, None).

    Convention : dans une barre, l extreme defavorable est suppose venir
    APRES le favorable. C est le pire cas pour un stop, donc le choix
    prudent. Un niveau ne s active qu a la barre SUIVANT sa demande, pour
    ne pas le declencher sur le creux de la minute ou il fut reclame.
    """
    i, actif = 0, None
    for b in bars:
        t = int(b["time"])
        while i < len(suite) and suite[i][0] < t:
            actif = suite[i][1]
            i += 1
        if actif is None:
            continue
        if sens > 0:
            if float(b["low"]) <= actif:
                return actif, t
        else:
            if float(b["high"]) >= actif:
                return actif, t
    return None, None


# ------------------------------------------------------------------ mesure

def tableau(titre_, lignes, entetes):
    print("")
    print("  " + titre_)
    print("  " + "-" * 68)
    print("  " + entetes)
    for l in lignes:
        print("  " + l)


def agrege(res, cle):
    d = {}
    for r in res:
        k = str(r[cle])
        s = d.setdefault(k, {"n": 0, "touche": 0, "eur": 0.0})
        s["n"] += 1
        if r["touche"]:
            s["touche"] += 1
            s["eur"] += r["eur"]
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--racine", default=RACINE_DEFAUT)
    ap.add_argument("--jours", type=int, default=5)
    ap.add_argument("--jour", default=None, help="un jour precis AAAA-MM-JJ")
    ap.add_argument("--actif", default=None)
    a = ap.parse_args()

    dispo = jours_dispo(a.racine)
    if not dispo:
        print("aucun dossier %s dans %s" % (SOUS_DOSSIER, a.racine))
        return 2
    jours = [a.jour] if a.jour else dispo[-a.jours:]

    print("bilan_c14 -- %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("jours lus : %s" % ", ".join(jours))

    par_tk, nb, sans_ts, kts = lit_blocs(a.racine, jours, a.actif)
    print("refus C14 lus       : %d" % nb)
    print("positions concernees: %d" % len(par_tk))
    print("champ horodatage    : %s" % (kts or "AUCUN"))
    if kts is None:
        print("  -> sans horodatage, chaque niveau est applique des la premiere")
        print("     barre. C est le choix le plus prudent possible, mais il")
        print("     avantage le verrou : lire le resultat comme une borne.")
    elif sans_ts:
        print("  refus sans horodatage exploitable : %d" % sans_ts)
    if not par_tk:
        return 0

    try:
        import MetaTrader5 as mt5
    except Exception as e:
        print("MetaTrader5 indisponible : %s" % e)
        return 2
    if not mt5.initialize():
        print("mt5.initialize a echoue : %s" % (mt5.last_error(),))
        return 2

    d0 = datetime.strptime(jours[0], "%Y-%m-%d") - timedelta(days=2)
    t0 = time.mktime(d0.timetuple())
    t1 = time.time() + 86400
    print("")
    print("lecture de l historique des deals...")
    par_pos = deals_fenetre(mt5, t0, t1)
    print("positions trouvees dans l historique : %d" % len(par_pos))

    res, ouvertes, introuvables, sans_bars, sans_euro = [], 0, 0, 0, 0
    for tk, e in sorted(par_tk.items()):
        dl = par_pos.get(tk)
        if not dl:
            introuvables += 1
            continue
        r = resume_position(mt5, dl)
        if r is None:
            ouvertes += 1
            continue
        sens, entree, sortie, vol, profit, t_ouv, t_fer, sym = r
        bars = barres(mt5, sym, t_ouv, t_fer)
        if not bars:
            sans_bars += 1
            continue
        suite = suite_monotone(e["niveaux"], sens)
        if not suite:
            continue
        niveau, t_stop = rejoue(bars, sens, suite)

        # euros par point, calibres sur le trade lui-meme : pas de table
        # de contrats a tenir a jour, et c est juste par construction.
        amp = (sortie - entree) * sens
        eur_pt = (profit / amp) if abs(amp) > 1e-9 else None
        if eur_pt is None:
            sans_euro += 1
        pts = ((niveau - sortie) * sens) if niveau is not None else 0.0
        res.append({
            "ticket": tk, "asset": e["asset"], "magic": e["magic"],
            "biais": max(e["biais"], key=lambda k: e["biais"][k]),
            "sens": "BUY" if sens > 0 else "SELL", "refus": e["refus"],
            "entree": entree, "sortie": sortie, "profit": profit,
            "touche": niveau is not None, "niveau": niveau,
            "pts": pts, "eur": (pts * eur_pt) if eur_pt else 0.0})

    mt5.shutdown()

    titre("COUVERTURE")
    print("positions rejouees            : %d" % len(res))
    print("  introuvables dans l historique: %d" % introuvables)
    print("  encore ouvertes               : %d" % ouvertes)
    print("  sans barres M1                : %d" % sans_bars)
    print("  sans conversion en euros      : %d" % sans_euro)
    if not res:
        print("rien a mesurer.")
        return 0

    touchees = [r for r in res if r["touche"]]
    sauve = [r for r in touchees if r["eur"] > 0]
    coute = [r for r in touchees if r["eur"] < 0]
    tot = sum(r["eur"] for r in touchees)

    titre("RESULTAT -- ce que le verrou refuse aurait fait")
    print("positions rejouees        : %d" % len(res))
    print("le verrou se declenche    : %d  (%.0f %%)"
          % (len(touchees), 100.0 * len(touchees) / len(res)))
    print("il ne se declenche jamais : %d  -- ces positions finissent a l identique"
          % (len(res) - len(touchees)))
    print("")
    print("  argent SAUVE   : %+9.2f EUR  sur %d positions" %
          (sum(r["eur"] for r in sauve), len(sauve)))
    print("  argent COUTE   : %+9.2f EUR  sur %d positions" %
          (sum(r["eur"] for r in coute), len(coute)))
    print("  " + "-" * 46)
    print("  NET            : %+9.2f EUR   soit %+.2f EUR par position rejouee"
          % (tot, tot / len(res)))
    print("")
    if tot > 0:
        print("  Positif : laisser passer ces verrouillages aurait rapporte.")
        print("  Le veto C14 coute donc de l argent sur cette periode.")
    else:
        print("  Negatif : ces verrouillages auraient coute. Le veto C14")
        print("  protege bien contre des sorties prematurees, et il faut")
        print("  le garder.")

    for cle, nom in (("asset", "PAR ACTIF"), ("biais", "PAR AVIS DE BUDDHA"),
                     ("sens", "PAR SENS")):
        d = agrege(res, cle)
        lignes = ["%-10s %6d %8d %12.2f" % (k, v["n"], v["touche"], v["eur"])
                  for k, v in sorted(d.items(), key=lambda x: x[1]["eur"])]
        tableau(nom, lignes, "%-10s %6s %8s %12s" % ("", "n", "touche", "EUR"))

    d = agrege(res, "magic")
    top = sorted(d.items(), key=lambda x: x[1]["eur"])[:12]
    tableau("PAR MAGIC -- les douze plus penalisants",
            ["%-10s %6d %8d %12.2f" % (k, v["n"], v["touche"], v["eur"])
             for k, v in top],
            "%-10s %6s %8s %12s" % ("magic", "n", "touche", "EUR"))

    ext = sorted(touchees, key=lambda r: r["eur"])
    # Sous douze cas, les deux bouts se recouvrent : on ne montre pas deux
    # fois la meme ligne, un doublon se lit comme deux positions.
    choix = ext if len(ext) <= 12 else (ext[:6] + ext[-6:])
    lignes = []
    for r in choix:
        lignes.append("%-7s %-5s M%-8s sortie %10.2f  verrou %10.2f  %+8.1f pt  %+9.2f"
                      % (r["asset"], r["sens"], r["magic"], r["sortie"],
                         r["niveau"], r["pts"], r["eur"]))
    tableau("LES DOUZE CAS EXTREMES, dans les deux sens", lignes,
            "actif   sens  magic      sortie reelle   verrou       ecart")

    print("")
    print("  Rappel des limites : spread non modelise (une sortie au stop se")
    print("  fait au bid pour un achat, on suppose le niveau exact), capital")
    print("  libere par une sortie anticipee non compte, gaps non modelises.")
    print("  Rien n a ete modifie, aucun ordre envoye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
