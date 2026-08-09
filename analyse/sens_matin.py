# -*- coding: utf-8 -*-
"""
sens_matin.py -- les tickets pris DANS le sens du matin gagnent-ils plus
                 que les tickets pris a contre-sens ?

CE QU ON SAIT DEJA, ET CE QU ON NE SAIT PAS
    Sur le prix : une matinee baissiere casse son plus bas dans ~9 seances
    sur 10, une matinee haussiere casse son plus haut dans ~9 sur 10. Effet
    massif, p=0,000, stable dans les trois bandes de largeur.

    MAIS : les deux bornes cassent dans environ la moitie des seances, donc
    l evenement "le bas est casse" n est PAS l evenement "ca descend". Et
    l extension une fois la borne cassee est identique dans les deux cas
    (p=0,872) : le matin oriente, il ne dit rien de l amplitude.

    Surtout, tout cela porte sur le PRIX. Ce fichier teste la seule chose
    qui compte pour toi : le P&L de TES tickets.

LES DEUX CONTROLES, NON NEGOCIABLES
    1. unite SEANCE et pas ticket. Les tickets d une meme journee sont
       correles ; un t-test sur tickets gonfle artificiellement le t.
    2. centrage horaire. Verifie sur donnees fabriquees : un effet purement
       horaire produit un resultat "tres significatif" a l unite seance.
       La correction par seance ne protege PAS du confondant horaire.

    Un effet qui ne survit pas aux deux n existe pas.
"""
import io, os, sys, math, json

CSV = "profil_jour.csv"
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]
# churn_trades et MT5/profil_jour ne nomment pas les indices pareil.
ALIAS = {"US100": "NAS100", "NAS100": "NAS100", "US500": "SPX500",
         "SPX500": "SPX500", "US30": "US30", "DJ30": "US30"}
ACHAT = ("BUY", "ACHAT", "LONG", "B")
VENTE = ("SELL", "VENTE", "SHORT", "S")


