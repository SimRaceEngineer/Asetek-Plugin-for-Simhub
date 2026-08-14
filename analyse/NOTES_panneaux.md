# Comment on ajoute un panneau au 8095

Écrit le 14/08/2026, après avoir livré une route sans bouton et perdu
un aller-retour à la redécouvrir. **Un panneau = une route + un
bouton.** L'un sans l'autre ne vaut rien : la route sans bouton est
introuvable, le bouton sans route affiche une erreur.

Tout ce qui suit est relevé dans `price_action.py`, pas supposé.

---

## Les deux sortes de boutons, et laquelle choisir

La barre compte **178 boutons**, tous de la forme `<div class="tab">`.
Ils se répartissent en deux familles très inégales :

```
177   onclick="showTab('id')"                        onglet interne
  1   onclick="window.open('/route','_blank')"       route servie
```

**`showTab('id')` — 177 cas.** Le contenu est **déjà dans la page**,
dans un bloc caché que `showTab` révèle. C'est le cas normal d'un
panneau de texte régénéré à chaque chargement.

```html
<div class="tab" onclick="showTab('railstr')" style="color:#3fb950;font-weight:bold;">RAILS TRADES</div>
<div class="tab" onclick="showTab('x60onset')" style="color:#3fb950;font-weight:bold;">X60 ONSET</div>
```

**`window.open('/route','_blank')` — 1 cas, `RAILS CYCLE`.** Le
contenu est servi par une route dédiée et s'ouvre dans un onglet du
navigateur.

```html
<div class="tab" onclick="window.open('/rails_cycle','_blank')" style="color:#58a6ff;font-weight:bold;">RAILS CYCLE</div>
```

### La règle de choix

**Le tableau de bord se recharge tout seul** — `setTimeout(() =>
location.reload(), 5000)`. Cinq secondes.

C'est ce qui décide, et non le goût :

- **Contenu figé au chargement** (texte, tableau, panneau régénéré
  ailleurs) → `showTab`. Le rechargement le rafraîchit, c'est même
  l'intérêt.
- **Contenu avec lequel on interagit** — menus, sélecteurs, état
  local, page lourde → `window.open` vers une route. Sur un onglet
  interne, chaque sélection serait balayée cinq secondes plus tard, et
  le poids de la page s'ajouterait à *chaque* rechargement du tableau
  de bord.

`cartes/panel_profils.html` pèse 383 425 octets et porte quatre menus :
c'est une route, sans hésitation.

---

## Les couleurs : il n'y a pas de convention

Relevé sur les 178 boutons : **une soixantaine de teintes distinctes**,
dont la majorité n'apparaît qu'une fois. Il n'existe donc **aucun code
couleur à respecter** — ne pas en inventer un après coup, et ne pas
recolorer l'existant.

Ce qui domine en tête est la palette GitHub dark, et c'est là qu'il
faut puiser pour rester cohérent :

```
17   #3fb950   vert
10   #7ee787   vert clair
 9   #79c0ff   bleu clair
 9   #a371f7   violet
 9   #d29922   ambre
 8   #e3b341   jaune
 7   #58a6ff   bleu          <- le bouton de route (RAILS CYCLE)
 7   #ffd700   or
 6   #f0883e   orange
 5   #d2a8ff   violet clair
```

La queue (`#ff66cc`, `#33ff99`, `#00ffcc`, `#ff3366`…) a été ajoutée au
fil de l'eau. Quatre boutons n'ont aucune couleur.

**Par défaut, pour un bouton de route : `#58a6ff`** — c'est celle du
seul précédent.

Le reste du style est identique partout : `font-weight:bold;`, classe
`tab`, aucun autre attribut. La police vient de la page
(`Consolas, monospace`), on n'en spécifie pas.

---

## La recette complète, dans l'ordre

### 1. Le générateur — hors ligne, jamais dans le fil HTTP

