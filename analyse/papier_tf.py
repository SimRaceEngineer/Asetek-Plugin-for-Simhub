# -*- coding: utf-8 -*-
"""
papier_tf.py -- x10 x20 x30 x60 x120 x240 en papier, 24h/24, bras 206 et 207

  python papier_tf.py --loop            l observateur, en continu
  python papier_tf.py --rapport         le releve
  python papier_tf.py --loop --pas 20

AUCUN ORDRE. JAMAIS. C EST LA SEULE CHOSE A RETENIR.

    Ce module appelle six fonctions de MetaTrader5 : initialize,
    account_info, symbol_info, symbol_info_tick, copy_rates_from_pos,
    shutdown. Aucune ne peut envoyer, modifier ni fermer quoi que ce
    soit. order_send n apparait nulle part -- c est une ligne de grep.

    Il tourne A COTE d ignition_trader, il ne le remplace pas et ne le
    touche pas. Il n importe pas ignition_trader non plus : ce module
    demarre un thread qui TRADE des l import.

LA REGLE EST CELLE DE LA PRODUCTION, PAS UNE IMITATION

    ignition_trader.py, recu le 12/08, donne la mecanique exacte. Elle
    est reprise ici telle quelle :

      entree   ignition FRAICHE de churn_regime -- ign=True ET dir
               change depuis la derniere consommee. Un flip BULL->BEAR
               est frais meme si `ignition` n est jamais retombe a
               False (correctif du 17/07 dans le fichier d origine).
      filtre   RSI(14) M3 : un BUY exige RSI > 50, un SELL RSI < 50.
               Fail-open si le RSI est indisponible. C est l ENFORCE
               du 20/07, il s applique aux deux bras.
      SL       filet fixe, JAMAIS traile : US30 4000, US500 200,
               US100 1600 points d indice.
      lot      balance / 20000, minimum 0.10 -- meme formule, pour que
               les EUR se comparent aux tickets reels.
      206      hold jusqu a l ignition inverse, qui ferme et ouvre
               l oppose. Meme sens pendant qu on tient = HOLD, pas de
               pyramide.
      207      MEMES ENTREES que le 206 -- c est un A/B de la SORTIE.
               Au premier break de la bougie M2 precedente, EN PROFIT
               seulement, on coupe 70 % du VOLUME, une seule fois par
               position. Les 30 % restants tiennent jusqu au reverse.
               Break : pour un BUY, bid < low(M2 precedente) - buffer ;
               miroir pour un SELL. Buffer US30 15, US500 2, US100 10.
      SKIP_REJECT = False, comme en production : on suit TOUTE
               ignition, y compris en contexte mtf REJECT.

    LE TRAIL DU 207 EST EN M2 QUELLE QUE SOIT LA DUREE DE LA CELLULE.
    C est ce que fait le fichier d origine -- une constante, pas une
    fonction de la cellule -- et c est repris tel quel. Il faut s y
    attendre en lisant les chiffres : une bougie M2 casse vite, donc
    sur H2 et H4 les 70 % partiront presque toujours tres tot. Si les
    longues durees ressortent mauvaises du cote 207 et bonnes du cote
    206, ce sera ca, et pas le marche. Tester un trail indexe sur la
    duree de la cellule serait le pas suivant -- mais ce ne serait
    plus la regle de production.

    LE SIGNAL VIENT DE churn_regime._analyze, LE VRAI. Pas d une
    reconstruction. Le fichier d origine le fait deja pour le M2, que
    churn ne calcule pas, et note que _analyze est offset-invariant
    (WaveTrend + RSI = du momentum, pas un niveau) donc valable sur des
    barres CFD de n importe quelle unite. C est exactement ce qui rend
    x10, x20, x30, x120 et x240 possibles sans toucher a une virgule
    de la logique.

    Sans churn_regime, ce module REFUSE de tourner. Un signal approche
    donnerait des chiffres qu on croirait comparables et qui ne le
    seraient pas.

CE QUI RESTE INCONNU, ET IL FAUT LE SAVOIR EN LISANT LES CHIFFRES

    1. Les deux traders sont lus, 206 et 207. Aucune regle n est
       inventee ici. Ce qui reste inconnu est churn_regime lui-meme :
       on l APPELLE sans savoir ce qu il calcule, ce qui est exactement
       ce qu il faut pour ne pas le deformer.

    2. En production, le H1 lit la cellule de churn.get_churn(asset).
       Ici les six durees passent toutes par _analyze sur des barres
       locales -- sinon H1 serait calcule autrement que ses cinq
       voisins et la comparaison entre durees, qui est tout l objet du
       module, ne voudrait rien dire. Le H1 papier peut donc differer
       du H1 reel a la marge.

    3. Le fichier d origine coupe la session a 19:30 (SESSION_STOP),
       meme si son commentaire mentionne 19:50. C est 19:30 qui fait
       foi ici, parce que c est le code qui tourne.

LES HORAIRES, ET POURQUOI DEUX COLONNES

    La production ne trade qu entre 08:00 et 19:30, en semaine, et
    ferme tout en dehors. Ici on entre 24h/24, mais chaque trade porte
    son creneau d entree :

        SEANCE   08:00-19:30 en semaine -- ferme a 19:30 comme en
                 production, donc directement comparable
        HORS     tout le reste -- pas de flat, il vit jusqu a sa regle
                 de sortie, son SL, ou MAX_H heures

    Sans cette separation, un gain nocturne se melangerait aux gains
    de seance et on croirait avoir ameliore la production alors qu on
    aurait seulement trade quand elle dort.

FICHIERS

    docs/papier_tf/trades.jsonl   un trade papier ferme par ligne
    docs/papier_tf/etat.json      les positions ouvertes, pour survivre
                                  a un redemarrage sans les perdre
"""
import argparse
import io
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

