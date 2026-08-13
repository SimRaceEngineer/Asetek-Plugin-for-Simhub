# -*- coding: utf-8 -*-
"""
patch_moteur_m10_m20_m30.py -- M10, M20, M30 en LIVE sur les deux bras

  python patch_moteur_m10_m20_m30.py --fichier ignition_trader.py --essai
  python patch_moteur_m10_m20_m30.py --fichier ignition_trader.py

  python patch_moteur_m10_m20_m30.py --fichier ignition_trader_trail.py --essai
  python patch_moteur_m10_m20_m30.py --fichier ignition_trader_trail.py

CE FICHIER ENVOIE DE VRAIS ORDRES. Lis tout avant de l appliquer.

CE QUI EST DEMANDE

    Les nouvelles unites de temps en live pendant la seance, en papier
    en dehors. La seconde moitie est deja acquise : papier_tf tourne
    24h/24 et continuera. La premiere se resume a ajouter les cellules
    au moteur, qui est DEJA borne a 08:00-19:30 (SESSION_START /
    SESSION_STOP) avec mise a plat au-dela.

CE QUI PASSE, ET CE QUI NE PASSE PAS

    M10, M20, M30 : OUI. Deux caracteres dans le magic, donc six
    chiffres, donc actif et unite decodes correctement.

    H2 et H4 : NON, et ce n est pas un choix. 120 et 240 minutes font
    trois caracteres, donc un magic a sept chiffres, et les deux
    decodeurs se trompent alors :

        _asset_of_magic(2062120) = (2062120 // 100) % 10 = 1 -> US30
                                   alors que c est US500
        _tf_of_magic(2061120)    = str(...)[-2:] = "20"      -> M20
                                   alors que c est H2

    Le SL filet est choisi PAR ACTIF -- 4000 / 200 / 1600. Une US100
    qui recoit le stop de l US500 est coupee immediatement ; une US500
    qui recoit celui de l US30 court avec un stop vingt fois trop
    large. H2 et H4 restent donc en papier tant que le schema de magic
    n a pas ete elargi, ce qui suppose de toucher les deux decodeurs
    dans le moteur, les panneaux et les gels.

PAR OU PASSE L ALLUMAGE DES NOUVELLES UNITES

    _cell_for_tf le dit : le churn ne publie que M1/M5/H1, et le M2
    est calcule EN LOCAL depuis les bougies CFD via _chr._analyze,
    parce que cette fonction est offset-invariante (WaveTrend + RSI =
    momentum, pas de niveau absolu).

    M10, M20 et M30 empruntent exactement cette voie. C est aussi ce
    que fait papier_tf depuis le 12/08 au soir sur six unites : la
    mecanique est deja eprouvee ailleurs, sur les memes bougies.

    Le patch REFUSE de s appliquer si _chr._analyze n est pas importe :
    sans lui, les nouvelles cellules ne s allumeraient jamais et rien
    ne le signalerait. C est le mode de panne le plus couteux -- pas
    une erreur, un silence.

CE QUE CA CHANGE EN EXPOSITION -- LE CHIFFRE A CONNAITRE AVANT

    Aujourd hui TFS_TRADED = ("M2", "M5", "H1") : trois unites, trois
    actifs, neuf magics par bras, dix-huit cellules en tout.

    Apres : six unites, dix-huit magics par bras, TRENTE-SIX cellules.
    Ca DOUBLE. Le compteur `pos` observe entre 8 et 14 positions
    simultanees ; attends-toi a 16-28, lot inchange a balance/20000.

LE RISQUE DU REDEMARRAGE, et il est reel

    _armed part vide a chaque demarrage du moteur. Une ignition en
    cours se lit alors comme fraiche, et toutes les cellules armables
    peuvent ouvrir dans la meme seconde. C est exactement ce qui est
    arrive au papier le 12/08 a 23:38:54 : huit positions d un coup,
    sur aucun signal, qui portaient ensuite la quasi-totalite des
    pertes de trois unites.

    En doublant le nombre de cellules, on double la portee de cet
    effet. REDEMARRE LE MOTEUR HORS SEANCE -- apres 19:30 ou avant
    08:00 -- pour que la regle de session empeche l ouverture, puis
    verifie dans docs/ignition_trader/decisions.jsonl qu il n y a pas
    de rafale d evenements OPEN dans les premieres secondes.

CE QUE LE PATCH TOUCHE

    obligatoire   TFS_TRADED, _TT, _TT2TF, _cell_for_tf
    facultatif    la liste de magics du panneau et sa grille

    Il ne touche NI SL_FIXED, NI la session, NI le lot, NI SKIP_REJECT,
    NI DISABLED_CELLS, NI la logique d entree ou de sortie.

VERIFICATION AU-DELA DE ast.parse

    Le patch relit _TT dans l ARBRE du fichier produit, refabrique les
    dix-huit magics comme le fait _magic(), et verifie pour chacun :

        - six chiffres exactement
        - (magic // 100) % 10 redonne le bon code actif
        - str(magic)[-2:] redonne la bonne unite via _TT2TF

    C est le controle qui aurait attrape H2 et H4 avant qu ils ne
    coutent quelque chose. --essai affiche les dix-huit lignes.

IDEMPOTENT. Sauvegarde horodatee. N EXECUTE PAS le fichier cible.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

NOUVELLES = (("M10", "10"), ("M20", "20"), ("M30", "30"))
MARQUEUR = '"M10"'

# Les deux bras n ont PAS la meme liste : le 207 porte M1 en plus,
# desactive sur US500 et US100 (DISABLED_CELLS), pour comparer
# M1-trail a M2-trail. Chaque ancre a donc ses deux formes, et le
# patch exige qu UNE SEULE corresponde, exactement une fois.
V_TFS = (
    ('''TFS_TRADED = ("M2", "M5", "H1")''',
     '''TFS_TRADED = ("M2", "M5", "H1", "M10", "M20", "M30")'''),
    ('''TFS_TRADED = ("M1", "M2", "M5", "H1")''',
     '''TFS_TRADED = ("M1", "M2", "M5", "H1", "M10", "M20", "M30")'''),
)

V_TT = (
    ('''_TT = {"M2": "02", "M5": "05", "H1": "60"}''',
     '''_TT = {"M2": "02", "M5": "05", "H1": "60",\n'''
     '''       "M10": "10", "M20": "20", "M30": "30"}'''),
    ('''_TT = {"M1": "01", "M2": "02", "M5": "05", "H1": "60"}''',
     '''_TT = {"M1": "01", "M2": "02", "M5": "05", "H1": "60",\n'''
     '''       "M10": "10", "M20": "20", "M30": "30"}'''),
)

V_TT2 = (
    ('''_TT2TF = {"02": "M2", "05": "M5", "60": "H1"}''',
     '''_TT2TF = {"02": "M2", "05": "M5", "60": "H1",\n'''
     '''          "10": "M10", "20": "M20", "30": "M30"}'''),
    ('''_TT2TF = {"01": "M1", "02": "M2", "05": "M5", "60": "H1"}''',
     '''_TT2TF = {"01": "M1", "02": "M2", "05": "M5", "60": "H1",\n'''
     '''          "10": "M10", "20": "M20", "30": "M30"}'''),
)

A_CELL = '''    if tf != "M2":
        return churn_r.get(tf) if churn_r else None
    try:
        bars = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M2, 0, 200)
'''
N_CELL = '''    # Le churn ne publie que M1/M5/H1. M2 etait deja calcule en local ;
    # M10, M20 et M30 empruntent la meme voie. _analyze est
    # offset-invariant (WaveTrend + RSI = momentum, pas de niveau
    # absolu), donc les barres CFD conviennent -- c est l argument qui
    # valait deja pour M2, et papier_tf le verifie depuis le 12/08 sur
    # six unites.
    _tfmt5 = _MT5_TF.get(tf)
    if _tfmt5 is None:
        return churn_r.get(tf) if churn_r else None
    try:
        bars = mt5.copy_rates_from_pos(sym, _tfmt5, 0, 200)
'''

# Pose juste avant _cell_for_tf. mt5 peut etre None (import protege en
# tete de fichier) : on construit la table sous garde, et son absence
# renvoie simplement toutes les unites vers le churn.
A_DEF = '''def _cell_for_tf(asset, sym, tf, churn_r):
'''
N_DEF = '''# Unites calculees EN LOCAL, hors churn. mt5 peut etre None -- l import
# est protege en tete de fichier -- auquel cas la table reste vide et
# tout repart vers le churn, sans exception.
_MT5_TF = {}
if mt5 is not None:
    for _n, _c in (("M2", "TIMEFRAME_M2"), ("M10", "TIMEFRAME_M10"),
                   ("M20", "TIMEFRAME_M20"), ("M30", "TIMEFRAME_M30")):
        _v = getattr(mt5, _c, None)
        if _v is not None:
            _MT5_TF[_n] = _v


def _cell_for_tf(asset, sym, tf, churn_r):
'''

RE_MAGICS = re.compile(
    r'all_magics = \[int\("(20\d)%d%s" % \(a, tt\)\) for a in \(1, 2, 3\)'
    r' for tt in \("02", "05", "60"\)\]')

V_GRILLE = (
    ('''        for tf in ("M2", "M5", "H1"):''',
     '''        for tf in ("M2", "M5", "H1", "M10", "M20", "M30"):'''),
    ('''        for tf in ("M1", "M2", "M5", "H1"):''',
     '''        for tf in ("M1", "M2", "M5", "H1", "M10", "M20", "M30"):'''),
)


def _variante(src, nom, paires):
    """Rend la seule paire (ancien, neuf) qui corresponde exactement une
    fois. Deux formes qui correspondraient a la fois, ou aucune, sont un
    refus : on ne devine pas dans un fichier qui envoie des ordres."""
    trouves = [(a, n) for a, n in paires if src.count(a) == 1]
    if len(trouves) == 1:
        return trouves[0], None
    if not trouves:
        detail = " / ".join("%d fois" % src.count(a) for a, _ in paires)
        return None, "aucune forme connue de %s (%s)" % (nom, detail)
    return None, "%d formes de %s correspondent a la fois" % (
        len(trouves), nom)


def _dico(arbre, nom):
    """Relit un dict litteral dans l arbre du fichier produit."""
    for nd in ast.walk(arbre):
        if not (isinstance(nd, ast.Assign) and isinstance(nd.value, ast.Dict)):
            continue
        if nom in [t.id for t in nd.targets if isinstance(t, ast.Name)]:
            try:
                return ast.literal_eval(nd.value)
            except ValueError:
                return None
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", required=True,
                   help="ignition_trader.py ou ignition_trader_trail.py")
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

    # Sans _chr._analyze, les nouvelles cellules ne s allumeraient
    # JAMAIS, et rien ne le dirait. Silence, pas erreur.
    if "_chr._analyze" not in src:
        print("KO : _chr._analyze absent de ce fichier.")
        print("     Les nouvelles unites passent par le calcul local ;")
        print("     sans lui elles ne s allumeraient jamais, en silence.")
        print("Rien n a ete ecrit.")
        return 1

    obligatoires = []
    for nom, paires in (("TFS_TRADED", V_TFS), ("_TT", V_TT),
                        ("_TT2TF", V_TT2),
                        ("le corps de _cell_for_tf", ((A_CELL, N_CELL),)),
                        ("l en-tete de _cell_for_tf", ((A_DEF, N_DEF),))):
        paire, err = _variante(src, nom, paires)
        if err:
            print("KO : %s." % err)
            print("     Colle-moi les lignes autour, je regarde la forme")
            print("     exacte plutot que de deviner -- ce fichier envoie")
            print("     des ordres.")
            print("Rien n a ete ecrit.")
            return 1
        obligatoires.append((nom, paire[0], paire[1]))
    print("Cinq ancres obligatoires, chacune unique.")
    if any('"M1"' in a for _n, a, _x in obligatoires):
        print("Ce bras porte M1 en plus -- forme reconnue, M1 conserve.")

    neuf = src
    for _nom, anc, nou in obligatoires:
        neuf = neuf.replace(anc, nou, 1)

    # Affichage du panneau : facultatif, mais son absence se dit. Sans
    # lui les nouvelles cellules tradent sans apparaitre sur le 8090.
    opt = []
    m = RE_MAGICS.search(neuf)
    if m:
        neuf = (neuf[:m.start()]
                + ('all_magics = [int("%s%%d%%s" %% (a, tt)) for a in (1, 2, 3)'
                   '\n                  for tt in ("02", "05", "60",'
                   ' "10", "20", "30")]' % m.group(1))
                + neuf[m.end():])
        opt.append("la liste de magics du panneau")
    for _a, _n in V_GRILLE:
        if neuf.count(_a) == 1:
            neuf = neuf.replace(_a, _n, 1)
            opt.append("la grille du panneau")
            break

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # --- la verification qui compte -------------------------------------
    # On refabrique les magics comme le fait _magic(), et on verifie que
    # les DEUX decodeurs les relisent correctement. C est ce controle qui
    # aurait arrete H2 et H4 avant qu ils ne coutent quelque chose.
    tt = _dico(arbre, "_TT")
    tt2 = _dico(arbre, "_TT2TF")
    if not tt or not tt2:
        print("KO : _TT ou _TT2TF illisible dans l arbre. Rien n a ete ecrit.")
        return 1
    mb = re.search(r'return int\(f"(20\d)\{acode\}\{_TT\[tf\]\}"\)', neuf)
    if not mb:
        print("KO : la fabrique de magic a change de forme.")
        print("Rien n a ete ecrit.")
        return 1
    bras = mb.group(1)
    acodes = {1: "US30", 2: "US500", 3: "US100"}

    print()
    print("Les %d magics du bras %s, relus par les deux decodeurs :"
          % (len(acodes) * len(tt), bras))
    print("  %-8s %-7s %-6s %-7s" % ("magic", "actif", "unite", "verdict"))
    mauvais = 0
    for tf in sorted(tt, key=lambda k: tt[k]):
        for ac in sorted(acodes):
            mg = int("%s%d%s" % (bras, ac, tt[tf]))
            s = str(mg)
            act = (mg // 100) % 10
            lu_tf = tt2.get(s[-2:], "?")
            ok = (len(s) == 6 and act == ac and lu_tf == tf)
            if not ok:
                mauvais += 1
            print("  %-8d %-7s %-6s %-7s"
                  % (mg, acodes.get(act, "?"), lu_tf, "ok" if ok else "FAUX"))
    if mauvais:
        print()
        print("KO : %d magic(s) mal relu(s). C est exactement le defaut"
              % mauvais)
        print("     qui rendrait H2 et H4 dangereux : mauvais actif = mauvais")
        print("     SL filet. Rien n a ete ecrit.")
        return 1
    print()
    print("Les %d magics sont a six chiffres et relus correctement."
          % (len(acodes) * len(tt)))

    # L exposition se CALCULE : le 206 et le 207 n avaient pas le meme
    # nombre d unites, et le 207 desactive deux cellules M1. L ecrire en
    # dur donnerait un chiffre faux sur l un des deux.
    anc_tfs = [x for _n, x, _y in obligatoires if x.startswith("TFS_TRADED")]
    av = len(re.findall(r'"(\w+)"', anc_tfs[0])) if anc_tfs else 0
    ap = len(tt)
    des = 0
    for nd in ast.walk(arbre):
        if not (isinstance(nd, ast.Assign)
                and isinstance(nd.value, (ast.Set, ast.Call))):
            continue
        if "DISABLED_CELLS" in [t.id for t in nd.targets
                                if isinstance(t, ast.Name)]:
            des = len(nd.value.elts) if isinstance(nd.value, ast.Set) else 0
    print()
    print("EXPOSITION DE CE BRAS : %d unites au lieu de %d, donc %d cellules"
          % (ap, av, ap * 3 - des))
    print("au lieu de %d." % (av * 3 - des), end=" ")
    if des:
        print("(%d cellule(s) desactivee(s) deduites des deux)" % des)
    else:
        print("(aucune cellule desactivee)")
    print("Les nouvelles unites ajoutent %d cellules ici. Lot inchange a"
          % ((ap - av) * 3))
    print("balance/20000 : l exposition croit du meme facteur.")
    print()
    print("H2 et H4 ne sont PAS ajoutes : sept chiffres, actif et unite")
    print("mal relus sur quatre cellules sur six. Ils restent en papier.")
    print()
    if opt:
        print("Panneau mis a jour : %s." % ", ".join(opt))
    else:
        print("ATTENTION : ni la liste de magics ni la grille du panneau")
        print("n ont ete trouvees dans ce fichier. Les nouvelles cellules")
        print("traderont sans apparaitre sur le panneau. Ce n est pas")
        print("bloquant, mais tu piloterais a l aveugle.")
    print()
    print("REDEMARRAGE : _armed part vide, donc une ignition en cours se")
    print("lit comme fraiche et les cellules peuvent ouvrir toutes en meme")
    print("temps -- c est l artefact du papier du 12/08 a 23:38:54, huit")
    print("positions dans la meme seconde. Redemarre HORS SEANCE, puis")
    print("verifie decisions.jsonl : pas de rafale d OPEN au demarrage.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Rollback : copier le .bak par-dessus.")
    print("PREND EFFET AU REDEMARRAGE DU MOTEUR -- hors seance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
