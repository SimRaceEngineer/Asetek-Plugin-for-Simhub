# PROTOCOLE.md — l'état du dispositif, pour ne pas le redécouvrir

**À lire AVANT toute analyse, en même temps que `mistakes.md`.**

`mistakes.md` dit ce qu'il ne faut pas refaire. Ce fichier dit **ce qui
existe déjà**. Le 17/08, faute de ce document, une matinée entière est
partie à réécrire un lecteur `.scid` et à réclamer un export
d'orderflow — alors qu'un pipeline complet tournait, joignait
l'orderflow aux tickets réels depuis le 29 avril, et produisait déjà
un contrefactuel en euros. Ce fichier existe pour que ça n'arrive plus.

**Tenu à jour à chaque ajout de source, d'outil ou de convention.**

---

## 1. Les sources, avec ce qu'elles valent RÉELLEMENT

Chaque ligne porte une mesure, pas une intention.

### `docs\buddha\<jour>\cycles.jsonl[.gz]`

Instantané complet du moteur par cycle. 352 000 caractères/ligne,
~1,8 Go/jour. **18 journées**, dont 17 en `.gz`.

- transcrit par **`extraire_cycles.py`** → `cartes\cycles\cycles_<jour>.csv`
  (70 colonnes, 36 959 cycles, 4,8 Go lus en 662 s)
- **INUTILISABLE POUR TOUTE FENÊTRE GLISSANTE.** L'audit du 17/08
  donne une **part utile médiane de 48 %**, un pas médian allant de
  **6 s à 3 181 s selon la journée**, et des trous de plusieurs heures.
  Les seules journées régulières (95-100 %) sont celles de **marché
  fermé** : le flux se troue quand la stack travaille.
- ce qu'il est seul à porter : les **états du moteur** — `bb_etat`,
  `fr_canal`, `fr_fb`, `fr_ev`, `piege_side`, `ib_etat`, `biais`, et à
  la racine `alignment` / `leader` / `weakest`.

### `docs\buddha\<jour>\snapshots.csv`

**90 fichiers, 1,9 Go, 21 journées, cadence ~190 s (trois minutes).**
Des milliers de colonnes, des lignes de plusieurs centaines de milliers
de caractères.

Porte ce que `cycles` n'a pas :

```
volume_profile.poc / vah / val / bid_position
market_laws.<actif>.M1 / M3 / M5 / M15.va_poc
vp_daily.* / vp_rolling.*  (poc, pov_vol, total_vol, price_vs_poc)
futures_heatmap.poc / max_vol / total_vol
cvd_strength.M1 / M3 / M5 / score
tick_micro.absorption / reversal_prob / burst_* / bid_velocity_*
volcan_m3.v1 / v2 / day_max  (body, volume, direction, heure)
pulse.delta_5min / delta_30min
positions.n / n_buy / n_sell / open_pnl / day_pnl
```

- transcrit par **`extraire_snapshots.py`** (sélection par motif de nom,
  module `csv` obligatoire — un split sur la virgule décale les
  colonnes sur les champs contenant du texte)
- **le POC est déjà calculé par la stack.** On le lit, on ne le
  reconstruit pas.

### `docs\churn_trades\churn_trades.jsonl` (+ archive)

**36 Mo. C'est la seule source en euros.** Clés :

```
asset  dir  entry_ts  entry_price  close_ts  close_reason
pnl_eur  mae_eur  mae_pts  mfe_eur  mfe_pts  volume  ticket  magic  pid
churn_entry  entry_captured_live
```

Toute mesure qui ne finit pas ici finit en points d'indice, c'est-à-dire
en rien.

### `C:\SierraChart\Data\*.scid` — orderflow réel

Binaire : en-tête 56 octets, enregistrements de 40 octets.

```
horodatage   ENTIER 64 BITS, microsecondes depuis 1899-12-30, en UTC
Open High Low Close   4 flottants
NumTrades TotalVolume BidVolume AskVolume   4 entiers
```

- **`BidVolume` / `AskVolume` séparés** — ce que MT5 ne peut pas donner
  (sur CFD d'indices MT5 fournit un volume de *ticks*, son delta est
  une inférence).
