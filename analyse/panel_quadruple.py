# -*- coding: utf-8 -*-
"""
panel_quadruple.py -- les quatre unites x10 / x20 / x30 / x60 cote a
                      cote, sur chaque section

  python panel_quadruple.py
  python panel_quadruple.py --depuis 2026-08-05
  python panel_quadruple.py --sortie panels/panel_quadruple.txt
  python panel_quadruple.py --boucle 5        (service du gardien)

POURQUOI UN PANNEAU SEPARE ET PAS UN PATCH DE x60_onset

    x60_onset est le COLLECTEUR du gel : c est lui qui accumule la
    matiere qu on paie quinze jours pour obtenir. Le patcher pour un
    gain d affichage, c est risquer les donnees pour de la mise en
    page. Ce lecteur ecrit a cote, ne touche a rien, et peut devenir
    un service du gardien pour se rafraichir seul.

CE QU IL LIT -- trois schemas verifies le 14/08, aucun devine

    docs/x60_onset/events.jsonl
        VEILLE       ouvertes, x60_ouverts, seance
        X60_ENTREE   ticket, magic, actif, sens, volume, plateau[]
        X_ENTREE     idem + setup   (x10/x20/x30, depuis 10:35)
        X60_SORTIE   mfe, mae, plateau[]
        X_SORTIE     idem + setup
        CLOTURE      final, mfe, mae, ouvert (ISO COMPLET), seance
        plateau[]    ticket, magic, actif, sens, volume, latent,
                     ouvert (HEURE SEULE), age_s, x60, setup

    docs/rails_trades/tickets_rails.jsonl
        ticket, asset, magic, dir, entry_ts, pnl_eur

LE DEFAUT DE age_s, ET SA REPARATION

    Dans le plateau, `ouvert` ne porte QUE l heure -- pas le jour. Le
    collecteur calcule donc age_s = heure(ts) - heure(ouvert), ce qui
    donne un age NEGATIF pour toute position ouverte la veille.

    Verifie a la seconde : X60_ENTREE du 13/08 a 08:00:17, membre
    ouvert a "11:00:14", age_s = -10796. Or 08:00:17 - 11:00:14 =
    -10797. La position avait en realite 75 603 s, soit 21 heures.

    C est un age faux sur exactement les positions qui comptent : le
    bras 206 tient jusqu au reverse, ses positions vivent souvent d un
    jour sur l autre.

    Ce lecteur le repare sans toucher au collecteur, par deux voies :
      1. le ticket du plateau a sa propre ligne CLOTURE, ou `ouvert`
         est un horodatage COMPLET -> age exact, sans plafond ;
      2. a defaut (position encore ouverte), age_s + 86400 s il est
         negatif -- correct sous 24 h, ambigu au-dela, et signale.

    La colonne `age` du panneau indique par quelle voie chaque chiffre
    a ete obtenu. Un age non reparable est affiche `?`, jamais devine.

LE DOUBLE COMPTAGE DU PLATEAU, ASSUME ET AFFICHE

    Un meme ticket accompagnant apparait dans le plateau de plusieurs
    entrees. La section 4 compte donc des PRESENCES, pas des tickets.
    Le nombre de tickets distincts est affiche a cote : si 300
    presences ne recouvrent que 40 tickets, la moyenne pese 40
    observations et pas 300.

SEUILS

    54 tickets pour une comparaison annoncee d avance, ~172 pour une
    cellule regardee parmi cent (paragraphe 0 de HYPOTHESES.md). Toute
    cellule sous 54 porte un `?`. Une moyenne sans son n est un
    chiffre sans unite.

LECTEUR SEUL. Aucun ordre, aucune ecriture hors de son propre fichier
de sortie.
"""
import argparse
import bisect
import collections
import datetime as dt
import io
import json
import os
import sys
import time

EVENTS = os.path.join("docs", "x60_onset", "events.jsonl")
RAILS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
SORTIE = os.path.join("panels", "panel_quadruple.txt")
QUATRE = ("10", "20", "30", "60")
PETIT = ("01", "02", "03", "05")
FUSION = 30
PORTEE = 120
SEANCES = ("ASIE", "EUROPE", "US", "NUIT")
SEUIL = 54
LARG = 74

