# Les sorties — ce que le dispositif atteint, puis rend

Etat au 11/08/2026, apres `sorties2.py` sur 2 720 tickets, 21/07 → 11/08.
Corpus `churn_trades*.jsonl`, couverture ~99,5 % du P&L MT5 sur la periode.

Bascule au 05/08 : 1 377 tickets en TENDANCE (+12 163,85), 1 343 en RANGE
(−11 918,32).

---

## Le trou est le matin, et il ne depend pas du regime

Sorties **avant 14h** :

| | tickets | resultat |
|---|---|---|
| TENDANCE | 467 | **−6 776 €** (pendant que la periode gagnait +12 164) |
| RANGE | 683 | **−7 281 €** |

Sur les 11 seances : les sorties d'avant 14h coutent **14 057 €**, tout le
reste rapporte **14 303 €**.

Rendu en part du MFE, par heure de sortie :

| sortie | tendance | range |
|---|---|---|
| 10h | 135 % | 137 % |
| 11h | 109 % | **173 %** |
| 12h | 124 % | **163 %** |
| 15h | 86 % | 131 % |
| 16h | **57 %** | 88 % |
| 18h | 78 % | 71 % |

Le decoupage par heure d'ENTREE dit la meme chose (−12 777 € avant 14h) :
deux decoupages independants, meme conclusion, donc pas un artefact.

**15:27 est disculpe comme cause principale.** 15h sort a 86 % en tendance
et 131 % en range — il se degrade, mais 11h et 12h font pire dans les deux
regimes. Le patch « BE ou mieux » du 11/08 reste juste ; il ne visait
simplement pas le probleme principal.

---

## Le mecanisme : le motif 3 s'effondre deux fois

| motif | tendance | range |
|---|---|---|
| **3** (70 % des tickets) | MFE 51,1 · rendu **103 %** | MFE 32,6 · rendu **163 %** |
| **4** (30 %) | MFE 88,8 · rendu 53 % | MFE 80,0 · rendu 58 % |

Le motif 4 tient dans les deux regimes (MFE −10 %, rendu 53→58 %). La
machinerie des gagnants fonctionne.

Le motif 3 monte 36 % moins haut ET rend 163 % au lieu de 103 %. Un ticket
motif-3 du range monte a +32,6, rend 53 €, finit a **−20**. Sur 975 tickets.

Decomposition de l'esperance :

```
tendance : 0,327 × 39,79 + 0,673 × (−6,19)                  = +8,84
range    : 0,263 × 29,64 + 0,726 × (−23,60) + 0,011 × 42,18 = −8,87
```

Les gagnants sont 20 % moins frequents et 25 % plus petits — gerable. Le
cout de chaque perdant a monte de **281 %** — pas gerable. En ne corrigeant
que ce dernier terme : **+5 073 € au lieu de −11 918 €**.

**La table des `close_reason` reste a trouver** dans `churn_trade_logger.py`.
Sans elle on ne sait pas QUEL mecanisme produit le motif 3.

---

## Le verdict churn : le meilleur signal causal du dossier

Monotone dans les **deux** regimes, et fige a l'entree.

| verdict | tendance | range | rendu (range) |
|---|---|---|---|
| **CLEAN** (96/100) | +16,36 · WR 57 % | **+3,26 · WR 52 %** | **87 %** |
| MIXED (463/460) | +12,69 · WR 58 % | −7,12 · WR 41 % | 103 % |
| OK (287/251) | +6,81 · WR 41 % | −10,40 · WR 39 % | 112 % |
| CHURN (531/532) | +5,21 · WR 50 % | −11,96 · WR 37 % | 122 % |

CLEAN est le seul verdict positif dans le range et le seul dont le rendu
passe sous 100 %.

**OK n'est pas CLEAN — c'est demontre, pas suppose.** +3,26 contre −10,40
dans le range. `patch_oos_churn2.py` les garde distincts par principe ;
les donnees le confirment, et les fusionner aurait detruit le seul bon
compartiment.

**Consequence pour le gel V9** : Y1 selectionne `churn MIXED` et Y2 le prend
pour temoin. MIXED est le milieu du gradient, a −7,12 dans le range. Le bon
compartiment est CLEAN. Le fichier gele ne bouge pas — c'est la regle — mais
il faudra lire le verdict du 01/09 en sachant qu'il teste un compartiment
mediocre, pas le meilleur.

---

## Les jumeaux sont du levier, pas de la diversification

| | tickets apparies | resultat | non apparies |
|---|---|---|---|
| tendance | 1 100 (80 %) | **+11 500** (+10,45/tk) | +663 (+2,40) |
| range | 1 008 (75 %) | **−10 397** (−10,31/tk) | −1 521 (−4,54) |

+10,45 puis −10,31 : symetrique au dixieme pres. M206 et M207 ouvrent la
meme minute, le meme actif, le meme sens, avec le meme MFE au centime.
Amplification identique dans les deux sens = definition du levier.

Couper un des deux ne changerait pas la forme du resultat, seulement son
amplitude : +5 750 / −5 199. C'est un choix de taille de position, pas de
strategie.

---

## Candidat gel V10 : le trou du matin

Il coche ce qui manquait a l'hypothese d'amplitude (voir `NOTES_amplitude.md`) :

- [x] 11 seances, 1 150 tickets — pas 5 seances et 56 tickets
- [x] **meme signe dans deux regimes opposes** : ce n'est pas un effet de periode
- [x] causal par construction : l'heure est connue a l'entree, aucun seuil a calibrer
- [x] coherent sur deux decoupages independants (heure d'entree, heure de sortie)
- [x] insensible au confondant de flotte : M186/M178 ne tradent plus

Reste a faire avant de geler :

- [ ] un **temoin** (une heure voisine sans effet attendu) et un **controle negatif**
- [ ] verifier que l'effet n'est pas porte par une seule seance
- [ ] decider l'unite : la seance, pas le ticket
- [ ] ne pas le poser avant que V9 ait rendu son verdict le 01/09

---

## Reserves valables partout ci-dessus

Le MFE vaut ce que vaut son echantillonnage par `churn_trade_logger.py` :
un pic entre deux mesures n'y figure pas, donc **le rendu reel est plutot
sous-estime**.

Une part rendue superieure a 100 % n'est pas une erreur : les positions ne
se contentent pas de rendre leur gain, elles finissent sous zero apres avoir
culmine.

Le rendu n'est pas une perte — personne ne sort au plus haut. Seule la
COMPARAISON entre heures, motifs et regimes se lit.
