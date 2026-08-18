# -*- coding: utf-8 -*-
r"""
papers_moteur.py -- les 17 papers qui tournent, en lecture seule

  python papers_moteur.py                 une passe
  python papers_moteur.py --rapport       le rapport sans rien traiter
  python papers_moteur.py --reset         repart de zero (demande --oui)

CE QU IL FAIT, ET CE QU IL NE FAIT PAS

    Il LIT le journal des tickets du moteur churn. Pour chaque ticket
    nouveau, il demande a chacun des 17 papers : est-ce que tu aurais
    pris celui-la ? Si oui, il enregistre une prise papier, dimensionnee
    sur une balance FICTIVE.

    Il N ENVOIE AUCUN ORDRE. Il n importe pas MetaTrader5, ne touche a
    aucun processus, et n ecrit que dans docs\papers_live\, panels\ et
    cartes\. Le journal source est ouvert en LECTURE.

POURQUOI IL NE CHOISIT PAS SES ENTREES, ET POURQUOI C EST VOULU

    Les lignes de l export rails_trades sont des ATTRIBUTIONS : elles
    disent ce que les trades du moteur churn ont fait quand tel etat
    tenait. Un moteur qui inventerait ses propres instants d entree ne
    serait comparable a rien -- ni a l export, ni aux autres papers.

    En filtrant les MEMES entrees, la comparaison entre les 17 est a
    armes egales, et la confrontation a la colonne ATTENDU garde un
    sens. C est une limite assumee, pas un raccourci : ces papers ne
    mesurent pas un timing, ils mesurent un FILTRE.

LE DIMENSIONNEMENT

    Balance FICTIVE de depart 20 000, propre a chaque paper.
    lot = balance / 20 000, plancher 0,01. Recalcule avant chaque prise.

    Le ticket porte son volume REEL et son pnl_eur. La prise papier vaut

        pnl_papier = pnl_eur x (lot_fictif / volume_reel)

    Ce qui suppose que le resultat est proportionnel a la taille -- vrai
    hors slippage et hors partiels. Le journal garde les deux valeurs
    pour qu on puisse verifier plus tard.

IDEMPOTENT, ET SUR L IDENTIFIANT

    L etat retient les TICKETS DEJA VUS, par leur identifiant, pas par
    horodatage. Relancer ne duplique rien.

    Caler sur le dernier horodatage aurait jete tout ticket arrive en
    retard -- le journal des tickets est un join produit par
    rails_join.py, rien ne garantit qu il arrive dans l ordre. Sur l
    identifiant, un retardataire est simplement traite au passage
    suivant.

D OU VIENNENT LES 17

    Dix de papers_regles.py, serie 240000, gelees le 18/08 et definies
    directement sur les champs.

    Sept de papers_encode.py, les seuls magics de l export dont TOUTES
    les cles ont retombe exactement sur leur effectif annonce. Les
    trente-neuf autres sont dehors : cle non validee, cle non encodee,
    ou croisement vide. Ils rentreront quand leur cle sera reparee.
"""
import argparse
import io
import json
import os
import sys

SOURCE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
DOSSIER = os.path.join("docs", "papers_live")
JOURNAL = os.path.join(DOSSIER, "trades.jsonl")
ETAT = os.path.join(DOSSIER, "etat.json")

BALANCE0 = 20000.0
LOT_PAR = 20000.0
LOT_MINI = 0.01


