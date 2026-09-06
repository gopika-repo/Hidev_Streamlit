import math
import re
import time
import unicodedata
from datetime import date

import geonamescache
import httpx
import pandas as pd
import streamlit as st
from supabase import create_client


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="HiDevs Event Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("HiDevs Event Dashboard")
st.caption("Search the HiDevs community and normalized Luma event registrations")


# ============================================================
# SUPABASE
# ============================================================

@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


supabase = get_supabase()

# General community view (scraping + LinkedIn + Luma, etc.)
VIEW = "all_hidevs_users"

# Profile layer. These tables hold one row per raw email identity.
LUMA_TABLES = [
    "luma_verified_designation",
    "luma_not_verified_designation",
    "luma_unverified_users",
]

# Normalized Luma event layer.
EVENT_MASTER_TABLE = "luma_event_master"
USER_EVENTS_TABLE = "luma_user_events"
IDENTITY_TABLE = "luma_identity_map"

FETCH_BATCH_SIZE = 1000


# ============================================================
# COLUMNS
# ============================================================

DB_COLUMNS = [
    "first_name",
    "last_name",
    "email",
    "linkedin",
    "city",
    "designation",
    "designation_category",
    "phone",
    "source_tab",
    "source_spreadsheet",
    "luma_event_name",
    "event_type",
    "event_mode",
    "event_date",
    "about",
    "reason_to_join_event",
    "category_source",
    "company",
    "are_you",
]


DISPLAY_NAMES = {
    "first_name": "FirstName",
    "email": "Email",
    "linkedin": "LinkedIn",
    "city": "City",
    "designation": "Designation",
    "designation_category": "Designation Category",
    "last_name": "LastName",
    "phone": "Phone",
    "source_tab": "Source Tab",
    "source_spreadsheet": "Source Spreadsheet",
    "luma_event_name": "Luma Event Name",
    "event_type": "Event Type",
    "event_mode": "Event Mode",
    "event_date": "event_date",
    "about": "About",
    "reason_to_join_event": "Reason to join our event",
    "category_source": "Category Source",
    "company": "Company",
    "are_you": "Are You?",
}


# Only controls how many result rows are DISPLAYED per page.
# It does NOT limit how many rows are fetched from Supabase.
PAGE_SIZE = 100


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def normalize_text(value):
    value = clean_text(value)

    value = unicodedata.normalize(
        "NFKD",
        value
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.casefold().strip()


# ============================================================
# DISPLAY-ONLY LABEL HELPERS
# DATABASE VALUES ARE NOT MODIFIED
# ============================================================

CATEGORY_SOURCE_DISPLAY_MAP = {
    "real_designation_clear": "Designation",
    "strong_are_you_evidence": "Are You",
}


def display_category_source(value):
    key = normalize_text(value).replace("-", "_").replace(" ", "_")
    return CATEGORY_SOURCE_DISPLAY_MAP.get(key, clean_text(value))


def is_luma_not_verified_row(row):
    source_table = normalize_text(row.get("_source_table"))
    source_tab = normalize_text(row.get("source_tab")).replace("-", " ")

    return (
        source_table == "luma_not_verified_designation"
        or "luma not verified designation" in source_tab
        or "not verified designation" in source_tab
    )


def split_multi_value(value, separator=";"):

    value = clean_text(value)

    if not value:
        return []

    return [
        item.strip()
        for item in value.split(separator)
        if item.strip()
    ]


def clean_event_label(value):

    value = clean_text(value)

    value = value.replace('""', '"')
    value = value.strip('"').strip()

    return value


def panel_button(label, key):
    opened = st.session_state.get(key, False)
    arrow = "▼" if opened else "▶"

    if st.button(
        f"{arrow} {label}",
        key=f"btn_{key}",
        use_container_width=True,
    ):
        st.session_state[key] = not opened
        st.rerun()

    return st.session_state.get(key, False)


def option_widget_key(prefix, value):
    safe = re.sub(
        r"[^a-zA-Z0-9_]+",
        "_",
        str(value),
    )[:70]
    return f"{prefix}_{safe}_{abs(hash(str(value))) % 1000000}"


def toggle_pending_value(bucket, value, widget_key):
    selected = set(st.session_state.get(bucket, []))

    if st.session_state.get(widget_key, False):
        selected.add(value)
    else:
        selected.discard(value)

    st.session_state[bucket] = sorted(selected, key=lambda x: normalize_text(x))
    st.session_state[f"{bucket}__all_selected"] = False


def toggle_single_pending_value(bucket, value, widget_key, prefix, options):
    """Checkbox UI with radio-style semantics for Event Audience."""
    if st.session_state.get(widget_key, False):
        st.session_state[bucket] = [value]
        for other in options:
            if other == value:
                continue
            other_key = option_widget_key(prefix, other)
            if other_key in st.session_state:
                st.session_state[other_key] = False
    else:
        current = list(st.session_state.get(bucket, []))
        if value in current:
            st.session_state[bucket] = []


def render_checkbox_list(
    options,
    prefix,
    bucket,
    columns=4,
    search_label=None,
):
    visible = list(options or [])

    if search_label:
        q = st.text_input(
            search_label,
            key=f"{prefix}_search",
            placeholder="Type to search options...",
        ).strip().lower()

        if q:
            visible = [
                x for x in visible
                if q in str(x).lower()
            ]

    selected_now = set(st.session_state.get(bucket, []))

    if not visible:
        st.caption("No matching options.")
        return

    cols = st.columns(columns)

    for i, option in enumerate(visible):
        key = option_widget_key(prefix, option)

        if key not in st.session_state:
            st.session_state[key] = option in selected_now

        with cols[i % columns]:
            st.checkbox(
                str(option),
                key=key,
                on_change=toggle_pending_value,
                args=(bucket, option, key),
            )


def render_single_checkbox_list(
    options,
    prefix,
    bucket,
    columns=4,
):
    selected_now = list(st.session_state.get(bucket, []))
    cols = st.columns(columns)

    for i, option in enumerate(options):
        key = option_widget_key(prefix, option)

        if key not in st.session_state:
            st.session_state[key] = option in selected_now

        with cols[i % columns]:
            st.checkbox(
                str(option),
                key=key,
                on_change=toggle_single_pending_value,
                args=(bucket, option, key, prefix, list(options)),
            )


def set_filter_selection(bucket, prefix, options, select_all):
    values = list(options or [])
    st.session_state[bucket] = values if select_all else []
    st.session_state[f"{bucket}__all_selected"] = bool(select_all)

    for option in values:
        st.session_state[option_widget_key(prefix, option)] = bool(select_all)


def render_all_none_controls(bucket, prefix, options, key_suffix):
    c1, c2, _ = st.columns([1, 1, 6])

    with c1:
        if st.button("All", key=f"all_{key_suffix}", use_container_width=True):
            set_filter_selection(bucket, prefix, options, True)
            st.rerun()

    with c2:
        if st.button("None", key=f"none_{key_suffix}", use_container_width=True):
            set_filter_selection(bucket, prefix, options, False)
            st.rerun()


def applied_selection(bucket):
    # "All" means no restriction in the actual filter query.
    if st.session_state.get(f"{bucket}__all_selected", False):
        return []
    return list(st.session_state.get(bucket, []))


# ============================================================
# CATEGORY NORMALIZATION
# DISPLAY/FILTER ONLY
# DATABASE IS NOT MODIFIED
# ============================================================

# ============================================================
# FIXED DESIGNATION CATEGORIES
# ============================================================
# The designation-category filter intentionally exposes 11 labels.
# "Registered Users" is an event-audience concept, not a designation category,
# so it is not shown in this filter. Raw source values are still normalized
# internally so existing data remains compatible.
DESIGNATION_CATEGORY_OPTIONS = [
    "Founder",
    "C-Suite",
    "Investor",
    "Student/Intern",
    "Director/VP/Head",
    "Professional",
    "HR",
    "Community",
    "Others",
    "Not Mentioned",
    "Unverified Users",
]


def normalize_category(value):
    """Normalize a raw category/designation into a stable dashboard label.

    Known source category labels are matched EXACTLY first. This is important:
    a value such as ``Director/VP/Head`` must never become ``C-Suite`` merely
    because it contains the token ``VP``.
    """
    raw = clean_text(value)
    key = normalize_text(raw)

    if not key:
        return "Not Mentioned"

    compact = re.sub(r"[^a-z0-9]+", " ", key).strip()

    # --------------------------------------------------------
    # 1) AUTHORITATIVE / KNOWN CATEGORY LABELS — exact aliases
    # --------------------------------------------------------
    exact_aliases = {
        "registered users": "Registered Users",
        "registered user": "Registered Users",
        "unverified users": "Unverified Users",
        "unverified user": "Unverified Users",

        "founder": "Founder",
        "founders": "Founder",
        "founder co founder": "Founder",
        "founder cofounder": "Founder",
        "co founder": "Founder",
        "cofounder": "Founder",

        "c suite": "C-Suite",
        "senior leadership c suite": "C-Suite",
        "senior leadership": "C-Suite",

        "investor": "Investor",
        "investors": "Investor",

        "student": "Student/Intern",
        "students": "Student/Intern",
        "student intern": "Student/Intern",
        "students interns": "Student/Intern",

        "director vp head": "Director/VP/Head",
        "director vp senior professional": "Director/VP/Head",

        "professional": "Professional",
        "professionals": "Professional",
        "individual contributor professional": "Professional",
        "other professional roles": "Professional",

        "hr": "HR",
        "human resources": "HR",

        "community": "Community",
        "community member": "Community",

        "other": "Others",
        "others": "Others",
        "other blank": "Others",
        "professor": "Others",
        "professors": "Others",
        "faculty": "Others",

        "not mentioned": "Not Mentioned",
        "not mention": "Not Mentioned",
        "not mentiones": "Not Mentioned",
        "unknown": "Not Mentioned",
        "none": "Not Mentioned",
        "null": "Not Mentioned",
        "na": "Not Mentioned",
        "n a": "Not Mentioned",
        "blank": "Not Mentioned",
    }

    if compact in exact_aliases:
        return exact_aliases[compact]

    # --------------------------------------------------------
    # 2) FALLBACK FOR FREE-TEXT DESIGNATIONS / "Are You?"
    # --------------------------------------------------------
    tokens = set(compact.split())

    if any(x in compact for x in [
        "founder", "co founder", "cofounder"
    ]):
        return "Founder"

    if any(x in compact for x in [
        "investor", "venture capital", "angel investor"
    ]):
        return "Investor"

    # C-Suite only for explicit chief / CXO signals. Do NOT use plain VP here.
    if any(x in compact for x in [
        "c suite", "senior leadership", "chief executive",
        "chief technology", "chief operating", "chief financial",
        "chief marketing", "chief product", "chief information",
        "chief revenue", "chief strategy", "chief people"
    ]) or tokens.intersection({"ceo", "cto", "coo", "cfo", "cmo", "cpo", "cio", "cro", "cso", "chro"}):
        return "C-Suite"

    # Director / VP / Head is intentionally checked separately from C-Suite.
    if (
        "director" in tokens
        or "vice president" in compact
        or "vp" in tokens
        or "head" in tokens
        or "head of" in compact
        or "department head" in compact
        or "business head" in compact
    ):
        return "Director/VP/Head"

    if any(x in compact for x in [
        "student", "intern", "internship", "college engineer",
        "college student", "university student"
    ]):
        return "Student/Intern"

    if (
        "hr" in tokens
        or any(x in compact for x in [
            "human resources", "human resource", "recruiter",
            "recruitment", "talent acquisition", "people operations"
        ])
    ):
        return "HR"

    if any(x in compact for x in [
        "community", "club", "chapter", "organizer", "organiser"
    ]):
        return "Community"

    if any(x in compact for x in [
        "individual contributor", "professional", "tech professional",
        "software engineer", "developer", "engineer", "consultant",
        "analyst", "designer", "manager"
    ]):
        return "Professional"

    if any(x in compact for x in [
        "not mentioned", "not mention", "not mentiones", "unknown",
        "none", "null", "blank"
    ]):
        return "Not Mentioned"

    if any(x in compact for x in [
        "other", "professor", "faculty", "volunteer"
    ]):
        return "Others"

    return "Others"


def get_dashboard_category(row):
    """Resolve a row into one stable dashboard category."""
    source_table = normalize_text(row.get("_source_table"))
    source_tab = normalize_text(row.get("source_tab"))
    source_text = f"{source_table} {source_tab}".strip()

    # Explicit source categories have priority.
    if "luma unverified users" in source_text or "unverified users" in source_text:
        return "Unverified Users"

    if "registered users" in source_text:
        return "Registered Users"

    # Main designation category from Supabase.
    raw_category = clean_text(row.get("designation_category"))
    if raw_category:
        normalized = normalize_category(raw_category)
        if normalized != "Not Mentioned":
            return normalized

    # For rows without a designation category, use Are You? as a safe
    # broad classification signal.
    are_you = clean_text(row.get("are_you"))
    if are_you:
        normalized = normalize_category(are_you)
        if normalized not in {"Not Mentioned", "Others"}:
            return normalized

    # Last fallback: designation text itself. This still returns only one
    # of the fixed labels and therefore cannot create random UI options.
    designation = clean_text(row.get("designation"))
    if designation:
        normalized = normalize_category(designation)
        if normalized != "Not Mentioned":
            return normalized

    return "Not Mentioned"


# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data(
    ttl=1800,
    show_spinner=False
)
def fetch_all_rows(table_name, columns):
    """Fetch a complete Supabase table safely in paginated batches.

    Transient HTTP disconnects can happen while Streamlit is loading a large
    dataset. Retry the same batch automatically instead of crashing the app.
    """

    all_rows = []
    start = 0
    max_retries = 5

    retryable_errors = (
        httpx.RemoteProtocolError,
        httpx.ConnectError,
        httpx.ReadError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
    )

    while True:

        response = None

        for attempt in range(1, max_retries + 1):

            try:
                response = (
                    supabase
                    .table(table_name)
                    .select(",".join(columns))
                    .range(
                        start,
                        start + FETCH_BATCH_SIZE - 1
                    )
                    .execute()
                )
                break

            except retryable_errors:
                if attempt == max_retries:
                    raise

                time.sleep(attempt * 2)

        rows = response.data or []
        all_rows.extend(rows)

        if len(rows) < FETCH_BATCH_SIZE:
            break

        start += FETCH_BATCH_SIZE

    return pd.DataFrame(all_rows)


