# -*- coding: utf-8 -*-
"""
regles_gelees_v9.py -- gel du 2026-08-10

ORIGINE
    Panel /rails_trades, export du 10/08 a 17:11, 1522 signaux classes,
    2492 trades live. Section "SIGNATURE DIRECTIONNELLE" et section
    "Les deux bouts x churn". Tous les chiffres cites ici ont ete relus
    LIGNE A LIGNE dans l export, pas repris d une lecture exterieure : trois
    analyses exterieures ont ete confrontees a ce meme fichier le 10/08 et
    les trois citaient au moins une ligne qui n existe pas.

    Ce gel ne retient QUE des cellules a N >= 100 signaux ET >= 8 jours.
    Le panel dit lui-meme "avec N < 30 par cellule, ne rien conclure" et
    "la colonne jours fait foi". Les deux familles gelees ici respectent les
    deux bornes ; ce qui a ete ecarte plus bas ne respectait que la premiere.

LE VOCABULAIRE, TEL QUE LE PANEL LE DEFINIT
    bull  = les DEUX rails au-dessus de 50      bear = les deux sous 50
    flat  = a cheval sur 50 (range) -- exclu, "le biais n y veut rien dire"
    RSI   : ABOVE au-dessus des deux rails, INSIDE entre les deux,
            BELOW sous les deux.
    Les rails sont deux lignes de divergence, pas des bandes : "bull + RSI
    BELOW" se lit donc "rails encore haussiers, RSI qui lache", et non
    "survente". C est la lecture qui avait ete corrigee a la main le 10/08.

============================================================================
FAMILLE X -- ON NE TRADE PAS CONTRE LA STRUCTURE RAPIDE
============================================================================

    Point de depart : une remarque de l operateur le 10/08 -- "M3 est plutot
    bear et M5 plutot bull, M1 est a eviter, c est du bruit jusqu a ce que
    M5 transforme". Mise en chiffres, elle donne autre chose et mieux.

    LES 48 LIGNES "biais x RSI x sens" REGROUPEES EN ACCORD / CONTRE
        accord = acheter sous des rails bull, ou vendre sous des rails bear.
        contre = l inverse. Le RSI ne sert plus qu a peupler les cases.

            pas   avec le biais        contre le biais      ecart
            M1    +6,33  (455 sig)     -14,31  (301)       +20,64
            M3    +7,73  (419)          -5,90  (373)       +13,63
            M5    -0,61  (383)          +2,27  (398)        -2,88
            M15   +2,19  (562)          -1,72  (561)        +3,91

        L ecart decroit de M1 a M5 puis S INVERSE. Ce n est donc pas "M1 est
        du bruit" : aller DANS le sens du M1 paye +6,33. C est aller CONTRE
        qui coute, et cela coute d autant plus que le pas est court.

    UNE SECONDE MESURE, INDEPENDANTE, DIT LA MEME CHOSE
        Le panel orderflow du 10/08 17:39 contient une section CONFLUENCE
        qui croise les rails avec le consensus HLC des trois indices --
        classification differente, construite sans le RSI, sur 1532 signaux
        et 9 jours :

            CONFLIT x VENTE   M1 -28,68 (96)   M3 -3,75 (154)
                              M5  +5,24 (151)  M15 +8,48 (219)

        Meme gradient, meme inversion au meme endroit, sur des populations
        qui ne sont pas construites pareil. Et le compteur du nombre de pas
        de temps en accord CONTRE le trade :

            0 TF  +2,62 (1372 sig, 9 j)
            1 TF -10,81  (153, 9 j)
            2 TF -16,85    (7, 4 j)

        Une replication n est pas une preuve -- c est le meme corpus de
        tickets vu deux fois. Mais deux definitions independantes qui
        tombent sur le meme point d inversion, cela vaut mieux qu une.

    LE CONFONDANT QUI PEUT TOUT EXPLIQUER, ET SON TEMOIN
        Sur ces neuf jours, les VENTES valent -8,67 EUR par ticket et les
        ACHATS +3,48. Or "contre un biais bull" veut dire "vendre", et le
        biais est bull bien plus souvent que bear.

        Donc "ne pas trader contre les rails" pourrait n etre, en entier,
        que "ne pas vendre pendant neuf jours de hausse". X2 est ecrit pour
        cela et c est LE test de la famille : si interdire toutes les ventes
        fait aussi bien que X1, ce gel ne parle pas des rails, il parle de
        la tendance des indices en aout 2026, et il ne survivra pas.

        Aucune des lectures exterieures du 10/08 -- ni la notre au premier
        jet -- n avait pose ce temoin.

    X1 EST UNE INTERDICTION, PAS UNE SELECTION. Elle ne concentre pas le
    volume sur une poignee de tickets, contrairement aux gels V6 et V8 ou
    5 pour cent des tickets portaient les trois quarts du resultat. Une
    interdiction se trompe moins cher qu une selection.

============================================================================
FAMILLE Y -- LA CAPITULATION : M1 BAISSIER SOUS UN M15 HAUSSIER
============================================================================

    Section "Les deux bouts x churn", biais M1 x biais M15 x verdict churn :

        M1 bear / M15 bull / churn mixed   102 sig   8 j   60 % WR  +20,61
        temoin, tout churn "mixed" confondu 540 sig   9 j            +2,38
        le miroir strict, M1 bull / M15 bear / mixed
                                            30 sig   4 j   40 % WR  -11,75

    Les 540 signaux et le +2,38 du temoin ne sont pas dans le panel : ils
    sont la somme des neuf cellules "mixed" du meme tableau, refaite a la
    main sur l export. Le lecteur peut la refaire.

    La cellule pese donc 102 signaux sur 540, et emporte a elle seule plus
    que la totalite du "mixed" (+2101 EUR sur +1283 au total). C est ce qui
    la rend interessante et c est aussi ce qui doit rendre mefiant.

    CE QUE Y1 DIT ET CE QU IL NE DIT PAS
        La cellule n est pas ventilee par sens : elle melange achats et
        ventes. On ne gele donc PAS "vendre la capitulation" -- on gele un
        CONTEXTE dans lequel ce que fait deja l EA marche mieux. Toute
        lecture directionnelle de Y1 serait ajoutee apres coup.

    L ASYMETRIE EST LE VRAI RISQUE, ET ELLE EST GELEE AVEC LE RESTE
        Si le mecanisme etait "les deux bouts se contredisent", il serait
        symetrique. Il ne l est pas : le miroir donne -11,75. Deux lectures
        restent ouvertes, et seul le hors-echantillon les separe :
          - soit M1 bear sous M15 bull est un repli dans une tendance
            haussiere, et alors Y1 n est qu un pari deguise sur la hausse
            des indices pendant ces neuf jours -- il ne survivra pas ;
          - soit l asymetrie est reelle, et les deux bouts ne jouent pas le
            meme role selon lequel des deux lache.
        Y4 est ecrit pour que cette question se lise directement.

        Reserve d effectif : le miroir tient sur 30 signaux et QUATRE jours.
        Il se decrit, il ne conclut pas. Ecrit ici pour qu on ne le lise pas
        en septembre comme s il valait Y1.

    LE VERDICT CHURN EST-IL CAUSAL ? OUI, ET C EST VERIFIE
        L export dit "churn a l entree verdict CHURN / NOISE" et "variables
        figees a l entree". Le verdict ne regarde donc pas ce que le trade
        est devenu. Sans cela Y1 aurait ete du recul deguise et la famille
        entiere serait tombee -- c est le defaut exact que le gel V7
        reproche a regime_jour.py. oos_v9.py le redit a l ecran.

============================================================================
CE QUI A ETE ECARTE, ET POURQUOI
============================================================================

  1. "M3 bear / RSI dedans / VENTE" : 54 signaux, 8 jours, 72 % WR,
     +23,28 EUR/sig. C est la meilleure case du tableau -- et c est
     precisement le probleme. La meilleure de ~48 cases n a pas besoin d
     etre reelle pour exister, et 54 signaux passent tout juste la barre de
     30 que le panel se donne. Le piege d exploration a deja ete verifie
     ici : sur des donnees ou le sens des tickets etait tire au hasard, deux
     sous-cellules sur six passaient sous p = 0,05. Si cette case vaut
     quelque chose, elle merite son propre gel et son propre temoin, pas une
     place de passager dans celui-ci -- chaque famille ajoutee ici coute a
     toutes les autres.

  2. La selection de configs et de magics ("TIGHT_CROSS et MID oui, CHURN
     non, magics 205 exclus"). Deja ecartee au gel V8 pour la meme raison,
     et rien n a change depuis.

  3. Tout ce qui reposait sur des lignes absentes de l export. Les motifs
     "M1+M5" et "M3+M5" n existent pas dans la section DEPART -- les motifs
     reels sont M1, M5, M1+M15, M3+M15, M5+M15, M3+M5+M15, M1+M3+M5+M15.
     Une strategie exterieure batie dessus a ete ecartee en entier.

  4. La cohesion "MITIGE" comme filtre : elle est la deuxieme PIRE des
     trois, pas la meilleure. CHAOS -1,38 (121) · MITIGE -8,26 (137) ·
     ALIGNE -7,13 (779).

  5. TOUT L ORDERFLOW COMME FILTRE D ENTREE, et c est la decision la plus
     couteuse de ce gel. Le panel orderflow du 10/08 17:39 a ete lu section
     par section. Il n en sort AUCUNE regle gelable, pour quatre raisons
     qui se cumulent :

       - COUVERTURE. 268 tickets sur 1625 sont apparies a une barre Ninja,
         soit 16,5 pour cent, et US100 n a aucune donnee. Toute cellule ER
         porte sur ces 268-la.

       - EFFECTIFS. Les cellules dont on voudrait faire des regles pesent
         2 a 26 tickets : EXHAUSTION_SELL 10, ABSORPTION 5, EXHAUSTION_BUY
         2, TIGHT_CROSS x EXHAUSTION_SELL 5, "15h + flux propre" 2. Le
         panel s interdit lui-meme de conclure sous 30.

       - LA MARGE CONTREDIT LA LECTURE COURANTE. Regroupe par qualite de
         flux, CARNAGE vaut -0,36 par ticket sur 109 -- pratiquement
         neutre -- tandis que MOU vaut -7,34 sur 74. Le gradient ER n est
         pas monotone, donc "flux sale = ne pas entrer" n a pas de support.
         L exception est US30, ou le gradient tient sur des N corrects :
         CARNAGE +1,57 (59), MOU -14,59 (47), CORRECT +11,97 (48),
         PROPRE +20,43 (24). Si l orderflow doit servir un jour, c est la,
         et sur US30 seulement.

       - LE CONTREFACTUEL DU PANEL LE DIT DEJA. Colonne Delta, PnL par
         signal apres moins avant : creneau 09h-11h +5,43 · PLAT ou
         DIVERGENT +2,58 · churn a l entree +1,30 · flux ER < 0,40 +0,50 ·
         flux CARNAGE seul +0,08 · CONTRE-FLUX -0,15. L orderflow entier
         vaut moins d un dixieme du simple filtre horaire, et la regle
         anti-contre-flux DEGRADE le resultat.

     Ce qui a ete GARDE de l orderflow n est pas une regle mais une
     MESURE : la section CONFLUENCE, citee plus haut, qui replique le
     gradient de la famille X sur une classification independante. C est
     le seul endroit du panel ou les effectifs et le nombre de jours
     autorisent a parler.

  6. UNE MISE EN GARDE DE CADRAGE, pour la relecture de septembre. Le log
     HLC demarre a son installation : ses 1037 signaux valent -6,61 EUR par
     signal, quand le corpus complet vaut +0,79. Lire une cellule de cette
     section comme "positive parce qu au-dessus de zero" est un faux
     positif : sa reference est -6,61, pas 0. Trois lectures exterieures
     du 10/08 ont fait cette erreur.

============================================================================
DEUX FAMILLES, DONC DEUX TESTS -- ET CA SE PAIE
============================================================================
    X1 et Y1 sont les deux seules tetes de serie. Elles sont declarees
    AVANT de voir le hors-echantillon, et le seuil se lit en consequence :
    0,05 / 2 = 0,025 sur chacune. Les temoins et les controles negatifs ne
    sont pas comptes dans cette correction -- ils ne se lisent pas comme des
    tests, ils se lisent comme un SENS attendu. Un temoin qui bat sa regle
    tue la regle, quel que soit son p.

CE FICHIER NE DOIT PLUS ETRE MODIFIE APRES LE GEL.
    oos_v9.py enregistre son empreinte SHA-256 et refuse de rendre un
    verdict si elle a change.

CONVENTION
    Chaque regle prend un signal et renvoie True si on AUTORISE le trade.
    Champ manquant = on autorise (fail-open), comme en live.

    Consequence a garder en tete pour X4, X5, Y1, Y2, Y3 et Y4, qui sont des
    regles de SELECTION : le fail-open les DILUE avec les tickets non
    classes, au lieu de les vider. La colonne "couv." du tableau dit de
    combien. Les regles d INTERDICTION (X1, X2, X3, X6, X7) n ont pas ce
    defaut : sur un ticket non classe, ne pas interdire est le bon defaut.
"""

