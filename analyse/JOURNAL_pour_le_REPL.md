# JOURNAL — ce qui est établi, ce qui est réfuté

À déposer sous `docs/JOURNAL.md` à la racine de la stack. `repl_web.py`
le charge dans le contexte du REPL ; au 13/08 il le cherchait et ne le
trouvait pas (`SOURCES ABSENTES ... INTROUVABLE`).

**Ce fichier existe pour une raison précise.** Le 13/08, interrogé sur
le panel orderflow, le REPL a proposé un entonnoir d'entrée en cinq
conditions. Chacun de ses chiffres était juste. Mais cet entonnoir
avait déjà été mesuré, sur plus de données, et **rejeté** — dans
`regles_gelees_v9.py`, qu'il n'a pas dans son contexte. Il ne pouvait
pas le savoir.

Sans ce journal, il re-proposera la même chose à chaque fois qu'on lui
montrera le panel. Avec, il peut chercher ce qu'on ne sait pas encore.

Format : ce qui est **mesuré**, avec son N et sa couverture. Pas
d'opinion. Une ligne datée par fait.

---

## 1. Ce qu'est la stack

Scalping sur indices CFD — US30, US500 (SPX500), US100 (NAS100) — via
MetaTrader 5, en argent réel, sur un VPS Windows qui ne s'éteint pas.

**Décomposition du magic** (établie, définitive) :

```
M 206 1 60
  │   │  └── unité de temps en MINUTES : 01=M1 02=M2 03=M3 05=M5 60=H1
  │   └───── actif : 1=US30  2=US500  3=US100
  └───────── bras
```

Les bras :

| bras | fichier | sortie |
|---|---|---|
| 206 | `ignition_trader.py` | hold-until-reverse, une seule jambe |
| 207 | `ignition_trader_trail.py` | mêmes entrées + sortie partielle |
| 208 | `leader_hold` | M3 fixe |

« x60 » = les cellules H1. Ce n'est pas une famille à part : c'est la
**même logique d'allumage sur une unité plus longue**.

**Le schéma tient en six chiffres, et c'est une contrainte dure.**
Deux décodeurs le lisent, et tous deux supposent une unité sur
**deux** caractères :

```
_asset_of_magic(m) = (m // 100) % 10        -> le code actif
_tf_of_magic(m)    = _TT2TF[str(m)[-2:]]    -> l'unité de temps
```

M10, M20, M30 donnent `10`, `20`, `30` : six chiffres, tout se relit.
Mais **H2 = 120 minutes et H4 = 240 donnent trois caractères**, donc
sept chiffres, et les deux décodeurs se trompent alors :

```
_asset_of_magic(2062120) = 1   -> US30,  alors que c'est US500
_tf_of_magic(2061120)    = "20" -> M20,  alors que c'est H2
```

Quatre cellules H2/H4 sur six lisent le mauvais actif. Comme le SL
filet est choisi **par actif** — 4000 / 200 / 1600 — une US100 qui
reçoit le stop de l'US500 est coupée immédiatement, et une US500 qui
reçoit celui de l'US30 court avec un stop vingt fois trop large.

**H2 et H4 ne peuvent donc pas passer en live** sans élargir le schéma
de magic, ce qui suppose de toucher les deux décodeurs dans le moteur,
dans les panneaux et dans les gels. Ils restent en papier.

## 2. Les règles de production, lues dans le code

- **Entrée** : allumage FRAIS de `churn_regime._analyze` — direction
  changée depuis le dernier consommé. Un basculement BULL→BEAR compte
  même si `ignition` n'est jamais repassé à False (correctif 17/07).
- **Filtre** : RSI(14) M3 > 50 pour un achat, < 50 pour une vente
  (ENFORCE 20/07, fail-open : si le RSI manque, on passe).
- **Stop** : filet fixe, jamais suivi — 4000 / 200 / 1600 points selon
  l'actif.
