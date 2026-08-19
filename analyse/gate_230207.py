# -*- coding: utf-8 -*-
r"""
gate_230207.py -- le filtre US500 SPLIT/CLEAN, isole et verifiable

  python gate_230207.py            verifie contre l historique
  python gate_230207.py --ou       ou brancher : le code qui entre

LECTEUR SEUL. N ENVOIE AUCUN ORDRE, N ECRIT AUCUN FICHIER, NE TOUCHE
AUCUN PROCESSUS. Importer ce module n a aucun effet de bord.

CE QUE CE FICHIER EST

    Une fonction, `decide(etat)`, qui rend (True|False, raison). Rien
    d autre. Elle ne connait ni MetaTrader, ni le journal, ni le
    panneau : on lui donne l etat fige a l entree -- exactement les
    champs que le churn a deja en main au moment de decider -- et elle
    dit oui ou non.

    C est un FILTRE, pas une strategie. Il ne choisit pas l instant
    d entree et n a aucune logique de sortie : le churn entre, le
    churn sort. Le gate ne fait que retirer des entrees.

CE QUI LE JUSTIFIE, AU NIVEAU DECISION ET NON AU NIVEAU PRISE

    230207 sur 4233 prises de journal, une fois les bras 206/207
    regroupes comme le fait _signals :

      70 prises -> 44 decisions (x1,59)
      taux 73 %, borne de Wilson 58 %
      RR observe 1,56 pour un RR exige de 0,72 a cette borne  -> x2,2

    Contre le temoin 220014 -- "long US500 a chaque entree", sans
    aucune regle -- +46,94 par decision contre +16,65 : x2,8.

    Recoupement avec 230201 : 37 %. Ce ne sont pas deux lectures du
    meme echantillon ; la moitie de chacun lui est propre.

CE QUI NE LE JUSTIFIE PAS, ET QUI DOIT RESTER ECRIT

    44 decisions. C est peu. Trois semaines, un seul regime, et une
    periode de hausse du S&P. Le jumeau US30 de la meme regle (230107)
    NE TIENT PAS a la borne : RR 1,22 pour 1,54 exige. Si l edge etait
    structurel et non lie a l actif, il devrait apparaitre des deux
    cotes. Il n apparait que d un.

    Donc : lot minimal, en parallele du papier, et on compare.

CE QUE FAIT --ou

    Il cherche dans le depot le code qui ENVOIE les entrees churn --
    celui qui ecrit churn_trades.jsonl ou qui passe un ordre avec un
    magic 206xxx/207xxx -- et l imprime. Le branchement sera ecrit
    contre ce code-la, lu, et non contre une API supposee.
"""
import argparse
import io
import os
import re
import sys

ACTIF = "US500"
FENETRE = ("14:00", "19:00")     # heure Paris, fin exclue
MAGIC = 230207

_CLEAN = ("CLEAN", "OK", "TRADE")


def _consensus(etat, tf="M15"):
    d = (etat.get("hlc_churn_entry") or {}).get(tf)
    return d.get("consensus") if isinstance(d, dict) else None


def _verdict(etat):
    d = etat.get("churn_entry")
    return d.get("verdict") if isinstance(d, dict) else None


def decide(etat):
    """(accepte, raison). Aucun effet de bord, aucune exception levee.

    Les trois conditions sont celles de 230207 dans papers_moteur :
    cle M15_SPL_CL (consensus M15 = SPLIT, seau clean) et actif impose
    par la numerotation 2xx = US500. La fenetre vient du moteur.
    """
    try:
        if etat.get("asset") != ACTIF:
            return False, "actif %s, attendu %s" % (etat.get("asset"), ACTIF)
        ts = etat.get("entry_ts")
        if isinstance(ts, str) and len(ts) >= 16:
            if not (FENETRE[0] <= ts[11:16] < FENETRE[1]):
                return False, "hors fenetre %s-%s" % FENETRE
        cons = _consensus(etat)
        if cons != "SPLIT":
            return False, "consensus M15 = %s, attendu SPLIT" % cons
        v = _verdict(etat)
        if v not in _CLEAN:
            return False, "verdict churn = %s, attendu clean" % v
        return True, "SPLIT M15 + clean + %s" % ACTIF
    except Exception as e:
        # Un gate qui leve est un gate qui bloque tout. En cas de doute
        # il LAISSE PASSER et le dit : le churn garde son comportement,
        # et l anomalie se voit au lieu de couper le flux en silence.
        return True, "gate en erreur, laisse passer : %s" % e