VERSION = "9.0"
DATE_REDACTION = "2026-08-10"
ORIGINE = ("panels du 10/08 (rails 17:11, orderflow 17:39) : le cout d aller "
           "contre le biais des rails decroit de M1 a M5 puis s inverse ; "
           "et cellule M1 bear x M15 bull x churn mixed")

# Vocabulaire du panel, tel qu il est ecrit dans l export.
BULL = "BULL"          # les deux rails au-dessus de 50
BEAR = "BEAR"          # les deux rails sous 50
FLAT = "FLAT"          # a cheval : exclu partout, le biais n y veut rien dire

DESSUS = "ABOVE"       # RSI au-dessus des deux rails
DEDANS = "INSIDE"      # RSI entre les deux
SOUS = "BELOW"         # RSI sous les deux

ACHAT = "ACHAT"
VENTE = "VENTE"

MIXTE = "MIXED"        # verdict churn intermediaire, fige a l entree

TF_RAPIDE = "M1"       # le pas ou aller contre coute le plus cher
TF_MOYEN = "M3"        # le point intermediaire du gradient
TF_LENT = "M5"         # le pas ou l ecart s inverse
TF_FOND = "M15"        # le bout lent, pour la famille Y

# Effectifs releves a la main dans les exports du 10/08 (rails 17:11,
# orderflow 17:39), pour memoire seulement. Aucun code ne les lit : ils
# sont la pour qu on puisse verifier en septembre que le gel parlait bien
# des memes populations. (N, jours, PnL/signal)
INSAMPLE = {
    # famille X -- rails seuls, 48 lignes biais x RSI x sens regroupees
    "X_avec_m1": (455, 9, +6.33),   "X_contre_m1": (301, 9, -14.31),
    "X_avec_m3": (419, 9, +7.73),   "X_contre_m3": (373, 9, -5.90),
    "X_avec_m5": (383, 9, -0.61),   "X_contre_m5": (398, 9, +2.27),
    "X_avec_m15": (562, 9, +2.19),  "X_contre_m15": (561, 9, -1.72),
    # le confondant directionnel, mesure sur le meme corpus
    "X_toutes_ventes": (334, 9, -8.67), "X_tous_achats": (422, 9, +3.48),
    # replication independante : panel orderflow, section CONFLUENCE
    "X_conflit_vente_m1": (96, 9, -28.68),
    "X_conflit_vente_m3": (154, 9, -3.75),
    "X_conflit_vente_m5": (151, 9, +5.24),
    "X_conflit_vente_m15": (219, 9, +8.48),
    "X_tf_contre_0": (1372, 9, +2.62), "X_tf_contre_1": (153, 9, -10.81),
    # famille Y
    "Y_m1bear_m15bull_mixed": (102, 8, +20.61),
    "Y_mixed_tout_confondu": (540, 9, +2.38),
    "Y_miroir_m1bull_m15bear_mixed": (30, 4, -11.75),
}