- lu par **`lire_scid_v3.py`**. Les versions v1/v2 lisaient
  l'horodatage comme un flottant : toutes les dates sortaient à
  `1899-12-30`. v3 **détecte** l'encodage.
- **`YMU26-CBOT.scid`** : 57 Mo, 1,42 M enregistrements, **depuis le
  2 février 2026**. `MESU26-CME.scid` : 1,1 Go.
- **`MNQU26-CME.scid` fait 1 Ko : PAS DE NASDAQ.** Toute hypothèse de
  rotation tech/value est invalidable en orderflow réel.
- la forme des OHLC dépend du symbole : MES met `Open=0`, `High=ask`,
  `Low=bid` ; YM met les quatre égaux au prix échangé. **Ce qui tranche
  la nature tick, c'est `bid + ask == total`**, pas la forme des OHLC.
- réglages SierraChart : `Intraday Data Storage Time Unit = 1 Tick`,
  `Maximum Historical Intraday Days = 186`.


### `C:\SierraChart\Data\*.scid` -- ATTENTION AU CYCLE DE VIE DU CONTRAT

Trois fichiers seulement dépassent 1 Mo (état du 17/08) :

| fichier | taille | ce que c'est |
|---|---|---|
| `MESU26-CME.scid` | **1 074 Mo** | Micro E-mini S&P 500 → notre US500 |
| `TICK-NYSE.scid` | **304 Mo** | indice TICK NYSE — largeur de marché |
| `YMU26-CBOT.scid` | 54 Mo | Micro Dow → notre US30 |
| `YMM26-CBOT.scid` | **244 Mo** | Dow juin — téléchargé le 17/08, change tout |

**Le piège : `U26` est l'échéance de SEPTEMBRE.** Avant le roulement
de mi-juin, le contrat actif était `M26` (juin). Un `.scid` couvrant
« février à août » est donc trompeur — le contrat n'est liquide que
sur son trimestre.

Mesuré sur YM : **médiane de 131 barres d'une minute par jour**, pour
une moyenne de 471. Un future qui cote 23 h devrait en avoir ~1 380.
La fenêtre réellement exploitable fait deux mois et demi, pas six.

Conséquence : **étendre le calendrier vers le passé ne sert à rien
sans les échéances antérieures** (`YMM26`, `MESM26`, `YMH26`…), qui ne
sont pas en stock. SierraChart sait les télécharger
(`Chart > Download Historical Data`), mais ça ne se fait pas tout
seul. Le raboutage en contrat continu est la pratique standard.

#### Le périmètre RÉEL du forfait, vérifié le 17/08

