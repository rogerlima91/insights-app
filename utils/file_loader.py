"""
utils/file_loader.py — Robust file reader for DSP export files.

Handles the real-world messiness of DV360, TTD, Amazon, and other DSP
CSV exports:
  - Metadata rows above the true header (report name, date range, filters)
  - Grand Total / Summary rows at the bottom
  - Non-comma delimiters (semicolon, tab)
  - Non-UTF-8 encodings
  - Excel files (.xlsx / .xls)
  - Fully empty files

Public API:
    df, error_msg = read_file(uploaded_file)
    # On success: df is a DataFrame, error_msg is None.
    # On failure: df is None, error_msg is a specific human-readable string.
"""

import io
import csv
import re
import pandas as pd

# Encoding fallback chain — tried in order on decode failure.
_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

# Pattern that identifies "total" rows by their first-column value.
_TOTAL_PATTERN = re.compile(
    r"^\s*(grand\s+total|total|totals|summary|subtotal)\s*$",
    re.IGNORECASE,
)

# Pattern that identifies DV360-style footer metadata rows by their first-column prefix.
# Examples: "Report:", "Filter by: ...", "Group By: ...", "This report covers..."
_FOOTER_PREFIX = re.compile(
    r"^\s*(report|group\s+by|filter\s+by|mrc|this\s+report|active\s+view|–|—|-\s)",
    re.IGNORECASE,
)


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _decode_bytes(raw: bytes) -> tuple:
    """
    Attempt to decode raw bytes using the encoding fallback chain.
    Returns (text_str, encoding_name) on success.
    Raises ValueError if all encodings fail.
    """
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(
        f"Could not decode file with any of: {', '.join(_ENCODINGS)}. "
        "The file may be corrupt or in an unsupported encoding."
    )


def _sniff_delimiter(line: str) -> str:
    """
    Detect the field delimiter from a single line of text.
    Uses csv.Sniffer first; falls back to counting occurrences of
    comma, semicolon, and tab, returning the most frequent one.
    """
    try:
        dialect = csv.Sniffer().sniff(line, delimiters=",;\t")
        return dialect.delimiter
    except csv.Error:
        pass
    counts = {",": line.count(","), ";": line.count(";"), "\t": line.count("\t")}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def _is_numeric_field(s: str) -> bool:
    """
    Return True if s looks like a number (integer, float, percentage, currency).
    Used to distinguish header column names from data values.
    """
    cleaned = s.strip().lstrip("$£€").rstrip("%").replace(",", "").replace(" ", "")
    if not cleaned:
        return False
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def _looks_like_header(fields: list) -> bool:
    """
    Heuristic: a header row has at least 2 non-empty fields,
    and the majority of fields are non-numeric (column name strings).
    """
    non_empty = [f for f in fields if f.strip()]
    if len(non_empty) < 2:
        return False
    non_numeric = sum(1 for f in non_empty if not _is_numeric_field(f))
    # At least 60 % of non-empty fields should be non-numeric to qualify
    return non_numeric >= max(1, len(non_empty) * 0.6)


def _find_header_row(all_lines: list, delimiter: str) -> int:
    """
    Scan up to the first 20 non-empty lines and return the original
    line index of the most likely header row.

    Strategy:
      1. Count fields in each line using the detected delimiter.
      2. The header row and data rows will all share the same (maximum)
         field count; metadata rows above the header have fewer fields.
      3. Return the FIRST line with the maximum field count that also
         passes the _looks_like_header() heuristic.
      4. If no line passes the heuristic, return the first line with the
         maximum field count (safest fallback).
      5. If every line has the same field count, return 0 (no skip needed).
    """
    parsed = []  # [(original_line_index, field_count, fields_list)]
    scanned = 0
    for original_idx, line in enumerate(all_lines):
        if not line.strip():
            continue  # skip blank lines for scoring but preserve their index
        try:
            fields = next(csv.reader([line], delimiter=delimiter))
        except StopIteration:
            fields = []
        parsed.append((original_idx, len(fields), fields))
        scanned += 1
        if scanned >= 20:
            break

    if not parsed:
        return 0

    max_fields = max(n for _, n, _ in parsed)

    # If all scanned lines have the same field count, no metadata rows → return 0
    if all(n == max_fields for _, n, _ in parsed):
        return 0

    # Prefer: first line with max fields that looks like a header
    for orig_idx, n, fields in parsed:
        if n == max_fields and _looks_like_header(fields):
            return orig_idx

    # Fallback: first line with max fields, regardless of header heuristic
    for orig_idx, n, _ in parsed:
        if n == max_fields:
            return orig_idx

    return 0


