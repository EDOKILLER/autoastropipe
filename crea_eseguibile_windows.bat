@echo off
REM ===========================================================================
REM Crea AutoAstroPipe.exe per Windows 11 (da fare UNA sola volta).
REM L'eseguibile finale funziona senza Python, senza JupyterLab e senza pacchetti.
REM
REM Prima serve Python per la sola compilazione: scaricalo da python.org e
REM durante l'installazione spunta "Add python.exe to PATH".
REM
REM Uso: metti questo file nella stessa cartella di autoastropipe.py e fai
REM      doppio clic su crea_eseguibile_windows.bat
REM ===========================================================================
chcp 65001 >nul
cd /d "%~dp0"

if not exist motore_aap.py goto mancante
if not exist roman_asdf.py goto mancante
if not exist rifinitura.py goto mancante
if not exist mappa_cielo.py goto mancante
if not exist lingua.py goto mancante
if not exist lingua_en.py goto mancante
if not exist autoastropipe.ico goto mancante
if not exist openngc_compatto.csv goto mancante
if not exist autoastropipe.py (
    echo ERRORE: autoastropipe.py non e' in questa cartella: %cd%
    pause
    exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo ERRORE: Python non trovato. Installalo da https://www.python.org
    echo spuntando "Add python.exe to PATH", poi riavvia questo file.
    pause
    exit /b 1
)

echo === 1/3  Ambiente Python temporaneo per la compilazione ===
if not exist .venv-build (%PY% -m venv .venv-build || goto errore)
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip || goto errore
python -m pip install numpy scipy matplotlib astropy photutils reproject scikit-image PyWavelets pyvo pillow tifffile psutil asdf asdf-astropy gwcs lz4 pyinstaller || goto errore

echo === 2/3  Creazione dell'eseguibile (qualche minuto) ===
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name AutoAstroPipe ^
    --collect-all astropy ^
    --collect-all photutils ^
    --collect-all reproject ^
    --collect-all astropy_healpix ^
    --collect-all skimage ^
    --collect-all pywt ^
    --collect-all pyvo ^
    --collect-all erfa ^
    --collect-all asdf ^
    --collect-all asdf_astropy ^
    --collect-all asdf_standard ^
    --collect-all asdf_transform_schemas ^
    --collect-all asdf_coordinates_schemas ^
    --collect-all asdf_wcs_schemas ^
    --collect-all gwcs ^
    --collect-all lz4 ^
    --collect-submodules scipy ^
    --collect-binaries scipy ^
    --collect-submodules matplotlib ^
    --collect-data astropy_iers_data ^
    --collect-submodules tifffile ^
    --copy-metadata scipy ^
    --copy-metadata numpy ^
    --copy-metadata astropy ^
    --copy-metadata photutils ^
    --copy-metadata reproject ^
    --copy-metadata astropy-healpix ^
    --copy-metadata scikit-image ^
    --copy-metadata PyWavelets ^
    --copy-metadata pyvo ^
    --copy-metadata matplotlib ^
    --copy-metadata pyerfa ^
    --copy-metadata astropy-iers-data ^
    --copy-metadata packaging ^
    --copy-metadata pyyaml ^
    --copy-metadata psutil ^
    --copy-metadata pillow ^
    --copy-metadata tifffile ^
    --copy-metadata lazy_loader ^
    --copy-metadata imageio ^
    --copy-metadata networkx ^
    --copy-metadata requests ^
    --copy-metadata asdf ^
    --copy-metadata asdf-astropy ^
    --copy-metadata asdf-standard ^
    --copy-metadata asdf-transform-schemas ^
    --copy-metadata asdf-coordinates-schemas ^
    --copy-metadata asdf-wcs-schemas ^
    --copy-metadata gwcs ^
    --copy-metadata lz4 ^
    --hidden-import roman_asdf ^
    --add-data "openngc_compatto.csv;." ^
    --add-data "autoastropipe.png;." ^
    --hidden-import rifinitura ^
    --hidden-import mappa_cielo ^
    --hidden-import lingua ^
    --hidden-import lingua_en ^
    --icon autoastropipe.ico ^
    --hidden-import matplotlib.backends.backend_tkagg ^
    --hidden-import PIL._tkinter_finder ^
    autoastropipe.py || goto errore
call deactivate

echo === Verifica dell'eseguibile (autotest) ===
del /q autotest_risultato.txt 2>nul
dist\AutoAstroPipe.exe --autotest > autotest.txt 2>&1
if exist autotest_risultato.txt type autotest_risultato.txt >> autotest.txt
type autotest.txt
findstr /c:"AUTOTEST SUPERATO" autotest.txt >nul || (
    echo.
    echo L'autotest e' FALLITO: i dettagli sono in %cd%\autotest.txt
    goto errore
)

echo === Prova di SIMBAD (diagnostica, serve Internet) ===
del /q diagnostica_risultato.txt 2>nul
dist\AutoAstroPipe.exe --diagnostica > diagnostica.txt 2>&1
if exist diagnostica_risultato.txt type diagnostica_risultato.txt >> diagnostica.txt
findstr /b /c:"[ok]" /c:"[ERRORE]" diagnostica.txt

echo === 3/3  Collegamento sul Desktop ===
copy /y dist\AutoAstroPipe.exe "%cd%\AutoAstroPipe.exe" >nul
powershell -NoProfile -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$d\AutoAstroPipe.lnk\"); $s.TargetPath='%cd%\AutoAstroPipe.exe'; $s.WorkingDirectory='%cd%'; $s.Save()"

rmdir /s /q .venv-build build 2>nul
del /q AutoAstroPipe.spec 2>nul

echo.
echo FATTO.
echo   Eseguibile: %cd%\AutoAstroPipe.exe
echo   Sul Desktop trovi il collegamento "AutoAstroPipe".
echo   Puoi copiare AutoAstroPipe.exe su qualsiasi PC Windows: non serve altro.
pause
exit /b 0

:mancante
echo ERRORE: autoastropipe.py, motore_aap.py, roman_asdf.py, rifinitura.py, mappa_cielo.py, lingua.py, lingua_en.py, openngc_compatto.csv, autoastropipe.png e autoastropipe.ico devono essere in questa cartella.
pause
exit /b 1

:errore
echo.
echo Si e' verificato un errore: copia i messaggi qui sopra e inviameli.
pause
exit /b 1
