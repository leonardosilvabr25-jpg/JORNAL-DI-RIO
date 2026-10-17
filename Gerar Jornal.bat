@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "BASE=https://raw.githubusercontent.com/leonardosilvabr25-jpg/JORNAL-DI-RIO/main"
echo Atualizando o programa...
curl -sSfL "%BASE%/jornal.py" -o jornal_novo.py
if not errorlevel 1 move /y jornal_novo.py jornal.py >nul
if exist jornal_novo.py del jornal_novo.py
curl -sSfL "%BASE%/feeds.json" -o feeds_novo.json
if not errorlevel 1 move /y feeds_novo.json feeds.json >nul
if exist feeds_novo.json del feeds_novo.json
echo Instalando dependencias...
python -m pip install -q -r requirements.txt
echo Gerando o jornal...
python jornal.py --nicho todos --idioma pt en
start "" jornal.html
pause
