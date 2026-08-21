# -*- coding: utf-8 -*-
"""
papers_exempt.py -- les miroirs paper ne sortent QUE par leur parent.

POURQUOI

    Le 21/08, sur 59 miroirs soldes, 5 seulement l ont ete par le
    miroir lui-meme. Les 54 autres ont ete ramasses par des modules
    qui ferment par symbole sans regarder le magic :

        M154_FOLLOW_*   30 sorties   (m154_leader_gate)
        IGN_COVER       18 sorties   (short_cover)
        stop loss        5 sorties
        PREOPEN_75       1 sortie    (preopen_protect)

    Or les trois modules qui ferment 80 % des positions PARENTES --
    IGNT_REVERSE, IGN_REVERSE, IGNT_TRAIL70 -- n ont jamais touche un
    seul miroir. Les deux populations vivaient donc sous deux regimes
    de sortie disjoints, et comparer leurs P&L ne mesurait rien.

    Un miroir doit etre la copie exacte de son parent : meme entree,
    meme sortie. Sa sortie appartient a son parent, a personne d autre.

CE QUE CE MODULE NE FAIT PAS

    Il ne change AUCUNE sortie de parent. Il n enleve rien a personne :
    il ajoute des plages de magics qui n ont jamais appartenu qu aux
    miroirs. Un magic de la stack reelle ne peut pas y tomber -- le
    plus haut observe est 208303, et les plages 251xxx, 300000-460000,
    2000815 et 20001711 sont hors de la fenetre 220000-249999.

SOURCE UNIQUE

    Les plages sont ici et nulle part ailleurs. Ajouter une famille de
    papers, c est modifier PLAGES, pas les trois modules.
"""

# (debut inclus, fin exclue). 220xxx = benchmarks, 230xxx = par actif,
# 240xxx = serie composee. La borne haute 250000 laisse dehors 251xxx.
PLAGES = ((220000, 250000),)


def est_miroir(magic):
    """True si ce magic appartient a un miroir paper. Ne leve jamais."""
    try:
        m = int(magic)
    except (TypeError, ValueError):
        return False
    for debut, fin in PLAGES:
        if debut <= m < fin:
            return True
    return False


def ajoute_plage(debut, fin):
    """Etend la couverture en cours d execution. fin est exclue."""
    global PLAGES
    PLAGES = PLAGES + ((int(debut), int(fin)),)