# ============================================================
# NORMALIZED LUMA HELPERS
# ============================================================

EVENT_MASTER_COLUMNS = [
    "event_id",
    "event_name",
    "event_start_at",
    "event_end_at",
    "event_date",
    "event_timezone",
    "event_url",
    "event_type",
    "event_mode",
]

USER_EVENT_COLUMNS = [
    "event_id",
    "guest_id",
    "user_id",
    "email",
    "first_name",
    "last_name",
    "phone",
    "approval_status",
    "registered_at",
    "is_registered",
    "checked_in",
    "checked_in_at",
]

# Lightweight columns used to build each person's complete normalized event
# history in the unfiltered dashboard. Event dates are then shown in the same
# order as the event names, so the Nth date always belongs to the Nth event.
USER_EVENT_HISTORY_COLUMNS = [
    "event_id",
    "email",
]

IDENTITY_COLUMNS = [
    "alias_email",
    "canonical_email",
    "match_status",
]


def normalize_email(value):
    return clean_text(value).casefold()


def resolve_identity(email, mapping):
    """Resolve an email through the alias map, including defensive chaining."""
    current = normalize_email(email)
    seen = set()

    while current and current in mapping and current not in seen:
        seen.add(current)
        nxt = normalize_email(mapping.get(current))
        if not nxt or nxt == current:
            break
        current = nxt

    return current


@st.cache_data(ttl=600, show_spinner=False)
def load_event_master():
    frame = fetch_all_rows(
        EVENT_MASTER_TABLE,
        tuple(EVENT_MASTER_COLUMNS),
    )

    if frame.empty:
        return pd.DataFrame(columns=EVENT_MASTER_COLUMNS)

    for col in EVENT_MASTER_COLUMNS:
        if col not in frame.columns:
            frame[col] = None

    frame["_event_date"] = pd.to_datetime(
        frame["event_date"],
        errors="coerce",
    ).dt.date

    return frame


@st.cache_data(ttl=600, show_spinner=False)
def load_identity_map():
    frame = fetch_all_rows(
        IDENTITY_TABLE,
        tuple(IDENTITY_COLUMNS),
    )

    if frame.empty:
        return pd.DataFrame(columns=IDENTITY_COLUMNS)

    for col in IDENTITY_COLUMNS:
        if col not in frame.columns:
            frame[col] = None

    frame["alias_email"] = frame["alias_email"].apply(normalize_email)
    frame["canonical_email"] = frame["canonical_email"].apply(normalize_email)
    return frame


@st.cache_data(ttl=1800, show_spinner=False)
def load_normalized_event_history(identity_df, event_master_df):
    """Build exact event-name/date history for every canonical Luma identity.

    One luma_user_events relationship is tied to one event_id. By joining those
    event_ids to luma_event_master first, the event names and dates stay aligned.
    The grouped strings are chronological and use the same separator/order:

        Luma Event Name: Event A; Event B; Event C
        event_date:      01-01-2026; 05-02-2026; 19-03-2026

    Therefore each date position corresponds to the event at the same position.
    """

    history_columns = [
        "_canonical_email",
        "_history_event_names",
        "_history_event_dates",
        "_history_event_types",
        "_history_event_modes",
    ]

    if event_master_df is None or event_master_df.empty:
        return pd.DataFrame(columns=history_columns)

    relationships = fetch_all_rows(
        USER_EVENTS_TABLE,
        tuple(USER_EVENT_HISTORY_COLUMNS),
    )

    if relationships.empty:
        return pd.DataFrame(columns=history_columns)

    for col in USER_EVENT_HISTORY_COLUMNS:
        if col not in relationships.columns:
            relationships[col] = None

    identity_lookup = {}
    if identity_df is not None and not identity_df.empty:
        for _, row in identity_df.iterrows():
            alias = normalize_email(row.get("alias_email"))
            canonical = normalize_email(row.get("canonical_email"))
            if alias and canonical:
                identity_lookup[alias] = canonical

    relationships["_email_clean"] = relationships["email"].apply(normalize_email)
    relationships["_canonical_email"] = relationships["_email_clean"].apply(
        lambda x: resolve_identity(x, identity_lookup)
    )

    relationships = relationships[
        relationships["_canonical_email"].fillna("").astype(str).str.strip().ne("")
    ].copy()

    if relationships.empty:
        return pd.DataFrame(columns=history_columns)

    master_cols = [
        "event_id",
        "event_name",
        "event_type",
        "event_mode",
        "_event_date",
    ]
    master = event_master_df[[c for c in master_cols if c in event_master_df.columns]].copy()

    for col in master_cols:
        if col not in master.columns:
            master[col] = None

    merged = relationships.merge(
        master[master_cols],
        on="event_id",
        how="left",
        sort=False,
    )

    # One canonical person + one event occurrence should appear only once in
    # the history even if defensive duplicate rows ever reach the client.
    merged = merged.drop_duplicates(
        subset=["_canonical_email", "event_id"],
        keep="first",
    )

    merged["_sort_date"] = pd.to_datetime(
        merged["_event_date"],
        errors="coerce",
    )

    merged = merged.sort_values(
        ["_canonical_email", "_sort_date", "event_id"],
        ascending=[True, True, True],
        na_position="last",
        kind="stable",
    )

    def joined_history(group, column, formatter=None):
        values = []
        for value in group[column]:
            if formatter is not None:
                value = formatter(value)
            else:
                value = clean_text(value)
            values.append(value or "None")
        return "; ".join(values)

    rows = []
    for canonical_email, group in merged.groupby("_canonical_email", sort=False):
        event_names = joined_history(
            group,
            "event_name",
            lambda x: clean_event_label(x) or "Unnamed Event",
        )
        event_dates = joined_history(
            group,
            "_event_date",
            lambda x: x.strftime("%d-%m-%Y") if pd.notna(x) else "Date unknown",
        )
        event_types = joined_history(group, "event_type")
        event_modes = joined_history(group, "event_mode")

        rows.append({
            "_canonical_email": canonical_email,
            "_history_event_names": event_names,
            "_history_event_dates": event_dates,
            "_history_event_types": event_types,
            "_history_event_modes": event_modes,
        })

    return pd.DataFrame(rows, columns=history_columns)


