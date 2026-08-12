# =====================================================================
#  Gardien-Stack.ps1 -- tout tourne, tout le temps, sans doublon
#
#    .\Gardien-Stack.ps1                une passe : relance ce qui manque
#    .\Gardien-Stack.ps1 -Constat       une passe SANS rien lancer
#    .\Gardien-Stack.ps1 -Boucle        boucle toutes les 60 s
#    .\Gardien-Stack.ps1 -Installer     tache planifiee, toutes les 5 min
#    .\Gardien-Stack.ps1 -Desinstaller  retire la tache
#
#  LE PRINCIPE, ET IL TIENT EN UNE PHRASE
#
#    Une passe compte les instances de chaque service et ramene ce
#    compte a UN : zero -> on lance, une -> on ne touche a rien, plus
#    d une -> on supprime les surnumeraires.
#
#    C est cette derniere branche qui manquait. Le 12/08,
#    orderflow_panel.py tournait en VINGT-DEUX exemplaires : un
#    demarrage qui ne verifie pas d abord finit toujours ainsi.
#
#  POURQUOI UNE PASSE ET NON UNE BOUCLE, PAR DEFAUT
#
#    Un gardien qui boucle doit lui-meme etre garde : s il meurt, plus
#    personne ne surveille, et rien ne le dit. En tache planifiee toutes
#    les cinq minutes, c est Windows qui garantit la cadence -- il n y a
#    plus de processus a babysitter.
#
#  COMMENT L ARRETER SANS LE DESINSTALLER
#
#    Cree un fichier nomme gardien.pause a cote de ce script. Tant qu il
#    existe, le gardien constate et ne lance rien. Supprime-le pour
#    reprendre. Sans ca, arreter un service a la main serait vain : la
#    passe suivante le relancerait.
#
#  CE QU IL NE FERA JAMAIS
#
#    Toucher a un processus qui ne correspond a aucun motif de la liste.
#    Pas de Stop-Process -Name python : cette commande tuerait les
#    traders. terminal64.exe n est jamais approche.
#
#  LA LISTE EST A COMPLETER
#
#    Elle ne contient que ce que je connais. Lance -Constat : il affiche
#    tous les python en cours et compte ceux qu il ne gere pas. Ce qui
#    doit etre garde, ajoute-le a $SERVICES -- une ligne par service.
# =====================================================================

param(
    [switch]$Constat,
    [switch]$Boucle,
    [switch]$Installer,
    [switch]$Desinstaller,
    [int]$Secondes = 60
)

$STACK   = "C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main"
$MOI     = $MyInvocation.MyCommand.Path
$PAUSE   = Join-Path (Split-Path $MOI) "gardien.pause"
$JOURNAL = Join-Path $STACK "logs\gardien.log"
$TACHE   = "Gardien-Stack"

# ---------------------------------------------------------------------
#  Motif  : ce qui reconnait le processus dans sa ligne de commande.
#  Port   : 0 si le service n en ecoute aucun.
#  Combien: nombre d instances voulu. 1 partout, et c est le point.
# ---------------------------------------------------------------------
$SERVICES = @(
    @{ Nom = "8095";        Motif = "price_action.py";   Script = "price_action.py";   Args = "";              Port = 8095 },
    @{ Nom = "orderflow";   Motif = "orderflow_panel.py"; Script = "orderflow_panel.py"; Args = "--port 8097"; Port = 8097 },
    @{ Nom = "panels_auto"; Motif = "panels_auto.py";    Script = "panels_auto.py";    Args = "--dest panels"; Port = 0 },
    @{ Nom = "sarkeep_m1";  Motif = "sarkeep_gel.py";    Script = "sarkeep_gel.py";    Args = "";              Port = 0 },
    @{ Nom = "sarkeep_m5";  Motif = "sarkeep_m5.py";     Script = "sarkeep_m5.py";     Args = "";              Port = 0 }
)

# ---------------------------------------------------------------------

function Noter($texte) {
    $ligne = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $texte
    Write-Host $ligne
    try {
        $d = Split-Path $JOURNAL
        if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
        Add-Content -Path $JOURNAL -Value $ligne -Encoding UTF8
    } catch { }
}

function Lister($motif) {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$motif*" } |
        Select-Object ProcessId, CommandLine, CreationDate |
        Sort-Object CreationDate
}

function Proprietaire($port) {
    if ($port -le 0) { return 0 }
    try {
        $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
             Select-Object -First 1
        if ($c) { return $c.OwningProcess }
    } catch { }
    return 0
}

