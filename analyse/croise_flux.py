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

LA CLASSIFICATION EST LA VOTRE, PAS UNE INVENTION

    Les bandes sont recopiees a l identique de orderflow_join.py
    (lignes 43-52), avec leurs bornes d origine :

        CARNAGE  0,00 - 0,20      CORRECT  0,40 - 0,60
        MOU      0,20 - 0,40      PROPRE   0,60 - 1,01

    L Efficiency Ratio se recalcule depuis les ticks : deplacement NET
    divise par chemin PARCOURU sur la barre M1. Mais le chemin depend
    de la resolution -- compte tick par tick il est plus long qu a la
    seconde, et l ER sort plus bas.

    Le script ne suppose donc pas qu il calcule le meme ER que vous :
    il le VERIFIE. Il relit les _er reellement enregistres dans les
    tickets, recalcule l ER sur la meme barre a plusieurs pas
    d echantillonnage, et affiche l ecart median et le pourcentage de
    bandes identiques. Si rien ne colle, il l ecrit noir sur blanc au
    lieu de continuer comme si de rien n etait.

DEUX LECTURES COTE A COTE

    live    la barre M1 se termine a l instant de l entree. C est ce
            qu un flux orderflow LIVE donnerait -- le cas a evaluer.

    ninja   la barre M1 close AVANT celle qui contient l entree, soit
            exactement _er_band_prec. C est ce que la chaine actuelle
            sait deja produire.

    L ecart entre les deux chiffre ce que la fraicheur apporte.

LE PIEGE PRINCIPAL, ET LE TEST QUI LE DESAMORCE

    185 trades ranges en 4 bandes font 46 par bande. L ecart entre la
    meilleure et la pire sera GROS par hasard seul -- c est
    arithmetique, pas de la malchance. Chercher la meilleure bande dans
    un tableau et la declarer regle est la facon la plus courante de
    fabriquer une regle qui ne survit pas au mois suivant.

    Le script fait donc systematiquement un test de permutation : il
    rebat les etiquettes de case entre les trades, sans toucher aux
    resultats, quelques centaines de fois, et regarde combien de fois le
    hasard produit un ecart aussi grand. C est ce pourcentage qui decide,
    jamais le tableau seul.

    Il applique aussi la regle que le panel s impose a lui-meme : sous
    30 trades, une bande ne conclut pas. Et la colonne  sans elle
    donne, pour chaque bande, ce que le total serait devenu si on
    l avait ecartee -- le decompte demande, sans avoir a le refaire
    a la main.

    Lecture seule. Aucun ordre, aucune ecriture.