# ------------------------------------------------------------- accesseurs
def _biais(sig, tf):
    """BULL / BEAR / FLAT du pas de temps demande, ou '' si inconnu."""
    return (sig.get("biais_" + tf.lower()) or "").strip().upper()


def _rsi(sig, tf):
    """ABOVE / INSIDE / BELOW du pas de temps demande, ou ''."""
    return (sig.get("rsi_" + tf.lower()) or "").strip().upper()


def _sens(sig):
    """ACHAT / VENTE, ou ''."""
    return (sig.get("sens") or "").strip().upper()


def _churn(sig):
    """CLEAN / MIXED / CHURN a l entree, ou ''."""
    return (sig.get("churn") or "").strip().upper()


def _config(sig, tf, biais, rsi):
    """True si le pas de temps porte exactement cet etat. Inconnu -> None."""
    b, r = _biais(sig, tf), _rsi(sig, tf)
    if not b or not r:
        return None
    return b == biais and r == rsi


# --------------------------------------------------------------- reference
def x0_reference(sig):
    """Aucun filtre. Toute regle doit battre celle-ci."""
    return True


# ================================================== FAMILLE X : accord au biais
def _contre_le_biais(sig, tf):
    """
    True si le trade va CONTRE le biais des rails de ce pas de temps.
    None si le biais est inconnu ou flat, ou si le sens est inconnu.

    flat n est pas un desaccord : le panel exclut ces etats parce que "le
    biais n y veut rien dire". Les compter comme accord ou comme contre
    fabriquerait un resultat a partir d une absence d information.
    """
    b, s = _biais(sig, tf), _sens(sig)
    if not b or not s or b == FLAT:
        return None
    return (b == BULL and s == VENTE) or (b == BEAR and s == ACHAT)


