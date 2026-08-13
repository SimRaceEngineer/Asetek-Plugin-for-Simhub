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

**Version 8 — 13/08, 16:35.** Sept choses ont changé depuis la v2 du
matin, et un conseil donné sans elles arrivera à côté :
0. **Le filet fixe engage 17,6 % du compte sur un seul ticket US30**,
   contre 7,0 % sur US100 (section 2). Rapporté au risque, le
   classement des actifs sur le setup 60 **s'inverse**. Toute
   comparaison entre actifs non normalisée compare des paris de
   tailles différentes.
0bis. **Les stops se déplacent en profit, sur les DEUX bras** — seuil
   entre +10 et +39 € (section 2). « Filet fixe, jamais suivi » était
   faux. Le hold-until-reverse du 206 n'est donc pas intact.
0ter. **Sur le x60, le bras 206 bat le 207 de +16,76 par ticket** sur
   les trois actifs, à entrées identiques — environ 1 590 €
   (section 4). Le 207 coupe 70 % tôt *et* remonte son stop.
0quater. **« Le x60 entraîne la fenêtre » ne tient plus** : 91 % de
   l'effet vient de trois fenêtres, toutes antérieures au 05/08
   (section 4). Le gradient x60, lui, tient encore.
1. **M10, M20 et M30 sont en live** depuis 13:10 (section 5). Le
   moteur ne tourne plus sur neuf magics par bras.
2. **L'ER est postérieur, et le flux est différé de 10 min** —
   question tranchée, section 7.
3. **L'archive orderflow a été rognée puis restaurée** ; la fenêtre
   réellement utilisable est 12 juin → 13 août (sections 5 et 6).
4. **Les barres orderflow portent les prix depuis 15:37** (section 5),
   après avoir passé des mois sans. Mais ce sont ceux du *future*, pas
   du CFD : les soustraire d'un prix d'entrée MT5 donnerait la base
   entre deux instruments, pas un coût de retard.

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

Vérification indirecte le 13/08 : `familles.py` lit 3087 tickets à six
chiffres et rapporte **« aucun conflit — le chiffre d'actif colle au
ticket »**. Le schéma se relit donc sans exception sur l'historique,
y compris pour les nouvelles unités 10/20/30.

## 2. Les règles de production, lues dans le code

- **Entrée** : allumage FRAIS de `churn_regime._analyze` — direction
  changée depuis le dernier consommé. Un basculement BULL→BEAR compte
  même si `ignition` n'est jamais repassé à False (correctif 17/07).
- **Filtre** : RSI(14) M3 > 50 pour un achat, < 50 pour une vente
  (ENFORCE 20/07, fail-open : si le RSI manque, on passe).
- **Stop** : un **filet fixe** — 4000 / 200 / 1600 points selon
  l'actif — **plus un déplacement en profit, sur les DEUX bras.**
  L'ancienne formule « jamais suivi » est fausse.
  Le déclencheur est le PROFIT, pas le bras. Book du 13/08 16:05 :

  | magic | profit | stop |
  |---|---|---|
  | 207210 M10 US500 | +208,21 | déplacé |
  | 207220 M20 US500 | +190,67 | déplacé |
  | 207302 M2 US100 | +83,80 | déplacé |
  | **206302 M2 US100** | **+79,88** | **déplacé** |
  | 207102 M2 US30 | +50,49 | déplacé |
  | 207101 M1 US30 | +38,95 | déplacé |
  | 207105 M5 US30 | +9,61 | filet |
  | 207360 H1 US100 | +8,56 | filet |
  | 206360 H1 US100 | +7,83 | filet |
  | 207120 M20 US30 | −110,75 | filet |

  Seuil entre +10 et +39 €. **Preuve directe** : le ticket 172133611
  (207220) portait encore le filet à 15:42 avec +17,71, et un stop
  déplacé à 16:05 avec +190,67. Même position, deux observations.
