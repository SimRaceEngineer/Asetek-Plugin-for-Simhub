# -*- coding: utf-8 -*-
"""
panneau_miroirs.py -- parent, miroir 1, miroir 2, cote a cote.

  python panneau_miroirs.py                 boucle, 15 s
  python panneau_miroirs.py --secondes 5
  python panneau_miroirs.py --une-fois

POURQUOI UN PANNEAU A PART

    panels_auto relit ~430 000 lignes deux fois par cycle et met deux a
    trois minutes ; il REFUSE un intervalle sous dix minutes, et il a
    raison -- en dessous, les cycles s empilent sans jamais aboutir.

    Or comparer un parent a ses miroirs, ce sont trois lignes et un
    positions_get : quelques dizaines de millisecondes. Ce panneau-la
    peut tenir 15 secondes sans gener personne, pendant que panels_auto
    garde son rythme pour le reste.

CE QU IL MONTRE, ET CE QU IL NE PEUT PAS MONTRER

    L ecart d entree est mesure contre le prix du parent, signe de sorte
    qu un chiffre POSITIF veut dire  paye plus cher que le parent .

    Le P&L d un miroir n est comparable a celui du parent que si les
    deux portent le meme volume. C est le cas ici (LOT = parent), mais
    ce n est PAS le cas des papers du rapport : chaque paper capitalise
    sa propre balance et mise donc un lot different. Le classement de ce
    panneau ne ressemblera pas a celui du rapport paper, et c est normal.

    Qui a ferme quoi se lit dans le commentaire du deal de sortie :
    mirX = le miroir lui-meme, M154_FOLLOW / IGN_COVER / PREOPEN_75 =
    un autre module, [sl = le stop. C est la colonne qui decide de tout
    le test.

CE QU IL NE FAIT PAS

    Aucun ordre, aucune modification. Lecture seule, MT5 en lecture.
"""
import argparse
import csv
import datetime
import io
import os
import sys
import time

DOSSIER = "docs"
CSV_MIROIR = os.path.join(DOSSIER, "miroir_papers.csv")
SORTIE = os.path.join("panels", "miroirs.txt")
LARG = 118


def miroir2(magic):
    try:
        return int(magic) >= 1000000
    except (TypeError, ValueError):
        return False


def role(magic):
    return "MIR2" if miroir2(magic) else "MIR1"


