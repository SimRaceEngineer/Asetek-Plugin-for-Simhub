# -*- coding: utf-8 -*-
"""
x60_onset.py -- l onset x60 : qui est en position quand ils entrent, et sortent

  python x60_onset.py --loop            observateur, en continu
  python x60_onset.py --rapport         le panneau, depuis ce qui est enregistre
  python x60_onset.py --loop --pas 5

CE QU IL FAIT, ET CE QU IL NE FAIT PAS

    LECTURE SEULE. Aucun ordre, aucune modification de position, aucun
    fichier du moteur. Il lit mt5.positions_get() et il ecrit deux
    fichiers a lui. C est la meme garantie que spx_onset_logger.py, dont
    il reprend le principe : au lieu de photographier au basculement du
    leader M5 sur US500, il photographie AUX EVENEMENTS x60.

LES QUATRE EVENEMENTS

    X60_ENTREE   un x60 vient d ouvrir. On note l instant a la seconde,
                 son prix, et LE PLATEAU : tous les autres magics en
                 position, avec leur P&L latent, leur age, leur MFE et
                 leur MAE a cet instant.

    X60_SORTIE   un x60 vient de fermer. Meme photo, plus son resultat.
                 C est la photo qui porte la question : fallait-il
                 conserver les tierces ou tout fermer avec lui ?

    CLOTURE      n importe quelle position se ferme. Resultat final,
                 MFE et MAE atteints. C est ce qui permet, plus tard, de
                 comparer « garder » a « fermer ».

    SUIVI        toutes les --pas secondes, le pic et le creux de chaque
                 position ouverte. Sans ce suivi, MFE et MAE seraient
                 ceux du courtier a la cloture et pas les notres, donc
                 incomparables entre deux tickets.

    VEILLE       toutes les 10 minutes, une ligne qui dit seulement
                 « je tournais, il y avait n positions ouvertes ».

LES SEANCES, ET POURQUOI LA VEILLE EXISTE

    Les indices cotent 23h/24 chez le courtier. Chaque evenement est
    donc range dans une seance, en heure locale de la machine :

        ASIE    01:00-09:00       EUROPE  09:00-15:30
        US      15:30-22:00       NUIT    22:00-01:00

    Sans les VEILLE, une seance vide serait ambigue : « aucun x60 n a
    trade en Asie » et « l observateur ne tournait pas cette nuit-la »
    produisent exactement le meme fichier. La colonne « observe » du
    rapport compte les VEILLE et tranche. Une seance a 0.0h observe ne
    dit rien du tout, et le rapport l ecrit au lieu de laisser croire a
    un resultat.

    L HORLOGE DE LA MACHINE FAIT FOI. Si elle derive de huit minutes,
    les evenements de 15h28 tombent dans EUROPE au lieu de US. Le
    rapport affiche son heure de generation en tete pour qu on puisse
    la comparer a une horloge de reference.

LA QUESTION CENTRALE, ET COMMENT ELLE SE TRANCHE

    A chaque X60_SORTIE, on connait le P&L latent de chaque position
    tierce. Quand cette position se ferme plus tard, on connait son P&L
    final. La difference dit, pour ce ticket-la :

        final - latent_a_la_sortie_x60

        > 0  garder a rapporte
        < 0  il aurait mieux valu fermer avec le x60

    On somme sur tous les tickets et toutes les sorties. C est un
    contrefactuel HONNETE dans un seul sens : fermer plus tot n aurait
    pas change le marche. L inverse -- « et si on avait garde plus
    longtemps » -- ne se mesure pas ainsi, et le rapport le dit.

LES RATIOS, ET CE QU ILS VALENT

    PnL, RR, PF, MAE, MFE, et un Sharpe PAR TICKET (moyenne sur
    ecart-type des P&L, pas annualise). Le rapport ecrit noir sur blanc
    que ce n est pas le Sharpe d une courbe de capital : avec des
    tickets qui se chevauchent, un Sharpe annualise serait faux, et
    faux dans le sens flatteur.

CE QU IL FAUT POUR QUE CA SERVE

    Il ne voit que ce qui se passe PENDANT qu il tourne. Les x60 sont
    rares -- 177 tickets en 16 seances, soit une dizaine par jour. Il
    faut donc le laisser tourner plusieurs jours avant que le rapport
    dise quoi que ce soit, et il refuse de conclure sous MINI sorties.

FICHIERS

    docs/x60_onset/events.jsonl    tout, une ligne par evenement
    panels/panel_x60_onset.txt     le panneau, rendu par panel_texte
"""
import argparse
import io
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

