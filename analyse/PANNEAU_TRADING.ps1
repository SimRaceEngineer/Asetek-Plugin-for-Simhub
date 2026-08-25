# =====================================================================
#  PANNEAU_TRADING.ps1 -- inventaire et redemarrage des processus qui
#                         TRADENT. Le complement de Redemarrer-Stack.ps1,
#                         qui refuse deliberement d y toucher.
#
#    .\PANNEAU_TRADING.ps1                 inventaire seul, ne touche a rien
#    .\PANNEAU_TRADING.ps1 -Go             arrete et relance, dans l ordre
#    .\PANNEAU_TRADING.ps1 -Go -Quoi pont  seulement celui-la
#    .\PANNEAU_TRADING.ps1 -Go -Moteur     y compris le moteur (lire plus bas)
#
#  POURQUOI CE SCRIPT EXISTE
#
#    Redemarrer-Stack.ps1 gere price_action, panels_auto et les deux
#    sarkeep. Il exclut le moteur, le miroir et le pont -- "un arret de
#    trop et ce sont des positions qui ne sont plus gerees". Et son
#    chemin pointe encore vers msitrident1.
#
#    Le 25/08 il a fallu redemarrer trois processus dans un ordre precis
#    pour que la journee de correctifs prenne effet. Le faire a la main
#    a coute deux erreurs : un pont lance deux fois, d ou dix positions
#    orphelines, et un miroir qu on a failli relancer sans le moteur.
#
#  L ORDRE N EST PAS UNE PREFERENCE
#
#    papers_exempt est LU par les modules de sortie, qui vivent dans le
#    MOTEUR. Relancer le miroir sans le moteur ferait sortir la branche 5
#    comme le miroir 2, et la comparaison entre les deux ne mesurerait
#    plus rien. Moteur d abord, miroir ensuite. Le script l impose.
#
#  RIEN N EST SUPERVISE POUR L INSTANT
#
#    Le 25/08 a 18:40, gardien_stack.py n etait PAS en cours -- son
#    journal etait fige a 14:20. La regle "un service supervise s arrete,
#    il ne se relance pas" ne s applique donc pas ici : ce script relance
#    lui-meme. Le jour ou le gardien tournera, il faudra revoir ca.
#
#  LE MOTEUR EST A PART, ET IL FAUT -Moteur POUR Y TOUCHER
#
#    Le gardien le demarre via START_TRADING_STACK_V3.bat, pas en direct.
#    Ce .bat pose probablement des variables d environnement, et son nom
#    laisse penser qu il lance TOUTE la stack -- le rejouer avec vingt
#    processus debout dupliquerait tout.
#
#    Ce script relance donc le moteur avec la ligne exacte relevee le
#    25/08, `python trading_engine.py --stop-hour 20`, et SEULEMENT si
#    on le lui demande. Si l environnement compte, ca se verra dans sa
#    fenetre, et la sauvegarde de son journal dira quoi.
#
#  CE QU IL NE FERA JAMAIS
#
#    terminal64.exe. Stop-Process -Name python. Et tout processus dont
#    la ligne de commande ne correspond a aucun motif de la liste.
# =====================================================================

param(
    [switch]$Go,
    [switch]$Moteur,
    [switch]$Force,
    [string]$Quoi = "",
    [int]$Attente = 4
)

$STACK = "C:\SVPS\Scalp-EA-main"

# ---------------------------------------------------------------------
#  LA LISTE. L ORDRE EST L ORDRE DE DEMARRAGE, et il compte.
#  Motif = ce qu on cherche dans la ligne de commande. Assez precis pour
#  ne rien attraper d autre : "pont_miroirs.py --lecteur" et non
#  "pont_miroirs.py", sinon les deux roles se confondent.
# ---------------------------------------------------------------------
$SERVICES = @(
    @{ Nom = "moteur";   Motif = "trading_engine.py";
       Args = "trading_engine.py --stop-hour 20";  Apart = $true },
    @{ Nom = "miroir";   Motif = "miroir_papers.py";
       Args = "-u miroir_papers.py --armer";       Apart = $false },
    @{ Nom = "lecteur";  Motif = "pont_miroirs.py --lecteur";
       Args = "pont_miroirs.py --lecteur";         Apart = $false },
    @{ Nom = "envoyeur"; Motif = "pont_miroirs.py --envoyeur";
       Args = "pont_miroirs.py --envoyeur --compte 182109 --reel";
       Apart = $false },
    @{ Nom = "gardien";  Motif = "gardien_stack.py";
       Args = "gardien_stack.py";                  Apart = $false }
)

