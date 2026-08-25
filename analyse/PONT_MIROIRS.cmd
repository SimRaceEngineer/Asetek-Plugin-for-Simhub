@echo off
setlocal
REM ====================================================================
REM  PONT_MIROIRS.cmd -- lance les DEUX processus du pont, ensemble.
REM
REM  Le pont copie les miroirs paper du compte du moteur vers le compte
REM  demo dedie. Il lui faut deux processus, parce qu un processus
REM  Python ne peut etre connecte qu a UN terminal MT5 :
REM
REM     lecteur    lit les positions sur le terminal du moteur
REM     envoyeur   les reproduit sur le terminal dedie
REM
REM  Lancer l un sans l autre laisse la copie a moitie ouverte. Ce
REM  fichier existe pour que ce ne soit plus possible.
REM
REM     PONT_MIROIRS.cmd          simulation -- aucun ordre
REM     PONT_MIROIRS.cmd reel     les ordres partent
REM ====================================================================

set "PROJ=C:\SVPS\Scalp-EA-main"
set "COMPTE=182109"
set "MODE="
set "ETIQUETTE=SIMULATION -- aucun ordre ne partira"

if /I "%~1"=="reel" (
  set "MODE=--reel"
  set "ETIQUETTE=REEL -- les ordres partiront sur le compte %COMPTE%"
)

echo.
echo ====================================================================
echo   PONT MIROIRS   %ETIQUETTE%
echo ====================================================================
echo.

cd /d "%PROJ%" || (echo Dossier introuvable : %PROJ% & pause & exit /b 1)

if not exist "%PROJ%\pont_miroirs.py" (
  echo pont_miroirs.py absent de %PROJ%
  echo Le copier depuis G:\Mon Drive\ScalpEA\ avant de relancer.
  pause
  exit /b 1
)

where python >nul 2>&1 || (echo python introuvable dans le PATH. & pause & exit /b 1)

if defined MODE (
  echo   Des ordres REELS vont partir sur le compte %COMPTE%.
  echo   Le compte du moteur n est jamais touche : le lecteur ne fait
  echo   que lire, l envoyeur ne voit pas ce compte.
  echo.
  echo   Ctrl+C maintenant pour renoncer.
  echo.
  pause
)

echo   1/2  lecteur   -- terminal du moteur, LECTURE SEULE
start "PONT lecteur" cmd /k "cd /d "%PROJ%" && python pont_miroirs.py --lecteur"

REM Laisser au lecteur le temps de joindre son terminal. L envoyeur
REM sait attendre le premier instantane, ce delai n est qu une
REM politesse pour que les deux fenetres s ouvrent dans l ordre.
timeout /t 3 /nobreak >nul

echo   2/2  envoyeur  -- compte dedie %COMPTE%
start "PONT envoyeur" cmd /k "cd /d "%PROJ%" && python pont_miroirs.py --envoyeur --compte %COMPTE% %MODE%"

echo.
echo   Deux fenetres ouvertes. Les laisser ouvertes.
echo   Pour arreter le pont : fermer les deux, ou Ctrl+C dans chacune.
echo.
timeout /t 6 /nobreak >nul
endlocal
