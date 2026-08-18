# -*- coding: utf-8 -*-
r"""
papers_regles.py -- DIX REGLES EXECUTABLES, gelees le 18/08/2026

  python papers_regles.py
  python papers_regles.py --decalage 2      (heure serveur -> Paris)

LECTEUR SEUL. N ECRIT RIEN.

POURQUOI UNE NOUVELLE SERIE

    Les 220000 et 230000 ont ete batis en croisant les sections d un
    export. Mesure du 18/08 : 14 d entre eux reposent sur des etats que
    rien ne journalise (T/S, etoile, with/against, pentes), et les 22
    autres sur un regime dont sept lectures ont ete testees sans qu
    aucune ne reproduise les effectifs annonces. Ils ne sont donc pas
    verifiables sur l historique.

    On ne les efface pas : ils restent l archive de ce qui a ete promis.
    La serie 240000 repart des CHAMPS QUI EXISTENT, verifies un par un
    dans tickets_rails.jsonl le 18/08.

CE QUE CE SCRIPT MESURE, ET CE QU IL NE MESURE PAS

    IL MESURE la FREQUENCE. Combien de fois chaque etat s est presente,
    sur quelle periode, combien de fois par jour ouvre. C est le
    chiffre qui decide si une regle sera jugeable avant 2027 : une
    regle qui sort trois fois par mois ne prouvera rien de l annee.

    IL NE MESURE PAS la performance de la strategie. Le PnL affiche est
    celui que le MOTEUR CHURN a realise sur ces memes tickets. L entree
    est la sienne, pas celle de la regle. Deux strategies qui entrent a
    des instants differents sur le meme etat n ont aucune raison de
    faire le meme resultat. Cette colonne dit "voila ce qui s est passe
    quand cet etat tenait", jamais "voila ce que la regle aurait fait".

    Confondre les deux serait exactement l erreur du tableau de bord
    des 220000 : presenter une attribution comme une prevision.

LES REGLES SONT GELEES

    Elles sont ecrites ci-dessous et datees. Elles ne seront PAS
    retouchees apres avoir vu les frequences. Si l une sort trop rare
    pour etre jugeable, elle sera ABANDONNEE, pas elargie jusqu a
    devenir frequente -- elargir apres coup, c est choisir la reponse.

L HEURE N EST PAS SUPPOSEE

    entry_ts est en heure SERVEUR du courtier. La contrainte "> 14h
    Paris" demande un decalage qui n a pas ete calibre ici. Par defaut
    --decalage vaut 0 et le filtre porte donc sur l heure SERVEUR : la
    sortie le dit en toutes lettres au lieu de laisser croire a Paris.
"""
import argparse
import io
import json
import os
import sys

CIBLE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
HEURE_MINI = 14


# --- acces defensifs : un champ absent rend None, jamais une exception,
# --- et None fait echouer la regle plutot que de la diluer.
def _ce(t, cle):
    d = t.get("churn_entry")
    return d.get(cle) if isinstance(d, dict) else None


def _hlc(t, tf, cle):
    d = (t.get("hlc_churn_entry") or {}).get(tf)
    return d.get(cle) if isinstance(d, dict) else None


def _rails(t, actif, tf, cle):
    d = ((t.get("rails_entry") or {}).get(actif) or {}).get(tf)
    return d.get(cle) if isinstance(d, dict) else None


def _moi(t, tf, cle):
    """L etat des rails DE L ACTIF TRADE, pas d un autre."""
    return _rails(t, t.get("asset"), tf, cle)


def _epoch(t, tf, cle):
    d = (t.get("epoch_entry") or {}).get(tf)
    return d.get(cle) if isinstance(d, dict) else None


# =====================================================================
# LES DIX REGLES. Gelees le 18/08/2026. Chaque champ cite a ete verifie
# present dans tickets_rails.jsonl le meme jour.
#
# `sens` : "achat", "vente" ou None (les deux). Impose, pas affiche.
# =====================================================================
def r01(t):
    """Ecartement serre, marche lisible. La plus large des dix."""
    return (t.get("rails_setup") == "TIGHT_CROSS"
            and _ce(t, "verdict") in ("OK", "CLEAN"))


def r02(t):
    """Ecartement large et momentum qui s ouvre sur M5."""
    return (t.get("rails_setup") == "WIDE"
            and _hlc(t, "M5", "self_mom") == "WIDENING")


def r03(t):
    """Les trois actifs alignes a la hausse sur M15."""
    return _hlc(t, "M15", "consensus") == "ALIGNED_BULL"


def r04(t):
    """Les trois actifs alignes a la baisse sur M15."""
    return _hlc(t, "M15", "consensus") == "ALIGNED_BEAR"


def r05(t):
    """Desaccord franc entre actifs sur M5, marche lisible."""
    return (_hlc(t, "M5", "consensus") == "SPLIT"
            and _ce(t, "verdict") in ("OK", "CLEAN"))


def r06(t):
    """L actif trade EST le leader sur M5. Test d identite."""
    return _hlc(t, "M5", "leader") == t.get("asset")


def r07(t):
    """L actif trade est le RETARDATAIRE sur M5 -- le pari inverse."""
    return _hlc(t, "M5", "laggard") == t.get("asset")


def r08(t):
    """Rails au-dessus de 50 sur M5 ET M15, RSI hors zone sur M5."""
    return (_moi(t, "M5", "rails_pos") == "BOTH>50"
            and _moi(t, "M15", "rails_pos") == "BOTH>50"
            and _moi(t, "M5", "rsi_pos") == "ABOVE")


