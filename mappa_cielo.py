"""
Mappa della posizione nel cielo, nello stile delle carte delle costellazioni
dell'IAU / Sky & Telescope: la costellazione che contiene l'immagine in bianco,
le altre in grigio, linee delle figure in verde, confini punteggiati, stelle
fino alla magnitudine 6 con lettere greche e nomi propri, eclittica in azzurro,
griglia in ascensione retta e declinazione e il campo dell'immagine in rosso.

Dati (licenza BSD-3, d3-celestial di Olaf Frohn): stelle XHIP/Hipparcos, linee
delle costellazioni IAU, confini IAU (Davenhall & Leggett 1989). Vengono cercati
accanto al programma (cartella dati_cielo), poi nella cache dell'utente; se
mancano si scaricano una volta sola da jsDelivr o GitHub.

Non usa astropy: solo numpy e matplotlib (le coordinate arrivano già in gradi).
© 2026 Edoardo Battistel
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

FILE_DATI = {"stelle": "stars.6.json", "linee": "constellations.lines.json",
             "confini": "constellations.bounds.json", "costellazioni": "constellations.json",
             "nomi_stelle": "starnames.json"}
URL_BASE = ["https://cdn.jsdelivr.net/npm/d3-celestial@0.7.35/data/",
            "https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/"]
CARTELLA = "dati_cielo"
OBLIQUITA = 23.4393            # gradi, J2000
LETTERE = {"alp": "α", "bet": "β", "gam": "γ", "del": "δ", "eps": "ε", "zet": "ζ", "eta": "η", "the": "θ",
           "iot": "ι", "kap": "κ", "lam": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "omi": "ο", "pi": "π",
           "rho": "ρ", "sig": "σ", "tau": "τ", "ups": "υ", "phi": "φ", "chi": "χ", "psi": "ψ", "ome": "ω"}
COLORI = {"fondo": "#d4d4d4", "dentro": "#ffffff", "linee": "#93cf8d", "linee_forti": "#7cc576",
          "confini": "#555555", "griglia": "#6f6f6f", "eclittica": "#5daee6", "stelle": "#000000",
          "campo": "#e0201b", "testo": "#1a1a1a"}

_DATI = None


# =============================================================================
# DATI
# =============================================================================
def cartella_cache():
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "autoastropipe" / CARTELLA


def _accanto_al_programma():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / CARTELLA


def _scarica(nome, dest, log=None):
    import requests
    errori = []
    for base in URL_BASE:
        try:
            r = requests.get(base + nome, timeout=60, headers={"User-Agent": "AutoAstroPipe/2.4"})
            r.raise_for_status()
            json.loads(r.content.decode("utf-8"))        # controllo: deve essere JSON valido
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".tmp")
            tmp.write_bytes(r.content)
            tmp.replace(dest)
            if log:
                log(f"  scaricato {nome} ({len(r.content) // 1024} kB) da {base.split('/')[2]}")
            return dest
        except Exception as e:
            errori.append(f"{base.split('/')[2]}: {type(e).__name__}: {e}")
    raise ConnectionError(f"non riesco a scaricare {nome} (" + "; ".join(errori) + ")")


def carica_dati(log=None, scarica=True, cartelle=None):
    """Dizionario con i 5 file JSON. 'cartelle' (per le prove) sostituisce i percorsi normali."""
    global _DATI
    if _DATI is not None and cartelle is None:
        return _DATI
    dove = list(cartelle) if cartelle else [_accanto_al_programma(), cartella_cache()]
    dati = {}
    for chiave, nome in FILE_DATI.items():
        p = next((Path(c) / nome for c in dove if (Path(c) / nome).is_file()), None)
        if p is None:
            if not scarica:
                raise FileNotFoundError(f"manca {nome} (dati della mappa del cielo)")
            p = _scarica(nome, cartella_cache() / nome, log)
        with open(p, encoding="utf-8") as f:
            dati[chiave] = json.load(f)
    if cartelle is None:
        _DATI = dati
    return dati


# =============================================================================
# GEOMETRIA
# =============================================================================
def _vettore(ra, de):
    ra, de = np.radians(ra), np.radians(de)
    return np.stack([np.cos(de) * np.cos(ra), np.cos(de) * np.sin(ra), np.sin(de)], axis=-1)


def _radec(v):
    v = v / np.linalg.norm(v, axis=-1, keepdims=True)
    return np.degrees(np.arctan2(v[..., 1], v[..., 0])) % 360, np.degrees(np.arcsin(np.clip(v[..., 2], -1, 1)))


class Proiezione:
    """Proiezione stereografica centrata in (ra0, de0), est a sinistra come sul cielo."""

    def __init__(self, ra0, de0):
        self.ra0, self.de0 = float(ra0) % 360, float(de0)
        self._a0, self._d0 = math.radians(self.ra0), math.radians(self.de0)

    def __call__(self, ra, de):
        a, d = np.radians(np.asarray(ra, dtype=float)), np.radians(np.asarray(de, dtype=float))
        cc = math.sin(self._d0) * np.sin(d) + math.cos(self._d0) * np.cos(d) * np.cos(a - self._a0)
        k = 2.0 / np.maximum(1.0 + cc, 1e-9)
        x = -k * np.cos(d) * np.sin(a - self._a0)
        y = k * (math.cos(self._d0) * np.sin(d) - math.sin(self._d0) * np.cos(d) * np.cos(a - self._a0))
        valido = cc > -0.5
        return np.where(valido, x, np.nan), np.where(valido, y, np.nan)


def _infittisci_cerchio_massimo(punti, passo=1.0):
    """Linee tra stelle: archi di cerchio massimo con punti ogni 'passo' gradi."""
    out = []
    for (r1, d1), (r2, d2) in zip(punti[:-1], punti[1:]):
        v1, v2 = _vettore(r1, d1), _vettore(r2, d2)
        ang = math.degrees(math.acos(float(np.clip(np.dot(v1, v2), -1, 1))))
        n = max(1, int(ang / passo))
        t = np.linspace(0, 1, n, endpoint=False)[:, None]
        v = v1 * (1 - t) + v2 * t
        ra, de = _radec(v)
        out.extend(zip(ra, de))
    out.append(tuple(punti[-1]))
    return np.array(out, dtype=float)


def _infittisci_confine(punti, passo=0.5):
    """Confini IAU: lati lungo i paralleli e i meridiani, interpolati in (ra, dec)."""
    out = []
    for (r1, d1), (r2, d2) in zip(punti[:-1], punti[1:]):
        dr = ((r2 - r1 + 180) % 360) - 180
        n = max(1, int(max(abs(dr), abs(d2 - d1)) / passo))
        t = np.linspace(0, 1, n, endpoint=False)
        out.extend(zip((r1 + dr * t) % 360, d1 + (d2 - d1) * t))
    out.append((punti[-1][0] % 360, punti[-1][1]))
    return np.array(out, dtype=float)


def _ra(lon):
    return float(lon) % 360


def _anelli(geom):
    """Anelli (lista di array Nx2 ra/dec) di un Polygon o MultiPolygon GeoJSON."""
    if geom is None:
        return []
    c = geom.get("coordinates", [])
    if geom.get("type") == "Polygon":
        poligoni = [c]
    elif geom.get("type") == "MultiPolygon":
        poligoni = c
    else:
        return []
    return [np.array([(_ra(p[0]), float(p[1])) for p in anello], dtype=float)
            for pol in poligoni for anello in pol[:1] if len(anello) > 2]


def _abbreviazione(fid):
    """'Ser1' / 'Ser2' (le due parti del Serpente) -> 'Ser'."""
    return str(fid or "")[:3]


def costellazione_di(dati, ra, de):
    """Abbreviazione IAU della costellazione che contiene (ra, de), o None."""
    from matplotlib.path import Path as Percorso
    pr = Proiezione(ra, de)
    for f in dati["confini"].get("features", []):
        for anello in _anelli(f.get("geometry")):
            x, y = pr(*_infittisci_confine(anello).T)
            ok = np.isfinite(x)
            if ok.sum() < 3 or not ok.all():
                continue
            if Percorso(np.column_stack([x, y])).contains_point((0.0, 0.0)):
                return _abbreviazione(f.get("id"))
    return None


def info_costellazioni(dati):
    """{abbreviazione: {nome, italiano, inglese, ra, dec}} dai nomi delle costellazioni."""
    out = {}
    for f in dati["costellazioni"].get("features", []):
        p = f.get("properties", {}) or {}
        ab = _abbreviazione(f.get("id") or p.get("desig"))
        coord = (f.get("geometry") or {}).get("coordinates") or [None, None]
        nome = p.get("name") or ab
        out[ab] = dict(nome=nome, italiano=p.get("it") or nome, inglese=p.get("en") or nome,
                       ra=_ra(coord[0]) if coord[0] is not None else None,
                       dec=float(coord[1]) if coord[1] is not None else None)
    return out


def stelle(dati):
    """Array ra, dec, mag, hip delle stelle (mag 6)."""
    ra, de, mag, hip = [], [], [], []
    for f in dati["stelle"].get("features", []):
        try:
            lon, lat = f["geometry"]["coordinates"][:2]
            m = float(f.get("properties", {}).get("mag"))
        except (KeyError, TypeError, ValueError):
            continue
        ra.append(_ra(lon)); de.append(float(lat)); mag.append(m); hip.append(str(f.get("id", "")))
    return np.array(ra), np.array(de), np.array(mag), hip


def _lettera(voce):
    """Lettera greca (o numero di Flamsteed) di una stella da starnames.json."""
    b = str(voce.get("bayer") or "").strip()
    if b:
        base = b.rstrip("0123456789")
        num = b[len(base):]
        base = LETTERE.get(base.lower()[:3], base) if not any("α" <= ch <= "ω" for ch in base) else base
        return base + ("" if not num else "".join("⁰¹²³⁴⁵⁶⁷⁸⁹"[int(c)] for c in num))
    return str(voce.get("flam") or "").strip()


# =============================================================================
# DISEGNO
# =============================================================================
def _passo_griglia(ampiezza_gradi, de0):
    """Passi della griglia: AR in ore, Dec in gradi, secondo l'ampiezza della mappa."""
    passo_dec = 5 if ampiezza_gradi < 30 else 10 if ampiezza_gradi < 90 else 20
    larghezza_ar = ampiezza_gradi / max(math.cos(math.radians(min(abs(de0), 80))), 0.15) / 15
    for passo in (0.5, 1, 2, 3, 4, 6):
        if larghezza_ar / passo <= 10:
            return passo, passo_dec
    return 6, passo_dec


