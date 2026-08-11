# Gel V9 — reference in-sample et criteres du verdict

Gel pose le **11/08/2026**. `gel_v9_2026-08-11.json`.
`regles_gelees_v9.py` SHA-256 `dcf4d07fe5de42f02b8ac1f962d904001de55d6ae7bce69c719a942269e9e2b1`.
**Ne plus toucher au fichier de regles.**

Verdict prevu le **01/09/2026**, sur les tickets d'entree posterieure au
11/08. Environ quinze seances.

---

## Comment le gel a pu tourner

Il ne pouvait pas, jusqu'au 11/08 : `oos_v9 --champs` annoncait une
couverture famille X de 0 %. J'en avais conclu que le panel ne persistait
pas les rails — **c'etait faux**. `churn_trade_logger._write_series()` ecrit
`rails_pos` et `rsi_pos` par actif et par pas de temps dans
`docs/rails_trades/series_DATE.jsonl`.

`rails_join.py` joint chaque ticket au dernier instantane **anterieur** a son
entree. Sur 2 721 tickets : 93 % renseignes aux quatre pas de temps,
**decalage median 17 s** (moyen 16, 90e centile 30, max 220). Couverture X
et Y a 93 % sur le corpus complet, 100 % sur la fenetre du gel.

Controle croise : le verdict churn compte `CHURN=1064 · CLEAN=196 ·
MIXED=923 · OK=538`, et `sorties2.py` — ecrit separement — donne
`1063 · 196 · 923 · 538`. Deux lecteurs independants, meme corpus, au
ticket pres.

---

## Reference in-sample — 2 555 tickets, 10 seances, 29/07 → 11/08

| regle | N | EUR/tk | ecart | p seance | p signe | p heure |
|---|---|---|---|---|---|---|
| X0 reference | 2555 | +0,47 | — | — | — | — |
| **X1 pas contre M1** | 2040 | +4,75 | **+4,27** | **0,000** | **0,002** | **0,000** |
| X2 temoin : aucune vente | 1336 | +2,40 | +1,92 | 0,483 | 1,000 | 0,079 |
| X3 pas contre M3 | 1964 | +2,76 | +2,28 | 0,117 | 0,754 | 0,002 |
| X4 temoin inverse : M5 | 1928 | −0,10 | −0,57 | 0,782 | 0,754 | 0,994 |
| X5 negatif : que contre M1 | 1853 | −2,65 | −3,12 | 0,251 | 0,754 | 0,005 |
| X6 X1 et X3 empiles | 1625 | +6,23 | +5,76 | 0,013 | 0,344 | 0,000 |
| **Y1 capitulation** | 168 | +21,57 | **+21,10** | 0,005 | 0,039 | 0,000 |
| Y2 temoin : MIXED seul | 873 | +3,15 | +2,67 | 0,404 | 0,754 | 0,389 |
| Y3 temoin : desaccord seul | 486 | +4,11 | +3,64 | 0,618 | 0,754 | 0,032 |
| **Y4 NEGATIF : miroir** | 60 | +9,57 | **+9,10** | **0,003** | 0,062 | 0,235 |

**In-sample ne prouve rien** : les deux regles ont ete choisies sur ces
donnees. Ce tableau sert de reference, pas de preuve.

---

## Ce qui va bien

**X1 est propre.** Les trois colonnes au plancher. 0,002 est le minimum
atteignable sur 10 seances, donc X1 va dans le meme sens 9 ou 10 fois sur
10. Le temoin X2 est nul a p signe = 1,000, le controle negatif X5 est
correctement negatif. C'est le comportement attendu d'un dispositif de gel
qui fonctionne.

En euros : X1 ecarte 515 tickets sur 2 555 et fait passer le total de
+1 209 a **+9 684 EUR**. Les tickets ecartes valaient **−16,46 EUR piece**.
Effet concentre, pas diffus.

**Ne pas empiler.** X6 a un ecart plus gros (+5,76) mais son p signe passe
de 0,002 a **0,344** : la moyenne monte, la regularite s'effondre. X3 seul
ne tient pas non plus (p seance 0,117, p signe 0,754). **La tete de serie
est X1, seule.**

