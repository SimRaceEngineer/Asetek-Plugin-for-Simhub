# -*- coding: utf-8 -*-
"""
regles_gelees_v8.py -- gel du 2026-08-10

ORIGINE
    Proposition exterieure ("Amplitude-Boost"), retenue pour ce qu elle a de
    testable et depouillee de ce qui ne l est pas. Elle part du seul resultat
    qui ait traverse les periodes : la taille de la premiere heure americaine
    annonce l amplitude du reste de la seance.

CE QU ELLE AJOUTE A CE QU ON A DEJA
    Le gel V6 coupe a la MEDIANE glissante -- la moitie haute des seances.
    Celle-ci coupe au TERCILE HAUT : n autoriser que le tiers des seances ou
    la premiere heure a ete la plus large. C est la seule difference de fond
    entre les deux, et c est elle qu on met a l epreuve. Rien d autre dans
    cette proposition n etait a la fois nouveau et mesurable.

    Le seuil 0,70 ne vient PAS d une mesure. Il vient de la proposition, ou il
    etait avance comme "top 30 pour cent". On le gele tel quel, sans l ajuster, et U3
    est la pour dire s il bat le 0,50 du gel V6 ou s il ne fait que reduire le
    volume. C est exactement la question que le gel V4 avait deja tranchee
    dans l autre sens pour les empilements.

CE QUE CE GEL NE PROUVE PAS
    Aucun chiffre in-sample n a ete produit pour justifier ce seuil-ci : on
    fige une hypothese venue d ailleurs, pas un resultat mesure ici. C est
    plus honnete que les gels precedents, et plus fragile.

    Et la reserve du gel V6 vaut integralement : sur le corpus in-sample, les
    118 tickets "grande premiere heure" font CINQ POUR CENT des tickets et
    portent pres des trois quarts du resultat, le SPX500 pesant a lui seul
    les deux tiers de l effet. Couper au tercile plutot qu a la mediane
    CONCENTRE encore ce profil-la. Si le gel V6 tient hors echantillon et pas
    celui-ci, la reponse sera qu on avait trop serre.

TROIS ELEMENTS DE LA PROPOSITION ONT ETE ECARTES, ET IL FAUT DIRE POURQUOI

  1. LE SEUIL SUR LA DISTRIBUTION COMPLETE. La proposition compare l amplitude
     du jour a "l historique des 128-134 seances de l etude". C est du recul
     deguise : cela revient a savoir aujourd hui ce que seront les amplitudes
     des mois a venir. C est le defaut exact que le gel V7 reproche a
     regime_jour.py. Remplace ici par un quantile GLISSANT sur les 20 seances
     precedentes du meme actif, jour courant exclu.

  2. LE BIAIS 70/30 SUR LES JUMEAUX 206/207. jumeaux.py dit que ces deux
     familles sont, si l appariement tient, la SEULE randomisation controlee
     du dispositif, et qu elle est la par conception. Biaiser le ratio la
     detruit : on transformerait le seul essai controle en observation. De
     plus l A/B n a pas encore rendu de verdict -- choisir le sens du biais
     maintenant, c est prejuger de ce qu on est en train de mesurer.

  3. LA SELECTION DES CONFIGS ET DES MAGICS. Rien dans ce depot ne corrobore
     "TIGHT_CROSS et MID oui, CHURN non, magics 205 exclus". Ces chiffres
     viennent du panel rails. Retenir des magics apres coup sur neuf seances
     est le piege d exploration deja verifie : sur des donnees ou le sens des
     tickets etait tire au hasard, deux sous-cellules sur six passaient sous
     p=0,05. Si cette piste vaut quelque chose, elle merite son propre gel,
     avec son propre temoin.

CE QUI A ETE GARDE SANS DISCUSSION
    Aucun filtre directionnel. C est la seule lecture correcte de l etude :
    cinq mesures independantes ont cherche le sens et l ont manque. La
    proposition le dit mieux que nous ne l avions ecrit.

SEUIL CAUSAL
    h1_q = part des 20 seances PRECEDENTES du meme actif dont la premiere
    heure a ete moins ample que celle du jour. Jour courant exclu, aucun jour
    futur. Moins de 10 seances d historique : champ vide, donc fail-open.

CE FICHIER NE DOIT PLUS ETRE MODIFIE APRES LE GEL.
    oos_v8.py enregistre son empreinte SHA-256 et refuse de rendre un verdict
    si elle a change.

CONVENTION
    Chaque regle prend un signal et renvoie True si on AUTORISE le trade.
    Champ manquant = on autorise (fail-open), comme en live.
"""

VERSION = "8.0"
DATE_REDACTION = "2026-08-10"
ORIGINE = ("proposition Amplitude-Boost, reduite a son seul element testable : "
           "tercile haut de la premiere heure US contre la mediane du gel V6")

