# -*- coding: utf-8 -*-
r"""
lire_scid.py -- l orderflow REEL de SierraChart, sans passer par un
export graphique

  python lire_scid.py --schema ESU26.CME.scid
  python lire_scid.py ESU26.CME.scid --pas 60
  python lire_scid.py --dossier "C:\SierraChart\Data" --pas 60

POURQUOI LIRE LE FICHIER PLUTOT QUE L EXPORTER

    SierraChart ecrit son intraday dans des fichiers `.scid`, un par
    symbole. Le format est binaire, documente et stable :

        en-tete   56 octets
        record    40 octets, repete jusqu a la fin du fichier

            double  horodatage   microsecondes depuis 1899-12-30 UTC
            float   Open, High, Low, Close
            uint32  NumTrades
            uint32  TotalVolume
            uint32  BidVolume
            uint32  AskVolume

    `BidVolume` et `AskVolume` SEPARES : c est exactement ce que MT5 ne
    peut pas donner. Sur des CFD d indices, MT5 fournit un volume de
    TICKS -- un compteur de changements de prix -- et son "delta" est
    donc une inference. Ici, ce sont des contrats echanges.

    Copier un fichier ne demande aucune connaissance de SierraChart, ne
    peut pas se tromper de menu, et n oublie aucune colonne. Un export
    graphique, si.

SUR DU TICK, LES CHAMPS OHLC NE VEULENT PAS DIRE OHLC

    L editeur de donnees de SierraChart le montre noir sur blanc sur un
    enregistrement au tick :

        Open      0          toujours nul
        High/Ask  7819.25    ce n est pas un plus haut, c est l ASK
        Low/Bid   7819       ce n est pas un plus bas, c est le BID
        Last      7819       le prix reellement echange

    Une premiere version prenait `Open` comme ouverture de barre : elle
    aurait ecrit ZERO dans toute la colonne. L ouverture, le plus haut
    et le plus bas d une barre se construisent donc a partir de `Close`
    -- le seul champ qui porte un prix de transaction -- et les deux
    autres servent a mesurer le SPREAD au moment de l echange, ce
    qu aucune de nos autres sources ne donne.

CE FICHIER VERIFIE LE FORMAT, IL NE LE SUPPOSE PAS

    L en-tete porte lui-meme `HeaderSize` et `RecordSize`. On les LIT
    et on les compare a 56 et 40. S ils different, on s arrete et on
    l affiche : decoder 40 octets a la fois dans un fichier qui en
    utilise 44 produirait des millions de lignes plausibles et fausses.

    C est la meme regle que pour les CSV : le format se lit dans les
    donnees, jamais dans mon souvenir.

LE CONTROLE QUI COMPTE : bid + ask == total

    Sur des donnees au TICK, `BidVolume + AskVolume` doit egaler
    `TotalVolume`. Si ce n est pas le cas, c est que le fichier est
    AGREGE -- typiquement parce que `Intraday Data Storage Time Unit`
    n etait pas sur "1 Tick" au telechargement. Le fichier reste
    lisible, mais son delta a perdu de la finesse, et il faut le savoir
    avant d en tirer un CVD. `--schema` mesure ce taux d accord.

CE QU IL ECRIT

    Un CSV par symbole, agrege au pas demande :

        ts;open;high;low;close;trades;volume;bid_vol;ask_vol;delta;cvd

    `delta` = ask - bid sur la barre. `cvd` = somme cumulee du delta
    depuis le debut de la JOURNEE -- jamais a cheval sur la nuit, une
    somme cumulee qui traverse une seance ne veut plus rien dire.

LECTEUR SEUL. Il ouvre les `.scid` en lecture binaire et ecrit des CSV
dans son propre dossier de sortie. Il ne touche a rien d autre.
"""
import argparse
import io
import os
import struct
import sys
import datetime as dt

SORTIE = os.path.join("cartes", "scid")
ENTETE = 56
RECORD = 40
# Les horodatages SierraChart comptent les microsecondes depuis cette
# date. Ce n est pas l epoch Unix : se tromper d origine donnerait des
# dates en 1970 ou en 2170, ce qui se voit -- mais un decalage de
# quelques heures ne se verrait pas, d ou le --schema.
ORIGINE = dt.datetime(1899, 12, 30, 0, 0, 0)
FMT = "<d4f4I"

LARG = 100


