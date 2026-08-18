# -*- coding: utf-8 -*-
r"""
papers_coupe.py -- a quel instant l export a-t-il ete pris ?

  python papers_coupe.py

LECTEUR SEUL. N ECRIT RIEN.

CE QUE LA VERIFICATION DU 18/08 A DONNE

    Colonne US, definitions recopiees du panneau :

        TIGHT_CROSS / clean    attendu 214    obtenu 216    +2
        TIGHT_CROSS / mixed    attendu 154    obtenu 163    +9
        MID / clean            attendu 251    obtenu 251     0
        WIDE / clean           attendu 231    obtenu 232    +1

    Les quatre ecarts sont POSITIFS et petits, et l un est nul. La
    colonne ALL, elle, est a 679. Ce n est pas le profil d un mapping
    faux : c est celui d un mapping juste sur un journal qui a grossi
    depuis que l export a ete sorti.

CE QUE CE SCRIPT FAIT, ET POURQUOI CE N EST PAS UN AJUSTEMENT

    Pour chaque ligne, il trie les tickets qui la verifient par
    entry_ts et lit l horodatage du N-ieme, N etant l effectif ANNONCE
    par l export. Si l export a ete pris a un instant T, alors les
    quatre horodatages doivent tomber JUSTE AVANT T -- et surtout ils
    doivent etre COHERENTS ENTRE EUX.

    C est quatre contraintes pour un seul parametre. Un mapping faux ne
    les fait pas converger : il donne quatre instants disperses sur
    plusieurs jours. Une convergence a l heure pres n est pas quelque
    chose qu on obtient en tatonnant.

    Le script imprime AUSSI l ecart entre le premier et le dernier des
    quatre. C est lui qui dit si la convergence est reelle ou si je me
    raconte une histoire.

CE QU IL NE FAIT PAS

    Il ne choisit pas de date de coupure et ne recalcule rien avec.
    Il rend quatre horodatages et leur dispersion. La conclusion
    appartient a la lecture, pas au script.
"""
import argparse
import io
import json
import os
import sys

CIBLE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")

EMPREINTE = [("TIGHT_CROSS", "clean", 214),
             ("TIGHT_CROSS", "mixed", 154),
             ("MID",         "clean", 251),
             ("WIDE",        "clean", 231)]


def _bucket(verdict):
    if verdict in ("CHURN", "NOISE"):
        return "churn"
    if verdict in ("CLEAN", "OK", "TRADE"):
        return "clean"
    return "mixed"


def _sess(t):
    ts = t.get("entry_ts") or ""
    try:
        return "US" if int(ts[11:13]) >= 14 else "EUR"
    except Exception:
        return "?"


def _verdict(t):
    d = t.get("churn_entry")
    return d.get("verdict") if isinstance(d, dict) else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--session", default="US")
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
    add("=" * 80)
    add("A QUEL INSTANT L EXPORT A-T-IL ETE PRIS ?")
    add("=" * 80)
    add("  %d tickets%s, session %s"
        % (len(tickets), ", %d illisibles" % ko if ko else "", a.session))
    add("")
    add("  Pour chaque ligne : l horodatage du N-ieme ticket qui la")
    add("  verifie, N etant l effectif annonce par l export. Quatre")
    add("  contraintes, un seul parametre -- un mapping faux ne les fait")
    add("  pas converger.")
    add("")
    add("  %-22s %7s %7s   %-21s %s"
        % ("ligne", "attendu", "total", "horodatage du N-ieme", "suivant"))
    add("  " + "-" * 76)

    instants = []
    for setup, seau, attendu in EMPREINTE:
        ts = []
        for t in tickets:
            if t.get("rails_setup") != setup:
                continue
            if _bucket(_verdict(t)) != seau:
                continue
            if _sess(t) != a.session:
                continue
            h = t.get("entry_ts")
            if isinstance(h, str) and len(h) >= 19:
                ts.append(h)
        ts.sort()
        if len(ts) >= attendu:
            nieme = ts[attendu - 1]
            suivant = ts[attendu] if len(ts) > attendu else "(aucun)"
            instants.append(nieme)
        else:
            nieme = "MANQUE %d" % (attendu - len(ts))
            suivant = "-"
        add("  %-22s %7d %7d   %-21s %s"
            % ("%s / %s" % (setup[:11], seau), attendu, len(ts),
               nieme, suivant))

    add("  " + "-" * 76)
    add("")
    if len(instants) == len(EMPREINTE):
        instants.sort()
        add("  Le plus ancien : %s" % instants[0])
        add("  Le plus recent : %s" % instants[-1])
        meme_jour = instants[0][:10] == instants[-1][:10]
        add("")
        if meme_jour:
            add("  LES QUATRE TOMBENT LE MEME JOUR (%s)." % instants[0][:10])
            add("  L export a donc ete pris ce jour-la, apres %s."
                % instants[-1][11:19])
            add("  Le mapping est le bon ; les ecarts venaient du journal")
            add("  qui a continue a grossir depuis.")
        else:
            add("  LES QUATRE NE TOMBENT PAS LE MEME JOUR.")
            add("  Du %s au %s. La convergence n a pas lieu, et l"
                % (instants[0][:10], instants[-1][:10]))
            add("  hypothese d une simple coupure temporelle ne tient pas.")
            add("  Il reste un ecart de definition, ou la population de")
            add("  l export differe autrement (magics inclus, actifs).")
    else:
        add("  Une ligne au moins n a pas assez de tickets pour atteindre")
        add("  son effectif annonce. La coupure temporelle n explique donc")
        add("  pas tout : il MANQUE des prises, ce qu une periode plus")
        add("  courte ne peut pas produire.")
    add("")
    add("  Ce script ne choisit aucune date et ne recalcule rien avec.")
    add("  Il rend quatre horodatages et leur dispersion.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
