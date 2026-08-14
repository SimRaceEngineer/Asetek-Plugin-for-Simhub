# -*- coding: utf-8 -*-
"""
matrice_croisement.py -- croiser les filtres deux a deux, avec le prix

  python matrice_croisement.py --schema
  python matrice_croisement.py
  python matrice_croisement.py --cassure 2026-08-05 --seuil 54

CE QU IL FAIT

    Les panneaux affichent une dizaine de filtres candidats -- setup
    rails, churn, trajectoire du gap HLC, consensus, seance. Chacun
    est lu seul. La question posee : que donne leur CROISEMENT, et
    combien de tickets survivent aux deux ?

    Pour chaque PAIRE, la matrice donne :

        n de l intersection   (en SIGNAUX, jumeaux 206/207 fusionnes)
        moyenne dans l intersection
        moyenne de chaque filtre SEUL
        l apport du croisement = intersection moins le meilleur des deux

    Un croisement qui n apporte rien repete un filtre deja pris. Un
    croisement qui apporte beaucoup sur douze signaux n apporte rien
    du tout : c est la colonne n qui decide, jamais la couleur.

POURQUOI CE N EST PAS UNE TABLE DE PROBABILITES

    Croiser des filtres CHOISIS APRES COUP multiplie les decoupes et
    divise l echantillon. Avec k filtres il y a k(k-1)/2 paires : a
    dix filtres, 45 comparaisons. Le seuil du paragraphe 0 monte en
    consequence, et la matrice l imprime au lieu de le taire.

    Aucune case ne dit "probabilite que ca marche". Elles disent
    "voila ce qui s est passe sur n signaux", ce qui n est pas la
    meme chose et ne le deviendra pas en le repetant.

LES FAMILLES -- le piege verifie aujourd hui

    Les blocs M1/M3/M5/M15 de la trajectoire HLC portent sur les
    MEMES tickets, repartis quatre fois : dans panel_rails_trades les
    quatre blocs totalisent 2 424 chacun. Croiser "M5 WIDENING" avec
    "M15 WIDENING" ne croise donc pas deux mesures, ca recoupe une
    mesure avec elle-meme sous un autre angle.

    Chaque filtre porte donc une FAMILLE. Une paire de la meme
    famille est marquee `=fam` et ne doit jamais etre lue comme une
    confirmation.

CE QUE LE BANC D ESSAI MONTRE -- a lire avant d exploiter une case

    Le banc fabrique 1 200 signaux avec DEUX effets principaux et
    AUCUNE interaction : seance US +12 contre -6 hors seance, et
    churn CHURN -10. Rien d autre.

    Le lecteur retrouve les deux (ecarts 13,4 et 12,6 pour 18 et 10
    attendus, l ecart venant du bruit a sigma = 60).

    Mais il affiche AUSSI `seance US x churn CLEAN : apport +10,23`
    sur 49 signaux -- une interaction qui n existe pas dans les
    donnees, puisque c est moi qui les ai ecrites. La matrice
    FABRIQUE donc des croisements apparents sous le seuil, sur
    commande et de facon reproductible.

    C est la raison d etre de la colonne n et du `?`. Une case
    marquee `?` n est pas "un resultat faible" : c est un resultat
    que le banc sait produire a partir de rien.

LA CASSURE

    Tout est calcule DEUX FOIS, avant et depuis le 5 aout, parce
    qu un chiffre agrege sur toute la fenetre melange cinq jours
    rentables et huit jours de pertes. C est la regle 2 du journal,
    et elle a deja piege deux sections du panneau quadruple
    aujourd hui.

Lecteur SEUL : il lit un .jsonl et ecrit un .txt. Aucun ordre,
aucun collecteur, aucun etat modifie.
"""
import argparse
import collections
import io
import json
import os
import sys
import datetime as dt

TRADES = os.path.join("docs", "churn_trades", "churn_trades.jsonl")
SORTIE = os.path.join("panels", "panel_matrice.txt")
SEUIL = 54
CASSURE = "2026-08-05"
LARG = 100

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(ts):
    if not ts:
        return None
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(str(ts)[:19], f)
        except ValueError:
            continue
    return None


def charger(chemin, limite):
    lot = []
    if not os.path.isfile(chemin):
        return lot
    for l in io.open(chemin, encoding="utf-8", errors="replace"):
        if not l.strip():
            continue
        try:
            lot.append(json.loads(l))
        except ValueError:
            continue
        if len(lot) >= limite:
            break
    return lot


