# Amplitude et resultat — ce qui tient, ce qui ne tient pas

Etat au 11/08/2026. A relire avant d'ecrire `regles_gelees_v10.py`.

Ce fichier existe parce que la premiere lecture, le matin du 11/08, etait
trop favorable, et que la version corrigee du soir est moins facile a
retenir. Sans note ecrite, c'est la premiere qui resterait.

---

## Ce qui a ete mesure

Trois passes, dans cet ordre :

| script | source | verdict |
|---|---|---|
| `amplitude_pnl.py` | `magic_daily_stats` + MT5 | gradient causal −3,28 / −2,13 / −0,38, WR 44/45/52 |
| `amplitude_familles.py` | MT5 seul | gradient causal −4,21 / −1,72 / −0,39, WR **49/42/52** |

Meme periode, 56 seances du 26/05 au 11/08. `N_PREC = 3`, fixe avant de
connaitre le resultat et **jamais rejoue** ensuite.

---

## Trois raisons de se mefier du resultat global

### 1. Deux familles mortes portent le tiers calme

- M186, causal calme : **−33 266 EUR** sur 1 349 trades (−24,66)
- M178, causal calme : **−12 546 EUR** sur 687 trades (−18,26)

Soit **~77 % du tiers calme (−59 822) sur 14 % de ses trades**. Les deux
sont a 0,00 depuis fin juillet.

Sans elles, le tiers calme tombe a environ −1,15 EUR/trade et l'ecart
calme→agite passe de **+3,83 a ~+0,76** — cinq fois moins.

*(Approximatif : les tiers de chaque famille sont recoupes sur ses propres
seances, les bornes ne se superposent donc pas exactement.)*

Le gradient global ne dit pas « l'amplitude ordonne le resultat ». Il dit
« deux modules perdaient, et ils tradaient plus au calme ».

### 2. Le garde-fou WR ne survit pas au changement de source

J'avais designe le WR comme plus fiable que le EUR/trade, parce qu'il ne
peut pas etre porte par trois gros tickets. Sur MT5 seul il fait
**49 % → 42 % → 52 %** : non monotone.

La monotonie 44/45/52 venait de la definition de « win » de
`magic_daily_stats`, differente du net apres swap et commission. C'etait
un artefact de source. **Seul le gradient en EUR/trade survit — et c'est
le plus manipulable des deux.**

### 3. Entre familles, la direction est un tirage a pile ou face

Ecart calme→agite, lecture causale, 16 familles :

| l'amplitude aide (9) | l'amplitude nuit (7) |
|---|---|
| M186 +21,81 · M178 +14,60 · M188 +6,68 · M206 +5,96 · M215 +5,68 · M207 +5,11 · M500 +2,04 · M131 +1,64 · M133 +1,21 | M201 **−27,90** · M152 −8,20 · M161 −2,00 · M164 −1,81 · M154 −1,56 · M242 −1,15 · M159 −0,82 |

9/16, test de signe p ≈ 0,4. **L'effet n'est pas structurel.** M201 pointe
violemment a l'envers (+10,64 calme, −17,26 agite).

---

## Ce qui survit : les jumeaux, et eux seuls

| | calme 0,63–1,01 | moyen 1,04–1,28 | agite 1,28–1,64 |
|---|---|---|---|
| **M207** | −3,41 (593 tr, WR 49 %) | **+1,56** (1017, 53 %) | **+1,70** (785, 58 %) |
| **M206** | −2,52 (617 tr, WR 37 %) | **+3,99** (570, 45 %) | **+3,44** (624, 51 %) |

1. Changement de **signe**, pas une nuance de perte.
2. WR **monotone** pour les deux (49→53→58 et 37→45→51). Ici il tient.
3. Volumes **equilibres** entre tiers : aucun tiers vide ne fabrique l'effet.
4. Ce n'est pas un gradient mais un **seuil** — moyen vaut autant qu'agite —
   et les deux familles le placent au meme endroit, **causal ~1,02**, alors
   que leurs tiers ont ete coupes separement.

Une forme a seuil est plus solide qu'un gradient : elle ne demande pas que
« plus d'amplitude = toujours mieux », seulement qu'en dessous d'un niveau
ca ne marche pas.

