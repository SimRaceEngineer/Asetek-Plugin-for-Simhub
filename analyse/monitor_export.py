# -*- coding: utf-8 -*-
"""
monitor_export.py -- rend exploitable le Trade Monitor, qui n a pas d export

  python monitor_export.py --champs monitor.txt     # ce qui a ete reconnu
  python monitor_export.py monitor.txt              # le rapport
  python monitor_export.py monitor.txt --sortie scalp_monitor_20260810-1758.txt

POURQUOI CE SCRIPT EXISTE
    Le Trade Monitor v1.5 affiche, ticket par ticket, quatre choses qu AUCUN
    autre panel ne montre : le nombre d entrees simultanees, le MFE atteint
    avant la sortie, la trajectoire complete du stop, et un score d entree
    sur 10. Il n a pas de bouton "Export .txt". Ce script lit la page telle
    qu on la copie et en fait un export au format de la maison.

    Il ne se branche sur rien. Il ne lit pas MT5, ni le bridge, ni la base.
    Il lit du TEXTE. C est volontaire : les noms de champs internes du
    monitor ne sont pas connus depuis ce depot, et une lecture de texte ne
    peut pas casser la stack en production.

COMMENT PRODUIRE L ENTREE
    Sur le VPS, onglet Live du monitor : Ctrl+A puis Ctrl+C, coller dans
    monitor.txt. C est tout. Deplier "Closed Trades" avant de copier, sinon
    seules les positions actives seront lues -- le script le dit.

CE QU IL MESURE, ET POURQUOI CES QUATRE-LA

  1. LES GRAPPES. "5x BUY simultanes sur US500 en <5min". Si cinq tickets
     partent ensemble sur le meme actif dans le meme sens, ils vivent et
     meurent ensemble : ce n est PAS cinq observations, c est une. Toutes
     les statistiques des panels rails et orderflow comptent en TICKETS.
     Si le facteur de grappe est de 4 ou 5, un N de 1625 vaut un N de 350,
     et tous les p publies jusqu ici sont trop petits d un facteur racine
     de la taille de grappe. C est la mesure la plus importante du script
     et elle ne remet en cause aucun resultat de signe -- seulement leur
     precision affichee.

  2. L EFFICACITE MFE. Le monitor affiche "Cum MFE +8271,68 / Cum MAE
     -8805,94" pour un realise de -3238,65. Autrement dit le dispositif a
     VU passer huit mille euros de gain latent et en a rendu la totalite.
     Aucun filtre d entree ne repare cela : c est une question de sortie.
     Le script compte les tickets "perdants malgre un MFE superieur a 20
     EUR" -- ceux-la etaient gagnants et ne le sont plus.

  3. LA TRAJECTOIRE DU STOP, et une regression precise. Sur plusieurs
     tickets on lit, dans cet ordre : TRAIL a un niveau qui verrouille du
     gain, puis BE qui REMET le stop a l entree, puis TRAIL a nouveau. Le
     passage par BE annule le verrou. Le script detecte ces regressions,
     les compte et chiffre le verrou rendu, en points.

     Il mesure aussi la distance du stop INITIAL a l entree. Sur les
     exemples lus elle va de 200 a 4000 points selon l actif : ce n est pas
     un stop, c est un plafond de securite. Tant que le premier TRAIL n a
     pas eu lieu, le MAE n est borne par rien -- ce qui explique mieux le
     R:R de 0,56 que n importe quelle histoire de setup.

  4. LE SCORE D ENTREE. Il est calcule a chaque ticket, affiche, et n a
     jamais ete confronte au resultat. Le script croise score et P&L. Si la
     relation est plate ou inversee, le score coute du temps de lecture
     pour rien, et il faut le dire.

  Bonus : l appariement 206/207. Les deux familles sont censees differer
  par la politique de sortie (hold contre trail) et jumeaux.py les traite
  comme la SEULE randomisation controlee du dispositif. Le script mesure
  quelle part des paires finit a moins d un euro d ecart -- si c est la
  majorite, l A/B ne teste rien.

CE QUE CE SCRIPT NE FAIT PAS
    Aucun gel, aucune regle, aucune recommandation. Il decrit un panel qui
    n a pas d export. Les gels vivent dans regles_gelees_v*.py et sont
    juges par oos_v*.py, pas ici.

RESERVE DE LECTURE
    Le monitor n affiche pas l heure d entree des tickets clos (la duree
    affichee est 0.0min sur tous). Aucune analyse horaire n est donc
    possible depuis cette source, et le script n en tente aucune. Pour
    l heure, c est le panel rails qui fait foi.
"""
import argparse
import io
import re
import sys
from collections import defaultdict

