# -*- coding: utf-8 -*-
"""
of_h1.py -- l orderflow de la premiere heure US donne-t-il le SENS ?

OU ON EN EST
    On a l AMPLITUDE : la taille de la premiere heure americaine annonce
    celle du reste de la seance. Taux de reussite du cinquieme haut 81 /
    73 / 64 %% contre 50 de reference, decroissance monotone jusqu au
    cinquieme bas a 26 / 33 / 30 %%, et le lien tient mois apres mois.

    On n a PAS le SENS. La direction de la premiere heure ne se prolonge
    pas : 51 / 49 / 49 %% de continuation, c est-a-dire pile ou face.

    Si l orderflow de cette heure-la donnait le sens, on aurait les deux
    morceaux : quand bouger, et de quel cote.

CE QUE CE SCRIPT REPOND
    0. DECOUVERTE : que contient reellement l orderflow, et sur quelles
       dates ? Le contexte ne commence qu au 03/08 dans join_context.jsonl.
       Si les fichiers bruts n ont pas plus d historique, tout ce qui
       depend de l orderflow portera sur cinq seances et ne prouvera rien.
       Cette section le mesure et le dit avant le reste.
    1. "PM only" contre "POST-GRANDE only" -- ne depend PAS de l orderflow
       et tourne toujours. C est la reformulation de la regle : filtrer sur
       la TAILLE de la premiere heure plutot que sur l heure. On a deja vu
       que l heure seule s evapore au controle horaire alors que la taille
       survit (p=0,044 contre 0,497).
    2. l orderflow pendant H1 differe-t-il entre GRANDE et PETITE ?
    3. l orderflow de H1 annonce-t-il la direction du reste ?

PRUDENCE SUR LA STRUCTURE
    Je ne connais pas la forme exacte de l index renvoye par
    orderflow_join.load_orderflow(). Le script l inspecte et affiche ce
    qu il trouve au lieu de le supposer. Si les clefs ne sont pas celles
    attendues, il le dit clairement plutot que de renvoyer des chiffres
    faux -- c est la lecon de la panne muette du filtre de dates.
"""
import io, os, sys, math, json, datetime as dt

CSV_H1 = "h1_seance.csv"
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]
ALIAS = {"US100": "NAS100", "NAS100": "NAS100", "US500": "SPX500",
         "SPX500": "SPX500", "US30": "US30", "DJ30": "US30"}
FENETRE_MED = 20
MIN_HIST = 10