def signaux(trades):
    """Fusionne les jumeaux 206/207 -- meme entree a 30 s pres, meme
    cellule magic%1000 -- en UN signal. Meme regle que _signals() de
    rails_trades_panel.py : sans elle un signal compte deux fois."""
    grp, ordre = {}, []
    for t in trades:
        if not t.get("entry_captured_live"):
            continue
        te = horo(t.get("entry_ts"))
        if te is None or t.get("pnl_eur") is None:
            continue
        m = int(t.get("magic") or 0)
        if m // 1000 in (206, 207):
            seau = int(te.timestamp() // 30)
            cle = ("IGN", t.get("asset"), t.get("dir"), m % 1000, seau)
        else:
            cle = ("SOLO", t.get("ticket"))
        if cle not in grp:
            grp[cle] = []
            ordre.append(cle)
        grp[cle].append(t)
    out = []
    for cle in ordre:
        arr = grp[cle]
        b = arr[0]
        pn = [float(x.get("pnl_eur") or 0) for x in arr]
        out.append({
            "t": horo(b.get("entry_ts")),
            "jour": str(b.get("entry_ts") or "")[:10],
            "h": str(b.get("entry_ts") or "")[11:16],
            "actif": b.get("asset"),
            "sens": b.get("dir"),
            "pnl": sum(pn) / len(pn),
            "rails_setup": b.get("rails_setup"),
            "churn": ((b.get("churn_entry") or {}).get("verdict")),
            "hlc": (b.get("hlc_churn_entry") or {}),
            "ll": (b.get("ll_entry") or {}),
        })
    return out


def seau_churn(v):
    v = (v or "").upper()
    if v in ("CLEAN", "OK", "TRADE"):
        return "CLEAN"
    if v in ("CHURN", "NOISE", "NO"):
        return "CHURN"
    if v:
        return "MIXED"
    return None


def hlc(s, tf, champ):
    """Le champ de trajectoire du gap s appelle `self_mom` dans les
    donnees reelles, pas `mom` -- j avais infere le nom depuis le code
    de rails_trades_panel.py et je me trompais. --schema l a montre
    avant la premiere lecture. On essaie les deux plutot que d en
    supposer un."""
    d = (s["hlc"] or {}).get(tf)
    if not isinstance(d, dict):
        return None
    if champ == "mom":
        v = d.get("self_mom")
        return v if v is not None else d.get("mom")
    return d.get(champ)


# Chaque filtre : (nom court, famille, predicat). La FAMILLE est ce
# qui empeche de croiser une mesure avec elle-meme.
def filtres():
    f = [("seance US", "heure",
          lambda s: "15:30" <= s["h"] < "19:30"),
         ("rails TIGHT", "rails",
          lambda s: s["rails_setup"] == "TIGHT_CROSS"),
         ("rails WIDE", "rails",
          lambda s: s["rails_setup"] == "WIDE"),
         ("churn CLEAN", "churn",
          lambda s: seau_churn(s["churn"]) == "CLEAN"),
         ("churn hors CHURN", "churn",
          lambda s: seau_churn(s["churn"]) in ("CLEAN", "MIXED"))]
    for tf in ("M1", "M3", "M5", "M15"):
        f.append(("%s WIDENING" % tf, "hlc_mom",
                  lambda s, _t=tf: hlc(s, _t, "mom") == "WIDENING"))
        f.append(("%s ALIGNE" % tf, "hlc_cons",
                  lambda s, _t=tf: str(hlc(s, _t, "consensus") or "")
                  .startswith("ALIGNED")))
    return f


def stat(v):
    n = len(v)
    if not n:
        return (0, 0.0)
    return (n, sum(v) / n)


def bloc(titre, lignes=None):
    dis()
    dis("=" * LARG)
    dis(titre)
    for l in (lignes or []):
        dis("  " + l)
    dis("=" * LARG)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trades", default=TRADES)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--cassure", default=CASSURE)
    p.add_argument("--seuil", type=int, default=SEUIL)
    p.add_argument("--limite", type=int, default=200000)
    p.add_argument("--schema", action="store_true",
                   help="montrer les champs REELS et sortir")
    a = p.parse_args()

    brut = charger(a.trades, a.limite)
    if not brut:
        print("KO : %s introuvable ou vide." % a.trades)
        print("     Lance depuis le dossier de la stack.")
        return 1
    sig = signaux(brut)

    # ---- le schema, avant toute conclusion -------------------------
    if a.schema or not sig:
        print("%d enregistrements, %d signaux apres fusion 206/207."
              % (len(brut), len(sig)))
        cles = collections.Counter()
        for t in brut[:5000]:
            for k in t.keys():
                cles[k] += 1
        print()
        print("champs presents (sur les 5000 premiers) :")
        for k, n in cles.most_common(60):
            print("  %-28s %6d" % (k, n))
        ex = None
        for t in brut:
            if t.get("hlc_churn_entry"):
                ex = t["hlc_churn_entry"]
                break
        print()
        if ex:
            print("hlc_churn_entry, TF observees : %s"
                  % ", ".join(sorted(str(x) for x in ex.keys())))
            for k, v in list(ex.items())[:1]:
                if isinstance(v, dict):
                    print("  champs de %s : %s"
                          % (k, ", ".join(sorted(v.keys()))))
        else:
            print("AUCUN enregistrement ne porte hlc_churn_entry --")
            print("les filtres HLC seront tous vides. Ce n est pas un")
            print("resultat, c est une absence de donnee.")
        vs = collections.Counter(str((t.get("churn_entry") or {})
                                     .get("verdict")) for t in brut)
        print()
        print("verdicts churn observes : %s"
              % ", ".join("%s(%d)" % (k, v) for k, v in vs.most_common(8)))
        rs = collections.Counter(str(t.get("rails_setup")) for t in brut)
        print("rails_setup observes    : %s"
              % ", ".join("%s(%d)" % (k, v) for k, v in rs.most_common(8)))
        return 0

    fl = filtres()
    k = len(fl)
    paires = k * (k - 1) // 2

    bloc("MATRICE DE CROISEMENT DES FILTRES",
         ["%d enregistrements -> %d signaux (jumeaux 206/207 fusionnes)."
          % (len(brut), len(sig)),
          "genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "",
          "%d filtres, donc %d paires examinees. Le paragraphe 0 dit"
          % (k, paires),
          "qu une comparaison annoncee d avance demande ~%d signaux ;"
          % a.seuil,
          "une cellule regardee parmi %d en demande DAVANTAGE." % paires,
          "Aucune de ces paires n a ete annoncee d avance. Elles sont",
          "donc TOUTES descriptives, et le `?` marque le minimum, pas",
          "le suffisant.",
          "",
          "`=fam` : les deux filtres viennent de la MEME famille, donc",
          "de la meme mesure vue sous deux angles. Verifie aujourd hui",
          "sur les blocs M1/M3/M5/M15, qui totalisent les memes 2 424",
          "tickets chacun. Une paire `=fam` ne confirme rien."])

    for cote, garde in (("DEPUIS le " + a.cassure,
                         lambda s: s["jour"] >= a.cassure),
                        ("AVANT le " + a.cassure,
                         lambda s: s["jour"] < a.cassure)):
        lot = [s for s in sig if s["jour"] and garde(s)]
        dis()
        dis("-" * LARG)
        dis("  %s -- %d signaux" % (cote, len(lot)))
        dis("-" * LARG)
        if not lot:
            dis("  aucun signal de ce cote.")
            continue

        n0, m0 = stat([s["pnl"] for s in lot])
        dis("  reference, tous signaux : n=%d  moy %+8.2f" % (n0, m0))
        dis()
        dis("  %-18s %-18s %6s %9s %9s %9s %9s"
            % ("filtre A", "filtre B", "n", "A+B", "A seul", "B seul",
               "apport"))
        dis("  " + "-" * (18 + 18 + 6 + 4 * 9 + 6))

        seuls = {}
        for nom, fam, f in fl:
            seuls[nom] = stat([s["pnl"] for s in lot if f(s)])

        for i in range(k):
            na, fa, pa = fl[i]
            for j in range(i + 1, k):
                nb, fb, pb = fl[j]
                v = [s["pnl"] for s in lot if pa(s) and pb(s)]
                n, m = stat(v)
                if not n:
                    continue
                sa, sb = seuls[na], seuls[nb]
                mieux = max(sa[1], sb[1]) if (sa[0] and sb[0]) else 0.0
                marque = "" if n >= a.seuil else "  ?"
                if fa == fb:
                    marque += "  =fam"
                dis("  %-18s %-18s %6d %+9.2f %+9.2f %+9.2f %+9.2f%s"
                    % (na, nb, n, m, sa[1], sb[1], m - mieux, marque))

    bloc("COMMENT LIRE",
         ["`apport` = moyenne du croisement moins la meilleure des deux",
          "moyennes seules. Positif = le croisement ajoute quelque",
          "chose. Proche de zero = le second filtre repete le premier.",
          "",
          "`?` = moins de %d signaux. A ce stade la valeur affichee" % a.seuil,
          "n est pas distinguable du bruit, quelle qu elle soit.",
          "",
          "`=fam` = meme famille de mesure. Ces paires sont affichees",
          "pour montrer la redondance, jamais pour la confirmer.",
          "",
          "Aucune ligne de cette matrice n est une regle. Une regle",
          "s ecrit AVANT de regarder, dans HYPOTHESES.md, avec son",
          "critere de refutation. Ce qui est trouve ici est une piste",
          "a re-tester sur donnees neuves."])

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)"
          % (a.sortie, os.path.getsize(a.sortie)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