def _charge_modules():
    """Importe les definitions plutot que de les recopier.

    Une copie de plus serait une source de verite de plus a maintenir --
    c est exactement ce qui a produit les deux TIGHT_SPREAD du 18/08.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")
    manque = []
    try:
        import papers_encode as pe
    except ImportError:
        pe, _ = None, manque.append("papers_encode.py")
    try:
        import papers_regles as pr
    except ImportError:
        pr, _ = None, manque.append("papers_regles.py")
    return pe, pr, manque


# Les sept magics de l export dont toutes les cles ont valide le 18/08.
# (magic, nom, actif impose, cles). L actif vient de la numerotation :
# 1xx = US30, 2xx = US500, 3xx = US100. La cle TC_CLEAN ne filtre aucun
# actif ; c est le magic qui le fait, donc chacun prend environ un tiers.
SEPT = [
    (230101, "US BASE CLEAN",           "US30",  ["TC_CLEAN"]),
    (230201, "US BASE CLEAN",           "US500", ["TC_CLEAN"]),
    (230301, "US BASE CLEAN",           "US100", ["TC_CLEAN"]),
    (230107, "US HLC SPLIT CONFLUENCE", "US30",  ["M15_SPL_CL"]),
    (230207, "US HLC SPLIT CONFLUENCE", "US500", ["M15_SPL_CL"]),
    (230307, "US HLC SPLIT CONFLUENCE", "US100", ["M15_SPL_CL"]),
    (230210, "US MULTI-TF M3+M5+M15",   "US500", ["M3M5M15"]),
]


def papers(pe, pr):
    """Rend la liste (magic, nom, actif, sens, predicat)."""
    L = []
    cles = dict((c[0], c[3]) for c in pe.CLES if c[3] is not None)
    for magic, nom, actif, kk in SEPT:
        manquantes = [k for k in kk if k not in cles]
        if manquantes:
            continue
        preds = [cles[k] for k in kk]
        L.append((magic, nom, actif, None,
                  (lambda t, _p=preds: all(f(t) for f in _p))))
    for magic, nom, sens, f in pr.REGLES:
        L.append((magic, nom, None, sens, f))
    return L


def lire_jsonl(chemin):
    out, ko = [], 0
    if not os.path.isfile(chemin):
        return out, ko
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                ko += 1
                continue
            if isinstance(o, dict):
                out.append(o)
    return out, ko


def lire_etat():
    vide = {"vus": [], "balances": {}}
    if not os.path.isfile(ETAT):
        return vide
    try:
        e = json.loads(io.open(ETAT, encoding="utf-8").read())
        if isinstance(e, dict) and "balances" in e:
            e.setdefault("vus", [])
            return e
    except (ValueError, IOError):
        pass
    return vide


def ecrire_etat(e):
    if not os.path.isdir(DOSSIER):
        os.makedirs(DOSSIER)
    io.open(ETAT, "w", encoding="utf-8", newline="").write(
        json.dumps(e, indent=1, sort_keys=True))


def lots(balance):
    return max(LOT_MINI, round(balance / LOT_PAR, 2))


def wilson_bas(p, n, z=1.96):
    if n <= 0:
        return 0.0
    d = 1.0 + z * z / n
    c = p + z * z / (2.0 * n)
    r = z * ((p * (1.0 - p) / n + z * z / (4.0 * n * n)) ** 0.5)
    return max(0.0, (c - r) / d)


def rr_equilibre(p):
    return (1.0 - p) / p if p > 0 else float("inf")


def traite(jeu, tickets, etat):
    """Une passe. Rend (prises, n_deja_vus, n_sans_volume)."""
    prises, deja, sans_vol = [], 0, 0
    vus = set(etat.setdefault("vus", []))
    bal = etat.setdefault("balances", {})
    # On traite dans l ordre chronologique pour que la balance compose
    # dans le bon sens, meme si le journal arrive dans le desordre.
    for t in sorted(tickets, key=lambda x: str(x.get("entry_ts") or "")):
        ts = t.get("entry_ts")
        if not isinstance(ts, str) or len(ts) < 19:
            continue
        ident = t.get("ticket")
        if ident is None:
            ident = "%s|%s|%s" % (ts, t.get("asset"), t.get("dir"))
        if ident in vus:
            deja += 1
            continue
        vus.add(ident)
        vol = t.get("volume")
        pnl_reel = t.get("pnl_eur")
        if not isinstance(vol, (int, float)) or vol <= 0 \
                or not isinstance(pnl_reel, (int, float)):
            sans_vol += 1
            continue
        for magic, nom, actif, sens, pred in jeu:
            if actif and t.get("asset") != actif:
                continue
            if sens == "achat" and t.get("dir") != "BUY":
                continue
            if sens == "vente" and t.get("dir") != "SELL":
                continue
            try:
                if not pred(t):
                    continue
            except Exception:
                continue
            k = str(magic)
            b = bal.get(k, BALANCE0)
            lot = lots(b)
            f = lot / float(vol)
            pnl = pnl_reel * f
            bal[k] = b + pnl
            prises.append({
                "magic": magic, "nom": nom, "ts": ts,
                "actif": t.get("asset"), "sens": t.get("dir"),
                "lot": lot, "vol_reel": vol, "facteur": round(f, 4),
                "pnl": round(pnl, 2), "pnl_reel": pnl_reel,
                "mfe": round((t.get("mfe_eur") or 0.0) * f, 2),
                "mae": round((t.get("mae_eur") or 0.0) * f, 2),
                "balance": round(bal[k], 2), "ticket": t.get("ticket")})
    etat["vus"] = sorted(vus, key=str)
    return prises, deja, sans_vol


def rapport(jeu, journal):
    par = {}
    for p in journal:
        par.setdefault(p["magic"], []).append(p)
    L = []
    a = L.append
    a("=" * 104)
    a("PAPERS EN LIGNE -- %d magics" % len(jeu))
    a("=" * 104)
    a("  Balance FICTIVE de depart %.0f par paper, lot = balance / %.0f,"
      % (BALANCE0, LOT_PAR))
    a("  plancher %.2f, recalcule avant chaque prise." % LOT_MINI)
    a("")
    a("  CES PAPERS FILTRENT LES ENTREES DU MOTEUR CHURN, ils n en")
    a("  choisissent pas. Ils mesurent un FILTRE, pas un timing. Deux")
    a("  strategies qui entreraient a des instants differents sur le meme")
    a("  etat n auraient aucune raison de faire le meme resultat.")
    a("")
    a("  %-7s %-26s %-6s %5s %6s %6s %6s %9s %9s"
      % ("MAGIC", "NOM", "ACTIF", "n", "taux", "borne", "RReq",
         "PnL", "balance"))
    a("  " + "-" * 100)
    for magic, nom, actif, sens, _ in jeu:
        pp = par.get(magic, [])
        n = len(pp)
        if not n:
            a("  %-7d %-26s %-6s %5d %6s %6s %6s %9s %9.2f"
              % (magic, nom[:26], actif or "tous", 0, "-", "-", "-", "-",
                 BALANCE0))
            continue
        g = sum(1 for x in pp if x["pnl"] > 0)
        taux = g / float(n)
        tot = sum(x["pnl"] for x in pp)
        a("  %-7d %-26s %-6s %5d %5.0f%% %5.0f%% %6.2f %9.2f %9.2f"
          % (magic, nom[:26], actif or "tous", n, 100 * taux,
             100 * wilson_bas(taux, n), rr_equilibre(taux), tot,
             pp[-1]["balance"]))
    a("  " + "-" * 100)
    a("")
    a("  borne  borne basse de Wilson a 95 %% sur le taux : ce qu on peut")
    a("         defendre, pas ce qu on a observe.")
    a("  RReq   (1-p)/p : le rapport gain/perte sous lequel le paper perd,")
    a("         quelle que soit sa qualite par ailleurs.")
    a("")
    a("  Un paper a moins de 30 prises ne dit rien encore. La borne de")
    a("  Wilson le rappelle toute seule : elle s effondre quand n est bas.")
    return L


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=SOURCE)
    p.add_argument("--rapport", action="store_true",
                   help="imprime le rapport sans traiter de nouveau ticket")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--oui", action="store_true",
                   help="confirme le --reset")
    a = p.parse_args()

    pe, pr, manque = _charge_modules()
    if manque:
        print("KO : introuvable(s) -- %s" % ", ".join(manque))
        print("Ils doivent etre dans le meme dossier que ce script.")
        return 1

    if a.reset:
        if not a.oui:
            print("--reset efface le journal et les balances.")
            print("Relance avec --reset --oui si c est bien voulu.")
            return 1
        for f in (JOURNAL, ETAT):
            if os.path.isfile(f):
                os.remove(f)
        print("journal et etat effaces.")

    jeu = papers(pe, pr)
    journal, ko_j = lire_jsonl(JOURNAL)

    if not a.rapport:
        tickets, ko_t = lire_jsonl(a.source)
        if not tickets:
            print("KO : aucun ticket lisible dans %s" % a.source)
            return 1
        etat = lire_etat()
        avant = len(etat.get("vus") or [])
        prises, deja, sans_vol = traite(jeu, tickets, etat)
        if prises:
            if not os.path.isdir(DOSSIER):
                os.makedirs(DOSSIER)
            with io.open(JOURNAL, "a", encoding="utf-8", newline="") as f:
                for x in prises:
                    f.write(json.dumps(x, sort_keys=True) + "\n")
        ecrire_etat(etat)
        journal.extend(prises)
        print("  source   : %s  (%d tickets%s)"
              % (a.source, len(tickets),
                 ", %d illisibles" % ko_t if ko_t else ""))
        print("  deja vus : %d ticket(s) avant cette passe" % avant)
        print("  nouveaux : %d ticket(s) traites" % (
            len(etat.get("vus") or []) - avant))
        print("  nouvelles prises : %d" % len(prises))
        if deja:
            print("  %d ticket(s) deja traites, ignores sans les rejouer."
                  % deja)
        if sans_vol:
            print("  %d ticket(s) sans volume ou sans pnl : non"
                  " dimensionnables." % sans_vol)
        print()

    L = rapport(jeu, journal)
    txt = "\n".join(L)
    print(txt)

    for dossier, nom in ((("panels"), "panel_papers_live.txt"),
                         (("cartes"), "papers_live.html")):
        if not os.path.isdir(dossier):
            os.makedirs(dossier)
        che = os.path.join(dossier, nom)
        if nom.endswith(".html"):
            h = (txt.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;"))
            contenu = ('<pre style="font:12px Consolas,monospace;'
                       'color:#c9d1d9;background:#0e1116;padding:16px 20px;'
                       'margin:0;white-space:pre">' + h + "</pre>\n")
        else:
            contenu = txt + "\n"
        io.open(che, "w", encoding="utf-8", newline="").write(contenu)
        print("  ecrit : %s" % che)
    return 0


if __name__ == "__main__":
    sys.exit(main())
