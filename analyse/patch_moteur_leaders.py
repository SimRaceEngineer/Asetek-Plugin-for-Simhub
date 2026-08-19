# -*- coding: utf-8 -*-
r"""
patch_moteur_leaders.py -- cabler les quatre magics leader reparees

  python patch_moteur_leaders.py --essai
  python patch_moteur_leaders.py
  python patch_moteur_leaders.py --defaire

CE QU IL AJOUTE, ET POURQUOI

    papers_repare.py a fait valider trois cles de plus le 19/08 :
    US30_BE_CL (124), US30_BE_MX (107), US500_BU_CL (108). Elles
    debloquent quatre magics -- 230106, 230205, 230102, 230202.

    "US30 BEAR" ne veut pas dire "vendre US30". C est la CONFIG LEADER
    de _section_leader : _leader_sig(ll_entry["M1"]) = "<leader>
    <jambe>". La legende du panneau le dit ligne 426 : "US100 BEAR =
    NAS chute en tete". Les trois cles ont valide EXACTEMENT sur cette
    lecture.

    LE "OU" DE DEEPSEEK N EST PAS UNE CONDITION. Il ecrit "le sens doit
    coincider avec US500 BULL OU US30 BEAR". En ET ce serait presque
    toujours vide : il n y a qu un leader a la fois. Il se resout par la
    DECOMPOSITION PAR ACTIF -- 230102 EST deja le cas US30, la branche
    US500 appartient a 230202.

    PAS DE 230302. L export ne contient aucune ligne US100 leader.

    220004 devient une HYPOTHESE DECLAREE, eclatee en 220004 (US30
    vente) et 220014 (US500 achat). Son idee tient ; sa preuve est
    tombee avec la relecture des cles. Le nom le dit a l ecran.

CE QU IL NE FAIT PAS

    Il ne touche que papers_moteur.py. Aucun trader, aucun processus,
    aucun fichier d etat. Sauvegarde .bak, --defaire restaure.

    Le journal des prises n est PAS efface : les quatre nouveaux magics
    commenceront a la prochaine passe, sur les tickets a venir. Pour
    qu ils rattrapent l historique, il faut le reconstruire :
        python papers_moteur.py --reset --oui
"""
import argparse
import io
import os
import shutil
import sys

CIBLE = "papers_moteur.py"

ANCRE_DOC = """    trente-neuf autres sont dehors : cle non validee, cle non encodee,
    ou croisement vide. Ils rentreront quand leur cle sera reparee.
\"\"\""""

SUITE_DOC = """    trente-neuf autres sont dehors : cle non validee, cle non encodee,
    ou croisement vide. Ils rentreront quand leur cle sera reparee.

    QUATRE DE PLUS LE 19/08, une fois les cles leader reparees :
    230106, 230205, 230102, 230202. "US30 BEAR" designe la CONFIG
    LEADER, pas le sens du trade, et le "ou" de DeepSeek se resout par
    la decomposition par actif. Voir LEADERS plus bas.

    DEUX SANS PREUVE : 220004 et 220014. Leur idee tient, leur
    justification est tombee avec la relecture des cles leader. Elles
    tournent en hypotheses declarees -- pas en attributions.
\"\"\""""

ANCRE_DEF = "def papers(pe, pr):"

BLOC = '''# ======================================================================
# LES MAGICS DONT LE FILTRE EST UNE CONFIG LEADER   (19/08/2026)
# ======================================================================
# "US30 BEAR" ne veut pas dire "vendre US30" : c est la CONFIG LEADER de
# _section_leader, soit _leader_sig(ll_entry["M1"]) = "<leader> <jambe>".
# La legende du panneau le dit mot pour mot ligne 426 : "US100 BEAR =
# NAS chute en tete". Les trois cles correspondantes ont valide
# EXACTEMENT sur cette lecture le 19/08 -- 124, 107 et 108.
#
# LE "OU" DE DEEPSEEK N EST PAS UNE CONDITION.
#
# Il ecrit "le sens doit coincider avec US500 BULL OU US30 BEAR". En ET
# ce serait presque toujours vide : il n y a qu un leader a la fois, le
# Dow ne peut pas mener en baissier pendant que le S&P mene en haussier.
# Le "ou" est resolu par la DECOMPOSITION PAR ACTIF -- 1xx = US30,
# 2xx = US500, 3xx = US100 -- chaque magic prenant sa propre branche.
# 230102 EST deja le cas US30 ; la branche US500 appartient a 230202.
#
# Le sens vient donc du leader, pas de l actif : "entree dans le sens du
# leader" (DeepSeek, gestion de 220005). Il n est pas ecrit ici, il se
# DEDUIT de la jambe -- une seule source, pas deux a tenir d accord.
#
# PAS DE 230302. L export ne contient aucune ligne US100 leader : ni
# jambe, ni effectif. Un magic sans donnee derriere lui n est pas un
# magic prudent, c est un magic invente.
#
# (magic, nom, actif trade = leader, jambe, seau ou None, cles en plus)
LEADERS = [
    (230106, "US LEADER ROTATION",      "US30",  "BEAR", "clean", []),
    (230205, "US LEADER ROTATION",      "US500", "BULL", "clean", []),
    (230102, "US TIGHT MIXED MOMENTUM", "US30",  "BEAR", None, ["TC_MIXED"]),
    (230202, "US TIGHT MIXED MOMENTUM", "US500", "BULL", None, ["TC_MIXED"]),
]

# Les magics qui n ont PLUS de ligne d export derriere eux.
# 220004 croisait US30_BE_CL, US30_BE_MX et US500_BU_CL en lisant
# "US30 BEAR" comme "vendre US30". C etait faux. Son IDEE -- le Dow paye
# a la baisse, le S&P a la hausse -- reste testable telle quelle ; c est
# sa PREUVE qui est morte. Elle tourne donc en hypothese pure, et le
# panneau doit le dire au lieu de la laisser passer pour une attribution.
#   (magic, nom, actif, sens)
SANS_PREUVE = [
    (220004, "ASYMETRIE PAR ACTIF (hypothese)", "US30",  "vente"),
    (220014, "ASYMETRIE PAR ACTIF (hypothese)", "US500", "achat"),
]


def _leader_sig(t):
    """_leader_sig du panneau (ligne 194), sur ll_entry['M1']."""
    m1 = (t.get("ll_entry") or {}).get("M1") or {}
    leader, leg = m1.get("leader"), m1.get("leg")
    if not leader or not leg:
        return "?"
    return "%s %s" % (leader, leg)


def _pred_leader(pe, actif, jambe, seau, cles_sup):
    """Le paper trade SON actif, quand SON actif mene, dans le sens de
    la jambe. Le sens n est pas un parametre : il se deduit."""
    sens = "BUY" if jambe == "BULL" else "SELL"
    signature = "%s %s" % (actif, jambe)
    supp = [dict((c[0], c[3]) for c in pe.CLES)[k] for k in cles_sup]

    def p(t):
        if t.get("asset") != actif:
            return False
        if _leader_sig(t) != signature:
            return False
        if t.get("dir") != sens:
            return False
        if seau is not None and pe.ver(t) != seau:
            return False
        return all(f(t) for f in supp)
    return p


def papers(pe, pr):'''

