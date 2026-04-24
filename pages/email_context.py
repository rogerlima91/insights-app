import json
import os
from datetime import datetime

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Email Context", layout="wide")

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT             = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH  = os.path.join(_ROOT, "credentials.json")
TOKEN_PATH        = os.path.join(_ROOT, "token.json")
BRAND_MEMORY_PATH = os.path.join(_ROOT, "brand_memory.json")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Default keywords shown in the multi-select list
DEFAULT_KEYWORDS = [
    "reporting", "insights", "KPI", "strategy", "objectives",
    "brief", "performance", "targets", "goals", "optimisation", "budget", "creative",
]

# ── Brand memory helpers ──────────────────────────────────────────────────────
def load_brand_memory():
    if os.path.exists(BRAND_MEMORY_PATH):
        with open(BRAND_MEMORY_PATH, "r") as f:
            return json.load(f)
    return {}

def save_brand_memory(memory):
    with open(BRAND_MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

def entry_to_text(entry):
    """
    Convert a single entry dict to a plain-text string for the AI rationale.
    Email entries (new per-email format) are formatted from their individual fields.
    Manual entries and legacy bundled email entries use their stored 'text' field.
    """
    if entry.get("type") == "email" and "subject" in entry:
        return (
            f"Email [{entry.get('email_date', entry.get('timestamp', ''))}] "
            f"From: {entry.get('sender', '')}\n"
            f"Subject: {entry.get('subject', '')}\n"
            f"Snippet: {entry.get('snippet', '')}"
        )
    return entry.get("text", "")

def entries_to_rationale(entries):
    """Concatenate all entries so app.py's rationale read still works."""
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

# ── Gmail auth ────────────────────────────────────────────────────────────────
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
    return build("gmail", "v1", credentials=creds)

# ── Email fetcher ─────────────────────────────────────────────────────────────
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
st.title("Email Context")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Search your Gmail for brand or client emails and save key context to Brand Memory."
    "</p>",
    unsafe_allow_html=True,
)

# ── Search form ───────────────────────────────────────────────────────────────
st.subheader("Search Emails")

# Load brands from brand_memory.json so the user can pick one instead of typing
_bm_for_search   = load_brand_memory()
_search_options  = list(_bm_for_search.keys()) + ["+ Type a new name"]

_search_selected = st.selectbox(
    "Brand / client name",
    _search_options,
    help="Pick an existing brand from Brand Memory, or choose '+ Type a new name' to search for something new.",
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

# Multi-select list of default keywords
selected_keywords = st.multiselect(
    "Filter by keywords (optional)",
    options=DEFAULT_KEYWORDS,
    default=[],
    help=(
        "Select keywords to narrow results. Only emails containing the brand name "
        "AND at least one selected keyword will be returned."
    ),
)

# Free-text field for any keywords not in the default list
custom_keyword_input = st.text_input(
    "Additional custom keywords (optional)",
    placeholder="e.g. Q3 review, campaign launch",
    help="Comma-separated. Combined with any keywords selected above.",
)

if st.button("Fetch Emails", type="primary", key="fetch_btn"):
    if not search_query.strip():
        st.warning("Enter a brand or client name to search.")
    else:
        # Merge multiselect keywords with any custom typed ones
        all_keywords = list(selected_keywords)
        for k in custom_keyword_input.split(","):
            k = k.strip()
            if k and k not in all_keywords:
                all_keywords.append(k)

        # Build brand search terms: full name PLUS each individual word > 3 characters.
        # e.g. "Coke Festive Campaign" → ["Coke Festive Campaign", "Coke", "Festive", "Campaign"]
        # This catches emails that mention only part of the brand name.
        brand_name_clean = search_query.strip()
        brand_terms = [brand_name_clean]
        for word in brand_name_clean.split():
            if len(word) > 3 and word.lower() != brand_name_clean.lower():
                brand_terms.append(word)

        # OR all brand terms together in the Gmail query
        if len(brand_terms) > 1:
            brand_part = "(" + " OR ".join(f'"{t}"' for t in brand_terms) + ")"
        else:
            brand_part = f'"{brand_terms[0]}"'

        # Combine with keywords if provided
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
                # Default all checkboxes to checked for the new result set
                for i in range(len(emails)):
                    st.session_state[f"email_check_{i}"] = True
            except Exception as e:
                st.error(f"Gmail error: {e}")

# ── Display fetched emails with checkboxes ────────────────────────────────────
emails      = st.session_state.get("fetched_emails", [])
brand_query = st.session_state.get("fetched_query", "")

if emails:
    # Show how many results came back and exactly which terms were searched
    brand_terms_used = st.session_state.get("fetched_brand_terms", [brand_query])
    terms_display    = ", ".join(f'"{t}"' for t in brand_terms_used)
    st.markdown(
        f"**{len(emails)} email(s) found** &nbsp;·&nbsp; "
        f"<span style='color:#6b7280;font-size:13px;'>Searched for: {terms_display}</span>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Select All / Deselect All buttons
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

    # Column headers
    h_chk, h_date, h_sender, h_subject, h_snippet = st.columns([0.4, 1.6, 2.5, 2.5, 3.0])
    h_chk.markdown    ("")
    h_date.markdown   ("<small><b>Date</b></small>",    unsafe_allow_html=True)
    h_sender.markdown ("<small><b>From</b></small>",    unsafe_allow_html=True)
    h_subject.markdown("<small><b>Subject</b></small>", unsafe_allow_html=True)
    h_snippet.markdown("<small><b>Snippet</b></small>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:4px 0 8px 0;'>", unsafe_allow_html=True)

    # One row per email
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

    # ── Save selected to Brand Memory ─────────────────────────────────────────
    st.markdown("---")
    st.subheader("Save to Brand Memory")

    # Dropdown of existing brands so the user can consolidate (e.g. save "Coke"
    # emails under "Coke Festive Campaign"), plus a free-type option for new brands
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

            # Save each selected email as its own individual entry so they can
            # be deleted independently in the Brand Memory page
            for email in selected:
                brand_data["entries"].append({
                    "type":       "email",
                    "timestamp":  save_timestamp,       # when saved to Brand Memory
                    "email_date": email["date"],        # actual date of the email
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