# ------------------------------------------------------ installation
if ($Installer) {
    $cmd = "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$MOI`""
    Noter "installation de la tache planifiee '$TACHE'"
    schtasks /Create /TN $TACHE /TR $cmd /SC MINUTE /MO 5 /RL HIGHEST /F | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Noter "tache creee : une passe toutes les 5 minutes"
        Noter "elle demarre aussi a l ouverture de session"
        schtasks /Create /TN ($TACHE + "-Logon") /TR $cmd /SC ONLOGON /RL HIGHEST /F | Out-Null
        Write-Host ""
        Write-Host "Verifie :  schtasks /Query /TN $TACHE" -ForegroundColor Cyan
        Write-Host "Journal :  $JOURNAL" -ForegroundColor Cyan
        Write-Host "Pause   :  cree le fichier $PAUSE" -ForegroundColor Cyan
    } else {
        Noter "ECHEC de la creation -- lance PowerShell en administrateur"
    }
    exit 0
}

if ($Desinstaller) {
    schtasks /Delete /TN $TACHE /F | Out-Null
    schtasks /Delete /TN ($TACHE + "-Logon") /F | Out-Null
    Noter "taches planifiees supprimees"
    exit 0
}

# ------------------------------------------------------------- passe
function Passe {
    if (Test-Path $PAUSE) {
        Noter "PAUSE : le fichier gardien.pause existe, rien n est lance"
        return
    }
    if (-not (Test-Path $STACK)) {
        Noter "KO : dossier de la stack introuvable -- $STACK"
        return
    }

    foreach ($s in $SERVICES) {
        $v = @(Lister $s.Motif)

        if ($v.Count -eq 1) { continue }

        if ($v.Count -eq 0) {
            $chemin = Join-Path $STACK $s.Script
            if (-not (Test-Path $chemin)) {
                Noter ("{0} : script absent, {1}" -f $s.Nom, $chemin)
                continue
            }
            if ($Constat) {
                Noter ("{0} : ARRETE (constat, rien lance)" -f $s.Nom)
                continue
            }
            $argus = $s.Script
            if ($s.Args -ne "") { $argus = $s.Script + " " + $s.Args }
            try {
                Start-Process -FilePath "python" -ArgumentList $argus `
                              -WorkingDirectory $STACK -WindowStyle Minimized
                Noter ("{0} : relance -- python {1}" -f $s.Nom, $argus)
            } catch {
                Noter ("{0} : ECHEC de relance -- {1}" -f $s.Nom, $_.Exception.Message)
            }
            continue
        }

        # Plus d une instance : on ramene a une seule.
        $garde = Proprietaire $s.Port
        $pourquoi = "detient le port " + $s.Port
        if ($garde -eq 0 -or -not ($v.ProcessId -contains $garde)) {
            $garde = $v[0].ProcessId
            $pourquoi = "le plus ancien (aucun ne detient le port)"
        }
        $trop = @($v | Where-Object { $_.ProcessId -ne $garde })
        if ($Constat) {
            Noter ("{0} : {1} instances, on garderait {2} ({3})" -f `
                   $s.Nom, $v.Count, $garde, $pourquoi)
            continue
        }
        Noter ("{0} : {1} instances -- on garde {2} ({3}), on supprime {4}" -f `
               $s.Nom, $v.Count, $garde, $pourquoi, $trop.Count)
        foreach ($p in $trop) {
            try {
                Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            } catch {
                Noter ("  pid {0} non supprime : {1}" -f $p.ProcessId, $_.Exception.Message)
            }
        }
    }
}

# ------------------------------------------------------------- etat
if ($Constat) {
    $tous = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'")
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host (" {0} processus python en cours" -f $tous.Count) -ForegroundColor Cyan
    Write-Host "=====================================================================" -ForegroundColor Cyan
    foreach ($s in $SERVICES) {
        $v = @(Lister $s.Motif)
        $etat = switch ($v.Count) {
            0       { "ARRETE" }
            1       { "en cours (" + $v[0].ProcessId + ")" }
            default { ("{0} INSTANCES -- doublons" -f $v.Count) }
        }
        Write-Host ("  {0,-14} {1,-24} {2}" -f $s.Nom, $s.Script, $etat)
    }
    $geres = 0
    foreach ($p in $tous) {
        foreach ($s in $SERVICES) {
            if ($p.CommandLine -and $p.CommandLine -like ("*" + $s.Motif + "*")) {
                $geres++
                break
            }
        }
    }
    Write-Host ""
    Write-Host ("  {0} geres par ce gardien, {1} hors de sa liste." -f `
                $geres, ($tous.Count - $geres)) -ForegroundColor Yellow
    Write-Host "  Ceux hors liste ne sont ni lances ni arretes -- c est voulu."
    Write-Host "  Ce qui doit etre garde s ajoute a la liste SERVICES."
    Write-Host ""
}

if ($Boucle) {
    Noter "boucle demarree, une passe toutes les $Secondes s -- Ctrl+C pour arreter"
    while ($true) {
        Passe
        Start-Sleep -Seconds $Secondes
    }
} else {
    Passe
}
