# Les papers -- ce qu ils sont, d ou ils viennent, et pourquoi
# l executeur que je voulais ecrire existait deja

25/08/2026. Consigne apres une demi-journee passee a chercher des
choses qui existaient. Le fil conducteur de ces notes est autant la
stack que mes propres erreurs de methode : quatre fois j ai conclu a une
absence a partir d une recherche dont je n avais pas verifie la portee.

## Il y a DEUX systemes de papers, et ce ne sont pas les memes

| | `papier_tf.py` | les 23 papers |
|---|---|---|
| magics | 206xxx / 207xxx | 220xxx / 230xxx / 240xxx |
| forme | grille de 36 cellules | strategies nommees |
| role | **decide** ses entrees | **filtre** celles du moteur churn |
| etat | `docs\papier_tf\etat.json` | `docs\papers_live\` |
| lot | `max(0.10, balance/20000)` sur le compte MT5 | `balance/20000` sur une balance FICTIVE par paper |

`papier_tf` est une grille : deux bras, trois actifs, six horizons
(10, 20, 30, 60, 120, 240 min). Le magic se lit `bras|actif|horizon` --
`207360` = bras 207, actif 3 (US100), horizon 60. Les x60 dont
l utilisateur voulait voir le travail sont les six cellules d horizon
60. Au-dela de 99 le champ prend trois chiffres, d ou les magics a sept
chiffres comme `2073120`.

Les 23 papers ne decident rien. Le panneau le dit lui-meme :

> CES PAPERS FILTRENT LES ENTREES DU MOTEUR CHURN, ils n en
> choisissent pas. Ils mesurent un FILTRE, pas un timing. Un paper qui
> bat les autres a mieux filtre, il n a pas mieux time.

## D ou viennent les 23 papers

Chantier de deux jours, entierement lisible dans les dates. Source :
`docs\rails_trades\` -- `series_*.jsonl` (6,5 Mo/jour) et
`config_*.jsonl` (3,8 Mo/jour).

**18/08** -- le vocabulaire. `papers_optimized` (les douze premieres
strategies), puis `papers_vocab`, `papers_vocab2`, `papers_champs`,
`papers_regime`, `papers_regles`, `papers_panel`, `papers_extrait`,
`papers_coupe`, `papers_constate`.

**19/08** -- l encodage et la confrontation. `papers_encode` a minuit,
`papers_fenetre`, `papers_rendu`, `papers_repl`, `papers_repare`,
`papers_compare` a 13:49, `papers_moteur` a 14:04, puis `papers_grille`,
`papers_instants`, `papers_reste`, `papers_conflit`,
`papers_confluence`, `papers_decisions`, **`gate_230207.py` a 20:16**,
`papers_boucle` a 20:57.

**20-21/08** -- `miroir_papers.v6`, `papers_recouvrement`,
`papers_exempt`.

Trois familles, nommees dans `panel_papers_compare.txt` :

- `220001-220012` : douze strategies, croisement de trois sections.
- `2301xx-2303xx` : **onze strategies DeepSeek**, eclatees par actif
  (1xx = US30, 2xx = US500, 3xx = US100).
- `240xxx` : la serie de `papers_regles.py`, decrite dans
  `papers_repl.py` comme *"la serie 240000, mes regles"*.

La confrontation des deux lectures est le sujet de
`papers_compare.py` : *"le jeu DeepSeek en 230000 face au mien en
220000"*.

**`gate_230207.py`** est le seul paper devenu gate, le soir meme. Le
tableau dit pourquoi : `230207 US HLC SPLIT CONFLUENCE` sur US500 fait
**+3 156 EUR sur 60 prises, RR 1,86** -- de loin le meilleur. Ses
jumeaux font +255 sur US30 et +458 sur US100.

## Le dimensionnement, dit trois fois

`papers_moteur.lots()` : balance fictive de depart **20 000 par paper**,
`lot = balance / 20000`, plancher 0,01, **recalcule avant chaque
prise**. Chaque paper capitalise sa propre balance ; les lots courants
vont de 0,97 a 1,19 selon la performance.

Le lot n a donc **aucun rapport avec le solde du compte reel**. Un
executeur doit recopier le lot du paper tel quel.

## La fenetre PM

`FENETRE = ("14:00", "19:00")` dans `papers_moteur.py`. Le panneau
precise l origine des deux bornes :

> 14:00 est la definition du panneau lui-meme (`_sess` : US si heure
> >= 14) ; 19:00 vient de la consigne.

## Ou sont les panneaux

`papers_rendu.py` ecrit **`cartes\papers_rendu.html`** (136 Ko,
regenere en continu) et la version console `panels\panel_papers_rendu.txt`.
Trois autres pages datent du 19/08 14:05 : `papers_compare.html`,
`papers_tableau.html`, `papers_220.html`.

La route existe : `patch_route_cartes.py` ajoute **`/cartes`** au
panneau 8095, avec un bouton `CARTES` dans la barre. Mais son index ne
reconnait que le motif `bougies_reperes_<date>.html` -- il annonce
"aucune carte lisible" alors que sept fichiers sont presents. En
attendant, `file:///C:/SVPS/Scalp-EA-main/cartes/papers_rendu.html`
fonctionne.

Elargir le filtre demande de modifier `price_action.py` **et de
redemarrer le panneau** -- operation sous interdit sans `PA_ROLE=panel`.
A faire a froid.

