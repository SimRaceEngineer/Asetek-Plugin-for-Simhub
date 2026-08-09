# -*- coding: utf-8 -*-
"""
of_h1_sens.py -- l orderflow de la premiere heure US donne-t-il le SENS ?

CE QUI MANQUE, ET POURQUOI C EST LA DERNIERE PIECE
    AMPLITUDE : acquise. La taille de la premiere heure americaine annonce
    celle du reste de la seance -- 81 / 73 / 64 %% de reussite dans le
    cinquieme haut contre 50 de reference, decroissance monotone jusqu au
    cinquieme bas, et le lien tient mois apres mois.

    SENS : absent. La direction de cette premiere heure ne se prolonge pas
    du tout : 51 / 49 / 49 %% de continuation. Pile ou face.

    Le prix seul ne donnera pas le sens -- on a essaye par le matin, par la
    pre-ouverture, par l ordre des cassures. L orderflow est la derniere
    source disponible qui puisse le porter.

LES DONNEES, ENFIN CONNUES
    load_orderflow() renvoie 125 102 barres du 29/04 au 07/08, sur US30 et
    US500. Une centaine de jours, pas cinq : ma crainte venait de
    join_context.jsonl, qui ne commence au 03/08 que parce que c est la
    date de la jointure.

    Par barre : delta et cum_delta (l agression), close_pos (ou la barre
    ferme dans son propre range -- la pression de fin de barre), er,
    events, vol, range_ticks.

LE CALAGE, SANS SUPPOSER AUCUNE HORLOGE
    Le champ s appelle epoch_utc mais la source est NinjaTrader, sur son
    propre fuseau. Plutot que de deviner un decalage -- une heure d ecart
    ruinerait toute la fenetre -- le script localise le PIC DE VOLUME dans
    l horloge de l orderflow. Ce pic EST l ouverture cash americaine,
    quelle que soit l horloge, et la premiere heure se definit a partir de
    lui. Le profil est affiche pour verification.

CE QU ON TESTE
    1. calage et profil de volume
    2. l agression pendant H1 differe-t-elle entre GRANDE et PETITE ?
    3. LE SENS : delta, cum_delta et close_pos de H1 annoncent-ils la
       direction du reste de la seance ? Temoin 50%%, qui est ici le bon
       temoin : deux fenetres disjointes sont independantes sous marche
       aleatoire.
    4. le sens est-il mieux annonce quand la premiere heure est GRANDE ?
       C est la combinaison qu on espere : amplitude par la taille, sens
       par le flux.
"""
import io, os, sys, math, json, datetime as dt

CSV_H1 = "h1_seance.csv"
ALIAS_OF = {"US500": "SPX500", "US30": "US30", "NAS100": "NAS100",
            "US100": "NAS100", "SPX500": "SPX500"}
FENETRE_MED = 20
MIN_HIST = 10
DUREE_H1 = 60          # minutes


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


def binom_demi(k, n):
    if n == 0:
        return None
    c = [1]
    for _ in range(n):
        c = [1] + [c[j] + c[j + 1] for j in range(len(c) - 1)] + [1]
    return min(1.0, sum(c[i] for i in range(n + 1)
                        if i >= max(k, n - k) or i <= min(k, n - k)) / float(sum(c)))


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
    if not os.path.isfile(CSV_H1):
        print("introuvable : %s -- lance h1_seance.py" % CSV_H1)
        sys.exit(1)
    par, info = {}, {}
    for d in _lire_csv(CSV_H1):
        j, a = (d.get("jour") or "").strip(), (d.get("asset") or "").strip()
        try:
            r = float((d.get("h1_range") or "").replace(",", "."))
        except ValueError:
            continue
        if not j or not a or r <= 0:
            continue
        par.setdefault(a, []).append((j, r))
        info[(j, a)] = {"h1_dir": (d.get("h1_dir") or "").strip().upper(),
                        "rds_dir": (d.get("rds_dir") or "").strip().upper()}
    for a in par:
        s = sorted(par[a])
        for i, (j, r) in enumerate(s):
            h = [x[1] for x in s[max(0, i - FENETRE_MED):i]]
            if len(h) >= MIN_HIST and (j, a) in info:
                info[(j, a)]["taille"] = "GRANDE" if r > med(h) else "PETITE"
    return info


def charger_of():
    sys.path.insert(0, ".")
    try:
        import orderflow_join as oj
    except Exception as e:
        print("import orderflow_join impossible : %s" % e); sys.exit(1)
    idx = oj.load_orderflow()
    print("orderflow : %d barres" % len(idx))
    bars = []
    for k, v in idx.items():
        try:
            a = v.get("asset") or (k[0] if isinstance(k, tuple) else "")
            ep = v.get("epoch_utc")
            if ep is None and isinstance(k, tuple) and len(k) > 1:
                ep = k[1]
            if ep is None:
                continue
            bars.append((int(ep), ALIAS_OF.get(str(a).upper(), str(a).upper()), v))
        except Exception:
            continue
    bars.sort()
    print("barres exploitables : %d, actifs : %s"
          % (len(bars), ", ".join(sorted({b[1] for b in bars}))))
    return bars


