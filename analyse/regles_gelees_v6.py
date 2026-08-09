# -*- coding: utf-8 -*-
"""
regles_gelees_v6.py -- gel du 2026-08-09

ORIGINE
    h1_seance.py : l amplitude de la PREMIERE HEURE americaine annonce
    celle du reste de la seance, et le P&L suit.

CE QUI A ETE MESURE
    Prevision de l amplitude du reste de la seance, 134 seances par actif :
        rho premiere heure US : +0,512 / +0,452 / +0,261, p <= 0,002
        rho range du matin    : +0,367 / +0,373 / +0,283
    La premiere heure bat le matin sur deux actifs, egale sur le troisieme.

    Direction de cette meme heure : 51%%, 49%%, 49%% de continuation,
    p entre 0,80 et 0,93. Rien. L amplitude se prevoit, pas le sens.

    P&L des tickets ouverts APRES 17h30 courtier, selon la taille de la
    premiere heure :
        petite  150 tk  +1,55 EUR/tk
        grande  118 tk  +32,60 EUR/tk
    Trois actifs sur trois dans le meme sens ; SPX500 p=0,004, les deux
    autres p=0,168 et p=0,297.

POURQUOI CELLE-CI PLUTOT QUE LA REGLE DE REGIME
    La regle de regime (trader apres les periodes calmes) repose sur
    l EFFICIENCE, dont on a mesure qu elle NE PERSISTE PAS : autocorrelation
    -0,182 / -0,044 / +0,041. Parier dessus, c est parier sur une quantite
    qu on ne sait pas anticiper.
    Celle-ci repose sur l AMPLITUDE, qui persiste au pas quotidien
    (+0,295 / +0,262 / +0,167) ET en intraday (+0,512 / +0,452 / +0,261).
    C est la seule quantite que ce marche rende previsible.

CE QUE CE GEL NE PROUVE PAS -- ET LA RESERVE EST LOURDE
    Les 268 tickets ouverts apres 17h30 font 12%% du corpus mais portent
    environ 4 080 EUR sur 5 030. Et les 118 tickets "grande premiere heure"
    -- CINQ POUR CENT du corpus -- en portent pres des trois quarts, avec
    le SPX500 qui pese les deux tiers de l effet.

    Cinq pour cent des tickets pour trois quarts du resultat, sur neuf
    seances : c est autant le profil d une vraie decouverte que celui d un
    surajustement. Les deux se ressemblent beaucoup a ce stade. Seul le
    hors-echantillon les separera.

SEUIL CAUSAL
    "Grande premiere heure" se juge contre la MEDIANE GLISSANTE des 20
    seances precedentes du meme actif, jour courant EXCLU. Un seuil calcule
    sur tout l echantillon serait du recul deguise : on saurait aujourd hui
    ce que seront les amplitudes des prochains mois.

CE FICHIER NE DOIT PLUS ETRE MODIFIE APRES LE GEL.
"""

VERSION = "6.0"
DATE_REDACTION = "2026-08-09"
ORIGINE = "h1_seance.py, amplitude de la premiere heure US, 134 seances/actif"

FIN_H1 = "17:30"          # heure COURTIER, soit 16h30 chez l utilisateur


def _h1(sig):
    """OUI / NON selon la mediane glissante, ou '' si inconnu."""
    return (sig.get("h1_grande") or "").strip().upper()


def _apres(sig):
    hm = (sig.get("hm") or "").strip()
    return bool(hm) and hm >= FIN_H1


# --------------------------------------------------------------- reference
def z0_reference(sig):
    """Aucun filtre. Toute regle doit battre celle-ci."""
    return True


# ------------------------------------------------------------- la regle
def z1_grande_h1_apres(sig):
    """
    La regle telle qu elle a ete mesuree : on n autorise que les tickets
    ouverts APRES la premiere heure americaine, les jours ou cette heure
    a ete large.
    """
    g = _h1(sig)
    if not g:
        return True                      # fail-open
    return g == "OUI" and _apres(sig)


def z2_apres_seulement(sig):
    """
    TEMOIN INDISPENSABLE. Le filtre horaire seul, sans regarder la taille
    de la premiere heure. Si z1 ne bat pas z2, alors la taille de l heure
    n apporte rien et c est l heure tardive qui portait tout -- exactement
    le piege qui a fait tomber l hypothese du seuil d excursion.
    """
    return _apres(sig)


def z3_grande_h1_partout(sig):
    """
    La taille de la premiere heure vaut-elle pour TOUTE la journee, ou
    seulement pour la fin de seance ? Si z3 tient aussi bien que z1, la
    regle est plus large et plus utile qu on ne le pensait.
    """
    g = _h1(sig)
    if not g:
        return True
    return g == "OUI"


# ------------------------------------------------------ croisement avec V5
def z4_avec_matin(sig):
    """
    Croisement avec le survivant du gel V5. Les deux filtres sont-ils
    additifs ? Rappel du gel V4 : empiler deux survivants avait detruit
    de l argent. On teste, on ne suppose pas.
    """
    a = (sig.get("accord_matin") or "").strip().upper()
    if a and a != "AVEC":
        return False
    return z1_grande_h1_apres(sig)


# ------------------------------------------------------------- le miroir
def z5_petite_h1_apres(sig):
    """
    CONTROLE NEGATIF. La regle absurde : ne prendre que les tickets de fin
    de seance les jours de PETITE premiere heure. Son ecart doit etre le
    miroir de z1. Son p sera identique a celui de z1 sur la meme partition
    -- c est l ecart qu il faut lire, pas le p.
    """
    g = _h1(sig)
    if not g:
        return True
    return g == "NON" and _apres(sig)


REGLES = [
    ("Z0", "reference : aucun filtre",         z0_reference,        []),
    ("Z1", "grande 1re heure US, apres 17h30", z1_grande_h1_apres,  ["h1_grande", "hm"]),
    ("Z2", "TEMOIN : apres 17h30 seulement",   z2_apres_seulement,  ["hm"]),
    ("Z3", "grande 1re heure US, toute heure", z3_grande_h1_partout, ["h1_grande"]),
    ("Z4", "Z1 et AVEC le matin (V5)",         z4_avec_matin,       ["h1_grande", "hm", "accord_matin"]),
    ("Z5", "CONTROLE NEGATIF : petite 1re h.", z5_petite_h1_apres,  ["h1_grande", "hm"]),
]
