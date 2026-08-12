# -*- coding: utf-8 -*-
"""
horloge_regime.py -- de telle heure a telle heure, dans quel regime

  python horloge_regime.py --histoire --jour 2026-08-12
  python horloge_regime.py --histoire --depuis 2026-08-05
  python horloge_regime.py --suivi
  python horloge_regime.py --sources

CE QU ON VEUT

    Savoir, en clair et horodate : de 15h28 a 17h20 on etait en churn,
    ca a dure 112 minutes, on y a pris 41 tickets et perdu 1 211 EUR.
    Ensuite v10/v11 pourra decider de ne pas trader la.

CE QU IL N INVENTE PAS

    Aucun score « propice » n est cree ici. L etat se deduit UNIQUEMENT
    du verdict churn que la stack ecrit deja avec chaque trade -- CLEAN,
    MIXED, CHURN, OK -- et de rien d autre. La regle d agregation est
    ecrite en toutes lettres dans la sortie, pour qu on puisse la
    contester sans lire le code.

    Ce qui est ajoute, et qui n est pas un avis : les EUROS REALISES de
    la periode. Un intervalle etiquete CHURN qui gagne de l argent doit
    se voir -- c est le seul moyen de savoir si l etiquette sert.

D OU VIENT L ETAT, ET CE QUE CA COUTE

    Le verdict churn est ecrit PAR TRADE, au moment de l entree, dans
    churn_trades*.jsonl / rails_trades*.jsonl. Il n existe pas, dans ce
    que je peux lire, de flux continu du verdict minute par minute.

    Consequence a garder en tete, elle est reelle :

      1. hors trade, pas de verdict. Une heure sans entree ne dit rien,
         et le fichier ecrit INCONNU -- il ne prolonge pas l etat d avant
         au-dela de --fenetre minutes ;
      2. le trade n apparait qu une fois CLOS. En suivi, l horloge a donc
         le retard de la duree de vie des positions.

    Le point 2 disparaitrait avec une source continue. --sources cherche
    les candidats (*.dat, *churn*, *regime*) et affiche leur age : si
    l un d eux publie un verdict a la minute, on branchera l horloge
    dessus et le reste du script ne changera pas.

L ETAT, PAR PAS DE TEMPS

    A l instant t, pour chaque actif, on regarde les verdicts des
    --fenetre dernieres minutes (15 par defaut) :

        aucun verdict          -> INCONNU pour cet actif
        que des CLEAN et OK    -> PROPRE
        au moins un CHURN      -> part = churn / total, et
                                  part >= 0.60 -> CHURN, sinon MIXTE
        le reste               -> MIXTE

    Puis, entre actifs connus (US30, US500, US100) :

        moins de 2 connus      -> INCONNU
        tous CHURN             -> CARNAGE
        au moins 2/3 CHURN     -> CHURN
        tous PROPRE            -> PROPICE
        sinon                  -> DOUTEUX

    Le seuil de 2 actifs connus vient du 12/08 : sans lui, un seul actif
    faisait l unanimite a lui tout seul et on lisait PROPICE -- un feu
    VERT -- sur la foi d un indice unique, les deux autres muets. Les
    minutes INCONNU restent comptees avec leurs tickets et leurs euros :
    le refus de nommer se mesure au lieu de se cacher.

    La fenetre glissante EST le lissage. On ne lisse pas une deuxieme
    fois et on ne fusionne pas les intervalles courts : un etat qui
    clignote est une information sur la journee, pas un defaut d affichage.

M1 CONTRE M5

    Le verdict churn n est pas decline par pas de temps dans les
    donnees -- il y en a un seul par trade. Ce qui EST decline, c est le
    biais des rails : biais_m1, biais_m5. Les deux colonnes sont donc
    ecrites cote a cote, et on saura laquelle delimite le mieux les
    periodes perdantes. Ce n est pas la meme grandeur que le churn, et
    l appeler « churn M5 » serait faux.

CE QU IL ECRIT

    panels/horloge_regime.txt     les intervalles, lisibles
    panels/horloge_samples.csv    un echantillon par pas, la trace brute

    Dans panels/ : le REPL les lit deja, et les onglets rails savent
    afficher ce format.

LECTURE SEULE. Aucun ordre, aucune position, aucun fichier du moteur.
"""
import argparse
import io
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import oos_v9 as O
except ImportError:
    print("KO : oos_v9.py introuvable a cote de ce script.")
    print("Il porte la normalisation des champs (CLEFS_TS, _churn,")
    print("CHURN_VALIDES...). La recopier ici produirait une deuxieme")
    print("lecture du meme fichier, donc des verdicts incomparables avec")
    print("le gel V9 et avec les panels rails.")
    sys.exit(1)

