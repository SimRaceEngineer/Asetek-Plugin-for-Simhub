#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""delta_momentum.py -- combien d entrees la regle du delta croissant
                         aurait-elle refusees, et que valaient-elles ?

  python delta_momentum.py --schema
  python delta_momentum.py
  python delta_momentum.py --pas 1 --variante normalise

LA REGLE, TELLE QU ELLE A ETE POSEE
-----------------------------------
On n entre que si le desequilibre S AGGRAVE par rapport a la bougie M1
precedente.

  vente   delta precedent -34  ->  on ne vend que si le delta courant
                                   atteint -35 ou moins
  achat   delta precedent +24  ->  on n achete que si le delta courant
                                   atteint +25 ou plus

LE DELTA DE CLOTURE, PAS L EXTREME
    Une bougie qui pousse a -42 et finit a -34 donne un seuil de -35,
    pas de -43. La meche dit ce qui a ete absorbe ; la cloture dit ce
    qui reste. C est la cloture qui sert de reference, donc le delta
    de la bougie ENTIERE.

LE TICK EST INDISPENSABLE, ET VOICI POURQUOI
    Le delta de la bougie EN COURS ne vaut que ce qui s est accumule
    entre le debut de la minute et l instant de l entree. Le prendre
    dans le CSV M1 reviendrait a lire la bougie une fois terminee,
    c est-a-dire a utiliser de l information posterieure a l entree :
    la mesure serait flatteuse et fausse. On lit donc le .scid, ou
    chaque tick porte son bid et son ask.

L ARTEFACT QU IL FAUT REGARDER EN FACE
    Comparer une bougie EN COURS a une bougie TERMINEE compare cinq
    secondes d accumulation a soixante. A la seconde 5 la condition est
    presque impossible ; a la seconde 55 presque acquise. La regle
    pousse donc mecaniquement les entrees vers la fin de la minute.

    Ce script ne cache pas cet effet : il imprime la repartition des
    secondes ecoulees pour les entrees autorisees et pour les refusees.
    Si les autorisees se tassent en fin de minute, l effet mesure est
    celui de l horloge et non celui du flux.

    `--variante normalise` compare delta_courant x 60 / secondes a
    delta_precedent, ce qui supprime l artefact. Les deux chiffres sont
    donnes cote a cote : c est au lecteur de trancher, pas au script.

CE QU IL NE FAIT PAS
    Il ne rejoue pas la strategie. Refuser une entree ne change ni les
    suivantes ni les sorties : on se contente de separer les entrees
    REELLEMENT prises en deux tas, celles que la regle aurait laissees
    passer et celles qu elle aurait refusees, et de sommer leur PnL
    reel. C est exact, et c est tout ce qu on peut affirmer sans
    simuler un moteur.

SOURCES
    tickets   docs\rails_trades\tickets_rails.jsonl
              champs entry_ts, dir, pnl_eur, ticket, magic, asset
    ticks     les .scid de SierraChart, lus par fenetre via croise_flux
              (classe Scid) -- on ne recharge pas 31 millions de ticks.

    Il n y a de .scid que pour YM et MES, donc pour US30 et US500. Les
    entrees NAS100 sont COMPTEES A PART et non mesurees : dire qu elles
    passent le filtre serait une invention.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import sys

RACINE = os.path.dirname(os.path.abspath(__file__))
TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
SCID_YM = r"C:\SierraChart\Data\YMU26-CBOT.scid"
SCID_MES = r"C:\SierraChart\Data\MESU26-CME.scid"
BAR = 60
PM = (14, 19)                  # la fenetre des papers, heures locales du ts
MAGIC_BAS, MAGIC_HAUT = 220000, 249999


def charge_croise():
    """Scid et mesure viennent de croise_flux.py. On ne reecrit pas un
    lecteur .scid a cote d un lecteur .scid correct -- c est l erreur du
    14/08 sur onglets() et du 18/08 sur seau_churn()."""
    if RACINE not in sys.path:
        sys.path.insert(0, RACINE)
    try:
        import croise_flux as cf
    except Exception as e:
        return None, "croise_flux.py illisible (%s)" % e
    for n in ("Scid", "ACTIFS_JSONL"):
        if not hasattr(cf, n):
            return None, "croise_flux n a pas %s" % n
    return cf, ""


def secondes(ts):
    try:
        d = datetime.datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    return int((d - datetime.datetime(1970, 1, 1)).total_seconds())


