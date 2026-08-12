# =====================================================================
#  Superviseur.ps1 -- un seul processus, aucune fenetre, surveillance active
#
#    .\Superviseur.ps1 -Etat        ce qui tourne, ce qui manque. N AGIT PAS.
#    .\Superviseur.ps1 -Arreter     arrete tout ce qu il gere
#    .\Superviseur.ps1 -Go          arrete, relance tout, puis surveille
#    .\Superviseur.ps1 -Go -Une     une seule passe, pas de boucle
#    .\Superviseur.ps1 -Installer   tache planifiee au logon, cachee
#
#  CE QU IL REMPLACE, ET RIEN D AUTRE
#
#    Les CINQ fenetres wrapper lancees par START_TRADING_STACK_V3.bat :
#    run_panel_loop, run_monitor_loop, run_latent_loop,
#    run_orderflow_loop, run_jauge_loop. Plus panels_auto et les deux
#    sarkeep, qui n etaient dans aucun .bat -- c est pour ca qu ils
#    etaient a l arret.
#
#    Il NE touche PAS a trading_engine.py, ni aux terminaux MT5, ni au
#    nettoyage des .dat et du __pycache__. Tout cela reste le travail du
#    V3, qui porte trois mois de correctifs qu on ne rejoue pas de tete.
#
#  POURQUOI PLUS AUCUNE FENETRE
#
#    Chaque service est lance en -WindowStyle Hidden, sa sortie ecrite
#    dans logs\<nom>.log. Le superviseur lui-meme tourne cache s il est
#    lance par la tache planifiee. Zero console qui vole le focus, zero
#    fenetre a fermer par erreur, et les logs restent lisibles apres coup
#    -- ce qu une fenetre fermee ne permet pas.
#
#  CE QU IL SURVEILLE, TOUTES LES 20 SECONDES
#
#    Nombre d instances de chaque service : 0 -> relance, 1 -> rien,
#    plus d une -> il supprime les surnumeraires en gardant celui qui
#    detient le port. C est cette derniere branche qui manquait partout,
#    et c est elle qui a laisse orderflow_panel monter a 23 exemplaires.
#
#    La sante : les ports 8095 / 8097 / 8081 repondent-ils, et le
#    heartbeat cross_index_gate.dat du MOTEUR est-il frais. Le moteur
#    n est pas gere ici -- s il est fige, le superviseur le DIT dans son
#    journal, il ne le relance pas. C est le role du V3 et de
#    stack_watchdog, qui savent aussi tuer les zombies eleves.
#
#  LES REDEMARRAGES NORMAUX NE SONT PAS DES PANNES
#
#    price_action.py en role panneau se termine SEUL toutes les ~40
#    minutes (PA_RESTART_SEC) pour repartir frais : c est voulu, et le
#    superviseur le relance sans le signaler comme incident. jauge_h1
#    fait un passage puis sort ; on attend 1800 s avant de le relancer,
#    exactement comme son wrapper.
#
#  PA_ROLE, ET POURQUOI C EST LA LIGNE LA PLUS IMPORTANTE DU FICHIER
#
#    price_action.py lit PA_ROLE. En 'panel' il sert le 8095 et
#    n envoie AUCUN ordre. Sans cette variable, il demarre en role
#    moteur, avec ses boucles de trading. Un superviseur qui l oublie
#    ouvre des positions. La variable est posee juste avant le
#    lancement, et retiree juste apres.
#
#  ROLLBACK
#
#    Ce fichier ne modifie rien. Pour revenir en arriere : -Arreter,
#    puis relance START_TRADING_STACK_V3.bat comme avant.
# =====================================================================

param(
    [switch]$Etat,
    [switch]$Arreter,
    [switch]$Go,
    [switch]$Une,
    [switch]$Installer,
    [switch]$Desinstaller,
    [int]$Secondes = 20
)

$STACK  = "C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main"
$MOI    = $MyInvocation.MyCommand.Path
$LOGS   = Join-Path $STACK "logs"
$JOURNAL = Join-Path $LOGS "superviseur.log"
$VERROU = Join-Path $LOGS "superviseur.verrou"
$TACHE  = "TradingStack\Superviseur"

$PY314 = "C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if (-not (Test-Path $PY314)) { $PY314 = "python" }