- **Lot** : balance / 20000, minimum 0.10.
- **Session** : 08:00–19:30 Paris, jours ouvrés, flat au-delà.
- **Sortie 207** : 70 % du VOLUME coupés au premier break de la bougie
  **M2 précédente**, en profit seulement, une fois par position. Les
  30 % restants courent jusqu'au reverse. Buffers US30 15 / US500 2 /
  US100 10. **Le trail reste en M2 à toutes les unités de temps.**

## 3. Ce qui a été MESURÉ ET REJETÉ

Ne pas re-proposer sans données nouvelles. Chaque ligne vient d'un
fichier gelé.

**L'entonnoir orderflow** (`regles_gelees_v9.py` l.171-198) :

- Le gradient ER **n'est pas monotone** : CARNAGE −0,36 sur 109 —
  quasi neutre — alors que MOU vaut −7,34 sur 74. « Flux sale = ne pas
  entrer » n'a donc pas de support.
- **Exception, et c'est la seule piste vivante** : sur **US30 seul**,
  le gradient tient sur des N corrects — CARNAGE +1,57 (59), MOU
  −14,59 (47), CORRECT +11,97 (48), PROPRE +20,43 (24). « Si
  l'orderflow doit servir un jour, c'est là, et sur US30 seulement. »
- Contrefactuel Δ par signal : créneau 09h-11h **+5,43** · PLAT ou
  DIVERGENT +2,58 · churn à l'entrée +1,30 · ER < 0,40 +0,50 · CARNAGE
  seul **+0,08** · CONTRE-FLUX **−0,15**. L'orderflow entier vaut
  moins d'un dixième du simple filtre horaire, et la règle
  anti-contre-flux **dégrade** le résultat.
- Les cellules dont on voudrait faire des règles pèsent 2 à 26
  tickets : EXHAUSTION_SELL 10, ABSORPTION 5, EXHAUSTION_BUY 2. Le
  panel s'interdit lui-même de conclure sous 30 (`MIN_N = 30`,
  `orderflow_join.py` l.42).
- Ce qui a été **gardé** de l'orderflow n'est pas une règle mais une
  **mesure** : la section CONFLUENCE.

**Le CARNAGE comme filtre** : `regles_gelees_v2.py` proposait
`v8_hors_carnage`. V9 l'a mesuré et rejeté. Ce n'est pas une variable
instable, c'est une hypothèse réfutée.

**Instabilité observée le 13/08** : deux lectures du même panel
orderflow à quelques minutes d'intervalle ont donné des verdicts
**opposés** sur ALIGNE_HAUSSE — +18,09 avec 83 % de WR dans la
première, −7,67 et « méfiance » dans la seconde. Une cellule dont le
signe s'inverse entre deux lectures du même tableau est du bruit.

À ne pas confondre avec de l'instabilité : EXHAUSTION_SELL passe de
+46,97 (n=9) à +40,34 (n=10) entre les deux lectures. C'est un ticket
de plus, pas une contradiction — mais un seul ticket qui déplace la
moyenne de 6,63 EUR dit assez à quel point la cellule est fragile.

**Et un accord, qui vaut mieux qu'un désaccord** : la règle anti
contre-flux a été mesurée trois fois indépendamment — Δ −0,02, −0,15
(gel V9), +0,03 sur 128 signaux (lecture du 13/08). Trois valeurs qui
encadrent zéro. Cette règle ne vaut rien, et ce n'est pas une opinion.

## 4. Ce qui tient

- **Le filtre horaire 09h-11h** : Δ +5,43, le plus gros du panel,
  confirmé sur deux slicings. C'est la seule règle orderflow qui
  survit.
- **Le gradient x60** : H1 saute à +22,9 / +40,1 par ticket dans les
  six découpages, alors que M1–M5 se tiennent entre −10 et +3. C'est
  une **marche, pas une pente** — un Spearman répond à la mauvaise
  question. H1 a aussi un WR plus haut (56-73 % contre 40-47 %) *et*
  un EUR/ticket plus haut, ce qui écarte un pur effet de taille.
