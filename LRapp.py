import streamlit as st
import pandas as pd
import csv, io, os, re, html

st.set_page_config(page_title="A1 Begrijpend Lezen", layout="centered")
st.title("📖 A1 Begrijpend Lezen — Interactieve Tekst")

# ----------------------------
# Robuuste loaders
# ----------------------------
def load_texts(path="texts.csv") -> pd.DataFrame:
    # texts.csv verwacht wél header: id,topic,text_nl,text_ar,glossary
    return pd.read_csv(path)

def load_general_dict(file="general_dict.csv"):
    """
    Laadt general_dict.csv met of zonder header.
    - delimiter: , of ;
    - encodings: utf-8 / utf-8-sig / cp1252
    - Als er geen kolomnamen zijn, gebruikt hij kolom 0 als 'nl' en kolom 1 als 'ar'.
    Returned: dict met lowercased NL-sleutels, haakjesinfo verwijderd (bv. 'zij (mv)' -> 'zij').
    """
    if not os.path.exists(file):
        return {}

    # 1) lees raw met meerdere encodings
    raw = None
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            with open(file, "r", encoding=enc, newline="") as f:
                raw = f.read()
            break
        except Exception:
            continue
    if raw is None:
        return {}

    # 2) delimiter detectie
    try:
        dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";" if raw.count(";") > raw.count(",") else ","

    rows = list(csv.reader(io.StringIO(raw), delimiter=delim))
    if not rows:
        return {}

    header_aliases = {
        "nl": "nl", "nederlands": "nl", "woord": "nl", "word": "nl",
        "ar": "ar", "arabisch": "ar", "arabic": "ar", "translation": "ar", "vertaling": "ar",
    }

    paren_re = re.compile(r"\s*\([^)]*\)")
    d = {}

    # 3) check of er een header is met nl/ar; zo niet, behandel alles als data
    has_header = False
    headers = [ (h or "").strip().lower() for h in rows[0] ]
    mapped = [header_aliases.get(h, h) for h in headers]
    if "nl" in mapped and "ar" in mapped:
        has_header = True
        idx_nl = mapped.index("nl")
        idx_ar = mapped.index("ar")
        data_start = 1
    else:
        # geen header → neem kolom 0 en 1 als data
        idx_nl, idx_ar = 0, 1
        data_start = 0

    for r in rows[data_start:]:
        if not r or all(not (c or "").strip() for c in r):
            continue
        nl = (r[idx_nl] if idx_nl < len(r) else "").strip()
        ar = (r[idx_ar] if idx_ar < len(r) else "").strip()
        if not nl or not ar:
            continue
        key = paren_re.sub("", nl.lower()).strip()  # strip "(...)" en lower
        if key and key not in d:
            d[key] = ar
    return d

# ----------------------------
# Teksthelpers (hover + icon inline)
# ----------------------------
WORD_TOKEN = re.compile(r"[A-Za-zÀ-ÿ0-9']+", re.UNICODE)

