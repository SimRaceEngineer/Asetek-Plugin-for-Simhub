# -*- coding: utf-8 -*-
r"""
collecteur_10s.py -- un flux propre a 10 s, sans toucher a la stack

  python collecteur_10s.py --sonde
  python collecteur_10s.py --jusqu-au 2026-09-01
  python collecteur_10s.py --pas 10 --url http://127.0.0.1:8095/raw

LA DEMANDE, LE 17/08

    "Si tu dois corriger les flux pour qu on log toutes les 10 s jusqu
    a debut septembre, fais-le si on obtient un meilleur flux
    d information."

CE QUE JE N AI PAS FAIT, ET POURQUOI

    Je n ai PAS modifie l ecriture de cycles.jsonl.

    L audit de cadence donne 48 % de part utile mediane, avec des trous
    allant jusqu a plusieurs heures. Mais le detail qui compte est
    ailleurs : les SEULES journees regulieres (95 a 100 %) sont le
    08/08, le 09/08 et le 15/08 -- des journees de MARCHE FERME. Le
    flux se troue quand le marche est ouvert, donc quand la stack
    travaille.

    Ca oriente vers une periode qui est celle de la BOUCLE DU MOTEUR,
    pas celle d un ecrivain paresseux. Si c est le cas, "logger toutes
    les 10 s" voudrait dire toucher la boucle de trading en plein gel :
    on changerait le comportement de la stack pour ameliorer une
    mesure. C est l inverse de ce qu on veut.

    Tant que la cause n est pas identifiee, modifier serait un pari sur
    du code vivant.

CE QUE FAIT CE FICHIER A LA PLACE

    Il interroge le panneau en LECTURE SEULE, a intervalle fixe, et
    ecrit SON PROPRE fichier. Il ne modifie aucun module de la stack,
    ne redemarre aucun service, ne touche pas a MT5, n ecrit dans aucun
    fichier existant. On peut l arreter par Ctrl-C a n importe quel
    moment sans consequence.

    Resultat identique pour nous -- un flux regulier a 10 s d ici
    septembre -- et risque nul pour la stack.

LE MODE SONDE EST OBLIGATOIRE AVANT LA PREMIERE COLLECTE

    `--sonde` fait UN appel, montre le code HTTP, la taille, le type et
    les cles de premier niveau, et n ecrit rien.

    On n ecrit pas un format de sortie contre une charge utile qu on n a
    pas regardee. C est la meme erreur que "le nom d un champ se lit
    dans les donnees, jamais dans le code qui les ecrit", et elle a
    deja coute une passe complete sur 34 Go.

CE QU IL ECRIT

    cartes\collecte\collecte_<jour>.jsonl -- une ligne JSON par appel :

        ts        l horodatage local de l APPEL, pas celui du serveur
        ms        duree de l appel en millisecondes
        ok        1 si la reponse a ete lue, 0 sinon
        err       le message d erreur le cas echeant
        data      la charge utile telle quelle

    L horodatage est celui de l appel parce que c est le seul dont on
    connaisse la source. Si la charge utile en porte un autre, on aura
    les deux et on pourra comparer -- ce qui est justement le genre de
    verification qui manquait jusqu ici.

    Un fichier par journee, ouvert en AJOUT. Relancer le collecteur ne
    detruit rien.

IL S AUDITE LUI-MEME

    A l arret, il imprime son propre pas median, son p90 et son plus
    grand trou. Un collecteur qui pretend faire du 10 s sans le
    verifier serait exactement le probleme qu il est cense resoudre.
    Le fichier produit se relit avec audit_cadence.py.

LECTEUR SEUL vis-a-vis de la stack. Il n ecrit que sous cartes\collecte\.
"""
import argparse
import io
import json
import os
import sys
import time
import datetime as dt

try:
    from urllib.request import urlopen
except ImportError:                                     # python 2
    from urllib2 import urlopen

URL = "http://127.0.0.1:8095/raw"
SORTIE = os.path.join("cartes", "collecte")
LARG = 100


def maintenant():
    return dt.datetime.now()


def appelle(url, delai):
    """Un appel, avec sa duree. Ne leve jamais : une erreur reseau est
    une donnee, pas un arret. Un collecteur qui meurt a la premiere
    coupure ne collecte rien la nuit."""
    t0 = time.time()
    try:
        r = urlopen(url, timeout=delai)
        brut = r.read()
        ms = (time.time() - t0) * 1000.0
        try:
            brut = brut.decode("utf-8", "replace")
        except AttributeError:
            pass
        return brut, ms, None
    except Exception as e:
        return None, (time.time() - t0) * 1000.0, "%s: %s" % (
            type(e).__name__, e)


