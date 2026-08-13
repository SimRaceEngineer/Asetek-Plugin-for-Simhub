# Cette machine trade en réel. À lire avant toute action.

À placer sous le nom `CLAUDE.md` à la racine du dossier de la stack
(`C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main`).
Claude Code le lit automatiquement au démarrage d'une session dans ce
dossier.

Ce fichier n'est pas une liste de bonnes pratiques. Chaque règle vient
d'un incident réel, daté, sur cette machine.

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