# Heartbeat du MOTEUR. On le lit, on ne le repare pas.
$COEUR = Join-Path $env:APPDATA "MetaQuotes\Terminal\Common\Files\cross_index_gate.dat"

# ---------------------------------------------------------------------
#  Attente = secondes avant relance apres une sortie. 2 s pour un
#  daemon, 1800 s pour jauge_h1 qui fait un passage puis sort.
#  Normal = $true quand la sortie du process est voulue (pas un
#  incident) : le journal ne crie pas.
# ---------------------------------------------------------------------
$SERVICES = @(
    @{ Nom="panel";       Script="price_action.py";    Args="";                Env="panel"; Attente=2;    Port=8095; Normal=$true  },
    @{ Nom="monitor";     Script="trade_monitor.py";   Args="--stop-hour 23";  Env="";      Attente=3;    Port=8081; Normal=$false },
    @{ Nom="orderflow";   Script="orderflow_panel.py"; Args="";                Env="";      Attente=2;    Port=8097; Normal=$false },
    @{ Nom="latent";      Script="latent_log.py";      Args="";                Env="";      Attente=5;    Port=0;    Normal=$false },
    @{ Nom="jauge";       Script="jauge_h1.py";        Args="";                Env="";      Attente=1800; Port=0;    Normal=$true  },
    @{ Nom="panels_auto"; Script="panels_auto.py";     Args="--dest panels";   Env="";      Attente=60;   Port=0;    Normal=$false },
    @{ Nom="sarkeep_m1";  Script="sarkeep_gel.py";     Args="";                Env="";      Attente=10;   Port=0;    Normal=$false },
    @{ Nom="sarkeep_m5";  Script="sarkeep_m5.py";      Args="";                Env="";      Attente=10;   Port=0;    Normal=$false }
)

# ---------------------------------------------------------------------

function Noter($texte) {
    if (-not (Test-Path $LOGS)) {
        New-Item -ItemType Directory -Path $LOGS -Force | Out-Null
    }
    $ligne = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $texte
    Write-Host $ligne
    try { Add-Content -Path $JOURNAL -Value $ligne -Encoding UTF8 } catch { }
}

function Lister($script) {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -like ("*" + $script + "*") } |
        Select-Object ProcessId, CreationDate |
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

function Repond($port) {
    if ($port -le 0) { return $null }
    try {
        $r = Invoke-WebRequest -Uri ("http://localhost:" + $port) -TimeoutSec 6 -UseBasicParsing
        return $r.RawContentLength
    } catch { return -1 }
}