# ======================================================================
# La verification. Elle ne sert pas au gate : elle sert a prouver que le
# gate est bien le paper, et pas une reecriture approximative.
# ======================================================================
def verifie(add):
    try:
        import papers_moteur as PM
        import papers_population as PP
    except ImportError as e:
        add("  papers_moteur.py et papers_population.py absents (%s)." % e)
        return
    tickets, _k = PP.lire(PP.RAILS)
    journal, _j = PM.lire_jsonl(PM.JOURNAL)
    pris = set(e.get("ticket") for e in journal if e.get("magic") == MAGIC)

    # Le moteur ecarte ce qui n a ni volume ni pnl (trade encore ouvert,
    # ligne incomplete). Comparer sans ce garde-fou ferait ressortir un
    # faux "le gate prend en plus" : ce ne serait pas un desaccord de
    # regle, seulement un ticket que le paper n a pas encore pu compter.
    def comptable(t):
        v, pn = t.get("volume"), t.get("pnl_eur")
        return isinstance(v, (int, float)) and v > 0 \
            and isinstance(pn, (int, float))

    gate = set(t.get("ticket") for t in tickets
               if comptable(t) and decide(t)[0])

    add("=" * 96)
    add("LE GATE EST-IL BIEN LE PAPER ? -- meme selection, ticket par ticket")
    add("=" * 96)
    add("  tickets lus            : %d" % len(tickets))
    add("  pris par le paper %d : %d" % (MAGIC, len(pris)))
    add("  retenus par le gate    : %d" % len(gate))
    trop = gate - pris
    manque = pris - gate
    add("  le gate prend en plus  : %d" % len(trop))
    add("  le gate rate           : %d" % len(manque))
    add("")
    if not trop and not manque:
        add("  IDENTIQUE. Le gate reproduit exactement la selection du")
        add("  paper -- ce n est donc pas une reecriture approximative,")
        add("  c est la meme regle.")
    else:
        add("  DIFFERENT. Tant que cet ecart n est pas explique, le gate")
        add("  ne doit pas etre branche : il ne filtre pas ce qui a ete")
        add("  mesure. Quelques cas :")
        for t in list(trop)[:5]:
            add("    en plus : ticket %s" % t)
        for t in list(manque)[:5]:
            add("    rate    : ticket %s" % t)
        add("")
        add("  Ecart attendu si le journal est en retard sur les tickets :")
        add("  relance papers_moteur.py puis ce script.")
    add("")


def montre_refus(add, combien=6):
    """Quelques entrees recentes, et ce que le gate en aurait fait."""
    try:
        import papers_population as PP
    except ImportError:
        return
    tickets, _k = PP.lire(PP.RAILS)
    us = [t for t in tickets if t.get("asset") == ACTIF][-combien * 4:]
    if not us:
        return
    add("=" * 96)
    add("SUR LES DERNIERES ENTREES %s -- oui ou non, et pourquoi" % ACTIF)
    add("=" * 96)
    for t in us[-combien:]:
        ok, pourquoi = decide(t)
        add("  %-19s %-4s  %s"
            % (t.get("entry_ts"), "OUI" if ok else "non", pourquoi))
    add("")


def ou_brancher(add, racine="."):
    add("=" * 96)
    add("OU BRANCHER -- le code qui ENVOIE les entrees churn")
    add("=" * 96)
    add("  Le branchement sera ecrit contre ce code-la, lu. Pas contre")
    add("  une API supposee.")
    add("")
    mots = ("churn_trades", "order_send", "206", "207")
    forts = ("churn_trades.jsonl", "order_send")
    vus = 0
    for f in sorted(os.listdir(racine)):
        if not f.endswith(".py") or f.startswith(("papers_", "gate_")):
            continue
        try:
            lignes = io.open(os.path.join(racine, f), encoding="utf-8",
                             errors="replace").read().split("\n")
        except Exception:
            continue
        touche = [(i, l) for i, l in enumerate(lignes)
                  if any(m in l for m in forts)]
        if not touche:
            continue
        add("  --- %s  (%d ligne(s))" % (f, len(touche)))
        for i, l in touche[:6]:
            nom = "<module>"
            ind = len(l) - len(l.lstrip())
            for j in range(i, -1, -1):
                m = re.match(r"(\s*)def\s+(\w+)\s*\(", lignes[j])
                if m and len(m.group(1)) < ind:
                    nom = m.group(2)
                    break
            add("    %5d  %-24s %s" % (i + 1, nom[:24], l.strip()[:56]))
        if len(touche) > 6:
            add("    ... %d de plus" % (len(touche) - 6))
        add("")
        vus += 1
        if vus >= 8:
            add("  ... (arrete a 8 fichiers)")
            return
    if not vus:
        add("  Aucun module ne porte churn_trades.jsonl ni order_send.")
        add("  L envoi se fait donc ailleurs -- peut-etre cote MQL.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ou", action="store_true",
                   help="chercher ou brancher le gate")
    a = p.parse_args()
    L = []
    add = L.append
    add("=" * 96)
    add("GATE 230207 -- US500, consensus M15 SPLIT, regime clean")
    add("=" * 96)
    add("")
    add("  Aucun ordre envoye. Aucun fichier ecrit. Aucun processus")
    add("  touche. Ce module ne fait RIEN tant qu il n est pas appele.")
    add("")
    add("  Justification, au niveau DECISION (bras 206/207 regroupes) :")
    add("    44 decisions, taux 73 %, borne de Wilson 58 %")
    add("    RR 1,56 pour 0,72 exige a cette borne          -> x2,2")
    add("    +46,94 par decision contre +16,65 pour le temoin -> x2,8")
    add("")
    add("  Contre-argument, garde en vue :")
    add("    44 decisions, trois semaines, un seul regime. Et le jumeau")
    add("    US30 de la meme regle (230107) NE TIENT PAS : RR 1,22 pour")
    add("    1,54 exige. L edge n apparait que d un cote.")
    add("")
    if a.ou:
        ou_brancher(add)
    else:
        verifie(add)
        montre_refus(add)
        add("  Pour voir ou le brancher :  python gate_230207.py --ou")
        add("")
    add("=" * 96)
    add("  Ce script n a envoye aucun ordre et n a rien ecrit.")
    add("=" * 96)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