- **Ce n'est PAS `auto_be_after_mfe`.** `trading_engine.py` l'importe
  (l.3031) avec `candle_trail` (l.3153), et il fait bien du BE +
  lock-half — 53 à 295 déplacements/jour selon son propre commentaire.
  Mais son `_is_in_scope()` ne couvre que 93000-97999, 5000-5009,
  6000-6009, 7000-7099, 8000-8009, 99500-99502, 100100-100300,
  53000-53999 et 1100-1399 à suffixe 27/28/32/33. **206xxx et 207xxx
  n'y sont pas.** Le déplacement vient d'ailleurs — `candle_trail`
  probablement. Non tranché.
- **Conséquence sur le x60, et elle n'est pas rassurante** : le
  hold-until-reverse du bras 206 n'est **pas** intact. Une cellule 206
  suffisamment en profit voit son stop remonter, donc peut sortir
  autrement qu'au reverse. Le +39,03 par ticket du 206 sur le setup 60
  décrit donc « entrée à l'allumage, sortie au reverse **ou** au stop
  remonté », pas la règle écrite. Aucune cellule H1 n'a encore été
  observée avec un stop déplacé, mais les deux vues n'ont montré que
  des H1 sous le seuil : **l'absence vient de l'échantillon, pas du
  mécanisme.** Erreur commise ici même une heure plus tôt — voir
  section 6, sixième cas.
- **Lot** : balance / 20000, minimum 0.10.
- **⚠ LE FILET N'EST PAS ÉQUIVALENT D'UN ACTIF À L'AUTRE.** Converti
  en euros au lot courant (0,95), à partir du book vivant :

  | actif | filet | EUR/pt/lot | risque | % du compte |
  |---|---|---|---|---|
  | US30 | 4000 | 0,867 | **3 295 €** | **17,6 %** |
  | US500 | 200 | 8,670 | 1 647 € | 8,8 % |
  | US100 | 1600 | 0,867 | 1 318 € | 7,0 % |

  Balance 18 763 €. **Un seul ticket US30 engage 17,6 % du compte**,
  soit 2,5 fois le risque d'un ticket US100 — et il y avait quatre
  positions US30 ouvertes simultanément. Ce n'est pas un stop, c'est
  un plafond de catastrophe : il ne se déclenche quasiment jamais, et
  quand il le fera, ce sera pour un montant qu'aucune moyenne du
  dossier n'anticipe.
  **Effet sur toutes les comparaisons entre actifs** : rapporté à son
  propre filet, le classement du setup 60 s'inverse — US30 +43,04 =
  **1,31 %** du filet, US500 +38,99 = **2,37 %**, US100 +34,30 =
  **2,60 %**. Le « meilleur » actif en euros par ticket est le
  **dernier** par unité de risque. Toute lecture de `familles.py` qui
  compare US30, US500 et US100 sans cette normalisation compare des
  paris de tailles différentes.
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
  Confirmé par `familles.py` le 13/08 sur 3311 tickets (21/07 →
  13/08) : **setup 60 = +30,47 par ticket sur 186, WR 63 %**, contre
  **−2,66 sur les 3125 autres**. Les six cellules sont positives, sans
  exception — US30 206 +43,04 · US500 206 +38,99 · US100 206 +34,30 ·
  US30 207 +30,09 · US500 207 +23,69 · US100 207 +11,57.
  **Depuis le 05/08 l'avantage est divisé par deux** (+15,52 sur 83,
  WR 67 %) mais reste le seul setup positif du corpus (−8,69 sur
  1851). Aucune des six cellules n'atteint 20 tickets sur cette
  fenêtre : on décrit, on ne conclut pas.