def r09(t):
    """Le pendant baissier strict du 240008."""
    return (_moi(t, "M5", "rails_pos") == "BOTH<50"
            and _moi(t, "M15", "rails_pos") == "BOTH<50"
            and _moi(t, "M5", "rsi_pos") == "BELOW")


def r10(t):
    """Convergence M5 en regime lisible. La plus etroite des dix."""
    return (_hlc(t, "M5", "transition") == "CONVERGING"
            and _ce(t, "verdict") in ("OK", "CLEAN"))


REGLES = [
    (240001, "SOCLE SERRE LISIBLE",      None,    r01),
    (240002, "LARGE QUI S OUVRE",        None,    r02),
    (240003, "ACCORD M15 HAUSSIER",      "achat", r03),
    (240004, "ACCORD M15 BAISSIER",      "vente", r04),
    (240005, "DESACCORD M5 LISIBLE",     None,    r05),
    (240006, "JE SUIS LE LEADER M5",     None,    r06),
    (240007, "JE SUIS LE RETARDATAIRE",  None,    r07),
    (240008, "RAILS HAUTS DEUX UNITES",  "achat", r08),
    (240009, "RAILS BAS DEUX UNITES",    "vente", r09),
    (240010, "CONVERGENCE M5 LISIBLE",   None,    r10),
]


def heure(ts):
    """Rend l heure entiere d un 'AAAA-MM-JJ HH:MM:SS', ou None."""
    if not isinstance(ts, str) or len(ts) < 13:
        return None
    try:
        return int(ts[11:13])
    except ValueError:
        return None


def jour(ts):
    return ts[:10] if isinstance(ts, str) and len(ts) >= 10 else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--decalage", type=int, default=0,
                   help="heures a AJOUTER a l heure serveur pour obtenir "
                        "Paris. 0 par defaut = on filtre en heure serveur")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        return 1

    tickets, ko = [], 0
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

    jours = set()
    for t in tickets:
        j = jour(t.get("entry_ts"))
        if j:
            jours.add(j)
    n_jours = max(1, len(jours))

    L = []
    add = L.append
    add("=" * 92)
    add("SERIE 240000 -- DIX REGLES EXECUTABLES, GELEES LE 18/08/2026")
    add("=" * 92)
    add("  %d tickets, %d jours distincts%s"
        % (len(tickets), len(jours), ", %d illisibles" % ko if ko else ""))
    if a.decalage:
        add("  filtre horaire : heure serveur + %d h, seuil %dh"
            % (a.decalage, HEURE_MINI))
    else:
        add("  filtre horaire : heure SERVEUR, seuil %dh. Le decalage vers"
            % HEURE_MINI)
        add("  Paris n a pas ete calibre ici -- ce n est donc PAS 14h Paris.")
    add("")
    add("  CE TABLEAU MESURE LA FREQUENCE, PAS LA PERFORMANCE.")
    add("  La colonne PnL est celle du MOTEUR CHURN sur ces memes tickets.")
    add("  Son entree est la sienne, pas celle de la regle. Elle dit ce qui")
    add("  s est passe quand l etat tenait, jamais ce que la regle aurait")
    add("  fait. Les lire comme un rendement serait refaire l erreur des")
    add("  220000.")
    add("")
    add("  %-7s %-24s %-6s %6s %7s %7s %9s"
        % ("MAGIC", "REGLE", "SENS", "n", "n/jour", "part", "PnL churn"))
    add("  " + "-" * 88)

    for magic, nom, sens, f in REGLES:
        n, pnl, gagnants = 0, 0.0, 0
        for t in tickets:
            h = heure(t.get("entry_ts"))
            if h is None or ((h + a.decalage) % 24) < HEURE_MINI:
                continue
            if sens == "achat" and t.get("dir") != "BUY":
                continue
            if sens == "vente" and t.get("dir") != "SELL":
                continue
            try:
                if not f(t):
                    continue
            except Exception:
                continue
            n += 1
            v = t.get("pnl_eur")
            if isinstance(v, (int, float)):
                pnl += v
                if v > 0:
                    gagnants += 1
        add("  %-7d %-24s %-6s %6d %7.2f %6.1f%% %9.2f"
            % (magic, nom[:24], sens or "deux", n, n / float(n_jours),
               100.0 * n / max(1, len(tickets)),
               pnl / n if n else 0.0))

    add("  " + "-" * 88)
    add("")
    add("  n/jour  frequence sur les jours ou le journal existe. En dessous")
    add("          de 1,0 il faudra des mois pour trancher quoi que ce soit.")
    add("  part    proportion des tickets concernes, apres filtre horaire.")
    add("")
    add("  CE QUI SE DECIDE AVEC CE TABLEAU, ET RIEN D AUTRE : lesquelles")
    add("  des dix sortent assez souvent pour etre jugees en quelques")
    add("  semaines. Une regle trop rare sera ABANDONNEE, pas elargie --")
    add("  l elargir apres avoir vu sa frequence serait choisir la reponse.")
    add("")
    add("  Aucune de ces dix n a encore pris un trade. Le prochain pas est")
    add("  un moteur qui les execute et journalise, avec la balance")
    add("  FICTIVE a 20 000 : papier_tf.py lit aujourd hui le solde REEL")
    add("  et ses lots vont de 0,24 a 0,99, jamais 1,00.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
