# -*- coding: utf-8 -*-
r"""
papers_coupure.py -- la coupure deduite par TOUTES les cles, pas par quatre

  python papers_coupure.py
  python papers_coupure.py --cle M5_ET_NO_C

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

CE QUE LE RUN DU 19/08 A ETABLI, ET CE QU IL A REVELE

    Etabli, et definitivement : la population n y est pour rien. Les
    35 cles rendent le MEME compte sur rails et sur churn, sans une
    exception. 4696 contre 4704 lignes. L hypothese est morte.

    Etabli aussi : ce que le code annonce est juste. Ecartement,
    accords TF -- sections entieres exactes. M3_CONV_CL exact sur ALL,
    comme la vue C le dit.

    Revele : MA FAUTE. papers_population deduit la coupure sur QUATRE
    effectifs de reference et termine par `return bas` -- le point le
    plus tot de la fenetre valide. Rien ne justifiait ce choix. Resultat
    19:00:04, alors que papers_repare tournait a 19:26:10 et rendait 20
    cles au lieu de 18. Memes predicats, memes donnees, seule la coupure
    change.

    Et la trace est lisible : presque tous les echecs MANQUENT de 2 a
    3 %. 288/295, 304/313, 183/190, 348/365, 346/355, 293/301, 100/104,
    106/107. C est la meme bande de 26 minutes qui manque a toutes.

CE QUE FAIT CE SCRIPT

    Une coupure est un scalaire. Chaque cle dont l effectif est
    atteignable impose une fenetre [Nieme, (N+1)ieme) : la coupure doit
    y tomber pour que la cle soit exacte. Trente-trois contraintes pour
    une inconnue.

    Le script balaye donc l axe du temps et compte, en chaque point,
    COMBIEN de cles seraient exactes. Le maximum designe la coupure --
    et le PROFIL autour du maximum dit si elle est identifiee ou non :
    un pic net vaut une deduction, un plateau mou n en vaut aucune.

    Ce n est pas un reglage. Un reglage choisit un parametre pour
    ameliorer un resultat. Ici les 33 fenetres sont imposees par des
    effectifs que nous n avons pas choisis, et le script publie le
    profil complet : si le maximum etait plat, ca se verrait.

CE QU IL DIT DE CHAQUE ECHEC, ET C EST LE PLUS UTILE

    Au point retenu, une cle qui rate le fait dans UN SENS :

      TROP TARD   sa fenetre s ouvre APRES la coupure -- au consensus
                  elle manque des lignes. Predicat trop strict, ou
                  effectif qui reclame une periode plus longue.
      TROP TOT    sa fenetre se ferme AVANT -- elle deborde. Predicat
                  trop permissif : il attrape ce qui ne lui revient pas.
      DEFICIT     meme sans aucune coupure elle n atteint pas N. La
                  coupure ne peut rien pour elle, jamais.

    C M15_VENTE (491 pour 358), M5_ET_NO_C (649 pour 290) et M15_NO_MX
    (698 pour 396) debordent : aucune coupure plus tardive ne les
    sauvera, elle ne fait qu ajouter. Le sens de l erreur est deja la.

CE QUE JE TESTE EN PLUS, ET POURQUOI CE N EST PAS UN 25e ESSAI

    L ORDRE DES OPERATIONS SUR LES SIGNAUX. Le panneau fait
    signals = _signals(trades) puis compte. papers_population fusionne
    les jumeaux PUIS coupe. L autre ordre -- couper puis fusionner --
    n est pas le meme calcul : une paire a cheval sur la coupure
    fusionne dans un cas et se scinde dans l autre.

    C est une question binaire de structure, posee d avance, pas une
    recherche : deux ordres possibles, on les regarde tous les deux et
    on dit lequel est compatible avec le consensus.

CE QUE JE SUPPOSE ENCORE, ET C EST MARQUE

    _ts_epoch reste reimplementee (voir papers_population). Et
    RSI_M1_BU / RSI_M15_BU ne viennent d aucune section du panneau :
    elles restent hors decompte, leur source est ailleurs.
"""
import argparse
import io
import os
import sys

