# -*- coding: utf-8 -*-
"""
sonde_regles.py -- ou sont les 19 predicats, sous quelle forme, et
                   peut-on les evaluer EN DIRECT ?

LECTEUR SEUL. N ECRIT RIEN, N ENVOIE AUCUN ORDRE.

La premiere sonde cherchait un dictionnaire magic -> fonction. Or
papers_regles expose une LISTE de tuples (magic, nom, sens, fonction).
Celle-ci ne suppose plus la forme : elle regarde tout objet du module
et en extrait les couples (magic, appelable) ou qu ils soient.

Elle repond ensuite a la question qui decide de tout :

    tickets_rails.jsonl est-il ecrit a l ENTREE du trade, ou a sa
    SORTIE ?

    A l entree  -> le miroir peut suivre le fichier et envoyer dans
                   la foulee. Faisable.
    A la sortie -> aucun point d accroche temps reel. Il faudrait
                   toucher au journaliseur churn, ce qui ne se fait
                   pas sans decision explicite.

    La reponse se lit, elle ne se devine pas : on compare les tickets
    presents dans le fichier aux positions actuellement OUVERTES. Si
    une position ouverte y figure deja, la ligne est ecrite a l entree.

Usage :
    python sonde_regles.py
    python sonde_regles.py --fichier docs\rails_trades\tickets_rails.jsonl
"""

import io
import json
import os
import sys

SEP = "=" * 92

MAGICS = [240007, 220014, 230207, 240004, 230201, 240005, 240002,
          230205, 240001, 220004, 230210, 240008, 240003, 240006,
          230106, 230307, 230102, 230202, 230107]
TEMOINS = {220004, 220014}

MODULES = ["papers_regles", "papers_moteur", "papers_decisions",
           "patch_moteur_leaders", "gate_230207"]

CIBLE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")


# ---------------------------------------------------------------------------
# extraction des predicats, sans supposer la forme
# ---------------------------------------------------------------------------
def couples_dans(obj, vus=None, profondeur=0):
    """Tous les (magic, appelable) trouvables dans obj.

    Gere : dict magic->f, liste/tuple de tuples contenant un magic et
    une fonction, listes imbriquees. S arrete a 3 niveaux.
    """
    if profondeur > 3:
        return []
    sortie = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, int) and callable(v):
                sortie.append((k, v))
            else:
                sortie.extend(couples_dans(v, vus, profondeur + 1))
        return sortie
    if isinstance(obj, (list, tuple)):
        magics = [x for x in obj if isinstance(x, int) and x > 100000]
        fonctions = [x for x in obj if callable(x)]
        if len(magics) == 1 and len(fonctions) == 1:
            return [(magics[0], fonctions[0])]
        for e in obj:
            sortie.extend(couples_dans(e, vus, profondeur + 1))
        return sortie
    return sortie


def fouille(nom):
    """(couples, erreur). Importe le module et en extrait les predicats."""
    try:
        mod = __import__(nom)
    except Exception as e:
        return {}, "%s: %s" % (type(e).__name__, e)
    trouves = {}
    detail = []
    for attr in dir(mod):
        if attr.startswith("__"):
            continue
        try:
            obj = getattr(mod, attr)
        except Exception:
            continue
        if callable(obj) and not isinstance(obj, type):
            continue
        couples = couples_dans(obj)
        couples = [(m, f) for m, f in couples if m in MAGICS]
        if couples:
            detail.append((attr, type(obj).__name__, len(couples)))
            for m, f in couples:
                trouves.setdefault(m, (f, nom, attr))
    return (trouves, detail), None


# ---------------------------------------------------------------------------
# lecture du journal des tickets
# ---------------------------------------------------------------------------
def lit_tickets(chemin, combien=None):
    tickets, ko = [], 0
    if not os.path.isfile(chemin):
        return None, 0
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
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
    if combien:
        tickets = tickets[-combien:]
    return tickets, ko


def cles_profondes(o, prefixe="", niveau=0, sortie=None):
    if sortie is None:
        sortie = []
    if niveau > 2 or not isinstance(o, dict):
        return sortie
    for k in sorted(o.keys()):
        v = o[k]
        chemin = prefixe + str(k)
        if isinstance(v, dict):
            sortie.append((chemin, "dict(%d)" % len(v)))
            cles_profondes(v, chemin + ".", niveau + 1, sortie)
        elif isinstance(v, list):
            sortie.append((chemin, "list(%d)" % len(v)))
        else:
            court = repr(v)
            if len(court) > 46:
                court = court[:43] + "..."
            sortie.append((chemin, court))
    return sortie


def cherche_ticket_mt5(t):
    """Les valeurs du record qui ressemblent a un numero de ticket MT5."""
    trouves = {}
    for k, v in t.items():
        if not isinstance(v, (int, str)):
            continue
        nom = str(k).lower()
        if "ticket" in nom or nom in ("deal", "order", "position", "id"):
            trouves[k] = v
    return trouves


# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    chemin = CIBLE
    if "--fichier" in args:
        i = args.index("--fichier")
        if i + 1 < len(args):
            chemin = args[i + 1]

    print(SEP)
    print("SONDE DES REGLES -- LECTURE SEULE")
    print(SEP)
    print()
    print("  Rien n est ecrit, rien n est envoye, rien n est ferme.")
    print()

    # --- 1. ou sont les predicats -----------------------------------------
    print(SEP)
    print("1. OU SONT LES PREDICATS")
    print(SEP)
    table = {}
    for nom in MODULES:
        res, err = fouille(nom)
        print()
        print("  %s" % nom)
        if err:
            print("    import impossible : %s" % err)
            continue
        trouves, detail = res
        if not detail:
            print("    aucun couple (magic, fonction) parmi les 19")
            continue
        for attr, typ, n in detail:
            print("    %-24s %-10s %2d des 19" % (attr, typ, n))
        for m, v in trouves.items():
            table.setdefault(m, v)
    print()

    print(SEP)
    print("2. COUVERTURE DES 19")
    print(SEP)
    print()
    manquants = []
    for m in MAGICS:
        v = table.get(m)
        if v:
            print("    M%-8s %s.%s" % (m, v[1], v[2]))
        else:
            manquants.append(m)
            marque = "  (temoin sans regle)" if m in TEMOINS else ""
            print("    M%-8s INTROUVABLE%s" % (m, marque))
    print()
    print("  trouves : %d / 19" % (19 - len(manquants)))
    if manquants:
        print("  manquants : %s" % ", ".join(str(x) for x in manquants))
    print()

    # --- 3. le journal des tickets ----------------------------------------
    print(SEP)
    print("3. LE JOURNAL DES TICKETS")
    print(SEP)
    print()
    tickets, ko = lit_tickets(chemin)
    if tickets is None:
        print("  %s introuvable." % chemin)
        print("  Sans lui, aucun predicat ne peut s evaluer.")
        return
    print("  fichier : %s" % chemin)
    print("  lignes lisibles : %d   illisibles : %d" % (len(tickets), ko))
    if not tickets:
        return
    jours = sorted(set(t.get("entry_ts", "")[:10] for t in tickets
                       if isinstance(t.get("entry_ts"), str)))
    print("  jours couverts : %d   du %s au %s"
          % (len(jours), jours[0] if jours else "?", jours[-1] if jours else "?"))
    print()

    dernier = tickets[-1]
    print("  DERNIER TICKET -- son schema reel :")
    print()
    for chemin_cle, apercu in cles_profondes(dernier):
        print("    %-46s %s" % (chemin_cle, apercu))
    print()

    ids = cherche_ticket_mt5(dernier)
    print("  champs ressemblant a un numero de ticket MT5 : %s"
          % (ids if ids else "AUCUN"))
    print()

    # --- 4. ecrit a l entree ou a la sortie ? -----------------------------
    print(SEP)
    print("4. ECRIT A L ENTREE, OU A LA SORTIE ?")
    print(SEP)
    print()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("  MetaTrader5 absent : test impossible depuis ce python.")
        mt5 = None
    if mt5 is not None:
        if not mt5.initialize():
            print("  connexion MT5 impossible : %s" % (mt5.last_error(),))
        else:
            try:
                ouvertes = mt5.positions_get() or []
                parents = [p for p in ouvertes if p.magic // 1000 in (206, 207)]
                print("  positions 206xxx/207xxx actuellement ouvertes : %d"
                      % len(parents))
                if not parents:
                    print("  aucune position ouverte : test non concluant,")
                    print("  a relancer pendant une seance.")
                else:
                    connus = set()
                    for t in tickets[-400:]:
                        for v in cherche_ticket_mt5(t).values():
                            try:
                                connus.add(int(v))
                            except (TypeError, ValueError):
                                pass
                    presentes = [p for p in parents if p.ticket in connus]
                    print("  dont deja presentes dans le journal : %d"
                          % len(presentes))
                    print()
                    if presentes:
                        print("  ==> LA LIGNE EST ECRITE A L ENTREE.")
                        print("      Le miroir peut suivre le fichier et")
                        print("      envoyer dans la foulee. Faisable.")
                    else:
                        print("  ==> aucune position ouverte ne figure dans")
                        print("      le journal. Soit la ligne est ecrite a")
                        print("      la SORTIE, soit le numero de ticket n y")
                        print("      est pas stocke sous un nom reconnu.")
                        print("      Le schema ci-dessus tranche : s il ne")
                        print("      porte aucun ticket MT5, c est le second")
                        print("      cas et il faut un autre point d accroche.")
            finally:
                mt5.shutdown()
    print()

    # --- 5. les predicats tournent-ils sur un vrai ticket ? ---------------
    print(SEP)
    print("5. LES PREDICATS TOURNENT-ILS SUR UN VRAI TICKET ?")
    print(SEP)
    print()
    if not table:
        print("  aucun predicat a essayer.")
        return
    echantillon = tickets[-50:]
    for m in MAGICS:
        v = table.get(m)
        if not v:
            continue
        f = v[0]
        vrais = faux = erreurs = 0
        premiere = None
        for t in echantillon:
            try:
                r = f(t)
                if r:
                    vrais += 1
                else:
                    faux += 1
            except Exception as e:
                erreurs += 1
                if premiere is None:
                    premiere = "%s: %s" % (type(e).__name__, e)
        etat = "%3d vrai / %3d faux" % (vrais, faux)
        if erreurs:
            etat += "  %d ERREUR(S)" % erreurs
        print("    M%-8s %s" % (m, etat))
        if premiere:
            print("        %s" % premiere)
    print()
    print("  sur les %d derniers tickets du journal." % len(echantillon))
    print()
    print(SEP)
    print("  Rien n a ete ecrit, rien n a ete envoye.")
    print(SEP)


if __name__ == "__main__":
    main()
