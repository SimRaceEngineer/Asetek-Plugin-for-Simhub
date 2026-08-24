# -*- coding: utf-8 -*-
"""
croise_flux.py -- faut-il acheter un flux orderflow LIVE ?
                  Ce qu il aurait trie sur les entrees 220/230/240.

  python croise_flux.py --banc
  python croise_flux.py --ym C:\\SierraChart\\Data\\YMU26-CBOT.scid
                        --mes C:\\SierraChart\\Data\\MESU26-CME.scid
                        --jours 10

LA QUESTION, POSEE PRECISEMENT

    Le flux Sierra dont on disposait arrivait avec dix minutes de
    retard. Il servait a JOURNALISER apres coup, pas a decider : c est
    le dispositif qui a ete choisi, pas un defaut.

    La question d aujourd hui est autre : si l on achetait un flux
    reellement live, pourrait-on classer les ordres EN AMONT et ne
    prendre que les bons ? On simule donc exactement ce qu un tel flux
    donnerait -- l etat du marche a l instant de l entree, jamais une
    seconde apres -- et on regarde s il separe les entrees gagnantes
    des perdantes.

    Le --retard permet de refaire le meme calcul avec un flux en
    retard. L ecart entre les deux chiffre ce que vaut la fraicheur,
    et le tableau de persistance dit quelle latence maximale le
    fournisseur devra tenir.

CE QUE CE SCRIPT NE FAIT PAS, ET POURQUOI

    Il ne reproduit pas les etiquettes CARNAGE / MOU / CORRECT / PROPRE
    du panneau 8097. Elles viennent de la classification Ninja, pas des
    .scid, et je n ai pas leur definition exacte. Les inventer puis leur
    donner les memes noms produirait un tableau qui a l air de repliquer
    le panel alors qu il mesure autre chose.

    Les cases ici sont donc NOMMEES AUTREMENT et definies en clair :
    deux axes mesures sur la fenetre avant l entree, coupes a leur
    mediane propre.

        intensite : volume de la fenetre / volume median des fenetres
        nettete   : |delta| / volume  --  0 = equilibre, 1 = un seul sens

    VIF+NET est ce qui ressemble le plus a un flux qui pousse ; CALME +
    BROUILLON a un marche qui pietine. Le rapprochement avec les mots du
    panel est une LECTURE, pas une equivalence.

LE PIEGE PRINCIPAL, ET LE TEST QUI LE DESAMORCE

    185 trades ranges en 4 cases font 46 par case. L ecart entre la
    meilleure et la pire case sera GROS par hasard seul -- c est
    arithmetique, pas de la malchance. Chercher la meilleure case dans
    un tableau et la declarer regle est la facon la plus courante de
    fabriquer une regle qui ne survit pas au mois suivant.

    Le script fait donc systematiquement un test de permutation : il
    rebat les etiquettes de case entre les trades, sans toucher aux
    resultats, quelques centaines de fois, et regarde combien de fois le
    hasard produit un ecart aussi grand. C est ce pourcentage qui decide,
    jamais le tableau seul.

    Il applique aussi la regle que le panel s impose a lui-meme : sous
    30 trades, une case ne conclut pas.

    Lecture seule. Aucun ordre, aucune ecriture.
"""
import argparse
import datetime
import os
import random
import struct
import sys

SEP = "=" * 78
ORIGINE = datetime.datetime(1899, 12, 30)
EN_TETE = 56
ENREG = 40
FMT = "<q4f4I"
MIROIR_BAS = 220000
MIROIR_HAUT = 250000
MINI_CASE = 30
CASES = ("CALME/BROUILLON", "CALME/NET", "VIF/BROUILLON", "VIF/NET")


def mediane(v):
    if not v:
        return 0.0
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def ecart_median(v):
    """Dispersion robuste : mediane des ecarts a la mediane."""
    if not v:
        return 0.0
    m = mediane(v)
    return mediane([abs(x - m) for x in v])


