@echo off
rem rotation_nuit.cmd -- appele par le planificateur, une fois par jour.
rem
rem Il ne COMPRIME que. Aucune suppression : elle demande deux drapeaux
rem explicites que cette tache ne passe pas.
rem
rem Le journal est ECRASE a chaque passage, pas complete. Une tache dont
rem le role est de liberer du disque ne doit pas laisser derriere elle
rem un fichier qui grossit sans fin. La derniere execution suffit : la
rem prochaine lecture de rotation_docs.py dit l etat reel.
cd /d "C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main"
set PY=C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe
if not exist "%PY%" set PY=python
"%PY%" rotation_docs.py --comprimer > docs\rotation.log 2>&1
