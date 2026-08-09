# -*- coding: utf-8 -*-
"""
jauge_h1.py -- calcule la jauge du jour et l ecrit pour le panel.

POURQUOI UN CALCULATEUR SEPARE
    h1_seance.py recharge 190 jours de M5 et met plusieurs minutes : on ne
    peut pas le brancher sur un rafraichissement de panel. Ce script-ci ne
    charge que les dernieres seances, tourne en quelques secondes, et ecrit
    deux fichiers legers :

      docs/jauge_h1.json   -- l etat du jour, a lire par le panel
      docs/jauge_h1.csv    -- une ligne par jour et par actif, pour
                              regarder la jauge se peupler

    Le panel n a donc qu a lire un JSON. Aucun calcul, aucun MT5, et
    surtout aucune modification du code qui trade.

CE QUE LA JAUGE MESURE, ET CE QU ELLE NE MESURE PAS
    TAILLE H1 : l amplitude de la premiere heure americaine comparee a la
    mediane des %d seances precedentes du meme actif. GRANDE ou PETITE.
    C est le seul signal qui ait tenu mois apres mois -- 81 / 73 / 64 %% de
    reussite dans le cinquieme haut contre 50 de reference.

    REGIME : l amplitude quotidienne moyenne des 10 dernieres seances
    comparee a la mediane de l historique. CALME ou AGITE.

    ELLE NE DONNE PAS LE SENS. Cinq tentatives ont echoue : direction du
    matin, de la pre-ouverture, ordre des cassures, direction de H1, et
    flux de H1. La jauge dit QUAND, jamais DANS QUEL SENS. Ne la lis pas
    comme un signal directionnel, ce serait le contresens exact.

    ET ELLE N EST PAS UNE REGLE. Les sept gels courent jusqu au 01/09.
    C est un affichage, rien de plus.

STATUTS POSSIBLES
    ATTENTE   : la premiere heure n est pas terminee, rien a dire encore
    GRANDE    : au-dessus de la mediane glissante
    PETITE    : en dessous
    HISTORIQUE INSUFFISANT : moins de 10 seances de reference
"""
import io, os, sys, json, math, datetime as dt

ACTIFS = ["US30", "SPX500", "NAS100"]
JOURS = 45              # assez pour 20 seances de reference, et rapide
FENETRE_MED = 20
MIN_HIST = 10
FENETRE_REG = 10
DEBUT_AM = 8
FIN = 22
SORTIE_JSON = os.path.join("docs", "jauge_h1.json")
SORTIE_CSV = os.path.join("docs", "jauge_h1.csv")


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def moy(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def charger():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("MT5 injoignable"); sys.exit(1)
    fin = dt.datetime.now()
    deb = fin - dt.timedelta(days=JOURS)
    out = {}
    for sym in ACTIFS:
        mt5.symbol_select(sym, True)
        r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, deb, fin)
        if r is None or len(r) == 0:
            print("  %-8s aucune bougie" % sym); continue
        prop = []
        for x in r:
            prop.append((dt.datetime.utcfromtimestamp(int(x["time"])),
                         float(x["high"]), float(x["low"]),
                         float(x["open"]), float(x["close"]),
                         float(x["tick_volume"])))
        prop.sort()
        out[sym] = prop
    mt5.shutdown()
    return out