def lit_tickets(chemin):
    """Les entrees, avec leur sens, leur magic et leur resultat reel."""
    out, sans_pnl, hors_plage, hors_pm = [], 0, 0, 0
    if not os.path.isfile(chemin):
        return None, {"erreur": "introuvable : %s" % chemin}
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        b = ligne.strip()
        if not b.startswith("{"):
            continue
        try:
            o = json.loads(b)
        except ValueError:
            continue
        ts = o.get("entry_ts")
        if not isinstance(ts, str) or len(ts) < 19:
            continue
        try:
            magic = int(o.get("magic") or 0)
        except (TypeError, ValueError):
            magic = 0
        if not (MAGIC_BAS <= magic <= MAGIC_HAUT):
            hors_plage += 1
            continue
        try:
            h = int(ts[11:13])
        except ValueError:
            continue
        if not (PM[0] <= h < PM[1]):
            hors_pm += 1
            continue
        pnl = o.get("pnl_eur")
        if pnl is None:
            sans_pnl += 1
            continue
        sec = secondes(ts)
        if sec is None:
            continue
        out.append({"sec": sec, "ts": ts, "magic": magic,
                    "sens": (o.get("dir") or "").upper(),
                    "actif": o.get("asset") or o.get("symbol") or "",
                    "pnl": float(pnl), "ticket": o.get("ticket")})
    return out, {"hors_plage": hors_plage, "hors_pm": hors_pm,
                 "sans_pnl": sans_pnl, "retenus": len(out)}


def delta(S, t0, t1):
    """Delta de la fenetre [t0, t1) : ask - bid, sur les ticks."""
    d = S.entre(t0, t1)
    if d is None:
        return None
    _tt, pr, _vo, bi, ak = d
    if not pr:
        return 0.0
    return float(sum(ak) - sum(bi))


