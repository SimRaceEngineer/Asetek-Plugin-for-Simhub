# -*- coding: utf-8 -*-
"""
croix_or.py -- la croix des rails, dans les deux sens, sur les 4 unites
               et les 3 actifs. Que valent NOS entrees selon l etat ?

  python croix_or.py
  python croix_or.py --seuil 2.0
  python croix_or.py --croise          (l actif de la croix != l actif trade)

CE QU ON PEUT MESURER, ET CE QU ON NE PEUT PAS

    Le journal garde un INSTANTANE a l entree, pas une serie. On peut
    donc lire l ETAT des deux rails au moment ou le trade s ouvre --
    lequel est au-dessus, et de combien -- mais PAS l instant du
    croisement. Un vrai  golden cross  est un evenement ; ce que ce
    script mesure est le REGIME qu il installe.

    C est une difference qui compte. Entrer trois secondes apres un
    croisement et entrer deux heures apres tombent ici dans la meme
    case. Si le regime ne dit rien mais que l evenement dit quelque
    chose, ce script ne le verra pas -- il faudrait rejouer les series,
    pas le journal des tickets.

LA CONVENTION

    OR    (golden) : bull au-dessus de bear.
    MORT  (death)  : bear au-dessus de bull.
    PLAT           : ecart plus petit que --seuil, les deux rails colles.

    Le seuil existe parce qu un ecart de 0.1 n est pas un regime, c est
    du bruit d arrondi. A --seuil 0 le PLAT disparait.

LE PIEGE DU NOMBRE DE CASES

    3 actifs x 4 unites x 3 etats x 2 sens = 72 cases. A 0,05, en
    attendre trois ou quatre remarquables par pur hasard est NORMAL.
    Le script les compte et le dit. Une case ne vaut donc rien seule :
    ce qui vaut, c est qu elle soit du meme signe seance apres seance
    ET qu elle survive au retrait de ses deux pires journees.
"""
import argparse
import io
import json
import math
import os
import sys

try:
    import oos_v9 as O
except ImportError:
    print("KO : oos_v9.py introuvable a cote de ce script.")
    sys.exit(1)

DEFAUT = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
ACTIFS = ["US30", "US500", "US100"]
LARG = 82


def trait(c="-"):
    print("  " + c * LARG)


def titre(t):
    print("")
    print("=" * (LARG + 4))
    print(t)
    print("=" * (LARG + 4))


def mediane(v):
    if not v:
        return 0.0
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def quantile(v, q):
    if not v:
        return 0.0
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(len(s) * q)))]