def load_profile_join_data(identity_df):
    """Build one best profile row per canonical Luma person."""
    identity_df = identity_df.copy()
    identity_lookup = {}

    if not identity_df.empty:
        for _, row in identity_df.iterrows():
            alias = normalize_email(row.get("alias_email"))
            canonical = normalize_email(row.get("canonical_email"))
            if alias and canonical:
                identity_lookup[alias] = canonical

    frames = []
    priorities = {
        "luma_verified_designation": 0,
        "luma_not_verified_designation": 1,
        "luma_unverified_users": 2,
    }

    for table_name in LUMA_TABLES:
        part = fetch_all_rows(table_name, tuple(DB_COLUMNS))
        if part.empty:
            continue

        for col in DB_COLUMNS:
            if col not in part.columns:
                part[col] = None

        part["_profile_source_table"] = table_name
        part["_source_priority"] = priorities[table_name]
        part["_email_clean"] = part["email"].apply(normalize_email)
        part["_canonical_email"] = part["_email_clean"].apply(
            lambda x: resolve_identity(x, identity_lookup)
        )

        completeness_cols = [
            "first_name", "last_name", "phone", "linkedin", "city",
            "designation", "company", "about",
        ]

        part["_completeness"] = part[completeness_cols].apply(
            lambda row: sum(bool(clean_text(v)) for v in row),
            axis=1,
        )
        frames.append(part)

    if not frames:
        return pd.DataFrame(columns=DB_COLUMNS + ["_canonical_email"])

    profiles = pd.concat(frames, ignore_index=True, sort=False)
    profiles = profiles.sort_values(
        ["_canonical_email", "_source_priority", "_completeness"],
        ascending=[True, True, False],
        kind="stable",
    )
    profiles = profiles.drop_duplicates(
        subset=["_canonical_email"],
        keep="first",
    )

    return profiles


@st.cache_data(ttl=300, show_spinner=False)
def fetch_event_relationships(event_ids):
    """
    Fetch complete luma_user_events rows for all selected event IDs.

    Performance fix:
    - The old implementation queried each selected event separately.
    - Selecting many events therefore caused N separate paginated scans and made
      the dashboard appear frozen.
    - This implementation batches event IDs into PostgREST IN queries and
      paginates the combined result with deterministic ordering.
    """
    event_ids = list(dict.fromkeys(
        clean_text(event_id)
        for event_id in (event_ids or [])
        if clean_text(event_id)
    ))

    if not event_ids:
        return pd.DataFrame(columns=USER_EVENT_COLUMNS)

    frames = []
    # Keep the URL/query payload comfortably small even if many events are ticked.
    event_id_chunk_size = 20

    for chunk_start in range(0, len(event_ids), event_id_chunk_size):
        chunk = event_ids[chunk_start:chunk_start + event_id_chunk_size]
        all_rows = []
        start = 0

        while True:
            response = None
            max_retries = 5

            retryable_errors = (
                httpx.RemoteProtocolError,
                httpx.ConnectError,
                httpx.ReadError,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
            )

            for attempt in range(1, max_retries + 1):

                try:
                    response = (
                        supabase
                        .table(USER_EVENTS_TABLE)
                        .select(",".join(USER_EVENT_COLUMNS))
                        .in_("event_id", chunk)
                        .order("event_id", desc=False)
                        .order("guest_id", desc=False)
                        .range(start, start + FETCH_BATCH_SIZE - 1)
                        .execute()
                    )
                    break

                except retryable_errors:
                    if attempt == max_retries:
                        raise

                    time.sleep(attempt * 2)

            rows = response.data or []
            all_rows.extend(rows)

            if len(rows) < FETCH_BATCH_SIZE:
                break

            start += FETCH_BATCH_SIZE

        if all_rows:
            frames.append(pd.DataFrame(all_rows))

    if not frames:
        return pd.DataFrame(columns=USER_EVENT_COLUMNS)

    result = pd.concat(frames, ignore_index=True, sort=False)

    for col in USER_EVENT_COLUMNS:
        if col not in result.columns:
            result[col] = None

    # UNIQUE(event_id, guest_id) exists in Supabase; this is an additional
    # defensive guard against accidental duplicate rows from pagination.
    if "guest_id" in result.columns:
        result = result.drop_duplicates(
            subset=["event_id", "guest_id"],
            keep="first",
        )

    return result.reset_index(drop=True)


def first_nonblank(series):
    for value in series:
        if clean_text(value):
            return value
    return None


def join_unique(values, separator="; "):
    output = []
    seen = set()

    for value in values:
        text = clean_text(value)
        if not text:
            continue
        key = normalize_text(text)
        if key in seen:
            continue
        seen.add(key)
        output.append(text)

    return separator.join(output)


def build_event_user_dataframe(
    event_ids,
    audience_mode,
    event_master_df,
    identity_df,
    profile_join_df,
):
    """
    Build normalized event results from luma_user_events.

    IMPORTANT MULTI-EVENT RULE:
    One output row represents one canonical person in one selected event.
    A person registered for three selected events therefore has three event rows,
    each with the exact name/date/type/mode of that occurrence.

    This prevents one person's multiple selected events from being collapsed into
    a semicolon history and makes every selected event visible in the results.
    """
    event_ids = list(dict.fromkeys(
        clean_text(event_id)
        for event_id in (event_ids or [])
        if clean_text(event_id)
    ))
    event_order = {event_id: i for i, event_id in enumerate(event_ids)}

    raw = fetch_event_relationships(event_ids)

    if raw.empty:
        empty = pd.DataFrame(columns=DB_COLUMNS)
        return empty, {
            "guest_rows": 0,
            "registered_rows": 0,
            "attended_rows": 0,
            "invited_only_rows": 0,
            "audience_relationships": 0,
            "canonical_users": 0,
            "event_user_rows": 0,
            "per_event": [],
        }

    registered_mask = raw["is_registered"].fillna(False).astype(bool)
    attended_mask = raw["checked_in"].fillna(False).astype(bool)
    invited_mask = (
        ~registered_mask
        & raw["approval_status"].fillna("").astype(str).str.casefold().eq("invited")
    )

    audit = {
        "guest_rows": int(len(raw)),
        "registered_rows": int(registered_mask.sum()),
        "attended_rows": int(attended_mask.sum()),
        "invited_only_rows": int(invited_mask.sum()),
    }

    if audience_mode == "Registered":
        selected = raw[registered_mask].copy()
    elif audience_mode == "Attended":
        selected = raw[attended_mask].copy()
    elif audience_mode == "Invited Only":
        selected = raw[invited_mask].copy()
    else:
        selected = raw.copy()

    audit["audience_relationships"] = int(len(selected))

    # Per-event relationship coverage is calculated before identity collapse so
    # the audit proves that every selected event was actually fetched.
    per_event_audit = []
    master_lookup = {}
    if not event_master_df.empty:
        master_lookup = event_master_df.set_index("event_id").to_dict("index")

    for event_id in event_ids:
        part = raw[raw["event_id"].astype(str).eq(str(event_id))]
        part_registered = part["is_registered"].fillna(False).astype(bool)
        part_attended = part["checked_in"].fillna(False).astype(bool)
        part_invited = (
            ~part_registered
            & part["approval_status"].fillna("").astype(str).str.casefold().eq("invited")
        )

        if audience_mode == "Registered":
            part_selected = part[part_registered]
        elif audience_mode == "Attended":
            part_selected = part[part_attended]
        elif audience_mode == "Invited Only":
            part_selected = part[part_invited]
        else:
            part_selected = part

        meta = master_lookup.get(event_id, {})
        event_date_value = meta.get("_event_date")
        per_event_audit.append({
            "event_id": event_id,
            "event_name": clean_text(meta.get("event_name")) or event_id,
            "event_date": (
                event_date_value.strftime("%d-%m-%Y")
                if pd.notna(event_date_value)
                else ""
            ),
            "event_type": clean_text(meta.get("event_type")) or "None",
            "event_mode": clean_text(meta.get("event_mode")) or "None",
            "guest_rows": int(len(part)),
            "registered_rows": int(part_registered.sum()),
            "attended_rows": int(part_attended.sum()),
            "invited_only_rows": int(part_invited.sum()),
            "selected_relationships": int(len(part_selected)),
        })

    audit["per_event"] = per_event_audit

    if selected.empty:
        empty = pd.DataFrame(columns=DB_COLUMNS)
        audit["canonical_users"] = 0
        audit["event_user_rows"] = 0
        return empty, audit

    identity_lookup = {}
    if not identity_df.empty:
        for _, row in identity_df.iterrows():
            alias = normalize_email(row.get("alias_email"))
            canonical = normalize_email(row.get("canonical_email"))
            if alias and canonical:
                identity_lookup[alias] = canonical

    selected["_email_clean"] = selected["email"].apply(normalize_email)
    selected["_canonical_email"] = selected["_email_clean"].apply(
        lambda x: resolve_identity(x, identity_lookup)
    )

    # Never collapse blank emails into one person. user_id/guest_id remains the
    # stable fallback identity inside the selected Luma relationship layer.
    selected["_person_key"] = selected.apply(
        lambda r: (
            r["_canonical_email"]
            if clean_text(r["_canonical_email"])
            else clean_text(r.get("user_id"))
            or clean_text(r.get("guest_id"))
        ),
        axis=1,
    )

    selected["_event_name"] = selected["event_id"].apply(
        lambda x: clean_text(master_lookup.get(x, {}).get("event_name"))
    )
    selected["_event_date_value"] = selected["event_id"].apply(
        lambda x: master_lookup.get(x, {}).get("_event_date")
    )
    selected["_event_date_text"] = selected["_event_date_value"].apply(
        lambda x: x.strftime("%d-%m-%Y") if pd.notna(x) else ""
    )
    selected["_event_url"] = selected["event_id"].apply(
        lambda x: clean_text(master_lookup.get(x, {}).get("event_url"))
    )
    selected["_event_type"] = selected["event_id"].apply(
        lambda x: clean_text(master_lookup.get(x, {}).get("event_type"))
    )
    selected["_event_mode"] = selected["event_id"].apply(
        lambda x: clean_text(master_lookup.get(x, {}).get("event_mode"))
    )

    profile_lookup = {}
    if not profile_join_df.empty:
        profile_lookup = profile_join_df.set_index("_canonical_email").to_dict("index")

    records = []

    # Group by BOTH event and person. This is the key multi-event fix.
    for (event_id, person_key), group in selected.groupby(
        ["event_id", "_person_key"],
        sort=False,
        dropna=False,
    ):
        canonical_email = first_nonblank(group["_canonical_email"])
        profile = profile_lookup.get(normalize_email(canonical_email), {})

        record = {col: profile.get(col) for col in DB_COLUMNS}

        record["first_name"] = clean_text(profile.get("first_name")) or clean_text(first_nonblank(group["first_name"]))
        record["last_name"] = clean_text(profile.get("last_name")) or clean_text(first_nonblank(group["last_name"]))
        record["email"] = clean_text(first_nonblank(group["email"])) or clean_text(profile.get("email"))
        record["phone"] = clean_text(profile.get("phone")) or clean_text(first_nonblank(group["phone"]))

        meta = master_lookup.get(event_id, {})
        event_date_value = meta.get("_event_date")

        # Exactly ONE selected occurrence per row.
        record["luma_event_name"] = clean_text(meta.get("event_name"))
        record["event_date"] = (
            event_date_value.strftime("%d-%m-%Y")
            if pd.notna(event_date_value)
            else ""
        )
        record["source_spreadsheet"] = clean_text(meta.get("event_url"))
        record["event_type"] = clean_text(meta.get("event_type"))
        record["event_mode"] = clean_text(meta.get("event_mode"))

        if not clean_text(record.get("source_tab")):
            record["source_tab"] = "Luma API Event"

        record["_canonical_email"] = normalize_email(canonical_email)
        record["_person_key"] = clean_text(person_key)
        record["_selected_event_id"] = clean_text(event_id)
        record["_selected_event_order"] = int(event_order.get(clean_text(event_id), 999999))
        record["_event_date"] = event_date_value if pd.notna(event_date_value) else None
        record["_registered_relationships"] = int(group["is_registered"].fillna(False).astype(bool).sum())
        record["_attended_relationships"] = int(group["checked_in"].fillna(False).astype(bool).sum())

        records.append(record)

    result = pd.DataFrame(records)

    for col in DB_COLUMNS:
        if col not in result.columns:
            result[col] = None

    # Unique people across all selected events vs person-event output rows.
    audit["canonical_users"] = int(selected["_person_key"].nunique(dropna=False))
    audit["event_user_rows"] = int(len(result))

    # Add per-event canonical counts after identity resolution.
    per_event_canonical = (
        selected.groupby("event_id", dropna=False)["_person_key"]
        .nunique(dropna=False)
        .to_dict()
    )
    for item in audit["per_event"]:
        item["canonical_users"] = int(per_event_canonical.get(item["event_id"], 0))

    return result, audit

