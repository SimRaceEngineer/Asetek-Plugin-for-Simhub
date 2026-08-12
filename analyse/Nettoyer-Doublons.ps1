# =====================================================================
#  Nettoyer-Doublons.ps1 -- un serveur par port, pas vingt-deux
#
#    .\Nettoyer-Doublons.ps1                inventaire seul
#    .\Nettoyer-Doublons.ps1 -Go            supprime les doublons
#    .\Nettoyer-Doublons.ps1 -Motif "x.py" -Port 8098
#
#  CE QU IL A TROUVE LE 12/08
#
#    orderflow_panel.py --port 8097 tournait en VINGT-DEUX exemplaires.
#    Un seul peut detenir le port ; les vingt et un autres occupent de la
#    memoire et des handles sans servir a rien.
#
#    Le mecanisme est annonce par le code lui-meme, price_action.py
#    ligne 5270 : « Lazy-load FOOTPRINT panel ». Chaque ouverture de
#    l onglet relance un serveur, qui echoue a prendre le port et reste.
#
#    C est un candidat serieux pour les episodes d irresponsivite du
#    VPS -- qui n auraient alors rien a voir avec son dimensionnement.
#
#  COMMENT IL CHOISIT LEQUEL GARDER
#
#    Celui qui DETIENT REELLEMENT LE PORT, via Get-NetTCPConnection. Pas
#    le plus ancien, pas le premier de la liste : celui qui rend le
#    service. Si personne ne detient le port, il garde le plus ancien et
#    le DIT, parce que ce choix-la est arbitraire.
#
#    Si le port n est pas connu (-Port 0), il garde le plus ancien, et
#    la aussi il le dit.
#
#  CE QU IL NE TOUCHE PAS
#
#    Tout ce qui ne correspond pas exactement au motif. Il affiche la
#    ligne de commande complete de chaque processus avant d agir, pour
#    qu on voie ce qui va etre tue.
#
#  VERIFIER LA CAUSE APRES COUP
#
#    Nettoie, ouvre l onglet FOOTPRINT dans la page 8095, relance
#    l inventaire. Si le compte remonte, la fuite est bien la : le
#    panneau relance un serveur a chaque ouverture, et c est le
#    chargement paresseux qu il faudra corriger, pas les processus.
# =====================================================================

param(
    [switch]$Go,
    [string]$Motif = "orderflow_panel.py",
    [int]$Port = 8097
)

function Lister($motif) {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$motif*" } |
        Select-Object ProcessId, CommandLine, CreationDate |
        Sort-Object CreationDate
}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " DOUBLONS : $Motif   port $Port" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan

$v = @(Lister $Motif)
if ($v.Count -eq 0) {
    Write-Host ""
    Write-Host "Aucun processus ne correspond a ce motif."
    exit 0
}

# ------------------------------------------- qui detient le port
$proprio = 0
$raison = ""
if ($Port -gt 0) {
    try {
        $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
             Select-Object -First 1
        if ($c) {
            $proprio = $c.OwningProcess
            $raison = "il detient le port $Port"
        }
    } catch { }
}
if ($proprio -eq 0) {
    $proprio = $v[0].ProcessId
    $raison = "CHOIX ARBITRAIRE : personne ne detient le port, on garde le plus ancien"
}

Write-Host ""
Write-Host ("{0} processus trouves." -f $v.Count) -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
foreach ($p in $v) {
    $marque = if ($p.ProcessId -eq $proprio) { "GARDE " } else { "doublon" }
    $coul = if ($p.ProcessId -eq $proprio) { "Green" } else { "Gray" }
    $cmd = $p.CommandLine
    if ($cmd.Length -gt 78) { $cmd = "..." + $cmd.Substring($cmd.Length - 75) }
    Write-Host ("  {0} {1,-7} {2,-20} {3}" -f $marque, $p.ProcessId,
                $p.CreationDate, $cmd) -ForegroundColor $coul
}
Write-Host "---------------------------------------------------------------------"
Write-Host ("  garde : {0} -- {1}" -f $proprio, $raison)

$doublons = @($v | Where-Object { $_.ProcessId -ne $proprio })
if ($doublons.Count -eq 0) {
    Write-Host ""
    Write-Host "Aucun doublon. Rien a faire." -ForegroundColor Green
    exit 0
}

if (-not $Go) {
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host (" {0} doublons a supprimer. Rien n a ete tue." -f $doublons.Count) -ForegroundColor Cyan
    Write-Host " Pour agir :  .\Nettoyer-Doublons.ps1 -Go" -ForegroundColor Cyan
    Write-Host "=====================================================================" -ForegroundColor Cyan
    exit 0
}

Write-Host ""
Write-Host "SUPPRESSION" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
$ok = 0
foreach ($p in $doublons) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Write-Host ("  pid {0} supprime" -f $p.ProcessId)
        $ok++
    } catch {
        Write-Host ("  pid {0} NON supprime : {1}" -f $p.ProcessId,
                    $_.Exception.Message) -ForegroundColor Red
    }
}

Start-Sleep -Seconds 2
$reste = @(Lister $Motif)
Write-Host "---------------------------------------------------------------------"
Write-Host ("  {0} supprimes, {1} restant(s)." -f $ok, $reste.Count)
if ($Port -gt 0) {
    try {
        $r = Invoke-WebRequest -Uri ("http://localhost:" + $Port) -TimeoutSec 8 -UseBasicParsing
        Write-Host ("  port {0} repond toujours ({1} octets)." -f $Port,
                    $r.RawContentLength) -ForegroundColor Green
    } catch {
        Write-Host ("  port {0} NE REPOND PLUS. Relance le service." -f $Port) -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " MAINTENANT VERIFIE LA CAUSE : ouvre l onglet FOOTPRINT dans la" -ForegroundColor Cyan
Write-Host " page 8095, puis relance cet inventaire. Si le compte remonte," -ForegroundColor Cyan
Write-Host " c est le chargement paresseux du panneau qu il faut corriger," -ForegroundColor Cyan
Write-Host " pas les processus -- les tuer ne ferait que repousser." -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