def x1_pas_contre_m1(sig):
    """
    LA REGLE. Interdire tout trade qui va contre le biais des rails M1.

    In-sample : contre M1 vaut -14,31 EUR par ticket sur 301, avec M1 vaut
    +6,33 sur 455. C est le plus grand ecart des quatre pas de temps.

    Biais inconnu ou flat : on autorise. Une interdiction ne doit jamais
    s appuyer sur ce qu elle ne sait pas.
    """
    c = _contre_le_biais(sig, TF_RAPIDE)
    if c is None:
        return True
    return not c


def x2_temoin_pas_de_vente(sig):
    """
    LE TEMOIN QUI DECIDE DE TOUTE LA FAMILLE. Interdire TOUTES les ventes,
    sans jamais regarder les rails.

    Sur les neuf jours du corpus, les ventes valent -8,67 EUR par ticket et
    les achats +3,48. Comme le biais est bull bien plus souvent que bear,
    "aller contre le biais" veut dire "vendre" dans la grande majorite des
    cas. X1 pourrait donc n etre qu une facon compliquee de ne pas vendre
    pendant une hausse de neuf jours.

    Si X1 ne bat pas X2 nettement, la famille X n a rien dit sur les rails.
    Cette ligne se lit AVANT toutes les autres.
    """
    s = _sens(sig)
    if not s:
        return True
    return s != VENTE


