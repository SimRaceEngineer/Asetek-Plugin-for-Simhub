# -*- coding: utf-8 -*-
r"""
papers_regime.py -- IDENTIFIER ce que "CLEAN" veut dire, par empreinte

  python papers_regime.py

LECTEUR SEUL. N ECRIT RIEN.

LE PROBLEME, EN UN CALCUL

    L export annonce  M15 T / CLEAN  sur 441 trades.
    Le fichier contient 312 tickets a churn_entry.verdict == CLEAN.

    Un sous-ensemble de CLEAN ne peut pas compter 441 membres. Donc le
    "CLEAN" de l export N EST PAS `verdict == "CLEAN"`. J avais ecrit
    le contraire apres avoir lu une chasse aux jetons qui ne montrait
    que la presence du mot, jamais son effectif.

CE QU ON NE FAIT PAS

    Choisir la lecture qui arrange. Il y a plusieurs facons de lire le
    regime, et si on les essaie l une apres l autre en gardant celle
    qui donne le plus joli tableau, on a choisi la reponse.

CE QU ON FAIT

    On se sert des EFFECTIFS de l export comme d une EMPREINTE. Quatre
    lignes de la section ecartement sont connues et independantes :

        TIGHT_CROSS / CLEAN   214
        TIGHT_CROSS / MIXED   154
        MID / CLEAN           251
        WIDE / CLEAN          231

    Ces quatre nombres n ont pas ete choisis par nous ; ils viennent du
    panneau. Une lecture du regime qui les reproduit est identifiee.
    Une lecture qui n en reproduit aucun est refutee. C est un test,
    pas une preference.

    Toutes les lectures candidates sont declarees CI-DESSOUS, AVANT de
    voir un seul chiffre, et TOUTES sont imprimees avec leur ecart --
    y compris les perdantes. On ne montre pas seulement la gagnante.

SI AUCUNE NE PASSE

    Alors l export ne porte pas sur cette population -- periode
    differente, filtre different, ou champ que nous n avons pas. Ce
    sera dit tel quel. Une lecture "presque" ne sera pas promue
    gagnante : 441 contre 312 etait deja un "presque", et c etait une
    impossibilite.
"""
import argparse
import io
import json
import os
import sys

CIBLE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")

# L empreinte : (rails_setup, regime_export, effectif annonce).
EMPREINTE = [
    ("TIGHT_CROSS", "CLEAN", 214),
    ("TIGHT_CROSS", "MIXED", 154),
    ("MID",         "CLEAN", 251),
    ("WIDE",        "CLEAN", 231),
]

# Les lectures candidates. Chacune rend "CLEAN", "MIXED", "CHURN" ou
# None a partir du ticket. DECLAREES AVANT MESURE.
def L_verdict(t):
    """A -- le verdict tel quel."""
    v = (t.get("churn_entry") or {}).get("verdict")
    return v if v in ("CLEAN", "MIXED", "CHURN") else None


def L_ok_avec_clean(t):
    """B -- OK compte comme CLEAN. 312 + 926 = 1238 tickets propres."""
    v = (t.get("churn_entry") or {}).get("verdict")
    if v in ("OK", "CLEAN"):
        return "CLEAN"
    return v if v in ("MIXED", "CHURN") else None


def _regime_tf(t, tf):
    c = t.get("churn_entry") or {}
    d = c.get(tf)
    return d.get("regime") if isinstance(d, dict) else None


def _fabrique_tf(tf):
    def f(t):
        """C -- le regime par unite de temps, vocabulaire TRADE/NOISE."""
        r = _regime_tf(t, tf)
        if r == "TRADE":
            return "CLEAN"
        if r == "NEUTRAL":
            return "MIXED"
        if r in ("CHURN", "NOISE"):
            return "CHURN"
        return None
    f.__doc__ = "C(%s) -- regime %s : TRADE=CLEAN, NEUTRAL=MIXED" % (tf, tf)
    return f


