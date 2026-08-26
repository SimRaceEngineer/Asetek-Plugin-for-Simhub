# memory.md — les faits stables de cette installation

Ce fichier ne raconte rien. Il contient les valeurs qu'on redécouvre
sinon à chaque session, et qui ont chacune coûté au moins un
aller-retour. `mistakes.md` explique **pourquoi** ; celui-ci dit
**quoi**, en une ligne.

À relire avant de donner une commande, pas après.

---

## La règle qui prime sur toutes les autres

**Un prompt = UNE commande.** Un seul bloc à coller, une seule
instruction. Une commande qui échoue doit arrêter la séquence — elle
ne le peut pas si la séquence est déjà dans le presse-papier.

Quand l'utilisateur demande d'aller vite, c'est l'ANALYSE qu'on
condense, jamais l'exécution.

Le bloc clôturé est réservé à ce qui se tape. Le code d'illustration
se cite en indentation simple.

---

## Les chemins

| quoi | où |
|---|---|
| la stack | `C:\SVPS\Scalp-EA-main` |
| le Drive local | `G:\Mon Drive\ScalpEA` — **Mon**, pas *My*, le client est en français |
| le Drive distant | dossier `ScalpEA`, id `1mg7ycg4Jy6V8ZdBvKst4lsv6AduPpE_4` |
| les journaux | `C:\SVPS\Scalp-EA-main\logs` |
| le panneau | `http://vmi654074:8095` |
| les cartes servies | `C:\SVPS\Scalp-EA-main\cartes` — relu à chaque requête |

Un journal est nommé au DÉMARRAGE du processus, pas à la date du jour :
`trading_engine_20260824.log` écrit encore le 25 signifie que le moteur
tourne depuis la veille.

---

## Les deux terminaux MT5

| rôle | chemin |
|---|---|
| moteur | `C:\Program Files\TF Global Markets MetaTrader 5 Termina-LOCALSTACKl\terminal64.exe` |
| dédié 18\*\*09 | `C:\Program Files\TF Global Markets MetaTrader 5 Terminal\terminal64.exe` |

**Un processus Python = un terminal MT5.** C'est la raison d'être des
deux processus du pont, et la raison pour laquelle seul l'envoyeur peut
rendre compte du compte dédié.

---

## Les magics

`bras | actif | horizon`. Au-delà de 99 l'horizon prend trois chiffres
(`2073120`).

| plage | ce que c'est |
|---|---|
| 206xxx / 207xxx | les bras du moteur |
| 220001 – 220012 | douze stratégies, croisement de trois sections |
| 2301xx – 2303xx | les stratégies DeepSeek, découpées par actif (1xx US30, 2xx US500, 3xx US100) |
| 240001 – 240010 | mes propres règles |
| 4xxxxxx | miroir 2 : le magic du miroir 1 préfixé d'un 4 |

Miroir 1 et miroir 2 : **même entrée, même lot, même instant**. Seule
la sortie diffère. L'écart entre les deux ne mesure donc que la gestion
de sortie.

---

## Les codes retour MT5 qui reviennent

| code | sens |
|---|---|
| 10020 | le faux « bloqué » des gates de la stack |
| 10025 | `NO_CHANGES` — cette position a déjà ce stop |
| 10027 | AutoTrading éteint côté client |
| 10030 | mode de remplissage non supporté |

`10025` n'est pas un échec : c'est une confirmation. Le traiter comme
une erreur produit un journal illisible.

---

## PowerShell, ce qui piège

- `sort` et `group` **bufferisent tout** avant d'émettre. Indiscernable
  d'un blocage. Trois faux « stuck » le 25/08.
- `Stop-Process -Name python` est **interdit**. Toujours par PID, et
  en filtrant d'abord sur `CommandLine`.
- `$_.CommandLine` n'existe que sur `gcim Win32_Process`, pas sur `gps`.

## Python, ce qui piège

- Un module chargé reste en mémoire : **corriger le `.py` ne corrige
  pas le processus qui tourne.**
- `os.remove` + `os.rename` ouvre une fenêtre où le fichier n'existe
  pas → `PermissionError [WinError 32]`. `os.replace` est atomique.
- `dire()` ne doit jamais dépendre d'une console : `sys.stdout` peut
  être `None` sous `pythonw` ou `DETACHED_PROCESS`.

---

## Les cinq interdits

1. jamais `Stop-Process -Name python` ;
2. jamais `price_action.py` sans `PA_ROLE=panel` ;
3. jamais approcher `terminal64.exe` ;
4. jamais modifier un `regles_gelees_v*.py` ;
5. jamais agir sur un processus hors d'une liste explicite ;
6. jamais « réparer » un flux dont la cause de panne n'est pas
   identifiée.

(Ils sont six. Le nom leur est resté.)

---

## Les secrets