CLEFS_ACTIF = ["asset", "symbol", "actif", "instrument", "symbole"]
CLEFS_MAGIC = ["magic", "magic_number", "magicnumber", "mg"]

ACTIFS = ["US30", "US500", "US100"]
FENETRE = 15          # minutes de verdicts pris en compte a l instant t
PAS_SUIVI = 30        # secondes entre deux echantillons, en suivi
PART_CHURN = 0.60     # part de CHURN a partir de laquelle un actif est CHURN
# Le quorum est ASYMETRIQUE, et c est le 12/08 qui l a impose. Avec le
# meme seuil des deux cotes, la case INCONNU pesait 34 tickets a -15,84
# EUR -- presque toutes des periodes « US30 en CHURN, les deux autres
# muets ». L information rouge etait la et le seuil la jetait.
#
#   un faux ROUGE coute un trade manque
#   un faux VERT coute un trade dans le hachoir
#
# On ne paie donc pas le meme prix des deux cotes.
MINI_ROUGE = 1        # actifs connus exiges pour nommer un etat rouge
MINI_VERT = 3         # ... et pour PROPICE ou CARNAGE, qui affirment fort
DEST = os.path.join(_ICI, "panels")
LARG = 100

# Candidats pour une source continue, si elle existe un jour.
INDICES = ("churn", "regime", "etat", "state", "verdict")

ORDRE = ["CARNAGE", "CHURN", "DOUTEUX", "PROPICE", "INCONNU"]


# --------------------------------------------------------------- lecture

def _actif(o):
    v = O._prem(o, CLEFS_ACTIF)
    if v is None:
        return ""
    s = str(v).strip().upper()
    # Le meme indice porte deux noms selon le module qui ecrit.
    return {"NAS100": "US100", "SPX500": "US500", "DJ30": "US30",
            "US30.CASH": "US30", "USTEC": "US100"}.get(s, s)


def charger(chemins):
    """Un enregistrement par ticket : ts, actif, churn, biais, magic, pnl.

    Meme normalisation que oos_v9 -- importee, pas recopiee."""
    par, brut = {}, 0
    for ch in chemins:
        try:
            f = io.open(ch, encoding="utf-8-sig")
        except IOError:
            continue
        for l in f:
            l = l.strip()
            if not l or l[0] != "{":
                continue
            brut += 1
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts = str(O._prem(o, O.CLEFS_TS) or "")
            tk = O._prem(o, O.CLEFS_TICKET)
            if len(ts) < 16 or tk is None or tk in par:
                continue
            mg = O._nombre(O._prem(o, CLEFS_MAGIC))
            par[tk] = {
                "ts": ts, "jour": ts[:10], "hm": ts[11:16],
                "ticket": str(tk),
                "pnl": O._nombre(O._prem(o, O.CLEFS_PNL)),
                "actif": _actif(o),
                "churn": O._churn(o),
                "biais_m1": O._etat_tf(o, "M1")[0],
                "biais_m5": O._etat_tf(o, "M5")[0],
                "magic": ("M%d" % int(mg)) if mg else "M?",
            }
    return list(par.values()), brut


def sources_continues():
    """Fichiers susceptibles de publier un verdict en continu.

    On ne les LIT pas -- on les signale, avec leur age. Tant qu aucun ne
    publie une minute, l horloge reste sur les tickets et le dit."""
    vus = []
    for d in (_ICI, os.path.join(_ICI, "docs"), r"C:\ScalpExport",
              os.path.join(_ICI, "panels")):
        if not os.path.isdir(d):
            continue
        try:
            noms = os.listdir(d)
        except OSError:
            continue
        for n in noms:
            b = n.lower()
            if not any(k in b for k in INDICES):
                continue
            if not b.endswith((".dat", ".json", ".txt", ".csv")):
                continue
            p = os.path.join(d, n)
            try:
                vus.append((p, int(time.time() - os.path.getmtime(p)),
                            os.path.getsize(p)))
            except OSError:
                continue
    return sorted(vus, key=lambda x: x[1])


# ------------------------------------------------------------------ etat

def _mn(ts):
    """'2026-08-12T15:28:41' -> minute absolue, pour comparer sans dates."""
    try:
        return (int(ts[11:13]) * 60 + int(ts[14:16]))
    except ValueError:
        return None