VERSION = "1.0"

# --------------------------------------------------------------- reconnaissance
# Le separateur entre le numero et le magic est un tiret long. Transcrit en
# ASCII il devient "-" ou "--" selon l outil : on accepte donc n importe
# quelle suite de tirets, y compris aucune.
RE_TETE = re.compile(
    r"#(\d+)\s*[-‐-―]*\s*UNK\(M(\d+)\)\s+(BUY|SELL)\s+(US\d+)\s+@([\d.]+)")
# Le symbole euro n est PAS ecrit en dur : sous Windows PowerShell 5.1 le
# pipe encode en ASCII et le transforme en '?'. On accepte donc n importe
# quel suffixe non blanc apres le nombre -- euro, point d interrogation, ou
# rien du tout. Sans cela le script lirait zero ticket sans dire pourquoi.
EUR = r"[^\s|]*"
RE_PL = re.compile(
    r"P/L:\s*([+-][\d.]+)\s*" + EUR + r"\s*\|\s*MFE:\s*([+-][\d.]+)\s*"
    + EUR + r"\s*\|\s*MAE:\s*([+-][\d.]+)")
RE_PL_ACTIF = re.compile(
    r"([+-][\d.]+)" + EUR + r"\s*\|\s*\d+min\s*\|\s*MFE:\s*([+-][\d.]+)"
    + EUR + r"\s*MAE:\s*([+-][\d.]+)")
RE_SCORE = re.compile(r"(?:Entry \(score|Score:)\s*(\d+)/10")
RE_SIMULT = re.compile(r"(\d+)x\s+(BUY|SELL)\s+(?:simultan\w*\s+)?sur\s+(US\d+)\s+en\s*<\s*5\s*min")
RE_SL = re.compile(r"^\s*(\d{2}:\d{2})\s+([\d.]+)\s+\((INITIAL|BE|TRAIL)\)")
RE_SL_ACTIF = re.compile(r"SL:([\d.]+)\s*(?:→|->)\s*([\d.]+)")


def lire(chemin):
    """Decoupe la page en tickets. Un ticket commence a sa ligne de tete.

    chemin = "-" : on lit l entree standard. C est le mode normal sous
    PowerShell, ou Get-Clipboard suffit a alimenter le script sans passer
    par un fichier intermediaire -- un fichier qu on oublie de creer.
    """
    if chemin == "-":
        txt = sys.stdin.buffer.read().decode("utf-8-sig", "replace")
    else:
        txt = io.open(chemin, encoding="utf-8-sig", errors="replace").read()
    lignes = txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    tickets, cour = [], None
    for l in lignes:
        m = RE_TETE.search(l)
        if m:
            if cour:
                tickets.append(cour)
            cour = {"ticket": m.group(1), "magic": m.group(2),
                    "sens": m.group(3), "asset": m.group(4),
                    "entree": float(m.group(5)),
                    "pnl": None, "mfe": None, "mae": None, "score": None,
                    "simult": 1, "sl": [], "actif": False, "lignes": []}
            # les positions actives portent le score sur la meme ligne
            s = RE_SCORE.search(l)
            if s:
                cour["score"] = int(s.group(1))
                cour["actif"] = True
            continue
        if cour is None:
            continue
        cour["lignes"].append(l)

        m = RE_PL.search(l)
        if m and cour["pnl"] is None:
            cour["pnl"] = float(m.group(1))
            cour["mfe"] = float(m.group(2))
            cour["mae"] = float(m.group(3))
        else:
            m = RE_PL_ACTIF.search(l)
            if m and cour["pnl"] is None:
                cour["pnl"] = float(m.group(1))
                cour["mfe"] = float(m.group(2))
                cour["mae"] = float(m.group(3))
                cour["actif"] = True

        m = RE_SCORE.search(l)
        if m and cour["score"] is None:
            cour["score"] = int(m.group(1))

        m = RE_SIMULT.search(l)
        if m:
            cour["simult"] = max(cour["simult"], int(m.group(1)))

        m = RE_SL.match(l)
        if m:
            cour["sl"].append((m.group(1), float(m.group(2)), m.group(3)))
        else:
            m = RE_SL_ACTIF.search(l)
            if m:
                cour["sl"].append(("--", float(m.group(1)), "INITIAL"))
    if cour:
        tickets.append(cour)
    return [t for t in tickets if t["pnl"] is not None]


