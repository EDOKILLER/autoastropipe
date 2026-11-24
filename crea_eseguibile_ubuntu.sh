#!/usr/bin/env bash
# =============================================================================
# Crea l'eseguibile "AutoAstroPipe" per Ubuntu (da fare UNA sola volta).
# L'eseguibile finale funziona senza Python, senza JupyterLab e senza pacchetti.
#
# Uso: metti questo file nella stessa cartella di autoastropipe.py, poi nel terminale:
#     cd <cartella con i due file>
#     bash crea_eseguibile_ubuntu.sh
# =============================================================================
set -e
cd "$(dirname "$(readlink -f "$0")")"

for f in autoastropipe.py motore_aap.py roman_asdf.py rifinitura.py mappa_cielo.py lingua.py lingua_en.py openngc_compatto.csv autoastropipe.png; do
    [ -f "$f" ] || { echo "ERRORE: manca $f in questa cartella ($(pwd))."; exit 1; }
done

echo "=== 1/4  Strumenti di sistema (chiede la password) ==="
sudo apt update
sudo apt install -y python3-venv python3-tk

echo "=== 2/4  Ambiente Python temporaneo per la compilazione ==="
# l'ambiente viene riusato se esiste già (ricompilazioni molto più rapide)
[ -d .venv-build ] || python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
python -m pip install numpy scipy matplotlib astropy photutils reproject scikit-image PyWavelets pyvo pillow tifffile psutil asdf asdf-astropy gwcs lz4 pyinstaller

echo "=== Dati della mappa del cielo (stelle, costellazioni: d3-celestial, licenza BSD) ==="
mkdir -p dati_cielo
for f in stars.6.json constellations.lines.json constellations.bounds.json constellations.json starnames.json; do
    if [ ! -s "dati_cielo/$f" ]; then
        curl -fsSL -A "AutoAstroPipe-compilazione" -o "dati_cielo/$f" "https://cdn.jsdelivr.net/npm/d3-celestial@0.7.35/data/$f" \
        || curl -fsSL -A "AutoAstroPipe-compilazione" -o "dati_cielo/$f" "https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/$f" \
        || { rm -f "dati_cielo/$f"; echo "  (non scaricato $f: il programma lo scaricherà alla prima mappa)"; }
    fi
done
DATI_CIELO=""
if [ -s dati_cielo/stars.6.json ] && [ -s dati_cielo/constellations.bounds.json ] && [ -s dati_cielo/constellations.lines.json ] \
   && [ -s dati_cielo/constellations.json ] && [ -s dati_cielo/starnames.json ]; then
    DATI_CIELO="--add-data dati_cielo:dati_cielo"
    echo "  dati inclusi nell'eseguibile"
fi

echo "=== 3/4  Creazione dell'eseguibile (qualche minuto) ==="
pyinstaller --noconfirm --clean --onefile --windowed \
    --name AutoAstroPipe \
    --collect-all astropy \
    --collect-all photutils \
    --collect-all reproject \
    --collect-all astropy_healpix \
    --collect-all skimage \
    --collect-all pywt \
    --collect-all pyvo \
    --collect-all erfa \
    --collect-all asdf \
    --collect-all asdf_astropy \
    --collect-all asdf_standard \
    --collect-all asdf_transform_schemas \
    --collect-all asdf_coordinates_schemas \
    --collect-all asdf_wcs_schemas \
    --collect-all gwcs \
    --collect-all lz4 \
    --collect-submodules scipy \
    --collect-binaries scipy \
    --collect-submodules matplotlib \
    --collect-data astropy_iers_data \
    --collect-submodules tifffile \
    --copy-metadata scipy \
    --copy-metadata numpy \
    --copy-metadata astropy \
    --copy-metadata photutils \
    --copy-metadata reproject \
    --copy-metadata astropy-healpix \
    --copy-metadata scikit-image \
    --copy-metadata PyWavelets \
    --copy-metadata pyvo \
    --copy-metadata matplotlib \
    --copy-metadata pyerfa \
    --copy-metadata astropy-iers-data \
    --copy-metadata packaging \
    --copy-metadata pyyaml \
    --copy-metadata psutil \
    --copy-metadata pillow \
    --copy-metadata tifffile \
    --copy-metadata lazy_loader \
    --copy-metadata imageio \
    --copy-metadata networkx \
    --copy-metadata requests \
    --copy-metadata asdf \
    --copy-metadata asdf-astropy \
    --copy-metadata asdf-standard \
    --copy-metadata asdf-transform-schemas \
    --copy-metadata asdf-coordinates-schemas \
    --copy-metadata asdf-wcs-schemas \
    --copy-metadata gwcs \
    --copy-metadata lz4 \
    --hidden-import roman_asdf \
    --add-data "openngc_compatto.csv:." \
    --add-data "autoastropipe.png:." \
    --hidden-import rifinitura \
    --hidden-import mappa_cielo \
    --hidden-import lingua \
    --hidden-import lingua_en \
    $DATI_CIELO \
    --hidden-import matplotlib.backends.backend_tkagg \
    --hidden-import PIL._tkinter_finder \
    autoastropipe.py
