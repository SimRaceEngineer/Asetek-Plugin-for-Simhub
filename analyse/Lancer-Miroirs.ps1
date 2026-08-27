# =====================================================================
#  Lancer-Miroirs.ps1 -- les cinq processus des miroirs, ensemble,
#                        et la preuve qu ils PRODUISENT.
#
#    .\Lancer-Miroirs.ps1              etat seul, ne touche a rien
#    .\Lancer-Miroirs.ps1 -Go          demarre ce qui manque, verifie
#    .\Lancer-Miroirs.ps1 -Tout        arrete tout et relance, verifie
#    .\Lancer-Miroirs.ps1 -Go -Quoi miroir      un seul service
#
#  POURQUOI IL EXISTE
#
#    27/08 : le miroir etait mort depuis 09:17 et personne ne l a su
#    avant 14:53. Quatre fois dans la matinee la reponse "il tourne" a
#    ete donnee sur la seule foi de sa presence dans la liste des
#    processus. Une heure et vingt-sept minutes de seance perdues.
#
#    Le meme matin, le pont tournait en DOUBLE -- deux envoyeurs en
#    --reel, nes a 09:36 et 09:39 -- parce qu un redemarrage n avait
#    pas commence par un inventaire.
#
#    Ce script repond aux deux. PRESENCE N EST PAS PRODUCTION : apres
#    chaque demarrage il compare la taille du journal avant et apres, et
#    ne declare OK que si elle a AUGMENTE. Un processus vivant mais muet
#    est signale MUET, pas OK.
#
#  CE QU IL NE TOUCHERA JAMAIS
#
#    terminal64.exe, trading_engine.py, les panneaux, et tout python
#    dont la ligne de commande ne correspond a aucun motif ci-dessous.
#    Pas de "Stop-Process -Name python" : cette commande tuerait les
#    traders avec le reste.
#
#  CE QU IL NE FAIT PAS
#
#    Il ne reessaie pas. Un service MUET est nomme et laisse en l etat :
#    reparer un flux dont on n a pas identifie la panne, c est ce qui
#    fabrique les pannes suivantes. On lit son journal d erreur, on
#    comprend, puis on relance.
# =====================================================================

param(
    [switch]$Go,
    [switch]$Tout,
    [string]$Quoi = "",
    [int]$Attente = 25,
    [int]$SilenceMax = 180
)

$PROJ = "C:\SVPS\Scalp-EA-main"

# ---------------------------------------------------------------------
#  LA LISTE. L ordre est l ordre de demarrage, et il compte : le
#  lecteur du pont doit etre debout avant l envoyeur, sans quoi
#  l envoyeur ouvre sur un instantane vide.
#  'pause' = secondes a attendre APRES avoir lance celui-la.
# ---------------------------------------------------------------------
$SERVICES = @(
  @{ nom = "miroir"
     motif = "miroir_papers\.py"
     args  = @("-u", "miroir_papers.py", "--armer")
     log   = "logs\miroir_sortie.txt"
     err   = "logs\miroir_erreur.txt"
     pause = 5 },

  @{ nom = "pont-lecteur"
     motif = "pont_miroirs\.py.*--lecteur"
     args  = @("-u", "pont_miroirs.py", "--lecteur")
     log   = "logs\pont_lect_sortie.txt"
     err   = "logs\pont_lect_erreur.txt"
     pause = 12 },

  @{ nom = "pont-envoyeur"
     motif = "pont_miroirs\.py.*--envoyeur"
     args  = @("-u", "pont_miroirs.py", "--envoyeur", "--compte", "182109", "--reel")
     log   = "logs\pont_env_sortie.txt"
     err   = "logs\pont_env_erreur.txt"
     pause = 5 },

  @{ nom = "trail6"
     motif = "trail_miroir6\.py"
     args  = @("-u", "trail_miroir6.py", "--reel")
     log   = "logs\trail6_sortie.txt"
     err   = "logs\trail6_erreur.txt"
     log2  = "logs\trail_miroir6.log"
     pause = 3 },

  @{ nom = "gardien"
     motif = "gardien_stops\.py"
     args  = @("-u", "gardien_stops.py", "--reel")
     log   = "logs\gardien_sortie.txt"
     err   = "logs\gardien_erreur.txt"
     log2  = "logs\gardien_stops.log"
     pause = 3 }
)

function Instances($motif) {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
      Where-Object { $_.CommandLine -match $motif }
}

function TailleLog($chemin) {
    $p = Join-Path $PROJ $chemin
    if (Test-Path $p) { return (Get-Item $p).Length }
    return -1
}