def localiser(prop):
    """Meme reperage que partout ailleurs : le pic de volume EST l ouverture
    cash americaine, et on ne code aucune heure en dur."""
    vol, n = {}, {}
    for t, h, l, o, c, v in prop:
        k = t.hour * 60 + (t.minute // 5) * 5
        vol[k] = vol.get(k, 0.0) + v
        n[k] = n.get(k, 0) + 1
    prof = dict((k, vol[k] / n[k]) for k in vol if n[k] >= 5)
    cand = [(v, k) for k, v in prof.items() if 12 * 60 <= k <= 18 * 60]
    return max(cand)[1] if cand else None


def par_jour(prop, ouv):
    j_h1, j_range = {}, {}
    for t, h, l, o, c, v in prop:
        k = t.hour * 60 + t.minute
        j = t.strftime("%Y-%m-%d")
        if ouv <= k < ouv + 60:
            d = j_h1.setdefault(j, [])
            d.append((h, l))
        if DEBUT_AM * 60 <= k < FIN * 60:
            d = j_range.setdefault(j, [])
            d.append((h, l))
    h1 = {}
    for j, b in j_h1.items():
        if len(b) >= 10:            # heure complete (12 bougies M5) ou presque
            h1[j] = max(x[0] for x in b) - min(x[1] for x in b)
    rg = {}
    for j, b in j_range.items():
        if len(b) >= 60:
            rg[j] = max(x[0] for x in b) - min(x[1] for x in b)
    return h1, rg


def main():
    print("=== jauge H1 ===")
    data = charger()
    if not data:
        return 1
    aujourdhui = max(max(t[0] for t in v).strftime("%Y-%m-%d") for v in data.values())
    etat = {"date": aujourdhui, "genere": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "avertissement": "jauge d ACTIVITE, pas de direction. Affichage seul,"
                             " aucune regle : les 7 gels courent jusqu au 01/09.",
            "actifs": {}}
    lignes = []
    for sym in sorted(data):
        ouv = localiser(data[sym])
        if ouv is None:
            continue
        h1, rg = par_jour(data[sym], ouv)
        jours = sorted(h1)
        if not jours:
            continue
        j = jours[-1]
        hist = [h1[x] for x in jours[:-1]][-FENETRE_MED:]
        e = {"h1_range": round(h1[j], 1),
             "ouverture_locale": "%02d:%02d" % (ouv // 60, ouv % 60)}
        if len(hist) < MIN_HIST:
            e["taille"] = "HISTORIQUE INSUFFISANT"
            e["ratio"] = None
        else:
            m = med(hist)
            e["mediane_%d" % FENETRE_MED] = round(m, 1)
            e["ratio"] = round(h1[j] / m, 2) if m else None
            e["taille"] = "GRANDE" if h1[j] > m else "PETITE"
        # regime d amplitude, meme convention causale que le gel V7
        jr = sorted(rg)
        rec = [rg[x] for x in jr if x < j][-FENETRE_REG:]
        anc = [rg[x] for x in jr if x < j]
        if len(rec) >= FENETRE_REG and len(anc) >= 2 * MIN_HIST:
            base = med(anc)
            e["regime"] = "CALME" if (moy(rec) / base) < 1.0 else "AGITE"
            e["regime_ratio"] = round(moy(rec) / base, 2) if base else None
        else:
            e["regime"] = "HISTORIQUE INSUFFISANT"
        etat["actifs"][sym] = e
        lignes.append((j, sym, e))
        print("  %-8s H1 %8.1f   mediane %8s   %-22s   regime %s"
              % (sym, e["h1_range"],
                 e.get("mediane_%d" % FENETRE_MED, "-"),
                 e["taille"], e.get("regime", "-")))

    if not os.path.isdir("docs"):
        os.makedirs("docs")
    io.open(SORTIE_JSON, "w", encoding="utf-8").write(
        json.dumps(etat, indent=2, ensure_ascii=False))
    print("ecrit %s" % SORTIE_JSON)

    # historique : une ligne par jour et par actif, sans doublon
    vus = set()
    if os.path.isfile(SORTIE_CSV):
        for l in io.open(SORTIE_CSV, encoding="utf-8-sig"):
            c = l.strip().split(";")
            if len(c) >= 2:
                vus.add((c[0], c[1]))
    else:
        io.open(SORTIE_CSV, "w", encoding="utf-8").write(
            "jour;asset;h1_range;mediane;ratio;taille;regime;regime_ratio\n")
    with io.open(SORTIE_CSV, "a", encoding="utf-8") as fo:
        n = 0
        for j, sym, e in lignes:
            if (j, sym) in vus:
                continue
            fo.write("%s;%s;%.1f;%s;%s;%s;%s;%s\n"
                     % (j, sym, e["h1_range"],
                        e.get("mediane_%d" % FENETRE_MED, ""),
                        e.get("ratio", "") if e.get("ratio") is not None else "",
                        e.get("taille", ""), e.get("regime", ""),
                        e.get("regime_ratio", "") if e.get("regime_ratio") is not None else ""))
            n += 1
    print("historique %s : %d ligne(s) ajoutee(s)" % (SORTIE_CSV, n))
    print()
    print("Rappel : cette jauge dit QUAND, jamais DANS QUEL SENS. Cinq")
    print("tentatives de trouver la direction ont echoue. Et c est un")
    print("affichage : les sept gels courent jusqu au 01/09, rien n est")
    print("applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
