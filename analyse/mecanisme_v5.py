# -*- coding: utf-8 -*-
"""
mecanisme_v5.py -- d ou vient la perte des tickets a contre-sens ?

CE QU ON SAIT
    Les tickets pris a contre-sens de la matinee perdent -10,44 EUR piece
    contre +12,56 pour ceux qui vont dans le sens. Ecart +23,00, survivant
    aux deux controles (unite seance p=0,008, heure egale p=0,000).

CE QU ON NE SAIT PAS, ET QUE CE FICHIER CHERCHE
    La perte est-elle ETALEE sur tout le carnet, ou CONCENTREE sur quelques
    setups, quelques magics, quelques heures ?

    C est la question qui decide de la nature du probleme :
      - etalee   -> c est un effet de marche. On subit une orientation
                    generale, et seul un filtre directionnel peut aider.
      - concentree -> c est une faille d execution ou de logique dans un
                    module precis. Reparable a la source, sans filtre.

    La deuxieme reponse serait de loin la meilleure nouvelle : on corrige
    un composant au lieu de brider toute la stack.

METHODE
    Pour chaque dimension (setup, magic, actif, heure, regime, er...), on
    classe les niveaux par CONTRIBUTION A LA PERTE TOTALE des contre-sens,
    et on affiche la part cumulee. Si deux ou trois niveaux portent la
    majorite de la perte, c est une concentration ; si la courbe monte
    doucement sur vingt niveaux, c est etale.

AVERTISSEMENT, A LIRE AVANT D AGIR
    Tout ce fichier est EXPLORATOIRE. On fouille des dizaines de cellules
    sur 9 seances : trouver des cellules "significatives" est garanti,
    meme dans du bruit pur. On l a deja verifie ailleurs -- sur des donnees
    ou le sens des tickets etait tire au hasard, deux sous-cellules sur six
    passaient sous p=0,05.

    Rien de ce qui sort d ici ne doit etre applique directement. Ce qui en
    sort est une HYPOTHESE, qui doit faire l objet d un nouveau gel. On ne
    retouche pas le gel V5.
"""
import io, os, sys, math, json

CSV = "profil_jour.csv"
JOIN = os.path.join("docs", "churn_trades", "join_context.jsonl")
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]
ALIAS = {"US100": "NAS100", "NAS100": "NAS100", "US500": "SPX500",
         "SPX500": "SPX500", "US30": "US30", "DJ30": "US30"}
ACHAT = ("BUY", "ACHAT", "LONG", "B")
VENTE = ("SELL", "VENTE", "SHORT", "S")
MIN_N = 15


def moy(xs):
    return sum(xs) / float(len(xs)) if xs else None