def is_replaced_luma_source(value):

    value = normalize_text(value)
    value = value.replace("-", " ")

    if not value.startswith("luma"):
        return False

    return (
        "verified designation" in value
        or "not verified designation" in value
        or "unverified users" in value
    )


@st.cache_data(
    ttl=600,
    show_spinner=False
)
def load_all_data():
    """
    Build the dashboard dataset.

    Important:
    - VIEW remains the source for the overall HiDevs community.
    - The three Luma tables are loaded directly and replace any Luma copies
      coming through VIEW.
    - This guarantees that event-user counts reflect the tables that were
      just verified in Supabase.
    """

    # General community data.
    view_df = fetch_all_rows(
        VIEW,
        tuple(DB_COLUMNS),
    )

    for col in DB_COLUMNS:
        if col not in view_df.columns:
            view_df[col] = None

    view_df["_is_direct_luma"] = False
    view_df["_source_table"] = VIEW

    # Remove the Luma copies from the view. They will be replaced below by
    # direct reads from the three authoritative Luma tables.
    if "source_tab" in view_df.columns:
        view_df = view_df[
            ~view_df["source_tab"].apply(
                is_replaced_luma_source
            )
        ].copy()

    frames = [view_df]

    # Fresh Luma source-of-truth data.
    for table_name in LUMA_TABLES:

        luma_df = fetch_all_rows(
            table_name,
            tuple(DB_COLUMNS),
        )

        if luma_df.empty:
            continue

        for col in DB_COLUMNS:
            if col not in luma_df.columns:
                luma_df[col] = None

        luma_df["_is_direct_luma"] = True
        luma_df["_source_table"] = table_name

        frames.append(luma_df)

    combined = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    for col in DB_COLUMNS:
        if col not in combined.columns:
            combined[col] = None

    return combined


with st.spinner(
    "Loading dashboard data..."
):

    df = load_all_data()


if df.empty:
    st.error(
        "No data returned from Supabase."
    )
    st.stop()


for col in DB_COLUMNS:

    if col not in df.columns:
        df[col] = None


# Normalized event and identity layers used for specific-event filtering.
event_master_df = load_event_master()
identity_map_df = load_identity_map()
profile_join_df = load_profile_join_data(identity_map_df)


# ============================================================
# CITY ENGINE
# ============================================================

@st.cache_resource
def build_city_database():

    gc = geonamescache.GeonamesCache()

    cities = gc.get_cities()
    countries = gc.get_countries()

    city_lookup = {}

    for city in cities.values():

        names = [city.get("name", "")]

        alternates = city.get(
            "alternatenames",
            []
        ) or []

        names.extend(alternates)

        for name in names:

            key = normalize_text(name)

            if not key:
                continue

            city_lookup.setdefault(
                key,
                []
            ).append(city)

    country_lookup = {}

    for country in countries.values():

        name = normalize_text(
            country.get("name")
        )

        code = country.get(
            "iso",
            ""
        )

        if name:
            country_lookup[name] = code

    return city_lookup, country_lookup


CITY_LOOKUP, COUNTRY_LOOKUP = (
    build_city_database()
)


INDIAN_STATE_NAMES = {
    normalize_text(x)
    for x in [
        "Andhra Pradesh",
        "Arunachal Pradesh",
        "Assam",
        "Bihar",
        "Chhattisgarh",
        "Goa",
        "Gujarat",
        "Haryana",
        "Himachal Pradesh",
        "Jharkhand",
        "Karnataka",
        "Kerala",
        "Madhya Pradesh",
        "Maharashtra",
        "Manipur",
        "Meghalaya",
        "Mizoram",
        "Nagaland",
        "Odisha",
        "Punjab",
        "Rajasthan",
        "Sikkim",
        "Tamil Nadu",
        "Telangana",
        "Tripura",
        "Uttar Pradesh",
        "Uttarakhand",
        "West Bengal",
        "Delhi",
        "New Delhi",
        "Chandigarh",
        "Puducherry",
        "Jammu and Kashmir",
        "Ladakh",
        "Andaman and Nicobar Islands",
    ]
}


def raw_contains_india_hint(raw):

    normalized = normalize_text(raw)

    if "india" in normalized:
        return True

    for state in INDIAN_STATE_NAMES:

        if state in normalized:
            return True

    return False


def detect_country_hint(raw):

    normalized = normalize_text(raw)

    for country_name, code in (
        COUNTRY_LOOKUP.items()
    ):

        if country_name and (
            country_name in normalized
        ):
            return code

    return None


def choose_city_candidate(
    candidates,
    raw
):

    if not candidates:
        return None

    # India explicitly mentioned
    if raw_contains_india_hint(raw):

        indian = [
            c
            for c in candidates
            if c.get("countrycode") == "IN"
        ]

        if indian:

            return max(
                indian,
                key=lambda x:
                x.get("population", 0) or 0
            )

    # Other country explicitly mentioned
    country_hint = detect_country_hint(
        raw
    )

    if country_hint:

        country_candidates = [
            c
            for c in candidates
            if c.get("countrycode")
            == country_hint
        ]

        if country_candidates:

            return max(
                country_candidates,
                key=lambda x:
                x.get("population", 0) or 0
            )

    # Otherwise choose most likely/populous
    return max(
        candidates,
        key=lambda x:
        x.get("population", 0) or 0
    )