function Demarrer($s) {
    $chemin = Join-Path $STACK $s.Script
    if (-not (Test-Path $chemin)) {
        Noter ("{0} : script absent -- {1}" -f $s.Nom, $chemin)
        return
    }
    $sortie = Join-Path $LOGS ($s.Nom + ".log")
    $erreur = Join-Path $LOGS ($s.Nom + ".err.log")

    # PA_ROLE : sans elle, price_action demarre en role MOTEUR et envoie
    # des ordres. Posee juste avant, retiree juste apres.
    if ($s.Env -ne "") { $env:PA_ROLE = $s.Env }
    $liste = @($chemin)
    if ($s.Args -ne "") { $liste += $s.Args.Split(" ") }
    try {
        Start-Process -FilePath $PY314 -ArgumentList $liste `
                      -WorkingDirectory $STACK -WindowStyle Hidden `
                      -RedirectStandardOutput $sortie `
                      -RedirectStandardError $erreur | Out-Null
        Noter ("{0} : lance (cache) -- {1} {2}" -f $s.Nom, $s.Script, $s.Args)
    } catch {
        Noter ("{0} : ECHEC -- {1}" -f $s.Nom, $_.Exception.Message)
    }
    if ($s.Env -ne "") { Remove-Item Env:\PA_ROLE -ErrorAction SilentlyContinue }
}

function Arreter-Tout {
    foreach ($s in $SERVICES) {
        $v = @(Lister $s.Script)
        foreach ($p in $v) {
            try {
                Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
                Noter ("{0} : pid {1} arrete" -f $s.Nom, $p.ProcessId)
            } catch {
                Noter ("{0} : pid {1} non arrete -- {2}" -f $s.Nom, $p.ProcessId, $_.Exception.Message)
            }
        }
    }
    # Les fenetres wrapper de l ancien systeme, si elles trainent encore.
    foreach ($t in @("Price Action Panel*", "Trade Monitor*", "Orderflow Panel*",
                     "Latent Log*", "Jauge H1*",
                     "Administrateur*Price Action Panel*",
                     "Administrateur*Trade Monitor*",
                     "Administrateur*Orderflow Panel*",
                     "Administrateur*Latent Log*",
                     "Administrateur*Jauge H1*")) {
        cmd /c "taskkill /F /T /FI ""WINDOWTITLE eq $t"" >nul 2>&1"
    }
    Noter "fenetres wrapper de l ancien systeme fermees"
}

# ------------------------------------------------------------ une passe
$script:Repos = @{}

function Passe {
    foreach ($s in $SERVICES) {
        $v = @(Lister $s.Script)

        if ($v.Count -eq 1) { continue }

        if ($v.Count -gt 1) {
            # QUI GARDER, ET POURQUOI CE N EST PAS CELUI QUE WINDOWS DIT.
            #
            # Sous Windows, HTTPServer met allow_reuse_address a 1 :
            # plusieurs process bindent le MEME port sans erreur, et c est
            # le DERNIER qui recoit le trafic. run_orderflow_loop.bat le
            # documente noir sur blanc.
            #
            # Get-NetTCPConnection, lui, retourne le PREMIER listener. S y
            # fier fait garder un dormant et tuer celui qui sert : le
            # 12/08 a 21h50, orderflow s est retrouve a une seule
            # instance et 8097 MUET. On garde donc le plus RECENT des
            # que le service porte un port.
            #
            # Sans port, on garde le plus ANCIEN : il est deja au travail,
            # et pour panels_auto le tuer en plein export tronquerait un
            # panneau.
            if ($s.Port -gt 0) {
                $garde = $v[$v.Count - 1].ProcessId
                $pourquoi = "le plus recent -- c est lui qui recoit le trafic"
                $declare = Proprietaire $s.Port
                if ($declare -ne 0 -and $declare -ne $garde) {
                    Noter ("{0} : Windows declare {1} proprietaire du port {2}," -f `
                           $s.Nom, $declare, $s.Port)
                    Noter "  on garde quand meme le plus recent (SO_REUSEADDR)"
                }
            } else {
                $garde = $v[0].ProcessId
                $pourquoi = "le plus ancien -- il est deja au travail"
            }
            Noter ("{0} : {1} instances -- on garde {2} ({3})" -f `
                   $s.Nom, $v.Count, $garde, $pourquoi)
            foreach ($p in $v) {
                if ($p.ProcessId -ne $garde) {
                    try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch { }
                }
            }
            # On VERIFIE apres coup. Un port muet apres un menage est
            # exactement ce qu on vient de provoquer une fois.
            if ($s.Port -gt 0) {
                Start-Sleep -Seconds 2
                if ((Repond $s.Port) -lt 0) {
                    Noter ("{0} : port {1} MUET apres le menage -- on relance" -f `
                           $s.Nom, $s.Port)
                    try { Stop-Process -Id $garde -Force -ErrorAction Stop } catch { }
                    $script:Repos.Remove($s.Nom)
                }
            }
            continue
        }

        # Zero instance : respecter le delai propre au service.
        $t = $script:Repos[$s.Nom]
        if ($t -and ((Get-Date) - $t).TotalSeconds -lt $s.Attente) { continue }
        if (-not $s.Normal -and $t) {
            Noter ("{0} : tombe -- relance" -f $s.Nom)
        }
        $script:Repos[$s.Nom] = Get-Date
        Demarrer $s
    }
}

function Sante {
    $lignes = @()
    foreach ($s in $SERVICES) {
        if ($s.Port -le 0) { continue }
        $o = Repond $s.Port
        if ($o -lt 0) { $lignes += ("{0} MUET" -f $s.Port) }
    }
    $age = 99999
    if (Test-Path $COEUR) {
        $age = [int]((Get-Date) - (Get-Item $COEUR).LastWriteTime).TotalSeconds
    }
    if ($age -gt 120) {
        $lignes += ("moteur FIGE (cross_index_gate {0}s)" -f $age)
    }
    if ($lignes.Count -gt 0) {
        Noter ("SANTE : " + ($lignes -join " | "))
        Noter "  le moteur n est pas gere ici : si c est lui, c est V3 et"
        Noter "  stack_watchdog qui doivent le relancer, eux savent tuer"
        Noter "  les zombies eleves."
    }
}

