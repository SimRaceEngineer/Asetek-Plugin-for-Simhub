# -*- coding: utf-8 -*-
r"""
autopsie_choc.py -- disseque une bougie de choc, en fait une signature,
puis balaie l historique a sa recherche

  python autopsie_choc.py
  python autopsie_choc.py --instant "2026-08-12 14:30"
  python autopsie_choc.py --fenetre 15 --apres 15,30,60

LA DEMANDE, LE 17/08

    "La bougie a d ailleurs fini rouge pour US30 et verte pour
    500/100, c est peut-etre une coincidence, mais l etude de ces
    bougies CPI du 12 aout a 14h30 sur tous les elements que l on peut
    tracer pourrait nous aider a definir, et ensuite a faire un reverse
    sur historique histoire de voir si on trouve d autres elements
    proches."

    C est la bonne facon de proceder et l ordre est le bon : d abord
    regarder UN evenement en detail, en tirer une definition, puis
    chercher cette definition ailleurs. Ce fichier fait les trois, dans
    cet ordre, et refuse de faire des statistiques quand il n a pas de
    quoi.

CE QUI FAIT LA DIFFERENCE ICI : LE SIGNE

    L observation n est pas "ca a bouge fort". C est "l US30 a fini
    ROUGE pendant que le 500 et le 100 finissaient VERTS, au meme
    instant". Une difference d amplitude peut venir de la volatilite ou
    de la cotation ; une difference de SIGNE, non. Deux actifs qui
    partent en sens contraire sur la meme minute, c est un arbitrage
    entre eux, pas du bruit.

    La signature retenue est donc a DEUX conditions, toutes deux lues
    dans les donnees, aucune constante inventee :

      1. AMPLITUDE : sur une fenetre de F minutes, les trois actifs
         bougent plus de S fois leur amplitude mediane sur F minutes ;
      2. DIVERGENCE : le signe du mouvement de l US30 est oppose a
         celui de l US100.

L HEURE FOURNIE N EST PAS CRUE SUR PAROLE

    Les graphiques TradingView sont a l heure du serveur, les cycles a
    l heure du VPS. Un decalage d une ou deux heures ferait disséquer
    une bougie calme en croyant tenir la bonne. Le script cherche donc,
    dans une plage de +/- R minutes autour de l instant fourni, la
    fenetre ou les TROIS actifs bougent le plus ensemble, et affiche
    l ecart entre l heure demandee et l heure trouvee. Si l ecart est
    grand, c est affiche en clair : ce n est pas un detail, c est peut-
    etre un fuseau.

CE QUE L AUTOPSIE MONTRE

    Pas 66 colonnes sur 720 cycles -- illisible. Deux choses :

      - la trajectoire des trois prix, en %% depuis l ancre, echantillonnee ;
      - le JOURNAL DES CHANGEMENTS : chaque fois qu une colonne d etat
        de la stack change de valeur (etat Bollinger, canal fractal,
        structure cassee, label d evenement, side du piege de fausse
        cassure, statut de l initial balance, biais, et a la racine
        alignment / leader / weakest). C est ce que la stack a VU
        changer, et quand. C est ca, l autopsie : pas ce que je pense
        qu il s est passe, ce que le moteur a enregistre.

LE REVERSE, ET SON TEMOIN

    On balaie toutes les journees a la recherche de la signature, avec
    une periode refractaire d une fenetre pour ne pas compter dix fois
    le meme evenement.

    Et surtout : un TEMOIN APPARIE. Les fenetres ou les trois actifs
    bougent tout aussi fort mais DANS LE MEME SENS. Sans lui, on
    mesurerait "ce qui se passe apres un gros mouvement" et on
    l appellerait "ce qui se passe apres une divergence". La difference
    entre les deux colonnes est le seul chiffre qui reponde a la
    question posee.

CE QUE CE SCRIPT REFUSE DE FAIRE

    En dessous de --mini evenements, il imprime la liste et s arrete
    la. Une moyenne sur deux lignes n est pas une statistique, et un
    tableau bien mis en page donne l illusion du contraire. Avec 18
    journees, ce cas est le plus probable -- et alors la reponse est
    "il faut plus d historique", pas un p-value.

LECTEUR SEUL : lit les CSV de cartes\cycles\, liste des fichiers
d archive sans les modifier, ecrit un .txt. Ne touche a aucun
processus.
"""
import argparse
import csv
import io
import json
import os
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "cycles")
ARCHIVES = os.path.join("docs", "buddha")
SORTIE = os.path.join("cartes", "panel_autopsie.txt")
VALUE = "US30"
LARGE = "US500"
TECH = "US100"
ACTIFS = (VALUE, LARGE, TECH)
LARG = 100