Un script qui lit et écrit un fichier. Il ne tourne **pas** dans le
serveur : recalculer quoi que ce soit dans le fil HTTP pendant que les
traders tournent, c'est offrir une latence au pire moment.

```
python carte_html.py        ->  cartes/panel_profils.html
```

### 2. La route — elle relit le fichier, elle ne le fabrique pas

Dans `_do_GET_impl` de `price_action.py`, cascade de
`if parsed.path == "...":`, **indentation à 12 espaces**, chaque route
finissant par son `return` :

```python
            if parsed.path == "/profils":
                try:
                    with open("cartes/panel_profils.html", "rb") as _h:
                        body = _h.read()
                except Exception as _e:
                    body = ("<html>… page lisible qui dit quoi lancer …"
                            "</html>" % _e).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
```

Trois points qui ne sont pas négociables :

- **Que des builtins** — `open`, `Exception`, `str`, `len`. Aucun `os`,
  aucun `io`. Le 14/08 à 21:18, un patch a fait tomber la page en
  écrivant `_os.environ` après avoir « vérifié » que `os` était
  importé : le contrôle utilisait `ast.walk`, qui descend dans les
  fonctions, et avait pris un import local pour un import de module.
- **Chemin en barres obliques** — `cartes/panel_profils.html`. Python
  les accepte sous Windows, et une barre inverse dans une chaîne non
  brute est une source d'échappement parasite.
- **Si le fichier manque, répondre 200 avec une page qui dit quoi
  lancer.** Jamais une trace de pile, jamais un 500 muet. Le panneau ne
  doit pas tomber parce qu'une carte n'a pas été générée.

Conséquence utile : la route relisant le fichier à chaque requête,
**régénérer suffit à rafraîchir**. Le redémarrage n'est nécessaire
qu'une fois, pour que la route existe.

### 3. Le bouton — sinon le panneau n'existe pas

Une ligne, dans la barre, sur le modèle du seul bouton de route :

```html
<div class="tab" onclick="window.open('/profils','_blank')" style="color:#58a6ff;font-weight:bold;">PROFILS</div>
```

### 4. Le redémarrage

Route et bouton ne prennent effet qu'au prochain démarrage de
`price_action.py`. **Jamais à la main sans `PA_ROLE=panel`** : sans
elle, `_run_trading` est vrai et de vrais ordres partent.

Arrêter **par pid**, jamais `Stop-Process -Name python` — ça tuerait
les traders.

**Et ne pas relancer.** Le panneau a un superviseur sur cette machine :
il le redémarre tout seul dans les secondes qui suivent l'arrêt. La
procédure est donc en deux temps, pas en trois :

1. arrêter par pid ;
2. attendre que le port 8095 réapparaisse, et vérifier que le **pid a
   changé**.

Constaté trois fois le 14/08, dont une où la course a été perdue à la
seconde près : arrêt de 11752 à 23:23:03, ports libres à 23:23:05,
lancement manuel démarré dans la foulée — et à 23:23:06 il sortait sur
`[PA-PANEL] port-token 18095 deja tenu -> EXIT (anti multi-bind)`,
parce que le superviseur avait déjà repris la main entre les deux.

18095 est ce jeton anti multi-bind. Il est tenu par le même processus
que 8095 ; c'est lui qui empêche deux panneaux de se disputer le port,
et c'est lui qui fait sortir toute relance manuelle arrivée trop tard.

Un lancement manuel n'est légitime que si le port **ne revient pas**.
Et alors, jamais sans `PA_ROLE=panel` sur la même ligne.

---

## Ce qu'il ne faut pas refaire

- Livrer la route sans le bouton. Fait le 14/08 : le panneau était
  servi, invisible, et il a fallu un aller-retour pour s'en rendre
  compte.
- Inventer un code couleur. Il n'y en a pas.
- Mettre une page interactive en onglet interne. Le rechargement à
  cinq secondes l'efface.
- Faire calculer le serveur. Le générateur tourne hors ligne.