function AgeLog($chemin) {
    if ($chemin -eq $null -or $chemin -eq "") { return $null }
    $p = Join-Path $PROJ $chemin
    if (-not (Test-Path $p)) { return $null }
    return [int]((Get-Date) - (Get-Item $p).LastWriteTime).TotalSeconds
}

function AgeService($s) {
    # Un service peut ecrire a DEUX endroits : la sortie redirigee par ce
    # script, et son propre journal. Lance a la main dans une fenetre, il
    # n alimente que le second -- et le premier, fige, le ferait passer
    # pour muet. 27/08 16:19 : c est exactement le faux verdict que ce
    # script a rendu sur le gardien. On retient le plus recent des deux.
    $a = AgeLog $s.log
    $b = $null
    if ($s.ContainsKey("log2")) { $b = AgeLog $s.log2 }
    if ($a -eq $null) { return $b }
    if ($b -eq $null) { return $a }
    if ($a -lt $b) { return $a } else { return $b }
}

function DernieresErreurs($chemin) {
    $p = Join-Path $PROJ $chemin
    if (-not (Test-Path $p)) { return @() }
    if ((Get-Item $p).Length -eq 0) { return @() }
    return Get-Content $p -Tail 4
}

# ---------------------------------------------------------------------
#  ETAT -- ce que voit quelqu un qui n a rien lance
# ---------------------------------------------------------------------
function Etat {
    Write-Host ""
    Write-Host ("{0,-14} {1,-7} {2,-9} {3,-10} {4}" -f `
                "service", "pid", "ne a", "journal", "verdict")
    Write-Host ("-" * 62)
    $manquants = @()
    foreach ($s in $SERVICES) {
        $inst = @(Instances $s.motif)
        $age  = AgeService $s
        if ($inst.Count -eq 0) {
            Write-Host ("{0,-14} {1,-7} {2,-9} {3,-10} {4}" -f `
                        $s.nom, "-", "-", "-", "ABSENT")
            $manquants += $s.nom
        }
        elseif ($inst.Count -gt 1) {
            $pids = ($inst | ForEach-Object { $_.ProcessId }) -join ","
            Write-Host ("{0,-14} {1,-7} {2,-9} {3,-10} {4}" -f `
                        $s.nom, $pids, "-", "-",
                        ("EN DOUBLE -- " + $inst.Count + " instances"))
            $manquants += $s.nom
        }
        else {
            $p = $inst[0]
            $ne = $p.CreationDate.ToString("HH:mm:ss")
            $j  = if ($age -eq $null) { "aucun" } else { "$age s" }
            $v  = if ($age -eq $null) { "MUET -- pas de journal" }
                  elseif ($age -gt $SilenceMax) { "MUET depuis $age s" }
                  else { "ok" }
            Write-Host ("{0,-14} {1,-7} {2,-9} {3,-10} {4}" -f `
                        $s.nom, $p.ProcessId, $ne, $j, $v)
            if ($v -ne "ok") { $manquants += $s.nom }
        }
    }
    Write-Host ""
    if ($manquants.Count -eq 0) {
        Write-Host "  Les cinq sont debout et ecrivent."
    } else {
        Write-Host ("  A traiter : " + ($manquants -join ", "))
        Write-Host "  Relancez avec -Go (ou -Tout pour tout reprendre a zero)."
    }
    return $manquants
}

# ---------------------------------------------------------------------
#  ARRET -- uniquement les pid nommes, jamais par nom d image
# ---------------------------------------------------------------------
function Arrete($s) {
    $inst = @(Instances $s.motif)
    foreach ($p in $inst) {
        Write-Host ("    arret pid " + $p.ProcessId + " (" + $s.nom + ")")
        taskkill /PID $p.ProcessId /F | Out-Null
    }
    if ($inst.Count -gt 0) { Start-Sleep -Seconds 2 }
    return $inst.Count
}

