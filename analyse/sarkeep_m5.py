# -*- coding: utf-8 -*-
"""
sarkeep_m5.py -- le SARKEEP en M5, qui n existe pas dans la stack

  python sarkeep_m5.py
  python sarkeep_m5.py --actifs US30 US100 US500 --intervalle 10

LA REGLE, TELLE QU ELLE A ETE DECRITE

    Une jambe de hausse : le SAR est sous le prix, ca monte. Le dernier
    point SAR finit par etre touche, le SAR bascule AU-DESSUS du prix.

    On retient alors comme FRONTIERE le dernier point SAR qui etait sous
    le prix -- le SAR shift=1 au moment de la bascule.

    Tant que le prix reste au-dessus de cette frontiere, on conserve les
    achats et on invalide les ventes, MEME SI le SAR courant est
    baissier. Le SARKEEP est donc un cliquet de memoire : il empeche un
    simple retournement de SAR d invalider une tendance.

    LA SORTIE DEMANDE DEUX CONDITIONS REUNIES :

        1. le SAR M5 s est retourne         (frontiere tracee)
        2. ET le prix casse cette frontiere (encaissement)

    Le retournement seul ne suffit pas. C est ce qui distingue un vrai
    reverse d une respiration -- et c est ce que le M1 seul ne dit pas.

POURQUOI UN MODULE A PART

    sar_anchor calcule le SARKEEP en M1 et lui seul. SarKeep3 n est pas
    un autre pas de temps : c est le meme M1 avec un shift de 3 bougies
    (seuil plus strict, SAR plus eloigne du prix). Le M5 n existe nulle
    part, il faut le construire.

    On le construit A COTE, pas dans sar_anchor. Ce module lit des
    bougies, calcule, ecrit un CSV. Il ne touche a rien de vivant.

DEUX EVENEMENTS, PAS UN

    FLIP      le SAR s est retourne, la frontiere est tracee
    CASSURE   le prix a traverse la frontiere -> la regle declenche

    Les deux sont enregistres avec l instantane des positions ouvertes,
    parce qu ils ne se mesurent pas pareil : le premier prepare, le
    second decide.

    Un evenement qui survient sans aucune position est ecrit lui aussi.
    Un signal qui se declenche a plat ne rapporte rien, et l oublier
    surestimerait sa valeur.

LES PARAMETRES DU SAR

    AF_DEPART / AF_PAS / AF_MAX ci-dessous, aux valeurs de Wilder
    (0,02 / 0,02 / 0,2). Le module les IMPRIME au demarrage.

    Si sar_anchor utilise d autres valeurs en M1, il faut les recopier
    ici : deux SAR de parametres differents ne se comparent pas, et
    toute la question est justement de comparer M1 et M5.

LECTURE SEULE. Aucun ordre. Un fichier par jour.
Meme schema de colonnes que sarkeep_gel.py -> une seule analyse pour les
deux pas de temps, avec la colonne `tf` pour les distinguer.

LE PROTOCOLE, POSE AVANT LA COLLECTE
    Unite      : la seance.
    Fenetre    : du 13/08 au 31/08.
    Verdict    : 01/09.
    Critere    : sur les CASSURES, la somme (latent_au_signal - realise)
                 des positions qui suivaient le mouvement doit etre
                 positive, test du signe a p <= 0,05 sur les seances.
    Comparateur: le M1 sur les memes instants, et les positions qui NE
                 suivaient PAS le mouvement.
    Ecrit d avance pour pouvoir REFUTER.
"""
import argparse
import csv
import io
import os
import sys
import time
from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    print("KO : MetaTrader5 introuvable dans cet interpreteur.")
    sys.exit(1)

AF_DEPART = 0.02
AF_PAS = 0.02
AF_MAX = 0.20

ACTIFS = ["US30", "US100", "US500"]
DOSSIER = os.path.join("docs", "sarkeep_gel")
BOUGIES = 400
COLONNES = ["ts", "tf", "evenement", "actif_flip", "de", "vers", "sarkeep",
            "sarkeep3", "sarkeep_prev", "confirms", "prix_signal",
            "ticket", "magic", "symbole", "sens", "suivait_le_mouvement",
            "prix_open", "prix_courant", "sl", "tp", "profit_latent",
            "pic_pts", "age_s", "n_positions"]


def sar_officiel(rates):
    """Le _compute_sar de sar_anchor, s il accepte nos bougies.

    On prefere TOUJOURS celui-la : le but est de comparer M1 et M5, et
    deux implementations qui divergeraient d un detail invalideraient la
    comparaison avant meme qu elle commence. Le calcul de secours
    ci-dessous n existe que si l import echoue -- et le module DIT lequel
    il utilise au demarrage.
    """
    try:
        import sar_anchor as _sa
    except Exception:
        return None
    fn = getattr(_sa, "_compute_sar", None)
    if not callable(fn):
        return None
    try:
        out = fn(rates)
    except Exception:
        return None
    # Forme attendue : une suite indexable dont [0] porte la valeur SAR.
    if not out or len(out) < 3:
        return None
    try:
        float(out[-1][0])
    except (TypeError, IndexError, ValueError):
        return None
    return out