# ------------------------------------------------------- .scid par fenetre
class Scid(object):
    """Acces a un .scid SANS le charger : les enregistrements sont de
    taille fixe, donc on cherche une date par dichotomie et on ne lit
    que la fenetre voulue. Un fichier de 31 millions de ticks se
    manipule alors en quelques kilo-octets."""

    def __init__(self, chemin):
        self.err = None
        self.f = None
        if not os.path.isfile(chemin):
            self.err = "fichier introuvable"
            return
        taille = os.path.getsize(chemin)
        f = open(chemin, "rb")
        brut = f.read(EN_TETE)
        if len(brut) < EN_TETE or brut[:4] != b"SCID":
            f.close()
            self.err = "signature absente"
            return
        te, tr = struct.unpack("<II", brut[4:12])
        if te != EN_TETE or tr != ENREG:
            f.close()
            self.err = "tailles inattendues (%d / %d)" % (te, tr)
            return
        f.seek(te)
        b8 = f.read(tr)[:8]
        if len(b8) < 8:
            f.close()
            self.err = "fichier sans aucun tick"
            return
        (vi,) = struct.unpack("<q", b8)
        (vd,) = struct.unpack("<d", b8)
        bornes = (datetime.datetime(1990, 1, 1), datetime.datetime(2100, 1, 1))

        def _mi(v):
            try:
                return ORIGINE + datetime.timedelta(microseconds=v)
            except Exception:
                return None

        def _mj(v):
            try:
                return ORIGINE + datetime.timedelta(days=v)
            except Exception:
                return None

        if _mi(vi) is not None and bornes[0] <= _mi(vi) <= bornes[1]:
            self.mode = "micro"
        elif _mj(vd) is not None and bornes[0] <= _mj(vd) <= bornes[1]:
            self.mode = "double"
        else:
            f.close()
            self.err = "aucun encodage de date plausible"
            return
        self.f = f
        self.te = te
        self.tr = tr
        self.total = (taille - te) // tr
        self.base = int((ORIGINE - datetime.datetime(1970, 1, 1))
                        .total_seconds())
        self.nom = os.path.basename(chemin)
        self.taille = taille

    def _sec(self, brut8):
        (v,) = struct.unpack("<q", brut8)
        if self.mode == "micro":
            return self.base + v // 1000000
        (jours,) = struct.unpack("<d", brut8)
        return self.base + int(jours * 86400)

    def temps(self, i):
        self.f.seek(self.te + i * self.tr)
        b = self.f.read(8)
        if len(b) < 8:
            return None
        return self._sec(b)

    def cherche(self, sec):
        """Dernier indice dont la date est <= sec, ou None."""
        bas, haut = 0, self.total - 1
        if self.total <= 0:
            return None
        if self.temps(0) > sec:
            return None
        while bas < haut:
            mil = (bas + haut + 1) // 2
            t = self.temps(mil)
            if t is None or t > sec:
                haut = mil - 1
            else:
                bas = mil
        return bas

    def fenetre(self, i_fin, n):
        """Les n enregistrements qui se terminent a i_fin inclus."""
        i0 = max(0, i_fin - n + 1)
        combien = i_fin - i0 + 1
        if combien <= 0:
            return None
        self.f.seek(self.te + i0 * self.tr)
        brut = self.f.read(combien * self.tr)
        util = brut[:len(brut) - len(brut) % self.tr]
        pr, vo, bi, ak = [], [], [], []
        for m in struct.iter_unpack(FMT, util):
            pr.append(m[4])
            vo.append(m[6])
            bi.append(m[7])
            ak.append(m[8])
        return pr, vo, bi, ak

    def prix_a(self, sec, tolerance=120):
        i = self.cherche(sec)
        if i is None:
            return None
        t = self.temps(i)
        if t is None or abs(t - sec) > tolerance:
            return None
        self.f.seek(self.te + i * self.tr)
        m = struct.unpack(FMT, self.f.read(self.tr))
        return m[4]

    def ferme(self):
        if self.f:
            self.f.close()
            self.f = None


# ------------------------------------------------------------ les traits
def traits(fen):
    """Ce que dit la fenetre qui PRECEDE l entree."""
    pr, vo, bi, ak = fen
    v = float(sum(vo))
    d = float(sum(ak) - sum(bi))
    return {
        "volume": v,
        "delta": d,
        "nettete": (abs(d) / v) if v > 0 else 0.0,
        "etendue": (max(pr) - min(pr)) if pr else 0.0,
        "sens": 1 if d > 0 else (-1 if d < 0 else 0),
    }


def range_case(t, med_vol, med_net):
    vif = "VIF" if t["volume"] > med_vol else "CALME"
    net = "NET" if t["nettete"] > med_net else "BROUILLON"
    return "%s/%s" % (vif, net)


# ------------------------------------------------------------ statistique
def par_case(lignes):
    """{case: (n, somme, moyenne)} sur des (case, resultat)."""
    d = {}
    for c, r in lignes:
        n, s = d.get(c, (0, 0.0))
        d[c] = (n + 1, s + r)
    return dict((c, (n, s, s / n)) for c, (n, s) in d.items())