Toute valeur ressemblant à une clé — KEY, TOKEN, SECRET, PASSWORD,
Authorization, Bearer, `sk-…` — est affichée **masquée, longueur
seule**. Les numéros de compte aussi : `18**09`, `17**80`.

Un mot de passe ne se colle pas dans la conversation. L'envoyeur
s'attache à un terminal DÉJÀ connecté, par son chemin, jamais avec des
identifiants.

---

## Déposer un fichier sur le Drive

On dépose sous un nom NOUVEAU et on renomme à la copie. Remplacer en
supprimant l'ancien a déjà détruit un fichier : Drive Desktop n'accepte
pas deux noms identiques et supprime celui que la corbeille désigne.

La synchronisation locale prend quelques dizaines de secondes. Un
fichier absent de `G:` juste après un dépôt n'est pas un échec.

---

## Le CVD et la règle d'expansion — mesuré les 25 et 26/08

**La règle.** Si le delta de la bougie précédente vaut −38, on ne vend
que si le delta courant descend **sous** −39. On ne joue pas le niveau
du flux, on joue son **expansion**.

**Trois cadrages, un seul honnête.**

| cadrage | ce qu'il fait | valeur |
|---|---|---|
| `closes` | delta(n−1) contre delta(n−2) | causal mais aveugle à la bougie en cours |
| **`écoulée`** | **portion écoulée de n, reconstruite des ticks, contre n−1** | **causal ET réaliste — le seul à lire** |
| `complete` | bougie d'entrée entière contre n−1 | **non causal**, et en partie circulaire |

`complete` n'est pas une « borne haute » atteignable : le delta de la
bougie d'entrée porte le signe de son `close − open`, donc il est déjà
corrélé au sort immédiat du trade.

**Ce que le cadrage change.** En M5, `closes` donnait **+1 149** — la
meilleure case du tableau. L'écoulé donne **−726**. Agir sur `closes`
aurait implémenté l'inverse de ce qu'il fallait.

**Résultat, colonne écoulée, 401 entrées PM :**

| pas (écarts-types) | M1 | M3 | M5 | M15 |
|---|---|---|---|---|
| 0 | +480 | +59 | −726 | +678 |
| 0,25 | +386 | −104 | −365 | +417 |
| 0,5 | +330 | +112 | −228 | +839 |
| 1 | +355 | +301 | +185 | +884 |

**M1 et M15 tiennent aux quatre pas.** M1 se **réplique** : 345 entrées
et pas absolus le 25/08 (+421/+403/+399/+290/+333), 401 entrées et pas
relatifs le 26/08 (+480/+386/+330/+355). Deux échantillons, deux
paramétrages, même bande.

Réserve : M1 et M15 marchent, M3 et M5 non — ce n'est pas un profil
lisse, et les quatre unités partagent les mêmes ticks. Ce ne sont pas
quatre tests indépendants.

**Le lissage EMA14 détruit la règle** : de +458 à −232. Lisser une
expansion, c'est l'effacer. On garde le delta **brut**.

**L'échelle des deltas grandit avec la bougie** — écart-type mesuré :

| | US30 | US500 | US100 |
|---|---|---|---|
| M1 | 29 | 24 | 66 |
| M15 | 428 | 350 | 982 |

Un pas **absolu** n'a donc pas le même sens selon l'unité : 5 points
comptent en M1 et sont invisibles en M15. Le pas se donne en
**écarts-types**.

`CVD_PAS = 1.0` point en live vaut donc un pas relatif de 0,02–0,03,
soit la case « M1 ≈ pas 0 » — celle qui s'est répliquée. Le réglage
live est le bon.

---

## MT5 : trois horloges, et elles ne sont pas les mêmes

1. **Serveur contre machine** : le serveur a **+1 h** (+3 600 s). Lu
   dans un tick, jamais supposé.
2. **Décalage de REQUÊTE des ticks** : pour obtenir les ticks de la
   barre `m`, il faut demander `[m+7200, m+7260]`. Mesuré en balayant
   ±4 h et en exigeant que les **quatre** prix OHLC coïncident sur au
   moins deux barres.
3. **Base des HORODATAGES retournés** : le champ `time` des ticks rendus
   revient en **+0 s**, pas en +7200.

**Les points 2 et 3 sont deux questions différentes.** Les confondre a
vidé le cadrage écoulé : 401 entrées sur 401 sans donnée, alors que
398 fenêtres de ticks avaient bien été lues. Un outil qui ne fait
qu'une seule fenêtre ne s'en aperçoit pas ; un outil qui découpe des
sous-fenêtres en comparant les temps, si.

Les barres M1 de MT5 sont construites sur le **bid**.

---

## Les sorties du papier — mesuré le 26/08

`docs\papier_tf\trades.jsonl` porte **deux bras, 206 et 207**. Ni
220xxx ni 240xxx : ce n'est **pas** le papier des stratégies du
panneau. Les poser côte à côte comparerait deux choses différentes.

