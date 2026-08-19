@echo off
rem papers_boucle.cmd -- appele par le planificateur, toutes les 5 min.
rem Il ne fait que se placer dans le dossier et lancer le wrapper Python,
rem qui porte le verrou et le journal.
cd /d "C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main"
set PY=C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe
if not exist "%PY%" set PY=python
"%PY%" papers_boucle.py >nul 2>&1
