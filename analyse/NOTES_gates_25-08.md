# Les 53 gates d entree -- inventaire et premiere mesure (25/08/2026)

Releve sur `C:\SVPS\Scalp-EA-main` (msitrident2). 53 fichiers `*_gate.py`,
environ 900 Ko de code dont le seul role est de REFUSER des entrees.

Le commentaire d `ai_master_agent.py` ligne 4534 parle de « 20+ gates
order_send ». Il en sous-estime le nombre de plus du double -- ce qui dit
deja qu aucune liste a jour n existait.

## Ce que chaque gate declare faire

Ligne de description telle qu ecrite dans son en-tete.

### Portee stack-wide (s appliquent a tout le monde)

| module | ce qu il dit faire |
|---|---|
| `dow_cap_gate.py` (60 Ko) | Stack-wide gate: SPX M3 Dow Law arbiter. Sauf `dow_cap_trader` (M98xxx) et autres autonomes |
| `buddha_clause_gate.py` (29 Ko) | Stack-wide Buddha hard clauses via `mt5.order_send` |
| `directional_anti_trade_gate.py` (18 Ko) | Stack-wide directional anti-trade gate |
| `anti_straddle_gate.py` | Anti-straddle STACK-WIDE (user 2026-06-24 : « etends a tout ») |
| `bounce_gate.py` | Stack-wide gate based on V-shape reversal detection |
| `fractal_regime_gate.py` (39 Ko) | Gate d entree stack-wide par regime fractal (chop) |
| `laggard_wall_gate.py` | Halte stack-wide quand le plus faible touche son mur |
| `rails_cycle_gate.py` | Gate directionnel stack-wide sur le sens M180 (par TF) |
| `vix_delta_gate.py` | Stack-wide : pas de mouvement si la vol ne bouge pas |

### Universels

| module | ce qu il dit faire |
|---|---|
| `universal_polarity_gate.py` (35 Ko) | -- |
| `bb_fair_value_zone_gate.py` (26 Ko) | BB Fair Value Zone universal entry filter v1.0 |
| `proximity_gate.py` | Gate UNIVERSEL de proximite structure weak/strong deja touchee (2026-07-07) |
| `session_plan_gate.py` | Universal entry gate enforcing session_plan zones |
| `vrp_gate.py` | Universal entry gate based on VIX trend + cross-asset |

### Directionnels -- ils bloquent un SENS, pas les deux

| module | ce qu il dit faire |
|---|---|
| `analyze_186_rail_gate.py` | Valeur du rail 186 comme gate directionnel de la stack |
| `dualcross_gate.py` | DualCross Direction Oracle (`DOC` dans les journaux) |
| `eqv3_ma2050_gate.py` | Directional gate on EQV3 MA20 vs MA50 cross |
| `leader_push_gate.py` | Gate ENFORCE directionnel sur les magics TREND |
| `ibre_direction_gate.py` (41 Ko) | -- |
| `polarity_gate.py` (34 Ko) | Per-asset polarity filter via TOP/BTM cross v2.0 |
| `zone_edge_gate.py` | VETO d entree CONTRE un bord DEFENDU de la zone du jour (2026-07-15) |
| `m188_zone_gate.py` | ANTI-FADE M188 : bloque les entrees weak-momentum qui FIGHTENT la zone defendue |

### Fenetres horaires

| module | ce qu il dit faire |
|---|---|
| `am_window_gate.py` | Gate chirurgical fenetre matin (< 10:00 Paris) |
| `session_va_gate.py` | Gate LEADER (US100) + PULLBACK suiveurs (US30/US500), post-10h |
| `atr_baseline_gate.py` | ATR de 10h = BASELINE du jour ; ne trader QUE si l ATR monte au-dessus |

### Plafonds et refroidissements

| module | ce qu il dit faire |
|---|---|
| `pyramid_cap_gate.py` | Anti-surenchere (concentration cap) |
| `cooldown_gate.py` | -- |
| `re_entry_cooldown_gate.py` | -- |
| `hard_close_gate.py` | -- |
| `deeps_only_close_gate.py` | -- |

### Regime et structure

| module | ce qu il dit faire |
|---|---|
| `regime_gate.py` | Market Regime Entry Gate (v1.1) |
| `regime_hold_gate.py` | 2026-06-26 (option A de l arc sorties/FOMO) |
| `strong_trend_gate.py` (25 Ko) | Strong-trend-only entry gate |
| `open_type_gate.py` | Gate regime open-type Dalton (ENFORCE) |
| `bb_expansion_gate.py` | Gate based on BB(20,2) width expansion |
| `zband_pullback_gate.py` | -- |
| `spx_conviction_gate.py` (25 Ko) | SPX500 V1 Body + CVD M1 Conviction Gate |
| `cross_index_gate.py` (38 Ko) | -- |
| `m154_leader_gate.py` (36 Ko) | M154 = LEADER FULL du convoi par asset (2026-06-09) |
| `rails_continuation_gate.py` | Machine a etats M15 x M1 sur le cycle rails-RSI |
| `rsi_m10_gate.py` (26 Ko) | -- |
| `rsi_div_gate.py` | -- |
| `rsi_rails_exit_gate.py` | -- |
| `hlc_m15_gate.py` | -- |
| `janira_m5_gate.py` | **« 2026-06-19 » -- aucune description** |
| `antifomo_gate.py` (15 Ko) | -- |
| `anticipation_override_gate.py` (24 Ko) | Pattern-anticipation supreme override v1.0 |
| `eqv3_gate.py` | -- |

