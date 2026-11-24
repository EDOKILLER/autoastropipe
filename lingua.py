"""
Lingua dell'interfaccia di AutoAstroPipe (italiano / inglese).

I testi del programma restano scritti in italiano nel codice; in inglese vengono
tradotti al volo nei punti in cui arrivano sullo schermo:
  - widget Tk/ttk (opzioni text e label, anche dei menu), titoli delle finestre,
    intestazioni delle tabelle;
  - tutte le scritte delle figure matplotlib (titoli, assi, etichette, legende)
    al momento del disegno, quindi anche nelle immagini salvate delle analisi;
  - il registro (App.scrivi).
Prima si cerca il testo intero nel dizionario (lingua_en.TRADUZIONI); se non
c'è (testi composti con numeri e nomi di file) si traducono i pezzi noti
contenuti nel testo, rispettando i confini delle parole.
© 2026 Edoardo Battistel
"""
import re

LINGUE = {"it": "Italiano", "en": "English"}
LINGUA = "it"
_EN = {}
_INV = {}
_RE = None
_INSTALLATO = False
_LETTERA = r"[0-9A-Za-zÀ-ÖØ-öø-ÿ_]"


def imposta(lingua):
    """Sceglie la lingua ("it" o "en") e prepara il dizionario."""
    global LINGUA, _EN, _INV, _RE
    LINGUA = lingua if lingua in LINGUE else "it"
    if LINGUA == "it":
        return
    from lingua_en import TRADUZIONI
    _EN = dict(TRADUZIONI)
    _INV = {v: k for k, v in _EN.items()}
    pezzi = sorted((k for k in _EN if len(k.strip()) >= 4), key=len, reverse=True)
    alternative = []
    for k in pezzi:
        e = re.escape(k)
        if re.match(_LETTERA, k[0]):
            e = f"(?<!{_LETTERA})" + e
        if re.match(_LETTERA, k[-1]):
            e = e + f"(?!{_LETTERA})"
        alternative.append(e)
    _RE = re.compile("|".join(alternative)) if alternative else None


def tr(s):
    """Testo nella lingua scelta (in italiano lo restituisce com'è)."""
    if LINGUA == "it" or not isinstance(s, str) or not s:
        return s
    t = _EN.get(s)
    if t is not None:
        return t
    if _RE is None:
        return s
    return _RE.sub(lambda m: _EN.get(m.group(0), m.group(0)), s)


def adatta(valore):
    """Per le preferenze salvate (etichette dei menu a tendina): porta un'etichetta
    salvata in una lingua nell'altra, solo se corrisponde esattamente."""
    if not isinstance(valore, str):
        return valore
    if LINGUA == "it":
        if not _INV:
            try:
                from lingua_en import TRADUZIONI
                _INV.update({v: k for k, v in TRADUZIONI.items()})
            except Exception:
                return valore
        return _INV.get(valore, valore)
    return _EN.get(valore, valore)


def installa():
    """Aggancia la traduzione a Tk e matplotlib (una volta sola; in italiano non fa nulla)."""
    global _INSTALLATO
    if _INSTALLATO or LINGUA == "it":
        return
    _INSTALLATO = True
    import tkinter as tk
    from tkinter import ttk

    orig_options = tk.Misc._options

    def _options(self, cnf, kw=None):
        for d in (cnf, kw):
            if isinstance(d, dict):
                for k in ("text", "label", "-text", "-label"):
                    if k in d and isinstance(d[k], str):
                        d[k] = tr(d[k])
        return orig_options(self, cnf, kw)
    tk.Misc._options = _options

    orig_titolo = tk.Wm.wm_title

    def wm_title(self, string=None):
        return orig_titolo(self, tr(string) if isinstance(string, str) else string)
    tk.Wm.wm_title = wm_title
    tk.Wm.title = wm_title

    orig_heading = ttk.Treeview.heading

    def heading(self, column, option=None, **kw):
        if isinstance(kw.get("text"), str):
            kw["text"] = tr(kw["text"])
        return orig_heading(self, column, option, **kw)
    ttk.Treeview.heading = heading

    import matplotlib.text as mtext
    orig_draw = mtext.Text.draw

    def draw(self, renderer, *a, **k):
        t = self.get_text()
        if t:
            n = tr(t)
            if n != t:
                self.set_text(n)
        return orig_draw(self, renderer, *a, **k)
    mtext.Text.draw = draw