def et(xs):
    if len(xs) < 2:
        return 0.0
    m = moy(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def p_norm(z):
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


def t_deux(a, b):
    if len(a) < 3 or len(b) < 3:
        return None, None
    e = moy(a) - moy(b)
    se = math.sqrt(et(a) ** 2 / len(a) + et(b) ** 2 / len(b))
    return e, (p_norm(e / se) if se else None)


def lire_matin():
    if not os.path.isfile(CSV):
        print("introuvable : %s -- lance profil_jour.py d abord" % CSV)
        sys.exit(1)
    lg = [l.rstrip("\n") for l in io.open(CSV, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    out = {}
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        d = dict(zip(ent, c))
        s = (d.get("am_dir") or "").strip().upper()
        s = "UP" if (s.startswith("H") or s == "UP") else ("DOWN" if (s.startswith("B") or s == "DOWN") else "")
        j, a = (d.get("jour") or "").strip(), (d.get("asset") or "").strip()
        if j and a and s:
            out[(j, a)] = s
    return out


def lire_ctx():
    out = {}
    if not os.path.isfile(JOIN):
        print("/!\\ %s absent : regime, er et flux seront vides." % JOIN)
        return out
    for l in io.open(JOIN, encoding="utf-8-sig"):
        l = l.strip()
        if not l:
            continue
        try:
            o = json.loads(l)
        except ValueError:
            continue
        out[o.get("ticket")] = o
    return out


def charger(matin, ctx):
    par = {}
    for ch in CHURN:
        if not os.path.isfile(ch):
            continue
        for l in io.open(ch, encoding="utf-8-sig"):
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts, pnl, tk = o.get("entry_ts") or "", o.get("pnl_eur"), o.get("ticket")
            if len(ts) < 16 or pnl is None or tk is None or tk in par:
                continue
            s = (o.get("dir") or "").strip().upper()
            sens = "UP" if s in ACHAT else ("DOWN" if s in VENTE else "")
            b = (o.get("asset") or "").strip().upper()
            asset = ALIAS.get(b, b)
            am = matin.get((ts[:10], asset))
            if not am or not sens:
                continue
            c = ctx.get(tk, {})
            par[tk] = {"jour": ts[:10], "heure": int(ts[11:13]), "asset": asset,
                       "accord": "AVEC" if sens == am else "CONTRE",
                       "sens": sens, "am": am, "pnl": float(pnl),
                       "setup": (o.get("rails_setup") or "SANS").strip().upper(),
                       "magic": str(o.get("magic") or "SANS"),
                       "regime": (c.get("regime") or "").strip().upper() or "SANS",
                       "er": (c.get("er") or "").replace("?", "").strip().upper() or "SANS",
                       "flux": (c.get("contra") or "").strip().upper() or "SANS"}
    return list(par.values())


def concentration(lot, cle, titre):
    """Classe les niveaux par contribution a la perte des contre-sens.
    La part cumulee est le vrai indicateur : si trois niveaux portent
    80% de la perte, c est une faille localisee et non un effet diffus."""
    contre = [t for t in lot if t["accord"] == "CONTRE"]
    perte = sum(t["pnl"] for t in contre if t["pnl"] < 0)
    if not contre or perte >= 0:
        return
    groupes = {}
    for t in lot:
        groupes.setdefault(str(t.get(cle)), []).append(t)
    lignes = []
    for k, g in groupes.items():
        gc = [t for t in g if t["accord"] == "CONTRE"]
        ga = [t for t in g if t["accord"] == "AVEC"]
        if len(gc) < 5:
            continue
        neg = sum(t["pnl"] for t in gc if t["pnl"] < 0)
        e, p = t_deux([t["pnl"] for t in ga], [t["pnl"] for t in gc])
        lignes.append((neg, k, len(gc), moy([t["pnl"] for t in gc]),
                       len(ga), moy([t["pnl"] for t in ga]) if ga else None, e, p))
    if not lignes:
        return
    lignes.sort()
    print()
    print("=" * 98)
    print("  " + titre)
    print("=" * 98)
    print("%-16s %6s %10s %8s %6s %10s %9s %8s %7s"
          % ("niveau", "N ctr", "perte ctr", "EUR/tk", "N avec", "EUR/tk", "ecart", "p", "cumul"))
    print("-" * 98)
    cum = 0.0
    for neg, k, nc, mc, na, ma, e, p in lignes:
        cum += neg
        mk = "" if nc >= MIN_N else " *"
        print("%-16s %6d %10.0f %8.2f %6d %10s %9s %8s %6.0f%%%s"
              % (k[:16], nc, neg, mc, na,
                 "%.2f" % ma if ma is not None else "-",
                 "%+.2f" % e if e is not None else "-",
                 "%.3f" % p if p is not None else "-",
                 100.0 * cum / perte, mk))
    print("-" * 98)
    # Le seuil doit etre RELATIF au nombre de niveaux. "Les 3 pires portent
    # 66%" ne veut rien dire s il n y a que 5 niveaux : sous repartition
    # uniforme ils en porteraient deja 60%. On compare donc a 3/N.
    n = len(lignes)
    k = min(3, n)
    part = 100.0 * sum(x[0] for x in lignes[:k]) / perte
    attendu = 100.0 * k / n
    print("les %d pires niveaux portent %.0f%% de la perte, contre %.0f%% "
          "attendus si c etait uniforme (%d niveaux)" % (k, part, attendu, n))
    if n < 6:
        print("  -> %d niveaux seulement : on ne peut pas juger de la "
              "concentration ici." % n)
    elif part > 2.0 * attendu:
        print("  -> CONCENTRE (%.1f fois l attendu). Piste de faille "
              "localisee, a instruire." % (part / attendu))
    elif part > 1.4 * attendu:
        print("  -> legerement concentre (%.1f fois l attendu). A regarder, "
              "sans plus." % (part / attendu))
    else:
        print("  -> ETALE. Ressemble a un effet de marche, pas a un bug.")
    print("  * = moins de %d tickets a contre-sens, cellule peu fiable." % MIN_N)


def main():
    matin, ctx = lire_matin(), lire_ctx()
    lot = charger(matin, ctx)
    if len(lot) < 200:
        print("trop peu de tickets apparies (%d)." % len(lot))
        return 1
    a = [t["pnl"] for t in lot if t["accord"] == "AVEC"]
    c = [t["pnl"] for t in lot if t["accord"] == "CONTRE"]
    print("%d tickets apparies, %d seances, %s -> %s"
          % (len(lot), len({t["jour"] for t in lot}),
             min(t["jour"] for t in lot), max(t["jour"] for t in lot)))
    print("AVEC %d tk %+.2f EUR/tk  |  CONTRE %d tk %+.2f EUR/tk  |  ecart %+.2f"
          % (len(a), moy(a), len(c), moy(c), moy(a) - moy(c)))
    print("perte brute des contre-sens (tickets negatifs seuls) : %.0f EUR"
          % sum(x for x in c if x < 0))

    for cle, titre in (("setup", "1. par setup rails"),
                       ("magic", "2. par magic"),
                       ("asset", "3. par actif"),
                       ("heure", "4. par heure (courtier, UTC+3 = ton heure +1)"),
                       ("am", "5. par direction de la matinee"),
                       ("regime", "6. par regime inter-indices"),
                       ("er", "7. par ER du flux"),
                       ("flux", "8. par sens vs orderflow")):
        concentration(lot, cle, titre)

    print()
    print("=" * 98)
    print("  comment lire, et quoi ne PAS faire")
    print("=" * 98)
    print("La colonne qui compte est 'cumul'. Une perte portee par deux ou")
    print("trois niveaux sur vingt est une faille localisee : on repare le")
    print("composant. Une perte qui monte doucement sur tous les niveaux est")
    print("un effet de marche : seul un filtre directionnel peut aider.")
    print()
    print("NE PAS appliquer ce qui sort d ici. On fouille des dizaines de")
    print("cellules sur 9 seances : trouver des p significatifs est garanti,")
    print("meme dans du bruit pur -- verifie ailleurs, sur des donnees ou le")
    print("sens des tickets etait tire au hasard, deux sous-cellules sur six")
    print("passaient sous 0,05. Ce qui sort d ici est une HYPOTHESE, qui")
    print("merite son propre gel. Le gel V5 n est pas retouche.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