def nombre(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def lit_envois():
    """Les paires parent -> miroir, telles que le miroir les a ecrites."""
    par_parent = {}
    if not os.path.isfile(CSV_MIROIR):
        return par_parent, "journal absent : %s" % CSV_MIROIR
    try:
        with io.open(CSV_MIROIR, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("evenement") != "ENVOI":
                    continue
                tm = r.get("ticket_miroir")
                tp = r.get("ticket_parent")
                if not tm or not tp:
                    continue
                par_parent.setdefault(tp, []).append(r)
    except Exception as e:
        return par_parent, "journal illisible : %s" % e
    return par_parent, None


def sorties_du_jour(mt5):
    """position_id -> (profit cumule, commentaire de sortie, prix)."""
    d = {}
    try:
        a = datetime.datetime.now().replace(hour=0, minute=0, second=0,
                                            microsecond=0)
        b = datetime.datetime.now() + datetime.timedelta(days=1)
        for x in (mt5.history_deals_get(a, b) or []):
            if x.entry != 1:
                continue
            p, com, prix = d.get(x.position_id, (0.0, "", None))
            d[x.position_id] = (p + float(x.profit),
                                x.comment or com, x.price)
    except Exception:
        pass
    return d


def ecart_pts(prix_parent, prix_miroir, sens, point):
    if prix_parent is None or prix_miroir is None or not point:
        return None
    e = prix_miroir - prix_parent
    if str(sens).upper().startswith("S"):
        e = -e
    return e / point


def bloc(mt5, par_parent, positions, deals):
    lignes = []
    tot = {"MIR1": [0.0, 0, 0], "MIR2": [0.0, 0, 0]}   # pnl, ouverts, fermes
    for tp, envois in sorted(par_parent.items(), key=lambda kv: kv[0]):
        parent = positions.get(int(tp))
        fini = deals.get(int(tp))
        if parent is None and fini is None:
            continue          # ni ouvert ni ferme aujourd hui : trop vieux
        r0 = envois[0]
        sym = r0.get("symbole") or ""
        info = mt5.symbol_info(sym)
        point = float(getattr(info, "point", 0) or 0)
        pp = nombre(r0.get("prix_parent"))
        sens = r0.get("sens") or ""

        lignes.append("")
        if parent is not None:
            lignes.append(
                "  PARENT  %-9s %-7s %-4s  entree %10.2f  vol %5.2f"
                "  SL %10.2f  P&L %8.2f   OUVERT"
                % (parent.magic, sym, sens, parent.price_open,
                   parent.volume, parent.sl or 0.0, parent.profit))
        else:
            lignes.append(
                "  PARENT  %-9s %-7s %-4s  entree %10.2f"
                "                                P&L %8.2f   ferme %s"
                % (r0.get("magic_parent"), sym, sens, pp or 0.0,
                   fini[0], (fini[1] or "?")[:22]))

        for r in sorted(envois, key=lambda x: (miroir2(x.get("magic_paper")),
                                               str(x.get("magic_paper")))):
            mg = r.get("magic_paper")
            tm = r.get("ticket_miroir")
            po = nombre(r.get("prix_obtenu"))
            ec = ecart_pts(pp, po, sens, point)
            vivant = positions.get(int(tm)) if tm else None
            clos = deals.get(int(tm)) if tm else None
            k = role(mg)
            if vivant is not None:
                tot[k][0] += vivant.profit
                tot[k][1] += 1
                etat = "OUVERT"
                pnl = vivant.profit
                vol = vivant.volume
                sl = vivant.sl or 0.0
            elif clos is not None:
                tot[k][0] += clos[0]
                tot[k][2] += 1
                etat = "ferme %s" % (clos[1] or "?")[:22]
                pnl = clos[0]
                vol = nombre(r.get("volume_miroir")) or 0.0
                sl = 0.0
            else:
                continue
            lignes.append(
                "    %-5s %-9s %-7s      obtenu %10.2f  vol %5.2f"
                "  SL %10.2f  P&L %8.2f   %s   ecart %s"
                % (k, mg, tm, po or 0.0, vol, sl, pnl, etat,
                   "%+7.1f pts" % ec if ec is not None else "      ?"))
    return lignes, tot


def rendu(mt5):
    par_parent, err = lit_envois()
    t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = ["=" * LARG,
           " PARENT vs MIROIR 1 vs MIROIR 2      %s" % t,
           "=" * LARG]
    if err:
        out += ["", "  " + err, ""]
        return out
    positions = dict((int(p.ticket), p) for p in (mt5.positions_get() or []))
    deals = sorties_du_jour(mt5)
    corps, tot = bloc(mt5, par_parent, positions, deals)
    if not corps:
        out += ["", "  Aucun parent suivi n est ouvert ni ferme aujourd hui.",
                "  %d paire(s) dans le journal, toutes anterieures."
                % len(par_parent), ""]
        return out
    out += corps
    out += ["", "-" * LARG]
    for k in ("MIR1", "MIR2"):
        p, o, f = tot[k]
        out.append("  %-5s  P&L %9.2f   %3d ouvert(s)   %3d ferme(s)"
                   % (k, p, o, f))
    d = tot["MIR1"][0] - tot["MIR2"][0]
    out.append("  ecart MIR1 - MIR2 : %+9.2f   "
               "(positif = sortir avec le parent rapporte plus)" % d)
    out += ["-" * LARG,
            "  ecart d entree : positif = paye plus cher que le parent.",
            "  la colonne  ferme  dit QUI a decide : mirX = le miroir,",
            "  M154_FOLLOW / IGN_COVER / PREOPEN_75 = un autre module.",
            "  Lecture seule. Aucun ordre n a ete envoye.",
            "=" * LARG]
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--secondes", type=float, default=15.0)
    p.add_argument("--une-fois", action="store_true")
    p.add_argument("--sortie", default=SORTIE)
    a = p.parse_args()

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 absent de ce python.")
        return 1
    if not mt5.initialize():
        print("connexion MT5 impossible : %s" % (mt5.last_error(),))
        return 1
    try:
        while True:
            t0 = time.time()
            try:
                lignes = rendu(mt5)
            except Exception as e:
                lignes = ["panneau en erreur : %s: %s" % (type(e).__name__, e)]
            texte = "\n".join(lignes)
            print("\n" * 2 + texte)
            sys.stdout.flush()
            try:
                d = os.path.dirname(a.sortie)
                if d:
                    os.makedirs(d, exist_ok=True)
                tmp = a.sortie + ".tmp"
                io.open(tmp, "w", encoding="utf-8",
                        newline="\n").write(texte + "\n")
                os.replace(tmp, a.sortie)
            except Exception as e:
                print("  ecriture impossible : %s" % e)
            if a.une_fois:
                return 0
            reste = a.secondes - (time.time() - t0)
            time.sleep(reste if reste > 0 else 0.5)
    except KeyboardInterrupt:
        print("arret demande")
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