# Colonnes d etat par actif : ce sont des ETIQUETTES, donc un
# changement de valeur est un evenement. Les colonnes numeriques ne
# sont pas dans ce journal -- elles changent a chaque cycle.
ETATS = ("bb_etat", "fr_canal", "fr_fb", "fr_ev", "piege_side",
         "ib_etat", "biais")
ETATS_RACINE = ("alignment", "leader", "weakest")

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def horo(s):
    try:
        return dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def charge(dossier):
    jours = {}
    if not os.path.isdir(dossier):
        return jours
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("cycles_") or not nom.endswith(".csv"):
            continue
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            L = [r for r in csv.DictReader(f, delimiter=";")]
        if L:
            jours[nom[7:-4]] = L
    return jours


def pas_median(jours):
    p = []
    for L in jours.values():
        for k in range(1, min(len(L), 300)):
            t0, t1 = horo(L[k - 1].get("ts")), horo(L[k].get("ts"))
            if t0 is None or t1 is None:
                continue
            d = (t1 - t0).total_seconds()
            if 0 < d < 600:
                p.append(d)
    p.sort()
    return p[len(p) // 2] if p else 10.0


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    return v[len(v) // 2]


def moyenne(v):
    return sum(v) / len(v) if v else None


def series(L):
    return dict((x, [flt(r.get("%s_bid" % x)) for r in L]) for x in ACTIFS)


def bouge(px, i, k):
    """Mouvement en %% entre le cycle i et le cycle i+k."""
    if i < 0 or i + k >= len(px):
        return None
    a, b = px[i], px[i + k]
    if a is None or b is None or a <= 0:
        return None
    return (b - a) / a * 100.0


def amplitudes(px, k):
    """Le mouvement signe sur chaque fenetre glissante de k cycles."""
    return [bouge(px, i, k) for i in range(len(px))]


# ----------------------------------------------------------------------
# 1. AUTOPSIE
# ----------------------------------------------------------------------

def trouve_ancre(L, sx, k, cible, rayon_cycles, med):
    """La fenetre ou les TROIS actifs bougent le plus ensemble, dans un
    rayon autour de l instant demande.

    Le score conjoint est le MINIMUM des trois amplitudes normalisees :
    il ne monte que si les trois bougent. Un maximum ou une moyenne
    serait pilote par le seul actif le plus agite, et on disséquerait un
    spike propre a un actif en croyant tenir une macro."""
    ts = [horo(r.get("ts")) for r in L]
    best = None
    for i in range(len(L) - k):
        if ts[i] is None:
            continue
        if cible is not None:
            if abs((ts[i] - cible).total_seconds()) > rayon_cycles:
                continue
        vals = []
        for x in ACTIFS:
            m = bouge(sx[x], i, k)
            if m is None or not med[x]:
                vals = None
                break
            vals.append(abs(m) / med[x])
        if not vals:
            continue
        score = min(vals)
        if best is None or score > best[1]:
            best = (i, score)
    return best


def journal(L, i0, i1):
    """Chaque changement d une colonne d etat entre deux cycles."""
    out = []
    for i in range(max(1, i0), min(len(L), i1)):
        a, b = L[i - 1], L[i]
        chg = []
        for c in ETATS_RACINE:
            va, vb = (a.get(c) or ""), (b.get(c) or "")
            if va != vb:
                chg.append(("(global)", c, va, vb))
        for x in ACTIFS:
            for c in ETATS:
                cle = "%s_%s" % (x, c)
                va, vb = (a.get(cle) or ""), (b.get(cle) or "")
                if va != vb:
                    chg.append((x, c, va, vb))
        if chg:
            out.append((b.get("ts") or "", chg))
    return out


def autopsie(L, i, k, cyc, pas_aff):
    ts = L[i].get("ts") or "?"
    sx = series(L)
    dis()
    dis("-" * LARG)
    dis("TRAJECTOIRE -- %s, fenetre de %d cycles (%.0f min)"
        % (ts, k, k * cyc / 60.0))
    dis("-" * LARG)
    dis("  %-21s %10s %10s %10s   %s"
        % ("horodatage", VALUE, LARGE, TECH, "en % depuis l ancre"))
    ancre = dict((x, sx[x][i]) for x in ACTIFS)
    j = max(0, i - k)
    fin = min(len(L), i + 3 * k)
    while j < fin:
        vals = []
        for x in ACTIFS:
            v, a0 = sx[x][j], ancre[x]
            vals.append((v - a0) / a0 * 100.0
                        if (v is not None and a0) else None)
        dis("  %-21s %10s %10s %10s   %s"
            % (L[j].get("ts") or "?",
               "%+10.3f" % vals[0] if vals[0] is not None else "  -",
               "%+10.3f" % vals[1] if vals[1] is not None else "  -",
               "%+10.3f" % vals[2] if vals[2] is not None else "  -",
               "<== ancre" if j == i else
               ("<-- fin de fenetre" if j == i + k else "")))
        j += pas_aff

    dis()
    dis("-" * LARG)
    dis("LE SIGNE, SUR LA FENETRE")
    dis("-" * LARG)
    signes = {}
    for x in ACTIFS:
        m = bouge(sx[x], i, k)
        signes[x] = m
        dis("  %-8s %+8.3f %%   %s"
            % (x, m if m is not None else 0.0,
               "VERT" if (m or 0) > 0 else ("ROUGE" if (m or 0) < 0 else
                                            "plat")))
    if signes[VALUE] is not None and signes[TECH] is not None \
            and signes[VALUE] * signes[TECH] < 0:
        dis()
        dis("  => DIVERGENCE DE SIGNE : %s et %s partent en sens"
            % (VALUE, TECH))
        dis("     contraire sur la meme fenetre. C est l observation de")
        dis("     l utilisateur, et elle est verifiee ici sur les prix du")
        dis("     moteur, pas sur une capture d ecran.")
    else:
        dis()
        dis("  => PAS de divergence de signe sur cette fenetre : les trois")
        dis("     vont dans le meme sens. L observation ne se retrouve pas")
        dis("     a cet instant precis -- essayer une autre fenetre")
        dis("     (--fenetre) avant d en conclure quoi que ce soit.")

    dis()
    dis("-" * LARG)
    dis("JOURNAL DES CHANGEMENTS D ETAT (ce que le moteur a enregistre)")
    dis("-" * LARG)
    jr = journal(L, i - k, i + 3 * k)
    if not jr:
        dis("  Aucun changement d etat dans la plage. C est en soi un")
        dis("  resultat : le moteur n a rien vu changer pendant le choc.")
    else:
        for ts_c, chg in jr:
            for actif, col, va, vb in chg:
                dis("  %-21s %-8s %-12s %-18s -> %s"
                    % (ts_c, actif, col, va[:18] or "(vide)",
                       vb[:24] or "(vide)"))
        dis()
        dis("  %d changements. Les colonnes numeriques ne sont pas dans ce"
            % sum(len(c) for _, c in jr))
        dis("  journal : elles bougent a chaque cycle et n apprendraient")
        dis("  rien. Seules les etiquettes y figurent.")
    return signes


# ----------------------------------------------------------------------
# 2. SIGNATURE + REVERSE
# ----------------------------------------------------------------------

def evenements(jours, k, seuil, med, exiger_divergence):
    """Toutes les fenetres ou les trois actifs depassent `seuil` fois
    leur amplitude mediane, avec ou sans divergence de signe.

    Periode refractaire d une fenetre : sinon un seul choc de dix
    minutes ressort cent fois et gonfle l effectif sans ajouter une
    seule observation."""
    out = []
    for j in sorted(jours):
        L = jours[j]
        sx = series(L)
        i = 0
        n = len(L)
        while i < n - k:
            ms = {}
            ok = True
            for x in ACTIFS:
                m = bouge(sx[x], i, k)
                if m is None or not med[x] or abs(m) < seuil * med[x]:
                    ok = False
                    break
                ms[x] = m
            if ok:
                div = ms[VALUE] * ms[TECH] < 0
                if div == bool(exiger_divergence):
                    out.append({"jour": j, "i": i, "ts": L[i].get("ts"),
                                "m": ms, "div": div})
                    i += k
                    continue
            i += 1
    return out


def suites(jours, ev, k, apres_k):
    """Ce que font les trois actifs APRES la fenetre, en %."""
    L = jours[ev["jour"]]
    sx = series(L)
    dep = ev["i"] + k
    out = {}
    for lab, ka in apres_k:
        out[lab] = dict((x, bouge(sx[x], dep, ka)) for x in ACTIFS)
    return out


# ----------------------------------------------------------------------
# 3. INVENTAIRE DES SOURCES QUI MANQUENT
# ----------------------------------------------------------------------

def cles_premiere_ligne(chemin):
    """Les cles de la premiere ligne JSON d un fichier, sans le lire en
    entier. On ne devine pas un schema, on le lit."""
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            for l in f:
                l = l.strip()
                if not l:
                    continue
                d = json.loads(l)
                if isinstance(d, dict):
                    return sorted(d.keys())
                return ["(la ligne n est pas un objet JSON)"]
    except Exception as e:
        return ["(illisible : %s)" % type(e).__name__]
    return ["(fichier vide)"]


# Ce qu on cherche, par fragment de NOM DE FICHIER. On ne suppose ni
# le dossier ni l extension : la premiere version ne regardait que
# docs\buddha\<jour>\ avec un prefixe exact, et aurait annonce "ABSENT"
# pour un fichier simplement range ailleurs. Annoncer une absence
# qu on n a pas cherchee est pire que ne rien dire.
CIBLES = (
    ("ORDERFLOW", ("of_", "orderflow", "order_flow", "footprint")),
    ("CHURN / TRADES", ("churn", "trades", "deals")),
    ("SNAPSHOTS", ("snapshot",)),
    ("NEWS", ("news", "newsletter", "flux_news")),
    ("CALENDRIER ECO", ("calend", "calendar", "econo", "cpi", "macro")),
)
IGNORE = (".git", "__pycache__", "node_modules", ".venv", "venv",
          "site-packages", ".idea", "backup", "bak")


def balaie(racines, profondeur):
    """Tous les fichiers sous quelques racines, jusqu a une profondeur.

    Limite volontaire : la stack fait 200 modules et des archives de
    plusieurs Go ; un os.walk sans borne mettrait des minutes et
    n apprendrait rien de plus."""
    vus, deja = [], set()
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        base = racine.rstrip(os.sep).count(os.sep)
        for dossier, sd, fs in os.walk(racine):
            sd[:] = [d for d in sd
                     if not any(m in d.lower() for m in IGNORE)]
            if dossier.count(os.sep) - base >= profondeur:
                sd[:] = []
            for f in fs:
                c = os.path.join(dossier, f)
                # `.` fait repasser sur docs\ et logs\ : sans cette cle
                # chaque fichier compte double et le poids annonce est
                # faux. Un inventaire qui se trompe de compte est pire
                # qu un inventaire absent.
                k = os.path.normcase(os.path.realpath(c))
                if k in deja:
                    continue
                deja.add(k)
                vus.append(c)
    return vus


def montre_schema(chemin):
    if chemin.endswith(".gz"):
        dis("    compresse : je ne l ouvre pas ici. Dites-moi si je le")
        dis("    transcris comme on l a fait pour cycles.jsonl.")
        return
    if chemin.endswith(".jsonl") or chemin.endswith(".json"):
        cles = cles_premiere_ligne(chemin)
        dis("    cles de la premiere ligne (%d) :" % len(cles))
        ligne = "      "
        for c in cles:
            if len(ligne) + len(c) > LARG - 4:
                dis(ligne)
                ligne = "      "
            ligne += c + "  "
        if ligne.strip():
            dis(ligne)
        return
    if chemin.endswith(".csv"):
        try:
            with io.open(chemin, encoding="utf-8", errors="replace") as f:
                tete = f.readline().strip()
            dis("    en-tete : %s" % tete[:LARG * 2])
        except OSError:
            dis("    en-tete illisible.")


def inventaire(racines, profondeur):
    dis()
    dis("=" * LARG)
    dis("INVENTAIRE DES SOURCES QUE JE N AI PAS ENCORE BRANCHEES")
    dis("=" * LARG)
    dis("  Lecture seule : on liste des noms, on lit UNE ligne des")
    dis("  fichiers texte, on n ouvre aucune archive compressee et on")
    dis("  n ecrit nulle part.")
    dis("  Racines balayees, profondeur %d : %s"
        % (profondeur, ", ".join(racines)))
    tout = balaie(racines, profondeur)
    dis("  %d fichiers examines." % len(tout))
    for nom, frags in CIBLES:
        trouves = [c for c in tout
                   if any(f in os.path.basename(c).lower() for f in frags)]
        dis()
        dis("-" * LARG)
        dis("  %s -- fragments cherches : %s"
            % (nom, ", ".join(frags)))
        if not trouves:
            dis("    RIEN sous ces racines a cette profondeur. Ca ne veut")
            dis("    pas dire que ca n existe pas : ca veut dire que je ne")
            dis("    l ai pas trouve la ou j ai cherche. Donnez-moi le")
            dis("    chemin et je le branche.")
            continue
        poids = 0
        for c in trouves:
            try:
                poids += os.path.getsize(c)
            except OSError:
                pass
        dis("    %d fichier(s), %.1f Mo au total."
            % (len(trouves), poids / 1e6))
        trouves.sort(key=lambda c: os.path.getsize(c)
                     if os.path.exists(c) else 0, reverse=True)
        for c in trouves[:4]:
            try:
                t = dt.datetime.fromtimestamp(os.path.getmtime(c))
                dis("      %-64s %8.1f Mo  %s"
                    % (c[-64:], os.path.getsize(c) / 1e6,
                       t.strftime("%Y-%m-%d %H:%M")))
            except OSError:
                dis("      %s" % c)
        if len(trouves) > 4:
            dis("      ... et %d autre(s)." % (len(trouves) - 4))
        dis("    le plus gros : %s" % trouves[0])
        montre_schema(trouves[0])


def couverture(jours):
    """CE QUE CHAQUE JOURNEE CONTIENT REELLEMENT.

    Ecrit apres un run reel du 17/08 ou quatre journees sont sorties a
    0,00 % sur les trois actifs, et ou la bougie du 12/08 visible sur
    le graphique n apparaissait pas dans les cycles. Une journee "plate"
    et une journee "fermee" donnent le meme zero, et une journee
    tronquee a 14h ressemble a une journee calme.

    Trois colonnes suffisent a les distinguer : la plage horaire
    couverte, le nombre de cycles, et le nombre de prix DISTINCTS. Un
    marche ferme donne un seul prix distinct sur des milliers de
    cycles. Une journee tronquee se voit a son heure de fin.

    Ce controle passe AVANT toute mesure. Une statistique calculee sur
    des journees fermees est fausse sans jamais le dire."""
    dis()
    dis("=" * LARG)
    dis("0. COUVERTURE REELLE DE CHAQUE JOURNEE")
    dis("=" * LARG)
    dis("  %-12s %8s %10s %10s %8s %8s %8s"
        % ("jour", "cycles", "debut", "fin", "prix " + VALUE,
           "prix " + LARGE, "prix " + TECH))
    dis("  %-12s %8s %10s %10s %8s %8s %8s"
        % ("", "", "", "", "distincts", "distincts", "distincts"))
    # L heure de fin normale n est pas connue d avance : la stack ne
    # tourne pas 24h et sa plage a pu changer. On la MESURE -- mediane
    # des heures de fin -- et on ne signale que les journees qui
    # s ecartent d au moins une heure. Une premiere version comparait a
    # 18h en dur et marquait 17 journees sur 18 : un seuil invente
    # produit un drapeau qui ne distingue plus rien.
    fins = []
    for j in sorted(jours):
        ts = [horo(r.get("ts")) for r in jours[j]]
        ts = [t for t in ts if t]
        if ts:
            fins.append(ts[-1].hour * 60 + ts[-1].minute)
    fin_normale = mediane(fins) or 0

    fermees, tronquees = [], []
    for j in sorted(jours):
        L = jours[j]
        ts = [horo(r.get("ts")) for r in L]
        ts = [t for t in ts if t]
        deb = ts[0].strftime("%H:%M") if ts else "?"
        fin = ts[-1].strftime("%H:%M") if ts else "?"
        sx = series(L)
        dist = dict((x, len(set(v for v in sx[x] if v is not None)))
                    for x in ACTIFS)
        marque = ""
        if all(dist[x] <= 1 for x in ACTIFS):
            marque = "FERMEE"
            fermees.append(j)
        elif ts and (ts[-1].hour * 60 + ts[-1].minute) < fin_normale - 60:
            marque = "COURTE"
            tronquees.append(j)
        dis("  %-12s %8d %10s %10s %8d %8d %8d   %s"
            % (j, len(L), deb, fin, dist[VALUE], dist[LARGE], dist[TECH],
               marque))
    dis()
    if fermees:
        dis("  %d journee(s) FERMEE(S) : %s"
            % (len(fermees), ", ".join(fermees)))
        dis("  Un seul prix distinct sur toute la journee : le marche")
        dis("  etait ferme. Ces journees ne sont pas plates, elles sont")
        dis("  vides -- les compter comme des journees a rendement nul")
        dis("  tire toutes les moyennes vers zero et gonfle l effectif.")
        dis("  Elles sont exclues de tout ce qui suit.")
    dis()
    dis("  Heure de fin habituelle, mesuree sur les journees presentes :"
        " %02d:%02d." % (int(fin_normale) // 60, int(fin_normale) % 60))
    if tronquees:
        dis()
        dis("  %d journee(s) COURTE(S), qui s arretent au moins une heure"
            % len(tronquees))
        dis("  plus tot que les autres : %s" % ", ".join(tronquees))
        dis("  Si la bougie cherchee est apres leur heure de fin, elle")
        dis("  n est PAS dans le fichier et aucune autopsie ne la")
        dis("  trouvera. Ce n est pas un probleme d analyse mais de")
        dis("  collecte.")
    else:
        dis("  Aucune journee ne s arrete anormalement tot.")
    dis()
    dis("  Si la bougie que vous cherchez est APRES cette heure sur")
    dis("  toutes les journees, alors ce n est pas une journee qui est")
    dis("  tronquee : c est la plage de collecte qui ne la couvre pas.")
    dis("  Ca se voit ici et nulle part ailleurs.")
    return set(fermees)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--archives", default="docs,logs,data,cartes,.",
                   help="racines a balayer pour l inventaire")
    p.add_argument("--profondeur", type=int, default=3)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--instant", default="2026-08-12 14:30")
    p.add_argument("--rayon", type=float, default=180.0,
                   help="minutes de recherche autour de l instant")
    p.add_argument("--fenetre", type=float, default=15.0,
                   help="duree de la bougie etudiee, en minutes")
    p.add_argument("--seuil", type=float, default=2.5,
                   help="un choc = amplitude > ce multiple de la mediane")
    p.add_argument("--apres", default="15,30,60",
                   help="horizons de suite, en minutes")
    p.add_argument("--mini", type=int, default=5,
                   help="en dessous, on liste et on ne calcule pas")
    p.add_argument("--pas-affichage", type=int, default=6)
    p.add_argument("--sans-inventaire", action="store_true")
    a = p.parse_args()

    jours = charge(a.entree)
    if not jours:
        print("KO : aucun CSV dans %s." % a.entree)
        print("     Lance d abord : python extraire_cycles.py")
        return 1
    cyc = pas_median(jours)
    k = max(1, int(round(a.fenetre * 60.0 / cyc)))
    apres_k = []
    for x in a.apres.split(","):
        x = x.strip()
        if x:
            apres_k.append((float(x), max(1, int(round(float(x) * 60.0
                                                       / cyc)))))
    noms = sorted(jours)

    dis("=" * LARG)
    dis("AUTOPSIE D UNE BOUGIE DE CHOC, PUIS RECHERCHE ARRIERE")
    dis("=" * LARG)
    dis("  %d journees (%s a %s), pas median %.0f s."
        % (len(noms), noms[0], noms[-1], cyc))
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis("  fenetre etudiee : %.0f min (%d cycles)" % (a.fenetre, k))
    dis()
    dis("  Signature cherchee, en deux conditions :")
    dis("    1. les TROIS actifs bougent plus de %.1f fois leur amplitude"
        % a.seuil)
    dis("       mediane sur %.0f min ;" % a.fenetre)
    dis("    2. le signe de %s est OPPOSE a celui de %s." % (VALUE, TECH))
    dis()
    dis("  La condition 2 est le coeur du sujet : une difference")
    dis("  d amplitude peut venir de la volatilite ou du pas de cotation,")
    dis("  une difference de SIGNE non.")
    dis("=" * LARG)

    # Controle d integrite AVANT toute mesure. Les journees fermees
    # sortent du jeu ici et pas plus loin : une seule fonction qui les
    # oublierait suffirait a fausser une moyenne en silence.
    fermees = couverture(jours)
    for j in fermees:
        del jours[j]
    noms = sorted(jours)
    if not noms:
        dis("  Toutes les journees sont fermees. Rien a mesurer.")
        return 1

    # mediane de reference des amplitudes, toutes journees
    med = {}
    for x in ACTIFS:
        tout = []
        for j in noms:
            sx = series(jours[j])[x]
            tout.extend(abs(v) for v in amplitudes(sx, k) if v is not None)
        med[x] = mediane(tout) or 0.0
    dis()
    dis("  Amplitude mediane sur %.0f min : %s %.3f %%, %s %.3f %%,"
        % (a.fenetre, VALUE, med[VALUE], LARGE, med[LARGE]))
    dis("  %s %.3f %%. Seuil de choc : %.1f fois ces valeurs."
        % (TECH, med[TECH], a.seuil))

    # ---- 1. autopsie ----
    cible = horo(a.instant) or horo(a.instant + " 00:00:00")
    jour = a.instant[:10]
    if jour not in jours:
        dis()
        dis("  La journee %s n est pas dans les CSV. Disponibles : %s"
            % (jour, ", ".join(noms)))
        dis("  Rien a disséquer -- on passe directement au reverse.")
        anc = None
    else:
        L = jours[jour]
        sx = series(L)
        best = trouve_ancre(L, sx, k, cible, a.rayon * 60.0, med)
        if best is None:
            dis()
            dis("  Aucune fenetre exploitable autour de %s." % a.instant)
            anc = None
        else:
            i, score = best
            ts = horo(L[i].get("ts"))
            dis()
            dis("=" * LARG)
            dis("1. AUTOPSIE")
            dis("=" * LARG)
            dis("  instant demande : %s" % a.instant)
            dis("  fenetre la plus violente trouvee dans +/- %.0f min : %s"
                % (a.rayon, L[i].get("ts")))
            if ts and cible:
                ecart = (ts - cible).total_seconds() / 60.0
                dis("  ecart : %+.0f minutes." % ecart)
                if abs(ecart) > 45:
                    dis("  ATTENTION : plus de 45 minutes d ecart. Les")
                    dis("  graphiques sont a l heure du serveur et les")
                    dis("  cycles a celle du VPS -- il y a probablement un")
                    dis("  decalage de fuseau. L autopsie porte sur la")
                    dis("  fenetre TROUVEE, pas sur celle demandee.")
            dis("  score conjoint : %.1f (le plus faible des trois"
                % score)
            dis("  rapports amplitude/mediane ; il ne monte que si les")
            dis("  trois bougent ensemble).")
            autopsie(L, i, k, cyc, max(1, a.pas_affichage))
            anc = (jour, i)

    # ---- 2. reverse ----
    dis()
    dis("=" * LARG)
    dis("2. RECHERCHE ARRIERE -- LA MEME SIGNATURE AILLEURS")
    dis("=" * LARG)
    div = evenements(jours, k, a.seuil, med, True)
    tem = evenements(jours, k, a.seuil, med, False)
    dis("  %d evenement(s) avec divergence de signe." % len(div))
    dis("  %d evenement(s) de meme amplitude SANS divergence -- c est le"
        % len(tem))
    dis("  temoin apparie : sans lui on mesurerait ce qui suit un gros")
    dis("  mouvement et on l appellerait ce qui suit une divergence.")
    dis()
    if div:
        dis("  %-21s %9s %9s %9s" % ("horodatage", VALUE, LARGE, TECH))
        for e in div:
            dis("  %-21s %+9.3f %+9.3f %+9.3f"
                % (e["ts"], e["m"][VALUE], e["m"][LARGE], e["m"][TECH]))
    if anc and not any(e["jour"] == anc[0] and abs(e["i"] - anc[1]) <= k
                       for e in div):
        dis()
        dis("  A NOTER : la bougie disséquee ci-dessus n apparait PAS dans")
        dis("  cette liste. Soit elle ne diverge pas de signe sur %.0f min,"
            % a.fenetre)
        dis("  soit elle n atteint pas %.1f fois l amplitude mediane."
            % a.seuil)
        dis("  Autrement dit : l evenement de depart ne verifie pas la")
        dis("  definition qu on en a tiree. C est un desaccord a regler")
        dis("  avant toute conclusion -- probablement en changeant")
        dis("  --fenetre, la duree de la bougie etant un choix, pas une")
        dis("  mesure.")

    if len(div) < a.mini:
        dis()
        dis("  => %d evenement(s), moins que le minimum de %d. On s arrete"
            % (len(div), a.mini))
        dis("     ici. Une moyenne sur %d ligne(s) n est pas une"
            % len(div))
        dis("     statistique, et un tableau bien aligne donnerait")
        dis("     l illusion du contraire.")
        dis()
        dis("     Ce n est pas un echec de la methode : avec %d journees,"
            % len(noms))
        dis("     un evenement de ce type est rare par construction. La")
        dis("     reponse est \"il faut plus d historique\", et elle est")
        dis("     chiffree : a ce rythme, il en faudrait environ %d"
            % (int(round(a.mini * len(noms) / max(1, len(div))))
               if div else 0))
        dis("     journees pour en reunir %d." % a.mini)
    else:
        dis()
        dis("-" * LARG)
        dis("CE QUI SE PASSE APRES -- divergence contre temoin")
        dis("-" * LARG)
        dis("  %-10s %-8s %12s %12s %10s"
            % ("horizon", "actif", "divergence", "temoin", "difference"))
        for lab, ka in apres_k:
            for x in ACTIFS:
                a1 = [s[lab][x] for s in (suites(jours, e, k, apres_k)
                                          for e in div)
                      if s[lab][x] is not None]
                a2 = [s[lab][x] for s in (suites(jours, e, k, apres_k)
                                          for e in tem)
                      if s[lab][x] is not None]
                if not a1 or not a2:
                    continue
                m1, m2 = moyenne(a1), moyenne(a2)
                dis("  %6.0f min %-8s %+11.3f %% %+11.3f %% %+9.3f %%"
                    % (lab, x, m1, m2, m1 - m2))
        dis()
        dis("  La colonne qui repond a la question est la DERNIERE.")
        dis("  Les deux premieres contiennent la tendance du marche sur")
        dis("  la periode ; leur difference, non.")
        dis()
        dis("  Aucun p-value ici : avec %d evenements, il serait calcule"
            % len(div))
        dis("  mais pas croyable. Quand l effectif le permettra, la")
        dis("  calibration se fera par permutation par journee, comme")
        dis("  dans cassure_par_actif.py.")

    if not a.sans_inventaire:
        inventaire([x.strip() for x in a.archives.split(",") if x.strip()],
                   a.profondeur)

    dis()
    dis("=" * LARG)
    dis("CE QUE CETTE AUTOPSIE NE PEUT PAS VOIR")
    dis("=" * LARG)
    dis("  Elle est faite sur cycles.jsonl : des instantanes a %.0f s des"
        % cyc)
    dis("  prix et des etats du moteur. Il lui manque, et l inventaire")
    dis("  ci-dessus dit lesquels sont sur le disque :")
    dis()
    dis("    - l ORDERFLOW : qui achete, qui vend, a quel prix. Sans lui")
    dis("      on voit le resultat du choc, jamais son mecanisme.")
    dis("    - le CHURN : les euros. Toutes les lignes ci-dessus sont en")
    dis("      points d indice ; aucune ne dit si la stack a gagne ou")
    dis("      perdu sur cette bougie. C est la mesure qui manque depuis")
    dis("      le debut.")
    dis("    - les NEWS : le seul endroit qui prouve que le 12/08 est un")
    dis("      CPI. Le detecteur voit un choc, il ne sait pas ce qui l a")
    dis("      cause.")
    dis("    - l HISTORIQUE LONG : 18 journees ne feront jamais un")
    dis("      reverse. Les barres MT5 sur plusieurs mois, oui.")

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (a.sortie, os.path.getsize(a.sortie)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