---

## Ce qui ne va pas : Y4

Y4 est le miroir strict de Y1 et devrait etre mauvais. Il fait **+9,57
EUR/ticket, p seance 0,003**.

Lecture la plus probable : Y1 ne capte pas la *capitulation* mais le
**desaccord M1/M15 dans n'importe quel sens**. Y3 le corrobore — le
desaccord seul vaut deja +3,64 — et le churn MIXED l'amplifie dans les deux
directions.

Y4 ne passe pas la regle des trois colonnes (p signe 0,062, p heure 0,235)
et ne compte que 60 tickets. Ca n'annule donc pas Y1. Mais un controle
negatif a +9,57 est exactement le signal qu'on ignore avant de publier une
fausse decouverte.

---

## Correction a ma propre mise en garde

J'avais annonce que X4 risquait de bien noter a cause du confondant vendeur
(les ventes a −8,67 EUR/ticket sur la fenetre). **Ca ne s'est pas produit** :
X4 fait −0,57 d'ecart, p a 0,78 / 0,75 / 0,99. Et l'inversion M5 observee
sur le panel ne se reproduit pas ici.

---

## Le risque connu du verdict

La fenetre in-sample **enjambe les deux regimes** : jambe de tendance
(29/07–04/08) et range (05/08–11/08). Elle sort a +0,47 EUR/ticket en
reference, alors que le range seul est a −8,87.

Si le 12/08 → 01/09 est integralement du range, X1 sera jugee dans des
conditions qui n'ont jamais existe isolement en in-sample. Ce n'est pas une
raison de renoncer — c'est la definition d'un test hors echantillon — mais
c'est ecrit **avant** le resultat, pour qu'on ne fabrique pas l'explication
apres coup.

---

## Criteres du 01/09, poses le 11/08 avant toute donnee

**Preparation obligatoire.** Relancer `rails_join.py` d'abord : les series
s'accumulent, le fichier joint est un instantane. Reporter le decalage
median. **S'il depasse 60 s, le verdict est qualifie** et le dire.

**Tete X1 — succes si :**
- [ ] ecart hors echantillon **positif**, et
- [ ] les **trois** colonnes p ≤ 0,05, et
- [ ] X2 et X5 se comportent encore en temoin et en controle negatif.

**Tete Y1 — succes si :**
- [ ] ecart hors echantillon positif, et
- [ ] les trois colonnes p ≤ 0,05, et
- [ ] **Y4 reste sous Y1**. Si Y4 ≥ Y1 hors echantillon, **Y1 est refutee**
      quels que soient ses propres p : le miroir aura prouve que l'effet
      n'est pas directionnel.

**Interdits, declares maintenant :**
- Ne pas juger X6 comme tete de remplacement si X1 echoue. Empiler apres
  coup, c'est choisir la regle qui a gagne.
- Ne pas deplacer `DEBUT_REGIME`, ne pas elargir la fenetre, ne pas changer
  `--tolerance`.
- Ne pas retoucher `regles_gelees_v9.py`. Son empreinte est verifiee.

**Exploratoire, sans valeur de preuve** (a rapporter separement, jamais
comme critere de succes) :
- ecart de X1 selon le regime, en coupant sur l'amplitude causale a 1,02
  (le seuil des jumeaux, voir `NOTES_amplitude.md`) ;
- recoupement des tickets ecartes par X1 avec le trou du matin
  (voir `NOTES_sorties.md`) : les 515 tickets a −16,46 EUR et les sorties
  d'avant 14h a −14 057 EUR sont-ils les memes trades ?

---

## Rappel de causalite, a relire avant de croire quoi que ce soit

Tout ce que lit ce gel doit etre **fige a l'entree** : biais des rails,
position du RSI, verdict churn. `rails_join` garantit `ts <= entry_ts` cote
rails. Si une seule de ces valeurs etait recalculee apres la sortie, tout
le gel serait du recul deguise et les deux familles tomberaient ensemble.