ANCRE_BOUCLE = """    for magic, nom, sens, f in pr.REGLES:
        L.append((magic, nom, None, sens, f))
    return L"""

SUITE_BOUCLE = """    for magic, nom, actif, jambe, seau, sup in LEADERS:
        if any(k not in cles for k in sup):
            continue
        L.append((magic, nom, actif, None,
                  _pred_leader(pe, actif, jambe, seau, sup)))
    for magic, nom, actif, sens in SANS_PREUVE:
        L.append((magic, nom, actif, sens, (lambda t: True)))
    for magic, nom, sens, f in pr.REGLES:
        L.append((magic, nom, None, sens, f))
    return L"""

CHANGEMENTS = [
    (ANCRE_DOC, SUITE_DOC, "1/3  l en-tete dit d ou viennent les quatre"),
    (ANCRE_DEF, BLOC, "2/3  LEADERS, SANS_PREUVE et leurs predicats"),
    (ANCRE_BOUCLE, SUITE_BOUCLE, "3/3  papers() les ajoute au jeu"),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", action="append", default=None)
    p.add_argument("--essai", action="store_true")
    p.add_argument("--defaire", action="store_true")
    a = p.parse_args()

    che = None
    for r in (a.racine or ["."]):
        c = os.path.join(r, CIBLE)
        if os.path.isfile(c):
            che = c
            break
    if che is None:
        print("KO : %s introuvable." % CIBLE)
        return 1

    print("=" * 74)
    print("PATCH MOTEUR -- quatre magics leader, deux hypotheses declarees")
    print("=" * 74)
    print("  cible : %s" % che)
    print()

    if a.defaire:
        bak = che + ".bak"
        if not os.path.isfile(bak):
            print("  Pas de sauvegarde : rien a restaurer.")
            return 1
        shutil.copyfile(bak, che)
        print("  restaure : %s <- %s" % (che, bak))
        return 0

    s = io.open(che, encoding="utf-8").read()
    absentes, deja = [], []
    for ancre, suite, desc in CHANGEMENTS:
        if suite in s:
            deja.append(desc)
        elif s.count(ancre) != 1:
            absentes.append((desc, s.count(ancre)))

    if deja:
        print("  DEJA APPLIQUE :")
        for d in deja:
            print("    %s" % d)
        print()
    if absentes:
        print("  ANCRE INTROUVABLE -- rien ne sera ecrit :")
        for d, n in absentes:
            print("    %s   (%d occurrence(s) au lieu de 1)" % (d, n))
        print()
        print("  papers_moteur.py n est pas dans l etat attendu (v3 du")
        print("  19/08). Recopie papers_moteur_v3.py, puis relance.")
        return 1
    if not deja:
        print("  Les 3 ancres sont trouvees, une seule fois chacune.")
        print()

    for ancre, suite, desc in CHANGEMENTS:
        if suite in s:
            continue
        s = s.replace(ancre, suite, 1)
        print("  %s" % desc)
    print()

    if a.essai:
        print("  --essai : RIEN n a ete ecrit.")
        return 0

    bak = che + ".bak"
    if not os.path.isfile(bak):
        shutil.copyfile(che, bak)
        print("  sauvegarde : %s" % bak)
    io.open(che, "w", encoding="utf-8", newline="").write(s)
    print("  ecrit      : %s" % che)
    print()
    print("  17 -> 21 papers. Les quatre nouveaux ne rattraperont PAS")
    print("  l historique tout seuls : le journal ne rejoue jamais un")
    print("  ticket deja vu. Pour qu ils partent du meme point que les")
    print("  autres, il faut reconstruire :")
    print("      python papers_moteur.py --reset --oui")
    return 0


if __name__ == "__main__":
    sys.exit(main())