### Ce qui n est PAS un gate d entree, malgre le nom

| module | pourquoi |
|---|---|
| `am_dow_gate.py` | **DEPRECATED 2026-04-30**, simple wrapper vers `strong_trend_gate` |
| `pattern_aligned_gate.py` | **Observe-only** -- il mesure, il ne bloque pas |
| `retro_gate.py` | Retro-test du `fractal_regime_gate` sur une journee passee |
| `anti_fomo_gate.py` | 5 Ko, « etape A de l arc sorties/FOMO » -- **doublon apparent** d `antifomo_gate.py` (15 Ko) |

## Trois defauts de structure, visibles sans lire le code

**Des doublons.** `antifomo_gate.py` / `anti_fomo_gate.py`, `polarity_gate.py` /
`universal_polarity_gate.py`, `eqv3_gate.py` / `eqv3_ma2050_gate.py`. Lequel
tourne ? Lequel est mort ? Le nom ne le dit pas.

**Un deprecated toujours present.** `am_dow_gate.py` porte
« DEPRECATED 2026-04-30 » depuis quatre mois et reste dans le dossier.

**Un non documente.** `janira_m5_gate.py` n a pour toute description
qu une date. Personne ne peut dire ce qu il bloque sans le lire.

## Premiere mesure -- journal du 24/08

Comptage des etiquettes entre crochets sur les lignes contenant BLOCK.

| occurrences | etiquette | remarque |
|---:|---|---|
| 22 050 | `MFE_TRAIL` | **PAS un gate** : les `MODIFY FAILED rc=10027`, AutoTrading desactive |
| 2 715 | `BBFV` | `bb_fair_value_zone_gate` |
| 1 516 | `DOC` | `dualcross_gate` -- DualCross Direction Oracle |
| 1 375 | `HARD_CAP_1850` | plafond dur d entrees |
| 362 | `Z_LOC_BLOCK` | |
| 302 | `LAGGARD_WALL` | `laggard_wall_gate` |
| 279 | `M154` | `m154_leader_gate` |
| 248 | `POC` | |
| 199 | `JANIRA_SR` | |
| 175 | `BLOCKED` | etiquette generique, source a identifier |
| 134 | `APPUI` | |
| 86 | `RSI_M10_GATE` | |
| 47 | `CONVICTION` | `spx_conviction_gate` |
| 46 | `REJECT` | |
| 6 | `bounce_entry_detector` | |
| 1 | `LEADPUSH`, `VIXGATE`, `AMGATE`, `EVENT_WEEK_BLOCK`, `RCGATE`, `ANTIC` | |

`US30` (193), `US500` (129) et `US100` (28) sont des etiquettes d actif,
pas des gates.

**Comptage corrige le 25/08.** Le premier motif exigeait des majuscules
sans espace et laissait de cote toute etiquette en contenant un. Refait
avec `\[([^\]]+)\]`, il donne un classement completement different :

| Blocages | Etiquette |
|---:|---|
| **30 934** | `DOW_CAP_GATE BLOCK` |
| 7 919 | `C14 BLOCK` |
| 4 400 | `M17-OBS` |
| 4 380 | `fbt_protect FAIL` |
| 2 715 | `BBFV` |
| 1 558 | `DOC` |
| 1 375 | `HARD_CAP_1850` |
| 362 | `Z_LOC_BLOCK` |
| 350 | `IZONE BLOCK` |
| 302 | `LAGGARD_WALL` |
| 279 | `M154` |
| 248 | `POC` |
| 201 | `JANIRA_SR` |
| 175 | `BLOCKED` |
| 134 | `APPUI` |
| 86 | `RSI_M10_GATE` |
| 54 | `EQV3_2050 OBSERVE` |
| 47 | `CONVICTION` |
| 46 | `REJECT` |
| 20 | `ANTIC BLOCK` |
| 6 | `bounce_entry_detector` |
| 1 | `LEADPUSH`, `VIXGATE`, `AMGATE`, `EVENT_WEEK_BLOCK`, `FRG`, `ANTIC`, `RCGATE`, `OK` |

`DOW_CAP_GATE` fait a lui seul **68 % de tous les blocages de la
journee** -- quatre fois le deuxieme. Les trois etiquettes que j avais
mises en tete (`BBFV`, `DOC`, `HARD_CAP_1850`) ne pesent ensemble que
11 %. Ma conclusion precedente etait fausse par construction : elle
portait sur le residu.

