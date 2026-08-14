# -*- coding: utf-8 -*-
"""
patch_papier_contexte.py -- enregistrer le CONTEXTE, a l entree et a la
                            sortie, avant que quinze jours ne passent

  python patch_papier_contexte.py --essai
  python patch_papier_contexte.py

CE QUI MANQUE AUJOURD HUI, ET POURQUOI C EST LE SEUL POINT URGENT

    cellule() rend le dict complet de churn_regime._analyze. La boucle
    n en garde que DEUX champs -- `ignition` et `dir` -- et jette tout
    le reste : le regime, le mtf, le HLC, la bande, tout. Les dix-sept
    champs ecrits par _jambe() ne contiennent aucun element de contexte.

    Consequence si on ne fait rien : dans quinze jours il y aura quinze
    jours d EUR et RIEN pour les trier. La question "le x10 est-il bon
    quand il tombe en MIXED avec un HLC qui s ecarte, en seance Asie"
    sera alors sans reponse -- non pas faute d analyse, faute de donnee.

    Et ca NE SE RATTRAPE PAS. Les barres se retelechargent ; l etat de
    la cellule a la seconde de l entree, non. Un rejeu ne redonne pas
    le meme dict : il redonne un dict plausible. Chaque nuit sans ce
    patch est une nuit perdue pour toujours.

CE QUE LE PATCH AJOUTE -- CINQ CHAMPS PAR TRADE, RIEN D AUTRE

      ctx            le dict _analyze COMPLET a l instant de l entree
      ctx_sortie     le meme, releve a l instant de la sortie
      seance         ASIE / EUROPE / US / NUIT a l entree
      seance_sortie  la meme a la sortie
      traverse       les ouvertures de seance franchies pendant la vie
                     de la position

    On serialise le dict ENTIER, pas une selection de cles. On ne sait
    pas encore lesquelles compteront ; choisir maintenant, c est decider
    aujourd hui de ce qu on aura le droit de decouvrir dans quinze
    jours.

POURQUOI LES QUATRE SEANCES SONT RECOPIEES DE x60_onset

    Les bornes sont IDENTIQUES a celles de x60_onset.py (60/540/930/
    1320 minutes). C est volontaire et c est tout l objet du croisement
    demande : deux panneaux qui decoupent la journee autrement ne se
    croisent pas, ils se juxtaposent. Aujourd hui le papier ne connait
    que SEANCE / HORS -- un trade de 08:30 est "ASIE" dans un panneau
    et "SEANCE" dans l autre, et "HORS" melange nuit asiatique,
    pre-marche europeen, apres-bourse US et week-end dans une colonne.

    `creneau` n est PAS touche : les tableaux existants rendent les
    memes chiffres qu avant. On ajoute une colonne, on n en corrige
    aucune.

POURQUOI traverse

    Hors seance il n y a pas de mise a plat : une position ne meurt
    qu au reverse, au SL ou a MAX_H = 24 h. Une nuit plate est une nuit
    SANS reverse. Le x10 ouvert a 02h traverse donc l ouverture
    europeenne et encaisse le mouvement du matin -- et le tableau PAR
    HEURE l impute a 02h. `traverse` rend ce biais lisible au lieu de
    le laisser produire de faux bons creneaux nocturnes.

LE PIEGE EVITE : ecrire_etat SERIALISE LES POSITIONS

    `ecrire_etat(ouvertes)` fait un json.dumps du dict des positions
    toutes les N minutes. Y ranger le dict brut de _analyze -- qui
    porte des flottants numpy -- leverait un TypeError et TUERAIT
    l observateur. Le contexte est donc rendu serialisable AVANT d etre
    range dans la position, par `_sur()`, qui ne peut pas lever :
    profondeur bornee, listes et dicts tronques, tout ce qui resiste
    finit en chaine.

QUATRE ANCRES, chacune verifiee unique. IDEMPOTENT. Sauvegarde
horodatee. ast.parse, puis EXECUTION du module patche : on appelle
_sur sur un objet volontairement hostile, on ouvre une position
factice, on la ferme, et on verifie que la ligne produite passe
json.dumps. Un patch de journalisation qui compile mais casse a la
premiere ecriture serait pire que pas de patch.

Aucun ordre, aucun MT5 requis pour la verification.
"""
import argparse
import ast
import io
import json
import os
import shutil
import sys
from datetime import datetime

CIBLE = "papier_tf.py"
MARQUEUR = "def _sur("

# --------------------------------------------------------------- ancre 1
A1 = '''def creneau(d=None):
    return "SEANCE" if en_session(d) else "HORS"
'''