# churn_regime porte le signal. On ne l imite pas : on l appelle.
try:
    import churn_regime as _chr
except ImportError:
    _chr = None

# Les memes que dans ignition_trader.py, recopies pour ne rien deduire.
LOGIN = 178780
SL_FIXE = {"US30": 4000.0, "US500": 200.0, "US100": 1600.0}
ACTIFS = (("US30", "1", "US30"),
          ("US500", "2", "SPX500"),
          ("US100", "3", "NAS100"))
SESSION_DEBUT, SESSION_FIN = 8 * 60, 19 * 60 + 30
SKIP_REJECT = False

DUREES = (10, 20, 30, 60, 120, 240)
BRAS = ("206", "207")
# Le trail du 207, tel qu il est ecrit dans ignition_trader_trail.py :
# 70 % du VOLUME au premier break de la bougie M2 precedente, en profit
# seulement, une fois par position. Le M2 est une constante du fichier
# d origine, pas une fonction de la cellule -- garde tel quel.
TRAIL_PART = 0.70
TRAIL_BUFFER = {"US30": 15.0, "US500": 2.0, "US100": 10.0}
BARRES = 200          # ce que _analyze recoit dans ignition_trader
PAS = 20
MAX_H = 24
VEILLE_MIN = 10

DOSSIER = os.path.join(_ICI, "docs", "papier_tf")
TRADES = os.path.join(DOSSIER, "trades.jsonl")
ETAT = os.path.join(DOSSIER, "etat.json")
LARG = 100


