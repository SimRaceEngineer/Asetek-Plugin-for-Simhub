# -*- coding: utf-8 -*-
"""
regles_gelees_v7.py -- gel du 2026-08-09

CE QU ON GELE ICI, ET POURQUOI C EST DIFFERENT DES AUTRES
    Les gels precedents figeaient une hypothese qu on croyait bonne. Celui-ci
    fige une CONTRADICTION, parce qu on ne sait pas la trancher.

    volatilite.py : les periodes CALMES sont les plus rentables.
        Amplitude moyenne glissante, moitie basse contre moitie haute :
        +362 contre +35 EUR par observation. Sur 42 observations, avec une
        coupure a la mediane choisie APRES avoir vu les donnees.

    h1_seance.py : les GRANDES premieres heures sont les plus rentables.
        +32,60 contre +1,55 EUR par ticket, sur les trois indices, et le
        lien H1 -> reste de seance tient mois apres mois avec une
        decroissance monotone du cinquieme haut au cinquieme bas.

    Or l amplitude PERSISTE (rho +0,295 / +0,262 / +0,167 au pas quotidien,
    sur les trois indices). Un regime calme devrait donc produire des
    petites premieres heures. Les deux resultats se contredisent en signe.

    L un des deux est faux. Le second est bien mieux etaye -- 128 seances
    contre 42, dose-reponse monotone contre coupure post hoc -- mais
    trancher a l intuition serait exactement ce qu on s interdit depuis le
    debut. On fige donc LES DEUX SENS et on laisse le hors-echantillon
    arbitrer.

L INDICATEUR, ET SA CAUSALITE
    ind = amplitude moyenne des 10 seances PRECEDENTES, divisee par la
    mediane des amplitudes de TOUTES les seances anterieures du meme actif.
    Ni le jour courant ni aucun jour futur n y entrent, et le seuil lui-meme
    (1,0) n est pas un parametre ajuste : c est le point ou la periode
    recente egale l historique.

    C est un detail qui compte. Dans regime_jour.py la coupure se faisait a
    la mediane de l echantillon complet, donc en connaissant l avenir. Ici,
    non.

CE FICHIER NE DOIT PLUS ETRE MODIFIE APRES LE GEL.
    oos_v7.py enregistre son empreinte SHA-256.

CONVENTION
    Chaque regle renvoie True si on AUTORISE le trade. Champ manquant =
    on autorise (fail-open), comme en live.
"""

VERSION = "7.0"
DATE_REDACTION = "2026-08-09"
ORIGINE = "contradiction volatilite.py (calme rentable) contre h1_seance.py (grande H1 rentable)"


def _regime(sig):
    """CALME / AGITE, ou '' si l indicateur n a pas pu etre calcule."""
    return (sig.get("regime_ampl") or "").strip().upper()


def _h1(sig):
    """GRANDE / PETITE premiere heure US, ou ''."""
    return (sig.get("h1_taille") or "").strip().upper()


# --------------------------------------------------------------- reference
def w0_reference(sig):
    return True


# ------------------------------------------- les deux sens de la contradiction
def w1_regime_calme(sig):
    """
    La regle issue de volatilite.py : on ne trade qu apres une periode
    d amplitude inferieure a l historique.
    """
    r = _regime(sig)
    return True if not r else r == "CALME"


def w2_regime_agite(sig):
    """
    Le miroir exact. Si c est h1_seance.py qui a raison -- l amplitude
    paie -- alors c est cette regle qui doit tenir hors echantillon, pas
    la precedente.

    w1 et w2 auront TOUJOURS le meme p : ce sont deux complements sur la
    meme partition. C est leur ECART qui les distingue, jamais leur p.
    """
    r = _regime(sig)
    return True if not r else r == "AGITE"


# ------------------------------------------------- le rappel du gel V6
def w3_grande_h1(sig):
    """
    Rappel de la regle V6, refige ici pour etre comparee aux deux
    precedentes SUR LE MEME CORPUS et avec les memes controles. Sans ce
    point de comparaison on ne saurait pas si w1 ou w2 apporte quoi que ce
    soit par-dessus ce qu on sait deja.
    """
    h = _h1(sig)
    return True if not h else h == "GRANDE"


# --------------------------------------------------------- les croisements
def w4_calme_et_grande_h1(sig):
    """
    Si les deux echelles disent des choses differentes plutot que
    contradictoires, cette combinaison devrait battre chacune seule.
    Reserve : trois fois de suite (X3, Y3, Z4) l empilement de deux
    survivants a DETRUIT de la valeur sur ce corpus. On l attend donc
    en dessous, et une surprise serait d autant plus interessante.
    """
    return w1_regime_calme(sig) and w3_grande_h1(sig)


def w5_agite_et_grande_h1(sig):
    """
    L autre croisement. C est la lecture la plus naturelle si l amplitude
    paie a toutes les echelles : periode agitee ET grande premiere heure.
    """
    return w2_regime_agite(sig) and w3_grande_h1(sig)


REGLES = [
    ("W0", "reference : aucun filtre",        w0_reference,        []),
    ("W1", "regime CALME (volatilite.py)",    w1_regime_calme,     ["regime_ampl"]),
    ("W2", "regime AGITE (le miroir)",        w2_regime_agite,     ["regime_ampl"]),
    ("W3", "grande 1re heure US (rappel V6)", w3_grande_h1,        ["h1_taille"]),
    ("W4", "CALME et grande 1re heure",       w4_calme_et_grande_h1, ["regime_ampl", "h1_taille"]),
    ("W5", "AGITE et grande 1re heure",       w5_agite_et_grande_h1, ["regime_ampl", "h1_taille"]),
]
