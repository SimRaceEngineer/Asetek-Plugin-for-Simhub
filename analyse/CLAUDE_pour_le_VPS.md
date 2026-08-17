# Cette machine trade en réel. À lire avant toute action.

À placer sous le nom `CLAUDE.md` à la racine du dossier de la stack
(`C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main`).
Claude Code le lit automatiquement au démarrage d'une session dans ce
dossier.

Ce fichier n'est pas une liste de bonnes pratiques. Chaque règle vient
d'un incident réel, daté, sur cette machine.

---


## À LIRE AVANT DE COMMENCER — dans cet ordre, à chaque session

Trois fichiers, et aucun n'est optionnel. Le 17/08, faute de les avoir
lus, une matinée est partie à réécrire un lecteur `.scid` et à réclamer
un export d'orderflow — alors qu'un pipeline complet tournait déjà,
joignait l'orderflow aux tickets réels depuis le 29 avril, et
produisait un contrefactuel en euros.

1. **ce fichier** — les règles de la machine et les interdits ;
2. **`PROTOCOLE.md`** — **ce qui existe déjà** : les sources avec leurs
   défauts mesurés, la table des fuseaux horaires, les outils, les
   panneaux, les rendez-vous en cours. C'est le fichier qui empêche de
   reconstruire l'existant ;
3. **`mistakes.md`** — ce qui a déjà été cassé, et les règles qui en
   sont nées.

Puis seulement : relire la conversation en cours.

**Ne rien écrire avant d'avoir vérifié dans `PROTOCOLE.md` que ça
n'existe pas.** Poser la question à l'utilisateur coûte trente
secondes ; réécrire un outil existant coûte une matinée, et le pire est
qu'on ne s'en aperçoit pas.

`PROTOCOLE.md` se tient à jour **à chaque ajout** de source, d'outil ou
de convention — au même titre que `mistakes.md` se tient à jour à
chaque erreur.

---

## Ce qu'est cette machine

Un VPS Windows Server qui fait tourner une stack de scalping en
**production, avec de l'argent réel** : environ 200 modules Python, un
terminal MetaTrader 5, des moteurs qui envoient des ordres, et des
positions ouvertes à toute heure de la journée.

Une commande maladroite ici ne casse pas un test — elle ferme des
positions, ou en ouvre.

---

## Les cinq interdits

**1. Jamais `Stop-Process -Name python`.**
Dix-neuf scripts Python tournent en permanence, dont `trading_engine`
qui envoie les ordres. Tuer par nom les tue tous. Pour arrêter un
script précis, filtrer sur sa ligne de commande et n'agir que sur les
PID retournés :

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object CommandLine -like '*nom_du_script*' |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**2. Jamais lancer `price_action.py` sans `PA_ROLE=panel`.**
C'est la variable la plus dangereuse de la stack. Avec `PA_ROLE=panel`,
le script sert le panneau du port 8095 et n'envoie aucun ordre. **Sans
elle, il démarre en rôle moteur et envoie de vrais ordres.** Le 12/08,
un script de supervision écrit sans avoir lu `run_panel_loop.bat`
l'aurait lancé sans cette variable. Découvert avant exécution, de
justesse.

Corollaire : **lire le `.bat` avant d'écrire quoi que ce soit qui
lance un processus.** Les wrappers portent des variables
d'environnement qu'on ne devine pas.

**3. Ne jamais approcher `terminal64.exe`.**
Le terminal MetaTrader. Ni le tuer, ni le redémarrer, ni le
reconfigurer. Tout le reste en dépend.

**4. Ne jamais toucher un `regles_gelees_v*.py`.**
Ces fichiers sont gelés à une date et servent de référence pour juger
les versions suivantes. Les modifier détruit rétroactivement la
comparaison.

**5. Ne jamais agir sur un processus qui n'est pas dans une liste
explicite.** Pas de « je nettoie ce qui traîne ».

Corollaire découvert le 13/08 : **tous les modules n'ont pas de
processus.** `ignition_trader.py` et `ignition_trader_trail.py` — les
deux bras qui envoient les ordres — n'apparaissent dans aucune liste
de processus. Ils sont **importés par `trading_engine.py`** :

```
PID 7124  python trading_engine.py --stop-hour 20
PID  368  stall_sniper.py 7124        <- il surveille 7124
```

Donc « redémarrer le moteur d'ignition » veut dire redémarrer le
processus qui envoie **tous** les ordres de la stack, qui héberge les
ports 8090, 8091, 8093, 8094 et 8096, et qui a un `stall_sniper`
accroché à son PID. Pendant la coupure, les positions ouvertes ne sont
plus gérées : pas de trail, pas de détection de reverse, pas de mise à
plat de séance. Elles restent ouvertes chez le courtier, sans personne
au volant.