N1 = '''def creneau(d=None):
    return "SEANCE" if en_session(d) else "HORS"


# --- contexte, seances, traversees -- ajoute le 14/08 -------------------
# Bornes RECOPIEES de x60_onset.py, a l identique et volontairement.
# Deux panneaux qui decoupent la journee differemment ne se croisent
# pas. `creneau` (SEANCE/HORS) reste intact a cote : les tableaux
# existants doivent rendre exactement les memes chiffres qu avant.
SEANCES = (("ASIE",    60, 540),      # 01:00 - 09:00
           ("EUROPE", 540, 930),      # 09:00 - 15:30
           ("US",     930, 1320),     # 15:30 - 22:00
           ("NUIT",  1320, 60))       # 22:00 - 01:00


def seance4(ts=None):
    """'AAAA-MM-JJTHH:MM:SS' -> ASIE / EUROPE / US / NUIT.

    Calcule a la LECTURE aussi bien qu a l ecriture : les lignes ecrites
    avant ce patch se classent donc sans retouche du fichier.
    """
    if ts is None:
        ts = maintenant()
    try:
        m = int(ts[11:13]) * 60 + int(ts[14:16])
    except (ValueError, IndexError, TypeError):
        return "?"
    for nom, deb, fin in SEANCES:
        if deb <= fin:
            if deb <= m < fin:
                return nom
        elif m >= deb or m < fin:      # NUIT passe minuit
            return nom
    return "?"


def _minuit(ep):
    """Minuit local du jour de `ep`, sans ambiguite d heure d ete.

    On passe par MIDI : a 12h aucune date n est ambigue, alors que
    minuit + 86400 se decale d une heure deux fois par an, en silence.
    """
    lt = time.localtime(ep + 43200)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday,
                        0, 0, 0, 0, 0, -1))


def _traverse(ts0, ts1):
    """Ouvertures de seance franchies entre l entree et la sortie.

    Hors seance rien ne remet a plat : une position vit jusqu au
    reverse, au SL ou a MAX_H. Une nuit calme est une nuit sans
    reverse, donc le trade de 02h encaisse le mouvement de 09h -- et
    le tableau par heure l impute a 02h. Ce champ rend le biais
    visible ; sans lui, la nuit paraitra un bon creneau.
    """
    try:
        e0 = time.mktime(time.strptime(ts0[:19], "%Y-%m-%dT%H:%M:%S"))
        e1 = time.mktime(time.strptime(ts1[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return []
    if e1 <= e0:
        return []
    out = []
    for j in range(3):                 # MAX_H = 24 h : deux jours suffisent
        base = _minuit(e0 + j * 86400)
        for nom, deb, _f in SEANCES:
            b = base + deb * 60
            if e0 < b <= e1 and nom not in out:
                out.append(nom)
        if base > e1:
            break
    return out


def _sur(o, prof=0):
    """Rend `o` serialisable en JSON, sans exception possible.

    _analyze rend des flottants numpy. Les ranger tels quels dans la
    position ferait lever json.dumps a la prochaine ecriture d etat, et
    l observateur mourrait -- en pleine nuit, sans rien dans le fichier
    pour le dire. Ici rien ne peut lever : la profondeur est bornee,
    les conteneurs tronques, et tout ce qui resiste finit en chaine.

    NaN et l infini deviennent None : json.dumps les accepte mais
    produit un fichier que json.loads relit... et que d autres outils
    refusent. Autant trancher a l ecriture.
    """
    if prof > 6:
        return "..."
    if o is None or isinstance(o, bool):
        return o
    if isinstance(o, str):
        return o[:200]
    if isinstance(o, dict):
        return dict((str(k)[:60], _sur(v, prof + 1))
                    for k, v in list(o.items())[:80])
    if isinstance(o, (list, tuple)):
        return [_sur(v, prof + 1) for v in list(o)[:40]]
    if isinstance(o, int):
        return int(o)
    try:
        f = float(o)
    except (TypeError, ValueError):
        return str(o)[:200]
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return round(f, 6)
'''

# --------------------------------------------------------------- ancre 2
A2 = '''def ouvrir(ouvertes, k, c, prix, sens, lot):
    ouvertes[k] = {"k": k, "bras": c["bras"], "actif": c["actif"],
                   "mn": c["mn"], "sens": 1 if sens == "BUY" else -1,
                   "entree": prix, "ts": maintenant(), "t0": time.time(),
                   "creneau": creneau(), "mfe": 0.0, "mae": 0.0,
                   "vp": c["vp"], "lot": lot, "reste": lot,
                   "partiel": False, "id": "%s@%s" % (k, maintenant()),
                   "sl": SL_FIXE.get(c["actif"], 0.0)}
'''