def entete(f):
    """Lit l en-tete et rend (taille_entete, taille_record, version) ou
    une erreur. On ne fait AUCUNE hypothese : les tailles viennent du
    fichier."""
    brut = f.read(ENTETE)
    if len(brut) < ENTETE:
        return None, "fichier trop court pour contenir un en-tete"
    ident, taille_h, taille_r, version = struct.unpack("<IIIH", brut[:14])
    # "SCID" en petit-boutien
    attendu = struct.unpack("<I", b"SCID")[0]
    if ident != attendu:
        return None, ("signature %s au lieu de SCID -- ce n est pas un "
                      "fichier .scid" % hex(ident))
    return {"entete": taille_h, "record": taille_r,
            "version": version}, None


def horo(micro):
    try:
        return ORIGINE + dt.timedelta(microseconds=micro)
    except (OverflowError, OSError, ValueError):
        return None


def records(f, taille_r, saut=0):
    """Un generateur sur les enregistrements. On lit par blocs pour ne
    pas faire un appel systeme par record : un .scid au tick peut faire
    plusieurs Go."""
    n = 0
    bloc = 65536 - (65536 % taille_r)
    while True:
        brut = f.read(bloc)
        if not brut:
            return
        for i in range(0, len(brut) - taille_r + 1, taille_r):
            n += 1
            if saut and n % saut:
                continue
            yield struct.unpack(FMT, brut[i:i + taille_r])


def schema(chemin, combien):
    print("=" * LARG)
    print("SCHEMA : %s" % chemin)
    print("=" * LARG)
    taille = os.path.getsize(chemin)
    with io.open(chemin, "rb") as f:
        h, err = entete(f)
        if err:
            print("  KO : %s" % err)
            return 1
        print("  taille du fichier : %.1f Mo" % (taille / 1e6))
        print("  en-tete annonce   : %d octets (attendu %d)"
              % (h["entete"], ENTETE))
        print("  record annonce    : %d octets (attendu %d)"
              % (h["record"], RECORD))
        print("  version           : %d" % h["version"])
        if h["entete"] != ENTETE or h["record"] != RECORD:
            print()
            print("  ARRET. Les tailles annoncees ne sont pas celles que")
            print("  je sais decoder. Decoder quand meme produirait des")
            print("  millions de lignes plausibles et fausses. Envoyez-moi")
            print("  ces deux nombres et j adapte le lecteur.")
            return 1
        n = (taille - h["entete"]) // h["record"]
        print("  %d enregistrements." % n)
        print()
        print("  %-21s %9s %9s %9s %8s %7s %7s %6s"
              % ("horodatage", "open", "last", "ask-bid", "volume",
                 "bid", "ask", "b+a=t"))
        f.seek(h["entete"])
        vus = accord = 0
        premiers = []
        for r in records(f, h["record"]):
            t, o, hi, lo, c, nt, tv, bv, av = r
            vus += 1
            if bv + av == tv:
                accord += 1
            if len(premiers) < combien:
                d = horo(t)
                premiers.append((d, o, c, hi - lo, tv, bv, av,
                                 bv + av == tv))
            if vus >= 200000:
                break
        for d, o, c, sp, tv, bv, av, ok in premiers:
            print("  %-21s %9.2f %9.2f %9.2f %8d %7d %7d %6s"
                  % (d.strftime("%Y-%m-%d %H:%M:%S") if d else "?",
                     o, c, sp, tv, bv, av, "oui" if ok else "NON"))
        print()
        print("  La colonne `open` doit valoir 0 sur du tick : c est")
        print("  normal, SierraChart n y met rien. Si elle porte un prix,")
        print("  le fichier n est PAS au tick.")
        print()
        print("  Sur %d enregistrements lus, bid+ask == total dans %.1f %%"
              % (vus, 100.0 * accord / max(1, vus)))
        print("  des cas.")
        if accord < vus * 0.98:
            print()
            print("  ATTENTION : le fichier est AGREGE, pas au tick. Le")
            print("  reglage `Intraday Data Storage Time Unit` n etait")
            print("  pas sur \"1 Tick\" au telechargement. Le delta reste")
            print("  calculable mais il a perdu de la finesse -- a savoir")
            print("  avant d en tirer un CVD et de le comparer a MT5.")
        else:
            print()
            print("  Coherent avec des donnees au tick : le delta est")
            print("  exploitable tel quel.")
        print()
        print("  LE FUSEAU RESTE A ETABLIR. SierraChart horodate en UTC.")
        print("  Comparez la premiere ligne d une seance connue a nos")
        print("  cycles avant de croiser quoi que ce soit : deux heures")
        print("  d ecart passeraient inapercues et fausseraient tout.")
    return 0