Avant de proposer de redémarrer quoi que ce soit, chercher le
processus par sa **ligne de commande**, pas par le nom du fichier
qu'on croit relancer.

**Et le moteur ne se redémarre pas à la main.** Il porte son propre
mécanisme, documenté dans les `.bat` :

```
START_TRADING_STACK_V3.bat:335   start "Trading Engine" /MIN cmd /c
                                 %PY% trading_engine.py --stop-hour %STOP_HOUR%
stack_watchdog.bat:16-19  REM Planifie : \TradingStack\FreshnessWatchdog,
                          REM toutes les 15 min. Relance = start V3.
                          REM V3 self-kill python + garde 8095/fraicheur
                          REM neutralise un survivant. Pas de double engine.
```

Donc le moteur **s'arrête seul à 20:00** (`--stop-hour 20`), une
demi-heure après la mise à plat de séance.

**Ce qui le relance n'est PAS vérifié.** Le commentaire ci-dessus
décrit une tâche `\TradingStack\FreshnessWatchdog`, mais le 13/08
`Get-ScheduledTask -TaskPath "\TradingStack\*"` répond « The system
cannot find the file specified », et le cmdlet échoue même sans filtre
— une entrée corrompue casse son énumération. Le commentaire d'un
`.bat` décrit une intention d'installation, pas un état constaté ;
c'est une source à traiter comme telle. Contourner avec
`schtasks /query /fo TABLE /nh`.

Ce qui se vérifie, en revanche, c'est le battement :

```powershell
$hb = "$env:APPDATA\MetaQuotes\Terminal\Common\Files\cross_index_gate.dat"
((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds
```

Sous 15 secondes après 20:00, quelque chose a relancé le moteur. Au
-delà, il est arrêté et il faut lancer `START_TRADING_STACK_V3.bat`.

Un `Stop-Process` à la main court-circuite le garde-fou
anti-double-moteur de V3 et risque d'en laisser tourner deux. La
relance passe par le `.bat`, pas autrement.

Conséquence pratique : **un patch sur un module importé par le moteur
prend effet au prochain démarrage, donc le soir après 20:00, hors
séance.** C'est la meilleure fenêtre possible — celle où la règle de
session empêche les cellules fraîchement armées d'ouvrir en rafale.
Elle demande au plus un geste, jamais en pleine séance.

---

## Ce qui tourne, et sur quels ports

```
8081  trade_monitor      8093  watchdog        8096  pos spy
8089  bridge             8094  guardian        8097  orderflow_panel
8090  pitwall            8095  price_action    8098  XAU
8091  inst dash
```

Le PID qui détient 8090, 8091, 8093, 8094 et 8096 est le même : c'est
`trading_engine`, qui héberge plusieurs panneaux.

**Le battement du moteur** est le seul indicateur de vie fiable :

```powershell
$hb = "$env:APPDATA\MetaQuotes\Terminal\Common\Files\cross_index_gate.dat"
((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds
```

Sous 15 secondes, le moteur est vivant. Un HTTP 200 sur un port ne
prouve rien : un processus zombie répond 200.

---

## Trois pièges Windows qui ont coûté des heures

**`SO_REUSEADDR`** : plusieurs processus peuvent écouter le même port
sans erreur, et **c'est le dernier qui reçoit le trafic**.
`Get-NetTCPConnection` renvoie le premier. Pour dédoublonner un
service porté, garder le plus RÉCENT.

**Le shim PyManager** : `Start-Process python` lance
`C:\Program Files\PyManager\python.exe`, qui relance le vrai
interpréteur `pythoncore-3.14-64`. Un lancement produit donc **deux**
processus portant la même ligne de commande. Un `Count` à 2 n'est pas
forcément un doublon — vérifier si l'un est le parent de l'autre.
Lancer directement
`C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe`
évite le couple.

**Un panneau lent n'est pas un panneau mort** : le 8097 mettait 9,46 s
à répondre. Un timeout HTTP à 6 s le déclarait mort et le redémarrait
en boucle. Toujours tester la connexion TCP d'abord, distinguer
« refusé » de « lent », et ne redémarrer que sur un refus.

**Le `VERIFY` de V3 annonce un double moteur qui n'existe pas.** Le
13/08 il a écrit `KO trading_engine : 2 instances (DOUBLE)` alors
qu'un seul tournait. Il compte les processus dont la ligne de commande
contient `trading_engine`, et le `stall_sniper` en fait partie :

```
stall_sniper.py 9140 ...\logs\trading_engine_20260813.log
```

Croire cette alerte et « supprimer le doublon » revient à tuer le seul
moteur en service, avec des positions ouvertes. Le compte juste exclut
le sniper :

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'trading_engine\.py' -and
                 $_.CommandLine -notmatch 'stall_sniper' }
