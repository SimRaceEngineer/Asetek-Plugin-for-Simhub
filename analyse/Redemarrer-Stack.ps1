# =====================================================================
#  Redemarrer-Stack.ps1 -- relancer les processus d analyse de la stack
#
#    .\Redemarrer-Stack.ps1                 inventaire seul, ne touche a rien
#    .\Redemarrer-Stack.ps1 -Go             arrete et relance
#    .\Redemarrer-Stack.ps1 -Go -Quoi 8095  seulement celui-la
#
#  POURQUOI L INVENTAIRE EST LE DEFAUT
#
#    Ce script vit a cote d une stack qui TRADE. Un arret de trop et ce
#    sont des positions qui ne sont plus gerees. Il ne fait donc rien
#    tant qu on ne lui passe pas -Go, et il n arrete QUE les scripts
#    nommes dans $SERVICES ci-dessous.
#
#  CE QU IL NE TOUCHERA JAMAIS
#
#    terminal64.exe (MetaTrader), et tout processus python dont la ligne
#    de commande ne correspond a aucun script de la liste. Pas de
#    "Stop-Process -Name python" : cette commande tuerait les traders
#    avec le reste.
#
#  COMMENT COMPLETER LA LISTE
#
#    Lance-le une fois sans -Go. Il affiche TOUS les python en cours avec
#    leur ligne de commande complete. Ce qui manque dans $SERVICES, tu
#    l ajoutes : c est la seule partie a maintenir.
# =====================================================================

param(
    [switch]$Go,
    [string]$Quoi = "",
    [int]$Attente = 3
)

$STACK = "C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main"

# ---------------------------------------------------------------------
#  LA LISTE. Ordre = ordre de demarrage.
#  Motif = ce qu on cherche dans la ligne de commande pour reconnaitre
#  le processus. Il doit etre assez precis pour ne rien attraper d autre.
# ---------------------------------------------------------------------
$SERVICES = @(
    @{ Nom = "8095";        Motif = "price_action.py";  Script = "price_action.py";  Args = "";                    Port = 8095 },
    @{ Nom = "panels_auto"; Motif = "panels_auto.py";   Script = "panels_auto.py";   Args = "--dest panels";       Port = 0 },
    @{ Nom = "sarkeep_m1";  Motif = "sarkeep_gel.py";   Script = "sarkeep_gel.py";   Args = "";                    Port = 0 },
    @{ Nom = "sarkeep_m5";  Motif = "sarkeep_m5.py";    Script = "sarkeep_m5.py";    Args = "";                    Port = 0 }
)

# ---------------------------------------------------------------------

function Lister-Python {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Select-Object ProcessId, CommandLine
}

function Trouver($motif) {
    Lister-Python | Where-Object { $_.CommandLine -and $_.CommandLine -like "*$motif*" }
}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " STACK : $STACK" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan

if (-not (Test-Path $STACK)) {
    Write-Host "KO : le dossier de la stack est introuvable." -ForegroundColor Red
    Write-Host "Corrige la variable STACK en tete de ce fichier."
    exit 1
}

# --------------------------------------------------------- inventaire
Write-Host ""
Write-Host "TOUS LES PYTHON EN COURS" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
$tous = Lister-Python
if (-not $tous) {
    Write-Host "  aucun."
} else {
    foreach ($p in $tous) {
        $cmd = $p.CommandLine
        if ($cmd.Length -gt 110) { $cmd = $cmd.Substring(0, 110) + "..." }
        Write-Host ("  {0,-8} {1}" -f $p.ProcessId, $cmd)
    }
}

Write-Host ""
Write-Host "CE QUE CE SCRIPT SAIT GERER" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
foreach ($s in $SERVICES) {
    $v = @(Trouver $s.Motif)
    $etat = if ($v.Count -eq 0) { "arrete" } else { "en cours (" + ($v.ProcessId -join ", ") + ")" }
    Write-Host ("  {0,-14} {1,-24} {2}" -f $s.Nom, $s.Script, $etat)
}

