# patch_gardien_panneau.ps1 -- ajoute panel_quadruple comme 8e service
#
#   .\patch_gardien_panneau.ps1 -Essai
#   .\patch_gardien_panneau.ps1
#
# CE QUE CA FAIT
#
#   Une ligne de plus dans le tableau $SERVICES du gardien :
#
#     @{ Nom = "quadruple"; Motif = "panel_quadruple.py";
#        Script = "panel_quadruple.py"; Args = "--boucle 5"; Port = 0 }
#
#   Port = 0 parce qu il n ecoute rien -- c est la convention du
#   fichier, ecrite a la ligne "Port : 0 si le service n en ecoute
#   aucun."
#
# POURQUOI --boucle ET PAS UN LANCEMENT SEC
#
#   Le gardien verifie qu un processus est VIVANT et le relance sinon.
#   Un generateur de rapport sort immediatement : il serait relance a
#   chaque passe et le journal se remplirait d une ligne toutes les
#   cinq minutes. Avec --boucle 5 il reste en vie et se regenere
#   lui-meme, comme papier_tf et x60_onset avec leur --loop.
#
# POURQUOI L ANCRE N EST PAS ECRITE EN DUR
#
#   Ma copie du gardien fait 14634 octets, celle du VPS 14255 : elles
#   ont diverge, et les numeros de ligne ne correspondent pas. Une
#   ancre recopiee de ma version echouerait -- ou pire, reussirait au
#   mauvais endroit.
#
#   Le patch cherche donc la ligne du service x60_onset par motif,
#   exige qu elle soit UNIQUE, et RECOPIE SON INDENTATION pour la
#   nouvelle ligne. Il ne suppose rien sur l espacement du fichier.
#
#   x60_onset est choisi comme point d insertion parce que sa ligne se
#   termine par une virgule : rien a rajouter ni a enlever ailleurs.
#   Inserer en fin de tableau demanderait de toucher la virgule de
#   l element precedent, donc deux modifications au lieu d une.
#
# CE QUI EST VERIFIE AVANT D ECRIRE -- rien n est ecrit si un seul
# controle echoue
#
#   1. le fichier existe et se lit
#   2. panel_quadruple.py est present a cote (sinon le gardien
#      relancerait un script absent en boucle, toutes les 5 minutes)
#   3. panel_quadruple.py connait --boucle (sinon il sortirait aussitot
#      et le gardien le relancerait sans fin)
#   4. idempotence : deja patche -> on sort sans rien faire
#   5. l ancre est presente UNE SEULE fois
#   6. le resultat PARSE en PowerShell -- l equivalent de ast.parse
#   7. le tableau compte exactement un service de plus
#   8. les sept services d origine sont tous encore la, par leur nom
#
#   Sauvegarde horodatee avant ecriture.
#
# PREND EFFET A LA PASSE SUIVANTE DU GARDIEN. Aucun processus n est
# arrete, aucun ordre n est envoye : ce patch ne touche qu un tableau
# de configuration.

[CmdletBinding()]
param(
    [string]$Fichier = "",
    [int]$Minutes = 5,
    [switch]$Essai
)

$ErrorActionPreference = "Stop"

function KO($m) { Write-Host "KO : $m" ; Write-Host "Rien n a ete ecrit." }