Ce qui a des données (`C:\SierraChart\Data\`) :

| symbole | taille | période liquide |
|---|---|---|
| `MESM26-CME` | **2,1 Go** | mi-mars → mi-juin |
| `MESU26-CME` | 1,1 Go | mi-juin → aujourd'hui |
| `YMU26-CBOT` | 55 Mo | mi-juin → aujourd'hui |
| `TICK-NYSE` | 311 Mo | — |

Ce qui est **vide (1 Ko)** — testé, pas supposé :

- **`MNQM26`, `MNQU26`, `NQM26`** → **aucun Nasdaq, sur aucune
  échéance.** La rotation tech/value restera invalidable en orderflow
  réel.
- **`SPM26-CME`** → le E-mini *plein format* est vide aussi. **Le
  forfait ne couvre que les micros.**
- **`MESU25`, `YMU25`** → aucun contrat 2025. L'historique s'arrête
  aux échéances de l'année en cours, et `MESH26` (mars) n'apparaît
  même plus dans la liste des symboles.
- **`$INX`, `$OEX`, `$DOWI`, `SPX500`** → les indices *cash* sont
  classés « Cash Indexes (End of Day) » : pas d'intraday, donc jamais
  de `.scid`.

**Conclusion : cinq mois de S&P micro liquide (mi-mars → août), et
rien d'autre.** C'est le plafond, il ne bougera pas sans changer de
forfait. Inutile d'y revenir.

### `TICK-NYSE.scid` -- la largeur de marché, jamais exploitée

Nombre d'actions en hausse moins en baisse à l'instant T. **Aucune
autre source ne porte ça.** C'est ce qui distingue « le S&P monte
parce que trois valeurs le portent » de « le S&P monte parce que tout
monte » — c'est-à-dire la question de bipolarisation, mesurée au lieu
d'être déduite de l'écart US30/US100.

### Exports MQL5 vers `Common\Files` -- un pipeline live inconnu

`%APPDATA%\MetaQuotes\Terminal\Common\Files\` contient :

- **`futures_<SYMBOLE>_M1.csv`** — une quinzaine de fichiers (~1,3 Ko)
  **réécrits toutes les minutes** : US2000, EURUSD, GBPUSD, USDJPY,
  NGAS, et une douzaine d'actions. Fenêtre glissante, pas d'historique.
- **`hama_kama_crosses.csv`** — 3,7 Mo.
- **`docs\rsi_50_crosses\<jour>\snapshots.csv`** — un arbre de
  snapshots **distinct** de `docs\buddha\`, 0,75 à 2,3 Mo par
  journée, remontant au moins au 08/08.

Aucun des trois n'était connu avant le 17/08. Contenu non inventorié.

### Où le calendrier MT5 n'est PAS

Cinq recherches ont échoué le 17/08 : pas de `*calend*.csv` sous
`AppData\MetaQuotes`, pas de gros CSV correspondant dans
`Common\Files`, rien par contenu (`TimeGMT`, `evenement`). Le fichier
produit par `export_calendrier.mq5` **n'est pas retrouvable sur la
machine** sous un nom identifiable.

Contournement en place : **`calendrier_HIGH.csv` sur le Drive** — les
261 événements HIGH extraits de l'export d'origine, en-tête compris.
C'est ce fichier que `reaction_evenements.py` lit.

### Calendrier économique MT5

- exporté par **`export_calendrier.mq5`** (script MQL5, lecteur seul,
  aucune fonction de trading — le paquet Python `MetaTrader5` n'expose
  pas le calendrier)
- relu par **`lire_calendrier.py`**
- **4 247 événements** juin→octobre, dont **261 `HIGH`**, 168 US
- **77 des 168 US HIGH n'ont pas de surprise calculable** (actual ou
  forecast absent) — près de la moitié
- **le `forecast` MT5 n'est pas fiable partout** : CPI y/y du 12/08,
  MT5 annonce 2,7 quand TradingEconomics donne 3,4 pour un actual de
  3,4. Le prix tranche en faveur de TE. **Confronter à une seconde
  source avant qu'une surprise serve à décider.**

### `news_feed.json`

Flux TradingView live (poll 45 s, ~198 items). **Aucune archive** :
rien du 12/08 n'est récupérable. Ne pas compter dessus pour dater un
événement passé.

### Pipeline orderflow existant — LE PLUS AVANCÉ, ET LE PLUS FACILE À OUBLIER

```
scid_orderflow.py / scid_orderflow_lu.py    lecture .scid
orderflow_join.py / _v3 / _v4 / _v5         jointure orderflow × tickets
orderflow_panel.py / _v2                    panneau
ScalpOrderflowExport.cs                     export NinjaTrader
ROADMAP_ORDERFLOW.md / INSTALL_ORDERFLOW.md
```

Sorties : **`scalp_orderflow_<date>-<heure>.txt` déposées sur le Drive
toutes les quinze minutes**, ~19 Ko.

Ce qu'il produit déjà (état du 17/08 10:25) :

- **153 481 barres orderflow, du 29/04 au 17/08**, assets US30 + US500
- **2 550 tickets rails, 1 635 appariés à une barre Ninja (64,1 %)**
- dix tableaux croisés **en euros** : churn × qualité de flux, setup ×
  événement, heure × ER, régime des trois indices, cohésion,
  confluence rails × HLC par timeframe
- un **contrefactuel** classant les règles d'abstention par Δ =
  PnL/signal après − avant

Les meilleures lignes de ce contrefactuel (pré-enregistrées en **H29**) :

| règle | retirés | Δ /signal |
|---|---|---|
| flux CARNAGE ou MOU (ER < 0,40) | 1 212 / 1 635 (74 %) | **+4,65** |
| heures 09h–11h | 757 / 2 550 (30 %) | **+3,69** |
| ABSORPTION | 47 (3 %) | **−0,07** |

L'absorption, qu'on citait comme prometteuse, est la seule règle du
tableau qui **détruit** de la valeur.

---

## 2. LES HORLOGES — la table à consulter avant tout croisement

Trois sources, trois fuseaux. Deux heures d'écart passent inaperçues
et faussent tout.

| source | fuseau | correction vers l'heure des cycles |
|---|---|---|
| `cycles.csv`, `snapshots.csv`, `churn_trades` | machine VPS = **UTC+2** | référence |
| calendrier MT5 (`CalendarValueHistory`) | serveur broker = **UTC+3** | **− 1 h** |
| SierraChart `.scid` | **UTC** | **+ 2 h** |
| TradingEconomics (sélecteur du site) | UTC+2 | aucune |

**Vérifié, pas déduit** : après correction, **20 CPI américains sur 20**
tombent à 14:30 — l'heure de publication réelle. Tout nouveau
croisement doit refaire ce type de contrôle sur un repère connu.

Attention : `14:30` est aussi l'heure d'ouverture de la fenêtre
d'**initial balance** du moteur. Le bloc de changements d'état à cette
seconde est une **horloge**, pas un événement de marché : il revient
6 jours sur 18.

---

## 3. Le protocole de mesure — non négociable

1. **Une fenêtre se définit en TEMPS, jamais en nombre de lignes.**
   Rejeter toute fenêtre dont la durée réelle dépasse le double de la
   durée voulue : elle enjambe un trou.
2. **Trier par horodatage avant de mesurer.** Les CSV contiennent des
   lignes qui reculent dans le temps.
3. **Témoin apparié obligatoire.** Sans lui on mesure la tendance de la
   période et on l'appelle un effet.
4. **Permutation par JOURNÉE** pour le p. L'unité d'observation est la
   journée : les cycles d'une même journée ne sont pas indépendants.
5. **Pré-enregistrement dans `HYPOTHESES.md`** avec date de rendez-vous
   et critère de réfutation, AVANT de mesurer.
6. **Règle de comptage §0** : n > (z·σ/e)², avec σ ≈ 60 € — une
   estimation, pas une constante.
7. **Un seuil se mesure, il ne s'invente pas.** Pas de « plus de 60 s »,
   pas de « avant 18 h » : un multiple du pas médian de la source, et
   le seuil retenu est affiché.
8. **Le format se lit dans les données** (`--schema`, `--colonnes`,
   en-tête du fichier), jamais dans un souvenir.
9. **Le résultat final est en euros.** Les points d'indice ne décident
   de rien.
10. **Un horizon en jours se compte en SÉANCES**, jamais en jours
    calendaires : +3 jours civils depuis un mercredi tombe le samedi.
    Et une séance est une date portant assez de barres — les futures
    CME rouvrent le dimanche soir et créent des séances fantômes.
11. **Un effectif non monotone est un bug**, pas un hasard : si `3j` a
    moins de points que `1j` et `5j`, on compte mal.
12. **Un balayage trouve toujours un maximum.** Le maximum d'une
    recherche sous H0 vaut déjà 1,5 à 3 : calibrer par permutation sur
    le MAXIMUM, pas sur la cellule choisie.

---

## 4. Les panneaux

Convention documentée dans **`NOTES_panneaux.md`**. En résumé :

- 178 boutons, **177 en `showTab('id')`** (onglets en page), **1 seul en
  `window.open('/route','_blank')`**
- le tableau de bord **se recharge toutes les 5 s** → une page
  interactive doit être une **route**, pas un onglet
- **un panneau = une route + un bouton.** L'un sans l'autre vaut zéro.
- **aucune convention de couleur** n'existe (~60 couleurs distinctes) :
  sur une interface qui existe, on **recopie**, on ne conçoit pas
- routage dans `price_action.py` (`_do_GET_impl`), cascade de
  `if parsed.path == "/x":`, **indentation 12 espaces**, chaque branche
  finit par `return`. Les `<div class="tab">` sont à **4 espaces**.
- redémarrage : **deux étapes** — arrêter par pid, attendre le
  superviseur. Un service supervisé ne se relance pas à la main.

---

## 5. Les interdits — sur cette machine, sans exception

1. Ne jamais `Stop-Process -Name python` : ça tue les traders.
2. Ne jamais lancer `price_action.py` **sans `PA_ROLE=panel`**
   (`_run_trading = _pa_role != "panel"`).
3. Ne jamais approcher `terminal64.exe`. Un script MQL5 est lancé **par
   l'utilisateur**, jamais par moi, et ne contient aucune fonction de
   trading.
4. Ne jamais modifier un `regles_gelees_v*.py`.
5. Ne jamais agir sur un processus hors d'une liste explicite.
6. **Ne jamais « réparer » un flux dont on n'a pas identifié la cause
   de la panne.** Quand une demande porte sur un résultat, chercher le
   chemin qui l'atteint sans toucher au vivant (ex. `collecteur_10s.py`,
   qui interroge le panneau en lecture seule au lieu de modifier le
   logger).

Contraintes de travail : **une commande par prompt**, livraison par
`G:\My Drive\ScalpEA\` (le push GitHub est refusé, 403 — politique du
dépôt), et le Drive **n'autorise pas le remplacement** d'un fichier :
d'où les suffixes `_v2`, `_v3`.

---

## 6. Les outils, et à quoi ils servent

| outil | ce qu'il fait |
|---|---|
| `extraire_cycles.py` | cycles.jsonl(.gz) → CSV/jour, 70 colonnes |
| `extraire_snapshots.py` | snapshots.csv → CSV/jour, volume/POC/CVD |
| `audit_cadence.py` | **à lancer avant toute mesure** : désordre, trous, part utile |
| `lire_scid_v3.py` | `.scid` → barres avec delta et CVD |
| `export_calendrier.mq5` | calendrier MT5 → CSV (heure + importance) |
| `lire_calendrier.py` | calendrier remis à l'heure des cycles, surprise |
| `journal_etats.py` | blocs synchrones, durée de séjour des labels |
| `autopsie_choc.py` | autopsie d'une bougie, signature, recherche arrière |
| `breakout_range.py`, `bruit_par_actif.py`, `cassure_par_actif.py`, `rotation_tech_value.py` | mesures — **toutes à revoir : fenêtres comptées en lignes** |
| `collecteur_10s.py` | flux indépendant à 10 s, lecture seule du panneau |
| `reaction_evenements.py` | calendrier × orderflow : prix ET delta cumulé, six horizons, témoin apparié, mode `--verifie` |
| `patch_seances.py` | correctif du comptage des séances pour l'outil ci-dessus |
| `contrat_continu.py` | raboute deux échéances par le volume mesuré, colonne `contrat` |
| `patch_base.py` | écarte les fenêtres à cheval sur un roulement |
| `patch_doublons.py` | écarte les échéances déjà contenues dans un raccord ; mesure en points les séries qui traversent zéro |
| `patch_permutation.py` | composition des groupes par jour de semaine + p par permutation stratifiée |
| `patch_temoin.py` | borne le témoin à la plage réellement couverte par le calendrier |
| `bougie_deux_actifs.py` | une bougie décrite sur deux carnets, minute par minute, étalon = la séance |

**Durées de séjour mesurées** (17/08) — ce qui décrit un régime et ce
qui n'en décrit pas : `piege_side` 616 s, `bb_etat` 221 s, `fr_canal`
139 s, `fr_fb` 110 s, **`biais` 78 s**, `fr_ev` 73 s, `alignment` 67 s,
**`leader` 54 s**. Un label qui bascule toutes les minute ne peut pas
servir de condition d'entrée sans lissage — et personne n'a décidé
lequel.

---

## 6 bis. La branche macro est CLOSE en l'état (17/08)

`reaction_evenements.py` sort, sur les trois symboles, **`AUCUN
horizon n'est testable`**. Ce n'est pas un manque de puissance, c'est
une impossibilité de construction :

- le seuil de 4 occurrences ne garde que **deux séries hebdomadaires**
  (EIA le mercredi, inscriptions au chômage le jeudi) ; CPI, NFP, Fed,
  ISM, PMI sont tous à 3 occurrences et tombent ;
- ces deux séries tombent **toujours le même jour de la semaine**,
  tandis que les témoins sont pris sur les journées sans publication,
  donc **jamais** un mercredi ni un jeudi à l'intérieur du calendrier ;
- il n'existe donc aucun mercredi ni jeudi témoin à mettre en face.
  Rien à permuter.

**Ce qui débloque, et rien d'autre : étendre le calendrier vers le
passé.** Les barres remontent au 28/12 ; le calendrier commence au
01/06. Les 28 événements écartés sont précisément les poids lourds, et
ils ne tombent pas tous le même jour de semaine — ce qui rouvre la
stratification du même coup.

**Ne pas** baisser `--mini-occurrences` : ça normaliserait des
surprises sur deux points.

Chiffre à retenir : le seul résultat significatif de la journée
(`-1330` contrats à 15 min, p = 0,0015) est tombé à `-267` sans
p-value une fois le témoin borné au calendrier. C'était le changement
d'échéance du 16 juin, pas une réaction macro.

---

## 7. Les rendez-vous en cours

| hypothèse | échéance | sujet |
|---|---|---|
| H22 | 18/08 | — |
| H26 | 20/08 | pas de consensus M15 |
| H23, H25 | 26/08 | — |
| H27a | 27/08 | US100, +12,2 sur 141 |
| H27 | 30/08 | sortie de range par le bas |
| H24 | 01/09 | séance US, gap M1 plat |
| H27b | 22/09 | US500, n ≈ 206 |
| **H28** | fin août | payer SierraChart, ou non |
| **H29** | **15/10** | les deux règles d'abstention, hors échantillon |

**Coupure H29 : tous les tickets clos à partir du 18/08 00:00.** Aucun
changement de paramètre sur ces règles d'ici là — elles sont
**observées**, pas appliquées.

---

## 8. Ce que SierraChart donne, mesuré le 17/08

```
of_MES-continu.csv   183 314 barres   28/12 -> 17/08   mediane 1260 b/j
of_YM-continu.csv    160 257 barres   29/12 -> 17/08   mediane 1250 b/j
of_TICK-NYSE.csv     124 279 barres   27/01 -> 04/08   mediane  961 b/j
```

**Deux actifs au même grain, enfin.** Avant le 17/08, `YMU26` seul
donnait **131 barres par jour** — deux heures d'activité par séance,
inutilisable pour regarder une minute précise. Avec `YMM26`, le Dow est
mesurable comme le S&P, et la divergence US30/US500 devient une mesure
au lieu d'une impression.

Roulements mesurés (par volume dominant, persistance de 3 séances) :
**MES le 16/06**, **YM le 15/06**. Un jour d'écart, cohérent.

`TICK-NYSE` s'arrête au **4 août** : le `.scid` n'a pas été
retéléchargé. Toute fenêtre postérieure l'écartera d'elle-même par
contrôle de couverture — ce n'est pas un bug de nos outils.

### Deux pièges de chaîne, tous deux trouvés le 17/08

1. **Un raccord relu comme une échéance.** `of_MES-continu.csv`
   commence par `MES` : un `--racine MES` naïf le recharge, il domine
   le volume tous les jours puisqu'il contient tout, et le nouveau
   raccord n'est qu'une copie de l'ancien. *La version du VPS ne fait
   pas cette faute* — vérifié : elle trouve bien 2 échéances avec le
   continu présent dans le dossier.

2. **Les mêmes barres comptées trois fois.** Le continu et ses deux
   échéances cohabitent dans `cartes\scid\`. La règle : un fichier qui
   porte une colonne `contrat` déclare lui-même les échéances qu'il
   absorbe. On lit ce que les données déclarent, jamais un motif de nom
   de fichier.

### La règle qui manquait, et qui vaut au-delà de l'orderflow

**Absence de donnée n'est pas donnée d'absence.** Une journée hors de
la plage couverte par une source n'est pas une journée « sans
événement » : c'est une journée dont on ne sait rien. Tout groupe
témoin doit être borné à la plage réellement couverte, et cette plage
se lit dans le fichier.