- **Le contre-cycle M1** (`regles_gelees_v2.py` v10, « la trouvaille
  la mieux étayée ») : M1 BEAR vente AVEC 193 → −20,89 · M1 BEAR achat
  CONTRE 120 → +11,31 · M1 BULL achat AVEC 254 → +3,39 · M1 BULL vente
  CONTRE 95 → +15,43. Réserve : l'effet disparaît sur M15, et M1 ne
  couvre que 662 / 1335.

## 5. En cours d'observation — 13/08

**`papier_tf.py`** — 36 cellules de trading papier, M10 à H4, bras 206
et 207, 24h/24, **lecture seule, aucun ordre**. Ni spread, ni
slippage, ni commission : les chiffres sont optimistes, et d'autant
plus que l'unité est courte.

**Décision du 13/08 — M10, M20, M30 passent en LIVE pendant la
séance.** Le moteur est déjà borné à 08:00–19:30 avec mise à plat
au-delà, donc l'ajout des cellules suffit : live en séance, papier en
dehors. `TFS_TRADED` passe de trois à six unités, soit **36 cellules
au lieu de 18 — l'exposition double**, lot inchangé à balance/20000.
H2 et H4 restent en papier pour la raison arithmétique de la
section 1. L'allumage des nouvelles unités passe par le calcul
**local** de `_cell_for_tf`, comme le M2 : le churn ne publie que
M1/M5/H1.

Conséquence à ne pas oublier en lisant les tableaux : à partir de ce
changement, M10/M20/M30 sont **à la fois** live en séance et suivies
en papier. Le papier reste donc un témoin utile — il dit ce que la
cellule aurait fait sans spread ni slippage — mais ce n'est plus une
observation indépendante du live.

**`x60_onset.py`** — observe les cellules H1 et photographie qui est en
position quand elles entrent et sortent.

Au 13/08 12:04, 11,8 h d'observation seulement. Rien de ce qui suit
n'a d'effectif pour conclure :

- M10 est la seule durée avec un N utilisable (8 par bras). Le **206 y
  passe devant le 207** (+13,17 contre +11,56), les deux à 50 % de WR.
  H2 et H4 n'ont encore **aucune** entrée fermée.
- Le papier n'a **aucune entrée fermée entre 05h et 07h**, mais dix
  cellules s'y sont ouvertes et courent encore. Une heure à zéro
  fermée n'est pas une heure sans signal.
- M10 SÉANCE 4 trades +8,06 · HORS SÉANCE 12 trades +13,80, les deux à
  50 % de WR. L'écart s'est **beaucoup resserré** en deux heures : à
  11:40 la séance était à −3,20 sur 2 trades. Couverture SÉANCE 3,8 h
  contre HORS 8,0 h, et 26 positions encore ouvertes ne figurent dans
  aucune des deux colonnes.
- 8 entrées du bras 207 sont écartées du compte : leurs 70 % ont été
  coupés en profit, les 30 % courent. Elles reviendront à leur
  clôture, avec leur résultat complet.

## 6. Trois chiffres qui se mesuraient eux-mêmes — 13/08

**Le compteur PARTIEL70.** Le regroupement des jambes considérait une
entrée comme close dès qu'une jambe existait. Une position 207 dont
les 70 % avaient été coupés **en profit** et dont les 30 % couraient
encore était donc comptée comme un trade terminé, avec pour seul
résultat son gain partiel — **positif par construction**, puisque la
sortie partielle ne se déclenche qu'en profit. Neuf entrées dans ce
cas, toutes du bras 207, ce qui lui donnait quatre durées gagnantes
sur quatre. Corrigé : les N des deux bras sont redevenus égaux, comme
ils doivent l'être pour des bras qui entrent sur le même signal.