def resolve_city(raw_value):

    raw = clean_text(raw_value)

    if not raw:
        return None, None

    # Reject very long free-text answers
    if len(raw) > 100:
        return None, None

    # Reject obvious non-location text
    rejected_terms = [
        "yes i am",
        "yes —",
        "yes -",
        "i am in",
        "based out of",
        "providers",
        "company",
        "student",
        "working",
        "remote",
        "earth",
    ]

    lower_raw = normalize_text(raw)

    if any(
        term in lower_raw
        for term in rejected_terms
    ):
        # exception:
        # "Yes, San Francisco"
        # is handled from segments below
        if not raw.lower().startswith(
            "yes,"
        ):
            return None, None

    # --------------------------------------------------------
    # Candidate pieces
    # --------------------------------------------------------

    pieces = re.split(
        r"[,;/|]+",
        raw
    )

    pieces = [
        clean_text(x)
        for x in pieces
        if clean_text(x)
    ]

    # Whole value first
    candidates_to_try = [raw]

    # Then separate parts
    candidates_to_try.extend(pieces)

    # Remove leading conversational words
    cleaned_candidates = []

    for candidate in candidates_to_try:

        candidate = re.sub(
            r"^(yes|city|location)\s*[:\-]?\s*",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip()

        if candidate:
            cleaned_candidates.append(
                candidate
            )

    # --------------------------------------------------------
    # Resolve exact known city
    # --------------------------------------------------------

    for candidate in cleaned_candidates:

        key = normalize_text(candidate)

        possible = CITY_LOOKUP.get(
            key,
            []
        )

        if possible:

            chosen = choose_city_candidate(
                possible,
                raw
            )

            if chosen:

                city_name = chosen.get(
                    "name"
                )

                country_code = chosen.get(
                    "countrycode"
                )

                group = (
                    "India"
                    if country_code == "IN"
                    else "Abroad"
                )

                return city_name, group

    # Not a verified city
    return None, None


# ============================================================
# BUILD RAW CITY -> CLEAN CITY MAP
# ============================================================

@st.cache_data(
    ttl=3600,
    show_spinner=False
)
def build_city_resolution_map(
    raw_cities
):

    result = {}

    for raw in raw_cities:

        city_name, group = (
            resolve_city(raw)
        )

        result[raw] = {
            "city": city_name,
            "group": group,
        }

    return result


unique_raw_cities = tuple(
    sorted(
        {
            clean_text(x)
            for x in df["city"]
            if clean_text(x)
        }
    )
)


city_resolution = (
    build_city_resolution_map(
        unique_raw_cities
    )
)


def get_clean_city(value):

    raw = clean_text(value)

    data = city_resolution.get(
        raw,
        {}
    )

    return data.get("city")


def get_city_group(value):

    raw = clean_text(value)

    data = city_resolution.get(
        raw,
        {}
    )

    return data.get("group")


df["_clean_city"] = (
    df["city"].apply(
        get_clean_city
    )
)

df["_city_group"] = (
    df["city"].apply(
        get_city_group
    )
)


# ============================================================
# UNIQUE CITY OPTIONS
# CASE INSENSITIVE
# ============================================================

def unique_case_insensitive(values):

    mapping = {}

    for value in values:

        value = clean_text(value)

        if not value:
            continue

        key = normalize_text(value)

        if key not in mapping:
            mapping[key] = value

    return sorted(
        mapping.values(),
        key=lambda x:
        normalize_text(x)
    )


india_city_options = (
    unique_case_insensitive(
        df.loc[
            df["_city_group"] == "India",
            "_clean_city"
        ]
    )
)


abroad_city_options = (
    unique_case_insensitive(
        df.loc[
            df["_city_group"] == "Abroad",
            "_clean_city"
        ]
    )
)


# ============================================================
# CATEGORY OPTIONS
# ============================================================

df["_category_filter"] = df.apply(
    get_dashboard_category,
    axis=1,
)

# Fixed UI order: never derive category names from raw database values.
category_options = DESIGNATION_CATEGORY_OPTIONS.copy()


# ============================================================
# NORMALIZED EVENT OPTIONS + DATE RANGE
# ============================================================

# Legacy profile event_date is retained for display only. It is never used to
# decide membership in a selected Luma event.
df["_event_datetime"] = pd.to_datetime(
    df["event_date"],
    errors="coerce",
    utc=True,
)
df["_event_date"] = df["_event_datetime"].dt.date


if not event_master_df.empty and event_master_df["_event_date"].notna().any():
    MIN_EVENT_DATE = event_master_df["_event_date"].dropna().min()
    MAX_EVENT_DATE = event_master_df["_event_date"].dropna().max()
else:
    MIN_EVENT_DATE = date.today()
    MAX_EVENT_DATE = date.today()


def build_event_label_maps(master_df):
    label_to_id = {}
    id_to_label = {}
    base_counts = {}

    rows = []
    for _, row in master_df.iterrows():
        event_id = clean_text(row.get("event_id"))
        event_name = clean_event_label(row.get("event_name")) or "Unnamed Event"
        event_date = row.get("_event_date")
        date_label = event_date.strftime("%d %b %Y") if pd.notna(event_date) else "Date unknown"
        base = f"{event_name} — {date_label}"
        base_counts[base] = base_counts.get(base, 0) + 1
        rows.append((event_id, event_name, event_date, base))

    for event_id, event_name, event_date, base in rows:
        label = base
        if base_counts.get(base, 0) > 1:
            suffix = event_id[-6:] if event_id else "unknown"
            label = f"{base} — {suffix}"

        label_to_id[label] = event_id
        id_to_label[event_id] = label

    return label_to_id, id_to_label


# Events confirmed by the Luma API to have zero guest/user relationships.
# Keep them in luma_event_master for historical accuracy, but hide them from
# the interactive "Luma Event" filter because selecting them can never return users.
ZERO_USER_EVENT_IDS = {
    "evt-1OsMC6h0uq2HdDg",  # Building Digital Clones - Workshop + Hackathon - 2025-04-12
    "evt-X74faDGjYuETatW",  # AI Agent Portfolio Sprint - 2026-07-28
    "evt-b2L8V2ScjResj0a",  # AI Engineering Career Accelerator - 2026-07-28
    "evt-DGW6cmcfMeAmTj2",  # Secure Your Agent - 2026-07-28
    "evt-DvxAzatHFn0gQCC",  # Token Economics - 2026-07-29
    "evt-A93sRzlynWFCHeg",  # Building Reliable Coding Agents - 2026-07-31
    "evt-ZB5htC4FHHFjfGu",  # Stop Hallucinations - 2026-07-31
}

filterable_event_master_df = event_master_df[
    ~event_master_df["event_id"].fillna("").astype(str).isin(ZERO_USER_EVENT_IDS)
].copy()

EVENT_LABEL_TO_ID, EVENT_ID_TO_LABEL = build_event_label_maps(filterable_event_master_df)


# ============================================================
# UNIFIED FOUR-SOURCE IDENTITY LAYER
# ============================================================
# The dashboard source is one combined people pool:
#   1) all_hidevs_users (non-replaced community/master sources)
#   2) luma_verified_designation
#   3) luma_not_verified_designation
#   4) luma_unverified_users
#
# Event selection is ONLY a membership constraint. It no longer swaps the
# result dataset to an event-only profile table. After event membership is
# resolved from luma_user_events, the matching people are looked up across
# the complete combined four-source people pool.

identity_lookup = {}
if not identity_map_df.empty:
    for _, row in identity_map_df.iterrows():
        alias = normalize_email(row.get("alias_email"))
        canonical = normalize_email(row.get("canonical_email"))
        if alias and canonical:
            identity_lookup[alias] = canonical


def add_unified_identity_columns(frame):
    out = frame.copy()

    if "email" not in out.columns:
        out["email"] = None

    out["_email_clean"] = out["email"].apply(normalize_email)
    out["_canonical_email"] = out["_email_clean"].apply(
        lambda x: resolve_identity(x, identity_lookup)
    )

    # Never merge blank-email rows together.
    out["_person_key"] = [
        canonical if canonical else f"row-{idx}"
        for idx, canonical in zip(out.index, out["_canonical_email"])
    ]

    return out


df = add_unified_identity_columns(df)


# ============================================================
# NORMALIZED PER-PERSON EVENT HISTORY
# ============================================================
# The old profile tables contain semicolon-separated event names but only one
# legacy event_date value. Replace that display history with the authoritative
# event_id-based history from luma_user_events + luma_event_master.
#
# Important: event names, dates, types and modes are aggregated in the same
# chronological order. If a user has 5 event names, the event_date cell has 5
# matching dates in the same positions. A one-event user receives one date.
normalized_event_history_df = load_normalized_event_history(
    identity_map_df,
    event_master_df,
)

if not normalized_event_history_df.empty:
    df = df.merge(
        normalized_event_history_df,
        on="_canonical_email",
        how="left",
        sort=False,
    )

    has_normalized_history = (
        df["_history_event_names"]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
    )

    df.loc[has_normalized_history, "luma_event_name"] = (
        df.loc[has_normalized_history, "_history_event_names"]
    )
    df.loc[has_normalized_history, "event_date"] = (
        df.loc[has_normalized_history, "_history_event_dates"]
    )
    df.loc[has_normalized_history, "event_type"] = (
        df.loc[has_normalized_history, "_history_event_types"]
    )
    df.loc[has_normalized_history, "event_mode"] = (
        df.loc[has_normalized_history, "_history_event_modes"]
    )

    df["_has_normalized_event_history"] = has_normalized_history
else:
    df["_has_normalized_event_history"] = False


def rebuild_filter_helpers(frame):
    out = frame.copy()

    for col in DB_COLUMNS:
        if col not in out.columns:
            out[col] = None

    if "_source_table" not in out.columns:
        out["_source_table"] = ""

    out["_category_filter"] = out.apply(get_dashboard_category, axis=1)
    out["_clean_city"] = out["city"].apply(get_clean_city)
    out["_city_group"] = out["city"].apply(get_city_group)

    if "_canonical_email" not in out.columns:
        out = add_unified_identity_columns(out)

    if "_has_normalized_event_history" not in out.columns:
        out["_has_normalized_event_history"] = False

    if "_event_date" not in out.columns:
        # Only legacy single-date rows are parsed here. Normalized multi-event
        # histories are already represented as an aligned semicolon date list.
        legacy_dates = out["event_date"].where(
            ~out["_has_normalized_event_history"].fillna(False).astype(bool),
            None,
        )
        out["_event_date"] = pd.to_datetime(
            legacy_dates,
            errors="coerce",
            utc=True,
        ).dt.date

    return out


def dedupe_filtered_people(frame):
    """
    Return one best display row per identity.

    Normal dashboard mode:
        one row per canonical person.

    Selected-event mode:
        one row per canonical person PER selected event occurrence.
        This is required so selecting multiple events does not collapse those
        events into only one/two visible result values.
    """
    if frame.empty:
        return frame

    out = frame.copy()

    if "_canonical_email" not in out.columns:
        out = add_unified_identity_columns(out)

    def build_dedupe_key(idx, row):
        canonical = normalize_email(row.get("_canonical_email"))
        person_key = clean_text(row.get("_person_key"))
        base = canonical or person_key or f"row-{idx}"

        selected_event_id = clean_text(row.get("_selected_event_id"))
        if selected_event_id:
            return f"{base}||event:{selected_event_id}"

        return base

    out["_dedupe_key"] = [
        build_dedupe_key(idx, row)
        for idx, row in out.iterrows()
    ]

    completeness_cols = [
        "first_name", "last_name", "email", "phone", "linkedin",
        "city", "designation", "company", "about", "are_you",
    ]

    out["_row_completeness"] = out[completeness_cols].apply(
        lambda row: sum(bool(clean_text(v)) for v in row),
        axis=1,
    )

    def source_priority(row):
        source = normalize_text(row.get("_source_table"))
        if source == "luma_verified_designation":
            return 0
        if source == VIEW:
            return 1
        if source == "luma_not_verified_designation":
            return 2
        if source == "luma_unverified_users":
            return 3
        return 4

    out["_source_priority"] = out.apply(source_priority, axis=1)

    out = out.sort_values(
        ["_dedupe_key", "_source_priority", "_row_completeness"],
        ascending=[True, True, False],
        kind="stable",
    )

    out = out.drop_duplicates(subset=["_dedupe_key"], keep="first")
    out = out.drop(
        columns=["_dedupe_key", "_row_completeness", "_source_priority"],
        errors="ignore",
    )

    return out.reset_index(drop=True)

def build_four_source_event_people(event_ids, audience_mode):
    """
    Resolve membership from normalized Luma tables and enrich every
    person-event row from the complete four-source people pool.

    Multi-event selections intentionally preserve the event dimension:
        canonical person + selected event_id = one eventual result row.
    """
    event_people, audit = build_event_user_dataframe(
        event_ids,
        audience_mode,
        event_master_df,
        identity_map_df,
        profile_join_df,
    )

    if event_people.empty:
        return rebuild_filter_helpers(event_people), audit

    event_people = rebuild_filter_helpers(event_people)

    # Event membership metadata, one row per canonical person + selected event.
    meta_cols = [
        "_canonical_email",
        "_person_key",
        "_selected_event_id",
        "_selected_event_order",
        "luma_event_name",
        "event_date",
        "_event_date",
        "event_type",
        "event_mode",
        "source_spreadsheet",
    ]
    for col in meta_cols:
        if col not in event_people.columns:
            event_people[col] = None

    membership_meta = event_people[meta_cols].copy()
    membership_meta = membership_meta.drop_duplicates(
        subset=["_person_key", "_selected_event_id"],
        keep="first",
    )

    canonical_meta = membership_meta[
        membership_meta["_canonical_email"].fillna("").astype(str).str.strip().ne("")
    ].copy()

    # Rename event fields before the merge so profile history columns can never
    # overwrite the exact selected occurrence metadata.
    canonical_meta = canonical_meta.rename(columns={
        "_person_key": "_selected_person_key",
        "luma_event_name": "_selected_luma_event_name",
        "event_date": "_selected_event_date_text",
        "_event_date": "_selected_event_date",
        "event_type": "_selected_event_type",
        "event_mode": "_selected_event_mode",
        "source_spreadsheet": "_selected_event_url",
    })

    if not canonical_meta.empty:
        unified = df.merge(
            canonical_meta,
            on="_canonical_email",
            how="inner",
            sort=False,
        )

        # Exact occurrence metadata wins over all profile-history fields.
        unified["_person_key"] = unified["_selected_person_key"]
        unified["luma_event_name"] = unified["_selected_luma_event_name"]
        unified["event_date"] = unified["_selected_event_date_text"]
        unified["_event_date"] = unified["_selected_event_date"]
        unified["event_type"] = unified["_selected_event_type"]
        unified["event_mode"] = unified["_selected_event_mode"]
        unified["source_spreadsheet"] = unified["_selected_event_url"]

        unified = unified.drop(columns=[
            "_selected_person_key",
            "_selected_luma_event_name",
            "_selected_event_date_text",
            "_selected_event_date",
            "_selected_event_type",
            "_selected_event_mode",
            "_selected_event_url",
        ], errors="ignore")
    else:
        unified = pd.DataFrame(columns=df.columns)

    # Determine which person-event memberships were represented by at least one
    # row in the four-source pool.
    matched_pairs = set()
    if not unified.empty:
        for canonical, event_id in zip(
            unified["_canonical_email"].fillna("").astype(str),
            unified["_selected_event_id"].fillna("").astype(str),
        ):
            canonical = normalize_email(canonical)
            event_id = clean_text(event_id)
            if canonical and event_id:
                matched_pairs.add((canonical, event_id))

    # Keep Luma event rows for identities not present in the four-source pool,
    # including blank-email guests, so current event members never disappear.
    fallback_mask = []
    for _, row in event_people.iterrows():
        canonical = normalize_email(row.get("_canonical_email"))
        event_id = clean_text(row.get("_selected_event_id"))
        fallback_mask.append(
            (not canonical)
            or ((canonical, event_id) not in matched_pairs)
        )

    fallback = event_people[pd.Series(fallback_mask, index=event_people.index)].copy()

    if not fallback.empty:
        if "_source_table" not in fallback.columns:
            fallback["_source_table"] = "Luma API Event"
        else:
            fallback["_source_table"] = fallback["_source_table"].apply(
                lambda x: clean_text(x) or "Luma API Event"
            )
        unified = pd.concat([unified, fallback], ignore_index=True, sort=False)

    return rebuild_filter_helpers(unified), audit


# ============================================================
# FILTER STATE
# ============================================================

if "applied_filters" not in st.session_state:
    st.session_state.applied_filters = {
        "categories": [],
        "city_regions": [],
        "indian_cities": [],
        "abroad_cities": [],
        "event_labels": [],
        "event_audience": "Registered",
        "event_types": [],
        "event_modes": [],
        "use_date_filter": False,
        "date_start": MIN_EVENT_DATE,
        "date_end": MAX_EVENT_DATE,
        "search": "",
    }

# Migrate any browser session created by an older dashboard version.
# Drop obsolete filter state and convert the old blank-value label "No" to "None".
_state_filters = st.session_state.applied_filters
_state_filters["categories"] = [
    value for value in (_state_filters.get("categories") or [])
    if normalize_text(value) != "registered users"
]
_state_filters.pop("email_types", None)
_state_filters["event_types"] = [
    "None" if normalize_text(value) == "no" else value
    for value in (_state_filters.get("event_types") or [])
]
_state_filters["event_modes"] = [
    "None" if normalize_text(value) == "no" else value
    for value in (_state_filters.get("event_modes") or [])
]


def render_checklist_editor(options, selected, key, height=260):
    """
    Lightweight checkbox checklist.

    One data-editor widget replaces hundreds of independent st.checkbox
    widgets. When used inside st.form, ticking boxes does NOT rerun the app.
    """
    options = list(options or [])
    selected = set(selected or [])

    frame = pd.DataFrame({
        "Select": [option in selected for option in options],
        "Option": [str(option) for option in options],
    })

    if frame.empty:
        st.caption("No options available.")
        return []

    edited = st.data_editor(
        frame,
        key=key,
        hide_index=True,
        use_container_width=True,
        height=height,
        disabled=["Option"],
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "✓",
                help="Tick the options you want to include.",
                width="small",
            ),
            "Option": st.column_config.TextColumn(
                "Option",
                width="large",
            ),
        },
    )

    return edited.loc[
        edited["Select"].fillna(False).astype(bool),
        "Option",
    ].tolist()


