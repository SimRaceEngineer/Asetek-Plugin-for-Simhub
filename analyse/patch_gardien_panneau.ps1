# patch_gardien_panneau.ps1 -- ajoute panel_quadruple comme 8e service
#
#   .\patch_gardien_panneau.ps1 -Essai
#   .\patch_gardien_panneau.ps1
#
# VERSION 2 -- la v1 ne parsait pas
#
#   En PowerShell, un operateur ne peut PAS commencer une ligne : `-f`
#   doit rester en fin de ligne precedente, meme entre parentheses.
#   La v1 contenait quatre expressions ecrites dans l autre sens et le
#   parseur les a toutes refusees.
#
#   Correction de fond plutot que de forme : plus AUCUNE expression
#   multi-lignes dans ce fichier. Tout tient sur une ligne, ou passe
#   par une variable intermediaire. C est plus verbeux et ca ne peut
#   plus tomber dans le meme piege.
#
#   L echec etait propre : le script est mort au parse, avant son
#   premier controle, donc le gardien n a pas ete touche.
#
# CE QUE CA FAIT
#
#   Une ligne de plus dans le tableau $SERVICES du gardien :
#
#     @{ Nom = "quadruple"; Motif = "panel_quadruple.py";
#        Script = "panel_quadruple.py"; Args = "--boucle 5"; Port = 0 }
#
#   Port = 0 parce qu il n ecoute rien : c est la convention du
#   fichier, ecrite dans son propre en-tete.
#
# POURQUOI --boucle ET PAS UN LANCEMENT SEC
#
#   Le gardien verifie qu un processus est VIVANT et le relance sinon.
#   Un generateur de rapport sort immediatement : il serait relance a
#   chaque passe et le journal se remplirait d une ligne toutes les
#   cinq minutes. Avec --boucle il reste en vie et se regenere
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
#   exige qu elle soit UNIQUE, et RECOPIE SON INDENTATION. Il ne
#   suppose rien sur l espacement du fichier.
#
#   x60_onset est le point d insertion parce que sa ligne se termine
#   par une virgule : rien a rajouter ni a enlever ailleurs. Inserer
#   en fin de tableau demanderait de toucher la virgule de l element
#   precedent, donc deux modifications au lieu d une.
#
# NEUF CONTROLES AVANT ECRITURE -- rien n est ecrit si un seul echoue
#
#   1. le gardien existe et se lit
#   2. panel_quadruple.py est present a cote
#   3. panel_quadruple.py connait --boucle
#   4. idempotence : deja patche -> on sort
#   5. l ancre est presente UNE SEULE fois
#   6. l ancre se termine par une virgule
#   7. le resultat PARSE -- Parser::ParseInput, l equivalent d ast.parse
#   8. le tableau compte exactement un service de plus
#   9. les sept services d origine sont tous la, par leur nom
#
#   Sauvegarde horodatee avant ecriture.
#
# PREND EFFET A LA PASSE SUIVANTE DU GARDIEN. Aucun processus arrete,
# aucun ordre envoye : ce patch ne touche qu un tableau de config.

[CmdletBinding()]
param(
    [string]$Fichier = "",
    [int]$Minutes = 5,
    [switch]$Essai
)

$ErrorActionPreference = "Stop"

function KO($m) {
    Write-Host "KO : $m"
    Write-Host "Rien n a ete ecrit."
}

# --- localiser le gardien ------------------------------------------
if (-not $Fichier) {
    $c = Get-ChildItem . -Filter "Gardien-Stack.ps1" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $c) {
        $racine = "C:\Users\Administrator\Downloads"
        $c = Get-ChildItem $racine -Recurse -Filter "Gardien-Stack.ps1" -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if (-not $c) { KO "Gardien-Stack.ps1 introuvable" ; exit 1 }
    $Fichier = $c.FullName
}
if (-not (Test-Path $Fichier)) { KO "$Fichier introuvable" ; exit 1 }

$src = Get-Content $Fichier -Raw -Encoding UTF8
$lignes = $src -split "`r?`n"
$octets = (Get-Item $Fichier).Length
Write-Host "$Fichier"
Write-Host "  $($lignes.Count) lignes, $octets octets"

