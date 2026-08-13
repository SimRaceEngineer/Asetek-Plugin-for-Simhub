@echo off
REM =====================================================================
REM  demarrage_quotidien.cmd -- relancer la stack ET les observateurs
REM
REM  Lance par la tache planifiee \TradingStack\DemarrageQuotidien,
REM  tous les jours a 20:05.
REM
REM  POURQUOI 20:05
REM
REM    trading_engine.py est lance avec --stop-hour 20 : il s arrete
REM    seul a 20:00, une demi-heure apres la mise a plat de seance.
REM    Rien ne le relancait -- la tache \TradingStack\FreshnessWatchdog
REM    decrite dans stack_watchdog.bat n existe pas, verifie le 13/08.
REM
REM    20:05 est HORS SEANCE. C est ce qui compte : au demarrage,
REM    _armed part vide, une ignition en cours se lit comme fraiche, et
REM    les 37 cellules pourraient ouvrir dans la meme seconde. La regle
REM    de session (08:00-19:30) l interdit a cette heure-la. Demarrer
REM    en seance, c est prendre ce risque en argent reel.
REM
REM  POURQUOI LES OBSERVATEURS SONT ICI
REM
REM    START_TRADING_STACK_V3.bat les TUE tous a son etape 0
REM    ("Previous windows killed"), alors qu aucun n ecoute de port et
REM    qu aucun n est dans ses listes. Constate le 13/08 : apres un
REM    redemarrage, papier_tf, x60_onset, rafraichir_x60 et panels_auto
REM    avaient disparu, et rien ne le signalait.
REM
REM    Sans eux, le moteur trade mais plus aucune mesure ne s ecrit --
REM    et c est la mesure qui decide de ce qu on gardera en septembre.
REM
REM  L INTERRUPTION, ET SA DUREE
REM
REM    Les observateurs sont coupes par V3 puis relances ici : environ
REM    deux minutes par jour, a 20:05, hors seance. C est le prix du
REM    redemarrage quotidien du moteur. Le journal papier et le journal
REM    x60 portent une VEILLE toutes les dix minutes : ce trou-la sera
REM    visible, et c est voulu -- une couverture qui ment est pire
REM    qu une couverture trouee.
REM
REM  CE QU IL N ARRETE JAMAIS
REM
REM    Rien, directement. Il ne tue aucun processus : c est V3 qui le
REM    fait, avec son garde-fou anti-double-moteur. Un Stop-Process a la
REM    main court-circuiterait ce garde-fou.
REM =====================================================================

set STACK=C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main
set PY=C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe
set JOURNAL=%STACK%\logs\demarrage_quotidien.log

cd /d "%STACK%"

echo. >> "%JOURNAL%"
echo ===== %date% %time% : demarrage quotidien ===== >> "%JOURNAL%"

REM --- 1. la stack, par son propre lanceur -----------------------------
REM  V3 porte trois mois de correctifs et son garde-fou single-instance.
REM  On ne reimplemente rien : on l appelle.
call "%STACK%\START_TRADING_STACK_V3.bat" >> "%JOURNAL%" 2>&1

REM --- 2. le temps que le moteur charge --------------------------------
timeout /t 45 /nobreak >nul

REM --- 3. les observateurs, que V3 vient de tuer -----------------------
REM  En fenetre cachee, sortie dans logs\. Une console qui vole le focus
REM  sur un VPS finit toujours par etre fermee par erreur.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p='%PY%'; foreach($a in @(@('-u','papier_tf.py','--loop'), @('-u','x60_onset.py','--loop'), @('-u','rafraichir_x60.py'), @('-u','panels_auto.py','--dest','panels'))) { Start-Process -WindowStyle Hidden -FilePath $p -ArgumentList $a -WorkingDirectory '%STACK%' }" >> "%JOURNAL%" 2>&1

timeout /t 8 /nobreak >nul

REM --- 4. dire ce qui tourne, plutot que de supposer -------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$m=Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" ^| Where-Object { $_.CommandLine -match 'trading_engine\.py' -and $_.CommandLine -notmatch 'stall_sniper' }; $o=Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" ^| Where-Object CommandLine -match 'papier_tf^|x60_onset^|rafraichir_x60^|panels_auto'; Write-Output ('moteur : ' + @($m).Count + ' instance(s)'); Write-Output ('observateurs : ' + @($o).Count + ' / 4'); foreach($x in $o){ Write-Output ('   ' + $x.ProcessId + '  ' + ($x.CommandLine -replace '.*python\.exe\" *','')) }; $hb=\"$env:APPDATA\MetaQuotes\Terminal\Common\Files\cross_index_gate.dat\"; if(Test-Path $hb){ Write-Output ('battement : ' + [int]((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds + ' s') } else { Write-Output 'battement : fichier absent' }" >> "%JOURNAL%" 2>&1

echo ===== %date% %time% : fin ===== >> "%JOURNAL%"