N2 = '''def ouvrir(ouvertes, k, c, prix, sens, lot, cel=None):
    _t = maintenant()
    ouvertes[k] = {"k": k, "bras": c["bras"], "actif": c["actif"],
                   "mn": c["mn"], "sens": 1 if sens == "BUY" else -1,
                   "entree": prix, "ts": _t, "t0": time.time(),
                   "creneau": creneau(), "mfe": 0.0, "mae": 0.0,
                   "vp": c["vp"], "lot": lot, "reste": lot,
                   "partiel": False, "id": "%s@%s" % (k, _t),
                   "sl": SL_FIXE.get(c["actif"], 0.0),
                   # --- ajoute le 14/08. `sym` et `tf` sont ranges ici
                   # pour que _jambe puisse relever le contexte de
                   # SORTIE sans avoir a le recevoir en parametre.
                   "sym": c.get("sym"), "tf": c.get("tf"),
                   "seance": seance4(_t),
                   # Le dict _analyze ENTIER, pas une selection : on ne
                   # sait pas encore quelles cles compteront, et choisir
                   # maintenant reviendrait a decider aujourd hui de ce
                   # qu on aura le droit de decouvrir dans quinze jours.
                   # _sur() le rend serialisable AVANT rangement --
                   # sans quoi ecrire_etat leverait sur un flottant
                   # numpy et tuerait l observateur.
                   "ctx": _sur(cel) if cel else None}
'''

# --------------------------------------------------------------- ancre 3
A3 = '''    pts = (prix - p["entree"]) * p["sens"]
    ecrire_trade({"quoi": "TRADE", "ts": maintenant(), "ouvert": p["ts"],
'''

N3 = '''    pts = (prix - p["entree"]) * p["sens"]
    _fin = maintenant()
    # Le contexte a la SORTIE, releve maintenant. Avec celui de
    # l entree, il dit ce qui a CHANGE pendant la vie de la position --
    # la seule chose qu un rejeu ne redonnera jamais.
    _cs = None
    if p.get("sym") is not None and p.get("tf") is not None:
        _cs = _sur(cellule(p["sym"], p["tf"]))
    ecrire_trade({"quoi": "TRADE", "ts": _fin, "ouvert": p["ts"],
'''

# --------------------------------------------------------------- ancre 4
A4 = '''                  "motif": motif, "lot": round(volume, 2)})
'''

N4 = '''                  "motif": motif, "lot": round(volume, 2),
                  # --- ajoute le 14/08 : le contexte, et rien que lui.
                  # `creneau` (SEANCE/HORS) reste au-dessus, inchange.
                  "seance": p.get("seance") or seance4(p.get("ts")),
                  "seance_sortie": seance4(_fin),
                  "traverse": _traverse(p.get("ts"), _fin),
                  "ctx": p.get("ctx"),
                  "ctx_sortie": _cs})
'''

# --------------------------------------------------------------- ancre 5
A5 = '''                    ouvrir(ouvertes, k, c, prix, veut, lot_de(c["sym"], bal))
'''

N5 = '''                    ouvrir(ouvertes, k, c, prix, veut,
                           lot_de(c["sym"], bal), cel)
'''

ANCRES = ((A1, N1, "creneau()"), (A2, N2, "ouvrir()"),
          (A3, N3, "_jambe(), entete"), (A4, N4, "_jambe(), fin du dict"),
          (A5, N5, "l appel a ouvrir() dans la boucle"))