# Seul --loop a besoin de MetaTrader5. --rapport ne fait que relire un
# fichier : le faire echouer faute de terminal empecherait de depouiller
# les releves ailleurs que sur le VPS -- et empechait de tester ce
# rapport du tout.
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

SETUP = "60"
PAS = 5
MINI = 8              # sorties x60 sous lesquelles on ne conclut pas
VEILLE_MIN = 10       # une preuve de presence toutes les N minutes
DOSSIER = os.path.join(_ICI, "docs", "x60_onset")
EVENTS = os.path.join(DOSSIER, "events.jsonl")
PANNEAU = os.path.join(_ICI, "panels", "panel_x60_onset.txt")
LARG = 100

# Bornes en minutes depuis minuit, heure LOCALE de la machine. Les
# indices cotent 23h/24 : il n y a pas de trou, chaque instant tombe
# dans exactement une seance. NUIT passe minuit, d ou le cas a part.
SEANCES = (("ASIE",    60, 540),      # 01:00 - 09:00
           ("EUROPE", 540, 930),      # 09:00 - 15:30
           ("US",     930, 1320),     # 15:30 - 22:00
           ("NUIT",  1320, 60))       # 22:00 - 01:00


def seance_de(ts):
    """'YYYY-MM-DDTHH:MM:SS' -> nom de seance. Calcule a la lecture, pas
    seulement a l ecriture : les evenements enregistres avant l ajout des
    seances sont donc classes eux aussi, sans retouche du fichier."""
    try:
        t = int(ts[11:13]) * 60 + int(ts[14:16])
    except (ValueError, IndexError, TypeError):
        return "?"
    for nom, debut, fin in SEANCES:
        if debut <= fin:
            if debut <= t < fin:
                return nom
        elif t >= debut or t < fin:
            return nom
    return "?"