function Lister-Python {
    Get-CimInstance Win32_Process `
        -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Select-Object ProcessId, CommandLine, CreationDate
}

function Trouver($motif) {
    Lister-Python | Where-Object { $_.CommandLine -and $_.CommandLine -like "*$motif*" }
}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " PANNEAU TRADING -- $STACK" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan

if (-not (Test-Path $STACK)) {
    Write-Host "KO : dossier de la stack introuvable." -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------- la fenetre
# Les papers travaillent de 14 h a 19 h. Relancer le miroir pendant la
# fenetre lui fait perdre ses parents : il repart d une page blanche et
# les positions deja ouvertes ne sont plus suivies par personne.
$h = (Get-Date).Hour
$enFenetre = ($h -ge 14 -and $h -lt 19)

Write-Host ""
Write-Host "ETAT" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
foreach ($s in $SERVICES) {
    $v = @(Trouver $s.Motif)
    if ($v.Count -eq 0) {
        Write-Host ("  {0,-9} ARRETE" -f $s.Nom) -ForegroundColor Red
    } else {
        foreach ($p in $v) {
            $age = [int]((Get-Date) - $p.CreationDate).TotalHours
            Write-Host ("  {0,-9} pid {1,-7} depuis {2:dd/MM HH:mm}  ({3} h)" `
                        -f $s.Nom, $p.ProcessId, $p.CreationDate, $age)
        }
        if ($v.Count -gt 1) {
            Write-Host ("             {0} EXEMPLAIRES -- un de trop" -f $v.Count) -ForegroundColor Red
        }
    }
}

$tous = @(Lister-Python)
$inconnus = @()
foreach ($p in $tous) {
    $connu = $false
    foreach ($s in $SERVICES) {
        if ($p.CommandLine -like ("*" + $s.Motif + "*")) { $connu = $true }
    }
    if (-not $connu) { $inconnus += $p }
}
Write-Host ""
Write-Host ("  {0} autre(s) processus python. Ni arretes ni relances -- c est voulu." -f $inconnus.Count)

if (-not $Go) {
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host " INVENTAIRE SEUL. Rien n a ete touche." -ForegroundColor Cyan
    Write-Host " Pour agir :  .\PANNEAU_TRADING.ps1 -Go" -ForegroundColor Cyan
    if ($enFenetre) {
        Write-Host " ATTENTION : il est ${h}h, les papers travaillent." -ForegroundColor Yellow
        Write-Host " Hors 14h-19h de preference, ou -Force." -ForegroundColor Yellow
    }
    Write-Host "=====================================================================" -ForegroundColor Cyan
    exit 0
}

if ($enFenetre -and -not $Force) {
    Write-Host ""
    Write-Host "REFUS : il est ${h}h, la fenetre des papers est ouverte." -ForegroundColor Red
    Write-Host "Relancer le miroir maintenant lui ferait perdre ses parents :"
    Write-Host "il repartirait d une page blanche et les positions deja"
    Write-Host "ouvertes ne seraient plus suivies par personne."
    Write-Host ""
    Write-Host "Si c est voulu malgre tout :  -Go -Force"
    exit 1
}

$cibles = $SERVICES | Where-Object { -not $_.Apart -or $Moteur }
if ($Quoi -ne "") {
    $cibles = $SERVICES | Where-Object { $_.Nom -eq $Quoi }
    if (-not $cibles) {
        Write-Host ""
        Write-Host "KO : aucun service nomme '$Quoi'." -ForegroundColor Red
        Write-Host ("Noms : " + (($SERVICES | ForEach-Object { $_.Nom }) -join ", "))
        exit 1
    }
}

