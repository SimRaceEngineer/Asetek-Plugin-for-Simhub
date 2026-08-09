# -*- coding: utf-8 -*-
"""
sans_par_jour.py -- le bucket "regime SANS" est-il une PERIODE ?

CE QU ON VIENT DE VOIR
    Le champ regime absent (SANS) porte 942 tickets sur 2223, et c est
    dans ce bucket que se concentre presque tout le profit du cote AVEC :
    plus de 15 000 EUR sur les 15 400 du total.

    Hors SANS, l ecart AVEC/CONTRE existe toujours (+16,31) mais par un
    mecanisme OPPOSE : le AVEC y est plat et c est le CONTRE qui saigne.

L HYPOTHESE A TESTER
    SANS n est peut-etre pas un defaut de couverture aleatoire, mais un
    marqueur de PERIODE. Les seances du 21 au 25 juillet, recuperees sur
    msitrident1, n ont probablement pas de contexte orderflow, alors que
    celles du 29 juillet au 7 aout en ont.

    Si c est le cas, SANS = juillet = CLOSER ACTIF, et l ecart mesure
    dans ce bucket melange l effet du sens du matin avec l effet du
    closer. Le confondant qu on croyait ecarte reviendrait par la fenetre.

CE QUI SE PASSE SELON LA REPONSE
    - SANS reparti sur toutes les seances -> defaut de couverture banal,
      le gel V5 n est pas menace.
    - SANS colle a une periode -> il faut refaire la mesure PAR PERIODE
      avant de croire quoi que ce soit, et le dire dans le journal.
"""
import io, os, sys, json

JOIN = os.path.join("docs", "churn_trades", "join_context.jsonl")
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]


def main():
    ctx = {}
    if os.path.isfile(JOIN):
        for l in io.open(JOIN, encoding="utf-8-sig"):
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ctx[o.get("ticket")] = (o.get("regime") or "").strip()
    else:
        print("introuvable : %s" % JOIN); return 1

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
            ts, tk, pnl = o.get("entry_ts") or "", o.get("ticket"), o.get("pnl_eur")
            if len(ts) < 10 or tk is None or tk in par or pnl is None:
                continue
            par[tk] = (ts[:10], ctx.get(tk, "") != "", float(pnl))

    if not par:
        print("aucun ticket lu."); return 1

    jours = {}
    for j, a, p in par.values():
        d = jours.setdefault(j, {"avec": 0, "sans": 0, "pnl": 0.0})
        d["avec" if a else "sans"] += 1
        d["pnl"] += p

    print("=" * 74)
    print("  couverture du champ regime, seance par seance")
    print("=" * 74)
    print("%-12s %8s %8s %9s %12s" % ("jour", "renseig.", "SANS", "% SANS", "PnL seance"))
    print("-" * 74)
    for j in sorted(jours):
        d = jours[j]
        n = d["avec"] + d["sans"]
        print("%-12s %8d %8d %8.0f%% %12.2f"
              % (j, d["avec"], d["sans"], 100.0 * d["sans"] / n, d["pnl"]))
    print("-" * 74)

    pleins = [j for j in jours if jours[j]["sans"] == 0]
    vides = [j for j in jours if jours[j]["avec"] == 0]
    mixtes = [j for j in jours if jours[j]["sans"] and jours[j]["avec"]]
    print("seances entierement renseignees : %d" % len(pleins))
    print("seances entierement SANS        : %d  %s"
          % (len(vides), ", ".join(sorted(vides)) if vides else ""))
    print("seances mixtes                  : %d" % len(mixtes))
    print()
    if vides and len(vides) >= 2 and len(mixtes) <= 1:
        print("*** SANS EST UNE PERIODE, PAS UN DEFAUT DE COUVERTURE ***")
        print("Les seances ci-dessus n ont AUCUN contexte orderflow, les autres")
        print("en ont partout. Le bucket SANS est donc un marqueur de date.")
        print()
        print("CONSEQUENCE : l ecart mesure dans SANS melange le sens du matin")
        print("et tout ce qui distingue cette periode -- closer actif, machine")
        print("differente, regime de marche. Il faut refaire la mesure PAR")
        print("PERIODE avant d interpreter, et l ecrire au journal.")
    elif len(mixtes) >= max(2, len(jours) // 2):
        print("SANS est reparti sur les seances : defaut de couverture banal.")
        print("Le gel V5 n est pas menace par ce point.")
    else:
        print("Situation intermediaire : ni pure periode, ni pur hasard.")
        print("Regarde la colonne %% SANS ci-dessus avant de conclure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
