# -*- coding: utf-8 -*-
"""
simul_motif4.py -- et si on ne sortait QUE par le stop broker ?

  python simul_motif4.py
  python simul_motif4.py --bascule 2026-08-05
  python simul_motif4.py --of-champ cvd_bias

CE QUE C EST, ET CE QUE CE N EST PAS
    Ce n est PAS un gel. Le gel V9 est ferme, son empreinte est posee, son
    verdict tombe le 01/09 ; poser un V10 avant cette date reviendrait a
    juger deux hypotheses avec un seul hors-echantillon. C est une
    SIMULATION : elle rejoue les panneaux existants en remplacant les
    sorties non-motif-4 par ce qu aurait donne un stop broker.

    Si elle tient, elle devient un candidat pour un gel apres septembre.
    Rien de plus aujourd hui.

LE PROBLEME CENTRAL, ET IL EST HONNETE DE LE DIRE EN PREMIER
    On ne peut PAS reconstruire la sortie broker d un ticket que le code a
    ferme : le journal ne porte pas le sl au moment de la cloture. Toute
    simulation repose donc sur un modele, et un modele peut mentir.

    D ou trois garde-fous, dans cet ordre d importance :

    1. DEUX LECTURES. La lecture A n extrapole rien : elle isole, dans
       chaque cellule, les tickets qui sont REELLEMENT sortis en motif 4.
       C est un fait. La lecture B est le contrefactuel.

    2. UN ENCADREMENT, PAS UN POINT. Pour un ticket monte en profit,
       l estimation est MFE x capture du motif 4. Pour un ticket JAMAIS
       monte en profit, aucune estimation n est possible -- c est la que
       les simulations trichent d ordinaire. Deux versions :
         opt.  = on garde le P&L reel, donc on suppose que le stop broker
                 aurait fait aussi bien que le closer sur un trade jamais
                 monte en profit.
         pess. = on leur applique la perte moyenne des motifs 4 jamais
                 montes en profit.
       Ce sont DEUX HYPOTHESES, pas un encadrement garanti : si pess.
       depasse opt., cela veut dire que les pertes du closer sont PIRES
       que celles du stop broker sur cette population -- et c est en soi
       un resultat, pas une anomalie de calcul. Un resultat qui ne survit
       qu en optimiste, lui, n est pas un resultat.

    3. UN CONTROLE NEGATIF. La colonne ctrl fait tourner la MEME machinerie
       avec la capture tous motifs confondus. Si elle ameliore autant que
       la colonne motif 4, alors ce qu on mesure c est "remplacer le
       realise par du MFE", pas "sortir en motif 4". C est le test qui peut
       tuer l idee, et c est pour ca qu il est la.

CE QU IL N AFFICHE PAS, VOLONTAIREMENT
    Pas de taux de reussite simule. Par construction tout ticket estime
    finit gagnant des que la capture est positive : un WR simule vaudrait
    100 pour cent et ne dirait rien de vrai.

LES PANNEAUX
    Rails M1/M3/M5/M15 -- le tableau donne tendance et range cote a cote,
    donc "rails trades" et "rails trades post 05/08" d un seul coup.
    Puis heure d entree, heure de sortie, magic, actif, verdict churn, et
    orderflow.

L ORDERFLOW NE SUPPOSE AUCUN NOM DE CHAMP
    Le script balaie les tickets, liste ce qui ressemble a de l orderflow
    et annonce ce qu il retient. S il ne trouve rien, il le DIT au lieu
    d inventer -- et cela voudra dire que l orderflow est dans l etat ou
    etaient les rails avant rails_join.py : present quelque part, jamais
    joint aux tickets.

CE QU IL LIT
    De preference docs/rails_trades/tickets_rails.jsonl (sortie de
    rails_join.py), qui porte le biais des rails a l entree. A defaut
    churn_trades*.jsonl, et les blocs rails sont alors vides.

    La normalisation des biais rails est IMPORTEE de oos_v9 quand il est
    la, pour que les cellules portent les memes noms que rails_range.py et
    que le gel V9. Sans lui, lecture directe des champs rails_pos_*, et le
    script le signale.
"""
import argparse
import glob
import io
import json
import os
import sys

