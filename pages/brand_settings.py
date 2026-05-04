import io
import json
import os
from datetime import datetime

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

# ── Global CSS ────────────────────────────────────────────────────────────────
# STYLE LOCK: Do not remove or modify this CSS block.
st.markdown("""
<style>
    /* ── Base font and body ─────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
        color: #374151;
    }

    /* ── Page background ────────────────────────────────────────── */
    .stApp {
        background-color: #F3F4F6;
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

    /* ── Primary buttons — purple ───────────────────────────────── */
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {
        background-color: #7C3AED !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 0.5rem 1.25rem !important;
    }
    .stButton > button[kind="primary"]:hover,
    [data-testid="baseButton-primary"]:hover {
        background-color: #6D28D9 !important;
    }

    /* ── File upload box ─────────────────────────────────────────── */
    [data-testid="stFileUploader"] {
        border: 2px dashed #7C3AED !important;
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
st.title("Brand Settings")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Store brand context so AI insights are tailored to each brand's objectives. "
    "Add notes manually, pull in emails from Gmail, or transcribe meeting recordings."
    "</p>",
    unsafe_allow_html=True,
)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_bm, tab_email, tab_transcript = st.tabs(
    ["📋  Brand Memory", "📧  Email Context", "🎙  Meeting Transcription"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Brand Memory
# ══════════════════════════════════════════════════════════════════════════════
with tab_bm:
    bm = load_brand_memory()
    bm_names = list(bm.keys())

    csv_brands = st.session_state.get("campaign_list", [])
    all_brand_options = bm_names + [b for b in csv_brands if b not in bm_names]

    # ── Add entry form ────────────────────────────────────────────────────────
    st.subheader("Add Entry")

    bm_options  = ["+ Add new brand"] + all_brand_options
    bm_selected = st.selectbox("Select brand", bm_options, key="bm_select")

    if bm_selected == "+ Add new brand":
        bm_new_name = st.text_input("Brand name", key="bm_new_name")
    else:
        bm_new_name = bm_selected

    bm_entry_text = st.text_area(
        "Brand rationale",
        value="",
        height=150,
        help=(
            "Describe this brand's objectives, preferred KPIs, and any context the AI "
            "should use when writing commentary. Each save creates a new dated entry."
        ),
        key="bm_entry_text",
    )

    if st.button("Save", type="primary", key="bm_save"):
        name_to_save = (
            bm_new_name.strip() if bm_selected == "+ Add new brand" else bm_selected
        )
        if not name_to_save:
            st.error("Enter a brand name before saving.")
        elif not bm_entry_text.strip():
            st.error("Enter some rationale text before saving.")
        else:
            brand_data = migrate_brand(bm.get(name_to_save, {}))
            brand_data["entries"].append({
                "type":      "manual",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "text":      bm_entry_text.strip(),
            })
            brand_data["rationale"] = entries_to_rationale(brand_data["entries"])
            bm[name_to_save] = brand_data
            save_brand_memory(bm)
            st.success(f"Entry saved for: {name_to_save}")
            st.rerun()

    # ── Saved brands — entries view ───────────────────────────────────────────
    st.markdown("---")
    st.subheader("Saved Brands")

    if not bm_names:
        st.info("No brands saved yet. Use the form above to add one.")
    else:
        for brand_name, brand_data in bm.items():
            brand_data = migrate_brand(brand_data)
            entries    = brand_data.get("entries", [])

            st.markdown(
                f"<h4 style='color:#111827;margin-bottom:4px;'>{brand_name}</h4>",
                unsafe_allow_html=True,
            )

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
                        badge_color, badge_label = "#2563EB", "Manual"
                    elif entry_type == "transcript":
                        badge_color, badge_label = "#F59E0B", "Transcript"
                    else:
                        badge_color, badge_label = "#7C3AED", "Email"

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

            st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)

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
                        for i in range(len(emails)):
                            st.session_state[f"email_check_{i}"] = True
                    except Exception as e:
                        st.error(f"Gmail error: {e}")

        # ── Email results ─────────────────────────────────────────────────────
        emails      = st.session_state.get("fetched_emails", [])
        brand_query = st.session_state.get("fetched_query", "")

        if emails:
            brand_terms_used = st.session_state.get("fetched_brand_terms", [brand_query])
            terms_display    = ", ".join(f'"{t}"' for t in brand_terms_used)
            st.markdown(
                f"**{len(emails)} email(s) found** &nbsp;·&nbsp; "
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

            h_chk, h_date, h_sender, h_subject, h_snippet = st.columns([0.4, 1.6, 2.5, 2.5, 3.0])
            h_chk.markdown    ("")
            h_date.markdown   ("<small><b>Date</b></small>",    unsafe_allow_html=True)
            h_sender.markdown ("<small><b>From</b></small>",    unsafe_allow_html=True)
            h_subject.markdown("<small><b>Subject</b></small>", unsafe_allow_html=True)
            h_snippet.markdown("<small><b>Snippet</b></small>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:4px 0 8px 0;'>", unsafe_allow_html=True)

            for i, email in enumerate(emails):
                col_chk, col_date, col_sender, col_subject, col_snippet = st.columns(
                    [0.4, 1.6, 2.5, 2.5, 3.0]
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

            # ── Save selected emails to Brand Memory ──────────────────────────
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
            type=["mp3", "mp4", "wav", "m4a", "webm"],
            help="Supported formats: MP3, MP4, WAV, M4A, WEBM. Max 25 MB (OpenAI Whisper limit).",
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