- **Sur le x60, le bras SIMPLE bat le bras à sortie partielle — sur
  les trois actifs.** Même signal d'entrée, seule la sortie diffère,
  donc c'est une comparaison appariée :

  | actif | 206 | 207 | écart |
  |---|---|---|---|
  | US30 | +43,04 (31) | +30,09 (32) | **+12,95** |
  | US500 | +38,99 (34) | +23,69 (35) | **+15,29** |
  | US100 | +34,30 (26) | +11,57 (28) | **+22,74** |
  | ensemble | **+39,03** (91) | **+22,27** (95) | **+16,76** |

  Soit environ **1 590 € laissés par le bras 207** sur la période, à
  entrées identiques. Depuis le 05/08 l'écart persiste (+20,95 contre
  +10,22) mais s'inverse sur US100 (−4,61) : cinq comparaisons sur six
  vont dans le même sens.
  **Le mécanisme est maintenant connu** (section 2) : le 207 coupe
  70 % tôt *et* remonte son stop, donc il tronque deux fois un edge
  qui vit de laisser courir jusqu'au reverse. Réserve : trois actifs
  ne font pas un grand échantillon de comparaisons, et les deux
  fenêtres se recouvrent. Mais la direction, la taille et le mécanisme
  concordent — c'est la piste la plus actionnable du 13/08.
- **⚠ Ce qui NE tient pas : « le x60 entraîne la fenêtre ».**
  `familles.py` montre ALLUME +473,79 par fenêtre contre PRESENT
  −34,24 et ABSENT −37,45, et en tire que le rang ajoute quelque
  chose. Mais le détail des 16 fenêtres dit autre chose : **trois
  d'entre elles portent 6 931 € des 7 580 €, soit 91 %** — 04/08
  +2 960, 31/07 +2 396, 29/07 +1 575. **Les trois sont antérieures
  au 05/08.** Depuis, les 5 fenêtres d'allumage totalisent
  **−267,40**, et le script refuse lui-même de conclure (5 allumages
  pour un minimum de 8). L'effet « il mène » est donc un phénomène de
  fin juillet / début août qui **ne s'est pas reproduit une seule
  fois** depuis le passage en régime range. Huit jours seulement, donc
  ce n'est pas une réfutation — c'est un avertissement : le chiffre le
  plus spectaculaire du dossier x60 repose sur trois séances. À ne pas
  confondre avec le gradient x60 ci-dessus, qui, lui, tient encore.
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
dehors.

**FAIT — 13/08 13:10 : le moteur a été redémarré, les nouvelles
cellules sont EN LIVE.** Les patchs sur `ignition_trader.py` et
`ignition_trader_trail.py` ne suffisaient pas : `trading_engine.py`
les *importe*, il tournait depuis le 12/08 avec l'ancien code en
mémoire, et `START_TRADING_STACK_V3.bat` ne tue pas un moteur sain —
il le rafraîchit. Il a donc fallu arrêter le moteur et relancer V3.
Moteur **PID 9140**. Première entrée sur une cellule neuve :
**`207230` (M30 US500) à 13:12:23**, sans rafale au démarrage.

Le compte exact, bras par bras — il ne se déduit pas d'un simple
« ×2 », les deux bras n'ont pas la même liste :

| bras | `TFS_TRADED` avant | après | cellules avant → après |
|---|---|---|---|
| 206 | M2, M5, H1 | + M10, M20, M30 | 9 → **18** |
| 207 | M1, M2, M5, H1 | + M10, M20, M30 | 10 → **19** |

Le 207 compte une cellule de moins que 3×7=21 parce que **M1 reste
désactivé sur US500 et US100** (`DISABLED_CELLS`, inchangé). Total
**19 → 37 cellules live**, lot inchangé à balance/20000 :
**l'exposition double**.

H2 et H4 **restent en papier**, et pas par prudence : c'est
arithmétique, voir section 1 — sept chiffres de magic, deux décodeurs
qui se trompent d'actif, donc de SL. L'allumage des nouvelles unités
passe par le calcul **local** de `_cell_for_tf`, comme le M2 : le
churn ne publie que M1/M5/H1.