def split_sents_with_spaces(text: str):
    """
    Split de tekst in [(zin_met_eindteken, opvolgende_spaties)] zodat we
    de originele spaties behouden en na elke zin inline iets kunnen invoegen.
    Voor het laatste stuk zonder eindteken is spaces = "".
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        m = re.search(r"[\.!\?]", text[i:])
        if not m:
            # geen eindteken meer
            out.append((text[i:], ""))  # laatste segment
            break
        end = i + m.end()              # index na het eindteken
        # verzamel spaties na eindteken
        j = end
        while j < n and text[j].isspace():
            j += 1
        sent = text[i:end]             # inclusief .?! 
        spaces = text[end:j]           # spaties erna
        out.append((sent, spaces))
        i = j
    return out or [("", "")]

def render_sentence_with_word_hovers(nl_sentence: str, lookup_fn) -> str:
    """Vervang alleen woordtokens door span met title; behoud leestekens en spaties."""
    out = []
    last = 0
    for m in WORD_TOKEN.finditer(nl_sentence):
        s, e = m.span()
        out.append(html.escape(nl_sentence[last:s]))
        token = m.group(0)
        tr = lookup_fn(token.lower())
        if tr:
            out.append(f"<span title='{html.escape(tr)}' style='cursor:help'>{html.escape(token)}</span>")
        else:
            out.append(html.escape(token))
        last = e
    out.append(html.escape(nl_sentence[last:]))
    return "".join(out)

def make_info_icon(ar_sentence: str, idx: int) -> str:
    """ℹ inline, klikbaar (summary/details). Hover toont korte tip; klik toont volledige Arabische zin."""
    if not ar_sentence:
        short_tip = "—"
        full = "—"
    else:
        short_tip = ar_sentence.strip()
        short_tip = (short_tip[:80] + "…") if len(short_tip) > 80 else short_tip
        full = ar_sentence.strip()
    return (
        "<details style='display:inline;'>"
        f"<summary style='display:inline; cursor:pointer;' title='{html.escape(short_tip)}'>"
        "<span style='color:#3366cc;'> ℹ</span></summary>"
        f"<span style='direction:rtl; text-align:right; background:#f6f7fb; border:1px solid #e7e7ef; "
        "border-radius:10px; padding:6px 8px; margin-left:6px; display:inline-block; font-size:0.95em;'>"
        f"{html.escape(full)}</span></details>"
    )

# ----------------------------
# Data laden
# ----------------------------
texts = load_texts("texts.csv")
general_dict = load_general_dict("general_dict.csv")  # werkt nu ook zonder kolomnamen!

# UI: kies een tekst
choice = st.selectbox("Kies een tekst:", [f"{r['id']} — {r['topic']}" for _, r in texts.iterrows()])
row = texts.iloc[[i for i, r in texts.iterrows() if f"{r['id']} — {r['topic']}" == choice][0]]

# Lokale glossary (prioriteit 1)
local_gloss = {}
gloss_raw = str(row.get("glossary", "") or "")
if gloss_raw:
    for part in re.split(r"[;،]+", gloss_raw):
        if "=" in part:
            k, v = part.split("=", 1)
            local_gloss[k.strip().lower()] = v.strip()

def get_word_translation(word, local_gloss, general_dict):
    word_clean = word.lower().strip(".,!?;:")
    if word_clean in local_gloss:
        return local_gloss[word_clean]
    elif word_clean in general_dict:
        return general_dict[word_clean]
    else:
        return
  
# Lookup met prioriteit: local_gloss -> general_dict
def lookup_word_lower(key: str):
    if key in local_gloss:
        return local_gloss[key]
    if key in general_dict:
        return general_dict[key]
    return None

# ----------------------------
# Render: tekst in één paragraaf, ℹ ICON DIRECT NA ELKE ZIN
# ----------------------------
text_nl = str(row.get("text_nl", "") or "")
text_ar_full = str(row.get("text_ar", "") or "")

# Split NL en AR in zinnen (zelfde methode) zodat indexen corresponderen
nl_chunks = split_sents_with_spaces(text_nl)  # lijst van (zin, spaces)
ar_sents = [s for (s, _) in split_sents_with_spaces(text_ar_full)]  # enkel zinnen

html_parts = []
for idx, (nl_sent, spaces) in enumerate(nl_chunks):
    # 1) zin met hoverbare woorden
    html_parts.append(render_sentence_with_word_hovers(nl_sent, lookup_word_lower))
    # 2) ℹ icoon direct na de zin (inline)
    ar_sent = ar_sents[idx] if idx < len(ar_sents) else ""
    html_parts.append(make_info_icon(ar_sent, idx))
    # 3) originele spaties terugplaatsen
    html_parts.append(html.escape(spaces))

final_html = "<div style='font-size:20px; line-height:1.9;'>" + "".join(html_parts) + "</div>"
st.markdown(final_html, unsafe_allow_html=True)