# --------------------------------------------------------------- modes
if ($Installer) {
    $cmd = "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$MOI`" -Go"
    schtasks /Create /TN $TACHE /TR $cmd /SC ONLOGON /RL HIGHEST /F | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Noter "tache '$TACHE' creee -- demarre cache a l ouverture de session"
        Write-Host ""
        Write-Host "Journal : $JOURNAL" -ForegroundColor Cyan
        Write-Host "Etat    : .\Superviseur.ps1 -Etat" -ForegroundColor Cyan
    } else {
        Noter "ECHEC de la creation -- PowerShell en administrateur"
    }
    exit 0
}

if ($Desinstaller) {
    schtasks /Delete /TN $TACHE /F | Out-Null
    Noter "tache '$TACHE' supprimee"
    exit 0
}

if ($Etat) {
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host " ETAT -- rien n est lance ni arrete" -ForegroundColor Cyan
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host ("  {0,-14} {1,-24} {2,-22} {3}" -f "nom", "script", "etat", "port")
    Write-Host "  -----------------------------------------------------------------"
    foreach ($s in $SERVICES) {
        $v = @(Lister $s.Script)
        $libelle = switch ($v.Count) {
            0       { "ARRETE" }
            1       { "en cours (" + $v[0].ProcessId + ")" }
            default { ("{0} INSTANCES" -f $v.Count) }
        }
        $p = ""
        if ($s.Port -gt 0) {
            $o = Repond $s.Port
            if ($o -lt 0) { $p = "{0} MUET" -f $s.Port }
            else { $p = "{0} OK ({1} o)" -f $s.Port, $o }
        }
        Write-Host ("  {0,-14} {1,-24} {2,-22} {3}" -f $s.Nom, $s.Script, $libelle, $p)
    }
    $age = 99999
    if (Test-Path $COEUR) {
        $age = [int]((Get-Date) - (Get-Item $COEUR).LastWriteTime).TotalSeconds
    }
    Write-Host ""
    Write-Host ("  moteur (non gere ici) : cross_index_gate.dat {0}s" -f $age)
    if ($age -gt 120) {
        Write-Host "  -> FIGE. C est le V3 / stack_watchdog qui le relancent." -ForegroundColor Red
    }
    Write-Host ""
    exit 0
}

if ($Arreter) {
    Arreter-Tout
    exit 0
}

if (-not $Go) {
    Write-Host ""
    Write-Host " Rien n a ete fait. Choisis :" -ForegroundColor Cyan
    Write-Host "   -Etat       voir sans toucher"
    Write-Host "   -Go         arreter, relancer, surveiller"
    Write-Host "   -Go -Une    une seule passe"
    Write-Host "   -Arreter    tout arreter"
    Write-Host "   -Installer  tache planifiee au logon, cachee"
    Write-Host ""
    exit 0
}

# ------------------------------------------------------------- marche
# Un seul superviseur a la fois. Deux passes concurrentes lanceraient
# deux fois le meme service -- c est arrive le 12/08 a 21h34.
if (Test-Path $VERROU) {
    $age = [int]((Get-Date) - (Get-Item $VERROU).LastWriteTime).TotalSeconds
    if ($age -lt 120) {
        Noter "un superviseur tourne deja (verrou de $age s) -- on s arrete"
        exit 0
    }
}
if (-not (Test-Path $LOGS)) { New-Item -ItemType Directory -Path $LOGS -Force | Out-Null }
"pid $PID" | Set-Content -Path $VERROU -Encoding UTF8

Noter "=== superviseur demarre, tout en fenetres cachees ==="
Arreter-Tout
Start-Sleep -Seconds 3

try {
    $n = 0
    while ($true) {
        $n++
        Passe
        if ($n % 15 -eq 1) { Sante }
        "pid $PID  tour $n" | Set-Content -Path $VERROU -Encoding UTF8
        if ($Une) { break }
        Start-Sleep -Seconds $Secondes
    }
} finally {
    Remove-Item $VERROU -Force -ErrorAction SilentlyContinue
    Noter "=== superviseur arrete ==="
}