Conséquence directe pour toute recommandation : un conseil du type
« ne code pas M10/M20/M30 avant d'avoir N » arrive **après** — ces
unités tournent en argent réel depuis 13:10. La question utile n'est
plus s'il faut les activer, mais ce qu'on mesure maintenant qu'elles
le sont, et à quel seuil on les retirerait.

**Premiers tickets fermés, et ils ne prouvent rien** (`familles.py`,
13/08 en fin d'après-midi) : setup 10 → **9 tickets** +16,68 · setup
20 → **3 tickets** −52,78 · setup 30 → **1 ticket** +45,91. Le script
marque les trois d'un « ? » : sous 20 tickets, il refuse de conclure,
et il a raison. Piège immédiat à ne pas manquer : au même moment, les
positions M10/M20 **encore ouvertes** flottaient à +287 € et
portaient à elles seules tout le positif du book. Fermées négatives,
ouvertes positives — lire l'un ou l'autre comme un verdict est la
même erreur, et c'est celle de la section 6.

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

**L'acquisition orderflow — l'objectif est un croisement en septembre.**
La chaîne : ticks SierraChart (`.scid`) → `scid_orderflow.py` →
`C:\OrderflowExport\of_<actif>_<date>.jsonl` → `orderflow_join.py` →
panneau 8097. `rafraichir_orderflow.py` rappelle l'export toutes les
30 s — sans quoi la donnée du panneau avait jusqu'à dix minutes de
gigue en plus du différé du flux.

Ce qui est réellement exploitable, après audit : **12 juin → 13 août**
sur US30 et US500, soit ~45 jours — et non les 3,5 mois que suggèrent
les tailles de fichier. **US100 (MNQ) n'est pas dans le flux** :
`_Free_Trial_Symbols` ne contient que MES, YM et TICK-NYSE, il faut un
package de service. Les ticks sont rechargeables sur ~186 jours en
arrière, donc rien n'oblige à décider maintenant.

**Ce que contient une barre — corrigé le 13/08 à 15:37.** Jusque-là,
l'enregistrement ne portait **aucun prix absolu** :

```
ts, epoch_utc, asset, src, delta, cum_delta, vol,
range_ticks, close_pos, er, net, gross, events
```

Ni `close`, ni `high`/`low`. Or `read_bars` les tenait depuis toujours
(`b["c"]` mis à jour à chaque tick, `b["h"]`, `b["l"]`) et `_detect`
les recevait : ils étaient calculés, utilisés, puis **jetés trois
lignes avant l'écriture**. `patch_scid_prix.py` les écrit —
`close`, `high`, `low`, treize champs d'origine intacts.

Contrôle d'intégrité sur une barre réelle (15:27) : `high` − `low` =
54045 − 54018 = **27,0**, soit exactement `range_ticks` ; et
(`close` − `low`) / amplitude = 10/27 = **0,370**, soit exactement
`close_pos`. Les nouveaux champs reconstituent les anciens au chiffre
près — ce sont bien les prix d'origine, pas du remplissage plausible.

**Couverture au 13/08 au soir** : aujourd'hui et hier portent les prix
(874/874 sur US30), parce que la boucle appelle `--days 1` et que
depuis le calage à minuit ça réécrit ces deux jours en entier. Le
**12 juin → 11 août attend un rattrapage à froid** (`--days 65`,
boucle arrêtée pendant l'opération).

**Ce que ça ne débloque pas.** Les prix écrits sont ceux du **future**
(YM, MES) ; les tickets sont des **CFD** (US30, US500). Entre les deux
il y a une base et des tailles de tick différentes. Soustraire
`_close_barre` d'un prix d'entrée MT5 donnerait **la base entre deux
instruments**, pas le coût du retard — un chiffre stable, plausible,
et sans rapport avec la question posée. Le coût du retard reste
mesurable en **différence interne au future**, ou après estimation de
la base.

Le but de l'attente : croiser un mois et plus d'orderflow avec
l'historique d'ignition et d'ignition x60, pour voir si l'orderflow
peut se mettre en correspondance avec l'allumage. Tant que ce
croisement n'est pas fait, l'orderflow reste une **mesure**, pas une
règle — voir section 3.

## 6. Quatre chiffres qui se mesuraient eux-mêmes — 13/08

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

**Le quatrième cas — l'archive qui se rognait elle-même.** Trois
lignes de `scid_orderflow.py` prises ensemble effaçaient de
l'historique : `since = time.time() - a.days * 86400` (fenêtre partant
de l'heure courante), `if ep < since_epoch: continue` (barres
antérieures sautées), et `open(fp, "w")` (le fichier du jour réécrit
**en entier**). Un `--days 1` lancé à 14h39 réécrivait donc le fichier
de la veille avec les seules barres postérieures à 14h39. Constaté en
direct : le 10 août est passé de **1312 barres à 501**, le 12 de
**1299 à 499**, entre deux audits espacés de neuf minutes — pendant
qu'une boucle appelait `--days 1` toutes les 30 secondes et rognait
l'archive en continu, le point de coupe avançant avec l'horloge.
Restauré par `--days 20`, corrigé par `patch_scid_minuit.py` : `since`
se cale sur **minuit local**, donc un fichier de jour est soit réécrit
en entier, soit pas touché.

C'est le même motif que les trois autres, sous sa pire forme : **un
jour tronqué a exactement la forme d'un jour complet** — mêmes champs,
mêmes valeurs plausibles, moins de lignes. Croisé tel quel en
septembre, il aurait produit des moyennes calculées sur une
demi-séance en les croyant calculées sur une journée.
`couverture_orderflow.py` existe pour que ça se voie avant l'étude et
pas pendant. Sa liste de jours utilisables **fait partie de l'étude**,
ce n'est pas de l'intendance.

**Le motif commun aux quatre, et c'est le plus important :** un chiffre
**garanti par sa méthode de calcul**, pas par le marché — et à chaque
fois, le fichier avait l'air parfaitement normal. Un gain partiel qui
ne se déclenche qu'en profit est positif par construction. Un
observateur qui démarre avec un état vide invente des entrées par
construction. Un camp « AVEC » observé à l'instant du basculement est
vide par construction. Un fichier réécrit depuis l'heure courante perd
sa matinée par construction. Quand un résultat semble trop beau ou
trop net, **chercher l'artefact avant de chercher l'explication**.

**Le sixième, et il est de moi, une heure avant d'écrire ces lignes.**
À 15:42 j'ai lu le book et conclu que **le bras 206 ne déplace jamais
ses stops** — les trois positions 206 portaient exactement le filet.
Vrai, et sans valeur : **les trois étaient en perte**, et le
déplacement est conditionné au profit. Ma conclusion était garantie
par l'échantillon, pas par le mécanisme. Vingt minutes plus tard,
`206302` à +79,88 avait un stop remonté. J'avais même écrit dans ce
journal que « le gradient x60 du 206 n'est pas contaminé » — c'était
faux, et ça rassurait dans la mauvaise direction. Le motif de cette
section vaut aussi pour qui l'écrit.

**Le cinquième, et il n'a pas eu lieu — parce qu'on ne l'a pas fait.**
Le 13/08 vers 15h45, le conseil a été donné de couper à la main le
short H1 US100 (`206360`, −141 € de flottant) « sur tout rebond qui
échoue ». Le bras 206 est *hold-until-reverse* : le gradient x60
mesuré plus haut vient de trades allés **jusqu'à leur reverse**,
pertes comprises. Couper sélectivement les queues perdantes rendrait
le chiffre garanti par l'intervention, pas par le marché — et la série
live cesserait d'être comparable à la mesure gelée. Une cellule se
retire **sur N, par règle**, jamais sur un mouvement en cours.

## 7. Ce qu'on ne sait pas

- **TRANCHÉ le 13/08 : l'ER est postérieur.** `orderflow_join.py`
  apparie par `minute = int(e // BAR_SEC) * BAR_SEC` — l'arrondi va
  vers le **bas**, donc la barre retenue est celle qui *contient*
  l'entrée, et elle se referme après. Les chiffres du gel V9, y
  compris la piste US30 (+1,57 / −14,59 / +11,97 / +20,43), décrivent
  ce qui s'est passé **pendant** le trade ; ils n'étaient pas lisibles
  au moment de décider. Aucune règle live ne les reproduit telle
  quelle.
  Ce qui reste ouvert, et c'est mesurable : (a) l'ER de la barre
  **précédente**, connu à l'instant t ; (b) **attendre la clôture** de
  la barre en cours puis entrer — c'est l'ER de la bonne barre, au
  prix d'un retard de 0 à 60 s. `patch_orderflow_er_decale_v2.py`
  ajoute `_er_prec`, `_er_band_prec` et `_close_barre` ; **appliqué le
  13/08 à 15:25**. (a) est donc mesurable dès maintenant. (b) ne
  l'est pas encore : les prix existent depuis 15:37, mais ce sont ceux
  du future — voir section 5.
- **Le flux SierraChart est DIFFÉRÉ de 10 min 10 s** (`DD: 00:10:10`
  dans l'en-tête du graphique). Ce n'est pas un réglage : c'est
  l'abonnement bourse. Tant qu'il n'est pas levé, *aucun* filtre
  orderflow n'est jouable en live, quelle que soit la barre choisie —
  le blocage n'est plus l'appariement, c'est le tuyau.
  `rafraichir_orderflow.py` surveille ce retard et le dira s'il tombe.
- Le gradient x60 tient-il **hors échantillon** ? Élément nouveau du
  13/08 : il tient sur 21/07 → 13/08 (+30,47 sur 186) *et* sur la
  sous-fenêtre 05/08 → 13/08 (+15,52 sur 83), donc il survit à un
  changement de régime — mais amputé de moitié. Ce qui ne survit pas,
  c'est l'effet « il mène la fenêtre » : voir section 4.
- **Une hypothèse testée et RÉFUTÉE le 13/08** : « 206360 (H1 US100)
  est le membre faible de la famille x60 ». Elle venait de son absence
  d'une liste de cellules gagnantes citée par le REPL. `familles.py`
  la contredit : **+34,30 par ticket sur 26, WR 69 %** — troisième des
  six sur l'historique complet. Depuis le 05/08 elle est **plate**
  (−1,79 € au total sur 12 tickets, WR 58 %), ce qui explique son
  absence d'une liste de positifs sans rien dire de plus. Une cellule
  à zéro n'est pas une cellule cassée.
- **224 tickets « hors format »** (magics à quatre chiffres : 2423,
  2403, 2411, 2413, 2422, 2412, 2402) pèsent **−1 314,70 à −5,87 par
  ticket, WR 23 %**. Ils ne sont décrits nulle part dans ce journal et
  n'appartiennent à aucun des bras documentés. D'où viennent-ils, et
  qui les passe ?
- **Le H1 papier et le H1 de production ne sont pas le même signal.**
  `papier_tf.py` le dit lui-même (l.77-82) : en production le H1 lit
  la cellule de `churn.get_churn(asset)`, alors que le papier fait
  passer les six durées par `_analyze` sur des barres locales — sinon
  H1 serait calculé autrement que ses cinq voisins et la comparaison
  entre durées, qui est tout l'objet du module, ne voudrait plus rien
  dire. Conséquence à ne pas rater : un écart entre H1 papier et H1
  live **n'est pas** forcément un effet de taille d'échantillon ou de
  spread. Ce peut être un constat sur le **churn** lui-même —
  c'est-à-dire sur le calcul qui porte la production. Deux signaux
  différents, pas deux échantillons d'un même signal.
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