def verifier_execution(chemin, dossier_essai):
    """Charge le module patche et l EXERCE. ast.parse ne dirait pas si
    _sur laisse passer un objet que json.dumps refuse -- et ce defaut-la
    ne se verrait qu a la premiere sortie de position, en pleine nuit."""
    import importlib.util
    sp = importlib.util.spec_from_file_location("_pt_essai", chemin)
    m = importlib.util.module_from_spec(sp)
    try:
        sp.loader.exec_module(m)
    except Exception as e:
        return "le module ne se charge pas : %s: %s" % (type(e).__name__, e)

    # 1. _sur sur un objet volontairement hostile
    class Retors(object):
        def __repr__(self):
            return "objet-sans-json"
    hostile = {"a": float("nan"), "b": float("inf"), "c": Retors(),
               "d": {"e": [1, 2, {"f": Retors()}]}, "g": ("t", "u"),
               "h": b"octets", 5: "cle-entiere"}
    boucle = {}
    boucle["moi"] = boucle          # reference circulaire
    hostile["i"] = boucle
    try:
        propre = m._sur(hostile)
        json.dumps(propre)
    except Exception as e:
        return "_sur ne protege pas : %s: %s" % (type(e).__name__, e)
    if propre.get("a") is not None or propre.get("b") is not None:
        return "_sur laisse passer NaN ou l infini"

    # 2. seances : une par heure de la journee, aucune '?'
    vus = set()
    for h in range(24):
        s = m.seance4("2026-08-14T%02d:30:00" % h)
        if s == "?":
            return "seance4 rend '?' a %02dh" % h
        vus.add(s)
    if vus != {"ASIE", "EUROPE", "US", "NUIT"}:
        return "les quatre seances ne sont pas toutes atteintes : %s" % vus

    # 3. traverse : le cas qui motive le champ -- entree 02h, sortie 11h
    tr = m._traverse("2026-08-14T02:00:00", "2026-08-14T11:00:00")
    if "EUROPE" not in tr:
        return "traverse ne voit pas l ouverture europeenne (%s)" % tr
    if m._traverse("2026-08-14T10:00:00", "2026-08-14T10:20:00"):
        return "traverse invente une ouverture dans un trade de 20 mn"

    # 4. le cycle complet : ouvrir puis _jambe, et la ligne doit passer
    #    json.dumps -- c est le defaut qui tuerait l observateur.
    m.DOSSIER = dossier_essai
    m.TRADES = os.path.join(dossier_essai, "trades.jsonl")
    m.ETAT = os.path.join(dossier_essai, "etat.json")
    ouvertes = {}
    c = {"bras": "207", "actif": "US30", "mn": 10, "vp": 0.9,
         "sym": None, "tf": None}
    try:
        m.ouvrir(ouvertes, "207110", c, 54000.0, "BUY", 0.94, hostile)
    except Exception as e:
        return "ouvrir() leve : %s: %s" % (type(e).__name__, e)
    p = ouvertes.get("207110")
    if not p or p.get("ctx") is None:
        return "ouvrir() n a pas range de contexte"
    try:
        json.dumps(ouvertes)
    except Exception as e:
        return ("ecrire_etat mourrait sur les positions : %s: %s"
                % (type(e).__name__, e))
    p["ts"] = "2026-08-14T02:00:00"
    try:
        m._jambe(p, 54050.0, 0.94, "REVERSE")
    except Exception as e:
        return "_jambe() leve : %s: %s" % (type(e).__name__, e)
    lignes = [l for l in io.open(m.TRADES, encoding="utf-8") if l.strip()]
    if not lignes:
        return "_jambe() n a rien ecrit"
    try:
        rec = json.loads(lignes[-1])
    except Exception as e:
        return "la ligne ecrite n est pas du JSON : %s" % e
    for champ in ("ctx", "seance", "seance_sortie", "traverse"):
        if champ not in rec:
            return "le champ %s manque dans la ligne ecrite" % champ
    for champ in ("k", "bras", "actif", "mn", "eur", "mfe", "mae",
                  "creneau", "motif", "minutes"):
        if champ not in rec:
            return "le patch a fait disparaitre le champ %s" % champ
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    neuf = src
    for anc, nouv, nom in ANCRES:
        n = neuf.count(anc)
        if n != 1:
            print("KO : %d occurrence(s) de l ancre %s, il en faut 1."
                  % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        neuf = neuf.replace(anc, nouv, 1)
    print("Cinq ancres, chacune unique.")

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # `creneau` doit rester intact : les tableaux existants en dependent.
    if src.count('def creneau(') != neuf.count('def creneau('):
        print("KO : creneau() a ete touche. Rien n a ete ecrit.")
        return 1

    essai = a.fichier + ".essai-%d.py" % os.getpid()
    dos = a.fichier + ".essai-%d.d" % os.getpid()
    io.open(essai, "w", encoding="utf-8").write(neuf)
    if not os.path.isdir(dos):
        os.makedirs(dos)
    try:
        souci = verifier_execution(essai, dos)
    finally:
        for f in (essai,):
            if os.path.isfile(f):
                os.remove(f)
        for r, _d, fs in os.walk(dos, topdown=False):
            for f in fs:
                os.remove(os.path.join(r, f))
        if os.path.isdir(dos):
            os.rmdir(dos)
    if souci:
        print("KO a l execution : %s" % souci)
        print("Rien n a ete ecrit.")
        return 1
    print("Execute et verifie : _sur resiste a NaN, a l infini, aux")
    print("references circulaires et aux objets sans JSON ; les quatre")
    print("seances couvrent les 24 heures ; traverse voit l ouverture")
    print("europeenne sur un 02h->11h et n en invente pas sur 20 mn ;")
    print("un cycle ouvrir/_jambe produit une ligne JSON valide qui")
    print("porte les nouveaux champs SANS avoir perdu les anciens.")

    print()
    print("Cinq champs ajoutes par trade, aucun modifie :")
    print("  ctx            _analyze COMPLET a l entree")
    print("  ctx_sortie     le meme a la sortie")
    print("  seance         ASIE / EUROPE / US / NUIT a l entree")
    print("  seance_sortie  la meme a la sortie")
    print("  traverse       les ouvertures franchies pendant la position")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE papier_tf. Les positions")
    print("deja ouvertes n auront pas de ctx d entree -- elles sont")
    print("perdues pour cette mesure, et c est pourquoi chaque heure")
    print("compte.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Relancer papier_tf pour que ca prenne effet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