def maintenant():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def libelle(mn):
    if mn < 60:
        return "M%d" % mn
    return "H%d" % (mn // 60) if mn % 60 == 0 else "%dmn" % mn


def en_session(d=None):
    d = d or datetime.now()
    if d.weekday() >= 5:
        return False
    return SESSION_DEBUT <= d.hour * 60 + d.minute < SESSION_FIN


def creneau(d=None):
    return "SEANCE" if en_session(d) else "HORS"


def tf_mt5(mn):
    """Minutes -> constante MetaTrader5. None si le terminal ne connait
    pas cette unite : on le dit, on ne prend pas la voisine."""
    nom = ("TIMEFRAME_M%d" % mn) if mn < 60 else ("TIMEFRAME_H%d" % (mn // 60))
    return getattr(mt5, nom, None) if mt5 else None


def cle(bras, code, mn):
    return ("%s%s%02d" % (bras, code, mn) if mn < 100
            else "%s%s%d" % (bras, code, mn))


def ecrire_trade(obj):
    if not os.path.isdir(DOSSIER):
        os.makedirs(DOSSIER)
    with io.open(TRADES, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def charger_trades():
    if not os.path.isfile(TRADES):
        return []
    out = []
    for l in io.open(TRADES, encoding="utf-8", errors="replace"):
        l = l.strip()
        if not l or l[0] != "{":
            continue
        try:
            out.append(json.loads(l))
        except ValueError:
            continue
    return out


def lire_etat():
    if not os.path.isfile(ETAT):
        return {}
    try:
        return json.load(io.open(ETAT, encoding="utf-8"))
    except (ValueError, IOError):
        return {}


def ecrire_etat(etat):
    if not os.path.isdir(DOSSIER):
        os.makedirs(DOSSIER)
    tmp = ETAT + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(
        json.dumps(etat, ensure_ascii=False, indent=1))
    if os.path.exists(ETAT):
        os.remove(ETAT)
    os.rename(tmp, ETAT)


# ----------------------------------------------------- le signal, le vrai

def cellule(sym, tf):
    """_analyze de churn_regime sur des barres locales. C est ce que
    ignition_trader fait deja pour le M2 : meme fonction, meme nombre
    de barres. Rien n est reimplemente ici."""
    try:
        bars = mt5.copy_rates_from_pos(sym, tf, 0, BARRES)
        if bars is None or len(bars) < 40:
            return None
        return _chr._analyze(bars)
    except Exception:
        return None


def rsi_m3(sym):
    """RSI(14) sur la derniere close M3, via _rsi_series de churn_regime.
    None -> fail-open, comme en production."""
    try:
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M3, 0, 60)
        if r is None or len(r) < 20:
            return None
        serie = _chr._rsi_series([float(x["close"]) for x in r], 14)
        return float(serie[-1]) if serie else None
    except Exception:
        return None


def rsi_bloque(sym, sens):
    """(bloque, rsi). ENFORCE du 20/07 : un BUY exige RSI M3 > 50, un
    SELL RSI M3 < 50."""
    v = rsi_m3(sym)
    if v is None:
        return False, None
    if sens == "BUY" and v <= 50.0:
        return True, v
    if sens == "SELL" and v >= 50.0:
        return True, v
    return False, v


def lot_de(sym, balance):
    brut = max(0.10, balance / 20000.0)
    try:
        si = mt5.symbol_info(sym)
        pas_v = si.volume_step or 0.01
        vmin = si.volume_min or 0.10
        return max(vmin, round(round(brut / pas_v) * pas_v, 2))
    except Exception:
        return round(brut, 2)


def valeur_point(sym):
    """EUR par unite de prix et par lot. Sans elle on compterait en
    points, et un point d US30 ne vaut pas un point de NAS100."""
    info = mt5.symbol_info(sym)
    if info is None or not info.trade_tick_size:
        return None
    return info.trade_tick_value / info.trade_tick_size


# ------------------------------------------------------------ observateur

def ouvrir(ouvertes, k, c, prix, sens, lot):
    ouvertes[k] = {"k": k, "bras": c["bras"], "actif": c["actif"],
                   "mn": c["mn"], "sens": 1 if sens == "BUY" else -1,
                   "entree": prix, "ts": maintenant(), "t0": time.time(),
                   "creneau": creneau(), "mfe": 0.0, "mae": 0.0,
                   "vp": c["vp"], "lot": lot, "reste": lot,
                   "partiel": False, "id": "%s@%s" % (k, maintenant()),
                   "sl": SL_FIXE.get(c["actif"], 0.0)}
    print("[%s] OUVRE  %-8s %-5s %-6s %-5s a %.2f  lot %.2f"
          % (maintenant()[11:], k, libelle(c["mn"]), c["actif"], sens,
             prix, lot))


def _jambe(p, prix, volume, motif):
    """Une sortie, totale ou partielle. Le 207 en produit deux : les
    70 % au break M2, puis les 30 % au reverse. Elles portent le meme
    `id` pour que le rapport compte des ENTREES et pas des morceaux."""
    pts = (prix - p["entree"]) * p["sens"]
    ecrire_trade({"quoi": "TRADE", "ts": maintenant(), "ouvert": p["ts"],
                  "id": p["id"], "k": p["k"], "bras": p["bras"],
                  "actif": p["actif"], "mn": p["mn"], "sens": p["sens"],
                  "creneau": p["creneau"], "entree": round(p["entree"], 2),
                  "sortie": round(prix, 2), "points": round(pts, 2),
                  "eur": round(pts * p["vp"] * volume, 2),
                  "mfe": round(p["mfe"] * p["vp"] * volume, 2),
                  "mae": round(p["mae"] * p["vp"] * volume, 2),
                  "minutes": int((time.time() - p["t0"]) / 60),
                  "motif": motif, "lot": round(volume, 2)})
    print("[%s] %-9s %-8s %-5s %-6s %+9.2f pts  %5d mn  lot %.2f"
          % (maintenant()[11:], motif, p["k"], libelle(p["mn"]), p["actif"],
             pts, int((time.time() - p["t0"]) / 60), volume))


def partiel(p, sym, prix):
    """Le trail du 207 : au premier break de la bougie M2 PRECEDENTE, en
    profit seulement, on coupe TRAIL_PART du volume, une seule fois.
    Un perdant n est jamais partialise -- soit gain partiel, soit SL."""
    if p["partiel"] or p["bras"] != "207":
        return False
    if (prix - p["entree"]) * p["sens"] <= 0:
        return False
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M2, 1, 1)
    if r is None or len(r) == 0:
        return False
    buf = TRAIL_BUFFER.get(p["actif"], 0.0)
    casse = ((p["sens"] > 0 and prix < float(r[0]["low"]) - buf)
             or (p["sens"] < 0 and prix > float(r[0]["high"]) + buf))
    if not casse:
        return False
    vol = round(p["lot"] * TRAIL_PART, 2)
    if vol <= 0 or vol >= p["reste"]:
        return False
    _jambe(p, prix, vol, "PARTIEL70")
    p["reste"] = round(p["reste"] - vol, 2)
    p["partiel"] = True
    return True


def fermer(ouvertes, k, c, prix, motif):
    p = ouvertes.pop(k)
    _jambe(p, prix, p["reste"], motif)


def boucle(pas):
    if mt5 is None:
        print("KO : MetaTrader5 introuvable dans cet interpreteur.")
        print("     --loop en a besoin ; --rapport, non.")
        return 1
    if _chr is None:
        print("KO : churn_regime.py introuvable a cote de ce script.")
        print("     C est lui qui porte le signal d ignition. Sans lui il")
        print("     faudrait l approcher, et les chiffres ressembleraient a")
        print("     ceux de la production sans en etre. On ne fait pas ca.")
        return 1
    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        return 1

    grille, absents = [], []
    for actif, code, sym in ACTIFS:
        vp = valeur_point(sym)
        if vp is None:
            absents.append("%s (%s) inconnu du terminal" % (actif, sym))
            continue
        for mn in DUREES:
            tf = tf_mt5(mn)
            if tf is None:
                absents.append("%s : unite %s absente de ce MetaTrader5"
                               % (actif, libelle(mn)))
                continue
            for bras in BRAS:
                grille.append({"k": cle(bras, code, mn), "bras": bras,
                               "actif": actif, "sym": sym, "mn": mn,
                               "tf": tf, "vp": vp})

    print("=" * LARG)
    print(" PAPIER -- %d cellules, lecture seule, aucun ordre" % len(grille))
    print("=" * LARG)
    print("durees   : %s" % "  ".join(libelle(m) for m in DUREES))
    print("bras     : 206 hold-until-reverse   207 memes entrees, %.0f%% du"
          % (TRAIL_PART * 100))
    print("           volume coupes au break de la bougie M2 precedente")
    print("signal   : churn_regime._analyze -- le vrai, pas une imitation")
    print("filtre   : RSI(14) M3 > 50 pour un BUY, < 50 pour un SELL")
    print("SL filet : %s (jamais traile)"
          % "  ".join("%s %.0f" % (a, v) for a, v in sorted(SL_FIXE.items())))
    print("horaires : SEANCE 08:00-19:30 en semaine (flat a 19:30) ; HORS =")
    print("           tout le reste, sans flat, %d h maxi" % MAX_H)
    print("journal  : %s" % TRADES)
    print("il est %s sur cette machine." % maintenant()[11:])
    for x in absents:
        print("  ABSENT : %s" % x)
    if not grille:
        print("Aucune cellule utilisable. Rien a observer.")
        mt5.shutdown()
        return 1
    print("Aucun ordre n est envoye. Ctrl+C pour arreter.")
    print()

    ouvertes = lire_etat()
    if ouvertes:
        print("%d position(s) papier reprises du fichier d etat."
              % len(ouvertes))
    armes = {}
    derniere = {}
    prochaine_veille = 0.0

    try:
        while True:
            try:
                bal = mt5.account_info().balance
            except Exception:
                bal = 20000.0
            insess = en_session()

            for c in grille:
                k = c["k"]
                tick = mt5.symbol_info_tick(c["sym"])
                if tick is None or not tick.bid:
                    continue
                prix = float(tick.bid)

                # --- la position en cours : SL, trail, flat de fin de seance
                p = ouvertes.get(k)
                if p:
                    gain = (prix - p["entree"]) * p["sens"]
                    p["mfe"] = max(p.get("mfe", 0.0), gain)
                    p["mae"] = min(p.get("mae", 0.0), gain)
                    motif = None
                    if p["sl"] > 0 and gain <= -p["sl"]:
                        motif = "SL"
                    elif p["creneau"] == "SEANCE" and not insess:
                        motif = "SESSION_FLAT"
                    elif (time.time() - p["t0"]) > MAX_H * 3600:
                        motif = "MAX_DUREE"
                    if motif:
                        fermer(ouvertes, k, c, prix, motif)
                        continue
                    # Le partiel du 207 s evalue a CHAQUE tour, meme sans
                    # ignition fraiche -- comme _apply_trail en production.
                    partiel(p, c["sym"], prix)

                # --- le signal : une seule evaluation par barre close
                r = mt5.copy_rates_from_pos(c["sym"], c["tf"], 0, 2)
                if r is None or len(r) < 2:
                    continue
                if derniere.get(k) == int(r[-2]["time"]):
                    continue
                derniere[k] = int(r[-2]["time"])

                cel = cellule(c["sym"], c["tf"])
                ign = bool(cel and cel.get("ignition"))
                d = cel.get("dir") if cel else None
                veut = "BUY" if d == "BULL" else ("SELL" if d == "BEAR"
                                                  else None)
                # « fresh » = la DIRECTION a change depuis la derniere
                # consommee. Un flip BULL->BEAR compte meme si ignition
                # n est jamais retombe a False -- correctif du 17/07.
                frais = ign and d in ("BULL", "BEAR") and armes.get(k) != d
                if not frais or veut is None:
                    armes[k] = d if ign else None
                    continue
                if SKIP_REJECT and (cel.get("mtf") or {}).get(
                        "signal") == "REJECT":
                    armes[k] = d
                    continue

                p = ouvertes.get(k)
                actuel = None if not p else ("BUY" if p["sens"] > 0
                                             else "SELL")
                if actuel == veut:
                    armes[k] = d          # meme sens : HOLD, pas de pyramide
                    continue
                if p:
                    fermer(ouvertes, k, c, prix, "REVERSE")
                bloque, _v = rsi_bloque(c["sym"], veut)
                if not bloque:
                    ouvrir(ouvertes, k, c, prix, veut, lot_de(c["sym"], bal))
                armes[k] = d

            if time.time() >= prochaine_veille:
                prochaine_veille = time.time() + VEILLE_MIN * 60
                ecrire_trade({"quoi": "VEILLE", "ts": maintenant(),
                              "creneau": creneau(), "ouvertes": len(ouvertes),
                              "cellules": len(grille)})
                ecrire_etat(ouvertes)
            time.sleep(pas)
    except KeyboardInterrupt:
        print()
        print("Arret demande. %d position(s) papier laissees ouvertes."
              % len(ouvertes))
        ecrire_etat(ouvertes)
    mt5.shutdown()
    return 0


# ---------------------------------------------------------------- rapport

def ratios(v):
    if not v:
        return 0, 0.0, 0.0, None, None
    n = len(v)
    s = sum(v)
    g = [x for x in v if x > 0]
    p = [x for x in v if x < 0]
    return n, s, s / n, 100.0 * len(g) / n, (sum(g) / abs(sum(p))
                                             if p else None)


def f(x, n=2):
    return "-" if x is None else ("%.*f" % (n, x))


def par_entree(tr):
    """Le 207 sort en deux fois : 70 % au break M2, 30 % au reverse. Les
    deux jambes portent le meme id. Compter les jambes gonflerait le N du
    207 et diviserait son EUR/trade par deux -- l A/B contre le 206
    deviendrait faux dans le sens qui l arrange."""
    g = {}
    for e in tr:
        i = e.get("id") or "%s@%s" % (e.get("k"), e.get("ouvert", e["ts"]))
        d = g.setdefault(i, {"id": i, "k": e.get("k"), "bras": e.get("bras"),
                             "actif": e.get("actif"), "mn": e.get("mn"),
                             "creneau": e.get("creneau"),
                             "ouvert": e.get("ouvert", e["ts"]),
                             "eur": 0.0, "minutes": 0, "motif": None,
                             "jambes": 0})
        d["eur"] += e.get("eur", 0.0)
        d["minutes"] = max(d["minutes"], e.get("minutes", 0))
        d["jambes"] += 1
        if e.get("motif") != "PARTIEL70":
            d["motif"] = e.get("motif")
    return list(g.values())


def rapport():
    ev = charger_trades()
    tr = [e for e in ev if e.get("quoi") == "TRADE"]
    entrees = par_entree(tr)
    veilles = [e for e in ev if e.get("quoi") == "VEILLE"]
    ouvertes = lire_etat()

    L = []
    L.append("=" * LARG)
    L.append("  PAPIER x10 x20 x30 x60 x120 x240 -- 24h/24, bras 206 et 207")
    L.append("=" * LARG)
    if not ev:
        L.append("Aucun releve. Lance d abord :")
        L.append("    python papier_tf.py --loop")
        L.append("Il ne voit que ce qui se passe PENDANT qu il tourne, et")
        L.append("les unites longues sont lentes : H4 ne donnera pas un")
        L.append("premier signal avant demain.")
        return L

    L.append("%d entrees papier fermees (%d jambes), %d ouvertes, %.1f h"
             " d observation"
             % (len(entrees), len(tr), len(ouvertes),
                len(veilles) * VEILLE_MIN / 60.0))
    L.append("du %s au %s" % (ev[0]["ts"][:16], ev[-1]["ts"][:16]))
    L.append("")
    L.append("  AUCUN ORDRE REEL. Le signal est celui de la production --")
    L.append("  churn_regime._analyze, le RSI M3 > 50 / < 50, le SL filet")
    L.append("  fixe, le lot balance/20000, le hold-until-reverse du 206.")
    L.append("  Deux choses ne le sont pas : le trail du 207 (70 %% du MFE,")
    L.append("  DEDUIT du nom, ignition_trader_trail.py n a pas ete lu) et")
    L.append("  le H1 papier, calcule comme ses cinq voisins alors que la")
    L.append("  production lit la cellule de churn.")
    L.append("  Ni spread, ni slippage, ni commission : les chiffres sont")
    L.append("  OPTIMISTES, et d autant plus que l unite est courte.")
    L.append("")

    L.append("=" * LARG)
    L.append("  EN POSITION A CET INSTANT -- avec le temps ecoule")
    L.append("=" * LARG)
    if not ouvertes:
        L.append("  Aucune position papier ouverte.")
    else:
        L.append("%-10s %-6s %-7s %-6s %-8s %-21s %10s"
                 % ("cellule", "duree", "actif", "sens", "creneau",
                    "ouvert le", "ecoule"))
        L.append("-" * LARG)
        for k in sorted(ouvertes):
            p = ouvertes[k]
            L.append("%-10s %-6s %-7s %-6s %-8s %-21s %7d mn"
                     % (k, libelle(p["mn"]), p["actif"],
                        "ACHAT" if p["sens"] > 0 else "VENTE", p["creneau"],
                        p["ts"].replace("T", " "),
                        int((time.time() - p["t0"]) / 60)))
    L.append("")

    L.append("=" * LARG)
    L.append("  PAR DUREE ET PAR BRAS -- ou est le sweet spot")
    L.append("=" * LARG)
    L.append("%-8s %-6s %6s %11s %10s %6s %7s %10s"
             % ("duree", "bras", "N", "EUR", "EUR/trade", "WR", "PF",
                "duree moy"))
    L.append("-" * LARG)
    for mn in DUREES:
        for bras in BRAS:
            v = [e for e in entrees
                 if e["mn"] == mn and e["bras"] == bras]
            n, s, moy, wr, pf = ratios([e["eur"] for e in v])
            if not n:
                L.append("%-8s %-6s %6d %11s %10s %6s %7s %10s"
                         % (libelle(mn), bras, 0, "-", "-", "-", "-", "-"))
                continue
            L.append("%-8s %-6s %6d %11.2f %10.2f %5.0f%% %7s %7.0f mn"
                     % (libelle(mn), bras, n, s, moy, wr, f(pf),
                        sum(e["minutes"] for e in v) / float(n)))
    L.append("-" * LARG)
    L.append("  Meme entree, deux sorties. Si une duree est bonne des DEUX")
    L.append("  cotes, c est l entree qui vaut ; si elle n est bonne que")
    L.append("  d un cote, c est la sortie -- et le 207 est deduit, donc")
    L.append("  une difference 206/207 peut venir de mon trail et pas du")
    L.append("  marche.")
    L.append("")

    L.append("=" * LARG)
    L.append("  SEANCE CONTRE HORS SEANCE -- la question posee")
    L.append("=" * LARG)
    entete = "   %6s %11s %10s %6s" % ("N", "EUR", "EUR/trade", "WR")
    L.append("%-8s%s%s" % ("duree", entete, entete))
    L.append("%-8s%s%s"
             % ("", "   ---- SEANCE 08:00-19:30 ----".ljust(39),
                "   ------- HORS SEANCE -------".ljust(39)))
    L.append("-" * LARG)
    for mn in DUREES:
        lig = "%-8s" % libelle(mn)
        for cr in ("SEANCE", "HORS"):
            v = [e["eur"] for e in entrees
                 if e["mn"] == mn and e.get("creneau") == cr]
            n, s, moy, wr, _pf = ratios(v)
            lig += ("   %6d %11s %10s %6s"
                    % (n, f(s) if n else "-", f(moy) if n else "-",
                       ("%.0f%%" % wr) if n else "-"))
        L.append(lig)
    L.append("-" * LARG)
    obs = defaultdict(int)
    for e in veilles:
        obs[e.get("creneau", "?")] += 1
    L.append("  observe : SEANCE %.1f h, HORS %.1f h."
             % (obs.get("SEANCE", 0) * VEILLE_MIN / 60.0,
                obs.get("HORS", 0) * VEILLE_MIN / 60.0))
    L.append("  Une colonne vide en face d une couverture nulle ne dit rien.")
    L.append("  En face d une couverture longue, elle dit que rien ne s est")
    L.append("  declenche -- et ca, c est un resultat.")
    L.append("")

    L.append("=" * LARG)
    L.append("  PAR HEURE D ENTREE -- horloge de cette machine")
    L.append("=" * LARG)
    oh, eh, ph = defaultdict(int), defaultdict(int), defaultdict(list)
    for e in veilles:
        oh[e["ts"][11:13]] += 1
    for e in entrees:
        h = e["ouvert"][11:13]
        eh[h] += 1
        ph[h].append(e["eur"])
    if not oh:
        L.append("  Pas encore de couverture enregistree.")
    else:
        ech = max([abs(sum(v)) for v in ph.values()] or [0.0]) or 1.0
        L.append("%-7s %8s %8s %11s %10s   %s"
                 % ("heure", "observe", "entrees", "EUR", "EUR/trade",
                    "profil"))
        L.append("-" * LARG)
        for h in range(24):
            k = "%02d" % h
            v = ph.get(k, [])
            if not (oh.get(k) or eh.get(k)):
                continue
            n, s, moy, _wr, _pf = ratios(v)
            if v:
                prof = ("-" if s < 0 else "+") + "#" * int(
                    round(16.0 * abs(s) / ech))
                ch = "%11.2f %10.2f" % (s, moy)
            else:
                prof, ch = "", "%11s %10s" % ("-", "-")
            L.append("%-7s %7.1fh %8d %s   %s"
                     % (k + "h", oh.get(k, 0) * VEILLE_MIN / 60.0,
                        eh.get(k, 0), ch, prof))
    L.append("")

    L.append("=" * LARG)
    L.append("  COMMENT ILS SORTENT")
    L.append("=" * LARG)
    L.append("%-14s %6s %11s %10s %6s"
             % ("motif", "N", "EUR", "EUR/trade", "WR"))
    L.append("-" * LARG)
    for m in sorted(set(e.get("motif", "?") for e in tr)):
        v = [e["eur"] for e in tr if e.get("motif") == m]
        n, s, moy, wr, _pf = ratios(v)
        L.append("%-14s %6d %11.2f %10.2f %5.0f%%" % (m, n, s, moy, wr))
    L.append("-" * LARG)
    L.append("  SL = le filet fixe a touche. SESSION_FLAT ne concerne que")
    L.append("  les trades de SEANCE. Un MAX_DUREE dit qu une position HORS")
    L.append("  a tenu %d h sans que l ignition inverse ne vienne : normal" % MAX_H)
    L.append("  sur H4, revelateur sur M10.")
    return L


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--loop", action="store_true")
    p.add_argument("--rapport", action="store_true")
    p.add_argument("--pas", type=int, default=PAS)
    a = p.parse_args()

    if a.loop:
        return boucle(a.pas)
    for l in rapport():
        print(l)
    return 0


if __name__ == "__main__":
    sys.exit(main())
