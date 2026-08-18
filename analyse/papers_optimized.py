# -*- coding: utf-8 -*-
r"""
papers_optimized.py -- douze strategies papier croisant l export rails trades

  python papers_optimized.py
  python papers_optimized.py --html

CE QUE C EST, ET CE QUE CE N EST PAS

    Les lignes d entree viennent d un export ou l utilisateur a retenu
    "l integralite des meilleurs chiffres". TOUTES sont positives, et
    elles le sont PARCE QU ELLES ONT ETE RETENUES POUR CA.

    C est le motif exact qui a fait ecrire, sur les neuf regles de H29 :
    "sur-ajuste, a lire comme un plafond, pas un plan". Un backtest
    dont on garde les meilleures lignes ne mesure pas une esperance, il
    mesure la dispersion de son propre echantillon.

    Ces chiffres ne sont donc PAS des previsions. Ce sont des ATTENTES
    A FALSIFIER, et le papier est l instrument qui les falsifie. Chaque
    magic est un pari pre-enregistre : sa ligne ATTENDU est figee
    aujourd hui, sa ligne CONSTATE se remplira toute seule.

LES TROIS CHIFFRES QUI COMPTENT, ET POURQUOI

    PnL / trade    ce que la ligne rapporte VRAIMENT par prise. Un
                   +5033 sur 243 trades vaut 20,7 ; un +3463 sur 38
                   vaut 91,1. Le total classe mal, le ratio classe bien.

    RR d equilibre  (1 - p) / p. A 45 % de reussite il faut gagner 1,22
                   fois ce qu on perd pour ne rien gagner. C est le
                   SEUIL que la strategie doit tenir, et il ne depend
                   d aucun ajustement : c est de l arithmetique.

    BORNE BASSE     borne inferieure de Wilson a 95 % sur le taux de
                   reussite. 76 % sur 38 trades tombe a 60 % ; 54 % sur
                   441 tient a 49 %. DEUX STRATEGIES AU MEME TAUX
                   AFFICHE N ONT PAS LE MEME RISQUE, et cette colonne
                   est la seule qui le dise.

LE CROISEMENT, ET SA CONTRAINTE

    Chaque strategie croise plusieurs sections de l export. Croiser ne
    peut que REDUIRE l effectif : l intersection de deux conditions est
    au plus la plus petite des deux.

    La colonne `n max` est donc un PLAFOND, jamais une prevision. Une
    strategie qui croise trois conditions a 200, 150 et 40 trades ne
    fera pas 40 trades -- elle en fera au plus 40, et probablement
    beaucoup moins.

L HORAIRE

    Toutes filtrent a partir de 14:00 Paris, soit 12:00 UTC en heure
    d ete. Le cash de New York ouvre a 15:30 Paris ; la fenetre couvre
    donc la derniere heure et demie avant l ouverture, puis toute la
    seance americaine.

    CONSEQUENCE NON CHIFFRABLE ICI : les effectifs de l export portent
    sur la journee entiere. Le filtre horaire va les reduire d une part
    que JE NE CONNAIS PAS -- l export ne donne pas la repartition
    horaire. La colonne `n max` n en tient donc pas compte, et c est
    dit plutot que devine.

LA COLONNE NON IDENTIFIEE

    Certaines lignes de l export portent une colonne supplementaire
    entre l effectif et le taux (valeurs 10 a 15). L export ne la nomme
    pas. Elle est CONSERVEE telle quelle et n entre dans AUCUN calcul :
    une colonne dont on ignore le sens ne se convertit pas en decision.

LECTEUR SEUL. N ecrit que dans `cartes\`.
"""
import argparse
import io
import os
import sys
from datetime import datetime

SORTIE = "cartes"