def x3_pas_contre_m3(sig):
    """
    Le meme interdit, un pas plus loin. In-sample : contre M3 vaut -5,90 sur
    373, avec M3 +7,73 sur 419.

    Sert deux fois. D abord comme point du gradient : l ecart doit etre plus
    faible qu en M1. Ensuite comme demi-temoin -- si X3 fait aussi bien que
    X1, le pas de temps ne comptait pas, seul l accord au biais comptait, et
    la regle a appliquer serait la plus stable des deux, donc M3.
    """
    c = _contre_le_biais(sig, TF_MOYEN)
    if c is None:
        return True
    return not c


def x4_pas_contre_m5(sig):
    """
    TEMOIN INVERSE, et le seul de ce gel dont on annonce d avance qu il doit
    ECHOUER. In-sample, contre M5 vaut +2,27 sur 398 et avec M5 -0,61 sur
    383 : l ecart s est inverse.

    Interdire les trades contre le biais M5 devrait donc etre neutre ou
    nuisible. Si X4 marche aussi bien que X1, il n y a pas de gradient de
    pas de temps du tout -- seulement un effet global qu on aurait attribue
    au M1 par commodite, et le gel se replierait sur X2.

    Un temoin dont on attend l echec vaut mieux qu un temoin dont on attend
    le succes : il ne peut pas etre lu a l envers apres coup.
    """
    c = _contre_le_biais(sig, TF_LENT)
    if c is None:
        return True
    return not c


