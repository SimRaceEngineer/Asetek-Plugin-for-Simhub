#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jauge_section.py -- l amplitude de la premiere heure americaine.

CE QU ELLE MONTRE
    Pour chaque indice, l amplitude de la premiere heure US comparee a la
    mediane des 20 seances precedentes du meme indice : GRANDE ou PETITE.
    Et le regime d amplitude des 10 dernieres seances face a l historique :
    CALME ou AGITE.

POURQUOI CES DEUX-LA ET PAS D AUTRES
    Etude du 09/08 sur 128 seances. La taille de la premiere heure annonce
    l amplitude du reste de la seance : 81 / 73 / 64 %% de reussite dans le
    cinquieme haut contre 50 de reference, decroissance monotone jusqu au
    cinquieme bas a 26 / 33 / 30, et le lien tient mois apres mois. C est
    le seul signal de toute l etude qui ait traverse les periodes.

    Et le croisement des deux, mesure au gel V7 : CALME + GRANDE donne
    +23,70 EUR par ticket, contre +12,56 pour le calme seul et +9,69 pour
    la grande heure seule. Premier empilement qui batte ses composantes.

CE QU ELLE NE DIT PAS -- A LIRE AVANT DE S EN SERVIR
    ELLE NE DONNE PAS LE SENS. Cinq mesures independantes ont echoue a
    trouver la direction : direction du matin, de la pre-ouverture, ordre
    des cassures, direction de la premiere heure, et flux de la premiere
    heure. La jauge dit QUAND, jamais DANS QUEL SENS. Voir "GRANDE" et y
    lire une orientation est le contresens exact.

ELLE DECRIT. Aucune regle, aucun ordre. Les sept gels courent jusqu au
01/09 et rien n est applique. Une jauge qu on regarde n est pas un filtre
qu on subit.

SOURCE
    docs/jauge_h1.json, ecrit par jauge_h1.py. Le panel ne calcule rien :
    h1_seance.py recharge 190 jours de M5 et met plusieurs minutes, ce qui
    est impensable a chaque rafraichissement.
"""
import json
import os
from datetime import datetime

VERT = "#3fb950"          # GRANDE, ou regime CALME
GRIS = "#6e7681"          # PETITE, neutre, en-tetes
ORANGE = "#d29922"        # avertissement, donnee vieillie
ROUGE = "#f85149"         # jauge absente ou illisible

FIC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "docs", "jauge_h1.json")
AGE_MAX_H = 30            # au-dela, on affiche la date en orange


def _lire():
    try:
        with open(FIC, "r", encoding="utf-8-sig") as f:
            return json.load(f), None
    except IOError:
        return None, "docs/jauge_h1.json absent -- lance jauge_h1.py"
    except ValueError as e:
        return None, "docs/jauge_h1.json illisible : %s" % e


def _age_heures(genere):
    try:
        t = datetime.strptime(str(genere)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return (datetime.now() - t).total_seconds() / 3600.0


def _cell(txt, couleur=GRIS, gras=False):
    p = "font-weight:600;" if gras else ""
    return "<td style='color:%s;%stext-align:right;padding:2px 8px'>%s</td>" % (
        couleur, p, txt)


def render(trades=None):
    """Renvoie le fragment HTML de la section. L argument trades n est pas
    utilise : il n est la que pour garder la meme signature que les autres
    modules de section, au cas ou l appel serait uniformise un jour."""
    etat, err = _lire()
    titre = ("<div style='margin-top:14px'>"
             "<span style='color:%s;font-weight:600'>JAUGE H1"
             "</span> <span style='color:%s;font-size:11px'>"
             "amplitude de la premiere heure US -- dit QUAND, jamais dans "
             "quel sens</span>" % (GRIS, GRIS))
    if err:
        return titre + ("<div style='color:%s;padding:4px 0'>%s</div></div>"
                        % (ROUGE, err))

    lignes = []
    for sym in sorted(etat.get("actifs", {})):
        e = etat["actifs"][sym]
        taille = e.get("taille") or "?"
        regime = e.get("regime") or "?"
        c_t = VERT if taille == "GRANDE" else GRIS
        c_r = VERT if regime == "CALME" else GRIS
        ratio = e.get("ratio")
        r_txt = ("%.2f" % ratio) if isinstance(ratio, (int, float)) else "-"
        med = e.get("mediane_20")
        m_txt = ("%.1f" % med) if isinstance(med, (int, float)) else "-"
        lignes.append(
            "<tr>"
            "<td style='color:%s;padding:2px 8px'>%s</td>" % (GRIS, sym)
            + _cell("%.1f" % e.get("h1_range", 0))
            + _cell(m_txt)
            + _cell(r_txt)
            + _cell(taille, c_t, taille == "GRANDE")
            + _cell(regime, c_r, regime == "CALME")
            + "</tr>")

    entete = ("<tr>" + "".join(
        "<th style='color:%s;text-align:right;padding:2px 8px;"
        "font-weight:400'>%s</th>" % (GRIS, h)
        for h in ("actif", "H1", "mediane 20", "ratio", "taille", "regime"))
        + "</tr>")

    age = _age_heures(etat.get("genere"))
    c_date = ORANGE if (age is None or age > AGE_MAX_H) else GRIS
    suffixe = ""
    if age is not None and age > AGE_MAX_H:
        suffixe = " -- vieille de %.0f h, relance jauge_h1.py" % age
    pied = ("<div style='color:%s;font-size:11px;padding-top:4px'>"
            "seance %s, calcul %s%s</div>"
            % (c_date, etat.get("date", "?"), etat.get("genere", "?"), suffixe))

    return (titre
            + "<table style='border-collapse:collapse;font-size:12px'>"
            + entete + "".join(lignes) + "</table>" + pied + "</div>")