# =====================================================================
# L EXPORT, RECOPIE TEL QUEL. Aucune ligne n est modifiee, aucune n est
# ecartee. `x` est la colonne non identifiee, conservee sans usage.
#   (cle, libelle, n, taux, pnl, x)
# =====================================================================
EXPORT = {
    # --- ecartement ---
    "TC_CLEAN":   ("TIGHT_CROSS / CLEAN",        214, 0.54, 1221.90, None),
    "TC_MIXED":   ("TIGHT_CROSS / MIXED",        154, 0.59, 4218.25, None),
    "MID_CLEAN":  ("MID / CLEAN",                251, 0.59, 2752.38, None),
    "WIDE_CLEAN": ("WIDE / CLEAN",               231, 0.53, 2441.89, None),
    "TC_MIX2":    ("TIGHT_CROSS / mixed",        250, 0.47, 1521.21, 15),
    # --- accords multi-unites ---
    "M3M5M15":    ("M3+M5+M15 / MIXED",           38, 0.76, 3463.18, None),
    "M1M15":      ("M1+M15 / CLEAN",              24, 0.58, 1576.20, None),
    "M1M3M5M15":  ("M1+M3+M5+M15 / CLEAN",        62, 0.56, 1300.85, None),
    # --- unite x T/S x regime ---
    "M1_T_CL":    ("M1 T / CLEAN",               299, 0.62, 4741.54, None),
    "M1_S_MX":    ("M1 S / MIXED",               254, 0.58, 3389.61, None),
    "M1_S_CH":    ("M1 S / CHURN",               295, 0.52, 2997.42, None),
    "M3_T_MX":    ("M3 T / MIXED",               271, 0.58, 4881.74, None),
    "M3_S_CL":    ("M3 S / CLEAN",               326, 0.52, 4240.50, None),
    "M5_T_CL":    ("M5 T / CLEAN",               401, 0.57, 4409.25, None),
    "M5_S_CL":    ("M5 S / CLEAN",               215, 0.54, 2289.24, None),
    "M15_T_CL":   ("M15 T / CLEAN",              441, 0.54, 3339.86, None),
    "M15_T_MX":   ("M15 T / MIXED",              359, 0.50, 3690.39, None),
    # --- actif x sens ---
    "US30_BE_CL": ("US30 BEAR / CLEAN",          124, 0.65, 2630.95, None),
    "US30_BE_MX": ("US30 BEAR / MIXED",          107, 0.64, 2736.13, None),
    "US500_BU_CL":("US500 BULL / CLEAN",         108, 0.69, 3539.98, None),
    # --- alignement ---
    "M1_ALBU_CL": ("M1 ALIGNED_BULL / CLEAN",    211, 0.54, 3318.77, None),
    "M1_SPL_CL":  ("M1 SPLIT / CLEAN",           243, 0.57, 3418.52, None),
    "M3_ALBU_MX": ("M3 ALIGNED_BULL / MIXED",    190, 0.56, 2512.04, None),
    "M3_ALBE_MX": ("M3 ALIGNED_BEAR / MIXED",    139, 0.57, 2260.03, None),
    "M3_SPL_CL":  ("M3 SPLIT / CLEAN",           251, 0.57, 3234.54, None),
    "M5_ALBU_MX": ("M5 ALIGNED_BULL / MIXED",    165, 0.50, 2651.06, None),
    "M5_ALBE_MX": ("M5 ALIGNED_BEAR / MIXED",    151, 0.57, 2316.68, None),
    "M5_SPL_CL":  ("M5 SPLIT / CLEAN",           231, 0.54, 3215.70, None),
    "M15_ALBU_CL":("M15 ALIGNED_BULL / CLEAN",   167, 0.60, 1968.21, None),
    "M15_SPL_CL": ("M15 SPLIT / CLEAN",          243, 0.57, 5033.59, None),
    "M15_SPL_MX": ("M15 SPLIT / MIXED",          225, 0.54, 1276.53, None),
    "M15_SCA_MX": ("M15 SCATTER / MIXED / ALL",   73, 0.58, 1534.98, None),
    # --- leader / laggard ---
    "M1_LEAD":    ("M1 leader / CLEAN",          411, 0.50, 2014.67, None),
    "M3_LEAD":    ("M3 leader / CLEAN",          360, 0.44, 2052.95, None),
    "M3_LAGG":    ("M3 laggard / MIXED",         382, 0.45, 1535.93, None),
    "M5_DIVG":    ("M5 divergent / CLEAN",       190, 0.52, 1356.45, None),
    "M15_LEAD":   ("M15 leader / CLEAN",         313, 0.53, 3329.55, None),
    # --- convergence ---
    "M3_CONV_CL": ("M3 CONVERGING / CLEAN",       84, 0.52, 1633.83, None),
    "M5_DIV_CL":  ("M5 DIVERGING / CLEAN",        46, 0.61, 1202.93, None),
    "M15_CONV_MX":("M15 CONVERGING / MIXED",      53, 0.62, 2044.46, None),
    # --- with / against ---
    "M5_AGA_CH":  ("M5 AGAINST / CHURN",         365, 0.45, 1838.22, None),
    "M5_WITH_MX": ("M5 WITH / MIXED",            589, 0.47,  887.79, None),
    "M15_WITH_CH":("M15 WITH / CHURN",           626, 0.46,  588.43, None),
    "M15_WITH_MX":("M15 WITH / MIXED",           506, 0.46,  895.91, None),
    # --- etoile ---
    "M5_ET_YES":  ("M5 * YES WITH / MIXED",       43, 0.54, 1127.23, None),
    "M5_ET_NO_A": ("M5 * NO AGAINST / CHURN",    104, 0.45, 1132.60, None),
    "M5_ET_NO_C": ("M5 * NO / CLEAN",            290, 0.48, 1616.49, None),
    "M3_NO_CL":   ("M3 NO / CLEAN",              302, 0.49, 1527.30, None),
    "M15_NO_CL":  ("M15 NO / CLEAN",             326, 0.44, 1677.15, None),
    "M15_NO_MX":  ("M15 NO / MIXED",             396, 0.52, 1082.80, None),
    # --- largeur ---
    "M3_NARR_CL": ("M3 NARROWING / CLEAN",       345, 0.46, 1344.87, None),
    "M5_WIDE_CL": ("M5 WIDENING / CLEAN",        355, 0.49, 1627.51, None),
    "M5_STEA_MX": ("M5 STEADY / MIXED",          150, 0.48,  747.64, None),
    "M15_WIDE_CL":("M15 WIDENING / CLEAN",       301, 0.51, 3246.65, None),
    "M15_STEA_MX":("M15 STEADY / MIXED",         145, 0.53,  630.05, None),
    # --- etats composes ---
    "BEAR_BULL":  ("bear/bull / mixed",          132, 0.50, 1542.88, 11),
    "BULL_BULL":  ("bull/bull / clean",           91, 0.55, 1051.94, 12),
    "FLAT_BULL":  ("flat/bull / mixed",          201, 0.51,  999.94, 14),
    "EXTR_ACC":   ("EXTREME accord bull / clean", 76, 0.55,  999.03, 11),
    "STRADDLE":   ("STRADDLE aux 2 bouts / churn",178, 0.46, 1011.89, 13),
    # --- RSI ---
    "RSI_M1_BU":  ("M1 bull RSI dedans / achat", 171, 0.55, 1227.03, 15),
    "RSI_M3_BU":  ("M3 bull RSI au-dessus/achat",163, 0.50, 1017.33, 15),
    "RSI_M3_BE":  ("M3 bear RSI dedans / vente", 117, 0.53, 1072.59, 13),
    "RSI_M5_BU":  ("M5 bull RSI au-dessus/achat",167, 0.47, 1014.43, 12),
    "RSI_M15_BU": ("M15 bull RSI au-dessus/achat",186, 0.49, 1854.86, 12),
    # --- pentes ---
    "P_M1_FLAT":  ("M1 flat=",                   633, 0.45, 1315.53, 15),
    "P_M1_BULL":  ("M1 bull=",                   196, 0.51, 1225.67, 15),
    "P_M3_FLATP": ("M3 flat+",                   294, 0.46, 1696.95, 15),
    "P_M3_BULLP": ("M3 bull+",                   172, 0.48, 1031.72, 15),
    "P_M3_BEAR":  ("M3 bear=",                   127, 0.50,  958.10, 13),
    "P_M5_BULLP": ("M5 bull+",                   173, 0.46, 1025.32, 13),
    "P_M15_BULLP":("M15 bull+",                  248, 0.46, 1621.08, 12),
    "P_M15_FLATM":("M15 flat-",                  150, 0.51, 1597.64, 10),
    # --- accord / conflit ---
    "A_M1_BU_W":  ("M1 ACCORD BULL WITH",        223, 0.46,  746.59, 15),
    "A_M3_BE_W":  ("M3 ACCORD BEAR WITH",        113, 0.51,  635.55, 13),
    "A_M3_BU_W":  ("M3 ACCORD BULL WITH",        195, 0.45,  481.45, 15),
    "C_M5_VENTE": ("M5 CONFLIT vente",           313, 0.45,  838.45, 15),
    "C_M15_VENTE":("M15 CONFLIT vente",          358, 0.52, 2019.33, 15),
}

