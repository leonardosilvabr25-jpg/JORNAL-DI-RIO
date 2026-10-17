@echo off
chcp 65001 >nul
set "PASTA=%USERPROFILE%\JornalDiario"
if not exist "%PASTA%" mkdir "%PASTA%"
curl -sSfL https://raw.githubusercontent.com/leonardosilvabr25-jpg/JORNAL-DI-RIO/main/Jornal.bat -o "%PASTA%\Jornal.bat"
if errorlevel 1 (echo Nao consegui baixar o programa. Verifique a internet. & pause & exit /b 1)
curl -sSfL https://raw.githubusercontent.com/leonardosilvabr25-jpg/JORNAL-DI-RIO/main/jornal.ico -o "%PASTA%\jornal.ico"
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Jornal Diario.lnk'); $s.TargetPath='%PASTA%\Jornal.bat'; $s.WorkingDirectory='%PASTA%'; $s.IconLocation='%PASTA%\jornal.ico'; $s.Save()"
echo Atalho "Jornal Diario" criado na area de trabalho.
echo Agora de duplo clique nele para abrir o jornal.
pause
