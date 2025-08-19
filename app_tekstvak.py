# app_textvak.py — stabiele versie (tabs, hover, ℹ inline, auto-zinsvertaling zonder widget-conflict)

import streamlit as st
import re, json, html

# --------------------------------------------------
# Streamlit config eerst
# --------------------------------------------------
st.set_page_config(page_title="A1 Lezen — Tekstvak", layout="wide")
st.title("📖 A1 Begrijpend Lezen — Tekst plakken + hover + ℹ per zin")

# --------------------------------------------------
# Session defaults (voordat we widgets maken)
# --------------------------------------------------
for k, v in {
    "nl_text": "",
    "ar_text": "",        # handmatige AR (widget)
    "ar_generated": "",   # automatische AR (geen widget)
    "gloss": {},
}.items():
    st.session_state.setdefault(k, v)

# --------------------------------------------------
# (Optioneel) deep-translator
# --------------------------------------------------
AUTOTRANS_AVAILABLE = False
try:
    from deep_translator import GoogleTranslator  # pip install deep-translator
    AUTOTRANS_AVAILABLE = True
except Exception:
    pass

# --------------------------------------------------
# Ingebouwd basis-lexicon (kern; breid via UI)
# --------------------------------------------------
BASE_LEXICON = {
    "de":"ال","het":"ال","een":"ـٌ/ـًا (نكرة)","en":"و","of":"أو","maar":"لكن","want":"لأن","dus":"لذا",
    "ik":"أنا","jij":"أنت","u":"حضرتك","hij":"هو","zij":"هي","wij":"نحن","jullie":"أنتم","ze":"هم/هن",
    "niet":"لا/ليس","wel":"نعم","is":"يكون","was":"كان","gaat":"يذهب","komen":"يأتي","gaan":"يذهب","blijven":"يبقى",
    "in":"في","op":"على/في","bij":"عند","naar":"إلى","van":"من","met":"مع","zonder":"بدون","voor":"لـ/أمام","achter":"خلف",
    "tussen":"بين","naast":"بجانب","boven":"فوق","onder":"تحت","door":"من خلال/عبر","om":"حول/عند","rond":"حول",
    "hier":"هنا","daar":"هناك","altijd":"دائمًا","nooit":"أبدًا","soms":"أحيانًا","vaak":"غالبًا","nu":"الآن",
    "vandaag":"اليوم","morgen":"غدًا","gisteren":"أمس",
    "brood":"خبز","melk":"حليب","water":"ماء","huis":"بيت","school":"مدرسة","boek":"كتاب","thee":"شاي","koffie":"قهوة",
    "soep":"حساء","rijst":"أرز","kip":"دجاج","groenten":"خضروات","winkel":"متجر","markt":"سوق","bus":"حافلة","halte":"موقف",
    "trein":"قطار","kaartje":"تذكرة","telefoon":"هاتف","bericht":"رسالة","laptop":"حاسوب محمول","keuken":"مطبخ","kamer":"غرفة",
    "open":"مفتوح","dicht":"مغلق","links":"يسار","rechts":"يمين","mooi":"جميل","goed":"جيد","slecht":"سيء","snel":"سريع","langzaam":"بطيء",
}

# --------------------------------------------------
# Helpers
# --------------------------------------------------
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9']+", re.UNICODE)

def split_sents_keep_spaces(text: str):
    """[(zin_met_eindteken, spaties_erachter)] zodat ℹ inline na de zin kan."""
    text = text or ""
    out = []
    i, n = 0, len(text)
    while i < n:
        m = re.search(r"[\.!\?]", text[i:])
        if not m:
            out.append((text[i:], "")); break
        end = i + m.end()
        j = end
        while j < n and text[j].isspace():
            j += 1
        out.append((text[i:end], text[end:j]))
        i = j
    return out or [("", "")]

def tokenize_unique_words(text: str):
    seen, order = set(), []
    for m in WORD_RE.finditer(text or ""):
        w = m.group(0).lower()
        if w not in seen:
            seen.add(w); order.append(w)
    return order

def build_initial_gloss(nl_text: str, base_lexicon: dict):
    return {w: base_lexicon.get(w, "") for w in tokenize_unique_words(nl_text)}