# ============================================================
# FILTERS — FAST APPLY-ONLY FORM
# ============================================================
# IMPORTANT:
# Streamlit reruns the entire Python script whenever a normal checkbox changes.
# This dashboard has tens of thousands of rows, so the old per-checkbox
# callbacks made the page look frozen. Every filter widget now lives inside
# ONE st.form. Browser-side selections are collected first, and the expensive
# data filtering happens only after Apply Filter is clicked.

st.markdown("## Filters")
st.caption(
    "All four source datasets are searched together. Tick the options you need, "
    "then click Apply Filter. Nothing is recalculated while you are selecting. "
    "Leaving a checklist empty means no restriction for that filter."
)

current_filters = st.session_state.applied_filters
all_event_name_options = sorted(
    EVENT_LABEL_TO_ID.keys(),
    key=normalize_text,
)

EVENT_AUDIENCE_OPTIONS = [
    "Registered",
    "Attended",
    "Invited Only",
    "All Guest List",
]
def normalized_master_filter_options(frame, column):
    if frame.empty or column not in frame.columns:
        return ["None"]

    values = unique_case_insensitive(
        frame[column].fillna("").astype(str).map(str.strip)
    )
    values = [value for value in values if clean_text(value)]
    return sorted(values, key=normalize_text) + ["None"]


# Hide event types that should not appear in the dashboard filter.
# The values remain unchanged in Supabase/luma_event_master; this is UI-only.
HIDDEN_EVENT_TYPES = {
    "Bootcamp",
    "Giveaway",
    "Networking",
    "Orientation",
    "Program",
    "Product / Startup Session",
    "Sprint",
    "Talk / Session",
}

_hidden_event_type_keys = {
    normalize_text(value).replace(" / ", "/")
    for value in HIDDEN_EVENT_TYPES
}

EVENT_TYPE_OPTIONS = [
    value
    for value in normalized_master_filter_options(event_master_df, "event_type")
    if normalize_text(value).replace(" / ", "/") not in _hidden_event_type_keys
]

EVENT_MODE_OPTIONS = normalized_master_filter_options(event_master_df, "event_mode")
CITY_REGION_OPTIONS = ["India", "Abroad"]

with st.form("dashboard_filter_form", clear_on_submit=False):

    with st.expander("Designation Category"):
        pending_categories = render_checklist_editor(
            category_options,
            current_filters.get("categories", []),
            "form_designation_categories",
            height=315,
        )

    with st.expander("City"):
        st.caption("Tick a region and/or specific cities. Empty means all cities.")

        pending_city_regions = render_checklist_editor(
            CITY_REGION_OPTIONS,
            current_filters.get("city_regions", []),
            "form_city_regions",
            height=125,
        )

        st.markdown("**Indian Cities**")
        pending_indian_cities = render_checklist_editor(
            india_city_options,
            current_filters.get("indian_cities", []),
            "form_indian_cities",
            height=320,
        )

        st.markdown("**Abroad Cities**")
        pending_abroad_cities = render_checklist_editor(
            abroad_city_options,
            current_filters.get("abroad_cities", []),
            "form_abroad_cities",
            height=320,
        )

    with st.expander("Luma Event Date Range"):
        pending_use_date_filter = st.checkbox(
            "Limit normalized Luma events by date range",
            value=bool(current_filters.get("use_date_filter", False)),
            key="form_use_event_date_filter",
        )

        default_start = current_filters.get("date_start") or MIN_EVENT_DATE
        default_end = current_filters.get("date_end") or MAX_EVENT_DATE

        pending_date_range = st.date_input(
            "Luma Event Date Range",
            value=(default_start, default_end),
            min_value=MIN_EVENT_DATE,
            max_value=MAX_EVENT_DATE,
            format="DD/MM/YYYY",
            key="form_event_date_range",
        )

    with st.expander("Luma Event"):
        st.caption(
            f"{len(all_event_name_options):,} normalized event occurrence(s). "
            "Duplicate titles stay separate by date/event_id."
        )
        pending_event_labels = render_checklist_editor(
            all_event_name_options,
            current_filters.get("event_labels", []),
            "form_event_labels",
            height=380,
        )

    with st.expander("Event Audience"):
        st.caption("Choose exactly one. Registered is the default.")
        pending_event_audience = render_checklist_editor(
            EVENT_AUDIENCE_OPTIONS,
            [current_filters.get("event_audience") or "Registered"],
            "form_event_audience",
            height=185,
        )

    with st.expander("Event Type"):
        pending_event_types = render_checklist_editor(
            EVENT_TYPE_OPTIONS,
            current_filters.get("event_types", []),
            "form_event_types",
            height=215,
        )

    with st.expander("Event Mode"):
        pending_event_modes = render_checklist_editor(
            EVENT_MODE_OPTIONS,
            current_filters.get("event_modes", []),
            "form_event_modes",
            height=185,
        )

    pending_search_text = st.text_input(
        "Search",
        value=current_filters.get("search", ""),
        placeholder="Search name, email, LinkedIn, designation, company or city",
        key="form_search_text",
    )

    apply_filter_clicked = st.form_submit_button(
        "🔍 Apply Filter",
        type="primary",
        use_container_width=True,
    )


