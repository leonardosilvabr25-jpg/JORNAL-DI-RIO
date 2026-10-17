@echo off
chcp 65001 >nul
title Jornal Diario
cd /d "%~dp0"
set "BASE=https://raw.githubusercontent.com/leonardosilvabr25-jpg/JORNAL-DI-RIO/main"
echo Atualizando o programa...
for %%F in (app.py jornal.py feeds.json index.html requirements.txt) do (
  curl -sSfL "%BASE%/%%F" -o "%%F.novo" && move /y "%%F.novo" "%%F" >nul
  if exist "%%F.novo" del "%%F.novo"
)
echo Instalando dependencias...
python -m pip install -q -r requirements.txt
echo Abrindo o painel. Para encerrar, feche esta janela.
python app.py
pause
