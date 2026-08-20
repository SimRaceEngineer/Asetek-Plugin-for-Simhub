#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scid_visites.py -- la base CFD/future, puis le flux visite par visite.

LECTEUR SEUL. N ECRIT RIEN.

  python scid_visites.py "C:\\SierraChart\\Data\\YMU26-CBOT.scid" \\
         --bas 53596 --haut 53705

TROIS ETAPES, DANS CET ORDRE, PARCE QUE CHACUNE DEPEND DE LA
PRECEDENTE.

1. LE DECALAGE HORAIRE. Sierra Chart horodate en UTC dans le .scid ;
   tickets_rails.jsonl est en heure locale du VPS. On ne suppose pas
   l ecart : on essaie tous les decalages d une demi-heure entre -12 h
   et +14 h, et on garde celui qui rend l ecart CFD/future le plus
   STABLE. Le bon decalage est celui qui aligne les deux series ; un
   mauvais decalage compare des instants differents et la dispersion
   explose.

2. LA BASE. Une fois l heure alignee, l ecart median entre le prix
   CFD de tes tickets US30 et le prix YM au meme instant. Elle derive
   vers l echeance : elle est donnee par semaine, pas en un chiffre.
   La bande demandee est alors convertie en prix YM.

3. LES VISITES. Un profil de six mois ecrase les passages successifs.
   Ici chaque visite est isolee -- une visite se termine quand le prix
   quitte la bande plus de --trou minutes. Pour chacune : date, heure,
   duree, volume, bid, ask, delta. Puis le delta par heure de la
   journee, toutes visites confondues.