def _incrocio(x, y, valore, asse):
    """Punti in cui la polilinea (x, y) attraversa x=valore (asse 0) o y=valore (asse 1)."""
    c = x if asse == 0 else y
    altro = y if asse == 0 else x
    out = []
    for i in range(len(c) - 1):
        a, b = c[i] - valore, c[i + 1] - valore
        if np.isfinite(a) and np.isfinite(b) and a * b <= 0 and a != b:
            t = a / (a - b)
            out.append(altro[i] + t * (altro[i + 1] - altro[i]))
    return out


def _testo_ar(ore):
    h = int(ore) % 24
    m = int(round((ore - int(ore)) * 60))
    return f"{h}ʰ" + (f"{m:02d}ᵐ" if m else "")


def disegna_mappa(dati, ra_campo, de_campo, contorno=None, nome="", fig=None, lingua="it"):
    """Disegna la mappa. contorno = array Nx2 (ra, dec) dei vertici dell'immagine.
    Restituisce (figura, dizionario con costellazione e stelle vicine)."""
    import matplotlib.patheffects as pe
    from matplotlib.patches import Polygon
    if fig is None:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        fig = Figure(figsize=(12, 11), dpi=110)
        FigureCanvasAgg(fig)
    info = info_costellazioni(dati)
    ab = costellazione_di(dati, ra_campo, de_campo)
    # anelli della costellazione dell'immagine (Serpens ne ha due)
    anelli_cost = []
    for f in dati["confini"].get("features", []):
        if ab and _abbreviazione(f.get("id")) == ab:
            anelli_cost += [_infittisci_confine(a) for a in _anelli(f.get("geometry"))]

    # centro e ampiezza della mappa: la costellazione intera, con un margine
    pr0 = Proiezione(ra_campo, de_campo)
    if anelli_cost:
        tutti = np.vstack(anelli_cost)
        ra_c, de_c = _radec(_vettore(tutti[:, 0], tutti[:, 1]).mean(axis=0))
        pr = Proiezione(float(ra_c), float(de_c))
        x, y = pr(tutti[:, 0], tutti[:, 1])
        ok = np.isfinite(x)
        x0, x1, y0, y1 = np.nanmin(x[ok]), np.nanmax(x[ok]), np.nanmin(y[ok]), np.nanmax(y[ok])
        if max(x1 - x0, y1 - y0) > 1.8:          # costellazione enorme: centro sull'immagine
            pr = pr0
            x0, x1, y0, y1 = -0.45, 0.45, -0.4, 0.4
    else:
        pr = pr0
        x0, x1, y0, y1 = -0.3, 0.3, -0.27, 0.27
    xc, yc = pr(ra_campo, de_campo)
    x0, x1 = min(x0, float(xc)), max(x1, float(xc))
    y0, y1 = min(y0, float(yc)), max(y1, float(yc))
    mx, my = (x1 - x0) * 0.12 + 0.02, (y1 - y0) * 0.12 + 0.02
    x0, x1, y0, y1 = x0 - mx, x1 + mx, y0 - my, y1 + my
    # stesse proporzioni della figura
    w_fig, h_fig = fig.get_size_inches()
    ax = fig.add_axes([0.07, 0.10, 0.86, 0.79])
    rapporto = (0.79 * h_fig) / (0.86 * w_fig)
    if (y1 - y0) / (x1 - x0) < rapporto:
        d = ((x1 - x0) * rapporto - (y1 - y0)) / 2
        y0, y1 = y0 - d, y1 + d
    else:
        d = ((y1 - y0) / rapporto - (x1 - x0)) / 2
        x0, x1 = x0 - d, x1 + d
    ampiezza = math.degrees(4 * math.atan((x1 - x0) / 4))    # gradi lungo la larghezza
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_facecolor(COLORI["fondo"])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#333333"); s.set_linewidth(1.0)
    scala_testo = 1.0

    # costellazione dell'immagine in bianco
    for a in anelli_cost:
        x, y = pr(a[:, 0], a[:, 1])
        ok = np.isfinite(x)
        if ok.sum() > 2:
            ax.add_patch(Polygon(np.column_stack([x[ok], y[ok]]), closed=True, facecolor=COLORI["dentro"],
                                 edgecolor="none", zorder=1))

    # griglia
    passo_ar, passo_dec = _passo_griglia(ampiezza, pr.de0)
    for ore in np.arange(0, 24, passo_ar):
        de = np.linspace(-89.5, 89.5, 360)
        x, y = pr(np.full_like(de, ore * 15), de)
        ax.plot(x, y, color=COLORI["griglia"], lw=0.6, zorder=2)
        for bordo, va in ((y1, "bottom"), (y0, "top")):
            for xx in _incrocio(x, y, bordo, 1):
                if x0 <= xx <= x1:
                    ax.text(xx, bordo + (0.006 if va == "bottom" else -0.006) * (y1 - y0), _testo_ar(ore),
                            ha="center", va=va, fontsize=13 * scala_testo, color=COLORI["testo"], clip_on=False)
    for dec in np.arange(-80, 81, passo_dec):
        ra = np.linspace(0, 360, 721)
        x, y = pr(ra, np.full_like(ra, dec))
        ax.plot(x, y, color=COLORI["griglia"], lw=0.6, zorder=2)
        for bordo, ha in ((x0, "right"), (x1, "left")):
            for yy in _incrocio(x, y, bordo, 0):
                if y0 <= yy <= y1:
                    ax.text(bordo + (-0.006 if ha == "right" else 0.006) * (x1 - x0), yy,
                            f"{'+' if dec > 0 else '−' if dec < 0 else ''}{abs(int(dec))}°",
                            ha=ha, va="center", fontsize=13 * scala_testo, color=COLORI["testo"], clip_on=False)

    # eclittica
    lam = np.radians(np.linspace(0, 360, 1441))
    eps = math.radians(OBLIQUITA)
    ra_e = np.degrees(np.arctan2(np.sin(lam) * math.cos(eps), np.cos(lam))) % 360
    de_e = np.degrees(np.arcsin(math.sin(eps) * np.sin(lam)))
    x, y = pr(ra_e, de_e)
    ax.plot(x, y, color=COLORI["eclittica"], lw=2.6, zorder=3, solid_capstyle="round")

    # confini di tutte le costellazioni
    for f in dati["confini"].get("features", []):
        for a in _anelli(f.get("geometry")):
            a = _infittisci_confine(np.vstack([a, a[:1]]))
            x, y = pr(a[:, 0], a[:, 1])
            ax.plot(x, y, color=COLORI["confini"], lw=0.7, ls=(0, (1, 2.2)), zorder=3)

    # linee delle figure
    for f in dati["linee"].get("features", []):
        forte = ab is not None and _abbreviazione(f.get("id")) == ab
        geom = f.get("geometry") or {}
        linee = geom.get("coordinates", [])
        if geom.get("type") == "LineString":
            linee = [linee]
        for linea in linee:
            if len(linea) < 2:
                continue
            p = _infittisci_cerchio_massimo([(_ra(q[0]), float(q[1])) for q in linea])
            x, y = pr(p[:, 0], p[:, 1])
            ax.plot(x, y, color=COLORI["linee_forti"] if forte else COLORI["linee"],
                    lw=3.4 if forte else 1.6, zorder=4, solid_capstyle="round")

    # stelle
    ra_s, de_s, mag, hip = stelle(dati)
    xs, ys = pr(ra_s, de_s)
    dentro = np.isfinite(xs) & (xs > x0) & (xs < x1) & (ys > y0) & (ys < y1)
    dim = (np.clip(7.2 - mag, 0.8, 9.0) ** 1.9) * 2.0
    ax.scatter(xs[dentro], ys[dentro], s=dim[dentro], c=COLORI["stelle"], edgecolors="white",
               linewidths=0.6, zorder=6)
    # lettere greche e nomi propri (solo nella costellazione dell'immagine)
    nomi = dati.get("nomi_stelle", {}) or {}
    if anelli_cost:
        from matplotlib.path import Path as Percorso
        percorsi = []
        for a in anelli_cost:
            x, y = pr(a[:, 0], a[:, 1])
            ok = np.isfinite(x)
            if ok.sum() > 2:
                percorsi.append(Percorso(np.column_stack([x[ok], y[ok]])))
        dx = (x1 - x0) * 0.008
        for i in np.where(dentro & (mag < 5.2))[0]:
            voce = nomi.get(hip[i])
            if not voce or not any(pp.contains_point((xs[i], ys[i])) for pp in percorsi):
                continue
            lettera = _lettera(voce)
            proprio = str(voce.get("name") or "").strip() if mag[i] < 3.2 else ""
            testo = lettera + ("  " + proprio if proprio else "")
            if testo.strip():
                t = ax.text(xs[i] + dx + math.sqrt(dim[i]) * 0.0007 * (x1 - x0), ys[i], testo,
                            fontsize=13 * scala_testo, color=COLORI["testo"], va="center", zorder=7)
                t.set_path_effects([pe.withStroke(linewidth=2.5, foreground="white")])

    # nomi delle costellazioni
    for abbr, c in info.items():
        if c["ra"] is None:
            continue
        x, y = pr(c["ra"], c["dec"])
        x, y = float(x), float(y)
        if not (np.isfinite(x) and x0 + 0.04 * (x1 - x0) < x < x1 - 0.04 * (x1 - x0)
                and y0 + 0.03 * (y1 - y0) < y < y1 - 0.03 * (y1 - y0)):
            continue
        t = ax.text(x, y, " ".join(c["nome"].upper()), ha="center", va="center", style="italic",
                    fontsize=(18 if abbr == ab else 15) * scala_testo, color=COLORI["testo"], zorder=8)
        t.set_path_effects([pe.withStroke(linewidth=3, foreground=COLORI["dentro"] if abbr == ab else COLORI["fondo"])])

    # campo dell'immagine
    xc, yc = float(xc), float(yc)
    if contorno is not None and len(contorno) > 2:
        cx, cy = pr(np.asarray(contorno)[:, 0], np.asarray(contorno)[:, 1])
        ax.add_patch(Polygon(np.column_stack([cx, cy]), closed=True, facecolor=COLORI["campo"], alpha=0.5,
                             edgecolor=COLORI["campo"], lw=1.5, zorder=9))
    ax.plot([xc], [yc], marker="o", ms=22, mfc="none", mec=COLORI["campo"], mew=3, zorder=10)
    ax.plot([xc], [yc], marker="+", ms=12, color=COLORI["campo"], mew=2.5, zorder=10)
    etichetta = nome or ""
    if etichetta:
        t = ax.text(xc + 0.022 * (x1 - x0), yc + 0.022 * (y1 - y0), etichetta, color=COLORI["campo"],
                    fontsize=16, fontweight="bold", zorder=11)
        t.set_path_effects([pe.withStroke(linewidth=3.5, foreground="white")])

    # legenda delle magnitudini e titolo
    leg = fig.add_axes([0.07, 0.02, 0.45, 0.05])
    leg.set_xlim(0, 6.6); leg.set_ylim(-1, 1); leg.axis("off")
    for k in range(1, 7):
        leg.scatter([k - 0.75], [0], s=(7.2 - k) ** 1.9 * 2.0, c="black", edgecolors="white", linewidths=0.6)
        leg.text(k - 0.55, 0, str(k), va="center", fontsize=12)
    leg.text(6.3, 0, "magnitudine", va="center", fontsize=11, color="#444444")
    c = info.get(ab, {}) if ab else {}
    nome_cost = c.get("italiano" if lingua == "it" else "inglese") or c.get("nome") or (ab or "?")
    latino = c.get("nome") or ab or ""
    titolo = f"Posizione nel cielo: {nome or 'campo dell' + chr(39) + 'immagine'} — costellazione {nome_cost}"
    if latino and latino != nome_cost:
        titolo += f" ({latino})"
    fig.text(0.5, 0.975, titolo, ha="center", va="center", fontsize=16, fontweight="bold")
    fig.text(0.5, 0.947, f"AR {_testo_ar_completo(ra_campo)}   Dec {_testo_dec_completo(de_campo)}   (J2000)"
             "   ·   in rosso il campo dell'immagine, in azzurro l'eclittica", ha="center", va="center",
             fontsize=12, color="#333333")
    fig.text(0.93, 0.02, "dati: d3-celestial (XHIP, IAU)", ha="right", va="bottom", fontsize=8, color="#777777")

    # stelle con nome più vicine (per il CSV)
    sep = np.degrees(np.arccos(np.clip(_vettore(ra_s, de_s) @ _vettore(ra_campo, de_campo), -1, 1)))
    vicine = []
    for i in np.argsort(sep):
        voce = nomi.get(hip[i])
        if voce and (voce.get("name") or voce.get("bayer") or voce.get("flam")):
            nome_s = str(voce.get("name") or "").strip()
            sigla = f"{_lettera(voce)} {ab_stella(voce, latino)}".strip()
            vicine.append(dict(stella=nome_s or sigla, sigla=sigla, magnitudine=round(float(mag[i]), 2),
                               distanza_gradi=round(float(sep[i]), 2)))
        if len(vicine) >= 5:
            break
    return fig, dict(costellazione=nome_cost, latino=latino, abbreviazione=ab or "", vicine=vicine)


def ab_stella(voce, latino):
    d = str(voce.get("desig") or "")
    return d.split()[-1] if " " in d else ""


def _testo_ar_completo(ra):
    t = int(round((ra % 360) / 15 * 36000)) % 864000          # decimi di secondo
    hh, resto = divmod(t, 36000)
    mm, ds = divmod(resto, 600)
    return f"{hh:02d}h {mm:02d}m {ds / 10:04.1f}s"


def _testo_dec_completo(de):
    s = "+" if de >= 0 else "−"
    t = int(round(abs(de) * 3600))
    dd, resto = divmod(t, 3600)
    mm, ss = divmod(resto, 60)
    return f"{s}{dd:02d}° {mm:02d}′ {ss:02d}″"