def ecart_cases(lignes, mini):
    """Meilleure moyenne moins pire, sur les cases assez peuplees."""
    t = par_case(lignes)
    moys = [m for c, (n, s, m) in t.items() if n >= mini]
    if len(moys) < 2:
        return None
    return max(moys) - min(moys)


def permutation(lignes, mini, tirages, rng):
    """Combien de fois le hasard fait aussi bien ? Les resultats ne
    bougent pas, seules les etiquettes de case sont rebattues."""
    vrai = ecart_cases(lignes, mini)
    if vrai is None:
        return None, None, None
    cases = [c for c, _r in lignes]
    res = [r for _c, r in lignes]
    aussi_bien = 0
    for _k in range(tirages):
        rng.shuffle(cases)
        e = ecart_cases(list(zip(cases, res)), mini)
        if e is not None and e >= vrai:
            aussi_bien += 1
    return vrai, aussi_bien, tirages


# ---------------------------------------------------------------- MT5
def lit_positions(jours):
    """[(magic, symbole, sec_entree, prix_entree, sens, resultat)]

    sens : +1 achat, -1 vente. resultat : somme des profits de sortie
    de la position. Lecture seule, aucun ordre.
    """
    try:
        import MetaTrader5 as mt5
    except Exception as e:
        return None, "MetaTrader5 indisponible : %s" % (e,)
    if not mt5.initialize():
        return None, "mt5.initialize() a echoue : %s" % (mt5.last_error(),)
    try:
        a = datetime.datetime.now() - datetime.timedelta(days=jours)
        b = datetime.datetime.now() + datetime.timedelta(days=1)
        deals = mt5.history_deals_get(a, b) or []
        entrees = {}
        sorties = {}
        for x in deals:
            if x.entry == 0:
                entrees[x.position_id] = x
            elif x.entry == 1:
                sorties[x.position_id] = sorties.get(x.position_id, 0.0) \
                    + float(x.profit)
        out = []
        for pid, x in entrees.items():
            if pid not in sorties:
                continue                      # position encore ouverte
            sens = 1 if x.type == 0 else -1   # 0 = BUY, 1 = SELL
            out.append((int(x.magic), str(x.symbol), int(x.time),
                        float(x.price), sens, sorties[pid]))
        return out, None
    finally:
        mt5.shutdown()