def binom(k, n):
    """P(X >= k) avec p = 1/2, exact."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(k, n + 1)) / float(2 ** n)


def rail(t, actif, tf, cle):
    """rails_entry[actif][tf][cle], sinon la forme a plat cle_m5."""
    d = ((t.get("rails_entry") or {}).get(actif) or {}).get(tf)
    if isinstance(d, dict) and d.get(cle) is not None:
        return d.get(cle)
    return t.get("%s_%s" % (cle, tf.lower()))


def ecart(t, actif, tf):
    """bull - bear, ou None si l un des deux manque."""
    b = O._nombre(rail(t, actif, tf, "bull"))
    r = O._nombre(rail(t, actif, tf, "bear"))
    if b is None or r is None:
        return None
    return b - r


def etat(e, seuil):
    if e is None:
        return None
    if e > seuil:
        return "OR"
    if e < -seuil:
        return "MORT"
    return "PLAT"


def charger(chemin):
    par, brut = {}, 0
    if not os.path.isfile(chemin):
        print("FICHIER INTROUVABLE : %s" % chemin)
        print("Repertoire courant  : %s" % os.getcwd())
        sys.exit(1)
    for l in io.open(chemin, encoding="utf-8-sig"):
        l = l.strip()
        if not l or l[0] != "{":
            continue
        brut += 1
        try:
            o = json.loads(l)
        except ValueError:
            continue
        ts = str(O._prem(o, O.CLEFS_TS) or "")
        pnl = O._nombre(O._prem(o, O.CLEFS_PNL))
        tk = O._prem(o, O.CLEFS_TICKET)
        if len(ts) < 10 or pnl is None or tk is None or tk in par:
            continue
        sens = str(O._prem(o, O.CLEFS_SENS) or "").upper()
        if sens in O.SENS_ACHAT:
            sens = "BUY"
        elif sens in O.SENS_VENTE:
            sens = "SELL"
        else:
            sens = "?"
        par[tk] = {"jour": ts[:10], "pnl": pnl, "sens": sens,
                   "actif": o.get("asset"), "brut": o}
    if not par:
        print("Aucun enregistrement exploitable sur %d lignes." % brut)
        sys.exit(1)
    return list(par.values())


def bloc_couverture(tk, seuil):
    titre("CE QUE LE JOURNAL PORTE -- les deux rails se croisent-ils ?")
    print("")
    print("  Si  bull - bear  garde toujours le meme signe, ce ne sont pas")
    print("  deux lignes qui se croisent et tout le reste est sans objet.")
    print("")
    print("   actif   tf     n      min      p10   mediane      p90      max"
          "   % OR")
    trait()
    vivant = []
    for a in ACTIFS:
        for tf in O.TFS:
            v = [e for e in (ecart(t["brut"], a, tf) for t in tk)
                 if e is not None]
            if not v:
                print("   %-7s %-4s     0   -- absent du journal --" % (a, tf))
                continue
            pos = 100.0 * sum(1 for x in v if x > 0) / len(v)
            print("   %-7s %-4s %5d %8.1f %8.1f %9.1f %8.1f %8.1f %6.1f"
                  % (a, tf, len(v), min(v), quantile(v, 0.10), mediane(v),
                     quantile(v, 0.90), max(v), pos))
            if 2.0 < pos < 98.0:
                vivant.append((a, tf))
    trait()
    print("")
    if not vivant:
        print("  AUCUN couple (actif, unite) ne change de signe. Les rails")
        print("  ne se croisent jamais dans ce journal : la notion de croix")
        print("  d or n y est pas definie. Rien de plus a mesurer.")
        return None
    print("  %d couple(s) sur %d changent reellement de signe."
          % (len(vivant), len(ACTIFS) * len(O.TFS)))
    print("  Seuls ceux-la sont analyses ci-dessous.")
    return vivant


def cellules(tk, vivant, seuil, croise):
    """(actif_croix, tf, etat, sens) -> liste de trades."""
    d = {}
    for t in tk:
        for a, tf in vivant:
            if not croise and t["actif"] != a:
                continue
            e = etat(ecart(t["brut"], a, tf), seuil)
            if e is None:
                continue
            d.setdefault((a, tf, e, t["sens"]), []).append(t)
    return d


def bloc_tableau(d, seuil):
    titre("LE RENDU DE NOS ENTREES, PAR ETAT DE LA CROIX")
    print("")
    print("  PLAT = les deux rails a moins de %.1f l un de l autre." % seuil)
    print("")
    print("   actif   tf   etat   sens     n      PnL   PnL/trade   mediane"
          "   seances")
    print("   %-56s rouges" % "")
    trait()
    lignes = []
    for (a, tf, e, s), v in sorted(d.items()):
        if s == "?" or len(v) < 20:
            continue
        pnl = sum(x["pnl"] for x in v)
        par_j = {}
        for x in v:
            par_j[x["jour"]] = par_j.get(x["jour"], 0.0) + x["pnl"]
        rouges = sum(1 for x in par_j.values() if x < 0)
        lignes.append((pnl / len(v), a, tf, e, s, len(v), pnl,
                       mediane([x["pnl"] for x in v]), rouges, len(par_j),
                       par_j))
    for pt, a, tf, e, s, n, pnl, med, rouges, nj, _pj in sorted(
            lignes, reverse=True):
        print("   %-7s %-4s %-6s %-5s %5d %8.1f %11.2f %9.2f    %2d/%-2d"
              % (a, tf, e, s, n, pnl, pt, med, rouges, nj))
    trait()
    return lignes


def bloc_survivants(lignes, seuil_pt):
    titre("CE QUI SURVIT AUX DEUX GARDE-FOUS")
    print("")
    print("  1. le signe doit etre regulier SEANCE par seance")
    print("  2. le total ne doit pas venir de deux journees")
    print("")
    n_cases = len(lignes)
    gardes = []
    for pt, a, tf, e, s, n, pnl, med, rouges, nj, pj in lignes:
        if abs(pt) < seuil_pt or nj < 8:
            continue
        gagne = pt > 0
        k = (nj - rouges) if gagne else rouges
        p = binom(k, nj)
        v = sorted(pj.values(), reverse=not gagne)
        sans2 = sum(v[2:])
        tient = (sans2 > 0) if gagne else (sans2 < 0)
        gardes.append((p, a, tf, e, s, n, pt, k, nj, sans2, tient))
    # Le seuil corrige : avec m cases essayees, exiger 0,05 sur CHACUNE
    # revient a accepter m fois plus de faux positifs. Holm au premier
    # rang, c est 0,05/m -- la barre que doit franchir la meilleure case
    # pour qu on puisse parler d autre chose que de hasard.
    corrige = 0.05 / max(1, n_cases)
    retenus = [g for g in gardes if g[0] < 0.05]
    if not retenus:
        print("  Aucune case sous p = 0,05. Sur %d essais c est exactement"
              % n_cases)
        print("  ce qu on attend d un jeu sans signal. Rien a retenir.")
        return
    print("   actif   tf   etat   sens     n  PnL/trade  seances    p"
          "   sans 2 pires   verdict")
    trait()
    for p, a, tf, e, s, n, pt, k, nj, sans2, tient in sorted(retenus):
        if p < corrige and tient:
            v = "SOLIDE"
        elif tient:
            v = "candidat"
        else:
            v = "rejete"
        print("   %-7s %-4s %-6s %-5s %5d %10.2f    %2d/%-2d %7.4f %10.1f   %s"
              % (a, tf, e, s, n, pt, k, nj, p, sans2, v))
    trait()
    print("")
    print("  %d case(s) essayees, %d sous 0,05. A ce compte, en attendre"
          % (n_cases, len(retenus)))
    print("  %.1f par pur hasard : %s"
          % (0.05 * n_cases,
             "on en a moins que ca, donc rien"
             if len(retenus) <= 0.05 * n_cases else
             "on en a plus, mais l exces est faible"))
    print("")
    print("  SOLIDE   = p < %.5f (0,05 corrige des %d essais) ET le total"
          % (corrige, n_cases))
    print("             tient sans ses deux pires journees.")
    print("  candidat = passe 0,05 brut seulement. A revoir sur des")
    print("             seances qui n ont pas servi a le trouver.")
    print("  rejete   = le total vient de deux journees.")


def bloc_accord(tk, vivant, seuil):
    titre("LES QUATRE UNITES SONT-ELLES D ACCORD ?")
    print("")
    print("  Un regime lisible sur une seule unite et contredit par les")
    print("  trois autres n est pas un regime. Ce tableau dit a quelle")
    print("  frequence les unites disponibles pointent dans le meme sens.")
    print("")
    par_actif = {}
    for a in ACTIFS:
        tfs = [tf for (aa, tf) in vivant if aa == a]
        if len(tfs) < 2:
            continue
        for t in tk:
            ets = [etat(ecart(t["brut"], a, tf), seuil) for tf in tfs]
            ets = [e for e in ets if e is not None]
            if len(ets) < 2:
                continue
            if all(e == "OR" for e in ets):
                k = "toutes OR"
            elif all(e == "MORT" for e in ets):
                k = "toutes MORT"
            else:
                k = "melangees"
            par_actif.setdefault(a, {}).setdefault(k, []).append(t["pnl"])
    if not par_actif:
        print("  Moins de deux unites exploitables : rien a comparer.")
        return
    print("   actif   accord           n      PnL   PnL/trade")
    trait()
    for a in ACTIFS:
        for k in ("toutes OR", "toutes MORT", "melangees"):
            v = par_actif.get(a, {}).get(k)
            if not v:
                continue
            print("   %-7s %-14s %5d %8.1f %11.2f"
                  % (a, k, len(v), sum(v), sum(v) / len(v)))
    trait()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=DEFAUT)
    p.add_argument("--seuil", type=float, default=1.0,
                   help="ecart en dessous duquel les rails sont dits PLAT")
    p.add_argument("--minpt", type=float, default=2.0,
                   help="PnL/trade minimum pour qu une case soit examinee")
    p.add_argument("--croise", action="store_true",
                   help="croiser tous les trades avec la croix de CHAQUE actif")
    a = p.parse_args()

    tk = charger(a.fichier)
    jours = sorted(set(t["jour"] for t in tk))
    titre("LA CROIX DES RAILS -- OR ET MORT, 4 UNITES, 3 ACTIFS")
    print("")
    print("  %d tickets, %d seances, du %s au %s"
          % (len(tk), len(jours), jours[0], jours[-1]))
    print("  seuil PLAT : %.1f    cases retenues : PnL/trade >= %.1f"
          % (a.seuil, a.minpt))
    print("  %s" % ("croise : chaque trade contre les 3 croix"
                    if a.croise else "chaque trade contre la croix de SON actif"))
    print("  Lecture seule. Rien n est ecrit, rien n est envoye.")

    vivant = bloc_couverture(tk, a.seuil)
    if not vivant:
        return
    d = cellules(tk, vivant, a.seuil, a.croise)
    lignes = bloc_tableau(d, a.seuil)
    bloc_survivants(lignes, a.minpt)
    bloc_accord(tk, vivant, a.seuil)

    print("")
    print("=" * (LARG + 4))
    print(" Rappel : c est l ETAT au moment de l entree qui est mesure,")
    print(" pas l instant du croisement. Le journal ne porte qu un")
    print(" instantane par ticket -- il ne peut pas dire  il vient de")
    print(" croiser . Ce qui est teste ici, c est le regime.")
    print("=" * (LARG + 4))


if __name__ == "__main__":
    main()