def sonde(url, delai):
    print("=" * LARG)
    print("SONDE -- un appel, rien d ecrit")
    print("=" * LARG)
    print("  url    : %s" % url)
    brut, ms, err = appelle(url, delai)
    print("  duree  : %.0f ms" % ms)
    if err:
        print("  ERREUR : %s" % err)
        print()
        print("  Si le panneau tourne, verifier l url : les routes du")
        print("  8095 sont nombreuses et `/raw` n est peut-etre pas celle")
        print("  qui porte les prix. Essayer --url avec une autre route.")
        return 1
    print("  taille : %d caracteres" % len(brut))
    try:
        d = json.loads(brut)
    except ValueError:
        print("  type   : ce n est pas du JSON")
        print()
        print("  Debut de la reponse :")
        print("  " + brut[:400].replace("\n", "\n  "))
        print()
        print("  Une page HTML ne se collecte pas ligne par ligne. Il")
        print("  faut une route qui rende du JSON -- sinon on stockerait")
        print("  des kilo-octets de mise en page.")
        return 1
    print("  type   : JSON %s" % type(d).__name__)
    if isinstance(d, dict):
        print("  %d cle(s) de premier niveau :" % len(d))
        ligne = "    "
        for k in sorted(d):
            if len(ligne) + len(str(k)) > LARG - 4:
                print(ligne)
                ligne = "    "
            ligne += str(k) + "  "
        if ligne.strip():
            print(ligne)
        print()
        print("  Apercu :")
        for k in sorted(d)[:12]:
            v = d[k]
            if isinstance(v, dict):
                apercu = "{%s}" % ", ".join(sorted(v)[:6])
            elif isinstance(v, list):
                apercu = "[%d element(s)]" % len(v)
            else:
                apercu = repr(v)
            print("    %-24s %s" % (k, apercu[:64]))
    print()
    print("  Rien n a ete ecrit. Relancer sans --sonde pour collecter.")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=URL)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--pas", type=float, default=10.0,
                   help="secondes entre deux appels")
    p.add_argument("--delai", type=float, default=5.0,
                   help="delai maximal d un appel, en secondes")
    p.add_argument("--jusqu-au", default=None,
                   help="AAAA-MM-JJ ; s arrete a minuit ce jour-la")
    p.add_argument("--sonde", action="store_true")
    a = p.parse_args()

    if a.sonde:
        return sonde(a.url, a.delai)

    fin = None
    if a.jusqu_au:
        try:
            fin = dt.datetime.strptime(a.jusqu_au, "%Y-%m-%d")
        except ValueError:
            print("KO : --jusqu-au attend AAAA-MM-JJ.")
            return 1
        if fin <= maintenant():
            print("KO : %s est deja passe." % a.jusqu_au)
            return 1

    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)

    print("=" * LARG)
    print("COLLECTEUR -- lecture seule, ecrit sous %s" % a.sortie)
    print("=" * LARG)
    print("  url %s, un appel toutes les %.0f s." % (a.url, a.pas))
    print("  fin %s" % (fin.strftime("%Y-%m-%d %H:%M")
                        if fin else "aucune, Ctrl-C pour arreter"))
    print("  Il ne modifie aucun fichier de la stack et ne touche a")
    print("  aucun processus. Ctrl-C est sans consequence.")
    print()

    n = ok = ko = 0
    ts_prec = None
    ecarts = []
    f = None
    jour = None
    t_suivant = time.time()
    try:
        while True:
            t = maintenant()
            if fin and t >= fin:
                print("\n  Date de fin atteinte.")
                break
            j = t.strftime("%Y-%m-%d")
            if j != jour:
                if f:
                    f.close()
                # ouverture en AJOUT : relancer le collecteur ne
                # detruit jamais ce qui a deja ete collecte.
                f = io.open(os.path.join(a.sortie, "collecte_%s.jsonl" % j),
                            "a", encoding="utf-8")
                jour = j
            brut, ms, err = appelle(a.url, a.delai)
            rec = {"ts": t.strftime("%Y-%m-%d %H:%M:%S"),
                   "ms": round(ms, 1), "ok": 0 if err else 1}
            if err:
                rec["err"] = err
                ko += 1
            else:
                ok += 1
                try:
                    rec["data"] = json.loads(brut)
                except ValueError:
                    rec["data"] = brut[:20000]
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
            if ts_prec is not None:
                ecarts.append((t - ts_prec).total_seconds())
            ts_prec = t
            if n % 30 == 0:
                sys.stdout.write("\r  %d appels, %d ok, %d en erreur, "
                                 "dernier %.0f ms" % (n, ok, ko, ms))
                sys.stdout.flush()
            # On vise une GRILLE, pas un sleep fixe : sleep(10) apres un
            # appel de 400 ms donne un pas de 10,4 s qui derive. La
            # grille garde le pas constant meme si les appels ralentissent.
            t_suivant += a.pas
            r = t_suivant - time.time()
            if r < 0:
                t_suivant = time.time()
            else:
                time.sleep(r)
    except KeyboardInterrupt:
        print("\n  Arret demande.")
    finally:
        if f:
            f.close()

    print()
    print("=" * LARG)
    print("CE QUE LE COLLECTEUR A REELLEMENT FAIT")
    print("=" * LARG)
    print("  %d appels, %d ok, %d en erreur." % (n, ok, ko))
    if ecarts:
        e = sorted(ecarts)
        print("  pas median %.1f s, p90 %.1f s, max %.1f s."
              % (e[len(e) // 2], e[int(0.9 * (len(e) - 1))], e[-1]))
        print()
        print("  Un collecteur qui annonce 10 s sans le mesurer serait")
        print("  exactement le probleme qu il est cense resoudre. Le")
        print("  fichier produit se relit avec audit_cadence.py.")
    if ko:
        print()
        print("  Les %d erreurs sont ECRITES dans le fichier avec leur"
              % ko)
        print("  message : un trou sans explication ne se distingue pas")
        print("  d un arret, et c est ce qui nous a coute une journee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