def L_churn_avg(t):
    """D -- seuil sur churn_avg : <=33 CLEAN, <=66 MIXED, sinon CHURN."""
    v = (t.get("churn_entry") or {}).get("churn_avg")
    if not isinstance(v, (int, float)):
        return None
    return "CLEAN" if v <= 33 else ("MIXED" if v <= 66 else "CHURN")


LECTURES = [("A  verdict tel quel", L_verdict),
            ("B  OK compte comme CLEAN", L_ok_avec_clean),
            ("C1 regime M1", _fabrique_tf("M1")),
            ("C3 regime M3", _fabrique_tf("M3")),
            ("C5 regime M5", _fabrique_tf("M5")),
            ("C15 regime M15", _fabrique_tf("M15")),
            ("D  seuil sur churn_avg", L_churn_avg)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        return 1

    tickets = []
    ko = 0
    with io.open(a.fichier, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                o = json.loads(ligne)
            except ValueError:
                ko += 1
                continue
            if isinstance(o, dict):
                tickets.append(o)

    L = []
    add = L.append
    add("=" * 76)
    add("IDENTIFIER LE REGIME PAR EMPREINTE")
    add("=" * 76)
    add("  %d tickets lus%s" % (len(tickets), ", %d illisibles" % ko if ko else ""))
    add("")
    add("  L export annonce quatre effectifs que nous n avons pas choisis.")
    add("  Une lecture du regime qui les reproduit est identifiee ; une")
    add("  lecture qui ne les reproduit pas est refutee. Toutes les")
    add("  lectures candidates ont ete declarees avant mesure et toutes")
    add("  sont imprimees, y compris les perdantes.")
    add("")
    add("  attendu :  %s" % "   ".join(
        "%s/%s=%d" % (s, r, n) for s, r, n in EMPREINTE))
    add("")
    add("  %-26s %s   %s" % ("LECTURE", "   ".join(
        "%-9s" % ("%s/%s" % (s[:2], r[:2])) for s, r, _ in EMPREINTE),
        "ecart total"))
    add("  " + "-" * 72)

    resultats = []
    for nom, f in LECTURES:
        obtenus, ecart = [], 0
        for setup, reg, attendu in EMPREINTE:
            n = 0
            for t in tickets:
                if t.get("rails_setup") != setup:
                    continue
                try:
                    if f(t) == reg:
                        n += 1
                except Exception:
                    pass
            obtenus.append(n)
            ecart += abs(n - attendu)
        resultats.append((ecart, nom, obtenus))
        add("  %-26s %s   %d"
            % (nom, "   ".join("%-9d" % x for x in obtenus), ecart))

    add("")
    resultats.sort()
    meilleur = resultats[0]
    add("=" * 76)
    add("CONCLUSION")
    add("=" * 76)
    if meilleur[0] == 0:
        add("  IDENTIFIE : %s reproduit les quatre effectifs exactement." % meilleur[1])
        add("  Les predicats peuvent etre ecrits sur cette lecture.")
    else:
        add("  AUCUNE lecture ne reproduit l empreinte.")
        add("  La moins eloignee est %s, a %d de distance totale --"
            % (meilleur[1], meilleur[0]))
        add("  ce qui ne la rend PAS gagnante. Un ecart non nul veut dire")
        add("  que l export ne porte pas sur cette population : periode")
        add("  differente, filtre different, ou champ que nous n avons pas.")
        add("")
        add("  Consequence a assumer : les effectifs de l export ne sont")
        add("  pas reproductibles ici, donc la colonne ATTENDU du tableau")
        add("  de bord ne peut pas etre confrontee a un CONSTATE calcule")
        add("  sur ces tickets. Il faudra mesurer en avant, ou retrouver")
        add("  la population d origine.")
    add("")
    add("  Rappel de ce que ce test ne dit pas : il identifie un CHAMP,")
    add("  pas une qualite. Meme identifie, le regime ne rend aucune")
    add("  strategie bonne -- il rend seulement son effectif calculable.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