INFINI = "9999-99-99 99:99:99"   # borne droite ouverte, > tout horodatage


def horodates(records, pred, colonne, PE):
    """Les entry_ts des lignes que ce predicat retient, triees."""
    ts = []
    for t in records:
        e = t.get("entry_ts")
        if not isinstance(e, str):
            continue
        if colonne != "ALL" and PE._sess(t) != colonne:
            continue
        try:
            if pred(t):
                ts.append(e)
        except Exception:
            pass
    ts.sort()
    return ts


def fenetre(ts, n):
    """[debut, fin) des coupures qui rendent EXACTEMENT n.

    La coupure est inclusive (on garde e <= c), donc c = ts[n-1] rend n
    et c = ts[n] rend n+1."""
    if len(ts) < n:
        return None, None
    return ts[n - 1], (ts[n] if len(ts) > n else INFINI)


def balaye(fenetres):
    """Combien de cles seraient exactes en chaque point de l axe.

    Rend [(debut, fin, nb, [cles])] par intervalle, du plus couvert au
    moins couvert. Les deltas d un meme instant sont tous appliques
    AVANT d evaluer l intervalle qui commence la : une fenetre qui se
    ferme en t n inclut pas t, une qui s ouvre en t l inclut."""
    delta = {}
    for _cle, (lo, hi) in fenetres.items():
        if lo is None:
            continue
        delta[lo] = delta.get(lo, 0) + 1
        delta[hi] = delta.get(hi, 0) - 1
    instants = sorted(delta)
    out, cur = [], 0
    for i, t in enumerate(instants):
        cur += delta[t]
        fin = instants[i + 1] if i + 1 < len(instants) else INFINI
        if cur > 0:
            dedans = [c for c, (lo, hi) in fenetres.items()
                      if lo is not None and lo <= t < hi]
            out.append((t, fin, cur, dedans))
    out.sort(key=lambda r: (-r[2], r[0]))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rails", default=None)
    p.add_argument("--cle", default=None)
    a = p.parse_args()

    try:
        import papers_encode as PE
        import papers_population as PP
    except ImportError as e:
        print("KO : papers_encode.py et papers_population.py doivent etre")
        print("     dans le meme dossier. (%s)" % e)
        return 1

    # Les predicats corriges. Sans eux on remesurerait avec les
    # definitions dont on sait deja qu elles sont fausses.
    try:
        import papers_repare as PR
        src = io.open(PR.trouve_panneau([".", "..", os.path.join("..", "..")]),
                      encoding="utf-8", errors="replace").read()
        below, _err = PR.literal_apres(src, "_ANCHOR_BELOW")
        nest = PR.fabrique_nest(below, PE) if isinstance(below, dict) else None
        cles = [(c, n, pr) for c, n, pr, _o in PR.construit_cles(PE, nest)]
        origine = "papers_repare (corriges le 19/08)"
    except Exception as e:
        print("KO : papers_repare.py est indispensable ici -- sans lui les")
        print("     predicats sont ceux qu on sait faux. (%s)" % e)
        return 1

    L = []
    add = L.append
    add("=" * 96)
    add("LA COUPURE, DEDUITE PAR TOUTES LES CLES AU LIEU DE QUATRE")
    add("=" * 96)
    add("")
    add("  Lecteur seul. Rien n est ecrit, aucun trade n est pris.")
    add("")

    chemin = a.rails or PP.RAILS
    trades, ko = PP.lire(chemin)
    sigs, ecartes = PP.signaux(trades)
    add("  %s : %d lignes (%d illisibles)" % (chemin, len(trades), ko))
    add("  signaux (jumeaux 206/207 fusionnes) : %d, %d ecarte(s)"
        % (len(sigs), ecartes))
    add("  predicats : %s, %d cles" % (origine, len(cles)))
    add("")
    if not trades:
        add("  Fichier vide ou introuvable. Rien a deduire.")
        print("\n".join(L))
        return 1

    # ---------------------------------------------------------------
    # 1. la fenetre de chaque cle
    # ---------------------------------------------------------------
    add("=" * 96)
    add("LA FENETRE DE CHAQUE CLE -- [Nieme, (N+1)ieme)")
    add("=" * 96)
    add("  Une coupure dans cette fenetre rend la cle exacte. Hors d elle,")
    add("  jamais. C est une contrainte, pas une preference.")
    add("")
    add("  %-13s %5s %-8s %-4s %6s  %-19s %-19s"
        % ("CLE", "N", "POP", "COL", "dispo", "ouvre a", "ferme a"))
    add("  " + "-" * 82)

    fenetres, tsmap, meta = {}, {}, {}
    hors = []
    for cle, n, pred in cles:
        genre, col_fixe = PP.SECTIONS.get(cle, (None, None))
        if genre is None:
            hors.append((cle, n))
            continue
        pop = sigs if genre == "signaux" else trades
        col = col_fixe or "US"
        ts = horodates(pop, pred, col, PE)
        lo, hi = fenetre(ts, n)
        fenetres[cle] = (lo, hi)
        tsmap[cle] = ts
        meta[cle] = (n, genre, col)
        add("  %-13s %5d %-8s %-4s %6d  %-19s %-19s"
            % (cle, n, genre, col, len(ts),
               lo or "DEFICIT (%d < %d)" % (len(ts), n),
               "" if lo is None else ("(ouverte)" if hi == INFINI else hi)))
    for cle, n in hors:
        add("  %-13s %5d %-8s %-4s %6s  %s"
            % (cle, n, "?", "?", "-", "hors panneau -- aucune section"))
    add("")

    # ---------------------------------------------------------------
    # 2. le balayage
    # ---------------------------------------------------------------
    prof = balaye(fenetres)
    add("=" * 96)
    add("LE BALAYAGE -- combien de cles seraient exactes, point par point")
    add("=" * 96)
    if not prof:
        add("  Aucune fenetre exploitable.")
        print("\n".join(L))
        return 1
    haut = prof[0][2]
    add("  %-19s %-19s %5s" % ("de", "a (exclu)", "cles"))
    add("  " + "-" * 46)
    montre = sorted([r for r in prof if r[2] >= haut - 2][:12],
                    key=lambda r: r[0])
    for deb, fin, nb, _d in montre:
        add("  %-19s %-19s %5d%s"
            % (deb, "(ouverte)" if fin == INFINI else fin, nb,
               "   <== maximum" if nb == haut else ""))
    add("")
    plateaux = [r for r in prof if r[2] == haut]
    add("  Maximum : %d cles exactes, sur %d qui ont une fenetre."
        % (haut, sum(1 for v in fenetres.values() if v[0] is not None)))
    if len(plateaux) == 1:
        add("  UN SEUL intervalle atteint ce maximum. La coupure est")
        add("  identifiee, pas choisie.")
    else:
        add("  %d intervalles disjoints atteignent ce maximum -- la coupure"
            % len(plateaux))
        add("  n est donc PAS identifiee a elle seule -- et ils ne rendent")
        add("  pas les MEMES cles exactes. Les voici tous, avec ce que")
        add("  chacun change, pour que le choix se voie au lieu de se")
        add("  cacher dans un return.")
        add("")
        commun = set(plateaux[0][3])
        for _d, _f, _n, dedans in plateaux[1:]:
            commun &= set(dedans)
        for deb, fin, _n, dedans in plateaux:
            propre = sorted(set(dedans) - commun)
            add("    %s -> %s   propre a cet intervalle : %s"
                % (deb, "(ouverte)" if fin == INFINI else fin,
                   ", ".join(propre) or "rien"))
        add("")
        add("    commun aux %d : %d cles" % (len(plateaux), len(commun)))
    COUPURE = plateaux[0][0]
    add("")
    add("  Coupure retenue : %s" % COUPURE)
    add("  (papers_population, sur 4 contraintes, donnait 2026-08-17"
        " 19:00:04)")
    add("")

    # ---------------------------------------------------------------
    # 3. le verdict, avec le SENS de chaque echec
    # ---------------------------------------------------------------
    add("=" * 96)
    add("CHAQUE CLE AU POINT RETENU -- et dans quel SENS elle rate")
    add("=" * 96)
    add("")
    add("  %-13s %5s %6s %6s  %s"
        % ("CLE", "N", "compte", "ecart", "verdict"))
    add("  " + "-" * 66)
    etats = {}
    for cle, n, _pred in cles:
        if cle not in fenetres:
            continue
        ts = tsmap[cle]
        v = sum(1 for e in ts if e <= COUPURE)
        lo, hi = fenetres[cle]
        if lo is None:
            et = "DEFICIT -- %d au total, aucune coupure n y suffit" % len(ts)
        elif lo <= COUPURE < hi:
            et = "EXACT"
        elif lo > COUPURE:
            et = "TROP TARD -- sa fenetre ouvre a %s" % lo
        else:
            et = "TROP TOT -- sa fenetre ferme a %s" % hi
        etats[cle] = et
        add("  %-13s %5d %6d %+6d  %s" % (cle, n, v, v - n, et))
    for cle, n in hors:
        etats[cle] = "hors panneau"
        add("  %-13s %5d %6s %6s  hors panneau" % (cle, n, "-", "-"))
    add("")
    exacts = [c for c, e in etats.items() if e == "EXACT"]
    add("  %d cles sur %d exactes." % (len(exacts), len(cles)))
    add("")

    # ---------------------------------------------------------------
    # 4. l ordre des operations sur les signaux
    # ---------------------------------------------------------------
    add("=" * 96)
    add("L ORDRE DES OPERATIONS SUR LES SIGNAUX")
    add("=" * 96)
    add("  Fusionner PUIS couper, ou couper PUIS fusionner ? Une paire a")
    add("  cheval sur la coupure fusionne dans un cas, se scinde dans")
    add("  l autre. Deux ordres possibles, poses d avance, regardes tous")
    add("  les deux.")
    add("")
    avant = [t for t in trades
             if isinstance(t.get("entry_ts"), str)
             and t["entry_ts"] <= COUPURE]
    sigs_cm, _e = PP.signaux(avant)
    add("  fusion PUIS coupe : %d signaux au total" % sum(
        1 for s in sigs if isinstance(s.get("entry_ts"), str)
        and s["entry_ts"] <= COUPURE))
    add("  coupe PUIS fusion : %d signaux au total" % len(sigs_cm))
    add("")
    add("  %-13s %5s %8s %8s  %s"
        % ("CLE", "N", "f->c", "c->f", "lequel tombe juste"))
    add("  " + "-" * 60)
    n_fc = n_cf = 0
    for cle, n, pred in cles:
        genre, col_fixe = PP.SECTIONS.get(cle, (None, None))
        if genre != "signaux":
            continue
        col = col_fixe or "ALL"
        a1 = sum(1 for e in tsmap[cle] if e <= COUPURE)
        a2 = len(horodates(sigs_cm, pred, col, PE))
        if a1 == n:
            n_fc += 1
        if a2 == n:
            n_cf += 1
        q = ("les deux" if a1 == n and a2 == n
             else ("f->c" if a1 == n
                   else ("c->f" if a2 == n else "aucun")))
        add("  %-13s %5d %8d %8d  %s" % (cle, n, a1, a2, q))
    add("")
    add("  exactes : %d avec fusion-puis-coupe, %d avec coupe-puis-fusion."
        % (n_fc, n_cf))
    if n_cf > n_fc:
        add("  L ordre coupe-puis-fusion en rend davantage. Le panneau")
        add("  filtrerait donc AVANT _signals, et papers_population")
        add("  applique le mauvais ordre.")
    elif n_fc > n_cf:
        add("  L ordre fusion-puis-coupe en rend davantage : celui de")
        add("  papers_population est le bon. La question est reglee.")
    else:
        add("  Les deux ordres se valent ici -- la question reste ouverte,")
        add("  et ce n est pas cette mesure qui la tranchera.")
    add("")

    # ---------------------------------------------------------------
    # 5. par famille
    # ---------------------------------------------------------------
    add("=" * 96)
    add("PAR FAMILLE")
    add("=" * 96)
    FAM = [
        ("ecartement    (trades, session)",
         ["TC_CLEAN", "TC_MIXED", "MID_CLEAN", "WIDE_CLEAN"]),
        ("par TF        (trades, session)",
         ["M1_T_CL", "M1_S_CH", "M3_T_MX", "M5_T_CL", "M15_T_CL",
          "M15_T_MX"]),
        ("accords TF    (trades, session)",
         ["M1M15", "M1M3M5M15", "M3M5M15"]),
        ("hlc vue A     (trades, session)",
         ["M1_ALBU_CL", "M15_ALBU_CL", "M15_SPL_CL", "M15_SCA_MX"]),
        ("hlc vue B     (trades, ALL)", ["M15_LEAD", "M5_DIVG"]),
        ("hlc vue C     (trades, ALL)",
         ["M3_CONV_CL", "M5_DIV_CL", "M15_CONV_MX"]),
        ("leader        (trades, session)",
         ["US30_BE_CL", "US30_BE_MX", "US500_BU_CL"]),
        ("vs pack       (SIGNAUX, ALL)", ["M5_AGA_CH", "C_M15_VENTE"]),
        ("nest          (SIGNAUX, ALL)",
         ["M5_ET_YES", "M5_ET_NO_A", "M5_ET_NO_C", "M15_NO_MX"]),
        ("trajectoire   (SIGNAUX, ALL)", ["M5_WIDE_CL", "M15_WIDE_CL"]),
        ("RSI           (hors panneau)", ["RSI_M1_BU", "RSI_M15_BU"]),
    ]
    for nom, membres in FAM:
        m = [c for c in membres if c in etats]
        if not m:
            continue
        bons = [c for c in m if etats[c] == "EXACT"]
        rate = [c for c in m if etats[c] != "EXACT"]
        etat = ("TOUTE la section" if len(bons) == len(m)
                else ("aucune" if not bons
                      else "%d sur %d" % (len(bons), len(m))))
        add("  %-34s %-16s %s" % (nom, etat, ", ".join(rate)))
    add("")
    tard = [c for c, e in etats.items() if e.startswith("TROP TARD")]
    tot = [c for c, e in etats.items() if e.startswith("TROP TOT")]
    defi = [c for c, e in etats.items() if e.startswith("DEFICIT")]
    add("  Il MANQUE des lignes a  : %s" % (", ".join(tard) or "aucune"))
    add("  Il en DEBORDE a         : %s" % (", ".join(tot) or "aucune"))
    add("  Hors d atteinte         : %s" % (", ".join(defi) or "aucune"))
    add("")
    add("  Une cle qui deborde ne sera jamais sauvee par une coupure plus")
    add("  tardive : celle-ci ne fait qu ajouter. Son predicat attrape ce")
    add("  qui ne lui revient pas, et c est la qu il faut relire.")
    add("")

    if a.cle:
        add("=" * 96)
        add("DETAIL -- %s" % a.cle)
        add("=" * 96)
        if a.cle not in tsmap:
            add("  Cle inconnue ou hors panneau.")
        else:
            n, genre, col = meta[a.cle]
            ts = tsmap[a.cle]
            lo, hi = fenetres[a.cle]
            add("  annonce %d, disponible %d, population %s, colonne %s"
                % (n, len(ts), genre, col))
            add("  fenetre [%s, %s)" % (lo, hi))
            add("")
            add("  les 5 horodates autour du Nieme :")
            for i in range(max(0, n - 3), min(len(ts), n + 2)):
                add("    %4d  %s%s" % (i + 1, ts[i],
                                       "   <== Nieme" if i == n - 1 else ""))
        add("")

    add("=" * 96)
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 96)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