$inconnus = @()
foreach ($p in $tous) {
    $connu = $false
    foreach ($s in $SERVICES) {
        if ($p.CommandLine -like ("*" + $s.Motif + "*")) { $connu = $true }
    }
    if (-not $connu) { $inconnus += $p }
}
if ($inconnus.Count -gt 0) {
    Write-Host ""
    Write-Host ("  {0} processus python NON GERES par ce script." -f $inconnus.Count) -ForegroundColor Yellow
    Write-Host "  Ils ne seront ni arretes ni relances -- c est voulu."
    Write-Host "  Si l un d eux doit l etre, ajoute-le a la liste SERVICES."
}

if (-not $Go) {
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host " INVENTAIRE SEUL. Rien n a ete arrete." -ForegroundColor Cyan
    Write-Host " Pour agir :  .\Redemarrer-Stack.ps1 -Go" -ForegroundColor Cyan
    Write-Host "=====================================================================" -ForegroundColor Cyan
    exit 0
}

# ------------------------------------------------------------- action
$cibles = $SERVICES
if ($Quoi -ne "") {
    $cibles = $SERVICES | Where-Object { $_.Nom -eq $Quoi }
    if (-not $cibles) {
        Write-Host ""
        Write-Host "KO : aucun service nomme '$Quoi'." -ForegroundColor Red
        Write-Host ("Noms possibles : " + (($SERVICES | ForEach-Object { $_.Nom }) -join ", "))
        exit 1
    }
}

Write-Host ""
Write-Host "ARRET" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
foreach ($s in $cibles) {
    $v = @(Trouver $s.Motif)
    if ($v.Count -eq 0) {
        Write-Host ("  {0,-14} deja arrete" -f $s.Nom)
        continue
    }
    foreach ($p in $v) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            Write-Host ("  {0,-14} pid {1} arrete" -f $s.Nom, $p.ProcessId)
        } catch {
            Write-Host ("  {0,-14} pid {1} NON arrete : {2}" -f $s.Nom, $p.ProcessId, $_.Exception.Message) -ForegroundColor Red
        }
    }
}

Start-Sleep -Seconds $Attente

Write-Host ""
Write-Host "DEMARRAGE" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
foreach ($s in $cibles) {
    $chemin = Join-Path $STACK $s.Script
    if (-not (Test-Path $chemin)) {
        Write-Host ("  {0,-14} SCRIPT ABSENT : {1}" -f $s.Nom, $chemin) -ForegroundColor Red
        continue
    }
    $argus = $s.Script
    if ($s.Args -ne "") { $argus = $s.Script + " " + $s.Args }
    try {
        Start-Process -FilePath "python" -ArgumentList $argus `
                      -WorkingDirectory $STACK -WindowStyle Minimized
        Write-Host ("  {0,-14} lance : python {1}" -f $s.Nom, $argus)
    } catch {
        Write-Host ("  {0,-14} ECHEC : {1}" -f $s.Nom, $_.Exception.Message) -ForegroundColor Red
    }
    Start-Sleep -Seconds 1
}

# ---------------------------------------------------------- controle
Write-Host ""
Write-Host "CONTROLE, dans $Attente secondes" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
Start-Sleep -Seconds $Attente
foreach ($s in $cibles) {
    $v = @(Trouver $s.Motif)
    if ($v.Count -eq 0) {
        Write-Host ("  {0,-14} PAS REPARTI -- regarde sa fenetre" -f $s.Nom) -ForegroundColor Red
        continue
    }
    $msg = "en cours (" + ($v.ProcessId -join ", ") + ")"
    if ($s.Port -gt 0) {
        try {
            $r = Invoke-WebRequest -Uri ("http://localhost:" + $s.Port) -TimeoutSec 8 -UseBasicParsing
            $msg += (" -- port {0} repond ({1} octets)" -f $s.Port, $r.RawContentLength)
        } catch {
            $msg += (" -- port {0} NE REPOND PAS ENCORE" -f $s.Port)
        }
    }
    Write-Host ("  {0,-14} {1}" -f $s.Nom, $msg)
}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " Termine. Un port qui ne repond pas tout de suite n est pas un" -ForegroundColor Cyan
Write-Host " echec : le 8095 charge ses documents au demarrage. Relance" -ForegroundColor Cyan
Write-Host " l inventaire dans une minute pour confirmer." -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
