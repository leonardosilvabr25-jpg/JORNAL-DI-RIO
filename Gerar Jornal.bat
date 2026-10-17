@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Instalando dependencias...
python -m pip install -r requirements.txt
echo Gerando o jornal...
python jornal.py --nicho todos --idioma pt en
start "" jornal.html
pause