def moy(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def et(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = moy(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def p_norm(z):
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


def t_deux(a, b):
    a = [x for x in a if x is not None]
    b = [x for x in b if x is not None]
    if len(a) < 3 or len(b) < 3:
        return None, None
    e = moy(a) - moy(b)
    se = math.sqrt(et(a) ** 2 / len(a) + et(b) ** 2 / len(b))
    return e, (p_norm(e / se) if se else None)


def _lire_csv(p):
    lg = [l.rstrip("\n") for l in io.open(p, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    out = []
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        out.append(dict(zip(ent, c)))
    return out


def lire_h1():
    """GRANDE / PETITE contre la mediane glissante du meme actif, jour
    courant exclu -- meme convention que le gel V6, pour que les deux
    parlent de la meme chose."""
    if not os.path.isfile(CSV_H1):
        print("introuvable : %s -- lance h1_seance.py d abord" % CSV_H1)
        sys.exit(1)
    par, extra = {}, {}
    for d in _lire_csv(CSV_H1):
        j, a = (d.get("jour") or "").strip(), (d.get("asset") or "").strip()
        try:
            r = float((d.get("h1_range") or "").replace(",", "."))
        except ValueError:
            continue
        if not j or not a or r <= 0:
            continue
        par.setdefault(a, []).append((j, r))
        extra[(j, a)] = {"h1_dir": (d.get("h1_dir") or "").strip().upper(),
                         "rds_dir": (d.get("rds_dir") or "").strip().upper()}
    out = {}
    for a in par:
        s = sorted(par[a])
        for i, (j, r) in enumerate(s):
            h = [x[1] for x in s[max(0, i - FENETRE_MED):i]]
            if len(h) < MIN_HIST:
                continue
            out[(j, a)] = "GRANDE" if r > med(h) else "PETITE"
    js = sorted({k[0] for k in out})
    print("%s : %d couples classes, %s -> %s"
          % (CSV_H1, len(out), js[0] if js else "-", js[-1] if js else "-"))
    return out, extra


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
            b = (o.get("asset") or "").strip().upper()
            par[tk] = {"jour": ts[:10], "hm": ts[11:16], "heure": int(ts[11:13]),
                       "asset": ALIAS.get(b, b), "pnl": float(pnl)}
    return list(par.values())


# ------------------------------------------------------------- section 0
def decouverte():
    """On inspecte au lieu de supposer. Si la structure n est pas celle
    attendue, on le dit -- plutot que de produire des chiffres faux, ce
    qui est la panne la plus dangereuse et on en a deja eu une ce soir."""
    print()
    print("=" * 86)
    print("  0. DECOUVERTE : que contient l orderflow, et sur quelles dates ?")
    print("=" * 86)
    try:
        sys.path.insert(0, ".")
        import orderflow_join as oj
    except Exception as e:
        print("  impossible d importer orderflow_join : %s" % e)
        print("  -> les sections 2 et 3 seront sautees, la section 1 tourne quand meme.")
        return None
    idx = None
    for nom in ("load_orderflow", "load_of", "charger_orderflow"):
        if hasattr(oj, nom):
            try:
                idx = getattr(oj, nom)()
                print("  %s() : OK" % nom)
                break
            except Exception as e:
                print("  %s() a echoue : %s" % (nom, e))
    if idx is None:
        print("  aucune fonction de chargement utilisable.")
        return None
    try:
        n = len(idx)
    except Exception:
        n = -1
    print("  entrees : %s" % (n if n >= 0 else "taille inconnue"))
    if hasattr(oj, "of_span"):
        try:
            print("  couverture (of_span) : %s" % (oj.of_span(idx),))
        except Exception as e:
            print("  of_span a echoue : %s" % e)
    # un echantillon, pour voir les clefs reellement disponibles
    try:
        k = list(idx.keys())[:1] if hasattr(idx, "keys") else None
        ech = idx[k[0]] if k else (idx[0] if n > 0 else None)
        if isinstance(ech, dict):
            print("  clefs d un echantillon : %s" % ", ".join(sorted(ech.keys())[:20]))
        else:
            print("  type d un echantillon : %s" % type(ech).__name__)
        if k:
            print("  forme d une clef : %r" % (k[0],))
    except Exception as e:
        print("  inspection d un echantillon impossible : %s" % e)
    print()
    print("  Colle-moi ces lignes : elles disent si les sections 2 et 3 sont")
    print("  realisables telles quelles, et sur combien de seances.")
    return idx


# ------------------------------------------------------------- section 1
def section1(h1, tickets):
    print()
    print("=" * 86)
    print("  1. 'PM only' contre 'POST-GRANDE only'")
    print("=" * 86)
    print("Ne depend pas de l orderflow : cette section tourne toujours.")
    print("On a deja vu que l heure seule s evapore au controle horaire")
    print("(p=0,497) alors que la taille de H1 survit (p=0,044). Ici on")
    print("chiffre la regle telle que tu la reformules.")
    lot = []
    for t in tickets:
        c = h1.get((t["jour"], t["asset"]))
        if c:
            t["h1"] = c
            lot.append(t)
    if len(lot) < 100:
        print("  seulement %d tickets classes -- trop peu." % len(lot))
        return
    js = sorted({t["jour"] for t in lot})
    print()
    print("  %d tickets classes, %d seances, %s -> %s"
          % (len(lot), len(js), js[0], js[-1]))
    print()
    print("  %-34s %6s %12s %10s" % ("regle", "N", "total EUR", "EUR/tk"))
    print("  " + "-" * 66)
    regles = [
        ("tout (reference)", lambda t: True),
        ("PM only (>= 14h courtier)", lambda t: t["heure"] >= 14),
        ("post-17h30 seulement", lambda t: t["hm"] >= "17:30"),
        ("POST-GRANDE, toute heure", lambda t: t["h1"] == "GRANDE"),
        ("POST-GRANDE et >= 14h", lambda t: t["h1"] == "GRANDE" and t["heure"] >= 14),
        ("POST-GRANDE et >= 17h30", lambda t: t["h1"] == "GRANDE" and t["hm"] >= "17:30"),
    ]
    for lib, fn in regles:
        g = [t for t in lot if fn(t)]
        if not g:
            continue
        print("  %-34s %6d %+12.2f %+10.2f"
              % (lib, len(g), sum(t["pnl"] for t in g), moy([t["pnl"] for t in g])))
    print("  " + "-" * 66)
    print()
    print("  ATTENTION SUR LA LIGNE 'toute heure' : l amplitude de la premiere")
    print("  heure US n est connue qu a 17h30 courtier. Autoriser les tickets")
    print("  du matin revient a utiliser le FUTUR -- c est le defaut assume de")
    print("  Z3 dans le gel V6. Cette ligne est affichee pour comparaison, elle")
    print("  n est PAS realisable. Seules les deux dernieres le sont.")


def main():
    h1, extra = lire_h1()
    tickets = lire_tickets()
    print("%d tickets lus" % len(tickets))
    idx = decouverte()
    section1(h1, tickets)
    if idx is None:
        print()
        print("=" * 86)
        print("  sections 2 et 3 non realisees")
        print("=" * 86)
        print("Il me faut la sortie de la section 0 pour ecrire la lecture de")
        print("l orderflow sans deviner sa structure. Colle-la-moi et je livre")
        print("la suite : agression pendant H1, et surtout le SENS -- la seule")
        print("piece qui manque encore au tableau.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