## Le journal source ne contient que des trades CLOS

`SOURCE = docs\rails_trades\tickets_rails.jsonl`, un join produit par
`rails_join.py`. Mesure du 25/08 :

    lignes totales : 6065
    pnl_eur = null : 0

**Aucune ligne ouverte, sur 6 065.** Le join n est ecrit qu une fois la
sortie connue. Les lignes n arrivent d ailleurs pas dans l ordre
chronologique, ce que l en-tete du moteur annonce.

Consequence : `traite()`, qui exige un `pnl_eur`, est une passe
**post-mortem**. Et la section "QUI EST EN POSITION" du panneau, qui
cherche des tickets a volume present et pnl absent, ne trouvera jamais
rien. Le panneau laissait deux hypotheses ouvertes -- *"le journal ne
contient que des trades clos, ou les ouverts tombent hors plage
horaire"* -- la mesure tranche pour la premiere, toujours.

Les 23 papers ne sont donc pas executables depuis ce journal. Ce sont
des instruments de mesure.

## Mais l executeur live existe deja : `miroir_papers.py`

Il ne lit pas le journal. Il prend ses parents dans
`mt5.positions_get()` -- les positions **reellement ouvertes** dont
`magic // 1000` vaut 206 ou 207 -- et leur applique les papers :

    187   accepte : la fonction du moteur, accepte(entry, ticket) -> bool
    193   import papers_moteur as pm
    853   if not self.accepte(entree, rec):

Il **importe** `accepte`, il ne la reecrit pas. C est la discipline que
sa docstring exige, avec sa raison :

> Deux ecritures du meme filtre auraient diverge -- c est ce qui a
> produit les deux TIGHT_SPREAD du 18/08.

## Le probleme reel : les positions des miroirs se font ramasser

`papers_exempt.py`, 21/08 :

> Le 21/08, sur 59 miroirs soldes, 5 seulement l ont ete par le miroir
> lui-meme. Les 54 autres ont ete ramasses par des modules qui ferment
> par symbole sans regarder le magic.

Il protege la plage `220000-249999`.

**Defaut : le miroir 2 tire sous `4240004`** -- le magic du paper
prefixe d un 4 -- et son propre commentaire ligne 346 le dit : *"Hors
de toute plage exemptee."* Ses positions ne sont donc pas protegees.

## Le compte dedie

`18**09`, ThinkMarkets-Demo, 25 000 EUR, hedging, AutoTrading actif,
US30/SPX500/NAS100 negociables, 0 position. Terminal
`...MetaTrader 5 Terminal\`, distinct de celui du moteur
(`...Termina-LOCALSTACKl\`). Verifie par `sonde_compte_papers.py`.

Aucun fichier de la stack ne pointe vers ce terminal, et un
`mt5.initialize()` sans chemin atterrit sur celui du moteur -- donc
l isolement tient aussi pour les modules qui ne nomment aucun chemin.

**Obstacle connu :** `miroir_papers.py` cherche ses parents par
`positions_get()` sur le compte auquel il est branche. Le brancher sur
le compte dedie lui donnerait zero parent. Lire sur un compte et ecrire
sur l autre demande deux terminaux, donc deux processus et un pont.

## Ce que j ai ecrit et mis de cote

`executeur_papers.py` lit `docs\papier_tf\etat.json` et rejoue les
mouvements de la grille 206/207. La mecanique de detection est juste
et testee -- douze cas, dont une cellule qui se ferme et se rouvre dans
le meme tour. Mais la source est celle de `papier_tf`, pas celle des 23
papers. Il reste utilisable si c est la grille qu on veut porter en
live ; il ne convient pas pour les papers filtres.

`corrige_etat_papier.py` reste utile dans les deux cas : il desindente
`ecrire_etat` pour que l etat de `papier_tf` soit ecrit a chaque tour
(20 s) au lieu de toutes les dix minutes.

## Mes quatre erreurs de portee, dans l ordre

1. Comptage des blocages par `\[([A-Z0-9_]+)\]` -- excluait toute
   etiquette contenant un espace, `DOW_CAP_GATE BLOCK` la premiere,
   celle qui faisait 68 % du total.
2. Inventaire des gates par `*_gate.py` -- ratait les quatre
   `gate_*.py`, dont `gate_230207.py`.
3. Balayage des dates borne au 20/08 -- ratait
   `papers_recouvrement.py` et `papers_exempt.py` du 21.
4. Recherche du panneau papers par le nom du fichier `.txt` dans
   `price_action.py` -- alors que `/cartes` est un **index generique**
   qui ne nomme aucun fichier, et un **bouton de route, pas un
   onglet**.

A chaque fois j ai conclu que la chose n existait pas. A chaque fois
elle existait.

## A faire

- Trancher : la grille `papier_tf` ou les 23 papers filtres.
- Si ce sont les papers : faire tourner `miroir_papers.py` contre le
  compte dedie, ce qui suppose de resoudre la lecture des parents.
- Etendre `papers_exempt` a la plage du miroir 2 (`4240004`).
- Elargir le filtre de `/cartes`, a froid, avec redemarrage du panneau.
- Reprendre le chantier des gates : `C14` (`buddha_clause_gate`) refuse
  7 976 fois par jour, et **99,6 % de ses refus frappent les bras
  206/207**.
