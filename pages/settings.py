import io
import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from openai import OpenAI

# Gmail imports — wrapped so the page still loads if google libraries aren't installed
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build as google_build
    _GMAIL_AVAILABLE = True
except ImportError:
    _GMAIL_AVAILABLE = False

# Sentence-transformers for semantic email search
# Cached so the model only downloads once per Streamlit session
@st.cache_resource
def load_embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")

# ── Global CSS ────────────────────────────────────────────────────────────────
# STYLE LOCK: Pacebird design system — primary #F5A623 orange, secondary #1B2A4A navy, font Poppins. Do not revert to purple (#7C3AED) or blue (#2563EB).
st.markdown("""
<style>
    /* ── Base font and body ─────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: "Poppins", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
        color: #374151;
    }

    /* ── Page background ────────────────────────────────────────── */
    .stApp {
        background-color: #EEF1F4;
    }

    /* ── Main area headings ──────────────────────────────────────── */
    h1, h2, h3, h4, h5, h6 {
        font-weight: 700 !important;
        color: #111827 !important;
    }
    h2, h3 {
        margin-top: 2rem !important;
        padding-top: 0.25rem !important;
        border-bottom: none !important;
        padding-bottom: 0 !important;
        border-left: none !important;
        padding-left: 0 !important;
    }

    /* ── Primary buttons — orange ───────────────────────────────── */
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {
        background-color: #F5A623 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 0.5rem 1.25rem !important;
    }
    .stButton > button[kind="primary"]:hover,
    [data-testid="baseButton-primary"]:hover {
        background-color: #E8951A !important;
    }

    /* ── File upload box ─────────────────────────────────────────── */
    [data-testid="stFileUploader"] {
        border: 2px dashed #F5A623 !important;
        border-radius: 12px;
        padding: 10px;
        background: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)
# STYLE LOCK

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT             = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND_MEMORY_PATH = os.path.join(_ROOT, "brand_memory.json")
CREDENTIALS_PATH  = os.path.join(_ROOT, "credentials.json")
TOKEN_PATH        = os.path.join(_ROOT, "token.json")

# ── OpenAI API key for Whisper transcription ──────────────────────────────────
try:
    openai_api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
except Exception:
    openai_api_key = os.environ.get("OPENAI_API_KEY")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

DEFAULT_KEYWORDS = [
    "reporting", "insights", "KPI", "strategy", "objectives",
    "brief", "performance", "targets", "goals", "optimisation", "budget", "creative",
]

# ── Shared brand memory helpers ───────────────────────────────────────────────
def load_brand_memory():
    if os.path.exists(BRAND_MEMORY_PATH):
        with open(BRAND_MEMORY_PATH, "r") as f:
            return json.load(f)
    return {}

def save_brand_memory(memory):
    with open(BRAND_MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

def entry_to_text(entry):
    """Convert a single entry dict to a plain-text string for the AI rationale."""
    if entry.get("type") == "email" and "subject" in entry:
        return (
            f"Email [{entry.get('email_date', entry.get('timestamp', ''))}] "
            f"From: {entry.get('sender', '')}\n"
            f"Subject: {entry.get('subject', '')}\n"
            f"Snippet: {entry.get('snippet', '')}"
        )
    return entry.get("text", "")

def entries_to_rationale(entries):
    """Concatenate all entry texts so app.py's rationale read still works."""
    return "\n\n".join(entry_to_text(e) for e in entries)

def migrate_brand(brand_data):
    """Convert old-format brand data (just 'rationale' string) to entries-list format."""
    if "entries" not in brand_data:
        old_text = brand_data.get("rationale", "").strip()
        brand_data["entries"] = (
            [{"type": "manual", "timestamp": "Added before timestamps", "text": old_text}]
            if old_text else []
        )
    return brand_data

# ── Gmail helpers ─────────────────────────────────────────────────────────────
def get_gmail_service():
    """
    Returns an authorised Gmail API service object.
    Uses token.json if valid, refreshes if expired, runs browser OAuth on first use.
    """
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                st.error("credentials.json not found in the project root.")
                st.stop()
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
    return google_build("gmail", "v1", credentials=creds)

def fetch_emails(service, query: str, max_results: int = 10):
    """Search Gmail and return a list of dicts: sender, date, subject, snippet."""
    result = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    emails = []
    for msg in result.get("messages", []):
        full = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Date", "Subject"]
        ).execute()
        headers = {h["name"]: h["value"]
                   for h in full.get("payload", {}).get("headers", [])}
        emails.append({
            "sender":  headers.get("From",    "Unknown sender"),
            "date":    headers.get("Date",    "Unknown date"),
            "subject": headers.get("Subject", "(no subject)"),
            "snippet": full.get("snippet",    ""),
        })
    return emails