```

**Et pour coller une commande** : PowerShell fusionne les lignes d'un
collage multi-lignes, ce qui a produit trois échecs le 13/08
(`patch_x60_atomique.py$PY = ...`). Une commande = **une seule ligne**,
les étapes séparées par des points-virgules. Une ligne unique ne peut
pas se fusionner avec la suivante.

---

## Comment on modifie un fichier ici

Jamais d'édition directe d'un fichier de production. Un **script de
patch**, qui :

1. vérifie que chaque ancre est **unique** dans le fichier, et refuse
   sinon ;
2. passe `ast.parse` sur le résultat **avant** d'écrire ;
3. écrit une sauvegarde horodatée à côté ;
4. est **idempotent** — relancé, il dit « déjà appliqué » ;
5. accepte `--essai`, qui affiche tout et n'écrit rien.

Et quand le contrôle syntaxique ne suffit pas, vérifier sur l'**arbre**.
Le 13/08, un bloc s'est posé dans la branche `else` au lieu d'après le
`if/else` : les deux versions compilent, mais la mauvaise ne s'exécute
que quand l'étape précédente échoue. `ast.parse` ne l'aurait jamais vu.

### `mistakes.md` — à lire avant, à tenir après

**Lire `mistakes.md` avant d'écrire un patch, et y ajouter une entrée
le jour même de chaque erreur ou de chaque casse.** Une erreur
rattrapée par un garde-fou compte autant qu'une erreur en production :
le garde-fou aurait pu manquer.

Chaque entrée porte cinq choses — ce qui a été fait, **le raisonnement
faux** qui y a conduit, la conséquence réelle sans l'adoucir, le
correctif, et la règle vérifiable qui en découle. C'est le raisonnement
faux qui est la partie utile : c'est lui qui se répète.

Le 14/08, la page du panneau est morte au chargement sur
`name '_os' is not defined` parce qu'un garde-fou utilisait `ast.walk`,
qui descend dans les fonctions, et avait pris un import local pour un
import de module. La règle qui en est sortie — *le code généré
n'emprunte aucun nom au module cible* — a servi trois heures plus tard
sur la route `/profils`, écrite avec des builtins uniquement. C'est à
ça que sert le fichier.

---

## Ce qui est en cours d'observation

- `papier_tf.py` — 36 cellules de trading papier, M10 à H4, bras 206 et
  207, règles reprises de `ignition_trader.py` et
  `ignition_trader_trail.py`. **Lecture seule, aucun ordre.**
- `x60_onset.py` — observe les magics de setup 60 (les cellules H1) et
  photographie qui est en position quand ils entrent et sortent.
- `panels_auto.py` — régénère les panneaux toutes les 15 minutes.

Ces trois-là n'envoient aucun ordre et ne touchent aucun fichier du
moteur. Ils peuvent être arrêtés et relancés sans risque.

**Mais `START_TRADING_STACK_V3.bat` les tue tous.** Constaté le 13/08 :
après un redémarrage du moteur, `papier_tf`, `x60_onset`,
`rafraichir_x60` et `panels_auto` avaient disparu — emportés par le
« Previous windows killed » de l'étape 0, alors qu'aucun d'eux
n'écoute de port et qu'aucun n'est dans les `.bat` de V3.

Aucun ordre en jeu, mais **plus aucune mesure ne s'écrit** tant qu'on
ne les relance pas, et rien ne le signale. Après tout redémarrage de
la stack, les relancer explicitement :

```powershell
$PY = "C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe"
Start-Process -WindowStyle Hidden $PY -ArgumentList '-u','papier_tf.py','--loop'
Start-Process -WindowStyle Hidden $PY -ArgumentList '-u','x60_onset.py','--loop'
Start-Process -WindowStyle Hidden $PY -ArgumentList '-u','rafraichir_x60.py'
Start-Process -WindowStyle Hidden $PY -ArgumentList '-u','panels_auto.py','--dest','panels'
```

`papier_tf` redémarre sans danger : son amorçage arme les 36 cellules
sans en ouvrir aucune — c'est le correctif du 12/08, écrit après les
huit positions ouvertes à la même seconde.

---

## La règle qui résume les autres

**Mesurer avant de conclure, et dire ce qu'on ne sait pas.**

Un chiffre sans sa couverture ne vaut rien : « zéro trade en Asie » et
« l'observateur ne tournait pas cette nuit-là » produisent le même
fichier vide. Toutes les mesures d'ici portent une colonne « observé »
pour cette raison.

Et quand un résultat semble trop beau, chercher l'artefact avant de
chercher l'explication. Le 12/08 à 23:38:54, huit positions se sont
ouvertes à la même seconde au démarrage d'un observateur : elles
portaient à elles seules la quasi-totalité des pertes attribuées à
trois unités de temps.