def juge(S, t, sens, pas, normalise):
    """(autorisee, d_prev, d_now, ecoulees) ou None si non mesurable."""
    m = (t // BAR) * BAR
    d_prev = delta(S, m - BAR, m)
    d_now = delta(S, m, t)
    if d_prev is None or d_now is None:
        return None
    ecoulees = t - m
    reference = d_now
    if normalise and ecoulees > 0:
        reference = d_now * float(BAR) / ecoulees
    if sens == "SELL":
        ok = reference <= d_prev - pas
    elif sens == "BUY":
        ok = reference >= d_prev + pas
    else:
        return None
    return ok, d_prev, d_now, ecoulees


def bloc(titre, lignes):
    print("")
    print("-" * 74)
    print(titre)
    print("-" * 74)
    for l in lignes:
        print(l)


def repartition(secs):
    """Combien d entrees dans chaque quart de minute."""
    q = [0, 0, 0, 0]
    for s in secs:
        q[min(3, int(s) // 15)] += 1
    n = float(len(secs)) or 1.0
    return "  ".join("%02d-%02ds %3d (%2.0f%%)"
                     % (i * 15, i * 15 + 14, c, 100 * c / n)
                     for i, c in enumerate(q))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", default=TICKETS)
    ap.add_argument("--ym", default=SCID_YM)
    ap.add_argument("--mes", default=SCID_MES)
    ap.add_argument("--pas", type=float, default=1.0,
                    help="de combien le delta doit s aggraver")
    ap.add_argument("--variante", choices=("brut", "normalise"),
                    default="brut")
    ap.add_argument("--schema", action="store_true",
                    help="dit ce qu il a trouve, ne calcule rien")
    a = ap.parse_args()

    print("=" * 74)
    print("DELTA MOMENTUM -- ce que la regle aurait refuse, seance PM")
    print("=" * 74)
    print("  regle    : le delta doit s aggraver de %.1f contre la CLOTURE"
          % a.pas)
    print("             de la bougie M1 precedente")
    print("  variante : %s" % a.variante)
    print("  fenetre  : %02dh-%02dh, magics %d a %d"
          % (PM[0], PM[1], MAGIC_BAS, MAGIC_HAUT))

    cf, err = charge_croise()
    if cf is None:
        print("")
        print("REFUS : %s" % err)
        return 1

    tickets, diag = lit_tickets(a.tickets)
    if tickets is None:
        print("")
        print("REFUS : %s" % diag["erreur"])
        return 1
    bloc("LES ENTREES", [
        "  retenues       %6d" % diag["retenus"],
        "  hors magics    %6d" % diag["hors_plage"],
        "  hors 14h-19h   %6d" % diag["hors_pm"],
        "  sans pnl_eur   %6d   (position encore ouverte)"
        % diag["sans_pnl"]])
    if not tickets:
        print("")
        print("Aucune entree exploitable. Rien n est affirme.")
        return 1

    fichiers = {"ym": a.ym, "mes": a.mes}
    scids, actif_de = {}, {}
    for cle, chemin in fichiers.items():
        S = cf.Scid(chemin)
        if S.err:
            print("  .scid %-4s : %s -- %s" % (cle, S.err, chemin))
            continue
        scids[cle] = S
        for nom in cf.ACTIFS_JSONL.get(cle, ()):
            actif_de[nom.upper()] = cle
    if not scids:
        print("")
        print("REFUS : aucun .scid lisible. Sans ticks, le delta de la")
        print("bougie en cours ne peut pas etre connu A L INSTANT de")
        print("l entree, et le mesurer sur la bougie terminee utiliserait")
        print("de l information posterieure. Je ne le ferai pas.")
        return 1

    if a.schema:
        vus = {}
        for t in tickets:
            vus[t["actif"]] = vus.get(t["actif"], 0) + 1
        bloc("CE QUI EST MESURABLE", [
            "  .scid lus      : %s" % ", ".join(sorted(scids)),
            "  actifs connus  : %s" % ", ".join(sorted(actif_de)),
            "  actifs des tickets :"] + [
            "     %-10s %5d  %s" % (k or "(vide)", v,
                                    "mesurable" if k.upper() in actif_de
                                    else "PAS DE .scid -- compte a part")
            for k, v in sorted(vus.items(), key=lambda x: -x[1])])
        print("")
        print("--schema : rien n a ete calcule.")
        return 0

    pris = {"n": 0, "pnl": 0.0, "secs": []}
    refuse = {"n": 0, "pnl": 0.0, "secs": []}
    sans_ticks = {"n": 0, "pnl": 0.0}
    par_magic = {}

    for t in tickets:
        cle = actif_de.get(t["actif"].upper())
        r = juge(scids[cle], t["sec"], t["sens"], a.pas,
                 a.variante == "normalise") if cle else None
        if r is None:
            sans_ticks["n"] += 1
            sans_ticks["pnl"] += t["pnl"]
            continue
        ok, _dp, _dn, ecoulees = r
        cible = pris if ok else refuse
        cible["n"] += 1
        cible["pnl"] += t["pnl"]
        cible["secs"].append(ecoulees)
        e = par_magic.setdefault(t["magic"], {"pris": 0, "ppnl": 0.0,
                                              "ref": 0, "rpnl": 0.0})
        if ok:
            e["pris"] += 1
            e["ppnl"] += t["pnl"]
        else:
            e["ref"] += 1
            e["rpnl"] += t["pnl"]

    tot_n = pris["n"] + refuse["n"]
    if tot_n == 0:
        print("")
        print("Aucune entree n a pu etre jugee : les .scid ne couvrent")
        print("pas les dates de ces tickets. Rien n est affirme.")
        return 1

    def tr(d):
        return d["pnl"] / d["n"] if d["n"] else 0.0

    bloc("LE VERDICT", [
        "  jugees         %6d" % tot_n,
        "  AUTORISEES     %6d  (%2.0f%%)   PnL %+10.2f   %+7.2f / trade"
        % (pris["n"], 100.0 * pris["n"] / tot_n, pris["pnl"], tr(pris)),
        "  REFUSEES       %6d  (%2.0f%%)   PnL %+10.2f   %+7.2f / trade"
        % (refuse["n"], 100.0 * refuse["n"] / tot_n, refuse["pnl"],
           tr(refuse)),
        "",
        "  total reel     %6d           PnL %+10.2f   %+7.2f / trade"
        % (tot_n, pris["pnl"] + refuse["pnl"],
           (pris["pnl"] + refuse["pnl"]) / tot_n),
        "",
        "  La regle rapporte %+.2f : c est le PnL des refusees, pris a"
        % (-refuse["pnl"]),
        "  l envers. Positif, elle evite des pertes ; negatif, elle coupe",
        "  des gains. Aucune autre lecture n est permise ici : refuser une",
        "  entree ne change ni les suivantes ni les sorties."])

    bloc("L ARTEFACT DE L HORLOGE -- a lire avant de conclure", [
        "  autorisees  %s" % repartition(pris["secs"]),
        "  refusees    %s" % repartition(refuse["secs"]),
        "",
        "  Si les autorisees se tassent dans le dernier quart, la regle",
        "  mesure l horloge et non le flux : une bougie en cours a plus de",
        "  temps pour depasser la precedente a la 55e seconde qu a la 5e.",
        "  Relancer avec --variante normalise pour l enlever."])

    lignes = ["  %-8s %6s %11s %8s %6s %11s %8s"
              % ("MAGIC", "pris", "PnL", "/trade", "refus", "PnL", "/trade")]
    for m in sorted(par_magic):
        e = par_magic[m]
        lignes.append("  %-8d %6d %+11.2f %+8.2f %6d %+11.2f %+8.2f"
                      % (m, e["pris"], e["ppnl"],
                         e["ppnl"] / e["pris"] if e["pris"] else 0.0,
                         e["ref"], e["rpnl"],
                         e["rpnl"] / e["ref"] if e["ref"] else 0.0))
    bloc("PAR MAGIC", lignes)

    if sans_ticks["n"]:
        bloc("NON MESUREES", [
            "  %d entree(s), PnL %+.2f" % (sans_ticks["n"], sans_ticks["pnl"]),
            "  Pas de .scid pour leur actif, ou date hors couverture du",
            "  fichier. Elles ne sont comptees NI dans les autorisees NI",
            "  dans les refusees. Les ranger d un cote serait une invention."])

    for S in scids.values():
        try:
            S.ferme()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