# =====================================================================
# LES DOUZE STRATEGIES. Chacune croise PLUSIEURS sections ; chaque
# element cite la ligne d ou il vient. `profil` dit ou elle se place
# entre frequence et conviction.
# =====================================================================
STRATEGIES = [
 {"magic": 220001, "nom": "SOCLE M5 TENDANCE",
  "profil": "frequence haute, edge mince",
  "tf": "M5", "actif": "US30 + US500", "sens": "les deux",
  "croise": ["M5_T_CL", "M5_WIDE_CL", "M5_ET_NO_C"],
  "regle": "M5 en T, regime CLEAN, ecartement en WIDENING, pas d etoile",
  "pourquoi":
    "Le socle. M5 T CLEAN est la plus grosse ligne CLEAN de l export "
    "(401 trades) et sa reussite tient a 52 % en borne basse. On la "
    "durcit par deux etats concordants du meme M5 -- WIDENING et "
    "absence d etoile -- qui sont eux-memes positifs separement. "
    "Aucune conviction sur le sens : c est la ligne de reference "
    "contre laquelle les onze autres se jugent."},

 {"magic": 220002, "nom": "M15 TENDANCE DEUX REGIMES",
  "profil": "frequence haute, robustesse par repetition",
  "tf": "M15", "actif": "US30 + US500", "sens": "les deux",
  "croise": ["M15_T_CL", "M15_T_MX", "M15_LEAD"],
  "regle": "M15 en T, regime CLEAN **ou** MIXED, et M15 en position leader",
  "pourquoi":
    "M15 T sort positif dans DEUX regimes differents -- 441 trades a "
    "54 % en CLEAN, 359 a 50 % en MIXED. Une regle qui survit a un "
    "changement de regime est moins probablement un artefact qu une "
    "regle qui n existe que dans un seul. On ne choisit donc pas le "
    "meilleur des deux : on prend les deux, ce qui coute du taux et "
    "achete de la robustesse."},

 {"magic": 220003, "nom": "M1 TENDANCE PROPRE",
  "profil": "reussite haute, effectif moyen",
  "tf": "M1", "actif": "US30 + US500", "sens": "les deux",
  "croise": ["M1_T_CL", "M1_ALBU_CL", "RSI_M1_BU"],
  "regle": "M1 en T, CLEAN, alignement BULL, RSI dedans",
  "pourquoi":
    "62 % de reussite sur 299 trades : le meilleur taux de l export "
    "au-dela de 250 prises, et 15,9 par trade. On le croise avec deux "
    "conditions haussieres du meme M1, ce qui en fait une strategie "
    "DIRECTIONNELLE assumee -- elle ne prendra que des achats, et "
    "elle sera muette dans un marche baissier. C est son cout."},

 {"magic": 220004, "nom": "ASYMETRIE PAR ACTIF",
  "profil": "conviction maximale, effectif faible",
  "tf": "toutes", "actif": "US30 vendeur / US500 acheteur",
  "sens": "impose par l actif",
  "croise": ["US30_BE_CL", "US30_BE_MX", "US500_BU_CL"],
  "regle": "sur US30 : vente seulement. Sur US500 : achat seulement.",
  "pourquoi":
    "Les TROIS plus hauts taux de tout l export sont ici : 65 %, 64 % "
    "et 69 %. Et ils disent la meme chose sous deux formes -- le Dow "
    "paye a la baisse, le S&P paye a la hausse. C est aussi la "
    "strategie la plus exposee au biais de selection : trois lignes "
    "choisies pour leur taux, sur 108 a 124 trades chacune. La borne "
    "basse la ramene autour de 56-60 %, ce qui reste le sommet du "
    "tableau -- mais elle est la premiere que le papier peut demolir."},

 {"magic": 220005, "nom": "CONFLIT M15 VENDEUR",
  "profil": "contrarien, effectif moyen",
  "tf": "M15", "actif": "US30 + US500", "sens": "vente seule",
  "croise": ["C_M15_VENTE", "M15_SPL_CL", "M15_NO_MX"],
  "regle": "M15 en CONFLIT, vente, sur SPLIT CLEAN ou NO MIXED",
  "pourquoi":
    "Elle fait le contraire de l intuition : elle vend QUAND les "
    "unites de temps se contredisent, la ou le reflexe est de "
    "s abstenir. 358 trades a 52 %, et le SPLIT M15 CLEAN est la plus "
    "grosse ligne de PnL de tout l export (+5033 sur 243). Deux "
    "manieres differentes de dire desaccord, toutes deux payantes."},

 {"magic": 220006, "nom": "SPLIT M15 PROPRE",
  "profil": "PnL par trade eleve, effectif moyen",
  "tf": "M15", "actif": "US30 + US500", "sens": "les deux",
  "croise": ["M15_SPL_CL", "M15_WIDE_CL", "M15_ALBU_CL"],
  "regle": "M15 en SPLIT, CLEAN, ecartement WIDENING",
  "pourquoi":
    "20,7 par trade, le meilleur ratio au-dela de 200 prises. La "
    "version MIXED du meme SPLIT tombe a 5,7 par trade pour un "
    "effectif voisin : le regime CLEAN n est pas un detail ici, il "
    "porte quatre cinquiemes du resultat. On l ecarte explicitement."},

 {"magic": 220007, "nom": "CROISEMENT SERRE MIXTE",
  "profil": "PnL par trade tres eleve, effectif faible",
  "tf": "toutes", "actif": "US30 + US500", "sens": "les deux",
  "croise": ["TC_MIXED", "M3_CONV_CL", "M15_CONV_MX"],
  "regle": "TIGHT_CROSS en regime MIXED, avec convergence M3 ou M15",
  "pourquoi":
    "27,4 par trade sur 154 prises -- le meilleur rendement unitaire "
    "au-dela de 100 trades. Et le TIGHT_CROSS se comporte de facon "
    "OPPOSEE selon le regime : 27,4 en MIXED contre 5,7 en CLEAN et "
    "6,1 sur la seconde ligne mixte. Cette contradiction interne est "
    "un avertissement autant qu une opportunite, et le papier est "
    "exactement l endroit ou la trancher."},

 {"magic": 220008, "nom": "ACCORD TROIS UNITES",
  "profil": "conviction extreme, tres rare",
  "tf": "M3 + M5 + M15", "actif": "US30 + US500", "sens": "les deux",
  "croise": ["M3M5M15", "M1M3M5M15", "M1M15"],
  "regle": "accord d au moins trois unites de temps",
  "pourquoi":
    "76 % de reussite et 91,1 par trade : les deux meilleurs chiffres "
    "de tout l export. Sur 38 trades. La borne basse de Wilson tombe "
    "a 60 % -- toujours excellent, mais l ecart entre 76 et 60 dit "
    "tout ce qu il faut savoir sur la confiance qu on peut accorder a "
    "un taux mesure sur 38 prises. A tenir tres longtemps avant de "
    "conclure quoi que ce soit."},

 {"magic": 220009, "nom": "ECARTEMENT QUI S OUVRE",
  "profil": "frequence haute, edge mince",
  "tf": "M15", "actif": "US30 + US500", "sens": "les deux",
  "croise": ["M15_WIDE_CL", "M15_LEAD", "P_M15_BULLP"],
  "regle": "M15 WIDENING, CLEAN, leader, pente bull+",
  "pourquoi":
    "L ecartement qui s ouvre paye (10,8 par trade sur 301) la ou "
    "l ecartement stable ne paye presque pas (4,3 sur 145). La "
    "difference entre WIDENING et STEADY est le vrai signal de cette "
    "section, et elle se retrouve sur M5 comme sur M15."},

 {"magic": 220010, "nom": "CONTRE-TENDANCE EN CHURN",
  "profil": "reussite basse, RR exige, effectif haut",
  "tf": "M5", "actif": "US30 + US500", "sens": "les deux",
  "croise": ["M5_AGA_CH", "M5_ET_NO_A", "M1_S_CH"],
  "regle": "M5 AGAINST en regime CHURN, sans etoile",
  "pourquoi":
    "45 % de reussite et pourtant +1838 : cette strategie ne gagne "
    "que par l asymetrie. Son RR d equilibre est de 1,22 -- elle "
    "DOIT encaisser plus qu elle ne rend, sinon elle perd. C est la "
    "seule du lot dont la survie depend d une gestion de sortie et "
    "non d un taux de reussite, et c est pour ca qu elle est dans le "
    "lot : si le papier la valide, il valide un mecanisme different "
    "des onze autres."},

 {"magic": 220011, "nom": "RSI M15 AU-DESSUS",
  "profil": "frequence moyenne, edge mince",
  "tf": "M15", "actif": "US30 + US500", "sens": "achat seul",
  "croise": ["RSI_M15_BU", "M15_ALBU_CL", "M15_CONV_MX"],
  "regle": "M15 bull, RSI au-dessus, achat, alignement bull",
  "pourquoi":
    "10,0 par trade sur 186 prises. Le RSI au-dessus qui reste "
    "acheteur est contre-intuitif -- on achete ce qui est deja "
    "etendu -- et cette famille est positive sur M3, M5 ET M15, donc "
    "sur trois unites independantes. La repetition vaut mieux qu un "
    "chiffre unique plus flatteur."},

 {"magic": 220012, "nom": "SCATTER TOUS ACTIFS",
  "profil": "rare, seul a sortir du perimetre US",
  "tf": "M15", "actif": "TOUS", "sens": "les deux",
  "croise": ["M15_SCA_MX", "M5_DIVG", "M5_DIV_CL"],
  "regle": "M15 SCATTER, regime MIXED, sur l ensemble des actifs",
  "pourquoi":
    "La SEULE ligne de l export marquee ALL et non US. 73 trades a "
    "58 %, 21,0 par trade. Elle est ici parce qu elle teste une "
    "question qu aucune autre ne pose : la dispersion paye-t-elle "
    "hors du perimetre americain ? Si elle tient, elle ouvre un "
    "terrain ; si elle tombe, on aura appris que le perimetre compte."},
]

