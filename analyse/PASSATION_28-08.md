# PASSATION — reprise en session locale, 28/08/2026

Ce document est écrit par la session **cloud** du 27/08 pour la session
**locale** qui reprend. La session cloud n'avait accès à aucune machine :
elle écrivait du code, le déposait sur le Drive, l'utilisateur le copiait
et le lançait, puis collait la sortie. Vous, vous avez les fichiers.
Cela change la vitesse, pas la méthode.

**Lisez `analyse/mistakes.md` en entier avant d'écrire une ligne.** 2 257
lignes, et chaque entrée est une erreur payée. Les cinq dernières datent
d'hier après-midi.

---

## 1. Les trois sources à lire

| source | quoi | comment |
|---|---|---|
| `C:\SVPS\Scalp-EA-main` | la stack qui tourne, ~200 modules | accès local direct |
| `G:\Mon Drive\ScalpEA` | dépôts de la session cloud (patchs, outils) | accès local direct |
| GitHub `SimRaceEngineer/Asetek-Plugin-for-Simhub` | branche `claude/trading-stack-vps-migration-28okwh`, dossier `analyse/` | historique complet et messages de commit détaillés |

**Le dépôt GitHub est en retard sur la machine pour plusieurs fichiers.**
Vérifié hier : `cartes_live.py` fait 26 265 o dans le dépôt et 42 273 o
sur la machine ; `pont_miroirs.py` 26 265 o contre 38 695 o. La machine
fait foi. Ne patchez jamais en vous fiant à la copie du dépôt.

Les messages de commit de la branche portent le raisonnement complet de
chaque correctif — souvent plus que le code lui-même.

---

## 2. Les machines et les comptes