def sar_serie(hauts, bas):
    """Parabolic SAR de Wilder, calcul de secours. Rend [(sar, sens)].

    sens vaut 'BULL' quand le SAR est SOUS le prix (tendance haussiere).
    N est utilise que si sar_anchor._compute_sar n est pas exploitable.
    """
    n = len(hauts)
    if n < 3:
        return []
    haussier = hauts[1] >= hauts[0]
    sar = bas[0] if haussier else hauts[0]
    ep = hauts[0] if haussier else bas[0]
    af = AF_DEPART
    out = [(sar, "BULL" if haussier else "BEAR")]

    for i in range(1, n):
        sar = sar + af * (ep - sar)
        # Le SAR ne peut pas entrer dans les deux bougies precedentes.
        if haussier:
            sar = min(sar, bas[i - 1], bas[max(0, i - 2)])
        else:
            sar = max(sar, hauts[i - 1], hauts[max(0, i - 2)])

        if haussier:
            if bas[i] < sar:                 # bascule en baissier
                haussier = False
                sar = ep
                ep = bas[i]
                af = AF_DEPART
            elif hauts[i] > ep:
                ep = hauts[i]
                af = min(af + AF_PAS, AF_MAX)
        else:
            if hauts[i] > sar:               # bascule en haussier
                haussier = True
                sar = ep
                ep = hauts[i]
                af = AF_DEPART
            elif bas[i] < ep:
                ep = bas[i]
                af = min(af + AF_PAS, AF_MAX)

        out.append((sar, "BULL" if haussier else "BEAR"))
    return out


def ouvrir_sortie(dossier):
    os.makedirs(dossier, exist_ok=True)
    ch = os.path.join(dossier, "sarkeep_m5_%s.csv"
                      % datetime.now().strftime("%Y%m%d"))
    neuf = not os.path.exists(ch) or os.path.getsize(ch) == 0
    f = io.open(ch, "a", encoding="utf-8", newline="")
    w = csv.DictWriter(f, fieldnames=COLONNES)
    if neuf:
        w.writeheader()
        f.flush()
    return ch, f, w


def meme_actif(symbole, actif):
    a, b = symbole.upper(), actif.upper()
    return a.startswith(b) or b.startswith(a)