if apply_filter_clicked:
    # Audience is intentionally single-select even though the UI is a checklist.
    if len(pending_event_audience) > 1:
        st.error(
            "Event Audience accepts one option only. "
            "Please keep only one of Registered, Attended, Invited Only, or All Guest List checked."
        )
    else:
        event_audience_pending = (
            pending_event_audience[0]
            if pending_event_audience
            else "Registered"
        )

        if isinstance(pending_date_range, (tuple, list)):
            if len(pending_date_range) == 2:
                date_start, date_end = pending_date_range
            elif len(pending_date_range) == 1:
                date_start = date_end = pending_date_range[0]
            else:
                date_start, date_end = MIN_EVENT_DATE, MAX_EVENT_DATE
        else:
            date_start = date_end = pending_date_range

        st.session_state.applied_filters = {
            "categories": list(pending_categories),
            "city_regions": list(pending_city_regions),
            "indian_cities": list(pending_indian_cities),
            "abroad_cities": list(pending_abroad_cities),
            "event_labels": [
                label
                for label in pending_event_labels
                if label in EVENT_LABEL_TO_ID
            ],
            "event_audience": event_audience_pending,
            "event_types": list(pending_event_types),
            "event_modes": list(pending_event_modes),
            "use_date_filter": bool(pending_use_date_filter),
            "date_start": date_start,
            "date_end": date_end,
            "search": pending_search_text.strip(),
        }

        # Reset result pagination only when filters are actually submitted.
        st.session_state["result_page"] = 1
        st.session_state.pop("result_page_input", None)

# ============================================================
# ACTIVE / APPLIED FILTERS
# ============================================================

F = st.session_state.applied_filters

selected_categories = list(F.get("categories") or [])
selected_city_regions = list(F.get("city_regions") or [])
selected_indian_cities = list(F.get("indian_cities") or [])
selected_abroad_cities = list(F.get("abroad_cities") or [])
selected_event_labels = list(F.get("event_labels") or [])
selected_event_ids = [
    EVENT_LABEL_TO_ID[label]
    for label in selected_event_labels
    if label in EVENT_LABEL_TO_ID
]

# Correct normalized event-date filtering. The legacy person-level event_date
# column is never used for event membership. A date range resolves event_ids
# from luma_event_master. If no explicit event is checked, the range means
# "all normalized event occurrences in this range".
if F.get("use_date_filter") and not event_master_df.empty:
    date_start = F.get("date_start") or MIN_EVENT_DATE
    date_end = F.get("date_end") or MAX_EVENT_DATE

    eligible_event_ids = set(
        event_master_df.loc[
            event_master_df["_event_date"].apply(
                lambda x: pd.notna(x) and date_start <= x <= date_end
            ),
            "event_id",
        ]
        .dropna()
        .astype(str)
    )

    if selected_event_ids:
        selected_event_ids = [
            event_id for event_id in selected_event_ids
            if event_id in eligible_event_ids
        ]
    else:
        selected_event_ids = sorted(eligible_event_ids)
event_audience = F.get("event_audience") or "Registered"
selected_event_types = list(F.get("event_types") or [])
selected_event_modes = list(F.get("event_modes") or [])
search_text = F.get("search") or ""


def _master_value_matches(value, choices):
    if not choices:
        return True

    text = clean_text(value)
    normalized_value = normalize_text(text)

    for choice in choices:
        if normalize_text(choice) == "none":
            if not text:
                return True
        elif normalized_value == normalize_text(choice):
            return True

    return False


# When normalized event occurrences are selected, Event Type and Event Mode
# filters are also evaluated against luma_event_master, never against the old
# person-level semicolon histories.
if selected_event_ids and not event_master_df.empty and (selected_event_types or selected_event_modes):
    selected_id_set = set(str(x) for x in selected_event_ids)
    selected_master = event_master_df[
        event_master_df["event_id"].astype(str).isin(selected_id_set)
    ].copy()

    if selected_event_types:
        selected_master = selected_master[
            selected_master["event_type"].apply(
                lambda x: _master_value_matches(x, selected_event_types)
            )
        ]

    if selected_event_modes:
        selected_master = selected_master[
            selected_master["event_mode"].apply(
                lambda x: _master_value_matches(x, selected_event_modes)
            )
        ]

    selected_event_ids = selected_master["event_id"].dropna().astype(str).tolist()


# ============================================================
# APPLY FILTERS TO THE UNIFIED FOUR-SOURCE PEOPLE POOL
# ============================================================

event_audit = {}
event_source_snapshot = pd.DataFrame()

if selected_event_ids:
    filtered, event_audit = build_four_source_event_people(
        selected_event_ids,
        event_audience,
    )
    event_source_snapshot = filtered.copy()
else:
    filtered = df.copy()


# DESIGNATION CATEGORY — OR semantics across the complete four-source pool.
if selected_categories:
    selected_keys = {normalize_text(x) for x in selected_categories}
    filtered = filtered[
        filtered["_category_filter"].apply(
            lambda x: normalize_text(x) in selected_keys
        )
    ]


# CITY REGION
if selected_city_regions and set(selected_city_regions) != {"India", "Abroad"}:
    filtered = filtered[
        filtered["_city_group"].isin(selected_city_regions)
    ]


# SPECIFIC CITIES
selected_cities = selected_indian_cities + selected_abroad_cities
if selected_cities:
    selected_city_keys = {normalize_text(x) for x in selected_cities}
    filtered = filtered[
        filtered["_clean_city"].apply(
            lambda x: normalize_text(x) in selected_city_keys
        )
    ]


# EVENT TYPE — legacy person-level histories only when no normalized event is selected.
if not selected_event_ids and selected_event_types:
    def event_type_matches(value):
        items = {normalize_text(x) for x in split_multi_value(value)}
        for choice in selected_event_types:
            if normalize_text(choice) == "none" and not clean_text(value):
                return True
            if normalize_text(choice) != "none" and normalize_text(choice) in items:
                return True
        return False

    filtered = filtered[filtered["event_type"].apply(event_type_matches)]


# EVENT MODE — legacy person-level histories only when no normalized event is selected.
if not selected_event_ids and selected_event_modes:
    def event_mode_matches(value):
        items = {normalize_text(x) for x in split_multi_value(value)}
        for choice in selected_event_modes:
            if normalize_text(choice) == "none" and not clean_text(value):
                return True
            if normalize_text(choice) != "none" and normalize_text(choice) in items:
                return True
        return False

    filtered = filtered[filtered["event_mode"].apply(event_mode_matches)]



# SEARCH
if search_text.strip():
    search = search_text.strip()
    SEARCH_COLUMNS = [
        "first_name", "last_name", "email", "linkedin",
        "designation", "company", "city",
    ]

    search_mask = pd.Series(False, index=filtered.index)
    for column in SEARCH_COLUMNS:
        search_mask |= (
            filtered[column]
            .fillna("")
            .astype(str)
            .str.contains(search, case=False, regex=False)
        )

    filtered = filtered[search_mask]


# Final de-duplication. With selected events, the key includes event_id so a
# person who belongs to multiple selected events remains visible once per event.
filtered = dedupe_filtered_people(filtered)

# Multi-event UX: interleave event rows so page 1 immediately shows every
# selected event instead of appearing to contain only the first one/two events.
if selected_event_ids and len(selected_event_ids) > 1 and not filtered.empty:
    event_order_map = {str(event_id): i for i, event_id in enumerate(selected_event_ids)}
    if "_selected_event_id" in filtered.columns:
        filtered["_selected_event_order"] = filtered["_selected_event_id"].astype(str).map(
            event_order_map
        ).fillna(999999).astype(int)
        filtered["_event_row_rank"] = filtered.groupby(
            "_selected_event_id", sort=False
        ).cumcount()
        filtered = filtered.sort_values(
            ["_event_row_rank", "_selected_event_order"],
            kind="stable",
        ).drop(columns=["_event_row_rank"], errors="ignore").reset_index(drop=True)


# ============================================================
# RESULTS
# ============================================================

st.divider()
st.markdown("## Results")