def _drop_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove trailing Grand Total / Summary rows that DSP exports often
    append after the data.

    Rules applied:
      1. Drop any row where the first column (lowercased, stripped) matches
         the _TOTAL_PATTERN — these are explicit total rows.
      2. Drop any row after the last non-total, non-blank row where the
         first column is blank/NaN (common footer spacer rows).
    """
    if df.empty or len(df.columns) == 0:
        return df

    first_col = df.columns[0]
    first_as_str = df[first_col].astype(str).str.strip()

    # Rows that are explicit totals
    mask_total = first_as_str.str.match(_TOTAL_PATTERN)

    # Rows where first column is blank or the literal string "nan"
    mask_blank = first_as_str.isin(["", "nan"])

    # Trim trailing blank / spacer rows: find the last good row and chop anything
    # after it that is blank (but keep interior blanks in case they're real data)
    good_mask = ~(mask_total | mask_blank)
    if good_mask.any():
        last_good_idx = good_mask[::-1].idxmax()
        # Drop rows after last_good_idx that are blank (footer spacers)
        trailing_blank = (df.index > last_good_idx) & mask_blank
        df = df[~trailing_blank]
        # Recompute mask_total on the trimmed df
        first_as_str = df[first_col].astype(str).str.strip()
        mask_total = first_as_str.str.match(_TOTAL_PATTERN)

    # Drop all explicit total rows wherever they appear
    df = df[~mask_total]

    return df.reset_index(drop=True)


def _drop_footer_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove trailing footer / metadata rows that DSPs (especially DV360)
    append below the data block.

    Works upward from the last row.  A row is a footer row when ANY of
    these conditions hold for its first-column value:
      1. The string ends with ":" — e.g. "Filter by:", "Report:"
      2. The string matches known DV360 footer keyword prefixes.
      3. More than half of the numeric columns in that row are null.

    Scanning stops as soon as a row fails all three tests — that row is
    treated as the last real data row and everything above it is kept.
    """
    if df.empty or len(df.columns) == 0:
        return df

    first_col = df.columns[0]
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    indices = df.index.tolist()

    drop_set = set()
    for idx in reversed(indices):
        val = str(df.at[idx, first_col]).strip()

        ends_colon = val.endswith(":")
        is_keyword = bool(_FOOTER_PREFIX.match(val))

        if numeric_cols:
            null_count = sum(1 for nc in numeric_cols if pd.isna(df.at[idx, nc]))
            sparse = null_count > len(numeric_cols) * 0.5
        else:
            sparse = False

        if ends_colon or is_keyword or sparse:
            drop_set.add(idx)
        else:
            break  # found a real data row — stop scanning

    if drop_set:
        df = df.drop(index=list(drop_set)).reset_index(drop=True)

    return df


# ── Public API ────────────────────────────────────────────────────────────────

def read_file(uploaded_file) -> tuple:
    """
    Robustly read a CSV / TSV / TXT / XLSX / XLS file uploaded via Streamlit.

    Returns:
        (df, None)          — success; df is a pandas DataFrame ready for use
        (None, error_msg)   — failure; error_msg is a specific, human-readable
                              string naming exactly what went wrong

    Never raises an exception to the caller.
    """
    try:
        name = uploaded_file.name.lower()

        # ── Route Excel files ─────────────────────────────────────────────────
        if name.endswith((".xlsx", ".xls")):
            return _read_excel(uploaded_file)

        # ── Route text files (CSV / TSV / TXT) ───────────────────────────────
        return _read_text(uploaded_file)

    except Exception as exc:
        return None, f"Unexpected error reading '{uploaded_file.name}': {exc}"


