# -*- coding: utf-8 -*-
"""
regles_gelees_v5.py -- gel du 2026-08-09

ORIGINE
    Croisement de la direction de la matinee (profil_jour.csv, colonne
    am_dir) avec le sens de chaque ticket (churn_trades, champ dir).
    Trouve le 09/08 par sens_matin.py.

CE QU ON A MESURE, ET POURQUOI ON LE GELE
    Sur 2223 tickets et 9 seances (21/07 -> 07/08) :
      ticket DANS le sens du matin  1228 tk  +12,56 EUR/tk
      ticket a CONTRE-SENS           995 tk  -10,44 EUR/tk
      ecart +23,00, p=0,000

    Il survit aux DEUX controles, ce qu aucune autre piste de la semaine
    n avait fait :
      a l unite seance  : +22,09, 7 seances sur 9, p=0,008
      a heure egale     : +22,13, p=0,000

    Le second chiffre est le plus important. L ecart brut vaut +23,00 et
    apres retrait complet de l effet horaire il reste +22,13 : il ne bouge
    pas. L effet est donc ORTHOGONAL a l heure -- il ne doit rien a la
    session US ni au creneau 09-11h, et n est pas un habillage du gel V2.
    A comparer avec l hypothese du seuil, ou le meme centrage faisait
    tomber un ecart de -20 a quelques euros avec un signe qui basculait.

CE QUE CE GEL NE PROUVE PAS
    Tout ceci est IN-SAMPLE INTEGRAL : la regle est nee de ces 9 seances.
    Neuf seances, c est peu. Le prix, lui, dit que la matinee donne une
    orientation FAIBLE : les deux bornes du matin cassent dans environ la
    moitie des seances, et l extension une fois la borne cassee est
    identique quel que soit le sens du matin (p=0,872). Autrement dit le
    marche ne justifie pas un effet de cette taille sur le P&L. Soit il
    s agit d une faille comportementale de la stack, soit d un artefact
    de 9 seances. C est precisement ce que le hors-echantillon dira.

CE FICHIER NE DOIT PLUS ETRE MODIFIE APRES LE GEL.
    oos_v5.py enregistre son empreinte SHA-256 et refuse de rendre un
    verdict si elle a change.

CONVENTION
    Chaque regle prend un signal et renvoie True si on AUTORISE le trade.
    Champ manquant = on autorise (fail-open), comme en live.
"""

VERSION = "5.0"
DATE_REDACTION = "2026-08-09"
ORIGINE = "sens_matin.py, croisement am_dir x dir sur 2223 tickets / 9 seances"

HEURES_MATIN = (9, 10, 11)


def _accord(sig):
    """AVEC / CONTRE la direction de la matinee, ou '' si inconnu."""
    return (sig.get("accord_matin") or "").strip().upper()


def _flux(sig):
    """AVEC / CONTRE l orderflow, ou '' si inconnu."""
    return (sig.get("contra") or "").strip().upper()


# --------------------------------------------------------------- reference
def y0_reference(sig):
    """Aucun filtre. Toute regle doit battre celle-ci."""
    return True


# ------------------------------------------------------ les deux effets
def y1_avec_matin(sig):
    """
    Le nouvel effet. On n autorise que les tickets qui vont dans le sens
    de la matinee.
    """
    a = _accord(sig)
    if not a:
        return True                      # fail-open
    return a == "AVEC"


def y2_contre_flux(sig):
    """
    L effet deja etabli, conserve ici pour comparaison directe sur le meme
    corpus et la meme periode : +10,70 EUR/tk, p environ 0,015, 7 seances
    sur 7 positives lors de sa mesure.
    """
    f = _flux(sig)
    if not f:
        return True
    return f == "CONTRE"


def y3_les_deux(sig):
    """
    L empilement. A comparer IMPERATIVEMENT a y1 et y2 pris seuls.
    On a deja vu, sur le gel V4, un empilement detruire de l argent :
    X3 = X1 et X2 rendait moins que X2 seul, sur les memes donnees.
    Si y3 ne bat pas le meilleur des deux, il ne fait que reduire le
    volume et il faudra le dire.
    """
    return y1_avec_matin(sig) and y2_contre_flux(sig)


# ------------------------------------------- l effet ajoute-t-il a l heure ?
def y4_matin_hors_9_11(sig):
    """
    Temoin de non-redondance avec le gel v1. Le centrage horaire dit deja
    que l effet est orthogonal a l heure ; si c est vrai, y4 doit faire
    mieux que le simple "hors 09-11h" et mieux que y1 seul de peu.
    """
    return y1_avec_matin(sig) and sig.get("heure") not in HEURES_MATIN


def y5_matin_session_us(sig):
    """
    Meme logique contre le gel V2, dont la decision numero 1 etait
    "rien avant 14h". Si y5 ne bat pas la session US seule, l effet du
    matin n apportait rien par-dessus l heure malgre le centrage.
    """
    h = sig.get("heure")
    return y1_avec_matin(sig) and h is not None and h >= 14


# ------------------------------------------------------------- le miroir
def y6_contre_matin(sig):
    """
    Le miroir de y1 : on n autorise QUE les tickets a contre-sens.
    Regle volontairement absurde, gelee comme controle negatif. Si elle
    ne s effondre pas hors echantillon alors que y1 tient, c est que le
    harnais mesure autre chose que ce qu on croit.
    """
    a = _accord(sig)
    if not a:
        return True
    return a == "CONTRE"


REGLES = [
    ("Y0", "reference : aucun filtre",        y0_reference,      []),
    ("Y1", "AVEC le sens du matin",           y1_avec_matin,     ["accord_matin"]),
    ("Y2", "CONTRE le flux (rappel)",         y2_contre_flux,    ["contra"]),
    ("Y3", "Y1 et Y2 empiles",                y3_les_deux,       ["accord_matin", "contra"]),
    ("Y4", "Y1 et hors 09h-11h",              y4_matin_hors_9_11, ["accord_matin", "heure"]),
    ("Y5", "Y1 et session US",                y5_matin_session_us, ["accord_matin", "heure"]),
    ("Y6", "CONTROLE NEGATIF : contre-sens",  y6_contre_matin,   ["accord_matin"]),
]