def caler(bars):
    """Pic de volume dans l horloge de l orderflow. Ce pic EST l ouverture
    cash americaine ; on n a donc jamais besoin de connaitre le decalage."""
    vol, n = {}, {}
    for ep, a, v in bars:
        t = dt.datetime.utcfromtimestamp(ep)
        k = t.hour * 60 + (t.minute // 5) * 5
        try:
            x = float(v.get("vol") or 0)
        except (TypeError, ValueError):
            continue
        vol[k] = vol.get(k, 0.0) + x
        n[k] = n.get(k, 0) + 1
    prof = dict((k, vol[k] / n[k]) for k in vol if n[k] >= 20)
    if not prof:
        print("profil de volume vide."); sys.exit(1)
    ouv = max(prof.items(), key=lambda kv: kv[1])[0]
    print()
    print("=" * 86)
    print("  1. calage : ou est l ouverture americaine dans l horloge orderflow ?")
    print("=" * 86)
    for k, v in sorted(prof.items(), key=lambda kv: -kv[1])[:8]:
        print("  %02d:%02d  volume moyen %10.0f%s"
              % (k // 60, k % 60, v, "   <== retenu" if k == ouv else ""))
    base = med(list(prof.values()))
    if base:
        print("  le pic vaut %.1f fois le volume median" % (prof[ouv] / base))
    print("  fenetre H1 orderflow : %02d:%02d -> %02d:%02d (horloge orderflow)"
          % (ouv // 60, ouv % 60, (ouv + DUREE_H1) // 60, (ouv + DUREE_H1) % 60))
    print("  rappel : dans l horloge COURTIER l ouverture est a 16h30.")
    print("  ecart apparent : %+d minutes -- ce n est pas une erreur, les deux"
          % (ouv - 990))
    print("  sources n ont simplement pas le meme fuseau, et on ne s en sert pas.")
    return ouv


def agreger(bars, ouv):
    par = {}
    for ep, a, v in bars:
        t = dt.datetime.utcfromtimestamp(ep)
        k = t.hour * 60 + t.minute
        if not (ouv <= k < ouv + DUREE_H1):
            continue
        d = par.setdefault((t.strftime("%Y-%m-%d"), a),
                           {"delta": 0.0, "vol": 0.0, "ev": 0.0, "rt": 0.0,
                            "cp": [], "er": [], "cd": [], "n": 0})
        def num(cle):
            try:
                return float(v.get(cle) or 0)
            except (TypeError, ValueError):
                return 0.0
        d["delta"] += num("delta")
        d["vol"] += num("vol")
        d["ev"] += num("events")
        d["rt"] += num("range_ticks")
        d["cp"].append(num("close_pos"))
        d["er"].append(num("er"))
        d["cd"].append(num("cum_delta"))
        d["n"] += 1
    out = {}
    for k, d in par.items():
        if d["n"] < 20:
            continue
        out[k] = {"delta": d["delta"], "vol": d["vol"], "ev": d["ev"],
                  "rt": d["rt"], "n": d["n"],
                  "close_pos": moy(d["cp"]), "er": moy(d["er"]),
                  "cd_var": (d["cd"][-1] - d["cd"][0]) if len(d["cd"]) > 1 else 0.0,
                  "delta_norm": d["delta"] / d["vol"] if d["vol"] else 0.0}
    print()
    print("  %d couples jour/actif agreges sur la fenetre H1" % len(out))
    return out


def section2(agg, info):
    print()
    print("=" * 86)
    print("  2. l agression differe-t-elle entre GRANDE et PETITE ?")
    print("=" * 86)
    lots = {}
    for (j, a), d in agg.items():
        i = info.get((j, a))
        if not i or not i.get("taille"):
            continue
        lots.setdefault((a, i["taille"]), []).append(d)
    actifs = sorted({k[0] for k in lots})
    print("  %-9s %-9s %6s %11s %11s %11s %11s"
          % ("actif", "taille", "N", "|delta|/vol", "events", "range_ticks", "er"))
    print("  " + "-" * 74)
    for a in actifs:
        for t in ("GRANDE", "PETITE"):
            g = lots.get((a, t), [])
            if len(g) < 8:
                continue
            print("  %-9s %-9s %6d %11.3f %11.0f %11.0f %11.3f"
                  % (a, t, len(g), med([abs(x["delta_norm"]) for x in g]),
                     med([x["ev"] for x in g]), med([x["rt"] for x in g]),
                     med([x["er"] for x in g])))
        ga, pe = lots.get((a, "GRANDE"), []), lots.get((a, "PETITE"), [])
        if len(ga) >= 8 and len(pe) >= 8:
            e, p = t_deux([abs(x["delta_norm"]) for x in ga],
                          [abs(x["delta_norm"]) for x in pe])
            print("  %-9s ecart |delta|/vol %+.3f, p=%s"
                  % ("", e or 0, "%.3f" % p if p is not None else "-"))
        print("  " + "-" * 74)
    print("  |delta|/vol = desequilibre acheteur-vendeur rapporte au volume :")
    print("  c est la mesure d agression, independante de la taille du volume.")


def section3(agg, info):
    print()
    print("=" * 86)
    print("  3. LE SENS : l orderflow de H1 annonce-t-il la direction du reste ?")
    print("=" * 86)
    print("Temoin 50%% : deux fenetres disjointes sont independantes sous")
    print("marche aleatoire, donc ici le 50/50 est LE bon temoin.")
    print()
    signaux = [("delta", "signe du delta cumule"),
               ("cd_var", "variation du cum_delta"),
               ("close_pos", "close_pos moyen (0,5 = neutre)")]
    print("  %-9s %-28s %6s %14s %9s"
          % ("actif", "signal", "N", "bonne direction", "p"))
    print("  " + "-" * 72)
    for a in sorted({k[1] for k in agg}):
        for cle, lib in signaux:
            k = n = 0
            for (jj, aa), d in agg.items():
                if aa != a:
                    continue
                i = info.get((jj, aa))
                if not i or i.get("rds_dir") not in ("UP", "DOWN"):
                    continue
                v = d.get(cle)
                if v is None:
                    continue
                seuil = 0.5 if cle == "close_pos" else 0.0
                if abs(v - seuil) < 1e-12:
                    continue
                pred = "UP" if v > seuil else "DOWN"
                n += 1
                if pred == i["rds_dir"]:
                    k += 1
            if n < 20:
                continue
            p = binom_demi(k, n)
            print("  %-9s %-28s %6d %13.0f%% %9s"
                  % (a, lib, n, 100.0 * k / n, "%.3f" % p if p is not None else "-"))
        print("  " + "-" * 72)
    print("  Au-dessus de 50%% = le flux annonce le sens. En dessous = il")
    print("  l annonce a l envers, ce qui serait tout aussi exploitable.")


def section4(agg, info):
    print()
    print("=" * 86)
    print("  4. le sens est-il mieux annonce quand la premiere heure est GRANDE ?")
    print("=" * 86)
    print("La combinaison esperee : amplitude par la taille, sens par le flux.")
    print()
    print("  %-9s %-9s %-22s %6s %14s %9s"
          % ("actif", "taille", "signal", "N", "bonne dir.", "p"))
    print("  " + "-" * 76)
    for a in sorted({k[1] for k in agg}):
        for t in ("GRANDE", "PETITE"):
            for cle, lib in (("delta", "signe du delta"),
                             ("close_pos", "close_pos moyen")):
                k = n = 0
                for (jj, aa), d in agg.items():
                    if aa != a:
                        continue
                    i = info.get((jj, aa))
                    if not i or i.get("taille") != t:
                        continue
                    if i.get("rds_dir") not in ("UP", "DOWN"):
                        continue
                    v = d.get(cle)
                    if v is None:
                        continue
                    seuil = 0.5 if cle == "close_pos" else 0.0
                    if abs(v - seuil) < 1e-12:
                        continue
                    n += 1
                    if ("UP" if v > seuil else "DOWN") == i["rds_dir"]:
                        k += 1
                if n < 12:
                    continue
                p = binom_demi(k, n)
                print("  %-9s %-9s %-22s %6d %13.0f%% %9s"
                      % (a, t, lib, n, 100.0 * k / n,
                         "%.3f" % p if p is not None else "-"))
        print("  " + "-" * 76)


def main():
    info = lire_h1()
    bars = charger_of()
    ouv = caler(bars)
    agg = agreger(bars, ouv)
    if len(agg) < 40:
        print("moins de 40 couples agreges -- trop peu."); return 1
    section2(agg, info)
    section3(agg, info)
    section4(agg, info)
    print()
    print("=" * 86)
    print("  ce qui deciderait")
    print("=" * 86)
    print("La section 3 est la derniere piece. Si un des trois signaux sort")
    print("nettement au-dessus ou en dessous de 50%% sur LES DEUX actifs, on a")
    print("le sens -- et avec l amplitude deja acquise, le tableau est complet.")
    print()
    print("Trois signaux fois deux actifs font six cellules : une seule sous")
    print("p=0,05 serait le bruit normal. Il faut une CONCORDANCE entre actifs,")
    print("pas une etoile isolee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