def _read_excel(uploaded_file) -> tuple:
    """Handle .xlsx and .xls files."""
    try:
        raw = uploaded_file.read()
        uploaded_file.seek(0)
        df = pd.read_excel(io.BytesIO(raw))
    except Exception as exc:
        return None, f"Could not read Excel file '{uploaded_file.name}': {exc}"

    # Drop fully empty columns (common artefact in DV360 Excel exports)
    df = df.dropna(axis=1, how="all")

    if df.empty:
        return None, (
            f"'{uploaded_file.name}' appears to be empty — "
            "no data rows were found after the header."
        )

    df = _drop_total_rows(df)
    df = _drop_footer_rows(df)

    if df.empty:
        return None, (
            f"'{uploaded_file.name}' had no data rows after removing header "
            "and summary/total rows."
        )

    return df, None


def _read_text(uploaded_file) -> tuple:
    """Handle CSV, TSV, and TXT files with full robustness."""
    # Read raw bytes once — rewind not required after this
    try:
        raw = uploaded_file.read()
        uploaded_file.seek(0)
    except Exception as exc:
        return None, f"Could not read bytes from '{uploaded_file.name}': {exc}"

    if not raw.strip():
        return None, f"'{uploaded_file.name}' appears to be empty."

    # ── Encoding detection ────────────────────────────────────────────────────
    try:
        text, encoding_used = _decode_bytes(raw)
    except ValueError as exc:
        return None, str(exc)

    all_lines = text.splitlines()

    # Quick emptiness check
    if not any(line.strip() for line in all_lines):
        return None, f"'{uploaded_file.name}' appears to be empty."

    # ── Delimiter detection ───────────────────────────────────────────────────
    # Sniff from the first non-empty line as an initial guess
    first_nonempty = next((l for l in all_lines if l.strip()), "")
    delimiter = _sniff_delimiter(first_nonempty)

    # ── Header row detection ──────────────────────────────────────────────────
    header_row_idx = _find_header_row(all_lines, delimiter)

    # Re-sniff delimiter from the actual header line — more accurate than the
    # first line, which may be a single-field metadata row
    if header_row_idx < len(all_lines) and all_lines[header_row_idx].strip():
        delimiter = _sniff_delimiter(all_lines[header_row_idx])

    if header_row_idx >= len(all_lines):
        return None, (
            f"Could not find a valid header row in the first 20 lines of "
            f"'{uploaded_file.name}'."
        )

    # ── Parse CSV ─────────────────────────────────────────────────────────────
    read_kwargs = dict(
        sep=delimiter,
        skiprows=header_row_idx,
        encoding=encoding_used,
        engine="python",      # more forgiving than C engine for messy files
    )

    try:
        # on_bad_lines="warn" requires pandas >= 1.3
        df = pd.read_csv(io.BytesIO(raw), on_bad_lines="warn", **read_kwargs)
    except TypeError:
        # Older pandas: parameter not supported — just skip it
        df = pd.read_csv(io.BytesIO(raw), **read_kwargs)
    except Exception as exc:
        return None, (
            f"CSV parse failed for '{uploaded_file.name}': {exc}. "
            "Check that the file is a valid CSV/TSV and is not password-protected."
        )

    # Drop fully empty columns (artefact of trailing commas in some DSP exports)
    df = df.dropna(axis=1, how="all")

    if df.empty:
        return None, (
            f"'{uploaded_file.name}' appears to be empty — "
            "no data rows were found after the header."
        )

    # ── Remove total/summary footer rows, then DSP metadata footer rows ──────
    df = _drop_total_rows(df)
    df = _drop_footer_rows(df)

    if df.empty:
        return None, (
            f"'{uploaded_file.name}' had no data rows after removing the header "
            "and summary/total rows."
        )

    return df, None