def suivait(sens, de):
    if de == "BULL":
        return sens == "ACHAT"
    if de == "BEAR":
        return sens == "VENTE"
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--actifs", nargs="*", default=ACTIFS)
    p.add_argument("--dossier", default=DOSSIER)
    p.add_argument("--intervalle", type=float, default=10.0)
    p.add_argument("--bougies", type=int, default=BOUGIES)
    a = p.parse_args()

    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        return 1

    ch, f, w = ouvrir_sortie(a.dossier)
    # Un essai a blanc dit tout de suite quel calcul on utilise, plutot
    # que de le decouvrir dans les chiffres trois semaines plus tard.
    _t = mt5.copy_rates_from_pos(a.actifs[0], mt5.TIMEFRAME_M5, 0, 60)
    officiel = _t is not None and sar_officiel(_t[:-1]) is not None

    print("=" * 78)
    print(" SCALP-EA / SARKEEP M5 -- CONSTRUIT ET OBSERVE, N AGIT PAS")
    print("=" * 78)
    print("actifs     : %s" % ", ".join(a.actifs))
    if officiel:
        print("SAR        : sar_anchor._compute_sar -- MEME calcul que le M1")
    else:
        print("SAR        : calcul de secours, af %.3f / %.3f / %.3f"
              % (AF_DEPART, AF_PAS, AF_MAX))
        print("             sar_anchor._compute_sar n a pas accepte nos")
        print("             bougies. Les valeurs sont celles de Wilder, et")
        print("             sar_anchor utilise les memes (lignes 82-84),")
        print("             mais l implementation peut differer d un detail.")
    print("sortie     : %s" % ch)
    print()
    print("FLIP    = le SAR se retourne, la frontiere est tracee")
    print("CASSURE = le prix traverse la frontiere -> la regle declenche")
    print()
    print("Aucun ordre n est envoye. Ctrl+C pour arreter.")
    print()

    etat = {}      # actif -> {sens, frontiere, sk3, sk_prev, cassee}
    debut = {}     # ticket -> premiere vue
    n_ev = n_lig = 0

    def ecrire(actif, ev, de, vers, sk, sk3, skp, prix):
        nonlocal n_ev, n_lig
        n_ev += 1
        pos = mt5.positions_get() or []
        base = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tf": "M5", "evenement": ev, "actif_flip": actif,
                "de": de, "vers": vers,
                "sarkeep": round(sk, 5) if sk else "",
                "sarkeep3": round(sk3, 5) if sk3 else "",
                "sarkeep_prev": round(skp, 5) if skp else "",
                "confirms": "VENTE" if vers == "BEAR" else "ACHAT",
                "prix_signal": round(prix, 5),
                "n_positions": len(pos)}
        if not pos:
            r = dict(base)
            for c in COLONNES:
                r.setdefault(c, "")
            w.writerow(r)
            n_lig += 1
            f.flush()
            return
        for q in pos:
            sens = "ACHAT" if q.type == 0 else "VENTE"
            si = mt5.symbol_info(q.symbol)
            pt = si.point if si and si.point else 0.01
            pic = ((q.price_current - q.price_open) if sens == "ACHAT"
                   else (q.price_open - q.price_current)) / pt
            t0 = debut.setdefault(q.ticket, time.time())
            sv = suivait(sens, de) if meme_actif(q.symbol, actif) else None
            r = dict(base)
            r.update({"ticket": q.ticket, "magic": q.magic,
                      "symbole": q.symbol, "sens": sens,
                      "suivait_le_mouvement": ("" if sv is None
                                               else ("oui" if sv else "non")),
                      "prix_open": q.price_open,
                      "prix_courant": q.price_current,
                      "sl": q.sl, "tp": q.tp,
                      "profit_latent": round(q.profit, 2),
                      "pic_pts": round(max(0.0, pic), 1),
                      "age_s": int(time.time() - t0)})
            w.writerow(r)
            n_lig += 1
        f.flush()

    try:
        while True:
            for actif in a.actifs:
                r = mt5.copy_rates_from_pos(actif, mt5.TIMEFRAME_M5, 0,
                                            a.bougies)
                if r is None or len(r) < 10:
                    continue
                # On ignore la bougie en cours : elle bouge encore.
                hauts = [float(x["high"]) for x in r[:-1]]
                bas = [float(x["low"]) for x in r[:-1]]
                clot = [float(x["close"]) for x in r[:-1]]
                brut = sar_officiel(r[:-1]) if officiel else None
                if brut is not None:
                    # sar_anchor rend la valeur en [0] ; le sens s en
                    # deduit de la position du SAR face au prix, ce qui
                    # ne suppose rien de sa forme interne.
                    serie = [(float(s[0]),
                              "BULL" if float(s[0]) < clot[i] else "BEAR")
                             for i, s in enumerate(brut)]
                else:
                    serie = sar_serie(hauts, bas)
                if len(serie) < 5:
                    continue

                sens_now = serie[-1][1]
                e = etat.get(actif)
                if e is None:
                    etat[actif] = {"sens": sens_now, "frontiere": None,
                                   "sk3": None, "skp": None, "cassee": True}
                    continue

                if sens_now != e["sens"]:
                    # Bascule : la frontiere est le dernier SAR de l ancien
                    # sens, c est-a-dire shift=1. shift=3 est plus eloigne
                    # du prix, donc plus indulgent.
                    sk = serie[-2][0]
                    sk3 = serie[-4][0] if len(serie) >= 4 else sk
                    skp = e["frontiere"]
                    e.update({"sens": sens_now, "frontiere": sk, "sk3": sk3,
                              "skp": skp, "cassee": False})
                    ecrire(actif, "FLIP", "BULL" if sens_now == "BEAR"
                           else "BEAR", sens_now, sk, sk3, skp, clot[-1])
                    continue

                # Cassure : le SAR est deja retourne, et le prix traverse.
                if e["frontiere"] and not e["cassee"]:
                    fini = "BULL" if e["sens"] == "BEAR" else "BEAR"
                    casse = (clot[-1] < e["frontiere"] if fini == "BULL"
                             else clot[-1] > e["frontiere"])
                    if casse:
                        e["cassee"] = True
                        ecrire(actif, "CASSURE", fini, e["sens"],
                               e["frontiere"], e["sk3"], e["skp"], clot[-1])
            if n_ev and n_ev % 10 == 0:
                try:
                    print("[%s] %d evenements, %d lignes"
                          % (datetime.now().strftime("%H:%M:%S"), n_ev, n_lig))
                except Exception:
                    pass
            time.sleep(a.intervalle)

    except KeyboardInterrupt:
        print()
        print("Arret demande.")
    finally:
        try:
            print("%d evenements, %d lignes." % (n_ev, n_lig))
            print("sortie : %s" % ch)
            print()
            print("Le verdict demande le P&L REALISE : joindre sur le ticket")
            print("avec docs\\rails_trades\\tickets_rails.jsonl apres la")
            print("cloture, et comparer profit_latent au resultat final.")
        except Exception:
            pass
        f.close()
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