## dow_cap_gate.py -- ce qu il refuse exactement

1361 lignes, 60 Ko, `OBSERVE_ONLY = False` depuis le 12/05 (ligne 49 :
*"user spec LIVE from day 1"*). Il ne calcule aucun signal : il
monkey-patche `mt5.order_send` et intercepte **tous** les envois
d ordre de la stack.

La decision est prise par `allows_entry(asset, direction, magic)`,
ligne 1059. Deux regimes selon l heure de Paris (`_is_us_session_active`,
ligne 851 : 15:30 <= h < 22:00).

**Avant 15:30 -- SPX arbitre strict.**

| Actif | Condition | Verdict |
|---|---|---|
| US500, US100 | SPX a une ligne Dow M3 BEAR ou BULL active | **bloque dans les deux sens** |
| US500, US100 | cassure SPX < 15 min, sens DOWN | BUY bloque |
| US500, US100 | cassure SPX < 15 min, sens UP | SELL bloque |
| US30 | sa propre ligne M3 est opposee a celle de SPX | **bloque** |
| US30 | accord ou pas de ligne | passe |

C est la ligne 1109 -- `PRE_US:SPX_M3_CAP_{type}_ACTIVE@{level}_block_all`
-- qui interdit les deux sens a la fois. Un seul trace sur SPX suffit a
fermer US500 et US100 jusqu a l ouverture cash.

**Apres 15:30 -- chaque indice sur sa propre ligne.**

`_asset_dow_verdict` (ligne 972) rend un verdict parmi cinq, et
`_verdict_allows` (ligne 1126) n en autorise qu un seul sens :

| Verdict | Sens autorise |
|---|---|
| `CAP_BROKEN_UP` (ligne BEAR, prix au-dessus) | BUY seulement |
| `FLOOR_HOLDING` (ligne BULL, prix au-dessus) | BUY seulement |
| `CAP_HOLDING` (ligne BEAR, prix en dessous) | SELL seulement |
| `FLOOR_BROKEN_DN` (ligne BULL, prix en dessous) | SELL seulement |
| `NO_LINE` | aucune contrainte |

Une ligne n existe que si elle a au moins `PIVOTS_MIN = 3` pivots et une
pente au-dela de `+/- 0.05 pts/bar` (lignes 105-107). En dessous, le
verdict retombe sur `NO_LINE` et le gate laisse passer.

**Donc, en seance, ce gate est un filtre directionnel permanent :** des
qu une ligne Dow M3 tient sur un indice, un des deux sens est ferme sur
cet indice pour toute la stack.

## Les trois sorties de secours qui existent deja

Elles sont dans le code, testees avant tout calcul :

1. **`ai_master_exempt`** (ligne 1170) -- M154 et M50002 passent sans
   examen.
2. **Commentaire `ETP`** (ligne 1180) -- les fermetures de
   `exit_tp_manager` passent : *"capital protection > Dow Cap
   conviction"*.
3. **`polarity_gate`** (ligne 1204) -- si la polarite de l actif est
   `BULL` et l ordre un BUY (ou `BEAR` et SELL), l ordre passe sans
   consulter Dow.
4. **`EXEMPT_MAGICS_BASE`** (ligne 54) -- une liste blanche de ~90
   magics dits *autonomous structural setups*.

**Les bras 206 et 207 ne sont dans aucune des quatre.** La liste blanche
contient les familles 63/73/83, 92 a 120, 130 a 134, 53215, 53711 --
pas un seul 206xxx ni 207xxx. Les setups dont vous voulez voir le
travail en live sont donc soumis, ordre par ordre, a un filtre que les
papers n ont jamais eu.

**Defaut au passage :** le commentaire ligne 53 annonce *"resolve at
install time + refresh dynamically each call"* depuis
`daily_watchdog.AUTONOMOUS_MAGICS`. Ce rafraichissement n existe pas
dans le code : `allows_entry` ne consulte que `EXEMPT_MAGICS_BASE`, en
dur. Toute famille ajoutee au watchdog depuis mai est bloquee sans que
personne l ait decide.

## A faire

- Compter les blocages `DOW_CAP_GATE` par magic, pour chiffrer ce que le
  gate a coute aux bras 206/207 le 24/08. **Commande envoyee, en
  attente.**
- Identifier ce qui emet `Z_LOC_BLOCK`, `POC`, `APPUI`, `JANIRA_SR`,
  `BLOCKED`, `REJECT` -- ces etiquettes ne correspondent a aucun nom de
  fichier evident.
- Lire `c14_gate` (7 919), `M17-OBS` (4 400) et `fbt_protect` (4 380),
  les trois suivants.
- Trancher les trois doublons.
- Retirer `am_dow_gate.py`, deprecated depuis le 30/04.
- Documenter ou supprimer `janira_m5_gate.py`.