def moy(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def et(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / float(len(xs))
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
        print("introuvable : %s -- lance d abord profil_jour.py" % CSV)
        sys.exit(1)
    lg = [l.rstrip("\n") for l in io.open(CSV, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    out, vus = {}, {}
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        d = dict(zip(ent, c))
        j = (d.get("jour") or "").strip()
        a = (d.get("asset") or "").strip()
        s = (d.get("am_dir") or "").strip().upper()
        if not j or not a or not s:
            continue
        # UP / DOWN, ou HAUSSIERE / BAISSIERE selon la version du script
        if s.startswith("H") or s == "UP":
            s = "UP"
        elif s.startswith("B") or s == "DOWN":
            s = "DOWN"
        else:
            continue
        out[(j, a)] = s
        vus[s] = vus.get(s, 0) + 1
    print("directions du matin lues : %s" % ", ".join("%s=%d" % kv for kv in sorted(vus.items())))
    return out


def lire_tickets():
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
            sens = (o.get("dir") or "").strip().upper()
            if sens in ACHAT:
                sens = "UP"
            elif sens in VENTE:
                sens = "DOWN"
            else:
                continue
            brut = (o.get("asset") or "").strip().upper()
            par[tk] = {"jour": ts[:10], "heure": int(ts[11:13]),
                       "brut": brut, "asset": ALIAS.get(brut, brut),
                       "sens": sens, "pnl": float(pnl)}
    return list(par.values())


def rapport(lot, titre):
    avec = [t["pnl"] for t in lot if t["accord"]]
    contre = [t["pnl"] for t in lot if not t["accord"]]
    if len(avec) < 20 or len(contre) < 20:
        print("  %-12s trop peu de tickets (avec=%d contre=%d)"
              % (titre, len(avec), len(contre)))
        return
    e, p = t_deux(avec, contre)
    print("  %-12s AVEC %5d tk %+8.2f EUR/tk | CONTRE %5d tk %+8.2f | ecart %+7.2f (p=%s)"
          % (titre, len(avec), moy(avec), len(contre), moy(contre), e,
             "%.3f" % p if p is not None else "-"))


def main():
    matin = lire_matin()
    tickets = lire_tickets()
    if not tickets:
        print("aucun ticket lu -- lance depuis le dossier de la stack.")
        return 1

    lot, sans, brut = [], 0, {}
    for t in tickets:
        brut[t["brut"]] = brut.get(t["brut"], 0) + 1
        s = matin.get((t["jour"], t["asset"]))
        if s is None:
            sans += 1
            continue
        # "accord" = le ticket va dans le sens de la matinee
        t["accord"] = (t["sens"] == s)
        t["am"] = s
        lot.append(t)

    print("actifs churn_trades : %s" % ", ".join("%s=%d" % kv for kv in sorted(brut.items())))
    print("%d tickets lus, %d apparies au matin, %d sans matin correspondant"
          % (len(tickets), len(lot), sans))
    if sans > 0.3 * len(tickets):
        print("/!\\ plus de 30%% des tickets sans matin : verifie ALIAS et la")
        print("    couverture de profil_jour.csv sur la periode des trades.")
    if len(lot) < 100:
        print("trop peu de tickets apparies pour conclure.")
        return 1
    js = sorted({t["jour"] for t in lot})
    print("%d seances, %s -> %s" % (len(js), js[0], js[-1]))

    print()
    print("=" * 92)
    print("  ticket DANS le sens du matin contre ticket a CONTRE-SENS")
    print("=" * 92)
    rapport(lot, "tous")
    for a in sorted({t["asset"] for t in lot}):
        rapport([t for t in lot if t["asset"] == a], a)
    for s in ("UP", "DOWN"):
        rapport([t for t in lot if t["am"] == s], "matin " + s)

    # ---- controle 1 : unite seance
    print()
    print("-" * 92)
    par_j = {}
    for t in lot:
        d = par_j.setdefault(t["jour"], {"avec": [], "contre": []})
        d["avec" if t["accord"] else "contre"].append(t["pnl"])
    paires = [(moy(d["avec"]), moy(d["contre"])) for d in par_j.values()
              if len(d["avec"]) >= 3 and len(d["contre"]) >= 3]
    if len(paires) >= 5:
        dd = [a - b for a, b in paires]
        m, s = moy(dd), et(dd)
        se = s / math.sqrt(len(dd))
        p = p_norm(m / se) if se else None
        print("A L UNITE SEANCE : %d seances, ecart moyen %+.2f, %d/%d en faveur"
              % (len(paires), m, sum(1 for x in dd if x > 0), len(paires)))
        print("                   p=%s" % ("%.3f" % p if p is not None else "-"))
    else:
        print("A L UNITE SEANCE : %d seances exploitables -- pas de test." % len(paires))

    # ---- controle 2 : centrage horaire
    ref = {}
    for t in lot:
        ref.setdefault(t["heure"], []).append(t["pnl"])
    ref = dict((h, moy(v)) for h, v in ref.items())
    ca = [t["pnl"] - ref[t["heure"]] for t in lot if t["accord"]]
    cc = [t["pnl"] - ref[t["heure"]] for t in lot if not t["accord"]]
    e, p = t_deux(ca, cc)
    print("A HEURE EGALE    : ecart %+.2f EUR/tk, p=%s"
          % (e if e is not None else 0.0, "%.3f" % p if p is not None else "-"))

    print()
    print("=" * 92)
    print("  lecture")
    print("=" * 92)
    print("Un effet n existe que s il survit AUX DEUX controles. Sur des")
    print("donnees fabriquees ne contenant qu un effet horaire, le test a")
    print("l unite seance sortait p=0,002 et 10 seances sur 12 -- entierement")
    print("faux. La correction par seance ne protege pas du confondant horaire.")
    print()
    print("LES SOUS-CELLULES (par actif, par sens du matin) SONT EXPLORATOIRES.")
    print("Verifie sur donnees ou le sens des tickets est TIRE AU HASARD : deux")
    print("des six sous-cellules sont quand meme sorties sous p=0,05. Avec six")
    print("comparaisons, en trouver une ou deux 'significatives' est le comportement")
    print("normal du bruit. Seules les lignes 'tous' et les deux controles comptent.")
    print()
    print("Et meme si l effet survit : il porte sur le SENS du ticket, pas sur")
    print("le moment. Bloquer les ordres a contre-sens toute l apres-midi sur")
    print("une statistique de matinee est une intervention lourde. A tester en")
    print("gel avant toute mise en production.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