def x5_controle_negatif_contre_m1(sig):
    """
    CONTROLE NEGATIF. La regle absurde : ne garder QUE les trades qui vont
    contre le biais M1 -- exactement ce que X1 interdit.

    Son ecart doit etre franchement negatif et de l ordre de grandeur de
    celui de X1, en miroir. S il ne l est pas, X1 interdit dans le vide.

    X1 et X5 ne sont pas complementaires : les tickets flat ou non classes
    sont autorises par les deux. Leurs p se lisent donc separement, comme
    U1 et U6 au gel V8 et contrairement a W1 et W2 au gel V7.
    """
    c = _contre_le_biais(sig, TF_RAPIDE)
    if c is None:
        return True                      # fail-open : dilue, ne vide pas
    return c


def x6_pas_contre_m1_ni_m3(sig):
    """
    X1 et X3 empiles : ne trader contre AUCUN des deux pas rapides.

    A lire avec la lecon du gel V4, ou deux filtres empiles faisaient MOINS
    bien que le meilleur des deux seul. Si X6 ne bat pas a la fois X1 et X3,
    on n empile pas -- et c est X1 seul qui part en production, parce qu il
    coupe moins de volume.
    """
    return x1_pas_contre_m1(sig) and x3_pas_contre_m3(sig)


# ================================================== FAMILLE Y : la capitulation
def y1_capitulation(sig):
    """
    LA REGLE. Ne garder que les signaux ou le bout rapide a lache sous un
    bout lent encore haussier, dans un marche au verdict churn intermediaire :
    M1 bear, M15 bull, churn MIXED.

    Aucune condition de sens : la cellule du panel melange achats et ventes
    et on ne lui fait pas dire ce qu elle ne dit pas.
    """
    b1, b15, c = _biais(sig, TF_RAPIDE), _biais(sig, TF_FOND), _churn(sig)
    if not b1 or not b15 or not c:
        return True
    return b1 == BEAR and b15 == BULL and c == MIXTE


def y2_temoin_mixed_seul(sig):
    """
    TEMOIN INDISPENSABLE. Le verdict churn MIXED seul, sans le desaccord des
    deux bouts.

    In-sample, "mixed" tout confondu vaut +2,38 EUR par signal sur 540, et
    la cellule de Y1 vaut +20,61 sur 102. L ecart est net -- mais c est
    justement pourquoi il faut le remesurer hors echantillon : si Y1 ne bat
    plus Y2 en septembre, tout ce gel se ramenait a "trader quand le marche
    est moyennement bruite", ce qui n a rien a voir avec les rails.
    """
    c = _churn(sig)
    if not c:
        return True
    return c == MIXTE