def horaire_de(debut, fin):
    return "%02d:%02d-%02d:%02d" % (debut // 60, debut % 60,
                                    fin // 60, fin % 60)


def setup_de(magic):
    d = str(int(magic))
    return d[4:] if len(d) == 6 else None


def est_x60(magic):
    return setup_de(magic) == SETUP


def ecrire(obj):
    # La seance est estampillee ici, en un seul endroit : tout ce qui
    # passe par ecrire() la porte, y compris les evenements ajoutes plus
    # tard sans qu on y pense.
    if "ts" in obj and "seance" not in obj:
        obj["seance"] = seance_de(obj["ts"])
    if not os.path.isdir(DOSSIER):
        os.makedirs(DOSSIER)
    with io.open(EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def maintenant():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def plateau(positions, sauf=None):
    """Qui est en position, et dans quel etat. Le plateau, a l instant t."""
    out = []
    for p in positions:
        if sauf is not None and p.ticket == sauf:
            continue
        out.append({
            "ticket": int(p.ticket), "magic": int(p.magic),
            "actif": str(p.symbol), "sens": "BUY" if p.type == 0 else "SELL",
            "volume": float(p.volume), "latent": round(float(p.profit), 2),
            "ouvert": datetime.fromtimestamp(p.time).strftime("%H:%M:%S"),
            "age_s": int(time.time() - p.time),
            "x60": est_x60(p.magic),
        })
    return sorted(out, key=lambda x: x["ticket"])


# ------------------------------------------------------------ observateur

def boucle(pas):
    if mt5 is None:
        print("KO : MetaTrader5 introuvable dans cet interpreteur.")
        print("     --loop en a besoin ; --rapport, non.")
        return 1
    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        return 1
    print("=" * LARG)
    print(" X60 ONSET -- observateur, lecture seule")
    print("=" * LARG)
    print("setup surveille : %s   pas : %d s" % (SETUP, pas))
    print("evenements : %s" % EVENTS)
    print("seances : " + "   ".join("%s %s" % (n, horaire_de(d, f_))
                                    for n, d, f_ in SEANCES))
    print("il est %s sur cette machine -- c est CETTE horloge qui range"
          % maintenant()[11:])
    print("les evenements par seance.")
    print("Aucun ordre n est envoye. Ctrl+C pour arreter.")
    print()

    connus = {}          # ticket -> {magic, actif, pic, creux, ouvert}
    prochaine_veille = 0.0
    try:
        while True:
            pos = mt5.positions_get()
            if pos is None:
                pos = ()
            vus = set()

            # La preuve de presence. Sans elle, une seance sans x60 et une
            # seance non observee donnent le meme fichier vide.
            if time.time() >= prochaine_veille:
                prochaine_veille = time.time() + VEILLE_MIN * 60
                ecrire({"quoi": "VEILLE", "ts": maintenant(),
                        "ouvertes": len(pos),
                        "x60_ouverts": len([p for p in pos
                                            if est_x60(p.magic)])})

            for p in pos:
                t = int(p.ticket)
                vus.add(t)
                lat = float(p.profit)
                if t not in connus:
                    connus[t] = {"magic": int(p.magic), "actif": str(p.symbol),
                                 "pic": lat, "creux": lat, "dernier": lat,
                                 "ouvert": maintenant(),
                                 "x60": est_x60(p.magic)}
                    if connus[t]["x60"]:
                        ecrire({"quoi": "X60_ENTREE", "ts": maintenant(),
                                "ticket": t, "magic": int(p.magic),
                                "actif": str(p.symbol),
                                "sens": "BUY" if p.type == 0 else "SELL",
                                "volume": float(p.volume),
                                "plateau": plateau(pos, sauf=t)})
                        print("[%s] X60_ENTREE  %d  M%d  %s  (%d autres en"
                              " position)" % (maintenant()[11:], t, p.magic,
                                              p.symbol, len(pos) - 1))
                else:
                    c = connus[t]
                    c["dernier"] = lat        # le resultat, a --pas pres
                    if lat > c["pic"]:
                        c["pic"] = lat
                    if lat < c["creux"]:
                        c["creux"] = lat

            # Ce qui a disparu depuis le tour d avant s est ferme.
            for t in [x for x in connus if x not in vus]:
                c = connus.pop(t)
                # final = DERNIER latent vu, pas le MFE. Le pic n est pas
                # le resultat, et les confondre transformerait chaque
                # perte en gain. L approximation vaut --pas secondes ; le
                # rapport le dit plutot que de le laisser croire exact.
                ecrire({"quoi": "CLOTURE", "ts": maintenant(), "ticket": t,
                        "magic": c["magic"], "actif": c["actif"],
                        "x60": c["x60"], "final": round(c["dernier"], 2),
                        "mfe": round(c["pic"], 2),
                        "mae": round(c["creux"], 2),
                        "ouvert": c["ouvert"]})
                if c["x60"]:
                    ecrire({"quoi": "X60_SORTIE", "ts": maintenant(),
                            "ticket": t, "magic": c["magic"],
                            "actif": c["actif"],
                            "mfe": round(c["pic"], 2),
                            "mae": round(c["creux"], 2),
                            "plateau": plateau(pos)})
                    print("[%s] X60_SORTIE  %d  M%d  MFE %+.2f  MAE %+.2f"
                          "  (%d tierces restent)"
                          % (maintenant()[11:], t, c["magic"], c["pic"],
                             c["creux"], len(pos)))
            time.sleep(pas)
    except KeyboardInterrupt:
        print()
        print("Arret demande.")
    mt5.shutdown()
    return 0


# ---------------------------------------------------------------- rapport

def charger():
    if not os.path.isfile(EVENTS):
        return []
    out = []
    for l in io.open(EVENTS, encoding="utf-8", errors="replace"):
        l = l.strip()
        if not l or l[0] != "{":
            continue
        try:
            out.append(json.loads(l))
        except ValueError:
            continue
    return out


def ratios(v):
    """(n, somme, moyenne, RR, PF, sharpe par ticket)."""
    if not v:
        return 0, 0.0, 0.0, None, None, None
    n = len(v)
    somme = sum(v)
    moy = somme / n
    g = [x for x in v if x > 0]
    p = [x for x in v if x < 0]
    rr = (statistics.mean(g) / abs(statistics.mean(p))) if (g and p) else None
    pf = (sum(g) / abs(sum(p))) if p else None
    sh = None
    if n > 2:
        e = statistics.pstdev(v)
        if e > 0:
            sh = moy / e
    return n, somme, moy, rr, pf, sh


def f(x, n=2):
    return "-" if x is None else ("%.*f" % (n, x))


def rapport():
    ev = charger()
    L = []
    L.append("=" * LARG)
    L.append("  ONSET x%s -- qui est en position quand ils entrent et sortent"
             % SETUP)
    L.append("=" * LARG)
    if not ev:
        L.append("Aucun evenement enregistre. Lance d abord :")
        L.append("    python x60_onset.py --loop")
        L.append("Il ne voit que ce qui se passe PENDANT qu il tourne.")
        return L

    entrees = [e for e in ev if e["quoi"] == "X60_ENTREE"]
    sorties = [e for e in ev if e["quoi"] == "X60_SORTIE"]
    clotures = {e["ticket"]: e for e in ev if e["quoi"] == "CLOTURE"}
    L.append("%d entrees x%s, %d sorties, %d clotures enregistrees"
             % (len(entrees), SETUP, len(sorties), len(clotures)))
    L.append("du %s au %s" % (ev[0]["ts"][:16], ev[-1]["ts"][:16]))
    L.append("rapport genere le %s -- horloge de la machine, celle qui"
             % maintenant())
    L.append("range les evenements par seance. Si elle derive, le classement")
    L.append("derive avec elle : compare-la a une horloge de reference.")
    L.append("")

    # --------------------------------------------- le journal, en clair
    L.append("=" * LARG)
    L.append("  LE JOURNAL -- chaque x%s, de son entree a sa sortie" % SETUP)
    L.append("=" * LARG)
    L.append("%-10s %-9s %-8s %-7s %9s %9s %7s"
             % ("heure", "quoi", "magic", "actif", "MFE", "MAE", "tierces"))
    L.append("-" * LARG)
    for e in ev:
        if e["quoi"] not in ("X60_ENTREE", "X60_SORTIE"):
            continue
        n = len([x for x in e.get("plateau", []) if not x["x60"]])
        L.append("%-10s %-9s M%-7d %-7s %9s %9s %7d"
                 % (e["ts"][11:19], e["quoi"][4:], e["magic"],
                    e["actif"][:7], f(e.get("mfe")), f(e.get("mae")), n))
    L.append("-" * LARG)
    L.append("  'tierces' = magics AUTRES que x%s en position a cet"
             " instant." % SETUP)
    L.append("")

    # ----------------------------------------------------- par seance
    veilles = [e for e in ev if e["quoi"] == "VEILLE"]
    x60_fermes = [c for c in clotures.values()
                  if c.get("x60") and c.get("final") is not None]

    L.append("=" * LARG)
    L.append("  PAR SEANCE -- ou les x%s travaillent, et ce que ca donne"
             % SETUP)
    L.append("=" * LARG)
    obs, ent_s, pnl_s = defaultdict(int), defaultdict(int), defaultdict(list)
    for e in veilles:
        obs[seance_de(e["ts"])] += 1
    for e in entrees:
        ent_s[seance_de(e["ts"])] += 1
    for c in x60_fermes:
        pnl_s[seance_de(c["ts"])].append(c["final"])

    L.append("%-8s %-13s %8s %8s %8s %10s %9s %6s %7s %7s"
             % ("seance", "horaire", "observe", "entrees", "fermes",
                "somme", "moyen", "WR", "PF", "Sharpe"))
    L.append("-" * LARG)
    for nom, debut, fin in SEANCES:
        v = pnl_s.get(nom, [])
        n, somme, moy, _rr, pf, sh = ratios(v)
        wr = (100.0 * len([x for x in v if x > 0]) / n) if n else None
        vu = obs.get(nom, 0) * VEILLE_MIN / 60.0
        L.append("%-8s %-13s %7.1fh %8d %8d %10s %9s %5s%% %7s %7s"
                 % (nom, horaire_de(debut, fin), vu, ent_s.get(nom, 0), n,
                    f(somme), f(moy), f(wr, 0), f(pf), f(sh)))
    L.append("-" * LARG)
    if not veilles:
        L.append("  AUCUNE VEILLE ENREGISTREE -- la colonne 'observe' est a")
        L.append("  zero partout parce que ce fichier a ete produit par une")
        L.append("  version anterieure de l observateur. Les seances restent")
        L.append("  justes ; c est la couverture qui est inconnue. Elle le")
        L.append("  sera des le prochain redemarrage.")
    else:
        L.append("  'observe' = temps pendant lequel l observateur tournait,")
        L.append("  compte a partir d une trace ecrite toutes les %d minutes."
                 % VEILLE_MIN)
        L.append("  UNE SEANCE A 0.0h NE DIT RIEN. Zero entree sur une seance")
        L.append("  jamais observee n est pas un resultat, c est une absence")
        L.append("  de mesure -- et les deux se ressemblent beaucoup trop.")
    L.append("")

    # ------------------------------------------------------ par heure
    L.append("=" * LARG)
    L.append("  PAR HEURE -- horloge de cette machine, pas celle du courtier")
    L.append("=" * LARG)
    oh, eh, ph = defaultdict(int), defaultdict(int), defaultdict(list)
    for e in veilles:
        oh[e["ts"][11:13]] += 1
    for e in entrees:
        eh[e["ts"][11:13]] += 1
    for c in x60_fermes:
        ph[c["ts"][11:13]].append(c["final"])

    if not (oh or eh or ph):
        L.append("  Rien a afficher pour l instant.")
    else:
        ech = max([abs(sum(v)) for v in ph.values()] or [0.0]) or 1.0
        L.append("%-7s %8s %8s %8s %10s %9s   %s"
                 % ("heure", "observe", "entrees", "fermes", "somme",
                    "moyen", "profil"))
        L.append("-" * LARG)
        for h in range(24):
            k = "%02d" % h
            v = ph.get(k, [])
            if not (oh.get(k) or eh.get(k) or v):
                continue
            n, somme, moy, _rr, _pf, _sh = ratios(v)
            # Une heure observee sans cloture n a pas de profil : ni barre,
            # ni signe, ni zero -- trois facons de faire croire a un
            # resultat la ou il n y a rien eu a mesurer.
            if v:
                profil = ("-" if somme < 0 else "+") + "#" * int(
                    round(18.0 * abs(somme) / ech))
                chiffres = "%10s %9s" % (f(somme), f(moy))
            else:
                profil = ""
                chiffres = "%10s %9s" % ("-", "-")
            L.append("%-7s %7.1fh %8d %8d %s   %s"
                     % (k + "h", oh.get(k, 0) * VEILLE_MIN / 60.0,
                        eh.get(k, 0), n, chiffres, profil))
        L.append("-" * LARG)
        L.append("  Une heure absente de ce tableau n a jamais ete observee.")
        L.append("  Les lignes a 0 entree ET plusieurs heures d observation")
        L.append("  sont les vraies : la, on sait qu il ne s est rien passe.")
    L.append("")

    # ------------------------------------------- qui accompagne un x60
    L.append("=" * LARG)
    L.append("  QUI EST LA QUAND UN x%s ENTRE" % SETUP)
    L.append("=" * LARG)
    g = defaultdict(lambda: [0, 0.0])
    for e in entrees:
        for a in e.get("plateau", []):
            if a["x60"]:
                continue
            g[("M%d" % a["magic"])][0] += 1
            g[("M%d" % a["magic"])][1] += a["latent"]
    if not g:
        L.append("  Aucun magic tiers en position lors d une entree x%s."
                 % SETUP)
    else:
        L.append("%-14s %10s %14s %14s"
                 % ("magic", "presences", "latent total", "latent moyen"))
        L.append("-" * LARG)
        for k, (n, s) in sorted(g.items(), key=lambda kv: -kv[1][0]):
            L.append("%-14s %10d %14.2f %14.2f" % (k, n, s, s / n))
        L.append("-" * LARG)
        L.append("  Un magic souvent present ET souvent en perte a l entree")
        L.append("  d un x%s dit quelque chose : le x%s entre quand lui"
                 % (SETUP, SETUP))
        L.append("  souffre. C est une piste, pas une causalite.")
    L.append("")

    # --------------------------------- garder ou fermer avec le x60
    L.append("=" * LARG)
    L.append("  A LA SORTIE D UN x%s : GARDER, OU TOUT FERMER ?" % SETUP)
    L.append("=" * LARG)
    if len(sorties) < MINI:
        L.append("  %d sorties enregistrees, il en faut %d."
                 % (len(sorties), MINI))
        L.append("  Les x%s sont rares -- une dizaine par jour. Laisse"
                 % SETUP)
        L.append("  l observateur tourner plusieurs seances.")
    else:
        gagne, perdu, inconnu = [], [], 0
        for e in sorties:
            for a in e.get("plateau", []):
                if a["x60"]:
                    continue
                c = clotures.get(a["ticket"])
                if not c:
                    inconnu += 1
                    continue
                final = c.get("final")
                if final is None:
                    inconnu += 1
                    continue
                delta = final - a["latent"]
                (gagne if delta > 0 else perdu).append(delta)
        L.append("%-30s %10s %14s %14s"
                 % ("", "tickets", "somme", "moyenne"))
        L.append("-" * LARG)
        n1, s1, m1, _r, _p, _s = ratios(gagne)
        n2, s2, m2, _r, _p, _s = ratios(perdu)
        L.append("%-30s %10d %14.2f %14.2f"
                 % ("garder a rapporte", n1, s1, m1))
        L.append("%-30s %10d %14.2f %14.2f"
                 % ("fermer aurait ete mieux", n2, s2, m2))
        L.append("-" * LARG)
        L.append("  bilan : %+.2f EUR a garder les tierces" % (s1 + s2))
        if inconnu:
            L.append("  %d tickets sans resultat connu (encore ouverts, ou"
                     % inconnu)
            L.append("  fermes avant que l observateur ne tourne) : non")
            L.append("  comptes, ni d un cote ni de l autre.")
        L.append("")
        L.append("  Le resultat d un ticket est son DERNIER latent observe,")
        L.append("  a %d secondes pres -- l observateur ne voit plus la"
                 % PAS)
        L.append("  position une fois fermee. Ce n est pas le P&L du")
        L.append("  courtier : sur un ticket qui bouge vite, l ecart peut")
        L.append("  atteindre quelques euros.")
        L.append("")
        L.append("  CE CONTREFACTUEL N EST HONNETE QUE DANS UN SENS.")
        L.append("  Fermer plus tot n aurait pas change le marche, donc la")
        L.append("  comparaison tient. « Et si on avait garde plus")
        L.append("  longtemps » ne se mesure pas ainsi : la position aurait")
        L.append("  ete fermee par un stop, un reverse ou la fin de seance,")
        L.append("  et rien ici ne le simule.")
    L.append("")

    # ------------------------------------------------------- les ratios
    L.append("=" * LARG)
    L.append("  LES RATIOS DES x%s" % SETUP)
    L.append("=" * LARG)
    v = [c["final"] for t, c in clotures.items()
         if c.get("x60") and c.get("final") is not None]
    n, somme, moy, rr, pf, sh = ratios(v)
    L.append("  tickets ..................... %d" % n)
    L.append("  somme ....................... %s" % f(somme))
    L.append("  moyenne par ticket .......... %s" % f(moy))
    L.append("  RR (gain moyen / perte moy) . %s" % f(rr))
    L.append("  PF (gains / pertes) ......... %s" % f(pf))
    L.append("  Sharpe PAR TICKET ........... %s" % f(sh))
    L.append("")
    L.append("  Le Sharpe ci-dessus est la moyenne des P&L divisee par leur")
    L.append("  ecart-type, PAR TICKET. Ce n est PAS le Sharpe d une courbe")
    L.append("  de capital : les tickets se chevauchent, une annualisation")
    L.append("  serait fausse -- et fausse dans le sens flatteur.")
    return L


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--loop", action="store_true")
    p.add_argument("--rapport", action="store_true")
    p.add_argument("--pas", type=int, default=PAS)
    a = p.parse_args()

    if a.loop:
        return boucle(a.pas)

    L = rapport()
    for l in L:
        print(l)
    d = os.path.dirname(PANNEAU)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(PANNEAU, "w", encoding="utf-8").write(
        "\n".join(["# panel_x60_onset.txt",
                   "# ecrit le %s" % maintenant(),
                   "# via x60_onset.py --rapport", ""] + L) + "\n")
    print()
    print("ecrit : %s" % PANNEAU)
    return 0


if __name__ == "__main__":
    sys.exit(main())
