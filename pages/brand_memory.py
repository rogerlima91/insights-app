import json
import os
from datetime import datetime
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Brand Memory", layout="wide")

# ── Paths ─────────────────────────────────────────────────────────────────────
BRAND_MEMORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "brand_memory.json")

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_brand_memory():
    """Load brand memory from JSON file. Returns empty dict if file doesn't exist."""
    if os.path.exists(BRAND_MEMORY_PATH):
        with open(BRAND_MEMORY_PATH, "r") as f:
            return json.load(f)
    return {}

def save_brand_memory(memory):
    """Save brand memory dict back to JSON file."""
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
    """
    Concatenate all entry texts into a single rationale string.
    Keeps the 'rationale' field in sync so app.py can still read it.
    """
    return "\n\n".join(entry_to_text(e) for e in entries)

def migrate_brand(brand_data):
    """
    Convert old-format brand data (just a 'rationale' string) to the new
    entries-list format. Safe to call on already-migrated data.
    """
    if "entries" not in brand_data:
        old_text = brand_data.get("rationale", "").strip()
        brand_data["entries"] = (
            [{"type": "manual", "timestamp": "Added before timestamps", "text": old_text}]
            if old_text else []
        )
    return brand_data

# ── Page title ────────────────────────────────────────────────────────────────
st.title("Brand Memory")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Store brand context so AI insights are tailored to each brand's objectives."
    "</p>",
    unsafe_allow_html=True,
)

bm = load_brand_memory()
bm_names = list(bm.keys())

# ── Add entry form ────────────────────────────────────────────────────────────
st.subheader("Add Entry")

bm_options  = ["+ Add new brand"] + bm_names
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

# ── Saved brands — entries view ───────────────────────────────────────────────
st.markdown("---")
st.subheader("Saved Brands")

if not bm_names:
    st.info("No brands saved yet. Use the form above to add one.")
else:
    for brand_name, brand_data in bm.items():
        brand_data = migrate_brand(brand_data)
        entries    = brand_data.get("entries", [])

        # Brand heading
        st.markdown(
            f"<h4 style='color:#14113b;margin-bottom:4px;'>{brand_name}</h4>",
            unsafe_allow_html=True,
        )

        # ── Individual entries ────────────────────────────────────────────────
        if not entries:
            st.caption("No entries yet.")
        else:
            for i, entry in enumerate(entries):
                entry_type   = entry.get("type", "manual")
                is_new_email = entry_type == "email" and "subject" in entry

                # Email entries: show the actual email date.
                # Manual / legacy entries: show the save timestamp.
                if is_new_email:
                    display_date = entry.get("email_date", entry.get("timestamp", ""))
                else:
                    display_date = entry.get("timestamp", "")

                badge_color = "#00b2a9" if entry_type == "manual" else "#6e2ca9"
                badge_label = "Manual"  if entry_type == "manual" else "Email"

                # [card content | Delete button] — wider gap so button is clearly visible
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
                        f"<div style='border:1px solid #e8e8f0;border-radius:8px;"
                        f"padding:10px 14px;margin-bottom:6px;background:#fafafa;'>"
                        f"<span style='font-size:11px;font-weight:700;color:#ffffff;"
                        f"background:{badge_color};padding:2px 8px;border-radius:12px;"
                        f"margin-right:8px;'>{badge_label}</span>"
                        f"<span style='font-size:12px;color:#6b7280;'>{display_date}</span>"
                        + body_html +
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                with col_btn:
                    # Small top margin so the button aligns with the card
                    st.markdown("<div style='margin-top:4px;'></div>",
                                unsafe_allow_html=True)
                    if st.button("🗑 Delete", key=f"del_{brand_name}_{i}"):
                        fresh_bm   = load_brand_memory()
                        fresh_data = migrate_brand(fresh_bm.get(brand_name, {}))
                        fresh_data["entries"].pop(i)
                        # If no entries remain, remove the brand entirely
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