def etat_actif(verdicts):
    """PROPRE / MIXTE / CHURN / INCONNU pour un actif, sur la fenetre."""
    v = [x for x in verdicts if x]
    if not v:
        return "INCONNU"
    ch = sum(1 for x in v if x == "CHURN")
    if ch and float(ch) / len(v) >= PART_CHURN:
        return "CHURN"
    if ch:
        return "MIXTE"
    if all(x in ("CLEAN", "OK") for x in v):
        return "PROPRE"
    return "MIXTE"


def etat_global(par_actif):
    """La regle est celle de l en-tete du fichier, et rien d autre.

    Le 12/08 a montre le defaut de la premiere version : avec « tous les
    actifs CONNUS sont CHURN », un seul actif connu faisait l unanimite
    a lui tout seul. On lisait CARNAGE a 08h49 sur le seul US30, et --
    bien plus grave -- PROPICE a 13h58 sur le seul US100, les deux autres
    muets. Un feu vert construit sur un indice unique, exactement la ou
    v10/v11 s en servirait.

    Il faut donc MINI_CONNUS actifs pour nommer un regime global. En
    dessous, INCONNU : on ne sait pas. Et comme les minutes INCONNU sont
    comptees avec leurs tickets et leurs euros dans le tableau suivant,
    ce refus de nommer se mesure au lieu de se cacher."""
    connus = [e for e in par_actif.values() if e != "INCONNU"]
    if len(connus) < MINI_ROUGE:
        return "INCONNU"
    ch = sum(1 for e in connus if e == "CHURN")
    # CARNAGE et PROPICE affirment quelque chose de fort : ils exigent les
    # trois actifs. CHURN se contente de ce qu on sait.
    if len(connus) >= MINI_VERT and ch == len(connus):
        return "CARNAGE"
    if float(ch) / len(connus) >= 2.0 / 3.0:
        return "CHURN"
    if len(connus) >= MINI_VERT and all(e == "PROPRE" for e in connus):
        return "PROPICE"
    return "DOUTEUX"


def echantillons(lot, jour, fenetre, pas_mn=1):
    """[(minute, etat, {actif: etat}, n_verdicts)] sur la journee.

    Une minute sans aucun verdict dans la fenetre sort INCONNU. On ne
    prolonge pas l etat precedent : le silence n est pas un regime."""
    du_jour = [s for s in lot if s["jour"] == jour and _mn(s["ts"]) is not None]
    if not du_jour:
        return []
    par_mn = defaultdict(list)
    for s in du_jour:
        par_mn[_mn(s["ts"])].append(s)
    debut, fin = min(par_mn), max(par_mn)

    out = []
    for m in range(debut, fin + 1, pas_mn):
        fen = []
        for k in range(max(0, m - fenetre + 1), m + 1):
            fen.extend(par_mn.get(k, []))
        pa = {}
        for a in ACTIFS:
            pa[a] = etat_actif([s["churn"] for s in fen if s["actif"] == a])
        out.append((m, etat_global(pa), pa, len(fen)))
    return out


def intervalles(ech):
    """Ecrase les pas consecutifs de meme etat. Rend [(m0, m1, etat, pa)].

    L etat global est constant sur l intervalle -- c est sa definition --
    mais le detail par actif, lui, peut bouger : DOUTEUX tient aussi bien
    avec US500 en CHURN qu avec US500 en MIXTE. On affiche donc l etat
    MAJORITAIRE de chaque actif sur l intervalle, pas celui du dernier
    echantillon, qui ne resumerait qu une minute sur deux cents."""
    out = []
    for m, e, pa, n in ech:
        if out and out[-1][2] == e:
            out[-1][1] = m
        else:
            out.append([m, m, e, defaultdict(lambda: defaultdict(int))])
        for a, v in pa.items():
            out[-1][3][a][v] += 1
    fin = []
    for a, b, e, cpt in out:
        maj = {}
        for act, g in cpt.items():
            k, n = max(g.items(), key=lambda kv: kv[1])
            tot = sum(g.values())
            maj[act] = k if n == tot else "%s~" % k
        fin.append((a, b + 1, e, maj))
    return fin


# ----------------------------------------------------------------- sortie