def render_sentence_with_hovers(nl_sentence: str, lookup):
    nl_sentence = nl_sentence or ""
    out, last = [], 0
    for m in WORD_RE.finditer(nl_sentence):
        s, e = m.span()
        out.append(html.escape(nl_sentence[last:s]))
        token = m.group(0)
        tr = lookup(token.lower())
        if tr:
            out.append(f"<span title='{html.escape(tr)}' style='cursor:help'>{html.escape(token)}</span>")
        else:
            out.append(html.escape(token))
        last = e
    out.append(html.escape(nl_sentence[last:]))
    return "".join(out)

def make_info_icon(ar_sentence: str):
    full = (ar_sentence or "—").strip()
    short = (full[:80] + "…") if len(full) > 80 else full
    return (
        "<details style='display:inline;'>"
        f"<summary style='display:inline; cursor:pointer;' title='{html.escape(short)}'>"
        "<span style='color:#3366cc;'> ℹ</span></summary>"
        f"<span style='direction:rtl; text-align:right; background:#f6f7fb; border:1px solid #e7e7ef; "
        "border-radius:10px; padding:6px 8px; margin-left:6px; display:inline-block; font-size:0.95em;'>"
        f"{html.escape(full)}</span></details>"
    )

def translate_sentence(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if AUTOTRANS_AVAILABLE:
        try:
            return GoogleTranslator(source="nl", target="ar").translate(s)
        except Exception:
            try:
                return GoogleTranslator(source="auto", target="ar").translate(s)
            except Exception:
                pass
    # Fallback: woord-voor-woord via gloss/basis
    WORD = re.compile(r"[A-Za-zÀ-ÿ0-9']+", re.UNICODE)
    out, last = [], 0
    for m in WORD.finditer(s):
        out.append(s[last:m.start()])
        tok = m.group(0)
        t = tok.lower()
        out.append(st.session_state.get("gloss", {}).get(t) or BASE_LEXICON.get(t, tok))
        last = m.end()
    out.append(s[last:])
    return "".join(out)

# --------------------------------------------------
# TABS
# --------------------------------------------------
tab1, tab2 = st.tabs(["🧰 Voorbereiden", "📖 Lezen"])

with tab1:
    colL, colR = st.columns([2,1])

    with colL:
        st.text_area("1) Plak Nederlandse tekst", height=220, key="nl_text")
        st.text_area("2) (Optioneel) Arabische zinnen (zelfde volgorde)", height=160, key="ar_text")

    with colR:
        st.markdown("**Basiswoordenlijst uitbreiden (CSV of JSON)**")
        extra = st.text_area("nl,ar  of  {\"de\":\"ال\",...}", height=140, key="extra_lex_raw")
        if st.button("➕ Voeg toe aan basis-lexicon"):
            added = 0
            raw = (extra or "").strip()
            if raw:
                try:
                    if raw.lstrip().startswith("{"):
                        extra_dict = json.loads(raw)
                    else:
                        extra_dict = {}
                        for line in raw.splitlines():
                            line = line.strip()
                            if not line or "," not in line: 
                                continue
                            k, v = line.split(",", 1)
                            extra_dict[k.strip().lower()] = v.strip()
                    for k,v in extra_dict.items():
                        BASE_LEXICON[k.lower()] = v
                        added += 1
                    st.success(f"Toegevoegd: {added} items. Totaal basis: {len(BASE_LEXICON)}")
                except Exception as e:
                    st.error(f"Kon extra lijst niet lezen: {e}")
        st.divider()
        font_prepare = st.slider("Tekstgrootte (voorbereiden)", 16, 30, 20, key="font_prep")
        use_autotrans_words = st.toggle("Auto-aanvullen onbekende woorden (woorden)", value=False and AUTOTRANS_AVAILABLE)

    st.markdown("**3) Woordenlijst (gloss) genereren / bewerken**")
    if st.button("🔁 Gloss opnieuw opbouwen uit tekst"):
        st.session_state["gloss"] = build_initial_gloss(st.session_state.get("nl_text",""), BASE_LEXICON)

    # init gloss (eerste keer)
    if not st.session_state.get("gloss"):
        st.session_state["gloss"] = build_initial_gloss(st.session_state.get("nl_text",""), BASE_LEXICON)

    # auto-aanvullen woordvertalingen
    if use_autotrans_words and AUTOTRANS_AVAILABLE:
        missing = [w for w,v in st.session_state["gloss"].items() if not v]
        if missing:
            with st.spinner("Automatisch vertalen van ontbrekende woorden…"):
                for w in missing:
                    tr = ""
                    try:
                        tr = GoogleTranslator(source="nl", target="ar").translate(w)
                    except Exception:
                        try:
                            tr = GoogleTranslator(source="auto", target="ar").translate(w)
                        except Exception:
                            tr = ""
                    if tr:
                        st.session_state["gloss"][w] = tr

    st.text_area(
        "Gloss (NL→AR) als JSON (bewerk en klik 'Gloss toepassen')",
        value=json.dumps(st.session_state.get("gloss", {}), ensure_ascii=False, indent=2),
        height=260, key="gloss_json"
    )
    cols = st.columns(3)
    with cols[0]:
        if st.button("✅ Gloss toepassen"):
            try:
                st.session_state["gloss"] = json.loads(st.session_state["gloss_json"])
                st.success("Gloss bijgewerkt.")
            except Exception as e:
                st.error(f"Kon JSON niet lezen: {e}")
    with cols[1]:
        st.download_button(
            "⬇ Gloss downloaden (JSON)",
            data=json.dumps(st.session_state.get("gloss", {}), ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="gloss.json",
            mime="application/json",
        )
    with cols[2]:
        up = st.file_uploader("Gloss JSON uploaden", type=["json"], label_visibility="collapsed")
        if up:
            try:
                st.session_state["gloss"] = json.loads(up.read().decode("utf-8"))
                st.success("Gloss geladen.")
            except Exception as e:
                st.error(f"Upload mislukt: {e}")

with tab2:
    st.subheader("Lezen")
    font_read = st.slider("Tekstgrootte (lezen)", 16, 30, 20, key="font_read")

    st.markdown(f"""
    <style>
      .para {{ font-size:{font_read}px; line-height:1.9; }}
      .tok {{ padding:0 1px; border-radius:4px; transition:background .12s ease; }}
      .tok:hover {{ background:rgba(0,0,0,.08); }}
    </style>
    """, unsafe_allow_html=True)

    # Kies bron: ar_generated (auto) > ar_text (handmatig)
    nl_here = st.session_state.get("nl_text", "") or ""
    ar_here = (st.session_state.get("ar_generated") or "").strip() or (st.session_state.get("ar_text") or "").strip()
    gloss = st.session_state.get("gloss", {})

    # Kleine debughulp
    debug = st.checkbox("🔎 Debug tonen", value=False)
    if debug:
        st.write({"len_nl": len(nl_here), "has_ar_generated": bool(st.session_state.get("ar_generated")),
                  "len_ar_text": len(st.session_state.get("ar_text","")), "gloss_items": len(gloss)})

    def lookup_fn(key: str):
        key = (key or "").lower()
        return gloss.get(key) or BASE_LEXICON.get(key, "")

    # Auto-zinnen vertalen -> schrijft naar ar_generated (geen widget!)
    auto_sentences = st.toggle("Zinnen automatisch vertalen (NL→AR)", value=False, key="auto_sentences")
    if auto_sentences and st.button("🔁 Genereer Arabische zinnen"):
        nl_chunks_btn = split_sents_keep_spaces(nl_here)
        nl_sents_btn = [s for (s, _) in nl_chunks_btn]
        with st.spinner("Zinnen vertalen…"):
            ar_lines = [translate_sentence(s) for s in nl_sents_btn]
        st.session_state["ar_generated"] = "\n".join(ar_lines)
        st.success("Arabische zinnen gegenereerd (gebruikt deze pagina).")
        st.rerun()

    # Als er geen NL-tekst is, toon tip en render niet
    if not nl_here.strip():
        st.info("💡 Vul eerst Nederlandse tekst in op tab **Voorbereiden**.")
    else:
        nl_chunks = split_sents_keep_spaces(nl_here)
        ar_sents  = [s for (s, _) in split_sents_keep_spaces(ar_here)]

        parts = []
        for i, (nl_sent, spaces) in enumerate(nl_chunks):
            parts.append(render_sentence_with_hovers(nl_sent, lookup_fn))
            ar_sent = ar_sents[i] if i < len(ar_sents) else ""
            parts.append(make_info_icon(ar_sent))
            parts.append(html.escape(spaces))

        st.markdown("<div class='para'>" + "".join(parts) + "</div>", unsafe_allow_html=True)