# ── Page title ────────────────────────────────────────────────────────────────
st.title("Settings")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Store brand context so AI insights are tailored to each brand's objectives. "
    "Add notes manually, pull in emails from Gmail, or transcribe meeting recordings."
    "</p>",
    unsafe_allow_html=True,
)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_bm, tab_email, tab_transcript, tab5, tab6 = st.tabs(
    ["📋  Brand Memory", "📧  Email Context", "🎙  Meeting Transcription", "📬 Scheduled Reports", "🔔 Alert Settings"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Brand Memory
# ══════════════════════════════════════════════════════════════════════════════
with tab_bm:
    bm = load_brand_memory()
    bm_names = list(bm.keys())

    csv_brands = st.session_state.get("campaign_list", [])
    all_brand_options = bm_names + [b for b in csv_brands if b not in bm_names]

    # ── Add / edit brand form ─────────────────────────────────────────────────
    st.subheader("Add Entry")

    bm_options  = ["+ Add new brand"] + all_brand_options
    bm_selected = st.selectbox("Select brand", bm_options, key="bm_select")

    _adding_new = bm_selected == "+ Add new brand"

    if _adding_new:
        # New brand — show name field and empty text area
        bm_new_name        = st.text_input("Brand name", key="bm_new_name")
        _existing_logic    = ""
        _btn_label         = "Save"
    else:
        # Existing brand — hide name field, pre-populate text area with saved logic
        bm_new_name     = bm_selected
        _brand_data_pre = migrate_brand(bm.get(bm_selected, {}))
        _existing_logic = _brand_data_pre.get("rationale", "")
        _btn_label      = "Update"

    bm_entry_text = st.text_area(
        "Logic",
        value=_existing_logic,
        height=150,
        help=(
            "Describe this brand's objectives, preferred KPIs, and any context the AI "
            "should use when writing commentary."
        ),
        key="bm_entry_text",
    )

    if st.button(_btn_label, type="primary", key="bm_save"):
        name_to_save = bm_new_name.strip() if _adding_new else bm_selected
        if not name_to_save:
            st.error("Enter a brand name before saving.")
        elif not bm_entry_text.strip():
            st.error("Enter some logic text before saving.")
        else:
            brand_data = migrate_brand(bm.get(name_to_save, {}))
            if _adding_new:
                # Append a new entry for a new brand
                brand_data["entries"].append({
                    "type":      "manual",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "text":      bm_entry_text.strip(),
                })
            else:
                # Update: replace all manual entries with the edited text,
                # keeping email and transcript entries intact
                non_manual = [e for e in brand_data["entries"] if e.get("type") != "manual"]
                brand_data["entries"] = non_manual + [{
                    "type":      "manual",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "text":      bm_entry_text.strip(),
                }]
            brand_data["rationale"] = entries_to_rationale(brand_data["entries"])
            bm[name_to_save] = brand_data
            save_brand_memory(bm)
            st.success(f"{'Saved' if _adding_new else 'Updated'}: {name_to_save}")
            st.rerun()

    # Delete button — only shown when editing an existing brand
    if not _adding_new:
        st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
        if st.button("🗑 Delete Brand", key="bm_delete_brand"):
            fresh_bm = load_brand_memory()
            if bm_selected in fresh_bm:
                del fresh_bm[bm_selected]
                save_brand_memory(fresh_bm)
                st.success(f"Deleted brand: {bm_selected}")
                st.rerun()

    # ── Saved brands — one collapsible expander per brand ────────────────────
    st.markdown("---")
    _saved_title = f"Saved Brands ({len(bm_names)})" if bm_names else "Saved Brands"
    st.subheader(_saved_title)

    if not bm_names:
        st.info("No brands saved yet. Use the form above to add one.")
    else:
        for brand_name, brand_data in bm.items():
            brand_data = migrate_brand(brand_data)
            entries    = brand_data.get("entries", [])

            # Each brand is its own collapsible — collapsed by default
            entry_count = len(entries)
            _brand_label = (
                f"{brand_name}  ·  {entry_count} {'entry' if entry_count == 1 else 'entries'}"
            )
            with st.expander(_brand_label, expanded=False):
                if not entries:
                    st.caption("No entries yet.")
                else:
                    for i, entry in enumerate(entries):
                        entry_type   = entry.get("type", "manual")
                        is_new_email = entry_type == "email" and "subject" in entry

                        if is_new_email:
                            display_date = entry.get("email_date", entry.get("timestamp", ""))
                        else:
                            display_date = entry.get("timestamp", "")

                        if entry_type == "manual":
                            badge_color, badge_label = "#1B2A4A", "Manual"
                        elif entry_type == "transcript":
                            badge_color, badge_label = "#F59E0B", "Transcript"
                        else:
                            badge_color, badge_label = "#F5A623", "Email"

                        col_info, col_btn = st.columns([9, 1])

                        with col_info:
                            if is_new_email:
                                body_html = (
                                    f"<p style='margin:6px 0 0 0;font-size:13px;color:#374151;'>"
                                    f"<b>From:</b> {entry.get('sender', '')}</p>"
                                    f"<p style='margin:2px 0 0 0;font-size:13px;color:#374151;'>"
                                    f"<b>Subject:</b> {entry.get('subject', '')}</p>"
                                    f"<p style='margin:2px 0 0 0;font-size:13px;color:#6b7280;'>"
                                    f"{entry.get('snippet', '')}</p>"
                                )
                            else:
                                text_escaped = entry.get("text", "").replace("<", "&lt;")
                                body_html = (
                                    f"<p style='margin:8px 0 0 0;font-size:13px;color:#111111;"
                                    f"white-space:pre-wrap;'>{text_escaped}</p>"
                                )

                            st.markdown(
                                f"<div style='border:1px solid #E5E7EB;border-radius:8px;"
                                f"padding:10px 14px;margin-bottom:6px;background:#FFFFFF;"
                                f"box-shadow:0 1px 2px rgba(0,0,0,0.05);'>"
                                f"<span style='font-size:11px;font-weight:700;color:#ffffff;"
                                f"background:{badge_color};padding:2px 8px;border-radius:12px;"
                                f"margin-right:8px;'>{badge_label}</span>"
                                f"<span style='font-size:12px;color:#6b7280;'>{display_date}</span>"
                                + body_html +
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                        with col_btn:
                            st.markdown("<div style='margin-top:4px;'></div>",
                                        unsafe_allow_html=True)
                            if st.button("🗑 Delete", key=f"del_{brand_name}_{i}"):
                                fresh_bm   = load_brand_memory()
                                fresh_data = migrate_brand(fresh_bm.get(brand_name, {}))
                                fresh_data["entries"].pop(i)
                                if fresh_data["entries"]:
                                    fresh_data["rationale"] = entries_to_rationale(
                                        fresh_data["entries"]
                                    )
                                    fresh_bm[brand_name] = fresh_data
                                else:
                                    del fresh_bm[brand_name]
                                save_brand_memory(fresh_bm)
                                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Email Context
# ══════════════════════════════════════════════════════════════════════════════
with tab_email:
    st.markdown(
        "<p style='color:#6b7280;font-size:14px;'>"
        "Search your Gmail for brand or client emails and save key context to Brand Memory."
        "</p>",
        unsafe_allow_html=True,
    )

    if not _GMAIL_AVAILABLE:
        st.warning(
            "Gmail libraries not installed. Run: "
            "`pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`"
        )
    else:
        # ── Search form ───────────────────────────────────────────────────────
        st.subheader("Search Emails")

        _bm_for_search  = load_brand_memory()
        _search_options = list(_bm_for_search.keys()) + ["+ Type a new name"]

        _search_selected = st.selectbox(
            "Brand / client name",
            _search_options,
            help="Pick an existing brand or choose '+ Type a new name' to search for something new.",
            key="search_brand_select",
        )

        if _search_selected == "+ Type a new name":
            search_query = st.text_input(
                "Type brand / client name",
                placeholder="e.g. Coke",
                key="search_brand_custom",
            )
        else:
            search_query = _search_selected

        selected_keywords = st.multiselect(
            "Filter by keywords (optional)",
            options=DEFAULT_KEYWORDS,
            default=[],
            help=(
                "Select keywords to narrow results. Only emails containing the brand name "
                "AND at least one selected keyword will be returned."
            ),
        )

        custom_keyword_input = st.text_input(
            "Additional custom keywords (optional)",
            placeholder="e.g. Q3 review, campaign launch",
            help="Comma-separated. Combined with any keywords selected above.",
        )

        if st.button("Fetch Emails", type="primary", key="fetch_btn"):
            if not search_query.strip():
                st.warning("Enter a brand or client name to search.")
            else:
                all_keywords = list(selected_keywords)
                for k in custom_keyword_input.split(","):
                    k = k.strip()
                    if k and k not in all_keywords:
                        all_keywords.append(k)

                # Expand brand name into individual words > 3 chars for broader matching
                brand_name_clean = search_query.strip()
                brand_terms = [brand_name_clean]
                for word in brand_name_clean.split():
                    if len(word) > 3 and word.lower() != brand_name_clean.lower():
                        brand_terms.append(word)

                if len(brand_terms) > 1:
                    brand_part = "(" + " OR ".join(f'"{t}"' for t in brand_terms) + ")"
                else:
                    brand_part = f'"{brand_terms[0]}"'

                if all_keywords:
                    kw_part     = " OR ".join(f'"{k}"' for k in all_keywords)
                    gmail_query = f"{brand_part} ({kw_part})"
                else:
                    gmail_query = brand_part

                with st.spinner("Connecting to Gmail…"):
                    try:
                        service = get_gmail_service()
                        emails  = fetch_emails(service, gmail_query)
                        st.session_state["fetched_emails"]      = emails
                        st.session_state["fetched_query"]       = brand_name_clean
                        st.session_state["fetched_brand_terms"] = brand_terms
                        st.session_state["_emails_scored"]      = False  # trigger re-scoring
                        for i in range(len(emails)):
                            st.session_state[f"email_check_{i}"] = True
                    except Exception as e:
                        st.error(f"Gmail error: {e}")

        # ── Semantic similarity scoring ────────────────────────────────────────────
        # Runs immediately after Fetch Emails. Embeds the search query and all
        # email subject+snippets, scores them with cosine similarity, then stores
        # ALL scored emails (unfiltered) in session state. The threshold slider
        # below re-filters the list dynamically without re-fetching from Gmail.
        if st.session_state.get("fetched_emails") and not st.session_state.get("_emails_scored"):
            _raw_emails = st.session_state["fetched_emails"]

            try:
                with st.spinner("Scoring email relevance…"):
                    from sklearn.metrics.pairwise import cosine_similarity
                    import numpy as np

                    _model = load_embedding_model()

                    # Embed the search query
                    _query_embedding = _model.encode(search_query)

                    # Embed all email subject + snippet texts in one batch
                    _email_texts = [
                        f"{e.get('subject', '')} {e.get('snippet', '')}"
                        for e in _raw_emails
                    ]
                    _email_embeddings = _model.encode(_email_texts)

                    # Cosine similarity: shape (1, n_emails) → flatten to list
                    _scores = cosine_similarity([_query_embedding], _email_embeddings)[0]

                    # Attach similarity score to each email dict, then sort high-to-low
                    for _i, _e in enumerate(_raw_emails):
                        _e["_similarity"] = round(float(_scores[_i]), 3)

                    _raw_emails.sort(key=lambda e: e.get("_similarity", 0), reverse=True)

                    # Store scored (but not yet threshold-filtered) list
                    st.session_state["fetched_emails"]  = _raw_emails
                    st.session_state["_emails_scored"]  = True

            except Exception as _sem_err:
                st.caption(f"Semantic scoring unavailable: {_sem_err}")
                for _e in _raw_emails:
                    _e.setdefault("_similarity", None)
                st.session_state["_emails_scored"] = True

        # ── Email results ─────────────────────────────────────────────────────
        _all_scored = st.session_state.get("fetched_emails", [])
        brand_query = st.session_state.get("fetched_query", "")

        if _all_scored:
            brand_terms_used = st.session_state.get("fetched_brand_terms", [brand_query])
            terms_display    = ", ".join(f'"{t}"' for t in brand_terms_used)

            # ── Relevance threshold slider ────────────────────────────────────
            # Adjusting the slider re-filters the scored list instantly — no
            # new Gmail request needed.
            _threshold = st.slider(
                "Relevance threshold",
                min_value=0.10,
                max_value=0.80,
                value=0.25,
                step=0.05,
                help="Only emails with a similarity score at or above this value are shown.",
                key="relevance_threshold",
            )

            # Apply threshold filter
            emails = [e for e in _all_scored if e.get("_similarity", 0) >= _threshold]

            if emails:
                st.markdown(
                    f"**{len(emails)} email(s) matched** &nbsp;·&nbsp; "
                    f"<span style='color:#6b7280;font-size:13px;'>Searched for: {terms_display}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("---")

                sel_col1, sel_col2, _ = st.columns([1, 1, 8])
                with sel_col1:
                    if st.button("Select All", key="sel_all"):
                        for i in range(len(emails)):
                            st.session_state[f"email_check_{i}"] = True
                        st.rerun()
                with sel_col2:
                    if st.button("Deselect All", key="desel_all"):
                        for i in range(len(emails)):
                            st.session_state[f"email_check_{i}"] = False
                        st.rerun()

                h_chk, h_date, h_sender, h_subject, h_snippet, h_match = st.columns([0.4, 1.6, 2.5, 2.5, 2.8, 0.7])
                h_chk.markdown    ("")
                h_date.markdown   ("<small><b>Date</b></small>",    unsafe_allow_html=True)
                h_sender.markdown ("<small><b>From</b></small>",    unsafe_allow_html=True)
                h_subject.markdown("<small><b>Subject</b></small>", unsafe_allow_html=True)
                h_snippet.markdown("<small><b>Snippet</b></small>", unsafe_allow_html=True)
                h_match.markdown  ("<small><b>Match</b></small>",   unsafe_allow_html=True)
                st.markdown("<hr style='margin:4px 0 8px 0;'>", unsafe_allow_html=True)

                for i, email in enumerate(emails):
                    col_chk, col_date, col_sender, col_subject, col_snippet, col_match = st.columns(
                        [0.4, 1.6, 2.5, 2.5, 2.8, 0.7]
                    )
                    with col_chk:
                        st.checkbox("", key=f"email_check_{i}", label_visibility="collapsed")
                    with col_date:
                        st.markdown(
                            f"<small style='color:#374151;'>{email['date'][:16]}</small>",
                            unsafe_allow_html=True,
                        )
                    with col_sender:
                        s = email["sender"]
                        sender_display = s[:35] + "…" if len(s) > 35 else s
                        st.markdown(
                            f"<small style='color:#374151;'>{sender_display}</small>",
                            unsafe_allow_html=True,
                        )
                    with col_subject:
                        st.markdown(
                            f"<small style='color:#111111;font-weight:600;'>{email['subject']}</small>",
                            unsafe_allow_html=True,
                        )
                    with col_snippet:
                        snip = email["snippet"]
                        snip_display = snip[:100] + "…" if len(snip) > 100 else snip
                        st.markdown(
                            f"<small style='color:#6b7280;'>{snip_display}</small>",
                            unsafe_allow_html=True,
                        )
                    with col_match:
                        # Colour-coded similarity badge: green 80%+, blue 60-79%, grey 25-59%
                        _score = email.get("_similarity")
                        if _score is not None:
                            _pct = int(_score * 100)
                            if _pct >= 80:
                                _badge_bg, _badge_fg = "#D1FAE5", "#065F46"   # green
                            elif _pct >= 60:
                                _badge_bg, _badge_fg = "#DBEAFE", "#1E40AF"   # blue
                            else:
                                _badge_bg, _badge_fg = "#F3F4F6", "#6B7280"   # grey
                            _match_str = f"Match: {_pct}%"
                        else:
                            _badge_bg, _badge_fg = "#F3F4F6", "#6B7280"
                            _match_str = "—"
                        st.markdown(
                            f"<span style='background:{_badge_bg};color:{_badge_fg};"
                            f"padding:2px 7px;border-radius:10px;font-size:11px;"
                            f"font-weight:700;white-space:nowrap;'>{_match_str}</span>",
                            unsafe_allow_html=True,
                        )

            else:
                # No emails above the threshold
                st.info(
                    "No semantically similar emails found. "
                    "Try lowering the relevance threshold or using different search terms."
                )

            # ── Save selected emails to Brand Memory ──────────────────────────
            if emails:
                st.markdown("---")
            st.subheader("Save to Brand Memory")

            bm_current   = load_brand_memory()
            bm_names_now = list(bm_current.keys())
            save_options = bm_names_now + ["+ Type new brand name"]

            save_brand_selected = st.selectbox(
                "Save under brand",
                save_options,
                help=(
                    "Choose an existing brand to consolidate emails there, "
                    "or select '+ Type new brand name' to create a new entry."
                ),
                key="save_brand_select",
            )

            if save_brand_selected == "+ Type new brand name":
                bm_name = st.text_input(
                    "New brand name",
                    placeholder="e.g. Coke Festive Campaign",
                    help="Must match the campaign name in your CSV for insights to pick it up.",
                    key="bm_name_new",
                )
            else:
                bm_name = save_brand_selected

            if st.button("Save Selected to Brand Memory", type="primary", key="save_bm_btn"):
                selected = [
                    emails[i] for i in range(len(emails))
                    if st.session_state.get(f"email_check_{i}")
                ]
                if not selected:
                    st.warning("No emails selected. Tick at least one email above.")
                elif not bm_name.strip():
                    st.warning("Enter a brand name to save under.")
                else:
                    save_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                    bm         = load_brand_memory()
                    brand_data = migrate_brand(bm.get(bm_name.strip(), {}))
                    for email in selected:
                        brand_data["entries"].append({
                            "type":       "email",
                            "timestamp":  save_timestamp,
                            "email_date": email["date"],
                            "sender":     email["sender"],
                            "subject":    email["subject"],
                            "snippet":    email["snippet"][:200],
                        })
                    brand_data["rationale"] = entries_to_rationale(brand_data["entries"])
                    bm[bm_name.strip()]     = brand_data
                    save_brand_memory(bm)
                    st.success(
                        f"Saved {len(selected)} email(s) to Brand Memory under '{bm_name.strip()}'."
                    )

        elif st.session_state.get("fetched_emails") is not None:
            st.info("No emails found. Try a different brand name or fewer keywords.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Meeting Transcription
# ══════════════════════════════════════════════════════════════════════════════
with tab_transcript:
    st.markdown(
        "<p style='color:#6b7280;font-size:14px;'>"
        "Upload a meeting recording and transcribe it with OpenAI Whisper. "
        "Save the transcript directly to Brand Memory."
        "</p>",
        unsafe_allow_html=True,
    )

    if not openai_api_key:
        st.warning(
            "No OpenAI API key found. Add `OPENAI_API_KEY` to your "
            "Streamlit secrets or environment variables to enable transcription."
        )
    else:
        # ── Upload and brand selector ─────────────────────────────────────────
        st.subheader("Upload Recording")

        uploaded_audio = st.file_uploader(
            "Choose an audio or video file",
            type=["mp3", "mp4", "wav", "m4a", "webm", "mpeg4", "mkv", "mov", "ogg"],
            help="Supported formats: MP3, MP4, WAV, M4A, WEBM, MPEG4, MKV, MOV, OGG. Max 25 MB (OpenAI Whisper limit). MKV files are automatically converted to MP3 before transcription.",
        )

        _bm_t        = load_brand_memory()
        _bm_names_t  = list(_bm_t.keys())
        _csv_brands  = st.session_state.get("campaign_list", [])
        _all_brands  = _bm_names_t + [b for b in _csv_brands if b not in _bm_names_t]
        brand_options = _all_brands + ["+ Type a new brand name"]

        brand_selected = st.selectbox(
            "Associate with brand",
            brand_options,
            help="The transcript will be saved under this brand in Brand Memory.",
            key="mt_brand_select",
        )

        if brand_selected == "+ Type a new brand name":
            brand_name = st.text_input(
                "New brand name",
                placeholder="e.g. Nike Summer 2024",
                key="mt_brand_new",
            )
        else:
            brand_name = brand_selected

        # ── Transcribe ────────────────────────────────────────────────────────
        if st.button("Transcribe", type="primary", key="transcribe_btn"):
            if not uploaded_audio:
                st.warning("Upload an audio or video file first.")
            elif not brand_name or not brand_name.strip():
                st.warning("Select or enter a brand name.")
            else:
                with st.spinner("Transcribing with OpenAI Whisper…"):
                    try:
                        client = OpenAI(api_key=openai_api_key)
                        audio_bytes  = uploaded_audio.read()

                        # MKV is not accepted by Whisper — convert to MP3 via pydub first
                        if uploaded_audio.name.lower().endswith(".mkv"):
                            from pydub import AudioSegment
                            mkv_buffer = io.BytesIO(audio_bytes)
                            audio_segment = AudioSegment.from_file(mkv_buffer, format="mkv")
                            mp3_buffer = io.BytesIO()
                            audio_segment.export(mp3_buffer, format="mp3")
                            mp3_buffer.seek(0)
                            audio_buffer = mp3_buffer
                            audio_buffer.name = uploaded_audio.name.rsplit(".", 1)[0] + ".mp3"
                        else:
                            audio_buffer = io.BytesIO(audio_bytes)
                            audio_buffer.name = uploaded_audio.name

                        result = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_buffer,
                        )
                        st.session_state["transcript_text"]        = result.text
                        st.session_state["transcript_brand"]       = brand_name.strip()
                        st.session_state["transcript_file"]        = uploaded_audio.name
                        st.session_state["transcript_audio_bytes"] = audio_bytes
                        st.session_state["transcript_audio_mime"]  = uploaded_audio.type
                    except Exception as e:
                        st.error(f"Transcription error: {e}")

        # STYLE LOCK: Do not change transcript display formatting
        # ── Display transcript ────────────────────────────────────────────────
        transcript = st.session_state.get("transcript_text", "")

        if transcript:
            st.markdown("---")
            st.subheader("Transcript")

            saved_brand = st.session_state.get("transcript_brand", "")
            saved_file  = st.session_state.get("transcript_file", "")

            st.markdown(
                f"<p style='font-size:12px;color:#6b7280;margin-bottom:12px;'>"
                f"File: <b>{saved_file}</b> &nbsp;·&nbsp; Brand: <b>{saved_brand}</b>"
                f"</p>",
                unsafe_allow_html=True,
            )

            # Audio player and download button
            audio_bytes_stored = st.session_state.get("transcript_audio_bytes")
            audio_mime_stored  = st.session_state.get("transcript_audio_mime", "audio/mpeg")

            if audio_bytes_stored:
                st.audio(audio_bytes_stored, format=audio_mime_stored)
                st.download_button(
                    label="⬇ Download Audio",
                    data=audio_bytes_stored,
                    file_name=saved_file,
                    mime=audio_mime_stored,
                    key="mt_download_audio",
                )

            st.markdown(
                f"<div style='background:#FFFFFF;border:1px solid #E5E7EB;border-radius:8px;"
                f"padding:16px 20px;font-size:14px;color:#374151;line-height:1.7;"
                f"max-height:420px;overflow-y:auto;white-space:pre-wrap;"
                f"box-shadow:0 1px 3px rgba(0,0,0,0.1);'>"
                f"{transcript}"
                f"</div>",
                unsafe_allow_html=True,
            )

            # ── Save to Brand Memory ──────────────────────────────────────────
            st.markdown("---")
            st.subheader("Save to Brand Memory")

            _bm_t2       = load_brand_memory()
            _bm_names_t2 = list(_bm_t2.keys())
            _csv_b2      = st.session_state.get("campaign_list", [])
            _all_b2      = _bm_names_t2 + [b for b in _csv_b2 if b not in _bm_names_t2]
            save_brand_options   = _all_b2 + ["+ Type a new brand name"]
            save_brand_selected  = st.selectbox(
                "Save under brand",
                save_brand_options,
                index=save_brand_options.index(saved_brand) if saved_brand in save_brand_options else 0,
                key="mt_save_brand_select",
            )

            if save_brand_selected == "+ Type a new brand name":
                save_brand_name = st.text_input(
                    "New brand name",
                    placeholder="e.g. Nike Summer 2024",
                    key="mt_save_brand_new",
                )
            else:
                save_brand_name = save_brand_selected

            if st.button("Save to Brand Memory", type="primary", key="mt_save_btn"):
                if not save_brand_name or not save_brand_name.strip():
                    st.warning("Select or enter a brand name to save under.")
                else:
                    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M")
                    entry_text = (
                        f"Meeting transcript (saved {timestamp}, file: '{saved_file}'):\n\n"
                        f"{transcript}"
                    )
                    fresh_bm   = load_brand_memory()
                    brand_data = migrate_brand(fresh_bm.get(save_brand_name.strip(), {}))
                    brand_data["entries"].append({
                        "type":      "transcript",
                        "timestamp": timestamp,
                        "text":      entry_text,
                    })
                    brand_data["rationale"] = entries_to_rationale(brand_data["entries"])
                    fresh_bm[save_brand_name.strip()] = brand_data
                    save_brand_memory(fresh_bm)
                    st.success(
                        f"Transcript saved to Brand Memory under '{save_brand_name.strip()}'."
                    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Scheduled Reports
# ══════════════════════════════════════════════════════════════════════════════
# ── Tab 5: Scheduled Reports ──────────────────────────────────────────────────
with tab5:
    st.markdown("## 📬 Scheduled Reports")
    st.markdown("Configure automated report delivery. Settings are saved here — connect to APScheduler or a cron service for live delivery.")

    st.warning("⚠️ Scheduled delivery requires server deployment. Configure settings here — your IT team or developer can connect to APScheduler or a cron service.")

    SCHEDULE_FILE = "scheduled_reports.json"

    def load_schedules():
        if os.path.exists(SCHEDULE_FILE):
            try:
                with open(SCHEDULE_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_schedules(schedules):
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(schedules, f, indent=2)

    bm_for_sched = load_brand_memory()
    brand_names_for_sched = list(bm_for_sched.keys())

    with st.form("schedule_form"):
        st.markdown("### ➕ Add Report Schedule")

        sched_brand = st.selectbox(
            "Brand / Advertiser",
            ["All Brands"] + brand_names_for_sched,
            key="sched_brand"
        )

        sched_email = st.text_input(
            "Recipient email address",
            placeholder="client@agency.com",
            key="sched_email"
        )

        sched_freq = st.selectbox(
            "Report frequency",
            ["Weekly — Monday 9am", "Bi-weekly", "Monthly"],
            key="sched_freq"
        )

        sched_content = st.multiselect(
            "Report content",
            ["Summary metrics", "Charts", "AI insights", "KPI RAG status"],
            default=["Summary metrics", "Charts", "AI insights"],
            key="sched_content"
        )

        save_sched = st.form_submit_button("💾 Save Schedule", type="primary")

        if save_sched:
            if not sched_email:
                st.error("Please enter a recipient email address.")
            else:
                schedules = load_schedules()
                schedules.append({
                    "brand": sched_brand,
                    "email": sched_email,
                    "frequency": sched_freq,
                    "content": sched_content,
                    "created": str(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")),
                    "active": True
                })
                save_schedules(schedules)
                st.success(f"✅ Schedule saved for {sched_brand} → {sched_email}")

    # Show existing schedules
    schedules_list = load_schedules()
    if schedules_list:
        st.markdown("### 📋 Saved Schedules")
        for i, sched in enumerate(schedules_list):
            with st.expander(f"{sched.get('brand', 'All')} — {sched.get('frequency', '')} → {sched.get('email', '')}", expanded=False):
                st.markdown(f"**Brand:** {sched.get('brand', 'All Brands')}")
                st.markdown(f"**Email:** {sched.get('email', '')}")
                st.markdown(f"**Frequency:** {sched.get('frequency', '')}")
                st.markdown(f"**Content:** {', '.join(sched.get('content', []))}")
                st.markdown(f"**Created:** {sched.get('created', '')}")

                if st.button(f"🗑 Delete schedule", key=f"del_sched_{i}"):
                    schedules_list.pop(i)
                    save_schedules(schedules_list)
                    st.rerun()
    else:
        st.info("No schedules configured yet.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Alert Settings
# Configure campaign alert thresholds and delivery methods
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("## 🔔 Alert Settings")
    st.markdown("Configure alert thresholds for campaign pacing. Alerts are shown as banners in Live Campaigns.")
    st.warning("⚠️ Live alert delivery requires server infrastructure. Configure settings here for production deployment.")

    ALERT_SETTINGS_FILE = os.path.join(_ROOT, "alert_settings.json")

    def load_alert_settings():
        if os.path.exists(ALERT_SETTINGS_FILE):
            try:
                with open(ALERT_SETTINGS_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_alert_settings(settings):
        with open(ALERT_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)

    alert_cfg = load_alert_settings()

    with st.form("alert_settings_form"):
        alert_method = st.selectbox(
            "Alert method",
            ["Email", "Slack", "Both"],
            index=["Email", "Slack", "Both"].index(alert_cfg.get("method", "Email"))
        )

        col_alert1, col_alert2 = st.columns(2)
        with col_alert1:
            alert_email_addr = st.text_input(
                "Email address",
                value=alert_cfg.get("email", ""),
                placeholder="ops@agency.com",
            )
        with col_alert2:
            alert_slack_url = st.text_input(
                "Slack webhook URL",
                value=alert_cfg.get("slack_webhook", ""),
                placeholder="https://hooks.slack.com/...",
            )

        alert_threshold = st.selectbox(
            "Alert threshold",
            ["Any Critical campaign", "Critical + At Risk", "Pacing below threshold %"],
            index=["Any Critical campaign", "Critical + At Risk", "Pacing below threshold %"].index(
                alert_cfg.get("threshold", "Any Critical campaign")
            )
        )

        pacing_threshold_val = 75
        if alert_threshold == "Pacing below threshold %":
            pacing_threshold_val = st.number_input(
                "Pacing threshold %", min_value=10, max_value=100,
                value=int(alert_cfg.get("pacing_threshold_value", 75))
            )

        save_alerts = st.form_submit_button("💾 Save Alert Settings", type="primary")
        if save_alerts:
            save_alert_settings({
                "method": alert_method,
                "email": alert_email_addr,
                "slack_webhook": alert_slack_url,
                "threshold": alert_threshold,
                "pacing_threshold_value": pacing_threshold_val,
            })
            st.success("✅ Alert settings saved.")

    # Show current settings summary
    current_alerts = load_alert_settings()
    if current_alerts:
        st.markdown("**Current configuration:**")
        st.markdown(f"- **Method:** {current_alerts.get('method', '—')}")
        st.markdown(f"- **Email:** {current_alerts.get('email', '—')}")
        st.markdown(f"- **Threshold:** {current_alerts.get('threshold', '—')}")
        if current_alerts.get("slack_webhook"):
            st.markdown(f"- **Slack:** Configured ✅")

# ── Access Tier section (visible only when current_tier is "full_access") ─────
_current_tier = st.session_state.get("current_tier", "full_access")
if _current_tier == "full_access":
    st.markdown("---")
    st.markdown("## 🔑 Access Tier")
    st.markdown("Control which navigation sections are visible. Use this to demo different client access levels.")

    _CONFIG_FILE = os.path.join(_ROOT, "config.json")

    def _load_config():
        if os.path.exists(_CONFIG_FILE):
            try:
                with open(_CONFIG_FILE, "r") as _f:
                    return json.load(_f)
            except Exception:
                pass
        return {"current_tier": "full_access"}

    def _save_config(c):
        with open(_CONFIG_FILE, "w") as _f:
            json.dump(c, _f, indent=2)

    _cfg = _load_config()
    _tier_options = ["full_access", "api_only", "upload_only"]
    _tier_labels  = {
        "full_access":  "✨ Full Access — show API Data, Upload Report and Audiences & Deals Pipeline",
        "api_only":     "📡 API Data Only — hide Upload Report",
        "upload_only":  "📁 Upload Report Only — hide API Data",
    }
    _current_idx = _tier_options.index(_cfg.get("current_tier", "full_access"))

    _selected_tier = st.selectbox(
        "Select access tier",
        options=_tier_options,
        index=_current_idx,
        format_func=lambda t: _tier_labels.get(t, t),
        key="access_tier_select"
    )

    if st.button("💾 Apply Access Tier", type="primary", key="apply_tier_btn"):
        _cfg["current_tier"] = _selected_tier
        _save_config(_cfg)
        st.success(f"✅ Tier updated to: {_tier_labels.get(_selected_tier, _selected_tier)}")
        st.info("Reload the app to see the updated navigation.")

print("Done. Settings page loaded.")