Sans tickets_rails.jsonl, les etapes 1 et 2 sont sautees et la bande
est prise telle quelle, en prix YM.
"""

import argparse
import bisect
import datetime
import gzip
import io
import json
import os
import struct
import sys
from array import array

SEP = "=" * 96
ORIGINE = datetime.datetime(1899, 12, 30)
EN_TETE = 56
ENREG = 40
FMT = "<q4f4I"
TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")


def humain(n):
    for u, s in (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("ko", 1024)):
        if n >= s:
            return "%.1f %s" % (n / float(s), u)
    return "%d o" % n


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def ecart_median(v):
    """Dispersion robuste : mediane des ecarts a la mediane."""
    m = mediane(v)
    if m is None:
        return None
    return mediane([abs(x - m) for x in v])


# ------------------------------------------------------------------ .scid
def lit_scid(chemin):
    """Rend (temps, prix, vol, bid, ask) en tableaux paralleles."""
    taille = os.path.getsize(chemin)
    f = open(chemin, "rb")
    try:
        brut = f.read(EN_TETE)
        if len(brut) < EN_TETE or brut[:4] != b"SCID":
            return None, "signature absente : ce n est pas un .scid"
        te, tr = struct.unpack("<II", brut[4:12])
        if te != EN_TETE or tr != ENREG:
            return None, "tailles inattendues (%d / %d)" % (te, tr)

        f.seek(te)
        b8 = f.read(tr)[:8]
        (vi,) = struct.unpack("<q", b8)
        (vd,) = struct.unpack("<d", b8)
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
        bornes = (datetime.datetime(1990, 1, 1), datetime.datetime(2100, 1, 1))
        ok_i = _mi(vi) is not None and bornes[0] <= _mi(vi) <= bornes[1]
        ok_d = _mj(vd) is not None and bornes[0] <= _mj(vd) <= bornes[1]
        if ok_i:
            mode = "micro"
        elif ok_d:
            mode = "double"
        else:
            return None, "aucun encodage de date plausible"

        t = array("q")
        p = array("f")
        v = array("I")
        b = array("I")
        a = array("I")
        f.seek(te)
        paquet = 65536 * tr
        base = int((ORIGINE - datetime.datetime(1970, 1, 1)).total_seconds())
        while True:
            bloc = f.read(paquet)
            if not bloc:
                break
            util = bloc[:len(bloc) - len(bloc) % tr]
            for m in struct.iter_unpack(FMT, util):
                if mode == "micro":
                    sec = base + m[0] // 1000000
                else:
                    (jours,) = struct.unpack("<d", struct.pack("<q", m[0]))
                    sec = base + int(jours * 86400)
                t.append(sec)
                p.append(m[4])
                v.append(m[6])
                b.append(m[7])
                a.append(m[8])
            if len(bloc) < paquet:
                break
        return (t, p, v, b, a, mode, taille), None
    finally:
        f.close()


# ------------------------------------------------------------------ tickets
def ouvre(c):
    if c.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(c, "rb"), encoding="utf-8",
                                errors="replace")
    return io.open(c, encoding="utf-8", errors="replace")


def lit_tickets(base, actif):
    out = []
    for c in (base, base + ".gz"):
        if not os.path.isfile(c):
            continue
        with ouvre(c) as f:
            for l in f:
                l = l.strip()
                if not l:
                    continue
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if not isinstance(o, dict) or o.get("asset") != actif:
                    continue
                ts, pr = o.get("entry_ts"), o.get("entry_price")
                if not isinstance(ts, str) or len(ts) < 19:
                    continue
                try:
                    d = datetime.datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
                    out.append((int((d - datetime.datetime(1970, 1, 1))
                                    .total_seconds()), float(pr)))
                except (ValueError, TypeError):
                    continue
    return out


def prix_a(temps, prix, sec, tolerance=120):
    """Le prix YM le plus proche de cet instant, ou None."""
    i = bisect.bisect_left(temps, sec)
    meilleur, ecart = None, None
    for j in (i - 1, i):
        if 0 <= j < len(temps):
            e = abs(temps[j] - sec)
            if ecart is None or e < ecart:
                ecart, meilleur = e, prix[j]
    if ecart is None or ecart > tolerance:
        return None
    return meilleur


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fichier")
    p.add_argument("--bas", type=float, required=True)
    p.add_argument("--haut", type=float, required=True)
    p.add_argument("--tickets", default=TICKETS)
    p.add_argument("--actif", default="US30")
    p.add_argument("--trou", type=int, default=30,
                   help="minutes hors bande qui terminent une visite")
    p.add_argument("--echantillon", type=int, default=1500)
    a = p.parse_args()
    bas, haut = min(a.bas, a.haut), max(a.bas, a.haut)

    print(SEP)
    print("BASE CFD/FUTURE ET FLUX PAR VISITE -- %s" % os.path.basename(a.fichier))
    print(SEP)
    print()
    print("  Lecture seule. Rien n est ecrit, rien n est envoye.")
    print()

    if not os.path.isfile(a.fichier):
        print("  introuvable : %s" % a.fichier)
        return
    donnees, err = lit_scid(a.fichier)
    if err:
        print("  %s" % err)
        return
    temps, prix, vols, bids, asks, mode, taille = donnees
    print("  %s, %d enregistrement(s), dates en %s"
          % (humain(taille), len(temps),
             "microsecondes" if mode == "micro" else "jours"))
    if not temps:
        print("  fichier vide.")
        return

    # ---------------------------------------------------------------- 1 + 2
    decalage = 0
    base_med = 0.0
    tickets = lit_tickets(a.tickets, a.actif)
    if not tickets:
        print("  %s introuvable ou sans ticket %s." % (a.tickets, a.actif))
        print("  Les etapes 1 et 2 sont sautees : la bande est prise")
        print("  telle quelle, en prix YM. Le resultat ne vaut alors")
        print("  que si tu as deja converti tes niveaux toi-meme.")
        print()
    else:
        ech = tickets[-a.echantillon:] if len(tickets) > a.echantillon else tickets
        print("  %d ticket(s) %s, %d retenus pour le calage"
              % (len(tickets), a.actif, len(ech)))
        print()
        print(SEP)
        print("1. LE DECALAGE HORAIRE -- essaye, pas suppose")
        print(SEP)
        print()
        essais = []
        for demi in range(-24, 29):
            d = demi * 1800
            ecarts = []
            for sec, pcfd in ech:
                py = prix_a(temps, prix, sec + d)
                if py is not None:
                    ecarts.append(pcfd - py)
            if len(ecarts) < max(20, len(ech) // 20):
                continue
            essais.append((ecart_median(ecarts), d, len(ecarts),
                           mediane(ecarts)))
        if not essais:
            print("  aucun decalage ne fait coincider les deux series.")
            print("  Les periodes ne se recouvrent peut-etre pas.")
            print()
        else:
            essais.sort()
            print("     decalage   apparies   base mediane   dispersion")
            print("     " + "-" * 60)
            for disp, d, n, med in essais[:6]:
                print("     %+6.1f h    %7d    %+10.1f    %10.1f"
                      % (d / 3600.0, n, med, disp))
            print()
            disp, decalage, n, base_med = essais[0]
            print("  retenu : %+.1f h  (dispersion %.1f points, la plus faible)"
                  % (decalage / 3600.0, disp))
            deuxieme = essais[1][0] if len(essais) > 1 else None
            if deuxieme and disp > 0 and deuxieme < disp * 1.3:
                print("  ATTENTION : le suivant est presque aussi bon (%.1f)."
                      % deuxieme)
                print("  Le calage n est pas net -- traite la suite avec")
                print("  prudence.")
            print()

            print(SEP)
            print("2. LA BASE, SEMAINE PAR SEMAINE")
            print(SEP)
            print()
            par_sem = {}
            for sec, pcfd in ech:
                py = prix_a(temps, prix, sec + decalage)
                if py is None:
                    continue
                d = datetime.datetime.utcfromtimestamp(sec)
                cle = "%s-S%02d" % (d.strftime("%Y"), d.isocalendar()[1])
                par_sem.setdefault(cle, []).append(pcfd - py)
            print("     semaine     n    base mediane   dispersion")
            print("     " + "-" * 56)
            for cle in sorted(par_sem):
                v = par_sem[cle]
                print("     %-10s %4d    %+10.1f    %10.1f"
                      % (cle, len(v), mediane(v), ecart_median(v)))
            print()
            print("  base retenue pour la conversion : %+.1f points" % base_med)
            print("  (CFD moins future : un CFD au-dessus donne un chiffre")
            print("   positif, et la bande YM est donc plus BASSE)")
            print()

    bas_ym, haut_ym = bas - base_med, haut - base_med
    print(SEP)
    print("3. LES VISITES DE LA BANDE")
    print(SEP)
    print()
    print("  bande CFD demandee : %.1f - %.1f" % (bas, haut))
    print("  bande YM equivalente : %.1f - %.1f" % (bas_ym, haut_ym))
    print()

    dedans = [i for i in range(len(temps)) if bas_ym <= prix[i] <= haut_ym]
    if not dedans:
        print("  le prix YM n est jamais entre dans cette bande.")
        print("  prix parcourus : %.1f a %.1f" % (min(prix), max(prix)))
        return

    trou = a.trou * 60
    visites = []
    debut = dedans[0]
    precedent = dedans[0]
    for i in dedans[1:]:
        if temps[i] - temps[precedent] > trou:
            visites.append((debut, precedent))
            debut = i
        precedent = i
    visites.append((debut, precedent))

    print("  %d enregistrement(s) dans la bande, %d visite(s)"
          % (len(dedans), len(visites)))
    print()
    print("     debut               duree      volume       bid       ask"
          "     delta   part")
    print("     " + "-" * 88)
    dedans_set = set(dedans)
    lignes = []
    for d0, d1 in visites:
        v = b = q = 0
        for i in range(d0, d1 + 1):
            if i in dedans_set:
                v += vols[i]
                b += bids[i]
                q += asks[i]
        duree = (temps[d1] - temps[d0]) / 60.0
        t0 = datetime.datetime.utcfromtimestamp(temps[d0])
        lignes.append((t0, duree, v, b, q, q - b))
    for t0, duree, v, b, q, delta in lignes:
        part = (100.0 * delta / v) if v else 0.0
        marque = "  <<<" if v and abs(part) >= 15 else ""
        print("     %s  %6.0f mn %9d %9d %9d %9d %+6.1f %%%s"
              % (t0.strftime("%Y-%m-%d %H:%M"), duree, v, b, q, delta,
                 part, marque))
    print()
    print("  La colonne part est le delta rapporte au volume de la visite.")
    print("  C est elle qui compte : un gros delta sur un gros volume peut")
    print("  n etre que du bruit, un delta moyen sur peu de volume non.")
    print("  Les visites marquees depassent 15 %.")
    print()

    # --- par heure ---------------------------------------------------------
    print(SEP)
    print("LE MEME FLUX, PAR HEURE (UTC)")
    print(SEP)
    print()
    heures = {}
    for i in dedans:
        h = datetime.datetime.utcfromtimestamp(temps[i]).hour
        s = heures.setdefault(h, [0, 0, 0])
        s[0] += vols[i]
        s[1] += bids[i]
        s[2] += asks[i]
    vmax = max(s[0] for s in heures.values()) or 1
    print("     h UTC     volume       bid       ask     delta   part")
    print("     " + "-" * 76)
    for h in sorted(heures):
        v, b, q = heures[h]
        delta = q - b
        part = (100.0 * delta / v) if v else 0.0
        barre = "#" * int(30.0 * v / vmax)
        print("     %02d:00 %10d %9d %9d %9d %+6.1f %%  %s"
              % (h, v, b, q, delta, part, barre))
    print()
    print(SEP)
    print("  Rien n a ete ecrit, rien n a ete envoye.")
    print(SEP)


if __name__ == "__main__":
    main()
