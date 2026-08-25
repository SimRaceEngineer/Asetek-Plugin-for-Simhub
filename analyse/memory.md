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