"""
import argparse
import datetime
import io
import json
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
BAR_SEC = 60

# A gauche le fichier .scid, a droite les noms d actifs tels qu ils sont
# ecrits DANS LE JSONL -- qui ne sont pas ceux du courtier. Le compte dit
# SPX500, le jsonl dit US500 : c est ce decalage qui avait fait rendre
# zero ticket a la verification.
ACTIFS_JSONL = {
    "ym": ("US30", "DOW", "YM"),
    "mes": ("US500", "SPX500", "SPX", "ES", "MES"),
}

# Recopie a l identique de orderflow_join.py, lignes 43 a 52. Ces bornes
# ne sont pas negociables ici : c est la classification du panneau 8097,
# et en changer une seule rendrait tout incomparable avec le gel V9.
ER_BANDS = (
    ("CARNAGE",   0.00, 0.20),
    ("MOU",       0.20, 0.40),
    ("CORRECT",   0.40, 0.60),
    ("PROPRE",    0.60, 1.01),
)
CASES = tuple(b[0] for b in ER_BANDS)


def er_band(er):
    """Identique a orderflow_join.er_band."""
    if er is None:
        return "?"
    for name, lo, hi in ER_BANDS:
        if lo <= er < hi:
            return name
    return "?"


def efficiency(prix):
    """Efficiency Ratio : deplacement NET sur chemin PARCOURU.

    1 = le prix est alle droit au but ; 0 = il a fait le meme chemin
    pour revenir au point de depart.

    Le chemin depend de la resolution a laquelle on le mesure : compte
    tick par tick, il est plus long qu echantillonne a la seconde, donc
    l ER sort plus bas. C est pourquoi --pas existe et pourquoi le
    script VERIFIE sa reconstruction contre les _er reellement
    enregistres au lieu de la supposer juste.
    """
    if len(prix) < 2:
        return None
    net = abs(prix[-1] - prix[0])
    chemin = 0.0
    for i in range(1, len(prix)):
        chemin += abs(prix[i] - prix[i - 1])
    if chemin <= 0:
        return None
    return net / chemin


def sous_echantillon(temps, prix, pas):
    """Dernier prix de chaque tranche de  pas  secondes."""
    if pas <= 0:
        return list(prix)
    out = []
    courant = None
    dernier = None
    for t, p in zip(temps, prix):
        tranche = t // pas
        if courant is None:
            courant = tranche
        elif tranche != courant:
            out.append(dernier)
            courant = tranche
        dernier = p
    if dernier is not None:
        out.append(dernier)
    return out


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

    def entre(self, t0, t1, plafond=20000):
        """(temps, prix, volume, bid, ask) des ticks dans [t0, t1).

        Sert a refaire une barre M1 exactement comme Ninja la decoupe,
        par le TEMPS et non par un nombre de ticks : une minute calme et
        une minute de panique n ont pas le meme nombre de ticks, et
        decouper au compte melangerait les deux.
        """
        if t1 <= t0:
            return None
        i1 = self.cherche(t1 - 1)
        if i1 is None:
            return None
        i0 = self.cherche(t0 - 1)
        i0 = 0 if i0 is None else i0 + 1
        combien = i1 - i0 + 1
        if combien <= 0:
            return None
        if combien > plafond:
            i0 = i1 - plafond + 1
            combien = plafond
        self.f.seek(self.te + i0 * self.tr)
        brut = self.f.read(combien * self.tr)
        util = brut[:len(brut) - len(brut) % self.tr]
        tt, pr, vo, bi, ak = [], [], [], [], []
        for m in struct.iter_unpack(FMT, util):
            if self.mode == "micro":
                tt.append(self.base + m[0] // 1000000)
            else:
                (j,) = struct.unpack("<d", struct.pack("<q", m[0]))
                tt.append(self.base + int(j * 86400))
            pr.append(m[4])
            vo.append(m[6])
            bi.append(m[7])
            ak.append(m[8])
        return tt, pr, vo, bi, ak

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


# ------------------------------------------------------------ la mesure
def mesure(S, t_fin, duree, pas):
    """ER et delta de la fenetre [t_fin - duree, t_fin)."""
    d = S.entre(t_fin - duree, t_fin)
    if d is None:
        return None
    tt, pr, vo, bi, ak = d
    if len(pr) < 3:
        return None
    er = efficiency(sous_echantillon(tt, pr, pas))
    if er is None:
        return None
    v = float(sum(vo))
    dd = float(sum(ak) - sum(bi))
    return {
        "er": er,
        "bande": er_band(er),
        "volume": v,
        "delta": dd,
        "sens": 1 if dd > 0 else (-1 if dd < 0 else 0),
        "ticks": len(pr),
    }


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
    """AVEC et SANS la bande MOU -- la question posee directement.

    Coupure binaire, plus puissante que le tableau a quatre bandes :
    tout l effectif sert a un seul contraste au lieu d etre divise en
    quatre. C est la forme la plus favorable que puisse prendre ce
    test ; s il ne passe pas ici, il ne passera nulle part.
    """
    print("")
    print(SEP)
    print("AVEC ET SANS LA BANDE MOU")
    print(SEP)
    print("")
    print("  MOU = Efficiency Ratio entre 0,20 et 0,40, bornes de")
    print("  orderflow_join.py. Meme definition que le panneau 8097.")
    print("")
    print("  Une seule difference, et elle est decisive : la barre est")
    print("  celle qui se termine A l entree, pas celle qui la CONTIENT.")
    print("  Celle qui contient l entree se ferme apres, son ER n existe")
    print("  pas encore au moment de decider -- c est le defaut releve")
    print("  le 13/08. Ici tout est lisible avant d entrer, donc ce qui")
    print("  suit est reellement applicable.")
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
        print("     Sur ces donnees, un filtre anti-MOU lisible AVANT")
        print("     l entree n aurait rien apporte de sur.")
    else:
        print("  -> l ecart depasse le hasard (%.1f %%)." % part)
        print("     Reste a le comparer au cout d execution : un filtre")
        print("     qui gagne moins que le spread aller-retour perd.")


# ---------------------------------------------------------------- main
def chemins_tickets(force):
    if force:
        return [force]
    d = "docs"
    return [os.path.join(d, "rails_trades", "tickets_rails.jsonl"),
            os.path.join(d, "churn_trades", "tickets_churn.jsonl"),
            os.path.join(d, "churn_trades", "tickets.jsonl"),
            os.path.join(d, "tickets_rails.jsonl"),
            os.path.join(d, "tickets.jsonl")]


def associe(symbole, chemins):
    s = symbole.upper()
    for clef, ch in chemins.items():
        if clef in s:
            return ch
    return None


def lit_tickets(chemins, actifs=None, plafond=40000):
    """Les tickets qui portent un _er enregistre.

    Rend aussi un DIAGNOSTIC : quand il n y a rien, il faut savoir si
    c est le fichier qui manque, le champ _er qui manque, ou le nom
    d actif qui ne correspond pas. Un zero sans explication ferait
    conclure  pas de donnees  alors que c est peut-etre  mauvais nom .

    actifs : les noms tels qu ils sont ECRITS DANS LE JSONL, qui ne
    sont pas ceux du courtier -- le compte dit SPX500, le jsonl dit
    US500. C est ce decalage qui a fait rendre zero au premier essai.
    """
    out = []
    diag = {"fichiers": [], "lignes": 0, "avec_er": 0, "actifs_vus": {}}
    for c in chemins:
        for cc in (c, c + ".gz"):
            if not os.path.isfile(cc):
                continue
            diag["fichiers"].append(cc)
            try:
                if cc.endswith(".gz"):
                    import gzip
                    f = io.TextIOWrapper(gzip.open(cc, "rb"),
                                         encoding="utf-8", errors="replace")
                else:
                    f = io.open(cc, encoding="utf-8", errors="replace")
            except Exception:
                continue
            with f:
                for l in f:
                    l = l.strip()
                    if not l:
                        continue
                    try:
                        o = json.loads(l)
                    except ValueError:
                        continue
                    if not isinstance(o, dict):
                        continue
                    diag["lignes"] += 1
                    act = o.get("asset")
                    diag["actifs_vus"][act] = \
                        diag["actifs_vus"].get(act, 0) + 1
                    er = o.get("_er")
                    if er is not None:
                        diag["avec_er"] += 1
                    if actifs and act not in actifs:
                        continue
                    ts = o.get("entry_ts")
                    if er is None or not isinstance(ts, str) or len(ts) < 19:
                        continue
                    try:
                        d = datetime.datetime.strptime(ts[:19],
                                                       "%Y-%m-%d %H:%M:%S")
                        sec = int((d - datetime.datetime(1970, 1, 1))
                                  .total_seconds())
                    except (ValueError, TypeError):
                        continue
                    out.append((sec, float(er), o.get("_er_band"), act))
                    if len(out) >= plafond:
                        return out, diag
    return out, diag


def bloc_calibrage(S, tickets, diag, decalage, duree, pas_essais):
    """Mon ER est-il LE MEME que celui qui a ete enregistre ?

    Sans cette verification, mes bandes pourraient etre decalees d un
    cran sans que rien ne le signale, et tout le decompte serait faux
    en silence. On recalcule l ER sur la MEME barre -- celle qui
    contient l entree, comme orderflow_join -- et on compare.

    Le chemin parcouru depend de la resolution : on essaie plusieurs
    pas d echantillonnage et on retient celui qui colle. Si aucun ne
    colle, le script le DIT au lieu de continuer.
    """
    print("")
    print("  MON ER CONTRE L ER ENREGISTRE -- verification")
    if not tickets:
        print("    aucun ticket utilisable. POURQUOI :")
        if not diag or not diag["fichiers"]:
            print("      aucun fichier trouve. Cherches :")
            for c in (diag or {}).get("essayes", []):
                print("        %s" % c)
            print("      -> donne le bon chemin avec --tickets")
        else:
            print("      fichier(s) lu(s) : %s"
                  % ", ".join(diag["fichiers"]))
            print("      %d ligne(s), dont %d avec un champ _er"
                  % (diag["lignes"], diag["avec_er"]))
            if diag["avec_er"] == 0:
                print("      -> le champ _er n existe pas dans ces")
                print("         tickets. Rien a verifier ici.")
            else:
                vus = sorted(diag["actifs_vus"].items(),
                             key=lambda kv: -kv[1])[:8]
                print("      actifs presents : %s"
                      % ", ".join("%s (%d)" % (a, n) for a, n in vus))
                print("      -> aucun ne correspond a ceux attendus pour")
                print("         ce fichier .scid.")
        print("")
        print("    Les bandes qui suivent restent une RECONSTRUCTION non")
        print("    verifiee. Sur US500 en particulier, le pas de cotation")
        print("    plus fin et la densite de ticks poussent l ER vers le")
        print("    bas : la repartition observee (beaucoup de CARNAGE,")
        print("    presque pas de PROPRE) en porte la trace.")
        return None
    print("    %d ticket(s) portant un _er" % len(tickets))
    print("")
    print("       pas    compares   ecart median   meme bande")
    print("       " + "-" * 50)
    meilleur = None
    for pas in pas_essais:
        ecarts, memes, n = [], 0, 0
        for sec, er_vrai, band_vrai, _a in tickets:
            debut = ((sec + decalage) // duree) * duree
            m = mesure(S, debut + duree, duree, pas)
            if m is None:
                continue
            n += 1
            ecarts.append(abs(m["er"] - er_vrai))
            if band_vrai and m["bande"] == band_vrai:
                memes += 1
        if n < 20:
            print("       %4d s %10d    trop peu" % (pas, n))
            continue
        med = mediane(ecarts)
        acc = 100.0 * memes / n
        print("       %4d s %10d %14.3f %10.1f %%" % (pas, n, med, acc))
        if meilleur is None or med < meilleur[1]:
            meilleur = (pas, med, acc, n)
    print("       " + "-" * 50)
    if meilleur is None:
        print("    aucun pas ne donne assez de comparaisons.")
        return None
    pas, med, acc, n = meilleur
    print("    meilleur pas : %d s, ecart median %.3f, %.1f %% de bandes"
          % (pas, med, acc))
    print("    identiques sur %d tickets." % n)
    if med > 0.10 or acc < 60.0:
        print("")
        print("    ATTENTION : la reconstruction ne colle PAS. L ER que")
        print("    je calcule depuis les ticks n est pas celui qui a ete")
        print("    enregistre -- formule ou source differente. Le")
        print("    decompte qui suit porte sur MON ER, pas sur le votre.")
    else:
        print("    -> reconstruction validee : relance avec --pas %d." % pas)
    return pas


def bloc_hors_echantillon(nom, trois, tirages, rng):
    """La regle apprise sur une moitie, appliquee telle quelle sur l autre.

    C EST LE SEUL TEST QUI DISTINGUE UNE REGLE D UNE COINCIDENCE.

    Tous les tableaux precedents cherchent la meilleure decoupe DANS les
    donnees puis la jugent SUR les memes donnees. Avec quatre bandes et
    quelques centaines de trades, on trouve toujours quelque chose. Le
    test de permutation limite les degats mais ne les annule pas : il
    dit si l ecart est gros, pas s il se reproduira.

    Ici on coupe la periode en deux. Sur la premiere moitie on regarde
    quelles bandes perdent -- c est TOUT ce qu on a le droit de
    regarder. Puis on ecarte ces bandes-la sur la seconde moitie, sans
    rien reajuster, et on compte. Si le gain disparait, la regle etait
    un ajustement au passe.

    On fait ensuite l inverse (apprendre sur la seconde, appliquer sur
    la premiere) : une regle qui tient dans un sens et pas dans l autre
    n en est pas une.

    Le temoin : on tire au hasard un ensemble de bandes de meme taille
    et on regarde combien de fois il fait aussi bien. Ecarter des
    trades au hasard change deja le total ; c est ce changement-la
    qu il faut battre, pas zero.
    """
    print("")
    print(SEP)
    print("HORS ECHANTILLON -- %s" % nom)
    print(SEP)
    if len(trois) < 60:
        print("")
        print("  %d trades : trop peu pour couper en deux moities" % len(trois))
        print("  qui veuillent dire quelque chose. On ne conclut pas.")
        return
    ordre = sorted(trois, key=lambda x: x[2])
    coupe = len(ordre) // 2
    moities = (("premiere -> seconde", ordre[:coupe], ordre[coupe:]),
               ("seconde -> premiere", ordre[coupe:], ordre[:coupe]))
    print("")
    print("  %d trades, coupes en %d et %d."
          % (len(ordre), coupe, len(ordre) - coupe))
    print("  Bornes : %s | %s | %s"
          % (quand_jour(ordre[0][2]), quand_jour(ordre[coupe][2]),
             quand_jour(ordre[-1][2])))
    for titre, apprend, applique in moities:
        print("")
        print("  --- %s ---" % titre)
        t = par_case([(b, r) for b, r, _s in apprend])
        perdantes = sorted(b for b, (n, sv, m) in t.items()
                           if m < 0 and n >= 10)
        if not perdantes:
            print("      aucune bande ne perd sur la moitie d apprentissage.")
            print("      Il n y a donc rien a ecarter, et rien a tester.")
            continue
        print("      bandes perdantes apprises : %s" % ", ".join(perdantes))
        for b in perdantes:
            n, sv, m = t[b]
            print("        %-10s %4d trades, %+8.2f par trade" % (b, n, m))
        tot = sum(r for _b, r, _s in applique)
        garde = [r for b, r, _s in applique if b not in perdantes]
        ecartes = len(applique) - len(garde)
        if not garde:
            print("      la regle ecarte TOUT sur l autre moitie.")
            continue
        neuf = sum(garde)
        gain = neuf - tot
        print("")
        print("      applique a l autre moitie (%d trades) :" % len(applique))
        print("        sans regle       %+9.2f" % tot)
        print("        avec la regle    %+9.2f   (%d ecartes, %.0f %%)"
              % (neuf, ecartes, 100.0 * ecartes / len(applique)))
        print("        gain             %+9.2f" % gain)
        # PREMIERE condition, et elle passe avant toute statistique :
        # la regle doit battre le fait de NE RIEN FILTRER. Sans ce
        # garde-fou, une regle qui ecarte 52 trades sur 60 laisse une
        # poignee de survivants dont la somme est difficile a egaler au
        # hasard -- et le test la declare bonne alors qu elle a fait
        # PERDRE. Le banc a produit exactement ce cas.
        if gain <= 0:
            print("        -> NE TIENT PAS : la regle fait PERDRE")
            print("           %+.2f par rapport a ne rien filtrer." % gain)
            continue
        if ecartes > 0.6 * len(applique):
            print("        ATTENTION : elle ecarte %.0f %% des trades."
                  % (100.0 * ecartes / len(applique)))
            print("        Ce n est plus un filtre, c est une abstention.")
        # SECONDE condition : battre un ecartement au hasard de meme
        # taille. Retirer des trades change deja le total ; c est ce
        # changement-la qu il faut depasser, pas zero.
        res = [r for _b, r, _s in applique]
        mieux = 0
        for _k in range(tirages):
            ech = res[:]
            rng.shuffle(ech)
            if sum(ech[ecartes:]) >= neuf:
                mieux += 1
        part = 100.0 * mieux / tirages
        print("        ecarter %d trades AU HASARD fait aussi bien"
              % ecartes)
        print("        %d fois sur %d, soit %.1f %%" % (mieux, tirages, part))
        if part > 5.0:
            print("        -> NE TIENT PAS hors echantillon.")
        else:
            print("        -> TIENT hors echantillon.")


def quand_jour(sec):
    """utcfromtimestamp est deprecie depuis 3.12 et inonde la sortie."""
    return datetime.datetime.fromtimestamp(
        sec, datetime.timezone.utc).strftime("%d/%m")


def bloc_persistance(nom, trades, S, decalage, duree, pas, retards):
    """Combien de temps la bande ER reste-t-elle la meme ?

    CE TABLEAU EST LE CAHIER DES CHARGES DU FLUX A ACHETER. Il dit si
    la bande mesuree il y a N secondes vaut encore a l instant ou l on
    decide. Si l accord rejoint le hasard des 60 s, aucun fournisseur,
    si rapide soit-il, ne vend quelque chose d utilisable.

    Le  hasard  n est pas 25 pour cent : les quatre bandes ne sont pas
    egalement peuplees. Il vaut la somme des carres de leurs parts,
    c est-a-dire la chance de tomber deux fois sur la meme bande en
    tirant au sort.
    """
    print("")
    print("  COMBIEN DE TEMPS LA BANDE ER RESTE LA MEME -- %s" % nom)
    print("    C est la fraicheur minimale a exiger du flux.")
    print("")
    ref = []
    for (magic, sym, sec, prix, sens, res) in trades:
        m = mesure(S, sec + decalage, duree, pas)
        if m is not None:
            ref.append((sec, m["bande"]))
    if len(ref) < 20:
        print("    moins de 20 entrees exploitables : rien a dire.")
        return
    comptes = {}
    for _s, b in ref:
        comptes[b] = comptes.get(b, 0) + 1
    n = float(len(ref))
    hasard = 100.0 * sum((c / n) ** 2 for c in comptes.values())
    print("    repartition : %s"
          % "  ".join("%s %.0f%%" % (b, 100.0 * comptes[b] / n)
                      for b in list(CASES) + [k for k in sorted(comptes)
                                              if k not in CASES]
                      if b in comptes))
    print("")
    print("     retard    compares    accord    hasard")
    print("     " + "-" * 44)
    for r in retards:
        justes = total = 0
        for sec, b0 in ref:
            m = mesure(S, sec + decalage - r, duree, pas)
            if m is None:
                continue
            total += 1
            if m["bande"] == b0:
                justes += 1
        if total < 20:
            print("     %6d s   %8d    trop peu" % (r, total))
            continue
        print("     %6d s   %8d %8.1f %% %8.1f %%"
              % (r, total, 100.0 * justes / total, hasard))
    print("     " + "-" * 44)
    print("    La premiere ligne ou  accord  rejoint  hasard  donne la")
    print("    latence maximale acceptable. Un accord NETTEMENT sous le")
    print("    hasard veut dire qu a ce retard la bande dit l inverse.")


def etudie(nom, trades, S, decalage, tirages, rng, retard=0,
           duree=BAR_SEC, pas=1):
    """Les entrees rangees par BANDE ER, et le decompte.

    Deux lectures cote a cote :

      live   la fenetre se termine a l instant de l entree. C est ce
             qu un flux orderflow reellement live donnerait, et c est
             le cas a evaluer.

      ninja  la barre M1 close AVANT celle qui contient l entree --
             exactement _er_band_prec de orderflow_join. C est ce que
             la chaine actuelle sait produire.

    retard decale la fenetre live vers le passe, pour chiffrer ce que
    coute un flux qui traine.
    """
    lignes, ninja, flux, trois = [], [], [], []
    ers = []
    manques = 0
    for (magic, sym, sec, prix, sens, res) in trades:
        t = sec + decalage - retard
        m = mesure(S, t, duree, pas)
        if m is None:
            manques += 1
            continue
        lignes.append((m["bande"], res))
        trois.append((m["bande"], res, sec))
        ers.append(m["er"])
        # la barre M1 close avant celle qui contient l entree
        debut_barre = ((sec + decalage) // duree) * duree
        mn = mesure(S, debut_barre, duree, pas)
        if mn is not None:
            ninja.append((mn["bande"], res))
        if m["sens"] == 0:
            flux.append(("SANS FLUX", res))
        elif m["sens"] == sens:
            flux.append(("AVEC", res))
        else:
            flux.append(("CONTRE", res))
    if not lignes:
        print("")
        print("  %s : aucune entree exploitable." % nom)
        print("  Le fichier ne couvre probablement pas ces dates.")
        return None, None
    print("")
    print("  %s : %d entree(s) sur %d" % (nom, len(lignes), len(trades)))
    if manques:
        print("    %d ecartee(s), pas de ticks dans la fenetre" % manques)
    if retard:
        print("    fenetre M1 arretee %d s avant l entree" % retard)
    else:
        print("    fenetre M1 arretee A l instant de l entree (flux live)")
    print("    ER median %.3f, echantillonne au pas de %d s"
          % (mediane(ers), pas))
    bloc_bandes("%s -- flux LIVE a l entree" % nom, lignes, tirages, rng)
    if ninja:
        bloc_bandes("%s -- barre M1 PRECEDENTE (ce qu on sait deja faire)"
                    % nom, ninja, tirages, rng)
    bloc_contreflux(flux, MINI_CASE, rng, tirages)
    return lignes, trois


def bloc_bandes(titre, lignes, tirages, rng):
    """Le decompte par bande, puis le contrefactuel bande par bande."""
    print("")
    print("  %s" % titre)
    t = par_case(lignes)
    if not t:
        print("     aucune entree classee.")
        return
    total_n = sum(n for n, _s, _m in t.values())
    total_s = sum(sv for _n, sv, _m in t.values())
    print("     bande       trades    part      total    par trade"
          "   sans elle")
    print("     " + "-" * 66)
    for c in list(CASES) + [k for k in sorted(t) if k not in CASES]:
        if c not in t:
            continue
        n, sv, m = t[c]
        part = 100.0 * n / total_n
        marque = "" if n >= MINI_CASE else "  (moins de %d)" % MINI_CASE
        print("     %-11s %6d %6.1f%% %10.2f %11.2f %11.2f%s"
              % (c, n, part, sv, m, total_s - sv, marque))
    print("     " + "-" * 66)
    print("     %-11s %6d %6.1f%% %10.2f %11.2f"
          % ("ensemble", total_n, 100.0, total_s,
             total_s / total_n if total_n else 0.0))
    vrai, aussi, sur = permutation(lignes, MINI_CASE, tirages, rng)
    print("")
    if vrai is None:
        print("     Moins de deux bandes atteignent %d trades : le test de"
              % MINI_CASE)
        print("     permutation n a rien a comparer. On ne conclut pas.")
        return
    part = 100.0 * aussi / sur
    print("     ecart meilleure - pire : %.2f par trade" % vrai)
    print("     le hasard fait aussi bien %d fois sur %d, soit %.1f %%"
          % (aussi, sur, part))
    if part > 5.0:
        print("     -> NON CONCLUANT. La colonne  sans elle  montre des")
        print("        gains qui sortent tout seuls du decoupage.")
    else:
        print("     -> l ecart depasse le hasard (%.1f %%)." % part)
        print("        Attention tout de meme : plusieurs tableaux sont")
        print("        produits ici, et sur une dizaine d essais il en")
        print("        sort un sous 5 % par pur hasard. Le seuil honnete")
        print("        est 0,05 divise par le nombre d essais.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ym", default=r"C:\SierraChart\Data\YMU26-CBOT.scid")
    p.add_argument("--mes", default=r"C:\SierraChart\Data\MESU26-CME.scid")
    p.add_argument("--jours", type=int, default=10)
    p.add_argument("--barre", type=int, default=BAR_SEC,
                   help="duree en secondes de la barre sur laquelle l ER "
                        "est calcule. 60 = le M1 de orderflow_join.")
    p.add_argument("--pas", type=int, default=1,
                   help="pas d echantillonnage du chemin parcouru, en "
                        "secondes. Le chemin compte tick par tick est "
                        "plus long qu a la seconde, donc l ER sort plus "
                        "bas : ce reglage sert a retomber sur les _er "
                        "reellement enregistres.")
    p.add_argument("--retard", type=int, default=0,
                   help="secondes de retard du flux. 0 = le flux LIVE "
                        "qu on envisage d acheter, c est le cas a "
                        "evaluer. 600 = le flux Sierra tel qu on l a eu, "
                        "utile seulement pour la comparaison.")
    p.add_argument("--tickets", default="",
                   help="jsonl portant les _er enregistres, pour verifier "
                        "la reconstruction. Par defaut, les emplacements "
                        "habituels sont essayes.")
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
    tous_trois = []
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
        noms = ACTIFS_JSONL["ym"] if ch == a.ym else ACTIFS_JSONL["mes"]
        tick, diag = lit_tickets(chemins_tickets(a.tickets), noms)
        diag["essayes"] = chemins_tickets(a.tickets)
        bloc_calibrage(S, tick, diag, decalage, a.barre, (0, 1, 2, 5, 10))
        bloc_persistance(S.nom, concernes, S, decalage, a.barre, a.pas,
                         (60, 120, 300, 600, 900, 1800))
        if par:
            _l, tp = etudie("PARENTS", par, S, decalage, a.tirages, rng,
                            retard=a.retard, duree=a.barre, pas=a.pas)
            if tp:
                bloc_hors_echantillon("PARENTS %s" % S.nom, tp,
                                      a.tirages, rng)
        m, tm = etudie("MIROIRS 220/230/240", mir, S, decalage, a.tirages,
                       rng, retard=a.retard, duree=a.barre, pas=a.pas)
        if m:
            tous_mou.extend(m)
        if tm:
            tous_trois.extend(tm)
        S.ferme()

    if tous_mou:
        bloc_mou(tous_mou, a.tirages, rng)
    if tous_trois:
        bloc_hors_echantillon("MIROIRS 220/230/240, les deux actifs",
                              tous_trois, a.tirages, rng)
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
    bloc_persistance("BANC", trades, S, decalage, a.barre, a.pas,
                     (60, 120, 300, 600, 900, 1800))
    m, trois = etudie("BANC", trades, S, decalage, a.tirages, rng,
                      retard=a.retard, duree=a.barre, pas=a.pas)
    if trois:
        bloc_hors_echantillon("BANC", trois, a.tirages, rng)
    if m:
        bloc_mou(m, a.tirages, rng)
        print("")
        print("  Bandes trouvees : %s"
              % ", ".join("%s %d" % (b, sum(1 for c, _r in m if c == b))
                          for b in CASES))
        # Le banc plante des blocs haches (ER bas) et des blocs qui
        # poussent (ER haut). Une bande basse sur un bloc hache est
        # juste ; une bande haute sur un bloc qui pousse aussi.
        if len(m) == len(verite):
            bas = ("CARNAGE", "MOU")
            justes = sum(1 for (c, _r), hache in zip(m, verite)
                         if (c in bas) == hache)
            print("  Accord bande/regime : %d sur %d  (%.0f %%)"
                  % (justes, len(verite), 100.0 * justes / len(verite)))
            if justes < 0.8 * len(verite):
                print("  ATTENTION : moins de 80 pour cent d accord. L ER")
                print("  calcule ne retrouve pas le regime plante.")
    S.ferme()
    return 0


if __name__ == "__main__":
    sys.exit(main())