# ---------------------------------------------------------------------
#  DEMARRAGE -- et la seule question qui compte : a-t-il ECRIT ?
# ---------------------------------------------------------------------
function Demarre($s) {
    $avant = TailleLog $s.log
    $out = Join-Path $PROJ $s.log
    $er  = Join-Path $PROJ $s.err
    $d = Split-Path $out -Parent
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }

    Start-Process -FilePath "python" -ArgumentList $s.args `
        -WorkingDirectory $PROJ `
        -RedirectStandardOutput $out -RedirectStandardError $er `
        -WindowStyle Minimized | Out-Null

    Start-Sleep -Seconds $s.pause
    return $avant
}

function Verifie($s, $avant) {
    $inst = @(Instances $s.motif)
    if ($inst.Count -eq 0) {
        Write-Host ("  {0,-14} MORT -- le processus n a pas survecu au demarrage" -f $s.nom)
        foreach ($l in (DernieresErreurs $s.err)) { Write-Host ("      | " + $l) }
        return $false
    }
    $apres = TailleLog $s.log
    if ($apres -gt $avant) {
        Write-Host ("  {0,-14} OK   pid {1}   journal {2} -> {3} octets" -f `
                    $s.nom, $inst[0].ProcessId, $avant, $apres)
        return $true
    }
    Write-Host ("  {0,-14} MUET pid {1}   journal inchange ({2} octets) apres {3} s" -f `
                $s.nom, $inst[0].ProcessId, $apres, $Attente)
    Write-Host    "                 present n est pas produire. Je ne relance pas :"
    Write-Host    "                 lisez son journal d erreur avant de reessayer."
    foreach ($l in (DernieresErreurs $s.err)) { Write-Host ("      | " + $l) }
    return $false
}

# ---------------------------------------------------------------------
#  MAIN
# ---------------------------------------------------------------------
if (-not (Test-Path $PROJ)) {
    Write-Host "ABANDON : $PROJ introuvable."
    exit 2
}
Set-Location $PROJ

Write-Host ""
Write-Host "======================================================================"
Write-Host "  LANCER-MIROIRS   $PROJ"
Write-Host "======================================================================"

$aFaire = @($SERVICES)
if ($Quoi -ne "") {
    $aFaire = @($SERVICES | Where-Object { $_.nom -eq $Quoi })
    if ($aFaire.Count -eq 0) {
        Write-Host ("ABANDON : service inconnu '" + $Quoi + "'. Connus : " +
                    (($SERVICES | ForEach-Object { $_.nom }) -join ", "))
        exit 2
    }
}

if (-not $Go -and -not $Tout) {
    Etat | Out-Null
    Write-Host ""
    Write-Host "  ETAT SEUL -- rien n a ete demarre ni arrete."
    exit 0
}

Write-Host ""
Write-Host "--- inventaire avant d agir ---"
$manquants = Etat

Write-Host ""
Write-Host "--- action ---"
$resultats = @()
foreach ($s in $aFaire) {
    $inst = @(Instances $s.motif)

    if ($Tout) {
        Arrete $s | Out-Null
    }
    elseif ($inst.Count -gt 1) {
        Write-Host ("  {0} : {1} instances, je les arrete toutes pour n en laisser qu une." -f `
                    $s.nom, $inst.Count)
        Arrete $s | Out-Null
    }
    elseif ($inst.Count -eq 1) {
        $age = AgeService $s
        if ($age -ne $null -and $age -le $SilenceMax) {
            Write-Host ("  {0,-14} deja debout et ecrit ({1} s) -- laisse tel quel" -f `
                        $s.nom, $age)
            $resultats += @{ nom = $s.nom; ok = $true }
            continue
        }
        Write-Host ("  {0} : present mais muet, je le reprends." -f $s.nom)
        Arrete $s | Out-Null
    }

    $avant = Demarre $s
    $resultats += @{ nom = $s.nom; ok = (Verifie $s $avant); attente = $true
                     avant = $avant }
}

# Un deuxieme regard, apres $Attente : certains n ecrivent leur premiere
# ligne qu au premier evenement de marche, pas au demarrage.
$aRevoir = @($resultats | Where-Object { -not $_.ok -and $_.attente })
if ($aRevoir.Count -gt 0) {
    Write-Host ""
    Write-Host ("--- second regard dans {0} s ---" -f $Attente)
    Start-Sleep -Seconds $Attente
    foreach ($r in $aRevoir) {
        $s = $SERVICES | Where-Object { $_.nom -eq $r.nom }
        # On repart de la taille relevee AVANT le demarrage, pas de zero :
        # sinon un journal deja rempli hier passerait pour une production
        # d aujourd hui. C est exactement l erreur que ce script existe
        # pour ne plus commettre.
        $r.ok = Verifie $s $r.avant
    }
}

Write-Host ""
Write-Host "--- etat final ---"
$restants = Etat
Write-Host ""
if ($restants.Count -eq 0) {
    Write-Host "  Les cinq produisent. Rien a faire a la main."
    exit 0
}
Write-Host ("  NON RESOLU : " + ($restants -join ", "))
Write-Host "  Je ne relance pas en boucle. Lisez le journal d erreur du service"
Write-Host "  nomme ci-dessus, puis .\Lancer-Miroirs.ps1 -Go -Quoi <nom>."
exit 1