# ---------------------------------------------------------------- calage
def calage(S, ech, pas=1800, demi_bas=-24, demi_haut=29):
    """Decalage horaire et base future/CFD, ESSAYES et non supposes.

    On balaie les decalages par demi-heure et on retient celui qui rend
    l ecart (prix du compte - prix du future) le plus CONSTANT. Ce n est
    pas la valeur de l ecart qui designe le bon decalage, c est sa
    faible dispersion : une base stable veut dire que les deux series
    parlent du meme instant.
    """
    essais = []
    for demi in range(demi_bas, demi_haut):
        d = demi * pas
        ecarts = []
        for sec, pcompte in ech:
            py = S.prix_a(sec + d)
            if py is not None:
                ecarts.append(pcompte - py)
        if len(ecarts) < max(20, len(ech) // 20):
            continue
        essais.append((ecart_median(ecarts), d, len(ecarts), mediane(ecarts)))
    if not essais:
        return None
    essais.sort()
    return essais


def bloc_calage(S, ech, nom):
    print("")
    print("  calage %s -- %d entree(s) pour caler" % (nom, len(ech)))
    essais = calage(S, ech)
    if not essais:
        print("    aucun decalage ne fait coincider les deux series.")
        print("    Les periodes ne se recouvrent pas : ce fichier ne")
        print("    peut rien dire sur ces trades.")
        return None, None
    print("       decalage   apparies   base mediane   dispersion")
    print("       " + "-" * 56)
    for disp, d, n, med in essais[:5]:
        print("       %+6.1f h    %7d    %+10.1f    %10.2f"
              % (d / 3600.0, n, med, disp))
    disp, decalage, n, base_med = essais[0]
    print("    retenu %+.1f h, base %+.1f, dispersion %.2f"
          % (decalage / 3600.0, base_med, disp))
    if len(essais) > 1 and disp > 0 and essais[1][0] < disp * 1.3:
        print("    ATTENTION : le suivant est presque aussi bon (%.2f)."
              % essais[1][0])
        print("    Le calage n est pas franc ; tout ce qui suit en depend.")
    return decalage, base_med


# ---------------------------------------------------------------- sortie
def bloc_tableau(titre, lignes, mini, tirages, rng):
    print("")
    print("  %s" % titre)
    print("     case              trades      total     par trade")
    print("     " + "-" * 54)
    t = par_case(lignes)
    if not t:
        print("     aucun trade.")
        return
    for c in CASES:
        if c not in t:
            continue
        n, s, m = t[c]
        marque = "" if n >= mini else "   (moins de %d, ne conclut pas)" % mini
        print("     %-16s %7d %10.2f %12.2f%s" % (c, n, s, m, marque))
    print("     " + "-" * 54)
    tot = sum(s for _n, s, _m in t.values())
    nb = sum(_n for _n, s, _m in t.values())
    print("     %-16s %7d %10.2f %12.2f" % ("ensemble", nb, tot,
                                            tot / nb if nb else 0.0))
    vrai, aussi, sur = permutation(lignes, mini, tirages, rng)
    print("")
    if vrai is None:
        print("     Moins de deux cases atteignent %d trades : le test de"
              % mini)
        print("     permutation n a rien a comparer. On ne conclut pas.")
        return
    part = 100.0 * aussi / sur
    print("     ecart meilleure - pire : %.2f par trade" % vrai)
    print("     le hasard fait aussi bien %d fois sur %d, soit %.1f %%"
          % (aussi, sur, part))
    if part > 5.0:
        print("     -> NON CONCLUANT. Un ecart de cette taille sort tout")
        print("        seul du decoupage en cases. Filtrer la-dessus")
        print("        reviendrait a suivre du bruit.")
    else:
        print("     -> l ecart depasse ce que le hasard produit (%.1f %%)."
              % part)
        pire = min(((m, c) for c, (n, s, m) in par_case(lignes).items()
                    if n >= mini))
        gain = -sum(r for c, r in lignes if c == pire[1])
        print("        Case la plus faible : %s." % pire[1])
        print("        L ecarter aurait change le total de %+.2f." % gain)
        print("        A comparer au cout d execution avant d en faire")
        print("        une regle.")


def bloc_contreflux(lignes, mini, rng, tirages):
    """Entrer CONTRE le flux dominant : cela coute-t-il vraiment ?"""
    print("")
    print("  ENTREES DANS LE SENS DU FLUX, ET CONTRE")
    print("     sens              trades      total     par trade")
    print("     " + "-" * 54)
    t = par_case(lignes)
    for c in ("AVEC", "CONTRE", "SANS FLUX"):
        if c not in t:
            continue
        n, s, m = t[c]
        marque = "" if n >= mini else "   (moins de %d)" % mini
        print("     %-16s %7d %10.2f %12.2f%s" % (c, n, s, m, marque))
    print("     " + "-" * 54)
    vrai, aussi, sur = permutation(lignes, mini, tirages, rng)
    if vrai is None:
        print("     Effectifs insuffisants pour trancher.")
        return
    part = 100.0 * aussi / sur
    print("     ecart %.2f par trade ; le hasard fait aussi bien %.1f %%"
          % (vrai, part))
    if part > 5.0:
        print("     -> NON CONCLUANT.")


def bloc_mou(lignes_mou, tirages, rng):
    """AVEC et SANS les entrees molles -- la question posee directement.

    Coupure binaire, plus puissante que le tableau a quatre cases : tout
    l effectif sert a un seul contraste au lieu d etre divise en quatre.
    """
    print("")
    print(SEP)
    print("AVEC ET SANS LES ENTREES MOLLES")
    print(SEP)
    print("")
    print("  MOU est defini ICI comme : flux d intensite ET de nettete")
    print("  toutes deux sous leur mediane, sur la fenetre qui PRECEDE")
    print("  l entree. Le marche ne pousse ni dans un sens ni dans")
    print("  l autre, et pas fort.")
    print("")
    print("  Ce n est PAS l etiquette MOU du panneau 8097. Celle-la vient")
    print("  de la barre Ninja qui CONTIENT l entree, laquelle se ferme")
    print("  APRES -- elle n etait pas lisible au moment de decider, et")
    print("  filtrer dessus serait de la voyance. Ici tout est mesure")
    print("  avant l entree, donc reellement applicable.")
    print("")
    mous = [r for c, r in lignes_mou if c == "MOU"]
    reste = [r for c, r in lignes_mou if c != "MOU"]
    tout = mous + reste
    if not tout:
        print("  aucun trade.")
        return
    print("     %-22s %7s %11s %12s" % ("", "trades", "total", "par trade"))
    print("     " + "-" * 56)
    for nom, v in (("tout", tout), ("dont MOU", mous),
                   ("sans les MOU", reste)):
        if not v:
            print("     %-22s %7d %11s %12s" % (nom, 0, "--", "--"))
            continue
        print("     %-22s %7d %11.2f %12.2f"
              % (nom, len(v), sum(v), sum(v) / len(v)))
    print("     " + "-" * 56)
    print("")
    if not mous or not reste:
        print("  Une des deux cases est vide : rien a comparer.")
        return
    gain = -sum(mous)
    print("  Ecarter les MOU aurait change le total de %+.2f." % gain)
    print("  (%d trades ecartes sur %d, soit %.0f %%)"
          % (len(mous), len(tout), 100.0 * len(mous) / len(tout)))
    if len(mous) < MINI_CASE or len(reste) < MINI_CASE:
        print("")
        print("  MAIS l un des deux groupes pese moins de %d trades."
              % MINI_CASE)
        print("  C est la limite que le panel s impose a lui-meme. On")
        print("  regarde le test de permutation, sans lui accorder plus")
        print("  de poids qu il n en a.")
    vrai, aussi, sur = permutation(lignes_mou, 1, tirages, rng)
    part = 100.0 * aussi / sur
    print("")
    print("  ecart MOU / reste : %.2f par trade" % vrai)
    print("  le hasard fait aussi bien %d fois sur %d, soit %.1f %%"
          % (aussi, sur, part))
    print("")
    if part > 5.0:
        print("  -> NON CONCLUANT. Rebattre les etiquettes au hasard")
        print("     produit un ecart de cette taille %.1f %% du temps." % part)
        print("     Sur ces donnees, un filtre anti-MOU construit sur le")
        print("     flux d avant l entree n aurait rien apporte de sur.")
    else:
        print("  -> l ecart depasse le hasard (%.1f %%)." % part)
        print("     Reste a le comparer au cout d execution : un filtre")
        print("     qui gagne moins que le spread aller-retour perd.")


# ---------------------------------------------------------------- main
def associe(symbole, chemins):
    s = symbole.upper()
    for clef, ch in chemins.items():
        if clef in s:
            return ch
    return None


def bloc_persistance(nom, trades, S, decalage, fenetre, retards):
    """Combien de temps l etat du flux reste-t-il valable ?

    CE TABLEAU DECIDE DU CAHIER DES CHARGES DU FLUX A ACHETER. Il dit
    a quel point l etat mesure il y a N secondes vaut encore
    maintenant. Si l accord tient a 60 s mais tombe au hasard a 300 s,
    alors un flux dont la latence depasse la minute ne sert a rien, et
    ce chiffre-la se negocie avec le fournisseur avant de signer.

    Si l accord est deja au niveau du hasard des les premieres
    secondes, aucun flux, si rapide soit-il, ne peut trier quoi que ce
    soit : l etat ne dure pas assez pour etre utilise.

    Un accord nettement SOUS le hasard est une alerte : a ce retard-la
    le flux ne dit pas rien, il dit le CONTRAIRE.
    """
    print("")
    print("  COMBIEN DE TEMPS L ETAT DU FLUX RESTE VALABLE -- %s" % nom)
    print("    Ce tableau dit quelle FRAICHEUR le flux doit avoir pour")
    print("    servir a quelque chose. C est le cahier des charges.")
    print("")
    ref = []
    for (magic, sym, sec, prix, sens, res) in trades:
        i = S.cherche(sec + decalage)
        if i is None or i < fenetre:
            continue
        f = S.fenetre(i - 1, fenetre)
        if f is None:
            continue
        ref.append((sec, traits(f)))
    if len(ref) < 20:
        print("    moins de 20 entrees exploitables : rien a dire.")
        return
    med_vol = mediane([t["volume"] for _s, t in ref])
    med_net = mediane([t["nettete"] for _s, t in ref])

    def mou(t):
        return t["volume"] <= med_vol and t["nettete"] <= med_net

    base = sum(1 for _s, t in ref if mou(t)) / float(len(ref))
    # Accord attendu si les deux etats sont independants.
    hasard = 100.0 * (base * base + (1 - base) * (1 - base))
    print("     retard    compares    accord    hasard")
    print("     " + "-" * 44)
    for r in retards:
        justes = total = 0
        for sec, t0 in ref:
            j = S.cherche(sec + decalage - r)
            if j is None or j < fenetre:
                continue
            g = S.fenetre(j - 1, fenetre)
            if g is None:
                continue
            total += 1
            if mou(traits(g)) == mou(t0):
                justes += 1
        if total < 20:
            print("     %6d s   %8d    trop peu" % (r, total))
            continue
        acc = 100.0 * justes / total
        print("     %6d s   %8d %8.1f %% %8.1f %%" % (r, total, acc, hasard))
    print("     " + "-" * 44)
    print("    Lire la premiere ligne ou  accord  rejoint  hasard  :")
    print("    au-dela de ce retard, le flux ne sait plus rien de")
    print("    l instant present. C est la latence maximale acceptable")
    print("    pour le flux qu on achete. Un accord NETTEMENT sous le")
    print("    hasard veut dire qu a ce retard il dit l inverse.")


def etudie(nom, trades, S, decalage, fenetre, tirages, rng, retard=0):
    """Un groupe de trades contre un fichier. Rend les lignes.

    retard : 0 par defaut, ce qui simule le flux LIVE dont il s agit de
    decider l achat -- la fenetre se termine a l instant de l entree, et
    jamais une seconde apres. Une valeur non nulle simule un flux qui
    arrive en retard, comme celui de Sierra ; l ecart entre les deux
    chiffre ce que vaut la fraicheur.
    """
    q4, qmou, qflux = [], [], []
    tr = []
    gardes = []
    for rang, (magic, sym, sec, prix, sens, res) in enumerate(trades):
        i = S.cherche(sec + decalage - retard)
        if i is None or i < fenetre:
            continue
        f = S.fenetre(i - 1, fenetre)      # i-1 : rien de l instant meme
        if f is None:
            continue
        tr.append((traits(f), sens, res))
        gardes.append(rang)
    if not tr:
        print("")
        print("  %s : aucune entree n a de fenetre exploitable." % nom)
        print("  Le fichier ne couvre probablement pas ces dates.")
        return None, []
    med_vol = mediane([t["volume"] for t, _s, _r in tr])
    med_net = mediane([t["nettete"] for t, _s, _r in tr])
    print("")
    print("  %s : %d entree(s) appariees a une fenetre de %d ticks"
          % (nom, len(tr), fenetre))
    if retard:
        print("    fenetre arretee %d s avant l entree (flux retarde)"
              % retard)
    else:
        print("    fenetre arretee A l instant de l entree (flux live)")
    print("    medianes de coupure -- volume %.0f, nettete %.3f"
          % (med_vol, med_net))
    for t, sens, res in tr:
        q4.append((range_case(t, med_vol, med_net), res))
        mou = (t["volume"] <= med_vol and t["nettete"] <= med_net)
        qmou.append(("MOU" if mou else "AUTRE", res))
        if t["sens"] == 0:
            qflux.append(("SANS FLUX", res))
        elif t["sens"] == sens:
            qflux.append(("AVEC", res))
        else:
            qflux.append(("CONTRE", res))
    if len(tr) < len(trades):
        print("    %d entree(s) ecartee(s) : pas assez de ticks avant."
              % (len(trades) - len(tr)))
    bloc_tableau("LES QUATRE CASES -- %s" % nom, q4, MINI_CASE, tirages, rng)
    bloc_contreflux(qflux, MINI_CASE, rng, tirages)
    return qmou, gardes


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ym", default=r"C:\SierraChart\Data\YMU26-CBOT.scid")
    p.add_argument("--mes", default=r"C:\SierraChart\Data\MESU26-CME.scid")
    p.add_argument("--jours", type=int, default=10)
    p.add_argument("--fenetre", type=int, default=300,
                   help="ticks lus AVANT chaque entree ; trop large, elle "
                        "chevauche plusieurs regimes et les melange -- au "
                        "banc, 5000 ticks font tomber l accord de 100 a 75 "
                        "pour cent")
    p.add_argument("--retard", type=int, default=0,
                   help="secondes de retard du flux. 0 = le flux LIVE "
                        "qu on envisage d acheter, c est le cas a "
                        "evaluer. 600 = le flux Sierra tel qu on l a eu, "
                        "utile seulement pour la comparaison.")
    p.add_argument("--tirages", type=int, default=400)
    p.add_argument("--graine", type=int, default=11)
    p.add_argument("--banc", action="store_true")
    p.add_argument("--banc-lien", type=float, default=0.0,
                   help="0 = aucun lien flux/resultat, 1 = lien franc")
    p.add_argument("--banc-fichier", default="")
    a = p.parse_args()
    rng = random.Random(a.graine)

    print(SEP)
    print("LES ENTREES 220/230/240 CONTRE LE FLUX D AVANT L ENTREE")
    print(SEP)
    print("")
    print("  Lecture seule. Aucun ordre, aucune ecriture.")
    print("")
    if a.retard <= 0:
        print("  RETARD 0 : on simule le flux LIVE qu il s agit d acheter.")
        print("  La fenetre se termine a l instant de l entree, jamais")
        print("  apres -- un flux live donne l etat du moment, pas celui")
        print("  d apres. La question est donc : ce flux-la, achete,")
        print("  aurait-il trie les entrees 220/230/240 ?")
    else:
        print("  RETARD %d s : on simule un flux qui arrive en retard," % a.retard)
        print("  comme celui de Sierra. A comparer au meme calcul avec")
        print("  --retard 0 : l ecart entre les deux EST la valeur de la")
        print("  fraicheur du flux.")

    if a.banc:
        return banc(a, rng)

    trades, err = lit_positions(a.jours)
    if trades is None:
        print("")
        print("  %s" % err)
        return 1
    miroirs = [t for t in trades
               if MIROIR_BAS <= t[0] < MIROIR_HAUT]
    parents = [t for t in trades
               if not (MIROIR_BAS <= t[0] < MIROIR_HAUT)]
    print("")
    print("  %d position(s) close(s) sur %d jours : %d miroir(s), %d parent(s)"
          % (len(trades), a.jours, len(miroirs), len(parents)))
    if not miroirs:
        print("")
        print("  Aucun trade de magic %d a %d sur la periode."
              % (MIROIR_BAS, MIROIR_HAUT - 1))
        print("  Rien a croiser. Elargis --jours.")
        return 1

    chemins = {}
    for clef, ch in (("US30", a.ym), ("DOW", a.ym), ("YM", a.ym),
                     ("US500", a.mes), ("SPX", a.mes), ("ES", a.mes)):
        if os.path.isfile(ch):
            chemins[clef] = ch
    symboles = sorted(set(t[1] for t in miroirs))
    print("  symboles miroirs : %s" % ", ".join(symboles))

    tous_mou = []
    for ch in sorted(set(chemins.values())):
        S = Scid(ch)
        if S.err:
            print("")
            print("  %s : %s" % (os.path.basename(ch), S.err))
            continue
        concernes = [t for t in trades if associe(t[1], chemins) == ch]
        mir = [t for t in concernes if MIROIR_BAS <= t[0] < MIROIR_HAUT]
        par = [t for t in concernes if not (MIROIR_BAS <= t[0] < MIROIR_HAUT)]
        print("")
        print(SEP)
        print("%s -- %d miroir(s), %d parent(s)" % (S.nom, len(mir), len(par)))
        print(SEP)
        if not mir and not par:
            S.ferme()
            continue
        # Le calage se fait sur TOUS les trades de l actif : plus il y a
        # de points, plus le decalage retenu est sur.
        ech = [(t[2], t[3]) for t in concernes]
        decalage, _base = bloc_calage(S, ech, S.nom)
        if decalage is None:
            S.ferme()
            continue
        bloc_persistance(S.nom, concernes, S, decalage, a.fenetre,
                         (60, 120, 300, 600, 900, 1800))
        if par:
            etudie("PARENTS", par, S, decalage, a.fenetre, a.tirages, rng,
                   retard=a.retard)
        m, _g = etudie("MIROIRS 220/230/240", mir, S, decalage, a.fenetre,
                       a.tirages, rng, retard=a.retard)
        if m:
            tous_mou.extend(m)
        S.ferme()

    if tous_mou:
        bloc_mou(tous_mou, a.tirages, rng)
    print("")
    print(SEP)
    print(" Lecture seule. Aucun ordre envoye, aucun fichier ecrit.")
    print(SEP)
    return 0


# ---------------------------------------------------------------- banc
def ecrit_scid_banc(chemin, ticks):
    h = bytearray(EN_TETE)
    h[0:4] = b"SCID"
    struct.pack_into("<II", h, 4, EN_TETE, ENREG)
    f = open(chemin, "wb")
    f.write(bytes(h))
    for (sec, prix, vol, bv, av) in ticks:
        us = int((datetime.datetime(1970, 1, 1)
                  + datetime.timedelta(seconds=sec) - ORIGINE)
                 .total_seconds() * 1000000)
        f.write(struct.pack("<q4f4I", us, prix, prix, prix, prix,
                            1, vol, bv, av))
    f.close()
    return os.path.getsize(chemin)


def banc(a, rng):
    """Le script se verifie sur des donnees dont on connait la reponse.

    Deux cas obligatoires :
      --banc-lien 0  aucun lien entre flux et resultat. Le verdict DOIT
                     etre  non concluant . S il trouve une regle, c est
                     le script qui la fabrique.
      --banc-lien 1  les entrees prises dans un flux mou perdent pour de
                     bon. Le verdict DOIT le voir.
    """
    import tempfile
    dossier = a.banc_fichier or tempfile.gettempdir()
    chemin = os.path.join(dossier, "BANC_croise_flux.scid")
    print("")
    print("  MODE BANC -- ce mode ECRIT une fixture, une seule :")
    print("  %s" % chemin)
    print("  Le mode normal, lui, n ecrit rien.")

    r = random.Random(2026)
    t0 = int((datetime.datetime(2026, 8, 17, 8, 0, 0)
              - datetime.datetime(1970, 1, 1)).total_seconds())
    ticks = []
    regimes = []                      # (debut, fin, mou ?)
    sec = t0
    prix = 44000.0
    for bloc in range(120):
        mou = (bloc % 2 == 0)
        pousse = 1 if r.random() < 0.5 else -1
        d0 = len(ticks)
        for _k in range(400):
            if mou:
                prix += r.choice((-1.0, 0.0, 0.0, 1.0)) * 0.5
                v = r.randint(1, 4)
                bv = r.randint(0, v)          # equilibre
            else:
                # Un vrai flux qui pousse garde son sens PENDANT le bloc.
                # Le faire changer a chaque tick annulerait le delta
                # cumule, et la nettete ne separerait plus rien : le banc
                # mesurerait alors sa propre fixture, pas le script.
                prix += (1.0 if pousse > 0 else -1.0) * r.choice((0.0, 1.5))
                v = r.randint(20, 60)
                bv = int(v * (0.12 if pousse > 0 else 0.88))
            ticks.append((sec, prix, v, bv, v - bv))
            sec += 2
        regimes.append((d0, len(ticks) - 1, mou))
    n = ecrit_scid_banc(chemin, ticks)
    print("  fixture : %d ticks, %d octets" % (len(ticks), n))

    S = Scid(chemin)
    if S.err:
        print("  ECHEC : %s" % S.err)
        return 1

    # Un trade au milieu de chaque bloc, prix pris DANS le .scid pour que
    # le calage doive retrouver exactement 0 h et 0 point de base.
    trades = []
    verite = []
    for (d0, d1, mou) in regimes:
        i = (d0 + d1) // 2
        s = ticks[i][0]
        px = ticks[i][1]
        sens = 1 if r.random() < 0.5 else -1
        if a.banc_lien >= 1.0:
            res = (-10.0 if mou else +10.0) + r.gauss(0, 3)
        else:
            res = r.gauss(0, 8)
        trades.append((220001, "BANC", s, px, sens, res))
        verite.append(mou)
    print("  %d trades fabriques, dont %d en regime mou"
          % (len(trades), sum(1 for x in verite if x)))
    print("  lien flux/resultat demande : %.0f" % a.banc_lien)

    print("")
    print(SEP)
    print("BANC -- CALAGE (doit retrouver 0.0 h et base 0.0)")
    print(SEP)
    ech = [(t[2], t[3]) for t in trades]
    decalage, base = bloc_calage(S, ech, S.nom)
    if decalage is None:
        print("  ECHEC : le calage n a rien trouve.")
        return 1
    if decalage != 0:
        print("  ECHEC : decalage %+.1f h au lieu de 0." % (decalage / 3600.0))
    else:
        print("  OK : decalage 0 h retrouve.")

    print("")
    print(SEP)
    print("BANC -- LES TABLEAUX")
    print(SEP)
    bloc_persistance("BANC", trades, S, decalage, a.fenetre,
                     (60, 120, 300, 600, 900, 1800))
    m, gardes = etudie("BANC", trades, S, decalage, a.fenetre, a.tirages,
                       rng, retard=a.retard)
    if m:
        bloc_mou(m, a.tirages, rng)
        print("")
        print("  Cases MOU reperees par le script : %d sur %d trades"
              % (sum(1 for c, _r in m if c == "MOU"), len(m)))
        print("  Regimes mous reellement plantes  : %d"
              % sum(1 for x in verite if x))
        justes = sum(1 for (c, _r), rang in zip(m, gardes)
                     if (c == "MOU") == verite[rang])
        print("  Accord case/regime : %d sur %d  (%.0f %%)"
              % (justes, len(gardes), 100.0 * justes / len(gardes)))
        if justes < 0.8 * len(gardes):
            print("  ATTENTION : moins de 80 pour cent d accord. La")
            print("  definition de MOU ne retrouve pas le regime plante.")
    S.ferme()
    return 0


if __name__ == "__main__":
    sys.exit(main())