# ------------------------------------------------------------------- utilitaires
def fam(magic):
    """Famille de magic : 206 / 207 / 208 / 24xx / autre."""
    for p in ("206", "207", "208"):
        if magic.startswith(p):
            return p
    if magic.startswith("24"):
        return "24xx"
    return "autre"


def bloc(titre, sous=None):
    print()
    print("=" * 78)
    print("  " + titre)
    if sous:
        print("  " + sous)
    print("=" * 78)


def ligne_stats(lab, lot, largeur=26):
    n = len(lot)
    if not n:
        return
    p = sum(t["pnl"] for t in lot)
    g = sum(1 for t in lot if t["pnl"] > 0)
    print("%-*s %5d  %8.2f  %8.2f  %4.0f%%"
          % (largeur, lab[:largeur], n, p, p / n, 100.0 * g / n))


# ------------------------------------------------------------------- 1. grappes
def grappes(ts):
    bloc("1. GRAPPES D ENTREE -- combien d observations INDEPENDANTES ?",
         "le compteur 'Nx simultanes' du monitor, relu comme une taille d essai")
    # Le monitor numerote les entrees D UNE MEME GRAPPE : le premier ticket
    # n a pas de drapeau, le deuxieme porte "2x", le troisieme "3x", etc.
    # Une grappe de taille k produit donc EXACTEMENT un ticket a chaque
    # rang de 1 a k. D ou : le nombre de grappes de taille >= j est le
    # nombre de tickets portant le drapeau j, et le nombre total de grappes
    # est le nombre de tickets SANS drapeau.
    d = defaultdict(int)
    for t in ts:
        d[t["simult"]] += 1
    n = len(ts)
    ngrappes = d.get(1, 0)
    print()
    print("tickets lus                    : %d" % n)
    print("grappes (tickets sans drapeau) : %d" % ngrappes)
    if ngrappes:
        print("taille moyenne de grappe       : %.2f tickets" % (float(n) / ngrappes))
    print()
    print("%-8s %8s  %s" % ("rang", "tickets", "= grappes de cette taille au moins"))
    for k in sorted(d):
        print("%-8s %8d" % ("%dx" % k if k > 1 else "aucun", d[k]))

    # Verification interne : les effectifs par rang doivent decroitre. Si
    # ce n est pas le cas, la page a ete copiee en partie et le nombre de
    # grappes est sous-estime -- donc le facteur de grappe est SUR-estime.
    rangs = [d[k] for k in sorted(d)]
    coherent = all(rangs[i] >= rangs[i + 1] for i in range(len(rangs) - 1))
    if not coherent:
        print()
        print("  /!\\ les effectifs par rang ne decroissent pas. La page a ete")
        print("      copiee en partie : il manque des premiers tickets de grappe.")
        print("      Le facteur ci-dessus est un MAJORANT, pas une mesure.")
        print("      Recopie la page entiere, Closed Trades deplie, et relance.")
    print()
    if not coherent:
        return
    print("CE QUE CELA CHANGE POUR LES AUTRES PANELS")
    if ngrappes and float(n) / ngrappes >= 1.5:
        f = float(n) / ngrappes
        print("  Les tickets d une meme grappe partent au meme prix, dans le meme")
        print("  sens, sur le meme actif, a moins de cinq minutes : ils vivent et")
        print("  meurent ensemble. Le N effectif des panels rails et orderflow est")
        print("  donc environ %.1f fois plus petit que le N affiche." % f)
        print("  Les intervalles et les p publies sont trop etroits d un facteur")
        print("  proche de %.2f. Les SIGNES ne changent pas, la PRECISION si." % (f ** 0.5))
        print("  A verifier avant de conclure quoi que ce soit d un p a 0,04.")
    else:
        print("  Facteur de grappe faible : les N tickets sont a peu pres des N")
        print("  observations. Rien a corriger.")