if (-not $Moteur -and $Quoi -eq "") {
    Write-Host ""
    Write-Host "Le moteur n est PAS dans le lot -- il faut -Moteur." -ForegroundColor Yellow
    Write-Host "Rappel : papers_exempt est lu par les modules de sortie, qui"
    Write-Host "vivent dans le moteur. Relancer le miroir sans lui ferait"
    Write-Host "sortir la branche 5 comme le miroir 2."
}

$avant = @{}
foreach ($s in $cibles) {
    $avant[$s.Nom] = @(Trouver $s.Motif | ForEach-Object { $_.ProcessId })
}

Write-Host ""
Write-Host "ARRET" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
foreach ($s in $cibles) {
    $v = @(Trouver $s.Motif)
    if ($v.Count -eq 0) { Write-Host ("  {0,-9} deja arrete" -f $s.Nom) ; continue }
    foreach ($p in $v) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            Write-Host ("  {0,-9} pid {1} arrete" -f $s.Nom, $p.ProcessId)
        } catch {
            Write-Host ("  {0,-9} pid {1} NON arrete : {2}" `
                        -f $s.Nom, $p.ProcessId, $_.Exception.Message) -ForegroundColor Red
        }
    }
}

Start-Sleep -Seconds $Attente

Write-Host ""
Write-Host "DEMARRAGE, dans l ordre" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
foreach ($s in $cibles) {
    try {
        Start-Process -FilePath "python" -ArgumentList $s.Args `
                      -WorkingDirectory $STACK -WindowStyle Minimized
        Write-Host ("  {0,-9} lance : python {1}" -f $s.Nom, $s.Args)
    } catch {
        Write-Host ("  {0,-9} ECHEC : {1}" -f $s.Nom, $_.Exception.Message) -ForegroundColor Red
    }
    # Le moteur doit etre debout AVANT le miroir : les modules de sortie
    # qui lisent papers_exempt vivent chez lui.
    if ($s.Nom -eq "moteur") { Start-Sleep -Seconds 15 } else { Start-Sleep -Seconds 2 }
}

Write-Host ""
Write-Host "CONTROLE, dans $Attente secondes" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------------"
Start-Sleep -Seconds $Attente
$souci = 0
foreach ($s in $cibles) {
    $v = @(Trouver $s.Motif)
    if ($v.Count -eq 0) {
        Write-Host ("  {0,-9} PAS REPARTI -- regarde sa fenetre" -f $s.Nom) -ForegroundColor Red
        $souci++
        continue
    }
    $neufs = @($v | Where-Object { $avant[$s.Nom] -notcontains $_.ProcessId })
    if ($neufs.Count -eq 0) {
        Write-Host ("  {0,-9} MEME PID qu avant -- il n a pas redemarre" -f $s.Nom) -ForegroundColor Red
        $souci++
    } elseif ($v.Count -gt 1) {
        Write-Host ("  {0,-9} {1} EXEMPLAIRES ({2}) -- un de trop" `
                    -f $s.Nom, $v.Count, ($v.ProcessId -join ", ")) -ForegroundColor Red
        $souci++
    } else {
        Write-Host ("  {0,-9} pid {1}, neuf" -f $s.Nom, $neufs[0].ProcessId) -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
if ($souci -eq 0) {
    Write-Host " Tout est reparti, avec des pid neufs." -ForegroundColor Green
} else {
    Write-Host " $souci service(s) a regarder de pres." -ForegroundColor Red
}
Write-Host " A verifier ensuite dans les journaux :" -ForegroundColor Cyan
Write-Host "   sl_arbitre annonce BLOQUE et non OBSERVATION"
Write-Host "   le miroir ecrit des lignes M5xxxxxx CVD ok / CVD REFUSE"
Write-Host "=====================================================================" -ForegroundColor Cyan