- **msitrident2**, `C:\SVPS\Scalp-EA-main`
- **compte moteur 17\*\*80** — ThinkMarkets-Demo
  terminal `C:\Program Files\TF Global Markets MetaTrader 5 Termina-LOCALSTACKl\terminal64.exe`
  (oui, le nom du dossier est bien celui-là, ce n'est pas une coquille)
- **compte miroir 18\*\*09** — ThinkMarkets-Demo, EUR
  terminal `C:\Program Files\TF Global Markets MetaTrader 5 Terminal\terminal64.exe`
- Un processus Python ne peut être connecté qu'à **un** terminal MT5.
  C'est pour ça que le pont a deux rôles : `--lecteur` sur le moteur,
  `--envoyeur` sur le dédié.

**Règle de discrétion en vigueur.** Les numéros de compte s'écrivent
masqués (`17**80`, `18**09`). Toute valeur ressemblant à une clé (KEY,
TOKEN, SECRET, PASSWORD, Authorization, Bearer, `sk-…`) s'affiche masquée
avec sa seule longueur. `START_TRADING_STACK_V3.bat` contient un mot de
passe d'application Gmail : **il doit être révoqué**, c'est une tâche en
attente. Les patchs qui touchent ce .bat le lisent et l'écrivent en
**latin-1**, octet pour octet.

---

## 3. Les six interdits sur le VPS

Non négociables. Ils viennent tous d'un incident réel.

1. Jamais `Stop-Process -Name python` — cela tuerait les traders avec le reste.
2. Jamais lancer `price_action.py` sans `PA_ROLE=panel`.
3. Ne jamais approcher `terminal64.exe`.
4. Ne jamais modifier un `regles_gelees_v*.py`.
5. N'agir que sur des processus d'une liste explicite, reconnus par leur ligne de commande.
6. Ne jamais « réparer » un flux dont la cause de panne n'a pas été identifiée.

---

## 4. L'architecture des miroirs

Le moteur trade sur 17\*\*80. Un **miroir** rejoue les mêmes entrées sous
d'autres magics pour isoler **une seule variable** à la fois. Le **pont**
copie ensuite ces positions sur 18\*\*09, où elles sont mesurées.

| branche | magic | ce qu'elle isole |
|---|---|---|
| 1 | le magic du paper, `220000-249999` | **exempte des modules de sortie** du moteur — la référence |
| 2 | préfixe `4` → `4220000-4249999` | **soumise aux modules de sortie** ; l'écart 2−1 ne mesure que la gestion de sortie |
| 5 | préfixe `5` → `5220000-5249999` | même sortie que la 1, mais l'entrée doit passer le **filtre CVD** ; l'écart 5−1 ne mesure que le filtre |
| 6 | préfixe `6` → `6220000-6249999` | même entrée que la 1, **sur les seuls accords M15** (`ACCORDS_M15 = (240003, 240004)`), sortie en **trailing 0.50R** |

Dans `miroir_papers.py` : `magic_double` → `int("4%d")`, `magic_cvd` →
`int("5%d")`, `magic_trail` → `int("6%d")`. **Les quatre branches sont en
cascade** : si la branche 1 échoue, 2, 5 et 6 sont sautées entièrement.

`pont_miroirs.PLAGES` doit contenir les quatre plages, sinon une branche
ouvre sur le moteur sans jamais être copiée — elle existerait sans être
lisible.

---

## 5. Les processus, et lesquels comptent

22 processus Python tournaient hier. Ceux qui écrivent des **ordres** ou
des **stops** :

```
trading_engine.py --stop-hour 20      le moteur. sl_cliquet y est arme.
trade_monitor.py --stop-hour 23
miroir_papers.py --armer              ouvre les branches 1/2/5/6
pont_miroirs.py --lecteur             lit 17**80
pont_miroirs.py --envoyeur --compte 182109 --reel   ecrit sur 18**09
trail_miroir6.py --reel               avance le stop de la branche 6
gardien_stops.py --reel               filet : un stop ne recule jamais
```

Les modules de sortie du moteur, tous importés par `trading_engine.py` :
`daily_watchdog`, `sl_freeze_176`, `us30_trail`, `structural_sl_enforcer`,
`mfe_ticket_trail`, `fbt_asset_protect`, `exit_tp_manager`, `exit_manager`.

### Les lanceurs

- `START_TRADING_STACK_V3.bat` — le moteur et le socle. Porte trois mois
  de correctifs, **on ne le rejoue pas de tête**.
- `Superviseur.ps1` — remplace les cinq fenêtres wrapper du V3. Ne touche
  ni au moteur ni aux terminaux.
- `Lancer-Miroirs.ps1` — **écrit le 27/08**, les cinq services des
  miroirs. `-Go` démarre ce qui manque, `-Tout` reprend tout, sans
  argument il ne fait qu'un état. Il ne déclare **OK** que si le journal
  du service a **grossi** après le démarrage ; un processus vivant mais
  muet est marqué **MUET**, et il ne relance jamais en boucle.
- `Redemarrer-Stack.ps1` — inventaire par défaut, `-Go` pour agir.
- `PONT_MIROIRS.cmd` — les deux rôles du pont ensemble.
- `boucle_cartes_live.py` — régénère le panneau toutes les 60 s ; il
  **relit `cartes_live.py` à chaque tour**, donc un patch du panneau
  prend effet sans redémarrage.

---

## 6. Ce qui a été trouvé et corrigé le 27/08

### 6.1 — Le miroir muet pendant 1 h 27

`sl_cliquet` avait été installé **en enveloppe sur `mt5.order_send`**
dans `miroir_papers.py`. Chaque ouverture échouait, `order_send` rendait
`None`, et le message d'erreur jetait la cause :

```python
res.comment if res else "sans reponse"
```

Le vrai motif était `(-2, 'Unnamed arguments not allowed')`. Il n'a paru
qu'après correction du message. Séance de 5 h par jour, 1 h 27 perdue.

> **Une enveloppe sur `order_send` s'interpose sur les OUVERTURES alors
> qu'elle n'a affaire qu'aux stops. C'est une mauvaise place.** Dans
> `trading_engine.py` elle tourne sans incident depuis le 10/08 ;
> ailleurs elle casse tout. Ne la reposez pas sur le miroir ni sur le pont.

`preflight_miroir.py` (écrit hier) refuse le départ si elle réapparaît.

### 6.2 — La guerre des stops, cause nommée

Journaux du terminal MT5 (**UTF-16LE**), compte 17\*\*80 :

| jour | acceptées | refusées `[Invalid stops]` | reculs | part |
|---|---|---|---|---|
| 25/08 | 26 271 | 5 455 | 12 847 | **49 %** |
| 26/08 | 29 590 | 399 | 14 327 | **48 %** |
| 27/08 (→16:11) | 2 019 | **2 173** | 477 | 24 % |

Format : `modify #TICKET buy 0.18 NAS100 sl: OLD, tp: 0.00 -> sl: NEW, tp: 0.00`
et `failed modify … [Invalid stops]`. **Compter les deux comme des
modifications est une erreur que j'ai commise pendant trois jours.**

**La cause est une collision de conception**, pas un bug :

- `miroir_papers.py:763-770` recopie sur la position miroir le stop de sa
  **position paper parente** — le bouchon d'ouverture, que le paper ne
  déplace jamais puisqu'il sort à la bougie.
- Les modules de sortie du moteur voient ces mêmes positions comme des
  positions ordinaires du compte et les suivent en trailing serré.

D'où deux valeurs qui alternent toutes les 1 à 3 s. Preuve par les dates :
**zéro recul entre 09 h et 14 h, le premier à 15:26:16**, alors que
`miroir_papers.py` est né à 15:21:42 et a envoyé son premier ordre à 15:26.

**Conséquence plus grave que le battement** : quand c'est le stop serré
qui est en place au moment où le prix le touche, la position miroir est
fermée par une sortie que le paper n'a jamais demandée. **Les résultats
des branches sont faussés depuis le 25/08.**

### 6.3 — Le break-even qui vise le mauvais côté du prix

`daily_watchdog._move_to_be` comparait le niveau visé au **stop** actuel,
jamais au **prix** :

```python
if p.type == 0:                      # BUY
    new_sl = p.price_open + buffer
    if p.sl >= new_sl:               # <- ou est le STOP
        return p.ticket, True
else:
    new_sl = p.price_open + buffer   # SELL, volontaire (commentaire du code)
    if p.sl > 0 and p.sl <= new_sl:  # <- ou est le STOP
        return p.ticket, True
```

Une position **en perte** franchit les deux tests et part quand même.
`BE_BUFFER_PTS = {"US30": 800, "US500": 80, "US100": 500}` × `info.point`
= 8.00 / 0.80 / 5.00 — exactement les trois constantes que le courtier a
refusées 2 173 fois. Correspondance sur trois actifs : aucun autre
candidat possible.

`_check_auto_breakeven` (R7), elle, est **juste** sur ce point : elle
soustrait bien pour une vente (ligne 807) et sa garde du côté du prix
existe (lignes 804 et 812). Son seul défaut était de s'appliquer aux
miroirs.

### 6.4 — Le trou du pont

Au démarrage, l'envoyeur fige les positions vivantes comme simple
référence et **ne les copie pas** — c'est voulu, leur prix d'entrée
appartient au passé. Mais rien ne le disait.

Le 27/08 la branche 6 a ouvert deux positions sur `6240004` à 15:24:15 et
15:24:16 ; le pont est né à 15:25:33 / 15:25:45. Le panneau affichait donc
zéro affaire pour `6240004`, ce qui se lit « cette branche n'a pas tradé »
alors que la vérité est « ces trades existent et personne ne les a copiés ».
Le pont a redémarré **trois fois** ce jour-là.

### 6.5 — Le panneau ignorait la branche 6

`base_et_branche` connaissait les préfixes 4 et 5, pas le 6. Et le
panneau HTML était piloté par `BRANCHES = (1, 2, 5)`.

---

## 7. Ce qui est en place au 27/08 au soir

Tous appliqués sur la machine, tous vérifiés, tous idempotents.

| fichier | marqueur | effet |
|---|---|---|
| `daily_watchdog.py` | `[BE-COTE-PRIX-2708]` ×3 | garde du côté du prix + exemption miroir dans `_move_to_be` |
| `daily_watchdog.py` | `[R7-MIROIRS-2708]` | exemption miroir dans `_check_auto_breakeven` |
| `sl_cliquet.py` | `VERSION = "2.1"`, `PLAGES_MIROIR` | aucun module du moteur n'écrit plus de stop sur un miroir |
| `pont_miroirs.py` | `[ORPHELINS-2708]` ×3 | relevé des positions qu'un démarrage ne copiera jamais |
| `cartes_live.py` | `6220000`, `BRANCHES = (1, 2, 5, 6)`, `h6{background`, `[ECART6-2708]`, `6 = miroir 6` | branche 6 lisible partout, écart 6−1 sur les mêmes magics |

**`daily_watchdog` et `sl_cliquet` sont importés au démarrage du moteur :
ces deux corrections n'agiront qu'au prochain lancement de
`trading_engine.py`.** Elles n'ont donc encore jamais tourné. La première
séance propre est celle du 28/08.

### Outils écrits le 27/08 (sur le Drive et dans `analyse/`)

- `Lancer-Miroirs.ps1` — les cinq services, vérifiés sur ce qu'ils produisent
- `preflight_miroir.py` — **17 contrôles, GO / NO-GO avant 14:00**, aucun ordre envoyé
- `gardien_stops.py` — filet « un stop ne recule jamais », **hors magics miroir**
- `orphelins.py` — lit le relevé du pont
- `trail_miroir6.py` — le trailing 0.50R de la branche 6
- `accord_m15.py`, `mfe_partage.py`, `tp_fixe.py`, `rejoue_sorties.py` — les études

---

## 8. Les mesures qui tiennent

Ne les refaites pas, servez-vous-en. Et ne les citez pas au-delà de ce
qu'elles disent.

**MFE / MAE** (`mfe_partage.py`) — les MFE du journal sont des **moyennes**,
pas des maxima. Les gagnants capturent 58 % de leur MFE (ils en rendent
42 %). Les perdants atteignent +16 EUR avant de mourir. **48 % des
perdants passent +0.25R**, ce qui concerne 76 119 EUR de pertes.

**TP fixe** (`tp_fixe.py`) — recalcul exact, pas simulation : un TP à k·R
est rempli ⟺ MFE ≥ k·R. **Négatif aux sept seuils testés, sur les trois
familles.** À 1.2R le total est −22 145 sur un mois qui a fait +24 630.
Raison : **la queue porte le profit** — 188 gagnants sur 3 761 font 27 %
du gain brut. Tout mécanisme qui coupe les extrêmes coupe d'abord ce qui
rapporte.

**R médian en points** (`accord_m15.py`) — la perte réalisée moyenne du
magic, convertie en points via `eur_pt = profit / ((sortie − entree) × sens)` :

```
240003   NAS100 51.7   SPX500 5.5   US30 55.0     (0.5R = 25.9 / 2.8 / 27.5)
240004   NAS100 42.4   SPX500 4.3   US30 43.1     (0.5R = 21.2 / 2.1 / 21.6)
```

**Les stops bouchons (1600 pts NAS100, 4000 US30, 200 SPX500) ne sont
jamais atteints** : la perte réalisée moyenne sur SPX500 est de 5,5 points.
J'ai passé une journée à les accuser à tort.

**Branche 1 contre branche 2**, 27/08 17:32, mêmes entrées, 429 trades
contre 427 :

```
branche 1  EXEMPTE des sorties   +225.61    amplitude par magic : 1399
branche 2  SOUMISE aux sorties   +332.86    amplitude par magic :  350
```

En total presque rien — 107 EUR d'écart. Mais **l'amplitude est divisée
par quatre**. Les modules de sortie ne gagnent ni ne perdent : ils
**compriment**. Ils coûtent 569 EUR sur 240004 et 478 sur 240007, les deux
meilleures, et sauvent 531 sur 240006 et 454 sur 220014, les deux pires.

> Réserve d'honnêteté : que l'écart soit négatif là où la branche 1 gagne
> est **en partie un artefact** — soustraire la branche 1 d'un résultat
> largement indépendant produit mécaniquement cette anticorrélation. Ce
> qui n'est pas un artefact, c'est l'étendue : 1 399 contre 350.

**Branche 6, premier signe** — sur `240003`, 27/08 17:32 :

```
miroir 1   n 45   67%   borne 52%   -1.99/tr    -89.72    4 ouvertes
miroir 2   n 47   55%   borne 41%   -0.51/tr    -24.11
miroir 5   n 17   65%   borne 41%   +2.20/tr    +37.39    1 ouverte
miroir 6   n 31   65%   borne 47%   +3.14/tr    +97.24    0 ouverte
```

**Ce n'est pas encore comparable** : n 45 contre n 31, la branche 6
n'existe que depuis 15:21, et la journée est contaminée par la guerre des
stops. `6240004` est absent — ses deux positions sont les orphelines de
15:24.

---

## 9. Faits techniques établis, à ne pas re-découvrir

- **Un processus né AVANT une modification de fichier exécute l'ancien
  code.** Seule la comparaison heure de naissance / mtime compte.
- **Présence n'est pas production.** Vérifier ce qu'un processus
  *produit*, jamais qu'il existe.
- `mt5.order_send` rendant `None` : la cause est dans `mt5.last_error()`.
  Tout code qui jette cette valeur est à corriger avant de chercher.
- `order_check()` valide une requête auprès du courtier **sans trader**.
  C'est la sonde sûre.
- **Modes de remplissage** : `SYMBOL_FILLING_FOK = 1` (masque du symbole)
  et `ORDER_FILLING_FOK = 0` (type d'ordre) n'ont pas la même numérotation.
  Ici, mesuré : `FOK(0) -> (0, 'Done')`, IOC et RETURN → `10030`.
- **`trade_stops_level = 1`**, soit 0.01 point : le courtier n'impose
  **aucune** distance minimale. Un refus `[Invalid stops]` signifie donc
  « stop du mauvais côté du prix », pas « trop près ».
- Les journaux du terminal MT5 sont en **UTF-16LE**.
- `[IO.File]::ReadAllText` avec un chemin relatif résout depuis le cwd de
  .NET (`C:\Windows\system32`). Utiliser `Resolve-Path`.
- Sous PowerShell, `copy` est un alias de `Copy-Item` : `/Y` n'existe pas,
  c'est `-Force`.
- **Un socket lié à `127.0.0.1` n'accepte que les connexions de la machine
  elle-même. Aucune règle de pare-feu n'y peut rien.**

---

## 10. Méthode — ce qui a échoué et pourquoi

Extraits de `mistakes.md`, à lire en entier. Les plus coûteux :

**Une sortie vide n'est pas une preuve.** Un `Select-String` revenu sans
rien m'a fait conclure que `sl_cliquet` n'avait jamais été armé depuis le
10/08. La commande suivante en a trouvé **3 194 lignes**. « Rien à
trouver » et « la commande n'a pas tourné » ne se distinguent pas à
l'écran.

**Compter des tentatives comme des faits.** Trois jours de volumes annoncés
mélangeaient `modify` et `failed modify`. Le mot `failed` était au début
de chaque ligne.

**Une hypothèse plausible tenue pour acquise.** J'ai écrit que les stops
étaient refusés pour proximité. `trade_stops_level` valait 1. Le courtier
écrit la raison de son refus ; la lire coûte une commande.

**Déduire une architecture d'un intervalle.** Deux écritures identiques à
30 ms m'ont fait annoncer « deux instances du même programme ».
L'inventaire montrait 22 processus, tous uniques.

**Un outil qui rend un faux verdict** vaut moins que pas d'outil.
`Lancer-Miroirs.ps1` a déclaré le gardien MUET parce qu'il surveillait la
sortie redirigée et non le journal propre du service.

### Règles pour les patchs

Trois patchs ont échoué cette semaine sur des ancres. Ce qui marche :

1. **Ancres en expressions régulières**, tolérantes aux espaces, jamais
   recopiées d'un écran au caractère près.
2. **Chaque ancre exigée exactement une fois**, et **délimitée à la
   fonction** quand le motif existe ailleurs — la requête SLTP de
   `_move_to_be` est identique à celle de `_check_auto_breakeven`.
3. **Marqueur sentinelle** qui n'existe nulle part ailleurs, vérifié
   **dans le fichier cible** — pas dans le patch lui-même.
4. **Nombre de marqueurs attendus DÉDUIT** des blocs posés, jamais écrit
   en dur : je l'ai codé 4 pour 3 marqueurs réels et la vérification a
   annulé le patch, ce qui était son rôle.
5. `compile()` avant écriture, sauvegarde horodatée, relecture après
   écriture, **retour arrière automatique** si la vérification échoue.
6. **Simulation par défaut**, `--appliquer` pour agir.
7. Lecture/écriture en **latin-1 octet-exact** pour les `.bat`, détection
   CRLF pour tout le reste.

### Règles de forme

- Une seule instruction par message.
- Un bloc de code encadré est réservé à ce que l'utilisateur doit taper ;
  le code illustratif se met en retrait simple.
- Toute commande destinée à la machine est précédée de `▶ SUR MSITRIDENT2`.
- Ne jamais présenter un chiffre de maquette comme un résultat réel.

---

## 11. Les demandes ouvertes au 28/08

### A — Les panneaux ne sont joignables qu'en local, pas via Tailscale

**Ce n'est probablement pas le pare-feu.** Le même défaut a été diagnostiqué
et corrigé le **12/08 sur le port 8097**, et `patch_orderflow_hote.py` le
documente :

```
    HTTPServer(("127.0.0.1", a.port), H).serve_forever()
```

Relevé de l'époque : `8097 -> 127.0.0.1` (injoignable), `8095 -> 0.0.0.0`
(joignable). Premier geste, en lecture seule :

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object LocalPort -in 8081,8095,8096,8097 |
  Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table -Auto
```

`127.0.0.1` → c'est le bind, et `patch_orderflow_hote.py` est le modèle du
correctif (argument `--hote`). `0.0.0.0` → alors seulement le pare-feu.

**Recommandation** : ne pas lier à `0.0.0.0`, qui expose le panneau à
toutes les interfaces sans mot de passe sur une machine qui trade. Lier à
l'**adresse Tailscale** précisément. L'argument `--hote <ip>` le permet.

### B — Les fichiers ne sont plus mis à jour sur le Drive

Inventaire du 27/08 au soir de `G:\Mon Drive\ScalpEA` : uniquement du
**code**. Les seuls exports de données datent du **25/08 à 12:26** :

```
scalp_rails_20260825-1226.txt       95 169 o
scalp_context_20260825-1226.txt     41 228 o
scalp_orderflow_20260825-1225.txt   18 900 o
scalp_account_20260825-1226.txt      1 651 o
```

Aucun panneau, aucun `.json` du pont, rien du 26 ni du 27. L'exportateur
n'est pas identifié — `archive_drive.py` est un outil d'archivage, pas lui.
Premier geste :

```powershell
Select-String -Path *.py -Pattern 'scalp_rails_|scalp_context_|scalp_account_' -List |
  ForEach-Object { $_.Filename }
```

Puis, une fois nommé : tourne-t-il encore, échoue-t-il en silence, ou
écrit-il ailleurs ? **Présence n'est pas production**, ici aussi.

L'utilisateur mentionne le **12/08** comme date de rupture. Les exports
que je vois datent du 25/08 ; il parle peut-être d'un autre jeu de
fichiers. À vérifier avant de conclure.

### C — L'appariement branche 1 / branche 6 par ticket

La comparaison du panneau porte sur des effectifs qui ne se recouvrent
qu'à moitié (n 45 contre n 31). **Le seul chiffre qui tranchera** est
l'écart calculé sur les **paires réelles** : même signal, même instant,
même lot, sorties différentes. À faire sur les données de la séance du 28.

### D — La séquence du matin

```
1.  .\Lancer-Miroirs.ps1 -Go        les cinq services, verifies sur leur production
2.  python preflight_miroir.py      17 controles, avant 14:00, aucun ordre envoye
3.  python orphelins.py             ce que le demarrage du pont n a pas copie
```

Le préflight est celui qui compte : il refuse en dix secondes si
l'enveloppe `sl_cliquet` est revenue dans le miroir. Lancé à 13:45, il
laisse le temps de corriger. **L'utilisateur a exigé, en toutes lettres,
que la perte d'1 h 27 du 27/08 ne se reproduise pas.**

### E — En attente, non urgent

- **Révoquer le mot de passe d'application Gmail** dans `START_TRADING_STACK_V3.bat`.
- Silencer les `DeprecationWarning` sur `utcfromtimestamp`, `pont_miroirs.py`.
- Purger `liens.json` au changement de jour.
- `etat.json.tmp` traîne depuis le 25/08.
- Nommer ce qui, sur le compte moteur, reposait le stop bouchon — la
  cause est identifiée (collision miroir/moteur) mais le module exact qui
  écrit le bouchon à l'ouverture n'a pas été isolé.

---

## 12. Les documents à lire dans `analyse/`

`mistakes.md` (2 257 lignes) — **en premier, en entier**
`PROTOCOLE.md`, `PROTOCOLE_17-08.md`, `PROTOCOLE_ajout_17-08.md`
`HYPOTHESES.md`, `HYPOTHESES_17-08.md`
`CLAUDE_pour_le_VPS.md` — les ports, la topologie
`NOTES_sorties.md`, `NOTES_c14_trail.md`, `NOTES_gates_25-08.md`,
`NOTES_papers_25-08.md`, `NOTES_orderflow_24-08.md`,
`NOTES_migration_24-08.md`, `NOTES_panneaux.md`, `NOTES_drive_a_faire.md`
`JOURNAL_14_08.md`, `JOURNAL_pour_le_REPL.md`

---

## 13. Le ton attendu

L'utilisateur trade en direct, 5 heures par jour. Il n'a pas de temps
pour l'approximation et il l'a dit sans détour hier :

> « on trade sur le paper 5 h par jour, et toi tu perds 1 h 15 encore au
> troisième jour car tu ne sais pas lancer correctement le miroir »

> « je ne veux pas de patch correctif, je veux que tout soit fonctionnel »

Ce qu'il attend : la cause nommée, pas le symptôme masqué. Un chiffre
mesuré, pas supposé. Et quand une mesure est fausse, le dire avant qu'il
la lise — j'ai dû me corriger plusieurs fois hier, et c'était à chaque
fois moins coûteux que de laisser passer.