if selected_event_ids:

    selected_labels_text = ", ".join(
        EVENT_ID_TO_LABEL.get(event_id, event_id)
        for event_id in selected_event_ids
    )

    st.caption(
        "Event membership is read from luma_user_events by event_id. "
        "The matching identities are then resolved across the complete four-source "
        "people pool. Event name, date, type and mode come from luma_event_master."
    )

    st.write("Selected event occurrence(s):", selected_labels_text)
    st.write("Audience:", event_audience)

    if len(selected_event_ids) == 1 and not event_master_df.empty:
        selected_event_meta = event_master_df[
            event_master_df["event_id"].astype(str).eq(str(selected_event_ids[0]))
        ]
        if not selected_event_meta.empty:
            selected_meta_row = selected_event_meta.iloc[0]
            st.write("Event Type:", clean_text(selected_meta_row.get("event_type")) or "None")
            st.write("Event Mode:", clean_text(selected_meta_row.get("event_mode")) or "None")

    with st.expander("Event source audit"):
        # Founder-facing audit: show each relationship metric once and use the
        # simple label "Unique Users" for identity-resolved people.
        audit_df = pd.DataFrame([
            {"Metric": "Guest-list relationships", "Count": event_audit.get("guest_rows", 0)},
            {"Metric": "Registered relationships", "Count": event_audit.get("registered_rows", 0)},
            {"Metric": "Attended relationships", "Count": event_audit.get("attended_rows", 0)},
            {"Metric": "Invited-only relationships", "Count": event_audit.get("invited_only_rows", 0)},
            {"Metric": "Unique Users", "Count": event_audit.get("canonical_users", 0)},
        ])

        st.dataframe(
            audit_df,
            use_container_width=True,
            hide_index=True,
        )

        per_event = pd.DataFrame(event_audit.get("per_event") or [])
        if not per_event.empty:
            st.markdown("**Selected event coverage**")
            coverage = per_event.rename(columns={
                "event_name": "Event",
                "event_date": "Date",
                "event_type": "Type",
                "event_mode": "Mode",
                "guest_rows": "Guest List",
                "registered_rows": "Registered",
                "attended_rows": "Attended",
                "invited_only_rows": "Invited Only",
                "canonical_users": "Unique Users",
            })
            keep_cols = [
                "Event", "Date", "Type", "Mode", "Guest List", "Registered",
                "Attended", "Invited Only", "Unique Users",
            ]
            st.dataframe(
                coverage[[c for c in keep_cols if c in coverage.columns]],
                use_container_width=True,
                hide_index=True,
            )


total_matches = len(filtered)

# In multi-event mode the result table intentionally has one row per
# person-event occurrence, while Matching Users remains a unique-person KPI.
if selected_event_ids and "_person_key" in filtered.columns:
    matching_users = int(
        filtered["_person_key"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .nunique(dropna=True)
    )
else:
    matching_users = total_matches


metric1, metric2, metric3, metric4 = (
    st.columns(4)
)


metric1.metric(
    "Matching Users",
    f"{matching_users:,}"
)

if selected_event_ids and len(selected_event_ids) > 1:
    st.caption(
        f"{total_matches:,} person-event result rows across "
        f"{len(selected_event_ids):,} selected events. "
        "Rows are interleaved so every selected event appears immediately."
    )


metric2.metric(
    "With Email",
    f"{filtered['email'].fillna('').astype(str).str.strip().ne('').sum():,}"
)


metric3.metric(
    "With LinkedIn",
    f"{filtered['linkedin'].fillna('').astype(str).str.strip().ne('').sum():,}"
)


metric4.metric(
    "Verified Cities",
    f"{filtered['_clean_city'].notna().sum():,}"
)


# ============================================================
# PAGINATION
# ============================================================

if total_matches == 0:

    st.warning(
        "No users match the selected filters."
    )

else:

    total_pages = max(
        1,
        math.ceil(
            total_matches
            / PAGE_SIZE
        ),
    )


    if "result_page" not in st.session_state:
        st.session_state["result_page"] = 1

    st.session_state["result_page"] = min(
        max(1, int(st.session_state["result_page"])),
        total_pages,
    )

    page = st.number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=st.session_state["result_page"],
        step=1,
        key="result_page_input",
    )

    st.session_state["result_page"] = int(page)


    start = (
        int(page) - 1
    ) * PAGE_SIZE

    end = (
        start + PAGE_SIZE
    )


    page_df = filtered.iloc[
        start:end
    ].copy()


    # --------------------------------------------------------
    # CLEAN DISPLAY COPY
    # --------------------------------------------------------

    result_df = page_df[
        DB_COLUMNS
    ].copy()


    # Display canonical city if verified
    result_df["city"] = (
        page_df["_clean_city"]
        .where(
            page_df[
                "_clean_city"
            ].notna(),
            page_df["city"]
        )
    )


    # Friendly Event Date
    if selected_event_ids:
        # Selected-event mode always contains the exact single occurrence date
        # from luma_event_master for that person-event row.
        result_df["event_date"] = page_df["event_date"].fillna("").astype(str)
    else:
        # General mode may contain many Luma events for the same user. When
        # normalized event history is available, event_date is already an aligned
        # semicolon list (one date for each Luma Event Name, same order).
        normalized_history_mask = (
            page_df.get(
                "_has_normalized_event_history",
                pd.Series(False, index=page_df.index),
            )
            .fillna(False)
            .astype(bool)
        )

        result_df["event_date"] = page_df["event_date"].fillna("").astype(str)

        legacy_mask = ~normalized_history_mask
        if legacy_mask.any():
            result_df.loc[legacy_mask, "event_date"] = (
                page_df.loc[legacy_mask, "_event_date"]
                .apply(
                    lambda x:
                    x.strftime("%d-%m-%Y")
                    if pd.notna(x)
                    else ""
                )
            )


    # --------------------------------------------------------
    # DISPLAY-ONLY DESIGNATION / CATEGORY SOURCE LABELS
    # --------------------------------------------------------

    # The database intentionally stores a blank designation for
    # luma_not_verified_designation rows. For founder-facing display,
    # show the historical label "Not Verified" instead of an empty cell.
    if "designation" in result_df.columns:
        blank_designation = (
            result_df["designation"]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
        )
        not_verified_source = page_df.apply(
            is_luma_not_verified_row,
            axis=1,
        )
        result_df.loc[
            blank_designation & not_verified_source,
            "designation",
        ] = "Not Verified"

    # Display the SAME normalized designation-category label used by the
    # filter. Do not expose raw Supabase labels such as "Founder/Co-Founder"
    # when the dashboard category is simply "Founder".
    if "designation_category" in result_df.columns:
        result_df["designation_category"] = page_df["_category_filter"].fillna("Not Mentioned")

    # Replace internal classification-source codes with clean UI labels.
    if "category_source" in result_df.columns:
        result_df["category_source"] = (
            result_df["category_source"]
            .apply(display_category_source)
        )


    result_df.rename(
        columns=DISPLAY_NAMES,
        inplace=True,
    )


    result_unit = (
        "person-event rows"
        if selected_event_ids and len(selected_event_ids) > 1
        else "users"
    )

    st.caption(
        f"Showing {start + 1:,}–"
        f"{min(end, total_matches):,} "
        f"of {total_matches:,} {result_unit}"
    )


    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True,
        height=600,
        column_config={
            "LinkedIn":
                st.column_config.LinkColumn(
                    "LinkedIn"
                ),

            "Source Spreadsheet":
                st.column_config.LinkColumn(
                    "Source Spreadsheet"
                ),
        },
    )


# ============================================================
# DOWNLOAD
# ============================================================

st.divider()
st.markdown("## Download CSV")

st.caption(
    "Choose the columns you want. "
    "The CSV contains ALL users matching "
    "the active filters."
)


# ============================================================
# DOWNLOAD CHECKBOX STATE
# ============================================================

select_col1, select_col2 = (
    st.columns(2)
)


with select_col1:

    if st.button(
        "Select All Columns",
        use_container_width=True,
    ):

        for db_col in DB_COLUMNS:

            st.session_state[
                f"download_{db_col}"
            ] = True

        st.rerun()


with select_col2:

    if st.button(
        "Clear All Columns",
        use_container_width=True,
    ):

        for db_col in DB_COLUMNS:

            st.session_state[
                f"download_{db_col}"
            ] = False

        st.rerun()


# ============================================================
# DOWNLOAD COLUMN CHECKBOXES
# ============================================================

selected_download_columns = []

checkbox_columns = st.columns(3)


for i, db_column in enumerate(
    DB_COLUMNS
):

    key = (
        f"download_{db_column}"
    )

    if key not in st.session_state:

        st.session_state[key] = True


    with checkbox_columns[
        i % 3
    ]:

        checked = st.checkbox(
            DISPLAY_NAMES[
                db_column
            ],
            key=key,
        )


        if checked:

            selected_download_columns.append(
                db_column
            )


# ============================================================
# DOWNLOAD CSV
# ============================================================

if selected_download_columns:

    download_df = filtered[
        selected_download_columns
    ].copy()


    # Clean city in CSV
    if "city" in download_df.columns:

        download_df["city"] = (
            filtered["_clean_city"]
            .where(
                filtered[
                    "_clean_city"
                ].notna(),
                filtered["city"]
            )
        )


    # Friendly date in CSV
    if "event_date" in download_df.columns:
        if selected_event_ids:
            download_df["event_date"] = filtered["event_date"].fillna("").astype(str)
        else:
            normalized_history_mask = (
                filtered.get(
                    "_has_normalized_event_history",
                    pd.Series(False, index=filtered.index),
                )
                .fillna(False)
                .astype(bool)
            )

            download_df["event_date"] = filtered["event_date"].fillna("").astype(str)

            legacy_mask = ~normalized_history_mask
            if legacy_mask.any():
                download_df.loc[legacy_mask, "event_date"] = (
                    filtered.loc[legacy_mask, "_event_date"]
                    .apply(
                        lambda x:
                        x.strftime("%d-%m-%Y")
                        if pd.notna(x)
                        else ""
                    )
                )


    # Keep downloaded data consistent with what is shown in the dashboard.
    if "designation" in download_df.columns:
        blank_designation = (
            download_df["designation"]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
        )
        not_verified_source = filtered.apply(
            is_luma_not_verified_row,
            axis=1,
        )
        download_df.loc[
            blank_designation & not_verified_source,
            "designation",
        ] = "Not Verified"

    if "designation_category" in download_df.columns:
        download_df["designation_category"] = filtered["_category_filter"].fillna("Not Mentioned")

    if "category_source" in download_df.columns:
        download_df["category_source"] = (
            download_df["category_source"]
            .apply(display_category_source)
        )


    download_df.rename(
        columns={
            col: DISPLAY_NAMES[col]
            for col
            in selected_download_columns
        },
        inplace=True,
    )


    csv_data = (
        download_df
        .to_csv(index=False)
        .encode("utf-8-sig")
    )


    download_unit = (
        "Person-Event Rows"
        if selected_event_ids and len(selected_event_ids) > 1
        else "Users"
    )

    st.download_button(
        label=(
            f"Download "
            f"{len(download_df):,} "
            f"{download_unit} as CSV"
        ),
        data=csv_data,
        file_name=(
            "hidevs_filtered_users.csv"
        ),
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )


else:

    st.info(
        "Select at least one column "
        "to enable CSV download."
    )