def hm(m):
    return "%02d:%02d" % (m // 60, m % 60)


def chiffres(lot, jour, m0, m1):
    """Tickets ENTRES dans l intervalle. Un ticket entre a 15h30 et clos
    a 16h10 compte a 15h30 : la question est quand on a pris le risque."""
    d = [s for s in lot if s["jour"] == jour
         and _mn(s["ts"]) is not None and m0 <= _mn(s["ts"]) < m1]
    eur = sum(s["pnl"] for s in d if s["pnl"] is not None)
    return d, eur


def par_magic(d, combien=4):
    """Les magics les plus decoupes, en euros. Nombre de trades ET EUR --
    un magic qui perd peu sur trente trades n est pas le meme probleme
    qu un magic qui perd beaucoup sur trois."""
    g = defaultdict(lambda: [0, 0.0])
    for s in d:
        g[s["magic"]][0] += 1
        if s["pnl"] is not None:
            g[s["magic"]][1] += s["pnl"]
    ordre = sorted(g.items(), key=lambda kv: kv[1][1])
    return [(k, v[0], v[1]) for k, v in ordre[:combien]]


def biais(d, clef):
    """Repartition du biais des rails sur l intervalle, en clair."""
    g = defaultdict(int)
    for s in d:
        g[s[clef] or "?"] += 1
    if not g:
        return "-"
    tot = sum(g.values())
    return " ".join("%s %.0f%%" % (k, 100.0 * v / tot)
                    for k, v in sorted(g.items(), key=lambda kv: -kv[1])[:3])


def par_actif_etat(lot, jour, ech, pas_mn):
    """{(actif, etat de CET actif): [minutes, tickets, EUR]}.

    C est le tableau qui met le verdict a l epreuve, et il ne depend
    d aucune regle d agregation : les tickets d US30 sont comptes sous
    l etat d US30, pas sous l etat global. Si le churn dit quelque chose
    d utile, un actif doit perdre quand il est en CHURN et pas quand il
    est PROPRE. Si les trois lignes se ressemblent, le verdict ne trie
    rien et il faudra le dire."""
    g = defaultdict(lambda: [0, 0, 0.0])
    par_mn = defaultdict(list)
    for s in lot:
        if s["jour"] != jour:
            continue
        m = _mn(s["ts"])
        if m is not None:
            par_mn[m].append(s)
    for m, _e, pa, _n in ech:
        for a in ACTIFS:
            e = pa.get(a, "INCONNU")
            g[(a, e)][0] += pas_mn
            for k in range(m, m + pas_mn):
                for s in par_mn.get(k, []):
                    if s["actif"] != a:
                        continue
                    g[(a, e)][1] += 1
                    if s["pnl"] is not None:
                        g[(a, e)][2] += s["pnl"]
    return g


def ecrire(lignes, chemin):
    d = os.path.dirname(chemin)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(chemin, "w", encoding="utf-8").write("\n".join(lignes) + "\n")


def rendre(lot, jour, fenetre, pas_mn=1):
    """Le texte de l horloge pour une journee."""
    L = []
    ech = echantillons(lot, jour, fenetre, pas_mn)
    if not ech:
        L.append("Aucun verdict churn horodate pour le %s." % jour)
        L.append("Rien a delimiter : ce n est pas une journee propre,")
        L.append("c est une journee sans donnee.")
        return L, []

    ivs = intervalles(ech)
    L.append("=" * LARG)
    L.append("  HORLOGE DE REGIME -- %s" % jour)
    L.append("=" * LARG)
    L.append("fenetre glissante : %d min   pas : %d min   %d echantillons"
             % (fenetre, pas_mn, len(ech)))
    L.append("etat par actif : au moins %.0f%% de CHURN dans la fenetre ->"
             " CHURN" % (100 * PART_CHURN))
    L.append("etat global : %d actif connu suffit pour un etat rouge,"
             % MINI_ROUGE)
    L.append("              %d sont exiges pour CARNAGE et pour PROPICE ;"
             % MINI_VERT)
    L.append("              un faux rouge coute un trade manque, un faux")
    L.append("              vert coute un trade dans le hachoir")
    L.append("un ~ apres l etat d un actif : c est l etat MAJORITAIRE de")
    L.append("l intervalle, pas un etat tenu de bout en bout")
    L.append("")

    L.append("%-13s %6s %-8s %-9s %-9s %-9s %6s %10s"
             % ("plage", "duree", "etat", "US30", "US500", "US100",
                "tickets", "EUR"))
    L.append("-" * LARG)
    total = defaultdict(lambda: [0, 0, 0.0])       # etat -> [min, tk, eur]
    detail = []
    for m0, m1, e, pa in ivs:
        d, eur = chiffres(lot, jour, m0, m1)
        L.append("%-13s %5dm %-8s %-9s %-9s %-9s %6d %+10.2f"
                 % ("%s-%s" % (hm(m0), hm(m1)), m1 - m0, e,
                    pa.get("US30", "-"), pa.get("US500", "-"),
                    pa.get("US100", "-"), len(d), eur))
        total[e][0] += m1 - m0
        total[e][1] += len(d)
        total[e][2] += eur
        detail.append((m0, m1, e, d, eur))
    L.append("-" * LARG)
    L.append("")

    L.append("=" * LARG)
    L.append("  CE QUE CHAQUE ETAT A COUTE OU RAPPORTE")
    L.append("=" * LARG)
    L.append("%-10s %8s %8s %12s %12s"
             % ("etat", "minutes", "tickets", "EUR", "EUR/ticket"))
    L.append("-" * LARG)
    for e in ORDRE:
        if e not in total:
            continue
        mn, tk, eur = total[e]
        L.append("%-10s %8d %8d %+12.2f %12s"
                 % (e, mn, tk, eur,
                    ("%+.2f" % (eur / tk)) if tk else "-"))
    L.append("-" * LARG)
    L.append("  Une seule journee ne prouve rien : c est un releve, pas un")
    L.append("  test. Il faut le meme tableau sur dix seances avant de")
    L.append("  couper quoi que ce soit dans v10 ou v11.")
    L.append("")

    L.append("=" * LARG)
    L.append("  LE VERDICT A L EPREUVE -- chaque actif sous SON propre etat")
    L.append("=" * LARG)
    L.append("%-8s %-9s %8s %8s %12s %12s"
             % ("actif", "etat", "minutes", "tickets", "EUR", "EUR/ticket"))
    L.append("-" * LARG)
    ga = par_actif_etat(lot, jour, ech, pas_mn)
    for a in ACTIFS:
        for e in ("CHURN", "MIXTE", "PROPRE", "INCONNU"):
            if (a, e) not in ga:
                continue
            mn, tk, eur = ga[(a, e)]
            L.append("%-8s %-9s %8d %8d %+12.2f %12s"
                     % (a, e, mn, tk, eur,
                        ("%+.2f" % (eur / tk)) if tk else "-"))
    L.append("-" * LARG)
    L.append("  Aucune regle d agregation ici : les tickets d un actif sont")
    L.append("  comptes sous l etat de CET actif. Si le verdict trie, la")
    L.append("  ligne CHURN doit etre nettement plus mauvaise que la ligne")
    L.append("  PROPRE. Si les deux se ressemblent, le verdict ne trie rien")
    L.append("  et le reste de ce fichier n a pas de fondation.")
    L.append("")

    L.append("=" * LARG)
    L.append("  LES PERIODES QUI ONT COUTE -- qui se fait decouper, et combien")
    L.append("=" * LARG)
    durs = [x for x in detail if x[4] < 0 and len(x[3]) >= 3]
    durs.sort(key=lambda x: x[4])
    if not durs:
        L.append("  Aucune periode perdante d au moins 3 tickets.")
    for m0, m1, e, d, eur in durs[:6]:
        L.append("")
        L.append("  %s-%s  %s  %d min  %d tickets  %+.2f EUR"
                 % (hm(m0), hm(m1), e, m1 - m0, len(d), eur))
        L.append("    biais M1 : %s" % biais(d, "biais_m1"))
        L.append("    biais M5 : %s" % biais(d, "biais_m5"))
        L.append("    %-12s %8s %12s" % ("magic", "trades", "EUR"))
        for mg, n, p in par_magic(d):
            L.append("    %-12s %8d %+12.2f" % (mg, n, p))
    L.append("")
    L.append("  Le nombre de trades compte autant que les euros : un magic")
    L.append("  qui prend trente entrees dans un hachoir se fait decouper")
    L.append("  meme si chaque perte est petite.")
    return L, ech


def csv_echantillons(ech, jour):
    out = ["ts,etat,US30,US500,US100,verdicts_fenetre"]
    for m, e, pa, n in ech:
        out.append("%sT%s,%s,%s,%s,%s,%d"
                   % (jour, hm(m), e, pa.get("US30", ""), pa.get("US500", ""),
                      pa.get("US100", ""), n))
    return out


# ------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--jour")
    p.add_argument("--depuis")
    p.add_argument("--fenetre", type=int, default=FENETRE)
    p.add_argument("--pas", type=int, default=1,
                   help="minutes entre deux echantillons, en histoire")
    p.add_argument("--dest", default=DEST)
    p.add_argument("--histoire", action="store_true")
    p.add_argument("--suivi", action="store_true")
    p.add_argument("--secondes", type=int, default=PAS_SUIVI)
    p.add_argument("--sources", action="store_true")
    a = p.parse_args()

    if a.sources:
        print("Sources continues candidates (non lues, seulement listees) :")
        v = sources_continues()
        if not v:
            print("  aucune. L horloge lit donc les verdicts par trade,")
            print("  et porte le retard de la duree de vie des positions.")
        for chemin, age, taille in v:
            print("  %-58s %6d s  %8d o" % (chemin[-58:], age, taille))
        print()
        print("Si l une d elles publie un verdict a la minute, dis-le :")
        print("l horloge s y branchera sans changer de format de sortie.")
        return 0

    if not (a.histoire or a.suivi):
        print("Choisis --histoire (le corpus) ou --suivi (la boucle).")
        print("--sources liste ce qui pourrait publier un etat en continu.")
        return 1

    chemins = a.fichier or O.sources(None)
    lot, brut = charger(chemins)
    if not lot:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        print("Lance  python oos_v9.py --champs  pour voir leur contenu.")
        return 1

    avec = sum(1 for s in lot if s["churn"])
    act = sum(1 for s in lot if s["actif"])
    print("%d tickets lus, %d avec verdict churn (%.0f%%), %d avec actif"
          " (%.0f%%)" % (len(lot), avec, 100.0 * avec / len(lot),
                         act, 100.0 * act / len(lot)))
    if avec < len(lot) * 0.5:
        print("ATTENTION : moins d un ticket sur deux porte un verdict.")
        print("L horloge sera surtout faite d INCONNU, et un INCONNU n est")
        print("pas un feu vert. Lance  python oos_v9.py --champs.")

    jours = sorted(set(s["jour"] for s in lot))
    if a.jour:
        cibles = [a.jour]
    elif a.depuis:
        cibles = [j for j in jours if j >= a.depuis]
    elif a.suivi:
        cibles = [datetime.now().strftime("%Y-%m-%d")]
    else:
        cibles = jours[-1:]

    if a.histoire:
        L = []
        for j in cibles:
            bloc, ech = rendre(lot, j, a.fenetre, a.pas)
            L.extend(bloc)
            L.append("")
        for l in L:
            print(l)
        txt = os.path.join(a.dest, "horloge_regime.txt")
        ecrire(["# horloge_regime.txt",
                "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "# via horloge_regime.py --histoire", ""] + L, txt)
        print()
        print("ecrit : %s" % txt)
        if len(cibles) == 1:
            _b, ech = rendre(lot, cibles[0], a.fenetre, a.pas)
            csv = os.path.join(a.dest, "horloge_samples.csv")
            ecrire(csv_echantillons(ech, cibles[0]), csv)
            print("ecrit : %s" % csv)
        return 0

    # ------------------------------------------------------------- suivi
    print()
    print("SUIVI -- un echantillon toutes les %d s. Ctrl+C pour arreter."
          % a.secondes)
    print("Les fichiers sont reecrits a chaque tour, dans %s." % a.dest)
    print("Rappel : un trade n apparait qu une fois clos. L horloge a donc")
    print("le retard de la duree de vie des positions -- elle ne le cache")
    print("pas, elle le porte.")
    print()
    n = 0
    try:
        while True:
            n += 1
            t0 = time.time()
            jour = datetime.now().strftime("%Y-%m-%d")
            lot, _b = charger(chemins)
            L, ech = rendre(lot, jour, a.fenetre, 1)
            ecrire(["# horloge_regime.txt",
                    "# ecrit le %s"
                    % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "# via horloge_regime.py --suivi, tour %d" % n, ""] + L,
                   os.path.join(a.dest, "horloge_regime.txt"))
            ecrire(csv_echantillons(ech, jour),
                   os.path.join(a.dest, "horloge_samples.csv"))
            etat = ech[-1][1] if ech else "INCONNU"
            print("[%s] tour %d  etat %-8s  %d echantillons  %.1f s"
                  % (datetime.now().strftime("%H:%M:%S"), n, etat,
                     len(ech), time.time() - t0))
            reste = a.secondes - (time.time() - t0)
            if reste > 0:
                time.sleep(reste)
    except KeyboardInterrupt:
        print()
        print("Arret demande apres %d tour(s)." % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