**Reserve : 16 seances, 5 a 7 par tiers.**

M206 et M207 sont aussi le seul terrain ou le confondant de flotte tombe :
ils tradent sur toute la fenetre, alors que la comparaison avant/depuis
melange partout ailleurs un changement de regime et l'arret d'une
vingtaine de familles fin juillet.

---

## Le defaut a declarer, pas a corriger

L'indicateur causal est **en retard de trois seances**.

| jour | ampl du jour | causale | tiers | P&L |
|---|---|---|---|---|
| 05/08 | 0,90 | **1,37** | agite | −3 925 |
| 06/08 | 0,84 | **1,28** | agite | −2 050 |
| 07/08 | 0,65 | **1,20** | agite | −1 180 |
| 10/08 | 0,40 | 0,79 | calme | −2 965 |
| 11/08 | 0,34 | 0,63 | calme | −1 743 |

L'amplitude du jour est calme des le 05/08, mais la moyenne des trois
seances precedentes traine encore la tendance du 31/07–04/08.

Une regle « ne trade pas sous 1,02 » aurait laisse passer −7 155 EUR et
n'aurait bloque que les 10 et 11/08 : **4 708 evites sur 11 863, soit
40 %**. Utile, pas salvateur. *(Illustratif : les tiers connaissent
l'avenir, ce n'est pas un backtest.)*

**Ne pas ajuster `N_PREC` pour rattraper ce retard.** C'est le reglage a
posteriori interdit dans l'en-tete du script avant que le resultat soit
connu. Le retard se declare dans le fichier gele ; il ne s'optimise pas.

---

## Hors echantillon des le 12/08

Causale du 12/08 = (0,65 + 0,40 + 0,34) / 3 = **0,46**.

Plancher de l'echantillon : **0,63**. Le dispositif trade dans un regime
jamais rencontre en 56 seances. Rien dans les tableaux ci-dessus ne
s'applique en dessous de 0,63, et l'extrapoler serait inventer.

---

## Ce qu'il faudrait pour un gel V10

A ne pas poser avant que V9 ait rendu son verdict le 01/09.

- [ ] Seuil **glissant**, calcule sur les seules seances passees. Les tiers
      actuels sont coupes en connaissant l'avenir.
- [ ] Restreint a **M206 / M207**. Le pile ou face entre familles interdit
      d'en faire une regle generale.
- [ ] Un **temoin** et un **controle negatif**, comme aux gels precedents.
- [ ] Le **retard de trois seances** ecrit noir sur blanc dans le fichier.
- [ ] `N_PREC = 3` conserve tel quel, ou alors les deux valeurs testees
      declarees a l'avance avec le cout du test multiple assume.

## Rappel de contexte, corrige le soir meme

Cette note portait, en fin d'apres-midi, l'avertissement suivant :
`churn_trades*.jsonl` ne contient aucun champ rails, donc le verdict hors
echantillon du gel V9 serait incalculable.

**C'etait faux, et c'est corrige le 11/08 au soir.** Les rails sont ecrits
par `churn_trade_logger._write_series()` dans
`docs/rails_trades/series_DATE.jsonl`, par actif et par pas de temps —
ailleurs que la ou je les cherchais, pas absents. `rails_join.py` les joint
a chaque ticket au dernier instantane anterieur a son entree : couverture
0 % → 93 %, decalage median 17 s. Le gel V9 a ete pose le 11/08 et rendra
son verdict le 01/09.

L'erreur est laissee ici plutot qu'effacee, comme au journal : elle a coute
une demi-journee a chercher au mauvais endroit, et c'est le genre de detour
qu'on refait si on n'en garde pas la trace.

**Ce qui reste prioritaire sur toute nouvelle hypothese d'amplitude** n'est
donc plus le V9, mais le trou du matin — voir `NOTES_sorties.md`. Il repose
sur 11 seances et 1 150 tickets, garde le meme signe dans deux regimes
opposes, et ne demande aucun seuil a calibrer. L'amplitude, elle, tient sur
seize seances avec un indicateur en retard de trois.