**Les huit positions de 23:38:54.** Au démarrage de l'observateur,
`armes` partait vide, donc l'allumage en cours se lisait comme frais :
huit cellules ouvertes à la même seconde, sur aucun signal. Elles
portaient à elles seules la quasi-totalité des pertes attribuées à
trois unités de temps. Journal réinitialisé au 13/08 00:00, les lignes
archivées à côté.

**Le motif commun, et c'est le plus important :** dans les deux cas,
un chiffre était **garanti par sa méthode de calcul**, pas par le
marché. Quand un résultat semble trop beau, chercher l'artefact avant
de chercher l'explication.

**Le troisième cas, et il n'est pas résolu.** Question posée : les
positions qui vont *contre* la direction d'un x60 perdent-elles ?
Première lecture, sur le même actif : aucune tierce n'est jamais dans
le sens du x60 (0 sur 12), et les 12 opposées finissent à −8,55.

Deux corrections successives :

1. L'échantillon était dominé par un **reverse** — sortie et
   ré-entrée du même magic à la même seconde. Dans un reverse, être
   contre le x60 et être en perte ont la **même cause** : le marché
   vient de se retourner. En ne gardant que les x60 premier entrés,
   le −8,55 devient **−4,90 sur 8 présences**. La moitié de l'effet
   était le miroir du reverse.
2. Il reste que **« même actif / AVEC » compte zéro présence dans les
   deux catégories**. Ce n'est pas un échantillon maigre, c'est une
   impossibilité : on photographie à l'instant où le x60 vient de
   basculer sur un allumage frais, donc les cellules courtes du même
   actif tiennent encore la direction d'avant. Elles sont « contre »
   **par définition de l'instant choisi**.

**Le −4,90 n'a donc aucun groupe témoin, et ne conclut rien.** La
comparaison n'existera qu'en mesurant à la **sortie** du x60, où les
cellules courtes ont eu le temps de basculer. Non fait à ce jour.

À noter, sans conclure : « REVERSE / autre actif / CONTRE » sort à
**+33,22 sur 10 présences**, la meilleure cellule du tableau. Quand un
x60 se retourne, les positions à contre-sens sur les *autres* indices
s'en sortent bien.

## 7. Ce qu'on ne sait pas

- **L'ER est-il connu à l'entrée, ou calculé après coup ?** Si la
  barre Ninja utilisée est celle qui *contient* l'entrée, aucun filtre
  ER n'est implémentable, y compris la piste US30. Non tranché.
- Le gradient x60 tient-il **hors échantillon** ?
- Le x60 est-il vraiment « premier entré » ? Une observation directe
  le 13/08 08:00:17 : entrée US30 avec **0 tierce**, sortie 09:16:09
  avec 10 tierces présentes, +38,12 sur 2 tickets. n = 1 épisode.
- Pourquoi M10 et M20 n'ont produit aucun allumage certaines heures :
  muettes, ou bloquées par un filtre ?
- Les positions alignées sur la direction d'un x60 s'en sortent-elles
  mieux ? **Indécidable en l'état** — voir section 6 : à l'instant de
  l'entrée d'un x60, il n'existe aucune position alignée sur le même
  actif. Il faut mesurer à la sortie.

## 8. Méthode — les trois règles de lecture

1. **Un chiffre sans sa couverture ne vaut rien.** « Zéro trade en
   Asie » et « l'observateur ne tournait pas cette nuit-là » produisent
   le même fichier vide. Toutes les mesures d'ici portent une colonne
   « observé » pour cette raison.
2. **Sous 30 tickets, on décrit, on ne conclut pas.** Le panel
   orderflow porte ce garde-fou à l'écran (`MIN_N`) ; il faut le lire
   avant les chiffres qu'il encadre.
3. **Un cumul de règles choisies parce que leur Δ était positif sur le
   même échantillon est positif par construction.** C'est un plafond,
   jamais un plan.