HORAIRE = "14:00 Paris -> cloture (12:00 UTC en heure d ete)"


def wilson_bas(p, n, z=1.96):
    """Borne inferieure de Wilson a 95 % sur une proportion.

    L approximation normale simple donne des bornes fausses sur les
    petits effectifs -- et c est justement la qu on en a besoin."""
    if n <= 0:
        return 0.0
    d = 1.0 + z * z / n
    c = p + z * z / (2.0 * n)
    r = z * ((p * (1.0 - p) / n + z * z / (4.0 * n * n)) ** 0.5)
    return max(0.0, (c - r) / d)


def agrege(cles):
    """Effectif PLAFOND, taux pondere, PnL par trade.

    Le plafond est le MINIMUM des effectifs croises : une intersection
    ne peut pas etre plus grande que le plus petit de ses termes. Ce
    n est pas une prevision, c est une borne."""
    lignes = [EXPORT[k] for k in cles]
    n_max = min(x[1] for x in lignes)
    n_tot = sum(x[1] for x in lignes)
    taux = sum(x[1] * x[2] for x in lignes) / float(n_tot)
    pnl_tr = sum(x[3] for x in lignes) / float(n_tot)
    return n_max, n_tot, taux, pnl_tr


def rr_equilibre(p):
    return (1.0 - p) / p if p > 0 else float("inf")