# --- localiser le gardien ------------------------------------------
if (-not $Fichier) {
    $c = Get-ChildItem . -Filter "Gardien-Stack.ps1" -ErrorAction SilentlyContinue |
         Select-Object -First 1
    if (-not $c) {
        $c = Get-ChildItem C:\Users\Administrator\Downloads -Recurse `
                -Filter "Gardien-Stack.ps1" -ErrorAction SilentlyContinue |
             Select-Object -First 1
    }
    if (-not $c) { KO "Gardien-Stack.ps1 introuvable" ; exit 1 }
    $Fichier = $c.FullName
}
if (-not (Test-Path $Fichier)) { KO "$Fichier introuvable" ; exit 1 }

$src = Get-Content $Fichier -Raw -Encoding UTF8
$lignes = $src -split "`r?`n"
Write-Host ("{0} : {1} lignes, {2} octets" -f $Fichier, $lignes.Count,
            (Get-Item $Fichier).Length)

# --- 2 et 3 : le script cible doit exister ET connaitre --boucle ----
$dossier = Split-Path $Fichier
$cible = Join-Path $dossier "panel_quadruple.py"
if (-not (Test-Path $cible)) {
    KO "panel_quadruple.py absent de $dossier -- le gardien relancerait un script introuvable toutes les 5 minutes"
    exit 1
}
$py = Get-Content $cible -Raw -Encoding UTF8
if ($py -notmatch '--boucle') {
    KO "panel_quadruple.py ne connait pas --boucle : il sortirait aussitot et serait relance sans fin. Copier la version a jour d abord."
    exit 1
}
Write-Host "panel_quadruple.py present, et il connait --boucle."

# --- 4 : idempotence -----------------------------------------------
if ($src -match 'panel_quadruple') {
    Write-Host "Deja applique -- rien a faire."
    exit 0
}

# --- 5 : l ancre, unique -------------------------------------------
$idx = @()
for ($i = 0; $i -lt $lignes.Count; $i++) {
    if ($lignes[$i] -match '@\{\s*Nom\s*=\s*"x60_onset"') { $idx += $i }
}
if ($idx.Count -ne 1) {
    KO ("{0} ligne(s) de service x60_onset, il en faut exactement 1" -f $idx.Count)
    exit 1
}
$n = $idx[0]
$ancre = $lignes[$n]
if ($ancre -notmatch ',\s*$') {
    KO "la ligne x60_onset ne se termine pas par une virgule -- l insertion apres elle casserait le tableau"
    exit 1
}
$indent = ($ancre -replace '^(\s*).*$', '$1')
Write-Host ("ancre trouvee ligne {0}, indentation de {1} espaces."
            -f ($n + 1), $indent.Length)

# --- construction ---------------------------------------------------
$neuve = $indent + ('@{{ Nom = "quadruple";   Motif = "panel_quadruple.py"; ' +
                    'Script = "panel_quadruple.py"; Args = "--boucle {0}"; Port = 0 }},'
                    -f $Minutes)
$avant = $lignes[0..$n]
$apres = $lignes[($n + 1)..($lignes.Count - 1)]
$sortie = (($avant + $neuve + $apres) -join "`r`n")

# --- 6 : ca parse ? -------------------------------------------------
$err = $null
$tok = $null
[System.Management.Automation.Language.Parser]::ParseInput(
    $sortie, [ref]$tok, [ref]$err) | Out-Null
if ($err -and $err.Count -gt 0) {
    KO ("ne parse pas : {0}" -f $err[0].Message)
    exit 1
}
Write-Host "Le resultat parse."

# --- 7 et 8 : le tableau, et les sept d origine ---------------------
$avantN = ([regex]::Matches($src, 'Nom\s*=\s*"')).Count
$apresN = ([regex]::Matches($sortie, 'Nom\s*=\s*"')).Count
if ($apresN -ne $avantN + 1) {
    KO ("le tableau passe de {0} a {1} services, il en faut {2}"
        -f $avantN, $apresN, ($avantN + 1))
    exit 1
}
foreach ($s in @("8095", "orderflow", "panels_auto", "papier_tf",
                 "x60_onset", "raf_x60", "raf_of")) {
    if ($sortie -notmatch ('Nom\s*=\s*"' + [regex]::Escape($s) + '"')) {
        KO "le service $s a disparu"
        exit 1
    }
}
Write-Host ("Services : {0} avant, {1} apres. Les sept d origine sont intacts."
            -f $avantN, $apresN)

Write-Host ""
Write-Host "Ligne ajoutee :"
Write-Host $neuve
Write-Host ""
Write-Host "PREND EFFET A LA PASSE SUIVANTE DU GARDIEN."
Write-Host "Aucun processus arrete, aucun ordre envoye."

if ($Essai) {
    Write-Host ""
    Write-Host "-Essai : rien n a ete ecrit."
    exit 0
}

$sauve = "{0}.bak-{1}" -f $Fichier, (Get-Date -Format "yyyyMMdd-HHmmss")
Copy-Item $Fichier $sauve -Force
[System.IO.File]::WriteAllText($Fichier, $sortie,
    (New-Object System.Text.UTF8Encoding($false)))
Write-Host ""
Write-Host "Sauvegarde : $sauve"
Write-Host "Applique."
exit 0