# --- 2 et 3 : le script cible ---------------------------------------
$dossier = Split-Path $Fichier
$cible = Join-Path $dossier "panel_quadruple.py"
if (-not (Test-Path $cible)) {
    KO "panel_quadruple.py absent de $dossier -- le gardien relancerait un script introuvable toutes les 5 minutes"
    exit 1
}
$py = Get-Content $cible -Raw -Encoding UTF8
if ($py -notmatch '--boucle') {
    KO "panel_quadruple.py ne connait pas --boucle : il sortirait aussitot et serait relance sans fin. Appliquer patch_panel_boucle.py d abord."
    exit 1
}
Write-Host "  panel_quadruple.py present, et il connait --boucle."

# --- 4 : idempotence -------------------------------------------------
if ($src -match 'panel_quadruple') {
    Write-Host "Deja applique -- rien a faire."
    exit 0
}

# --- 5 et 6 : l ancre -------------------------------------------------
$idx = @()
for ($i = 0; $i -lt $lignes.Count; $i++) {
    if ($lignes[$i] -match '@\{\s*Nom\s*=\s*"x60_onset"') { $idx += $i }
}
if ($idx.Count -ne 1) {
    KO "$($idx.Count) ligne(s) de service x60_onset, il en faut exactement 1"
    exit 1
}
$n = $idx[0]
$ancre = $lignes[$n]
if ($ancre -notmatch ',\s*$') {
    KO "la ligne x60_onset ne se termine pas par une virgule -- inserer apres elle casserait le tableau"
    exit 1
}
if ($n -ge ($lignes.Count - 1)) {
    KO "la ligne x60_onset est la derniere du fichier, ce qui est impossible pour un element de tableau suivi d une virgule"
    exit 1
}
$indent = ($ancre -replace '^(\s*).*$', '$1')
Write-Host "  ancre ligne $($n + 1), indentation de $($indent.Length) espaces."

# --- construction -----------------------------------------------------
$corps = '@{ Nom = "quadruple";   Motif = "panel_quadruple.py"; Script = "panel_quadruple.py"; Args = "--boucle ' + $Minutes + '"; Port = 0 },'
$neuve = $indent + $corps
$avant = $lignes[0..$n]
$apres = $lignes[($n + 1)..($lignes.Count - 1)]
$tout = $avant + $neuve + $apres
$sortie = $tout -join "`r`n"

# --- 7 : ca parse ? ---------------------------------------------------
$err = $null
$tok = $null
$null = [System.Management.Automation.Language.Parser]::ParseInput($sortie, [ref]$tok, [ref]$err)
if ($err -and $err.Count -gt 0) {
    KO "ne parse pas : $($err[0].Message)"
    exit 1
}
Write-Host "  le resultat parse."

# --- 8 et 9 : le tableau ----------------------------------------------
$avantN = ([regex]::Matches($src, 'Nom\s*=\s*"')).Count
$apresN = ([regex]::Matches($sortie, 'Nom\s*=\s*"')).Count
$attendu = $avantN + 1
if ($apresN -ne $attendu) {
    KO "le tableau passe de $avantN a $apresN services, il en faut $attendu"
    exit 1
}
$origine = @("8095", "orderflow", "panels_auto", "papier_tf", "x60_onset", "raf_x60", "raf_of")
foreach ($s in $origine) {
    $motif = 'Nom\s*=\s*"' + [regex]::Escape($s) + '"'
    if ($sortie -notmatch $motif) {
        KO "le service $s a disparu"
        exit 1
    }
}
Write-Host "  services : $avantN avant, $apresN apres. Les sept d origine sont intacts."

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

$horo = Get-Date -Format "yyyyMMdd-HHmmss"
$sauve = "$Fichier.bak-$horo"
Copy-Item $Fichier $sauve -Force
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($Fichier, $sortie, $utf8)
Write-Host ""
Write-Host "Sauvegarde : $sauve"
Write-Host "Applique."
exit 0