FENETRE_Q = 20            # seances servant au quantile glissant
MIN_HIST = 10             # en dessous, champ vide : fail-open

FIN_H1 = "17:30"          # heure COURTIER, soit 16h30 a Paris en ete
FIN_FENETRE = "21:00"     # heure COURTIER, soit 20h00 a Paris en ete

Q_TERCILE = 0.70          # le seuil de la proposition, gele tel quel
Q_MEDIANE = 0.50          # le seuil du gel V6, rappele pour comparaison
Q_BAS = 0.30              # le miroir, pour le controle negatif


def _q(sig):
    """Quantile glissant de la premiere heure, ou None si inconnu."""
    v = sig.get("h1_q")
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _apres_h1(sig):
    hm = (sig.get("hm") or "").strip()
    return bool(hm) and hm >= FIN_H1


def _avant_fin(sig):
    hm = (sig.get("hm") or "").strip()
    return bool(hm) and hm < FIN_FENETRE


# --------------------------------------------------------------- reference
def u0_reference(sig):
    """Aucun filtre. Toute regle doit battre celle-ci."""
    return True


# ------------------------------------------------------------- la regle
def u1_tercile_apres(sig):
    """
    La regle telle qu elle a ete proposee : n autoriser que les tickets
    ouverts APRES la premiere heure americaine, les jours ou cette heure a
    ete dans le TERCILE HAUT des 20 seances precedentes.
    """
    q = _q(sig)
    if q is None:
        return True                      # fail-open
    return q >= Q_TERCILE and _apres_h1(sig)


def u2_apres_seulement(sig):
    """
    TEMOIN INDISPENSABLE, le meme qu au gel V6. Le filtre horaire seul, sans
    regarder la taille de la premiere heure. Si U1 ne bat pas U2, la taille
    n apporte rien et c est l heure tardive qui portait tout -- le piege qui
    a fait tomber l hypothese du seuil d excursion.
    """
    return _apres_h1(sig)


def u3_mediane_apres(sig):
    """
    LA COMPARAISON QUI DECIDE DE CE GEL. Le seuil du gel V6 -- la mediane
    glissante -- applique au meme corpus et avec les memes controles.

    Si U1 ne bat pas U3, le tercile ne fait que reduire le volume, et toute
    la proposition se ramene a ce qu on savait deja depuis le 09/08. Si U1
    bat U3, serrer le seuil paie, et c est un resultat neuf.

    A la definition du quantile pres, cette regle reproduit Z1 du gel V6.
    Le gel V6 reste juge sur son propre fichier ; celui-ci n est qu un point
    de comparaison interne.
    """
    q = _q(sig)
    if q is None:
        return True
    return q >= Q_MEDIANE and _apres_h1(sig)


# --------------------------------------------------- la borne de fin proposee
def u4_tercile_fenetre(sig):
    """
    U1 borne a 21h00 courtier. La proposition arrete la fenetre la, sans
    justification chiffree. On teste, on ne suppose pas.
    """
    return u1_tercile_apres(sig) and _avant_fin(sig)


def u5_fenetre_seule(sig):
    """
    TEMOIN de la borne de fin, sans la taille de la premiere heure. Sans lui
    on ne saurait pas si U4 gagne par le tercile ou par la simple exclusion
    de la fin de seance. Meme raisonnement que U2, un cran plus loin.
    """
    return _apres_h1(sig) and _avant_fin(sig)


# ------------------------------------------------------------- le miroir
def u6_tercile_bas_apres(sig):
    """
    CONTROLE NEGATIF. La regle absurde : ne prendre que les tickets de fin de
    seance les jours ou la premiere heure a ete dans le TERCILE BAS. Son
    ecart doit etre le miroir de U1.

    Attention a la lecture : U1 et U6 ne sont pas complementaires -- le
    tiers du milieu n est dans ni l un ni l autre -- donc leurs p ne seront
    pas identiques, contrairement a W1 et W2 du gel V7. Ici le p se lit.
    """
    q = _q(sig)
    if q is None:
        return True
    return q <= Q_BAS and _apres_h1(sig)


REGLES = [
    ("U0", "reference : aucun filtre",          u0_reference,        []),
    ("U1", "tercile haut 1re h., apres 17h30",  u1_tercile_apres,    ["h1_q", "hm"]),
    ("U2", "TEMOIN : apres 17h30 seulement",    u2_apres_seulement,  ["hm"]),
    ("U3", "mediane (V6), apres 17h30",         u3_mediane_apres,    ["h1_q", "hm"]),
    ("U4", "U1 borne a 21h00",                  u4_tercile_fenetre,  ["h1_q", "hm"]),
    ("U5", "TEMOIN : 17h30-21h00 seulement",    u5_fenetre_seule,    ["hm"]),
    ("U6", "CONTROLE NEGATIF : tercile bas",    u6_tercile_bas_apres, ["h1_q", "hm"]),
]