# ---------------------------------------------------------------------- 2. MFE
def efficacite(ts):
    bloc("2. EFFICACITE MFE -- ce qui a ete vu, ce qui a ete garde",
         "aucun filtre d entree ne repare une sortie ; c est le poste le plus lourd")
    mfe = sum(t["mfe"] for t in ts if t["mfe"] > 0)
    mae = sum(t["mae"] for t in ts if t["mae"] < 0)
    pnl = sum(t["pnl"] for t in ts)
    print()
    print("MFE cumule (gain latent vu)   : %+10.2f" % mfe)
    print("MAE cumule (perte latente vue): %+10.2f" % mae)
    print("P&L realise                   : %+10.2f" % pnl)
    if mfe:
        print("part du MFE conservee         : %+9.1f%%" % (100.0 * pnl / mfe))
    print()
    seuil = 20.0
    perdus = [t for t in ts if t["pnl"] < 0 and t["mfe"] >= seuil]
    print("tickets PERDANTS apres un MFE >= %.0f EUR : %d sur %d (%.0f%%)"
          % (seuil, len(perdus), len(ts), 100.0 * len(perdus) / max(1, len(ts))))
    if perdus:
        print("  MFE cumule laisse sur la table par eux seuls : %+.2f"
              % sum(t["mfe"] for t in perdus))
        print("  P&L de ces memes tickets                     : %+.2f"
              % sum(t["pnl"] for t in perdus))
        pires = sorted(perdus, key=lambda t: t["mfe"] - t["pnl"], reverse=True)[:5]
        print("  les cinq plus gros abandons :")
        for t in pires:
            print("    #%s M%s %-4s %-6s MFE %+7.2f -> P&L %+7.2f"
                  % (t["ticket"], t["magic"], t["sens"], t["asset"], t["mfe"], t["pnl"]))
    print()
    print("%-26s %5s %9s %9s %5s" % ("famille de magic", "N", "PnL", "PnL/tk", "WR"))
    par = defaultdict(list)
    for t in ts:
        par[fam(t["magic"])].append(t)
    for k in sorted(par):
        ligne_stats(k, par[k])
    print()
    print("%-26s %5s %9s %9s %5s" % ("actif", "N", "PnL", "PnL/tk", "WR"))
    par = defaultdict(list)
    for t in ts:
        par[t["asset"]].append(t)
    for k in sorted(par):
        ligne_stats(k, par[k])