def y3_temoin_desaccord_seul(sig):
    """
    SECOND TEMOIN. Le desaccord des deux bouts seul, dans les deux sens,
    sans le verdict churn.

    Separe ce qui vient de la structure M1/M15 de ce qui vient du regime de
    bruit. Y1 doit battre Y2 ET Y3 ; battre l un des deux seulement ne
    suffit pas, puisque Y1 est la conjonction des deux conditions.
    """
    b1, b15 = _biais(sig, TF_RAPIDE), _biais(sig, TF_FOND)
    if not b1 or not b15:
        return True
    if b1 == FLAT or b15 == FLAT:
        return False
    return b1 != b15


def y4_controle_negatif_miroir(sig):
    """
    CONTROLE NEGATIF. Le miroir strict : M1 bull, M15 bear, churn MIXED.

    In-sample il donne -11,75 sur 30 signaux et QUATRE jours -- trop peu
    pour conclure, assez pour poser la question. C est la question du gel :
    si Y1 tient et que Y4 reste negatif, l asymetrie est un fait a
    expliquer ; si les deux deviennent positifs, Y1 n etait qu un effet de
    desaccord et Y3 aurait du le montrer ; si les deux s effondrent, la
    cellule etait un pari sur la hausse des indices pendant ces neuf jours.

    Y1 et Y4 ne sont pas complementaires -- les accords et les etats flat ne
    sont dans ni l un ni l autre -- donc leurs p se lisent separement, comme
    U1 et U6 au gel V8 et contrairement a W1 et W2 au gel V7.
    """
    b1, b15, c = _biais(sig, TF_RAPIDE), _biais(sig, TF_FOND), _churn(sig)
    if not b1 or not b15 or not c:
        return True
    return b1 == BULL and b15 == BEAR and c == MIXTE


CH_X = ["sens", "biais_m1"]
CH_X3 = ["sens", "biais_m3"]
CH_X4 = ["sens", "biais_m5"]
CH_Y = ["biais_m1", "biais_m15", "churn"]

REGLES = [
    ("X0", "reference : aucun filtre",            x0_reference,               []),
    ("X1", "pas de trade contre le biais M1",     x1_pas_contre_m1,           CH_X),
    ("X2", "TEMOIN : aucune vente, jamais",       x2_temoin_pas_de_vente,     ["sens"]),
    ("X3", "pas de trade contre le biais M3",     x3_pas_contre_m3,           CH_X3),
    ("X4", "TEMOIN INVERSE : contre le biais M5", x4_pas_contre_m5,           CH_X4),
    ("X5", "NEGATIF : que les trades contre M1",  x5_controle_negatif_contre_m1, CH_X),
    ("X6", "X1 et X3 empiles",                    x6_pas_contre_m1_ni_m3,     CH_X + ["biais_m3"]),
    ("Y1", "capitulation M1 bear / M15 bull",     y1_capitulation,            CH_Y),
    ("Y2", "TEMOIN : churn MIXED seul",           y2_temoin_mixed_seul,       ["churn"]),
    ("Y3", "TEMOIN : desaccord M1/M15 seul",      y3_temoin_desaccord_seul,   ["biais_m1", "biais_m15"]),
    ("Y4", "NEGATIF : miroir M1 bull / M15 bear", y4_controle_negatif_miroir, CH_Y),
]

# Tetes de serie declarees AVANT le hors-echantillon. Le seuil se lit
# 0,05 / 2 = 0,025 sur chacune. Tout le reste se lit en SENS, pas en p.
TETES = ["X1", "Y1"]
