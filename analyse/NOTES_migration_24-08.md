# Migration du VPS vers msitrident2 -- 24/08/2026

## Ce qui a change

La stack ne tourne plus sur le VPS Contabo (VMI654074, eteint a 17h15).
Elle tourne sur **msitrident2**, dans `C:\SVPS\Scalp-EA-main`, sur le
compte demo **178780**, solde 15 179,12 EUR au demarrage.

PC1 et PC2 sont desormais la meme machine : le DATA_NODE du port 8200
(`C:\data_node\data_node.py`) et le moteur cohabitent.

## Ce qui a ete deplace, et verifie

| quoi | ou | verification |
|---|---|---|
| code | `C:\SVPS\Scalp-EA-main` | 2 910 fichiers, 452,17 Mo, comptage independant |
| etat `docs` | idem | 984 fichiers, 880,28 Mo, ECHEC 0 |
| archive `docs` (buddha, lifecycle, gate_blocks) | **reste sur le VPS** | 7,76 Go |
| `logs` | **reste sur le VPS** | 2,9 Go |
| Abaure | **reste sur le VPS et le Drive** | 94,9 Go |

Le disque du VPS persiste machine eteinte : rien n est perdu, tout est
recuperable en le rallumant.

## Les six pannes trouvees, et leur cause

**1. Les papers ne prenaient plus rien depuis 10h53.**
La tache `ScalpEA papers` etait bloquee en `Running` avec
`Last Result 0x800710E0`. Une instance de `papers_boucle.cmd` figee vers
10h58 refusait tous les declenchements suivants. `ExecutionTimeLimit`
etait a **72 heures** : rien ne l aurait tuee. Corrige par
`schtasks /end`, puis par une tache recreee avec une limite de 4 minutes
sur msitrident2 -- une passe normale dure 5 secondes.

Le `>nul 2>&1` de `papers_boucle.cmd` n a pas cause la panne mais l a
**cachee** six heures. Toujours a retirer.

**2. La derniere prise du 21/08 a 18:58 n etait pas une panne.**
La fenetre des papers est 14:00-19:00 ; 18:58 un vendredi, c est la fin
normale. J avais conclu trop vite.

**3. Le miroir mort depuis le 21/08 a 20:39.**
Il n a jamais figure dans `demarrage_quotidien.cmd`. `START_TRADING_STACK_V3.bat`
tue tous les python a son etape 1, la relance ne remonte que quatre
observateurs, et le miroir n en fait pas partie. Il mourait donc a chaque
20:05 sans revenir. Point identifie depuis des semaines, mesure ce jour.

**4. Le moteur refusait de demarrer sur msitrident2.**
Deux installations MetaTrader coexistent :

    ...\TF Global Markets MetaTrader 5 Terminal\             -> 176309
    ...\TF Global Markets MetaTrader 5 Termina-LOCALSTACKl\  -> 178780

Le nom du second est `Terminal` avec `-LOCALSTACK` insere **au milieu du
mot** : une corruption de presse-papiers lors d un renommage. Le moteur
ciblait le premier en dur, voyait `#176309`, et s arretait :

    !!! WRONG ACCOUNT #176309 -- expected Think #178780 !!!

**Ce garde-fou a parfaitement fonctionne.** Aucun ordre n est parti sur le
mauvais compte. Corrige par `repointe_mt5.py`, qui repointe tous les
chemins vers l installation `-LOCALSTACKl`. Pas de renommage de dossier :
MetaTrader indexe ses donnees par empreinte du chemin, et renommer aurait
perdu le login enregistre de 178780.

**5. Le miroir mourait des que le gardien le lancait.**
Erreur de ma part : `DETACHED_PROCESS` ne cree aucune console, et un
module qui ecrit sur la sortie standard meurt aussitot dans un descripteur
invalide. Sans laisser de trace, puisqu il n avait nulle part ou l ecrire.
Corrige : la sortie part dans `logs\<nom>_gardien.log`.

**6. L hibernation est interdite sur cette machine.**
`powercfg /h on` echoue : le service Guardian (securite par
virtualisation) la desactive. `powercfg /a` confirme que **S3 reste
disponible**. Le gardien utilise donc `SetSuspendState` plutot que
`shutdown /h`. On ne desarme pas Credential Guard pour economiser du
courant.

## Le gardien

`gardien_stack.py` est le point d entree unique. Il ne lance QUE ce qui
manque, donc rejouable sans creer de doublons -- contrairement a un `.bat`
qui relance tout aveuglement. Il couvre le moteur, les quatre
observateurs et le miroir.

Fenetre : **lundi 07:50 -> vendredi 20:00**. En dehors, il refuse d agir.

Quatre taches sur msitrident2 :

| tache | quand | quoi |
|---|---|---|
| `ScalpEA gardien matin` | lun-ven 07:50, `WakeToRun` | `--agir` |
| `ScalpEA gardien apresmidi` | lun-ven 14:20 | `--agir` |
| `ScalpEA gardien demarrage` | ouverture de session + 3 min | `--agir` |
| `ScalpEA weekend` | vendredi 20:00 | `--weekend --avec-veille` |

Le miroir est lance en **`--armer`** : il envoie de vrais ordres avec les
magics paper, seul moyen de mesurer latence, prix obtenu, spread et
slippage. Il ignore les trades deja ouverts (`entree passee`) : pas de
rattrapage retroactif.

## Ce qui reste

**Bloquant pour l autonomie reelle**
- BIOS : *Restore on AC Power Loss* = **Power On**.
- `netplwiz` : connexion automatique. MetaTrader exige une session de
  bureau ; sans elle, un redemarrage s arrete sur l ecran de mot de passe.
- Tester le reveil S3 **avant vendredi** : la tache de 07:50 sortira-t-elle
  vraiment la machine de veille ?

**Securite**
- Un mot de passe d application Gmail en clair dans les dernieres lignes
  de `START_TRADING_STACK_V3.bat` (apres le `exit`, jamais execute).
  A revoquer, a supprimer du fichier, et retirer la copie deposee sur le
  Drive dans `ScalpEA`.

**Propre**
- `SyntaxWarning: invalid escape sequence '\<'`, gardien ligne 162.
- `papers_boucle.cmd` : retirer `>nul 2>&1`.
- Le `echo` de `START_TRADING_STACK_V3.bat` casse sur le `&` de "P&L".
- Deux taches preexistantes non identifiees sur msitrident2 :
  `LLM-PaperScalp-MS2` et `LLM-PaperScalp-Report`.

**Arrete, et deja arrete sur le VPS -- donc pas une regression**
- `sarkeep_gel.py`, `sarkeep_m5.py`, `data_node_sync.py`.
  `docs\pc2\` est pourtant rafraichi : le miroir des JSON se fait
  ailleurs, probablement dans un fil du moteur. A confirmer.

**Sans urgence**
- Rapatrier l archive `docs`/`logs` (11,4 Go) et Abaure (94,9 Go) du VPS.
- Decider du sort du VPS : le garder eteint, ou resilier.