# ---------------------------------------------------------------------- 3. stop
def stops(ts):
    bloc("3. TRAJECTOIRE DU STOP -- le BE qui defait le trail",
         "un stop ne doit jamais reculer ; on compte les fois ou il recule")
    avec = [t for t in ts if len(t["sl"]) >= 2]
    print()
    print("tickets avec une trajectoire de stop lisible : %d sur %d"
          % (len(avec), len(ts)))
    if not avec:
        print("Aucune trajectoire lue. Deplie les blocs 'SL:' avant de copier la page.")
        return

    regr, total_rendu = [], 0.0
    for t in avec:
        best = None
        for _, niv, typ in t["sl"]:
            if typ == "INITIAL":
                best = niv
                continue
            if best is None:
                best = niv
                continue
            # BUY : un stop plus haut est meilleur. SELL : plus bas.
            mieux = niv > best if t["sens"] == "BUY" else niv < best
            if mieux:
                best = niv
            else:
                ecart = abs(best - niv)
                if ecart > 0:
                    regr.append((t, typ, ecart))
                    total_rendu += ecart
    print("stops qui RECULENT                          : %d evenements sur %d tickets"
          % (len(regr), len({r[0]["ticket"] for r in regr})))
    if regr:
        d = defaultdict(int)
        for _, typ, _ in regr:
            d[typ] += 1
        print("  par type d evenement : %s"
              % ", ".join("%s=%d" % (k, d[k]) for k in sorted(d)))
        print("  verrou rendu cumule  : %.1f points (toutes paires confondues)"
              % total_rendu)
        print("  les cinq plus gros reculs :")
        for t, typ, e in sorted(regr, key=lambda r: r[2], reverse=True)[:5]:
            print("    #%s M%s %-4s %-6s  %s recule de %.1f points  (P&L %+.2f, MFE %+.2f)"
                  % (t["ticket"], t["magic"], t["sens"], t["asset"], typ, e,
                     t["pnl"], t["mfe"]))
        print()
        print("  LECTURE. Un BE qui arrive APRES un TRAIL deja profitable ramene le")
        print("  stop a l entree et annule le verrou. Ce n est pas une politique de")
        print("  sortie, c est deux politiques qui se marchent dessus. A verifier")
        print("  dans le code de l EA avant toute autre optimisation de sortie.")

    print()
    print("DISTANCE DU STOP INITIAL A L ENTREE, par actif")
    print("%-8s %5s %10s %10s" % ("actif", "N", "mediane", "max"))
    par = defaultdict(list)
    for t in avec:
        ini = [n for _, n, ty in t["sl"] if ty == "INITIAL"]
        if ini:
            par[t["asset"]].append(abs(ini[0] - t["entree"]))
    for k in sorted(par):
        v = sorted(par[k])
        print("%-8s %5d %10.1f %10.1f" % (k, len(v), v[len(v) // 2], v[-1]))
    print()
    print("  Un stop pose a plusieurs centaines ou milliers de points n est pas un")
    print("  stop : tant que le premier TRAIL n a pas eu lieu, le MAE n est borne")
    print("  par rien. Cela explique le rapport gain moyen / perte moyenne bien")
    print("  mieux que n importe quelle histoire de setup d entree.")


# --------------------------------------------------------------------- 4. score
def score(ts):
    bloc("4. LE SCORE D ENTREE -- calcule a chaque ticket, jamais verifie",
         "s il ne separe rien, il coute du temps de lecture pour rien")
    avec = [t for t in ts if t["score"] is not None]
    print()
    print("tickets avec un score : %d sur %d" % (len(avec), len(ts)))
    if len(avec) < 20:
        print("Trop peu pour decrire. On s arrete la.")
        return
    print()
    print("%-26s %5s %9s %9s %5s" % ("score", "N", "PnL", "PnL/tk", "WR"))
    par = defaultdict(list)
    for t in avec:
        par[t["score"]].append(t)
    for k in sorted(par):
        ligne_stats("score %d/10" % k, par[k])
    bas = [t for t in avec if t["score"] <= 3]
    haut = [t for t in avec if t["score"] >= 7]
    print()
    if bas and haut:
        mb = sum(t["pnl"] for t in bas) / len(bas)
        mh = sum(t["pnl"] for t in haut) / len(haut)
        print("scores 0-3 : %+7.2f EUR/ticket sur %d" % (mb, len(bas)))
        print("scores 7-10: %+7.2f EUR/ticket sur %d" % (mh, len(haut)))
        print("ecart haut moins bas : %+.2f" % (mh - mb))
        if mh - mb <= 0:
            print()
            print("  Le score ne separe pas, ou separe a l envers. Tel quel il ne")
            print("  doit servir a aucune decision. Le verifier sur plusieurs")
            print("  journees avant de le retirer de l affichage -- une journee ne")
            print("  suffit pas a condamner un indicateur.")


# ------------------------------------------------------------------- 5. jumeaux
def jumeaux(ts):
    bloc("5. JUMEAUX 206 / 207 -- l A/B teste-t-il encore quelque chose ?",
         "jumeaux.py en fait la SEULE randomisation controlee du dispositif")
    # 206302 et 207302 sont jumeaux : meme suffixe de magic. Ils entrent a
    # la meme seconde mais PAS au meme prix -- l ecart observe va jusqu a
    # un point entier. On apparie donc au plus proche prix a l interieur du
    # groupe, avec une tolerance relative, et non sur une egalite stricte.
    TOL = 0.0005                      # 5 points sur 10 000, soit ~27 pts sur US30
    par = defaultdict(lambda: {"206": [], "207": []})
    for t in ts:
        f = fam(t["magic"])
        if f in ("206", "207"):
            par[(t["magic"][3:], t["asset"], t["sens"])][f].append(t)
    paires, orphelins = [], 0
    for v in par.values():
        libres = list(v["207"])
        for a in v["206"]:
            if not libres:
                orphelins += 1
                continue
            b = min(libres, key=lambda x: abs(x["entree"] - a["entree"]))
            if abs(b["entree"] - a["entree"]) <= TOL * max(1.0, a["entree"]):
                libres.remove(b)
                paires.append((a, b))
            else:
                orphelins += 1
        orphelins += len(libres)
    print()
    print("paires appariees (meme suffixe, actif, sens, prix voisin) : %d" % len(paires))
    print("tickets 206/207 restes sans jumeau                        : %d" % orphelins)
    if not paires:
        print("Aucune paire. Rien a dire.")
        return
    ecarts = sorted(abs(a["pnl"] - b["pnl"]) for a, b in paires)
    ident = sum(1 for e in ecarts if e < 1.0)
    print("paires a moins de 1,00 EUR d ecart : %d (%.0f%%)"
          % (ident, 100.0 * ident / len(paires)))
    print("ecart median                       : %.2f EUR" % ecarts[len(ecarts) // 2])
    print("ecart maximum                      : %.2f EUR" % ecarts[-1])
    print()
    if 100.0 * ident / len(paires) >= 50:
        print("  Plus de la moitie des paires finissent identiques : sur ces")
        print("  tickets-la, hold et trail n ont pas produit deux sorties")
        print("  differentes. L A/B ne mesure alors que le bruit d execution, et")
        print("  le verdict des jumeaux portera sur bien moins de paires que le")
        print("  compte affiche. A verifier avant d en tirer une conclusion.")


# ------------------------------------------------------------------------ champs
def champs(ts):
    print("tickets reconnus : %d" % len(ts))
    for nom, f in (("P&L", lambda t: t["pnl"] is not None),
                   ("MFE", lambda t: t["mfe"] is not None),
                   ("score", lambda t: t["score"] is not None),
                   ("drapeau simultane", lambda t: t["simult"] > 1),
                   ("trajectoire de stop", lambda t: len(t["sl"]) >= 2),
                   ("position active", lambda t: t["actif"])):
        k = sum(1 for t in ts if f(t))
        print("  %-22s %5d  (%3.0f%%)" % (nom, k, 100.0 * k / max(1, len(ts))))
    clos = sum(1 for t in ts if not t["actif"])
    if clos < 20:
        print()
        print("*** MOINS DE 20 TICKETS CLOS ***")
        print("La section 'Closed Trades' n a probablement pas ete depliee avant")
        print("la copie. Deplie-la, recopie la page, relance.")
        return 1
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fichier", nargs="?", default="-",
                   help="la page du monitor dans un .txt, ou '-' pour "
                        "l entree standard (defaut)")
    p.add_argument("--champs", action="store_true",
                   help="diagnostic : ce qui a ete reconnu, puis on s arrete")
    p.add_argument("--sortie", help="ecrire le rapport dans un fichier")
    a = p.parse_args()

    try:
        ts = lire(a.fichier)
    except IOError:
        print("Fichier introuvable : %s" % a.fichier)
        print()
        print("Le plus simple est de ne pas passer par un fichier du tout.")
        print("Sous PowerShell, apres avoir copie la page (Closed Trades")
        print("DEPLIE, puis Ctrl+A / Ctrl+C) :")
        print()
        print("  Get-Clipboard | python monitor_export.py --champs")
        return 1
    if not ts:
        print("Aucun ticket reconnu (source : %s)."
              % ("le presse-papiers" if a.fichier == "-" else a.fichier))
        print("Attendu des lignes de la forme :")
        print("  #171921750 - UNK(M206260) BUY US500 @7781.75")
        print()
        print("Si la page a bien ete copiee, c est que le presse-papiers etait")
        print("vide au moment du pipe. Recopie la page, puis relance.")
        return 1

    if a.champs:
        return champs(ts)

    sortie = None
    if a.sortie:
        sortie = io.open(a.sortie, "w", encoding="utf-8")
        vrai = sys.stdout
        sys.stdout = sortie

    print("=== SCALP-EA / TRADE MONITOR (export reconstruit) ===")
    print("monitor_export.py v%s -- source : %s" % (VERSION, a.fichier))
    print()
    print("PROTOCOLE DE LECTURE -- a respecter par tout agent qui lit ce fichier :")
    print("Ce panel n a pas d export officiel ; ceci est une relecture de la page.")
    print("1. Il DECRIT une journee. Il ne conclut sur rien.")
    print("2. Aucune heure d entree n est disponible pour les tickets clos : toute")
    print("   analyse horaire doit passer par le panel rails, pas par celui-ci.")
    print("3. La section 1 conditionne la lecture de TOUS les autres panels.")
    clos = sum(1 for t in ts if not t["actif"])
    print()
    print("tickets lus : %d, dont %d clos et %d actifs."
          % (len(ts), clos, len(ts) - clos))

    grappes(ts)
    efficacite([t for t in ts if not t["actif"]] or ts)
    stops(ts)
    score([t for t in ts if not t["actif"]] or ts)
    jumeaux([t for t in ts if not t["actif"]] or ts)

    bloc("RESERVES")
    print()
    print("  Une journee. Les cinq sections decrivent le %s tel qu il a ete" % a.fichier)
    print("  copie, rien de plus. Les sections 1 et 3 posent des questions de")
    print("  MECANIQUE -- taille d essai, stop qui recule -- et celles-la se")
    print("  tranchent en relisant le code, pas en accumulant des journees.")
    print("  Les sections 2, 4 et 5 posent des questions de RESULTAT et")
    print("  demandent, elles, plusieurs journees avant qu on en dise un mot.")

    if sortie:
        sys.stdout = vrai
        sortie.close()
        print("Rapport ecrit : %s" % a.sortie)
    return 0


if __name__ == "__main__":
    sys.exit(main())