**Le 207 solde en DEUX FOIS.** C'est ce qui explique 740
enregistrements contre 504 — pas deux fois plus de trades, des trades
coupés en deux. Sans fusionner les morceaux :

- le PnL du 207 est amputé de moitié sur ces trades ;
- **pire**, le MFE du second morceau est mesuré après une prise
  partielle : il sort trop bas et classe le trade en « mort-né ». La
  part de mort-nés passait de **0 % à 85 %** sur données d'essai. Le
  diagnostic lui-même était faux, pas seulement les montants.

**L'autopsie, bras 206 (propre) :** 60 % de **mort-nés** (MFE < 50 % de
la perte — l'entrée est en cause), 26 % de **retournés** (la sortie
laisse filer). Rendu moyen **55,7 points** depuis le meilleur point.

**L'asymétrie achat/vente traverse les trois motifs** : achats −4 993,
ventes +1 877. `SESSION_FLAT` achat 19 % de réussite contre vente 75 %.
Achat perd sur les trois actifs, vente gagne sur les trois. Le pire :
`achat en séance` −3 856 contre `vente en séance` +2 669.

**Mais ça ne prouve rien sur le signal** tant que la dérive n'est pas
séparée. `derive_papier.py` décompose :

    moyenne(sens × mouvement) = moyenne(sens) × moyenne(mouvement)  ← BIAIS
                              + covariance(sens, mouvement)         ← SÉLECTION

Le test : `discrimination = moyenne(d | achat) − moyenne(d | vente)`,
t de Welch. **La dérive déplace les deux moyennes ensemble et disparaît
de leur différence** — c'est un test que la période ne peut pas truquer.

---

## Comparer deux bras : ce qui est légitime et ce qui ne l'est pas

**Effectifs identiques par construction** (miroir 1 contre 2, même
entrée au même instant) → comparer les **montants** a un sens.

**Effectifs différents par construction** (branche 5 refuse des
entrées) → comparer les montants mesurerait le **nombre de trades**.
Seul le **PnL par trade** compare la qualité.

Afficher le même écart des deux côtés serait plus symétrique et faux.

Le **t apparié** est le chiffre d'un A/B : les deux bras partagent la
même entrée, donc le même aléa de marché ; l'apparier annule cet aléa.
Un écart en euros sans son t ne dit rien.

**Le témoin « vente systématique » ne marche pas** : sur un trade
vendeur, il EST le trade. L'apport y vaut zéro par construction.

---

## Les pièges de mesure, tous rencontrés

- **Une marque de vérification doit exister dans le SOURCE**, pas dans
  la sortie. Chercher `MIROIR 5` alors que l'en-tête naît d'une boucle
  a fait crier « RESTAURER » sur un patch correct. Une fausse alerte
  est pire qu'un échec franc : elle pousse à défaire du travail valide.
- **Deux regex, deux noms.** Réutiliser `m` pour `CVD_PAS` puis
  `MAX_MIROIRS` a fait tester le filtre avec un pas de **90** au lieu
  de 1 — les trois actifs ressortaient « bloqué », résultat faux et
  alarmant.
- **Un processus né AVANT l'édition du fichier porte l'ancien code.**
  Python charge en mémoire au démarrage. Le seul contrôle qui vaut
  compare l'heure de naissance du processus à la date du fichier.
- **`MAX_MIROIRS` compte des BRANCHES**, pas des parents. Trois
  branches au lieu de deux, c'est +50 % de compte : un plafond à 60
  coupe la branche 5 **les jours chargés seulement** — le pire des
  défauts.
- **Compter les combinaisons essayées.** 48 cases, la meilleure sortira
  toujours bonne : c'est la définition d'un maximum. Ce qui compte,
  c'est un réglage qui tient sur **plusieurs unités et plusieurs pas**.
- **Un nombre rangé sous le mauvais en-tête est un nombre qui ment.**
- **Un ratio absent se voit, un ratio faux ne se voit pas** : rendre
  `None` plutôt que zéro quand la donnée manque.
- **Une exclusion tue est une exclusion qui ment** : orphelins et
  fractionnés sont comptés et affichés, jamais écartés en silence.

---

## Les ratios, et où les mettre

`Wilson` (borne basse 95 %), `RR d'équilibre` (1−p)/p, `PF`
(gains/pertes, `inf` sans perte — signal d'effectif trop faible, pas
une performance), `espérance`, `sigma`, `Sharpe`.

**Sharpe par trade et NON annualisé** : annualiser demanderait de
supposer un nombre de trades par an.

Les ratios vont là où **l'effectif** les justifie. À la maille
magic × actif × branche, un groupe porte trois affaires : un PF sur
trois trades donne au bruit l'apparence d'une mesure. Ils vivent donc
dans la **synthèse par actif**, pas dans la table croisée.