deactivate

echo "=== Verifica dell'eseguibile (autotest) ==="
if ! ./dist/AutoAstroPipe --autotest > autotest.txt 2>&1; then
    cat autotest.txt
    echo
    echo "L'autotest è FALLITO: i dettagli sono in $(pwd)/autotest.txt"
    echo "L'eseguibile non è stato installato. Invia autotest.txt per la correzione."
    rm -rf build AutoAstroPipe.spec
    exit 1
fi
cat autotest.txt

echo "=== Prova di SIMBAD (diagnostica, serve Internet) ==="
./dist/AutoAstroPipe --diagnostica > diagnostica.txt 2>&1 || true
grep -E "^\[(ok|ERRORE)\]" diagnostica.txt || true

echo "=== 4/4  Installazione nella home e icona nel menu ==="
DEST="$HOME/.local/bin"
mkdir -p "$DEST" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/512x512/apps"
cp autoastropipe.png "$HOME/.local/share/icons/hicolor/512x512/apps/autoastropipe.png"
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
cp dist/AutoAstroPipe "$DEST/AutoAstroPipe"
chmod +x "$DEST/AutoAstroPipe"

# il programma si chiamava "Pipeline FITS": tolgo le sue vecchie icone per non avere doppioni
rm -f "$HOME/.local/share/applications/pipeline-fits.desktop"
rm -f "$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Scrivania")/pipeline-fits.desktop"

cat > "$HOME/.local/share/applications/autoastropipe.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=AutoAstroPipe (AAP)
Comment=AutoAstroPipe - FITS e Roman: rumore, fondo, stretching, stack B/N e RGB, rifinitura, analisi
Exec=$DEST/AutoAstroPipe
Icon=$HOME/.local/share/icons/hicolor/512x512/apps/autoastropipe.png
StartupWMClass=AutoAstroPipe
Terminal=false
Categories=Science;Astronomy;Education;
EOF
chmod +x "$HOME/.local/share/applications/autoastropipe.desktop"

# Copia anche sulla Scrivania (cartella Desktop o Scrivania, a seconda della lingua)
SCRIVANIA="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Scrivania")"
if [ -d "$SCRIVANIA" ]; then
    cp "$HOME/.local/share/applications/autoastropipe.desktop" "$SCRIVANIA/"
    chmod +x "$SCRIVANIA/autoastropipe.desktop"
    gio set "$SCRIVANIA/autoastropipe.desktop" metadata::trusted true 2>/dev/null || true
fi

# Pulizia dei file della compilazione (l'eseguibile resta in dist/ e in ~/.local/bin)
rm -rf .venv-build build AutoAstroPipe.spec

echo
echo "FATTO."
echo "  Eseguibile:  $DEST/AutoAstroPipe   (copia anche in $(pwd)/dist/)"
echo "  Avvio:       cerca 'AutoAstroPipe' nel menu delle applicazioni,"
echo "               oppure doppio clic sull'icona sulla Scrivania"
echo "               (la prima volta: tasto destro -> 'Consenti avvio')."