def rendu():
    L = []
    a = L.append
    a("=" * 118)
    a("PAPERS OPTIMIZED -- douze strategies pre-enregistrees")
    a("=" * 118)
    a("  horaire commun : %s" % HORAIRE)
    a("  magics         : 220001 -> 220012")
    a("")
    a("  CE TABLEAU N EST PAS UNE PREVISION. Les lignes sources sont")
    a("  les MEILLEURES d un export : toutes positives parce que")
    a("  retenues pour ca. Un backtest dont on garde le haut du panier")
    a("  mesure sa propre dispersion, pas une esperance.")
    a("")
    a("  La colonne ATTENDU est figee aujourd hui. La colonne CONSTATE")
    a("  se remplit toute seule et c est elle qui tranchera.")
    a("")
    a("-" * 118)
    a("%-7s %-27s %-38s %6s %6s %7s %7s %8s"
      % ("MAGIC", "NOM", "PROFIL", "n max", "taux", "borne", "RR eq.",
         "PnL/tr"))
    a("-" * 118)
    for s in STRATEGIES:
        n_max, n_tot, taux, pnl_tr = agrege(s["croise"])
        b = wilson_bas(taux, n_tot)
        a("%-7d %-27s %-38s %6d %5.0f%% %6.0f%% %7.2f %8.2f"
          % (s["magic"], s["nom"][:27], s["profil"][:38], n_max,
             100 * taux, 100 * b, rr_equilibre(taux), pnl_tr))
    a("-" * 118)
    a("")
    a("  n max   PLAFOND d effectif, pas prevision : une intersection")
    a("          ne depasse pas le plus petit de ses termes. Et le")
    a("          filtre horaire le reduira encore d une part inconnue.")
    a("  borne   borne basse de Wilson a 95 %. L ecart avec le taux")
    a("          affiche mesure la fragilite de l effectif.")
    a("  RR eq.  (1-p)/p : le rapport gain/perte SOUS lequel la")
    a("          strategie perd, quelle que soit sa qualite par ailleurs.")
    a("")
    a("=" * 118)
    a("LE DETAIL, ET LA JUSTIFICATION DE CHAQUE CROISEMENT")
    a("=" * 118)
    for s in STRATEGIES:
        n_max, n_tot, taux, pnl_tr = agrege(s["croise"])
        a("")
        a("-" * 118)
        a("  %d  %s" % (s["magic"], s["nom"]))
        a("-" * 118)
        a("     unites   : %s" % s["tf"])
        a("     actifs   : %s" % s["actif"])
        a("     sens     : %s" % s["sens"])
        a("     horaire  : %s" % HORAIRE)
        a("     regle    : %s" % s["regle"])
        a("")
        a("     croise %d section(s) :" % len(s["croise"]))
        for k in s["croise"]:
            lib, n, t, p, x = EXPORT[k]
            sup = ("   [col. non identifiee : %s]" % x) if x else ""
            a("        %-30s n=%4d  %3.0f%%  PnL %+9.2f  (%5.2f/tr)%s"
              % (lib, n, 100 * t, p, p / float(n), sup))
        a("")
        a("     ATTENDU  n max %d   taux %.0f%%   borne basse %.0f%%"
          % (n_max, 100 * taux, 100 * wilson_bas(taux, n_tot)))
        a("              RR d equilibre %.2f   PnL/trade %.2f"
          % (rr_equilibre(taux), pnl_tr))
        a("     CONSTATE (papier)   -- vide, se remplira")
        a("")
        for ligne in decoupe(s["pourquoi"], 108):
            a("     %s" % ligne)
    a("")
    a("=" * 118)
    a("CE QUE CE PANNEAU NE DIT PAS")
    a("=" * 118)
    a("  Aucun de ces chiffres n est hors echantillon. Aucun n a de")
    a("  temoin. Aucun n a paye un euro reel.")
    a("")
    a("  Douze strategies tirees du haut d un meme export partagent")
    a("  leurs donnees : si le marche de ces mois etait particulier,")
    a("  elles se tromperont TOUTES ENSEMBLE, et leur accord ne sera")
    a("  pas une confirmation.")
    a("")
    a("  Ce qui les separera, c est le papier -- et le fait que leurs")
    a("  attentes sont ecrites ici, datees, avant.")
    a("")
    a("  Genere le %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    return "\n".join(L)


def decoupe(t, n):
    mots, ligne, out = t.split(), "", []
    for m in mots:
        if len(ligne) + len(m) + 1 > n:
            out.append(ligne)
            ligne = m
        else:
            ligne = (ligne + " " + m).strip()
    if ligne:
        out.append(ligne)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sortie", default=SORTIE)
    a = p.parse_args()
    txt = rendu()
    print(txt)
    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)
    che = os.path.join(a.sortie, "panel_papers.txt")
    io.open(che, "w", encoding="utf-8", newline="").write(txt + "\n")
    print()
    print("  ecrit : %s (%d octets)" % (che, len(txt.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