def agrege(chemin, dest, pas, saut):
    """Agrege les enregistrements en barres de `pas` secondes."""
    with io.open(chemin, "rb") as f:
        h, err = entete(f)
        if err:
            return None, err
        if h["entete"] != ENTETE or h["record"] != RECORD:
            return None, ("tailles inattendues (%d / %d)"
                          % (h["entete"], h["record"]))
        f.seek(h["entete"])
        g = io.open(dest, "w", encoding="utf-8", newline="")
        g.write("ts;open;high;low;close;trades;volume;bid_vol;ask_vol;"
                "delta;cvd;spread_moy\n")
        cle = None
        b = None
        cvd = 0.0
        jour = None
        n = 0
        for r in records(f, h["record"], saut):
            t, o, hi, lo, c, nt, tv, bv, av = r
            d = horo(t)
            if d is None:
                continue
            k = int((d - ORIGINE).total_seconds() // pas)
            if k != cle:
                if b:
                    n += ecris(g, b)
                # Le CVD repart de zero a chaque journee : une somme
                # cumulee qui traverse la nuit ne veut plus rien dire.
                if jour != d.date():
                    jour = d.date()
                    cvd = 0.0
                cle = k
                # `o` (le champ Open) vaut 0 sur du tick : l ouverture
                # de la barre est le PRIX ECHANGE du premier
                # enregistrement, c est-a-dire `c`.
                b = {"ts": ORIGINE + dt.timedelta(seconds=k * pas),
                     "o": c, "h": c, "l": c, "c": c,
                     "nt": 0, "tv": 0, "bv": 0, "av": 0, "cvd": 0.0,
                     "sp": 0.0, "nsp": 0}
            # hi = ask, lo = bid : leur difference est le spread au
            # moment de l echange, pas une amplitude.
            if hi > 0 and lo > 0 and hi >= lo:
                b["sp"] += (hi - lo)
                b["nsp"] += 1
            b["h"] = max(b["h"], c)
            b["l"] = min(b["l"], c)
            b["c"] = c
            b["nt"] += nt
            b["tv"] += tv
            b["bv"] += bv
            b["av"] += av
            cvd += (av - bv)
            b["cvd"] = cvd
        if b:
            n += ecris(g, b)
        g.close()
    return n, None


def ecris(g, b):
    sp = (b["sp"] / b["nsp"]) if b["nsp"] else 0.0
    g.write("%s;%.2f;%.2f;%.2f;%.2f;%d;%d;%d;%d;%d;%.0f;%.4f\n"
            % (b["ts"].strftime("%Y-%m-%d %H:%M:%S"),
               b["o"], b["h"], b["l"], b["c"], b["nt"], b["tv"],
               b["bv"], b["av"], b["av"] - b["bv"], b["cvd"], sp))
    return 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fichier", nargs="?", default=None)
    p.add_argument("--dossier", default=None,
                   help="traite tous les .scid d un dossier")
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--pas", type=int, default=60,
                   help="taille des barres, en secondes")
    p.add_argument("--saut", type=int, default=0,
                   help="ne garde qu un enregistrement sur N")
    p.add_argument("--schema", action="store_true")
    p.add_argument("--lignes", type=int, default=12)
    a = p.parse_args()

    cibles = []
    if a.fichier:
        cibles.append(a.fichier)
    if a.dossier:
        for n in sorted(os.listdir(a.dossier)):
            if n.lower().endswith(".scid"):
                cibles.append(os.path.join(a.dossier, n))
    if not cibles:
        print("KO : donner un fichier .scid ou --dossier.")
        return 1

    if a.schema:
        for c in cibles[:3]:
            schema(c, a.lignes)
            print()
        return 0

    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)
    for c in cibles:
        nom = os.path.basename(c)[:-5]
        dest = os.path.join(a.sortie, "of_%s.csv" % nom)
        n, err = agrege(c, dest, a.pas, a.saut)
        if err:
            print("  %-28s KO : %s" % (nom, err))
            continue
        print("  %-28s %7d barres de %d s -> %d Ko"
              % (nom, n, a.pas, os.path.getsize(dest) / 1000))
    print()
    print("Sortie : %s" % a.sortie)
    print("Rien n a ete analyse : c est une transcription.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