try:
    import oos_v9 as O
except ImportError:
    O = None

CANDIDATS = [os.path.join("docs", "rails_trades", "tickets_rails.jsonl"),
             os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
             os.path.join("docs", "churn_trades", "churn_trades.jsonl"),
             "churn_trades_archive.jsonl", "churn_trades.jsonl"]
TFS = ["M1", "M3", "M5", "M15"]
BASCULE = "2026-08-05"
MINI = 30          # sous ce nombre de tickets, une cellule ne se lit pas
LARG = 100        # largeur des tableaux
MINI_CAP = 15      # sous ce nombre de motifs 4, la capture de la cellule
                   # n est pas estimable : on retombe sur celle du regime

MOTS_OF = ("cvd", "delta", "imbalance", "absorb", "orderflow", "of_",
           "flux", "footprint", "aggress", "buy_vol", "sell_vol",
           "bid_ask", "tick_rule", "pression")


def nombre(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def verdict(v):
    if isinstance(v, dict):
        for k in ("VERDICT", "verdict", "Verdict"):
            if v.get(k):
                return str(v[k]).strip().upper()
        return "?"
    return str(v).strip().upper() if v else "?"


def biais(o, tf):
    """Le biais rails du pas de temps, normalise comme oos_v9 si possible."""
    if O is not None:
        try:
            return O._etat_tf(o, tf)[0]
        except (KeyError, TypeError, IndexError, AttributeError):
            pass
    v = o.get("rails_pos_" + tf.lower())
    return str(v) if v else "-"


def charger(exp):
    ch = exp or [p for p in CANDIDATS if os.path.isfile(p)]
    if not ch:
        for m in ("docs/*/churn_trades*.jsonl", "churn_trades*.jsonl"):
            ch = sorted(glob.glob(m))
            if ch:
                break
    if not ch:
        print("KO : aucun journal trouve. Utilise --fichier CHEMIN.")
        sys.exit(1)
    par = {}
    for f in ch:
        for l in io.open(f, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts = str(o.get("entry_ts") or "")
            pnl = nombre(o.get("pnl_eur"))
            tk = o.get("ticket")
            if len(ts) < 16 or pnl is None or tk is None or tk in par:
                continue
            cts = str(o.get("close_ts") or "")
            mg = nombre(o.get("magic"))
            s = {
                "jour": ts[:10],
                "hentree": ts[11:13] + "h",
                "hsortie": (cts[11:13] if len(cts) >= 16 else "??") + "h",
                "pnl": pnl,
                "mfe": nombre(o.get("mfe_eur")),
                "motif": str(o.get("close_reason")),
                "magic": ("M%d" % int(mg)) if mg else "M?",
                "actif": str(o.get("asset") or "?"),
                "churn": verdict(o.get("churn_entry")),
                "brut": o,
            }
            for tf in TFS:
                s["b" + tf.lower()] = biais(o, tf)
            par[tk] = s
    if not par:
        print("Aucun enregistrement exploitable.")
        sys.exit(1)
    print("journaux : %s" % ", ".join(os.path.basename(c) for c in ch))
    if O is None:
        print("oos_v9 absent : lecture directe des champs rails_pos_*. Les")
        print("libelles de cellules peuvent differer de ceux de rails_range.")
    return list(par.values())


# ------------------------------------------------------------------ mesures

def cap(lot):
    """Fraction du MFE encaissee, en fraction. None si non definie."""
    g = [s for s in lot if s["mfe"] is not None and s["mfe"] > 0]
    smfe = sum(s["mfe"] for s in g)
    if smfe <= 0:
        return None
    return sum(s["pnl"] for s in g) / smfe


def refs(sel):
    """Les references du regime : capture motif 4, capture tous motifs,
    et la perte moyenne d un motif 4 qui n est jamais monte en profit."""
    q4 = [s for s in sel if s["motif"] == "4"]
    perdants = [s for s in q4 if s["mfe"] is None or s["mfe"] <= 0]
    return {
        "c4": cap(q4) or 0.0,
        "ctous": cap(sel) or 0.0,
        "perte": (sum(s["pnl"] for s in perdants) / len(perdants)
                  if perdants else 0.0),
        "n4": len(q4),
        "nperd": len(perdants),
    }


def simule(lot, R):
    """(opt, pess, ctrl, n_estimes, n_non_estimables, capture_empruntee)."""
    q4 = [s for s in lot if s["motif"] == "4"]
    c = cap(q4) if len(q4) >= MINI_CAP else None
    empruntee = c is None
    if c is None:
        c = R["c4"]
    cc = cap(lot) if len(lot) >= MINI_CAP else None
    if cc is None:
        cc = R["ctous"]

    opt = pess = ctrl = 0.0
    nsim = nnon = 0
    for s in lot:
        if s["motif"] == "4":
            opt += s["pnl"]
            pess += s["pnl"]
            ctrl += s["pnl"]
        elif s["mfe"] is not None and s["mfe"] > 0:
            opt += s["mfe"] * c
            pess += s["mfe"] * c
            ctrl += s["mfe"] * cc
            nsim += 1
        else:
            # Jamais monte en profit : rien a capturer, donc rien a estimer.
            opt += s["pnl"]
            pess += R["perte"]
            ctrl += s["pnl"]
            nnon += 1
    return opt, pess, ctrl, nsim, nnon, empruntee


# ------------------------------------------------------------- presentation

def groupes(sel, clef):
    g = {}
    for s in sel:
        g.setdefault(clef(s), []).append(s)
    return g


def panneau(titre, clef, av, dp, Rav, Rdp, ordre=None, largeur=18):
    ga, gd = groupes(av, clef), groupes(dp, clef)
    cles = ordre if ordre is not None else sorted(set(ga) | set(gd))
    cles = [c for c in cles if ga.get(c) or gd.get(c)]
    if not cles:
        return

    print()
    print("=" * LARG)
    print("  " + titre)
    print("=" * LARG)

    # ---- lecture A : observe, aucune extrapolation
    print("  A. OBSERVE -- ce qu ont fait les tickets reellement sortis en motif 4")
    print("%-*s%35s%35s" % (largeur, "", "TENDANCE avant bascule",
                            "RANGE depuis bascule"))
    print("%-*s %5s %6s %9s %9s%2s %5s %6s %9s %9s%2s"
          % (largeur, "", "N", "part4", "EUR/tk 4", "EUR/tk !4", "",
             "N", "part4", "EUR/tk 4", "EUR/tk !4", ""))
    print("-" * LARG)
    for c in cles:
        ligne = "%-*s" % (largeur, str(c)[:largeur])
        for g in (ga.get(c, []), gd.get(c, [])):
            if not g:
                ligne += "%35s" % "-"
                continue
            q4 = [s for s in g if s["motif"] == "4"]
            q3 = [s for s in g if s["motif"] != "4"]
            e4 = sum(s["pnl"] for s in q4) / len(q4) if q4 else 0.0
            e3 = sum(s["pnl"] for s in q3) / len(q3) if q3 else 0.0
            ligne += " %5d %5.0f%% %9s %9s%2s" % (
                len(g), 100.0 * len(q4) / len(g),
                "%.2f" % e4 if q4 else "-",
                "%.2f" % e3 if q3 else "-",
                "?" if len(g) < MINI else "")
        print(ligne)
    print("-" * LARG)

    # ---- lecture B : contrefactuel
    print("  B. SIMULE -- EUR par ticket si les sorties non-motif-4 passaient au stop broker")
    print("%-*s%38s%38s" % (largeur, "", "TENDANCE avant bascule",
                            "RANGE depuis bascule"))
    print("%-*s %8s %8s %8s %8s%2s %8s %8s %8s %8s%2s"
          % (largeur, "", "reel", "opt.", "pess.", "ctrl", "",
             "reel", "opt.", "pess.", "ctrl", ""))
    print("-" * LARG)
    for c in cles:
        ligne = "%-*s" % (largeur, str(c)[:largeur])
        for g, R in ((ga.get(c, []), Rav), (gd.get(c, []), Rdp)):
            if not g:
                ligne += "%38s" % "-"
                continue
            o, p, k, ns, nn, emp = simule(g, R)
            n = len(g)
            ligne += " %8.2f %8.2f %8.2f %8.2f%2s" % (
                sum(s["pnl"] for s in g) / n, o / n, p / n, k / n,
                "*" if emp else ("?" if n < MINI else ""))
        print(ligne)
    print("-" * LARG)


def decouvre_of(lot, force):
    """Cherche un champ d orderflow sans en supposer le nom."""
    print()
    print("=" * LARG)
    print("  ORDERFLOW -- ce que les tickets portent reellement")
    print("=" * LARG)
    vus = {}
    for s in lot:
        for k, v in s["brut"].items():
            kb = k.lower()
            if v is None or not any(m in kb for m in MOTS_OF):
                continue
            d = vus.setdefault(k, {"n": 0, "vals": set(), "num": 0})
            d["n"] += 1
            if len(d["vals"]) < 40:
                d["vals"].add(str(v)[:20])
            if nombre(v) is not None:
                d["num"] += 1
    if not vus:
        print("  Aucun champ d orderflow dans les tickets.")
        print()
        print("  Ce n est pas une absence de donnee : orderflow_panel.py")
        print("  tourne sur le VPS. C est une absence de JOINTURE -- l etat")
        print("  ou etaient les rails avant rails_join.py. Il faut ecrire un")
        print("  orderflow_join.py sur le meme modele : pour chaque ticket,")
        print("  le dernier instantane STRICTEMENT anterieur a son entree.")
        print("  Tant qu il n existe pas, ce panneau ne peut rien dire, et")
        print("  fabriquer un chiffre ici serait pire que de n en pas avoir.")
        return None
    print("%-28s %7s %9s %9s" % ("champ", "tickets", "distincts", "numerique"))
    print("-" * LARG)
    for k in sorted(vus, key=lambda x: -vus[x]["n"]):
        d = vus[k]
        print("%-28s %7d %9s %8.0f%%"
              % (k[:28], d["n"], ("%d" % len(d["vals"])) +
                 ("+" if len(d["vals"]) >= 40 else ""),
                 100.0 * d["num"] / d["n"]))
    print("-" * LARG)

    if force:
        if force not in vus:
            print("  --of-champ %s : ce champ n est pas dans la liste." % force)
            return None
        return force
    for k in sorted(vus, key=lambda x: -vus[x]["n"]):
        if len(vus[k]["vals"]) <= 12:
            print("  retenu : %s (categoriel). Force-en un autre avec"
                  " --of-champ." % k)
            return k
    k = sorted(vus, key=lambda x: -vus[x]["n"])[0]
    print("  retenu : %s, decoupe en trois. Les bornes sont calculees sur"
          % k)
    print("  TOUT l echantillon : elles connaissent l avenir, ce panneau est")
    print("  descriptif et ne se lit pas comme une regle.")
    return k


def clef_of(champ, lot):
    """Categoriel tel quel ; numerique decoupe en trois."""
    vals = [nombre(s["brut"].get(champ)) for s in lot]
    vals = [v for v in vals if v is not None]
    distincts = set(str(s["brut"].get(champ)) for s in lot
                    if s["brut"].get(champ) is not None)
    if len(distincts) <= 12 or len(vals) < 0.8 * len(lot):
        return lambda s: str(s["brut"].get(champ) or "-")[:18]
    vals.sort()
    a, b = vals[len(vals) // 3], vals[2 * len(vals) // 3]

    def k(s):
        v = nombre(s["brut"].get(champ))
        if v is None:
            return "-"
        return "1 bas" if v < a else ("2 moyen" if v < b else "3 haut")
    return k


def main():
    global MINI, MINI_CAP
    p = argparse.ArgumentParser()
    p.add_argument("--bascule", default=BASCULE)
    p.add_argument("--mini", type=int, default=MINI)
    p.add_argument("--mini-cap", type=int, default=MINI_CAP)
    p.add_argument("--of-champ")
    p.add_argument("--fichier", nargs="*")
    a = p.parse_args()
    MINI, MINI_CAP = a.mini, a.mini_cap

    lot = charger(a.fichier)
    lot.sort(key=lambda s: s["jour"])
    av = [s for s in lot if s["jour"] < a.bascule]
    dp = [s for s in lot if s["jour"] >= a.bascule]

    print("=== SCALP-EA / SIMULATION : ET SI ON NE SORTAIT QUE PAR LE STOP BROKER ? ===")
    print("%d tickets, %s -> %s, bascule %s"
          % (len(lot), lot[0]["jour"], lot[-1]["jour"], a.bascule))
    if not av or not dp:
        print("Un des deux compartiments est vide -- verifie --bascule.")
        return 1

    Rav, Rdp = refs(av), refs(dp)
    print()
    print("REFERENCES DU MODELE -- tout le reste en decoule")
    print("%-12s %8s %8s %10s %10s %9s"
          % ("regime", "N", "N motif4", "capt. 4", "capt. tous", "perte 4"))
    print("-" * LARG)
    for lab, sel, R in (("TENDANCE", av, Rav), ("RANGE", dp, Rdp)):
        print("%-12s %8d %8d %9.0f%% %9.0f%% %9.2f"
              % (lab, len(sel), R["n4"], 100.0 * R["c4"],
                 100.0 * R["ctous"], R["perte"]))
    print("-" * LARG)
    print("capt. 4    = fraction du MFE encaissee par les sorties au stop broker.")
    print("capt. tous = la meme chose tous motifs confondus. C est le CONTROLE :")
    print("             si la colonne ctrl gagne autant que opt./pess., la")
    print("             simulation mesure le MFE, pas le motif 4.")
    print("perte 4    = perte moyenne d un motif 4 jamais monte en profit.")
    print("             C est elle qu on applique dans la colonne pess.")

    # ------------------------------------------------------------ panneaux
    for tf in TFS:
        panneau("RAILS %s A L ENTREE" % tf, lambda s, t=tf: s["b" + t.lower()],
                av, dp, Rav, Rdp)

    panneau("HEURE D ENTREE", lambda s: s["hentree"], av, dp, Rav, Rdp,
            ordre=["%02dh" % h for h in range(24)])
    panneau("HEURE DE SORTIE", lambda s: s["hsortie"], av, dp, Rav, Rdp,
            ordre=["%02dh" % h for h in range(24)] + ["??h"])

    mags = sorted(set(s["magic"] for s in lot),
                  key=lambda m: -sum(1 for s in lot if s["magic"] == m))
    panneau("PAR MAGIC", lambda s: s["magic"], av, dp, Rav, Rdp,
            ordre=mags[:22])
    panneau("PAR ACTIF", lambda s: s["actif"], av, dp, Rav, Rdp)
    panneau("PAR VERDICT CHURN A L ENTREE", lambda s: s["churn"],
            av, dp, Rav, Rdp)

    champ = decouvre_of(lot, a.of_champ)
    if champ:
        panneau("ORDERFLOW : %s" % champ, clef_of(champ, lot),
                av, dp, Rav, Rdp)

    # ------------------------------------------------------------ jour par jour
    print()
    print("=" * LARG)
    print("  JOUR PAR JOUR -- l ecart tient-il, ou vient-il d une seance ?")
    print("=" * LARG)
    print("%-12s %6s %7s %10s %10s %10s %10s"
          % ("jour", "N", "part4", "reel", "opt.", "pess.", "ctrl"))
    print("-" * LARG)
    for j in sorted(set(s["jour"] for s in lot)):
        g = [s for s in lot if s["jour"] == j]
        R = Rav if j < a.bascule else Rdp
        o, pe, k, ns, nn, emp = simule(g, R)
        n4 = sum(1 for s in g if s["motif"] == "4")
        print("%-12s %6d %6.0f%% %10.2f %10.2f %10.2f %10.2f"
              % (j, len(g), 100.0 * n4 / len(g),
                 sum(s["pnl"] for s in g), o, pe, k))
    print("-" * LARG)

    # ------------------------------------------------------------ totaux
    print()
    print("=" * LARG)
    print("  TOTAUX")
    print("=" * LARG)
    print("%-12s %6s %8s %12s %12s %12s %12s"
          % ("regime", "N", "estim.", "reel", "opt.", "pess.", "ctrl"))
    print("-" * LARG)
    for lab, sel, R in (("TENDANCE", av, Rav), ("RANGE", dp, Rdp),
                        ("ENSEMBLE", lot, None)):
        if R is None:
            o = pe = k = 0.0
            ns = nn = 0
            for s2, R2 in ((av, Rav), (dp, Rdp)):
                a1, a2, a3, a4, a5, _ = simule(s2, R2)
                o += a1
                pe += a2
                k += a3
                ns += a4
                nn += a5
        else:
            o, pe, k, ns, nn, _ = simule(sel, R)
        print("%-12s %6d %8d %12.2f %12.2f %12.2f %12.2f"
              % (lab, len(sel), ns, sum(s["pnl"] for s in sel), o, pe, k))
    print("-" * LARG)
    print("estim. = tickets dont le resultat a ete REMPLACE par une estimation.")
    print("         Les autres gardent leur P&L reel : soit ils sont deja")
    print("         motif 4, soit ils ne sont jamais montes en profit.")

    # ------------------------------------------------------------ reserves
    print()
    print("=" * LARG)
    print("  COMMENT LIRE CE QUI PRECEDE -- et comment ne pas le lire")
    print("=" * LARG)
    print("  1. La colonne ctrl d abord. Si elle progresse autant que opt.,")
    print("     arrete-toi la : la simulation mesure le MFE et pas le motif 4.")
    print("  2. La colonne pess. ensuite. Un resultat qui ne survit qu en")
    print("     opt. n est pas un resultat -- opt. suppose que le stop broker")
    print("     aurait fait aussi bien que le closer sur des trades qui ne")
    print("     sont JAMAIS montes en profit, ce qui est peu credible.")
    print("     Si pess. DEPASSE opt., ce n est pas un bug : cela dit que")
    print("     les pertes du closer sont pires que celles du stop broker")
    print("     sur les trades jamais montes en profit. C est un resultat.")
    print("  3. Le biais de selection ne disparait dans AUCUNE colonne. Les")
    print("     tickets sortis en motif 4 sont peut-etre precisement ceux qui")
    print("     sont montes assez haut pour armer le trailing. Leur capture")
    print("     appliquee aux autres suppose qu ils leur ressemblent, ce que")
    print("     rien ici ne demontre.")
    print("  4. Une cellule * emprunte la capture du regime : moins de %d"
          % MINI_CAP)
    print("     motifs 4 dedans. Une cellule ? compte moins de %d tickets."
          % MINI)
    print()
    print("  CE QUI TRANCHERAIT POUR DE BON, et que ce script ne peut pas")
    print("  faire : journaliser sl au moment de la cloture dans")
    print("  churn_trade_logger. On saurait alors, ticket par ticket, ou le")
    print("  stop se trouvait quand le code a ferme -- donc ce que le stop")
    print("  aurait rendu, mesure et non estime. Une ligne de code, et toute")
    print("  cette page de reserves devient inutile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