_L = []


def dis(s=""):
    _L.append(s)


def setup_de(magic):
    """Le meme decodeur que x60_onset : 6 chiffres = bras, actif,
    unite. Calcule depuis le magic et non lu dans le champ `setup`,
    pour que les lignes ANTERIEURES au patch du 14/08 10:35 soient
    classees comme les autres."""
    try:
        d = str(int(magic))
    except (TypeError, ValueError):
        return None
    return d[4:] if len(d) == 6 else None


def bras_de(magic):
    try:
        d = str(int(magic))
    except (TypeError, ValueError):
        return None
    return d[:3] if len(d) == 6 else None


def horo(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s[:19].replace("T", " "),
                                    "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def bloc(titre, sous=None):
    dis()
    dis("=" * LARG)
    dis(titre)
    if sous:
        for l in sous:
            dis("  " + l)
    dis("=" * LARG)


def cellule(v):
    """Rend '  +12.34/95 ' ou '        -' ou marque '?' sous seuil."""
    n = len(v)
    if not n:
        return "%13s" % "-"
    m = sum(v) / n
    return "%+8.2f/%-4d%s" % (m, n, " " if n >= SEUIL else "?")


def table4(titre, lignes, get):
    """Un tableau a quatre entrees : lignes x colonnes x10/20/30/60."""
    dis()
    dis(titre)
    dis("  %-14s %13s %13s %13s %13s"
        % ("", "x10", "x20", "x30", "x60"))
    dis("  " + "-" * (14 + 4 * 14))
    for nom in lignes:
        dis("  %-14s %s" % (nom, " ".join(cellule(get(nom, s))
                                          for s in QUATRE)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--events", default=EVENTS)
    p.add_argument("--rails", default=RAILS)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--depuis", default=None)
    a = p.parse_args()

    ev = []
    if os.path.isfile(a.events):
        for l in io.open(a.events, encoding="utf-8", errors="replace"):
            if not l.strip():
                continue
            try:
                ev.append(json.loads(l))
            except ValueError:
                continue

    rails = []
    if os.path.isfile(a.rails):
        for l in io.open(a.rails, encoding="utf-8", errors="replace"):
            if not l.strip():
                continue
            try:
                rails.append(json.loads(l))
            except ValueError:
                continue

    def garde(iso):
        return (not a.depuis) or (iso or "")[:10] >= a.depuis

    dis("=" * LARG)
    dis("PANNEAU QUADRUPLE  x10 / x20 / x30 / x60")
    dis("genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if a.depuis:
        dis("restreint aux evenements depuis %s" % a.depuis)
    dis("=" * LARG)
    dis("  %-28s %7d lignes" % (a.events, len(ev)))
    dis("  %-28s %7d lignes" % (a.rails, len(rails)))

    par = collections.Counter(e.get("quoi") for e in ev)
    dis("  types d evenements : "
        + "  ".join("%s:%d" % (k, v) for k, v in sorted(par.items())))
    if not ev:
        dis()
        dis("  AUCUN EVENEMENT -- le collecteur x60_onset ne tourne pas,")
        dis("  ou le chemin est faux. Les sections 1 a 5 seront vides.")

    veilles = [e for e in ev if e.get("quoi") == "VEILLE"
               and garde(e.get("ts"))]
    if veilles:
        dis("  preuves de presence (VEILLE) : %d, soit ~%.1f h observees"
            % (len(veilles), len(veilles) * 10 / 60.0))
        dis("  Une section vide AVEC des VEILLE = rien ne s est produit.")
        dis("  Une section vide SANS VEILLE = on ne regardait pas.")

    # ------------------------------------------------------------------
    # Index des clotures : c est la seule source du resultat final, et
    # la seule ou `ouvert` porte une date complete.
    # ------------------------------------------------------------------
    clot = {}
    for e in ev:
        if e.get("quoi") != "CLOTURE":
            continue
        t = e.get("ticket")
        if t is None:
            continue
        clot[t] = e

    def final_de(ticket):
        c = clot.get(ticket)
        return None if c is None else c.get("final")

    # ------------------------------------------------------------------
    bloc("1. RESULTAT PAR SETUP ET PAR ACTIF",
         ["Source : les lignes CLOTURE. Le setup est recalcule depuis",
          "le magic, donc les clotures anterieures au patch de 10:35",
          "sont classees comme les autres.",
          "Chaque cellule : moyenne/n. `?` = moins de %d tickets."
          % SEUIL])
    g = collections.defaultdict(list)
    actifs = set()
    for e in ev:
        if e.get("quoi") != "CLOTURE" or not garde(e.get("ts")):
            continue
        s = setup_de(e.get("magic"))
        f = e.get("final")
        if s is None or f is None:
            continue
        actifs.add(e.get("actif"))
        g[(e.get("actif"), s)].append(f)
        g[("TOUS", s)].append(f)
        b = bras_de(e.get("magic"))
        if b:
            g[("bras " + b, s)].append(f)
    lignes = ["TOUS"] + sorted(x for x in actifs if x) \
        + sorted("bras " + b for b in ("206", "207")
                 if any(k[0] == "bras " + b for k in g))
    table4("PnL moyen par ticket, en euros", lignes,
           lambda n, s: g.get((n, s), []))

    # ------------------------------------------------------------------
    bloc("2. PAR SEANCE",
         ["La seance est celle inscrite par le collecteur, en heure",
          "locale de la machine. Si l horloge derive, ce decoupage",
          "derive avec elle."])
    gs = collections.defaultdict(list)
    for e in ev:
        if e.get("quoi") != "CLOTURE" or not garde(e.get("ts")):
            continue
        s = setup_de(e.get("magic"))
        f = e.get("final")
        if s is None or f is None:
            continue
        gs[(e.get("seance") or "?", s)].append(f)
    table4("PnL moyen par ticket, par seance", list(SEANCES) + ["?"],
           lambda n, s: gs.get((n, s), []))

    # ------------------------------------------------------------------
    bloc("3. SI ON SORTAIT AVANT",
         ["Ecart entre le meilleur latent atteint (mfe) et le resultat",
          "final, par setup. CE N EST PAS UN GAIN DISPONIBLE : sortir",
          "au pic suppose de connaitre le pic, et aucune regle ne sait",
          "le viser. Ca mesure de combien la sortie actuelle s ecarte",
          "du meilleur moment -- rien de plus.",
          "Rappel H1 : tout TP fixe teste est ressorti NEGATIF."])
    gr = collections.defaultdict(list)
    for e in ev:
        if e.get("quoi") != "CLOTURE" or not garde(e.get("ts")):
            continue
        s = setup_de(e.get("magic"))
        f, m = e.get("final"), e.get("mfe")
        if s is None or f is None or m is None:
            continue
        gr[("rendu", s)].append(m - f)
        gr[("mfe", s)].append(m)
        gr[("mae", s)].append(e.get("mae") or 0.0)
    table4("moyennes, en euros", ["mfe", "mae", "rendu"],
           lambda n, s: gr.get((n, s), []))

    # ------------------------------------------------------------------
    bloc("4. LE PLATEAU -- QUI EST LA QUAND CHACUN ENTRE",
         ["Pour chaque entree, la composition des positions deja",
          "ouvertes, par setup. Ligne = le setup QUI ENTRE, colonne =",
          "le setup DEJA EN POSITION. La valeur est le resultat FINAL",
          "de l accompagnant, retrouve par son ticket dans CLOTURE.",
          "",
          "ATTENTION : ce sont des PRESENCES, pas des tickets. Un meme",
          "accompagnant compte autant de fois qu il est present a une",
          "entree. Le nombre de tickets distincts est donne dessous."])
    gp = collections.defaultdict(list)
    distincts = collections.defaultdict(set)
    n_entrees = collections.Counter()
    for e in ev:
        if e.get("quoi") not in ("X_ENTREE", "X60_ENTREE"):
            continue
        if not garde(e.get("ts")):
            continue
        se = setup_de(e.get("magic"))
        if se is None:
            continue
        n_entrees[se] += 1
        for m in (e.get("plateau") or []):
            sm = setup_de(m.get("magic"))
            f = final_de(m.get("ticket"))
            if sm is None or f is None:
                continue
            gp[(se, sm)].append(f)
            distincts[(se, sm)].add(m.get("ticket"))
    table4("resultat final de l accompagnant, en euros",
           ["entree x%s" % s for s in QUATRE],
           lambda n, s: gp.get((n.split("x")[1], s), []))
    dis()
    dis("  tickets distincts derriere ces presences :")
    dis("  %-14s %13s %13s %13s %13s"
        % ("", "x10", "x20", "x30", "x60"))
    for se in QUATRE:
        dis("  %-14s %s"
            % ("entree x%s" % se,
               " ".join("%13d" % len(distincts.get((se, sm), ()))
                        for sm in QUATRE)))
    dis()
    dis("  nombre d entrees relevees par setup : "
        + "  ".join("x%s:%d" % (s, n_entrees.get(s, 0)) for s in QUATRE))

    # ------------------------------------------------------------------
    bloc("5. L AGE DES ACCOMPAGNANTS",
         ["age_s du collecteur est FAUX pour toute position ouverte la",
          "veille : le champ `ouvert` du plateau ne porte que l heure,",
          "sans le jour, donc la soustraction passe en negatif.",
          "Repare ici par jointure sur CLOTURE (age exact) ou, a",
          "defaut, par +86400 si age_s est negatif (correct sous 24 h).",
          "Les ages non reparables ne sont pas devines : ils sont",
          "comptes a part."])
    ages = collections.defaultdict(list)
    voie = collections.Counter()
    for e in ev:
        if e.get("quoi") not in ("X_ENTREE", "X60_ENTREE"):
            continue
        if not garde(e.get("ts")):
            continue
        t_ev = horo(e.get("ts"))
        for m in (e.get("plateau") or []):
            sm = setup_de(m.get("magic"))
            if sm is None:
                continue
            c = clot.get(m.get("ticket"))
            t_ouv = horo(c.get("ouvert")) if c else None
            if t_ev is not None and t_ouv is not None:
                ages[sm].append((t_ev - t_ouv).total_seconds() / 3600.0)
                voie["exact (CLOTURE)"] += 1
                continue
            v = m.get("age_s")
            if v is None:
                voie["non reparable"] += 1
                continue
            if v < 0:
                v += 86400
                voie["repare +24h"] += 1
            else:
                voie["age_s direct"] += 1
            ages[sm].append(v / 3600.0)
    dis()
    dis("  age median des accompagnants, en heures")
    dis("  %-14s %13s %13s %13s %13s"
        % ("", "x10", "x20", "x30", "x60"))
    dis("  " + "-" * (14 + 4 * 14))
    dis("  %-14s %s"
        % ("age median",
           " ".join(("%13s" % "-") if not ages.get(s)
                    else ("%9.1f h/%-3d" % (sorted(ages[s])[len(ages[s]) // 2],
                                            len(ages[s])))
                    for s in QUATRE)))
    dis()
    for k, v in sorted(voie.items()):
        dis("    %-20s %6d" % (k, v))

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 6 a 9 : ce que tickets_rails apporte et que events.jsonl ne peut
    # pas donner -- il remonte au 21/07 la ou le collecteur x60 ne
    # remonte qu au 12/08.
    # ------------------------------------------------------------------
    tk = []
    for d in rails:
        t = horo(d.get("entry_ts"))
        if t is None or d.get("pnl_eur") is None:
            continue
        tk.append({"t": t, "jour": (d.get("entry_ts") or "")[:10],
                   "actif": d.get("asset"),
                   "setup": setup_de(d.get("magic")),
                   "pnl": d.get("pnl_eur"),
                   "h": (d.get("entry_ts") or "")[11:16]})
    tk.sort(key=lambda k: k["t"])
    tk = [k for k in tk if garde(k["jour"])]

    # Episodes : un allumage de grand timeframe en ouvre un ; un second
    # a moins de FUSION minutes le prolonge au lieu d en rouvrir un.
    allum = collections.defaultdict(list)
    for k in tk:
        if k["setup"] in QUATRE:
            allum[k["actif"]].append(k["t"])
    for act in allum:
        allum[act].sort()
    eps = collections.defaultdict(list)
    for act, ar in allum.items():
        cur = None
        for t in ar:
            if cur and (t - cur["fin"]).total_seconds() <= FUSION * 60:
                cur["fin"] = t
                cur["n"] += 1
                continue
            cur = {"debut": t, "fin": t, "n": 1, "petits": []}
            eps[act].append(cur)
    debuts = dict((a2, [e["debut"] for e in v]) for a2, v in eps.items())
    for k in tk:
        if k["setup"] not in PETIT:
            continue
        v = eps.get(k["actif"])
        if not v:
            continue
        i = bisect.bisect_right(debuts[k["actif"]], k["t"]) - 1
        if i < 0:
            continue
        e = v[i]
        if (k["t"] - e["fin"]).total_seconds() > PORTEE * 60:
            continue
        k["rang"] = len(e["petits"]) + 1
        k["ep"] = e
        e["petits"].append(k)
    for act in eps:
        for e in eps[act]:
            for k in e["petits"]:
                k["taille"] = len(e["petits"])

    bloc("6. LES EPISODES  (source tickets_rails, depuis le 21/07)",
         ["Un allumage de grand timeframe ouvre un episode ; un second",
          "a moins de %d min le prolonge au lieu d en rouvrir un." % FUSION,
          "L episode se ferme %d min apres son dernier allumage." % PORTEE,
          "Ces deux durees sont des CHOIX, pas des mesures."])
    tot_ep = sum(len(v) for v in eps.values())
    dis()
    dis("  allumages par actif et par setup")
    dis("  %-14s %13s %13s %13s %13s"
        % ("", "x10", "x20", "x30", "x60"))
    dis("  " + "-" * (14 + 4 * 14))
    for act in sorted(eps):
        cpt = collections.Counter(k["setup"] for k in tk
                                  if k["actif"] == act and k["setup"] in QUATRE)
        dis("  %-14s %s"
            % (act, " ".join("%13d" % cpt.get(x, 0) for x in QUATRE)))
    rat = [k for act in eps for e in eps[act] for k in e["petits"]]
    dis()
    dis("  %d episodes, %d petits rattaches, %d hors episode"
        % (tot_ep, len(rat),
           len([k for k in tk if k["setup"] in PETIT and "ep" not in k])))

    bloc("7. LE PETIT SOUS COUVERTURE  (H10)",
         ["Ligne = le petit setup qui entre. Colonne = le grand qui a",
          "ouvert l episode. Mesure du 14/08 : porteur M10-M30",
          "+13,89 EUR/tk contre -15,09 sous porteur H1, t ~ 4,1 --",
          "mais sur une seance et demie d allumages x10/x20/x30.",
          "C est cette ligne-la que le gel doit remplir."])
    gpo = collections.defaultdict(list)
    for act in eps:
        for e in eps[act]:
            # Le setup du PREMIER allumage de l episode : c est lui qui
            # a ouvert, les suivants n ont fait que le prolonger.
            prem = None
            for k in tk:
                if k["actif"] == act and k["setup"] in QUATRE \
                        and k["t"] == e["debut"]:
                    prem = k["setup"]
                    break
            if prem is None:
                continue
            for k in e["petits"]:
                gpo[(k["setup"], prem)].append(k["pnl"])
    table4("PnL moyen du petit, selon le grand qui a ouvert",
           ["x%s entre" % x for x in PETIT],
           lambda nm, x: gpo.get((nm.split(" ")[0][1:], x), []))

    bloc("8. LA RICHESSE DE L EPISODE  (H14)",
         ["Le seul resultat de la journee dont l effectif tienne a",
          "l unite qui compte -- l EPISODE, pas le ticket.",
          "Un bon depart est avare : il declenche trois ou quatre",
          "entrees puis laisse courir. Un moteur qui ne cesse plus de",
          "tirer signale l absence de depart, pas sa force.",
          "ATTENTION : la taille finale n est PAS connue au moment",
          "d entrer. Ce tableau explique, il ne se joue pas."])
    dis()
    for lib, f in (("1-4 entrees", lambda t: t <= 4),
                   ("5-9 entrees", lambda t: 5 <= t <= 9),
                   ("10+ entrees", lambda t: t >= 10)):
        v = [k["pnl"] for k in rat if f(k.get("taille", 0))]
        n2 = len(v)
        if not n2:
            dis("  %-16s        -" % lib)
            continue
        dis("  %-16s n=%-5d moy %+8.2f  total %+10.2f%s"
            % (lib, n2, sum(v) / n2, sum(v), "" if n2 >= SEUIL else "  ?"))
    dis()
    for lib, f in (("rangs 1-4", lambda r: r <= 4),
                   ("rangs 5+", lambda r: r >= 5)):
        v = [k["pnl"] for k in rat if f(k.get("rang", 0))]
        n2 = len(v)
        if not n2:
            continue
        dis("  %-16s n=%-5d moy %+8.2f  total %+10.2f%s"
            % (lib, n2, sum(v) / n2, sum(v), "" if n2 >= SEUIL else "  ?"))

    bloc("9. SEANCE US  (H9)",
         ["Le seul edge demontrable du dossier au 14/08. Mesure sur",
          "3 560 tickets : -5,48 EUR/tk hors seance contre +9,80 en",
          "seance. Moyenne elaguee a 1 % : -5,71, soit PIRE que la",
          "brute -- ce n est donc pas une queue. Negatif 11 jours",
          "sur 14. Le decoupage se fait sur l heure d entree seule,",
          "sans classifieur."])
    gse = collections.defaultdict(list)
    for k in tk:
        if k["setup"] is None:
            continue
        camp = "en seance" if "15:30" <= k["h"] < "19:30" else "hors seance"
        gse[(camp, k["setup"])].append(k["pnl"])
        gse[(camp, "TOUS")].append(k["pnl"])
    table4("PnL moyen par ticket, les quatre grands",
           ["en seance", "hors seance"],
           lambda nm, x: gse.get((nm, x), []))
    dis()
    for camp in ("en seance", "hors seance"):
        v = gse.get((camp, "TOUS"), [])
        if v:
            dis("  %-16s tous setups confondus : n=%-5d moy %+8.2f"
                % (camp, len(v), sum(v) / len(v)))

    bloc("10. RAPPELS DE LECTURE",
         ["Ce panneau DECRIT. Il ne conclut pas.",
          "",
          "`?` = moins de %d tickets : une comparaison annoncee" % SEUIL,
          "d avance en demande ~%d, une cellule regardee parmi cent"
          % SEUIL,
          "en demande ~172 (paragraphe 0 de HYPOTHESES.md).",
          "",
          "Section 4 : des PRESENCES, pas des tickets. Regarder la",
          "ligne des tickets distincts avant de croire un n.",
          "",
          "Section 5 : un age negatif au depart signifie une position",
          "de la veille, pas une anomalie de marche.",
          "",
          "Au 14/08, deux resultats seulement tiennent sur l ensemble",
          "du dossier : ne pas trader hors seance US, et ne pas trader",
          "un episode qui s emballe. Tout le reste est descriptif."])

    txt = "\n".join(_L) + "\n"
    sys.stdout.write(txt)
    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write(txt)
    sys.stderr.write("\necrit : %s (%d octets)\n"
                     % (a.sortie, len(txt.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    # --boucle est retire d argv AVANT argparse : le mode boucle est
    # une affaire de lancement, pas de rapport, et le reste du script
    # n a pas a le connaitre. Le gardien peut ainsi le traiter comme
    # les autres services -- un processus qui reste en vie -- au lieu
    # de le relancer a chaque passe et d inonder son journal.
    _argv = sys.argv[1:]
    _min = 0
    if "--boucle" in _argv:
        _i = _argv.index("--boucle")
        try:
            _min = int(_argv[_i + 1])
        except (IndexError, ValueError):
            sys.stderr.write("KO : --boucle attend un nombre de minutes\n")
            sys.exit(1)
        del _argv[_i:_i + 2]
        sys.argv = [sys.argv[0]] + _argv
    if _min > 0:
        while True:
            del _L[:]
            try:
                main()
            except Exception as e:
                # Un rapport qui echoue ne doit pas tuer la boucle :
                # le gardien relancerait, l erreur se reproduirait, et
                # on aurait un cycle au lieu d un message.
                sys.stderr.write("passe en echec : %s\n" % e)
            time.sleep(_min * 60)
    sys.exit(main())
