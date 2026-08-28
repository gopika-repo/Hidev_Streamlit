
import math
import re
import time
from datetime import date, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st
from supabase import create_client


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="HiDevs Data Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .stApp { background:#f8fafc; }
      .block-container { padding-top:1.3rem; padding-bottom:2rem; }
      .main-title { font-size:34px; font-weight:800; color:#111827; margin-bottom:2px; }
      .subtitle { font-size:14px; color:#64748b; margin-bottom:14px; }
      .section-title { font-size:22px; font-weight:750; color:#111827; margin-top:18px; margin-bottom:10px; }
      .metric-card {
          background:#fff; border:1px solid #e2e8f0; border-radius:12px;
          padding:14px; min-height:88px; box-shadow:0 3px 10px rgba(15,23,42,.04);
      }
      .metric-label { font-size:12px; color:#64748b; font-weight:600; margin-bottom:4px; }
      .metric-value { font-size:24px; font-weight:800; color:#111827; }
      .info-card {
          background:#fff; border:1px solid #dbeafe; border-left:4px solid #6366f1;
          border-radius:10px; padding:11px 13px; color:#334155;
      }
      section[data-testid="stSidebar"] { display:none !important; }
      button[data-testid="stSidebarCollapsedControl"] { display:none !important; }
      div.stButton > button { border-radius:9px; }
      .filter-help { color:#64748b; font-size:12px; margin-bottom:6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SUPABASE CONNECTION
# ============================================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("Could not create Supabase connection.")
    st.exception(e)
    st.stop()


TABLE = "unified_people_dashboard"
EVENT_TABLE = "person_event"


# ============================================================
# VERIFIED SUPABASE CATEGORY FLAGS
# ============================================================
CATEGORY_TO_FLAG = {
    "Founder": "is_founder",
    "Investor": "is_investor",
    "Student / Intern": "is_student_intern",
    "Professional": "is_professional",
    "Senior Leadership / C-Suite": "is_senior_leadership",
    "Director / VP / Senior Professional": "is_director_vp",
    "Professor": "is_professor",
    "Community": "is_community",
    "HR": "is_hr",
    "Other / Blank": "is_other_blank",
}

SOURCE_OPTIONS = ["Luma", "Master"]


# ============================================================
# MAIN CITY FILTER
# Hardcoded from the uploaded unified Supabase CSV + Deepak master Excel.
# Only the MAIN/CANONICAL names are shown in the UI.
# Raw Supabase City values are never overwritten.
# ============================================================
CITY_ALIASES = {
    "Bengaluru": [
        "bengaluru", "bangalore", "banglore", "bengalore", "bangaluru",
        "bengaluru, karnataka", "bangalore urban", "bengaluru urban",
        "devarbisanahalli", "whitefield", "koramangala", "marathahalli",
        "hsr", "electronic city", "indiranagar", "hebbal", "yelahanka",
        "mahadevapura", "adugodi"
    ],
    "Mumbai": [
        "mumbai", "mumbai, maharashtra", "mumbai metropolitan region",
        "bombay", "andheri", "bandra", "powai", "worli", "borivali"
    ],
    "Hyderabad": [
        "hyderabad", "hyderabad, telangana", "secunderabad", "gachibowli",
        "madhapur", "hitech city", "kukatpally", "banjara hills"
    ],
    "Pune": [
        "pune", "pune, maharashtra", "hinjewadi", "wakad", "kharadi", "baner", "akurdi"
    ],
    "Delhi": [
        "delhi", "new delhi", "new delhi, delhi", "south delhi", "north delhi",
        "east delhi", "west delhi"
    ],
    "Gurugram": [
        "gurugram", "gurgaon", "gurugram, haryana", "gurgaon, haryana"
    ],
    "Noida": [
        "noida", "noida, uttar pradesh", "greater noida"
    ],
    "Chennai": [
        "chennai", "chennai, tamil nadu", "madras"
    ],
    "Ahmedabad": [
        "ahmedabad", "ahmedabad, gujarat", "ahemdabad", "ahmadabad"
    ],
    "Jaipur": [
        "jaipur", "jaipur, rajasthan"
    ],
    "Kolkata": [
        "kolkata", "kolkata, west bengal", "calcutta"
    ],
    "Indore": [
        "indore", "indore, madhya pradesh"
    ],
    "Chandigarh": ["chandigarh"],
    "Vadodara": ["vadodara", "baroda"],
    "Thane": ["thane", "thane, maharashtra"],
    "Navi Mumbai": ["navi mumbai"],
    "Kochi": ["kochi", "ernakulam", "cochin"],
    "Coimbatore": ["coimbatore"],
    "Mangaluru": ["mangaluru", "mangalore", "mangluru"],
    "Mysuru": ["mysuru", "mysore"],
    "Belagavi": ["belagavi", "belgaum", "belgavi"],
    "Nagpur": ["nagpur"],
    "Surat": ["surat"],
    "Aurangabad": ["aurangabad"],
    "Lucknow": ["lucknow"],
    "Bhilwara": ["bhilwara", "bhilwara, rajasthan"],

    "San Francisco": [
        "san francisco", "san francisco, california", "san francisco bay area"
    ],
    "New York": [
        "new york", "new york, new york", "new york city",
        "new york city metropolitan area", "ny"
    ],
    "Singapore": ["singapore"],
    "Dubai": ["dubai"],
    "Chicago": ["chicago", "chicago, illinois", "greater chicago area"],
    "London": ["london", "london, england"],
    "Seattle": ["seattle", "seattle, washington", "greater seattle area"],
    "Boston": ["boston", "boston, massachusetts", "greater boston"],
    "Houston": ["houston"],
    "Atlanta": ["atlanta", "atlanta, georgia"],
    "San Jose": ["san jose", "san jose, california", "san josé"],
    "Austin": ["austin", "austin, texas"],
    "Los Angeles": [
        "los angeles", "los angeles, california", "los angeles metropolitan area"
    ],
    "Dallas": ["dallas"],
    "Riyadh": ["riyadh"],
    "Berlin": ["berlin", "berlin, berlin"],
    "Jakarta": ["jakarta"],
    "Washington DC": [
        "washington", "washington, district of columbia",
        "washington dc", "washington dc-baltimore area"
    ],
    "Toronto": ["toronto", "toronto, ontario"],
    "Bangkok": ["bangkok"],
    "Denver": ["denver"],
    "San Diego": ["san diego", "san diego, california"],
    "Miami": ["miami", "miami, florida"],
    "Philadelphia": ["philadelphia"],
    "Istanbul": ["istanbul"],
    "Sydney": ["sydney", "sydney, new south wales"],
    "Vienna": ["vienna"],
    "Minneapolis": ["minneapolis"],
    "Cincinnati": ["cincinnati"],
    "Abu Dhabi": ["abu dhabi", "abu dhabi emirate"],
    "Fremont": ["fremont"],
    "Mountain View": ["mountain view", "mountain view, california"],
    "Palo Alto": ["palo alto", "palo alto, california"],
    "Sunnyvale": ["sunnyvale", "sunnyvale, california"],
    "Santa Clara": ["santa clara", "santa clara, california"],
    "Irvine": ["irvine"],
    "Menlo Park": ["menlo park", "menlo park, california"],
    "San Mateo": ["san mateo", "san mateo, california"],
    "Plano": ["plano"],
    "Quezon City": ["quezon city"],
    "Makati": ["makati"],
    "Pasig": ["pasig"],
}

CITY_OPTIONS = list(CITY_ALIASES.keys())


# ============================================================
# EMAIL DOMAIN FILTER
# ============================================================
EMAIL_DOMAIN_OPTIONS = [
    "Gmail",
    "No Category",
    "Other Domain",
]


DISPLAY_COLUMNS = [
    "FirstName", "LastName", "Are You?", "Event Date", "Email", "Phone", "Linkedin",
    "About", "City", "Designation", "Company Name", "Reason to join our event",
    "Luma Event Name", "Luma Event Type", "Event Mode", "source_spreadsheet_url",
    "Data Source",
]

DOWNLOADABLE_COLUMNS = [
    "FirstName", "LastName", "Are You?", "Event Date", "Email", "Phone", "Linkedin",
    "How Did You Hear About Event?", "City", "Designation", "Company Name",
    "Reason to join our event", "Luma Event Name", "Luma Event Type", "Event Mode",
    "source_spreadsheet_url", "Data Source",
]


# ============================================================
# HELPERS
# ============================================================
def metric_card(label, value):
    try:
        shown = f"{int(value):,}"
    except Exception:
        shown = str(value)

    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{shown}</div></div>',
        unsafe_allow_html=True,
    )


def is_timeout(exc):
    text = f"{type(exc).__name__} {exc}".lower()
    return "timeout" in text or "timed out" in text


def execute_with_retry(builder, attempts=5):
    last = None

    for attempt in range(1, attempts + 1):
        try:
            return builder.execute()
        except Exception as e:
            last = e

            if is_timeout(e) and attempt < attempts:
                time.sleep(attempt * 1.2)
                continue

            raise

    if last is not None:
        raise last

    raise RuntimeError("Supabase request failed without returning an exception.")


def clean_values(values):
    result = []

    for value in values:
        if value is None:
            continue

        text = str(value).strip()

        if not text or text.lower() in {"nan", "none", "null"}:
            continue

        result.append(text)

    return sorted(set(result), key=lambda x: x.lower())


def make_excel(df, sheet_name="Unified People"):
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            index=False,
            sheet_name=sheet_name[:31],
        )

    return buffer.getvalue()


@st.cache_data(ttl=1800, show_spinner=False)
def load_option_view(view_name):
    r = execute_with_retry(
        supabase
        .table(view_name)
        .select("value")
    )

    return clean_values(
        [row.get("value") for row in (r.data or [])]
    )


@st.cache_data(ttl=600, show_spinner=False)
def exact_count(flag=None):
    q = (
        supabase
        .table(TABLE)
        .select("person_key", count="exact")
    )

    if flag:
        q = q.eq(flag, True)

    q = q.limit(1)

    r = execute_with_retry(q)

    return int(r.count or 0)


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
    )[:60]

    return f"{prefix}_{safe}_{abs(hash(str(value))) % 1000000}"


def toggle_pending_value(bucket, value, widget_key):
    selected = set(
        st.session_state.get(bucket, [])
    )

    if st.session_state.get(widget_key, False):
        selected.add(value)
    else:
        selected.discard(value)

    st.session_state[bucket] = sorted(selected)

    # Once a user manually changes one checkbox after pressing All,
    # this becomes a real/custom filter again.
    st.session_state[f"{bucket}__all_selected"] = False


def render_checkbox_list(
    options,
    prefix,
    bucket,
    columns=4,
    search_label=None,
):
    visible = list(options)

    if search_label:
        q = st.text_input(
            search_label,
            key=f"{prefix}_search",
            placeholder="Type to search options...",
        ).strip().lower()

        if q:
            visible = [
                x
                for x in visible
                if q in str(x).lower()
            ]

    selected_now = set(
        st.session_state.get(bucket, [])
    )

    if not visible:
        st.caption("No matching options.")
        return

    cols = st.columns(columns)

    for i, option in enumerate(visible):
        key = option_widget_key(
            prefix,
            option,
        )

        if key not in st.session_state:
            st.session_state[key] = (
                option in selected_now
            )

        with cols[i % columns]:
            st.checkbox(
                str(option),
                key=key,
                on_change=toggle_pending_value,
                args=(bucket, option, key),
            )


def set_filter_selection(bucket, prefix, options, select_all):
    """Update only pending UI state. Nothing is applied until Apply Filter."""
    values = list(options or [])
    selected = values if select_all else []
    st.session_state[bucket] = list(selected)

    # IMPORTANT:
    # All = show every checkbox selected, but DO NOT restrict the Supabase query.
    # None = clear every checkbox, which also means no restriction for this dimension.
    st.session_state[f"{bucket}__all_selected"] = bool(select_all)

    for option in values:
        key = option_widget_key(prefix, option)
        st.session_state[key] = bool(select_all)


def applied_selection(bucket):
    """Convert pending UI state into the actual filter sent to Supabase."""
    if st.session_state.get(f"{bucket}__all_selected", False):
        return []

    return list(st.session_state.get(bucket, []))


def add_matched_category_column(df, selected_categories):
    """
    Backward-compatible no-op.

    Supabase "Are You?" is the authoritative primary category.
    The app must never rewrite or fabricate category labels at display/export time.
    """
    if df is None:
        return df
    return df.copy()

def render_all_none_controls(bucket, prefix, options, key_suffix):
    """All selects every visible filter option; None clears the filter selection."""
    c1, c2, c3 = st.columns([1, 1, 6])

    with c1:
        if st.button("All", key=f"all_{key_suffix}", use_container_width=True):
            set_filter_selection(bucket, prefix, options, True)
            st.rerun()

    with c2:
        if st.button("None", key=f"none_{key_suffix}", use_container_width=True):
            set_filter_selection(bucket, prefix, options, False)
            st.rerun()


def build_city_or_clause(selected_cities):
    clauses = []

    for city in selected_cities:
        aliases = CITY_ALIASES.get(
            city,
            [city],
        )

        for alias in aliases:
            safe = (
                str(alias)
                .replace(",", " ")
                .replace("(", " ")
                .replace(")", " ")
                .strip()
            )

            clauses.append(
                f"City.ilike.*{safe}*"
            )

    return ",".join(clauses)


def add_email_domain_filter(query, selected):
    selected = set(selected or [])

    if not selected:
        return query

    if selected == set(EMAIL_DOMAIN_OPTIONS):
        return query

    clauses = []

    if "Gmail" in selected:
        clauses.extend([
            "email_domain_group.eq.Gmail",
            "email_domain_group.eq.gmail.com",
        ])

    if "No Category" in selected:
        clauses.extend([
            "email_domain_group.is.null",
            "email_domain_group.eq.",
            "email_domain_group.eq.No Email",
            "email_domain_group.eq.Not Specified",
            "email_domain_group.eq.No Category",
        ])

    if "Other Domain" in selected:
        clauses.extend([
            "email_domain_group.eq.Other Domain",
            "email_domain_group.eq.Other Domains",
        ])

    if clauses:
        query = query.or_(
            ",".join(clauses)
        )

    return query


# ============================================================
# PEOPLE FILTERS
# ============================================================
def add_people_filters(query, F):

    # CATEGORY
    # "Are You?" is now the authoritative single primary category in Supabase.
    # Multiple selected categories use OR semantics via PostgREST IN.
    categories = list(
        F.get("categories") or []
    )

    if categories:
        # PostgREST must quote this identifier because the column name
        # contains spaces and a question mark.
        query = query.in_(
            '"Are You?"',
            categories,
        )


    # SOURCE
    sources = list(
        F.get("sources") or []
    )

    if sources:
        allowed = set()

        if "Luma" in sources:
            allowed.update([
                "Luma",
                "Luma + Master",
            ])

        if "Master" in sources:
            allowed.update([
                "Master",
                "Luma + Master",
            ])

        query = query.in_(
            "Data Source",
            sorted(allowed),
        )


    # CITY
    cities = list(
        F.get("cities") or []
    )

    if cities:
        city_clause = build_city_or_clause(
            cities
        )

        if city_clause:
            query = query.or_(
                city_clause
            )


    # EMAIL DOMAIN
    query = add_email_domain_filter(
        query,
        F.get("email_domains") or [],
    )


    # SEARCH
    # Token-based search fixes full-name lookups such as "Vanshika Gupta".
    # Each word must match at least one searchable field, while different
    # words may match different fields (Vanshika -> FirstName, Gupta -> LastName).
    search = (
        F.get("search") or ""
    ).strip()

    if search:
        safe = (
            search
            .replace(",", " ")
            .replace("(", " ")
            .replace(")", " ")
            .replace("*", "")
            .strip()
        )

        tokens = [t for t in safe.split() if t]

        for token in tokens:
            p = f"*{token}*"
            query = query.or_(
                ",".join([
                    f"FirstName.ilike.{p}",
                    f"LastName.ilike.{p}",
                    f"Email.ilike.{p}",
                    f"Phone.ilike.{p}",
                    f"Linkedin.ilike.{p}",
                    f"City.ilike.{p}",
                    f"Designation.ilike.{p}",
                ])
            )

    return query


# ============================================================
# EVENT FILTERS
# ============================================================
def event_filter_active(F):
    return bool(
        F.get("event_names")
        or F.get("event_types")
        or F.get("event_modes")
        or F.get(
            "date_mode",
            "All Dates",
        ) != "All Dates"
    )


@st.cache_data(ttl=600, show_spinner=False)
def resolve_event_person_keys(
    event_names,
    event_types,
    event_modes,
    date_mode,
    custom_start,
    custom_end,
):
    start_date = end_date = None

    today = date.today()

    if date_mode == "Today":
        start_date = end_date = today

    elif date_mode == "Last 7 Days":
        end_date = today
        start_date = (
            today
            - timedelta(days=6)
        )

    elif date_mode == "Last 30 Days":
        end_date = today
        start_date = (
            today
            - timedelta(days=29)
        )

    elif date_mode == "This Month":
        end_date = today
        start_date = (
            today.replace(day=1)
        )

    elif (
        date_mode == "Custom Date Range"
        and custom_start
        and custom_end
    ):
        start_date = custom_start
        end_date = custom_end


    all_keys = []
    page_size = 1000
    start = 0


    while True:
        q = (
            supabase
            .table(EVENT_TABLE)
            .select(
                "person_event_id,person_key"
            )
            .order(
                "person_event_id",
                desc=False,
            )
        )

        if event_names:
            q = q.in_(
                "luma_event_name",
                list(event_names),
            )

        if event_types:
            q = q.in_(
                "luma_event_type",
                list(event_types),
            )

        if event_modes:
            q = q.in_(
                "event_mode",
                list(event_modes),
            )

        if start_date and end_date:
            q = (
                q
                .gte(
                    "event_date",
                    str(start_date),
                )
                .lte(
                    "event_date",
                    str(end_date),
                )
            )

        r = execute_with_retry(
            q.range(
                start,
                start + page_size - 1,
            )
        )

        rows = r.data or []

        if not rows:
            break

        all_keys.extend(
            str(row.get("person_key"))
            for row in rows
            if row.get("person_key")
        )

        if len(rows) < page_size:
            break

        start += page_size

        if start >= 100000:
            break


    return sorted(
        set(all_keys)
    )


def event_key_chunks(keys, size=150):
    keys = list(keys or [])

    return [
        keys[i:i + size]
        for i in range(
            0,
            len(keys),
            size,
        )
    ]


def normalize_email_domain_label(value):
    if value is None:
        return "No Category"

    text = str(value).strip()

    if (
        not text
        or text.lower()
        in {
            "none",
            "nan",
            "null",
            "no email",
            "not specified",
            "no category",
        }
    ):
        return "No Category"

    if text.lower() in {
        "gmail",
        "gmail.com",
    }:
        return "Gmail"

    return "Other Domain"


def canonical_city_matches(
    value,
    selected_cities,
):
    if not selected_cities:
        return True

    if value is None:
        return False

    raw = str(value).strip().lower()

    for city in selected_cities:
        aliases = CITY_ALIASES.get(
            city,
            [city],
        )

        if any(
            str(alias).lower() in raw
            for alias in aliases
        ):
            return True

    return False


def apply_people_filters_to_dataframe(
    df,
    F,
):
    if df.empty:
        return df

    out = df.copy()


    # CATEGORY
    # Keep event-filtered/in-memory results consistent with the server-side
    # primary-category filter.
    categories = list(
        F.get("categories") or []
    )

    if (
        categories
        and "Are You?" in out.columns
    ):
        out = out[
            out["Are You?"]
            .fillna("")
            .isin(categories)
        ]


    # SOURCE
    sources = list(
        F.get("sources") or []
    )

    if (
        sources
        and "Data Source"
        in out.columns
    ):
        allowed = set()

        if "Luma" in sources:
            allowed.update([
                "Luma",
                "Luma + Master",
            ])

        if "Master" in sources:
            allowed.update([
                "Master",
                "Luma + Master",
            ])

        out = out[
            out["Data Source"]
            .fillna("")
            .isin(allowed)
        ]


    # CITY
    cities = list(
        F.get("cities") or []
    )

    if (
        cities
        and "City" in out.columns
    ):
        out = out[
            out["City"].apply(
                lambda x:
                canonical_city_matches(
                    x,
                    cities,
                )
            )
        ]


    # EMAIL DOMAIN
    email_domains = list(
        F.get("email_domains") or []
    )

    if (
        email_domains
        and "email_domain_group"
        in out.columns
    ):
        labels = (
            out["email_domain_group"]
            .apply(
                normalize_email_domain_label
            )
        )

        out = out[
            labels.isin(
                email_domains
            )
        ]


    # SEARCH
    # Same token semantics as the server-side query so event-filtered results
    # and normal results behave identically for full names.
    search = (
        F.get("search") or ""
    ).strip().lower()

    if search:
        cols = [
            "FirstName",
            "LastName",
            "Email",
            "Phone",
            "Linkedin",
            "About",
            "City",
            "Designation",
            "Company Name",
            "Reason to join our event",
            "Are You?",
            "Data Source",
        ]

        tokens = [t for t in search.split() if t]
        combined_mask = pd.Series(True, index=out.index)

        for token in tokens:
            token_mask = pd.Series(False, index=out.index)

            for c in cols:
                if c in out.columns:
                    token_mask |= (
                        out[c]
                        .fillna("")
                        .astype(str)
                        .str.lower()
                        .str.contains(token, regex=False)
                    )

            combined_mask &= token_mask

        out = out[combined_mask]


    return out


def fetch_event_filtered_people(
    F,
    event_keys,
):
    if not event_keys:
        return pd.DataFrame()

    frames = []

    for chunk in event_key_chunks(
        event_keys,
        150,
    ):
        q = (
            supabase
            .table(TABLE)
            .select("*")
            .in_(
                "person_key",
                chunk,
            )
        )

        r = execute_with_retry(q)

        rows = r.data or []

        if rows:
            frames.append(
                pd.DataFrame(rows)
            )


    if not frames:
        return pd.DataFrame()


    df = pd.concat(
        frames,
        ignore_index=True,
    )


    if "person_key" in df.columns:
        df = (
            df
            .drop_duplicates(
                subset=["person_key"],
                keep="first",
            )
        )


    df = (
        apply_people_filters_to_dataframe(
            df,
            F,
        )
    )


    if "person_key" in df.columns:
        df = (
            df
            .sort_values("person_key")
            .reset_index(drop=True)
        )


    return df


# ============================================================
# NORMAL SERVER-SIDE RESULT QUERIES
# ============================================================
def filtered_count(F):
    q = (
        supabase
        .table(TABLE)
        .select(
            "person_key",
            count="exact",
        )
    )

    q = add_people_filters(
        q,
        F,
    )

    q = q.limit(1)

    r = execute_with_retry(q)

    return int(r.count or 0)


def fetch_page(
    F,
    page,
    page_size,
):
    start = (
        (page - 1)
        * page_size
    )

    end = (
        start
        + page_size
        - 1
    )

    q = (
        supabase
        .table(TABLE)
        .select("*")
    )

    q = add_people_filters(
        q,
        F,
    )

    q = (
        q
        .order(
            "person_key",
            desc=False,
        )
        .range(
            start,
            end,
        )
    )

    r = execute_with_retry(q)

    return pd.DataFrame(
        r.data or []
    )


def fetch_all_filtered(
    F,
    max_rows=100000,
):
    rows = []
    page_size = 750
    start = 0


    while True:
        q = (
            supabase
            .table(TABLE)
            .select("*")
        )

        q = add_people_filters(
            q,
            F,
        )

        q = (
            q
            .order(
                "person_key",
                desc=False,
            )
            .range(
                start,
                start + page_size - 1,
            )
        )

        r = execute_with_retry(q)

        batch = r.data or []

        if not batch:
            break

        rows.extend(batch)

        if len(batch) < page_size:
            break

        start += page_size

        if start >= max_rows:
            break


    return pd.DataFrame(rows)


# ============================================================
# HEADER
# ============================================================
st.markdown(
    '<div class="main-title">📊 HiDevs Data Explorer</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">Single Unified Luma + Master Dashboard • Unique People Only • Supabase Connected</div>',
    unsafe_allow_html=True,
)


refresh_col, info_col = st.columns(
    [1, 5]
)


with refresh_col:
    if st.button(
        "🔄 Refresh Data",
        use_container_width=True,
    ):
        st.cache_data.clear()

        st.session_state.pop(
            "prepared_export",
            None,
        )

        st.rerun()


# ============================================================
# OVERVIEW
# ============================================================
try:
    with st.spinner(
        "Loading Supabase overview counts..."
    ):
        total_people = exact_count()

        overview_counts = {
            name: exact_count(flag)
            for name, flag
            in CATEGORY_TO_FLAG.items()
        }

except Exception as e:
    st.error(
        "Could not load dashboard counts from Supabase."
    )

    st.exception(e)

    st.stop()


with info_col:
    st.markdown(
        f'<div class="info-card">'
        f'<b>Unified Luma + Master</b> • '
        f'<b>{total_people:,}</b> unique people • '
        f'data queried directly from Supabase'
        f'</div>',
        unsafe_allow_html=True,
    )


st.markdown(
    '<div class="section-title">📈 Unique People Overview</div>',
    unsafe_allow_html=True,
)


r1 = st.columns(5)

with r1[0]:
    metric_card(
        "Total Unique People",
        total_people,
    )

with r1[1]:
    metric_card(
        "Founders",
        overview_counts["Founder"],
    )

with r1[2]:
    metric_card(
        "Investors",
        overview_counts["Investor"],
    )

with r1[3]:
    metric_card(
        "Students / Intern",
        overview_counts["Student / Intern"],
    )

with r1[4]:
    metric_card(
        "Professionals",
        overview_counts["Professional"],
    )


r2 = st.columns(5)

with r2[0]:
    metric_card(
        "Senior Leadership",
        overview_counts[
            "Senior Leadership / C-Suite"
        ],
    )

with r2[1]:
    metric_card(
        "Director / VP",
        overview_counts[
            "Director / VP / Senior Professional"
        ],
    )

with r2[2]:
    metric_card(
        "Professor",
        overview_counts["Professor"],
    )

with r2[3]:
    metric_card(
        "Community",
        overview_counts["Community"],
    )

with r2[4]:
    metric_card(
        "HR",
        overview_counts["HR"],
    )


# ============================================================
# STATE
# ============================================================
for key in [
    "pending_categories",
    "pending_sources",
    "pending_cities",
    "pending_email_domains",
    "pending_event_names",
    "pending_event_types",
    "pending_event_modes",
]:
    if key not in st.session_state:
        st.session_state[key] = []


if "applied_filters" not in st.session_state:
    st.session_state.applied_filters = {
        "categories": [],
        "sources": [],
        "cities": [],
        "email_domains": [],
        "event_names": [],
        "event_types": [],
        "event_modes": [],
        "date_mode": "All Dates",
        "custom_start": None,
        "custom_end": None,
        "search": "",
    }


# ============================================================
# FILTERS
# ============================================================
st.markdown(
    '<div class="section-title">🔎 Filters</div>',
    unsafe_allow_html=True,
)

st.caption(
    "Click a filter heading to open it. "
    "Results change only after you click Apply Filter. All means no restriction for that filter; None clears its checkbox selections."
)


# CATEGORY
if panel_button(
    "Category",
    "open_category",
):
    category_options = list(CATEGORY_TO_FLAG.keys())
    render_all_none_controls(
        "pending_categories",
        "category",
        category_options,
        "category",
    )
    render_checkbox_list(
        category_options,
        "category",
        "pending_categories",
        columns=4,
    )


# SOURCE
if panel_button(
    "Source",
    "open_source",
):
    render_all_none_controls(
        "pending_sources",
        "source",
        SOURCE_OPTIONS,
        "source",
    )
    render_checkbox_list(
        SOURCE_OPTIONS,
        "source",
        "pending_sources",
        columns=2,
    )


# CITY
if panel_button(
    "City",
    "open_city",
):
    st.caption(
        "Main city names only."
    )

    render_all_none_controls(
        "pending_cities",
        "city",
        CITY_OPTIONS,
        "city",
    )
    render_checkbox_list(
        CITY_OPTIONS,
        "city",
        "pending_cities",
        columns=4,
        search_label="Search City",
    )


# EMAIL DOMAIN
if panel_button(
    "Email Domain",
    "open_email_domain",
):
    render_all_none_controls(
        "pending_email_domains",
        "email_domain",
        EMAIL_DOMAIN_OPTIONS,
        "email_domain",
    )
    render_checkbox_list(
        EMAIL_DOMAIN_OPTIONS,
        "email_domain",
        "pending_email_domains",
        columns=3,
    )


# EVENT NAME
if panel_button(
    "Event Name",
    "open_event_name",
):
    try:
        with st.spinner(
            "Loading Event Name options..."
        ):
            event_name_options = (
                load_option_view(
                    "dashboard_event_name_options"
                )
            )

        st.caption(
            f"{len(event_name_options):,} unique Luma event names."
        )

        render_all_none_controls(
            "pending_event_names",
            "event_name",
            event_name_options,
            "event_name",
        )
        render_checkbox_list(
            event_name_options,
            "event_name",
            "pending_event_names",
            columns=3,
            search_label="Search Event Name",
        )

    except Exception as e:
        st.error(
            "Could not load Event Name options from Supabase."
        )

        st.exception(e)


# EVENT TYPE
if panel_button(
    "Event Type",
    "open_event_type",
):
    try:
        with st.spinner(
            "Loading Event Type options..."
        ):
            event_type_options = (
                load_option_view(
                    "dashboard_event_type_options"
                )
            )

        render_all_none_controls(
            "pending_event_types",
            "event_type",
            event_type_options,
            "event_type",
        )
        render_checkbox_list(
            event_type_options,
            "event_type",
            "pending_event_types",
            columns=4,
        )

    except Exception as e:
        st.error(
            "Could not load Event Type options from Supabase."
        )

        st.exception(e)


# EVENT MODE
if panel_button(
    "Event Mode",
    "open_event_mode",
):
    try:
        with st.spinner(
            "Loading Event Mode options..."
        ):
            event_mode_options = (
                load_option_view(
                    "dashboard_event_mode_options"
                )
            )

            event_mode_options = [
                value
                for value in event_mode_options
                if str(value).strip().lower()
                not in {
                    "not specified",
                    "not specifies",
                    "not specify",
                    "unspecified",
                }
            ]

        render_all_none_controls(
            "pending_event_modes",
            "event_mode",
            event_mode_options,
            "event_mode",
        )
        render_checkbox_list(
            event_mode_options,
            "event_mode",
            "pending_event_modes",
            columns=4,
        )

    except Exception as e:
        st.error(
            "Could not load Event Mode options from Supabase."
        )

        st.exception(e)


# EVENT DATE
if panel_button(
    "Event Date",
    "open_event_date",
):
    d1, d2, d3 = st.columns(3)

    with d1:
        st.selectbox(
            "Event Date",
            [
                "All Dates",
                "Today",
                "Last 7 Days",
                "Last 30 Days",
                "This Month",
                "Custom Date Range",
            ],
            key="pending_date_mode",
        )


    if (
        st.session_state
        .get(
            "pending_date_mode"
        )
        == "Custom Date Range"
    ):
        with d2:
            st.date_input(
                "Custom start",
                value=(
                    date.today()
                    - timedelta(days=30)
                ),
                key="pending_custom_start",
            )

        with d3:
            st.date_input(
                "Custom end",
                value=date.today(),
                key="pending_custom_end",
            )


# SEARCH
st.text_input(
    "Search",
    key="pending_search",
    placeholder=(
        "Name, email, phone, "
        "LinkedIn, city, designation..."
    ),
)


# APPLY FILTERS
if st.button(
    "🔍 Apply Filter",
    type="primary",
    use_container_width=True,
):
    st.session_state.applied_filters = {
        "categories": applied_selection("pending_categories"),

        "sources": applied_selection("pending_sources"),

        "cities": applied_selection("pending_cities"),

        "email_domains": applied_selection("pending_email_domains"),

        "event_names": applied_selection("pending_event_names"),

        "event_types": applied_selection("pending_event_types"),

        "event_modes": applied_selection("pending_event_modes"),

        "date_mode": (
            st.session_state.get(
                "pending_date_mode",
                "All Dates",
            )
        ),

        "custom_start": (
            st.session_state.get(
                "pending_custom_start"
            )
            if (
                st.session_state.get(
                    "pending_date_mode"
                )
                == "Custom Date Range"
            )
            else None
        ),

        "custom_end": (
            st.session_state.get(
                "pending_custom_end"
            )
            if (
                st.session_state.get(
                    "pending_date_mode"
                )
                == "Custom Date Range"
            )
            else None
        ),

        "search": (
            st.session_state
            .get(
                "pending_search",
                "",
            )
            .strip()
        ),
    }


    st.session_state.result_page = 1


    st.session_state.pop(
        "prepared_export",
        None,
    )


    st.rerun()


F = st.session_state.applied_filters


# ============================================================
# EVENT FILTER RESOLUTION
# ============================================================
event_filtered_df = None


if event_filter_active(F):
    try:
        with st.spinner(
            "Applying Luma attendance filters..."
        ):
            event_keys = (
                resolve_event_person_keys(
                    tuple(
                        F.get(
                            "event_names"
                        )
                        or []
                    ),

                    tuple(
                        F.get(
                            "event_types"
                        )
                        or []
                    ),

                    tuple(
                        F.get(
                            "event_modes"
                        )
                        or []
                    ),

                    F.get(
                        "date_mode",
                        "All Dates",
                    ),

                    F.get(
                        "custom_start"
                    ),

                    F.get(
                        "custom_end"
                    ),
                )
            )


            event_filtered_df = (
                fetch_event_filtered_people(
                    F,
                    event_keys,
                )
            )

    except Exception as e:
        st.error(
            "Could not apply Luma event filters from Supabase."
        )

        st.exception(e)

        st.stop()


# ============================================================
# FILTERED RESULTS
# ============================================================
st.markdown(
    '<div class="section-title">🔎 Filtered Results</div>',
    unsafe_allow_html=True,
)


try:
    if event_filtered_df is not None:
        match_count = len(
            event_filtered_df
        )

    else:
        match_count = filtered_count(F)

except Exception as e:
    st.error(
        "Could not count filtered people from Supabase."
    )

    st.exception(e)

    st.stop()


metric_card(
    "Matching Unique Users",
    match_count,
)


active = []


if F.get("categories"):
    active.append(
        "Category: "
        + ", ".join(
            F["categories"]
        )
    )


if F.get("sources"):
    active.append(
        "Source: "
        + ", ".join(
            F["sources"]
        )
    )


if F.get("cities"):
    active.append(
        "City: "
        + ", ".join(
            F["cities"]
        )
    )


if F.get("email_domains"):
    active.append(
        "Email Domain: "
        + ", ".join(
            F["email_domains"]
        )
    )


if F.get("event_names"):
    active.append(
        "Event: "
        + ", ".join(
            F["event_names"][:5]
        )
        + (
            " ..."
            if len(
                F["event_names"]
            ) > 5
            else ""
        )
    )


if F.get("event_types"):
    active.append(
        "Event Type: "
        + ", ".join(
            F["event_types"]
        )
    )


if F.get("event_modes"):
    active.append(
        "Event Mode: "
        + ", ".join(
            F["event_modes"]
        )
    )


if (
    F.get(
        "date_mode"
    )
    != "All Dates"
):
    active.append(
        "Event Date: "
        + F["date_mode"]
    )


if F.get("search"):
    active.append(
        "Search: "
        + F["search"]
    )


if active:
    st.info(
        "Applied filters → "
        + " | ".join(active)
    )


# ============================================================
# PAGINATION
# ============================================================
rows_per_page = st.selectbox(
    "Rows per page",
    [25, 50, 100, 250],
    index=1,
)


total_pages = max(
    1,
    math.ceil(
        match_count
        / rows_per_page
    ),
)


if "result_page" not in st.session_state:
    st.session_state.result_page = 1


st.session_state.result_page = min(
    max(
        1,
        int(
            st.session_state.result_page
        ),
    ),
    total_pages,
)


page = st.number_input(
    "Page",
    min_value=1,
    max_value=total_pages,
    value=(
        st.session_state
        .result_page
    ),
    step=1,
)


st.session_state.result_page = int(page)


try:
    if event_filtered_df is not None:
        start_row = (
            (int(page) - 1)
            * rows_per_page
        )

        page_df = (
            event_filtered_df
            .iloc[
                start_row:
                start_row + rows_per_page
            ]
            .copy()
        )

    else:
        page_df = fetch_page(
            F,
            int(page),
            rows_per_page,
        )

except Exception as e:
    st.error(
        "Could not load the current result page from Supabase."
    )

    st.exception(e)

    st.stop()


# ============================================================
# RESULT TABLE
# ============================================================
if not page_df.empty:

    if "About" in page_df.columns:
        page_df[
            "How Did You Hear About Event?"
        ] = page_df["About"]


    show_cols = []


    for c in DISPLAY_COLUMNS:
        actual = (
            "How Did You Hear About Event?"
            if c == "About"
            else c
        )

        if actual in page_df.columns:
            show_cols.append(actual)


    column_config = {}


    if "Linkedin" in show_cols:
        column_config[
            "Linkedin"
        ] = (
            st.column_config.LinkColumn(
                "LinkedIn",
                display_text="Open Profile",
            )
        )


    if (
        "source_spreadsheet_url"
        in show_cols
    ):
        column_config[
            "source_spreadsheet_url"
        ] = (
            st.column_config.LinkColumn(
                "Spreadsheet URL",
                display_text="Open Sheet",
            )
        )


    st.caption(
        f"Page {page} of {total_pages} • "
        f"{len(page_df):,} rows shown • "
        f"{match_count:,} matching unique users"
    )


    st.dataframe(
        page_df[show_cols],
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )


else:
    st.info(
        "No matching users found."
    )


# ============================================================
# DOWNLOAD
# ============================================================
st.markdown(
    '<div class="section-title">📥 Download Filtered Data</div>',
    unsafe_allow_html=True,
)


st.caption(
    "Select exactly the columns you want in the export."
)


download_cols = st.columns(4)


for i, col in enumerate(
    DOWNLOADABLE_COLUMNS
):
    with download_cols[i % 4]:
        st.checkbox(
            col,
            value=(
                col in {
                    "FirstName",
                    "LastName",
                    "Email",
                    "Phone",
                }
            ),
            key=f"download_col_{i}",
        )


selected_download_columns = [
    col
    for i, col
    in enumerate(
        DOWNLOADABLE_COLUMNS
    )
    if st.session_state.get(
        f"download_col_{i}",
        False,
    )
]


if not selected_download_columns:
    st.warning(
        "Select at least one download column."
    )


if st.button(
    "Prepare Full Filtered Export",
    use_container_width=True,
    disabled=(
        match_count == 0
        or not selected_download_columns
    ),
):
    try:
        with st.spinner(
            f"Preparing {match_count:,} filtered rows..."
        ):

            if event_filtered_df is not None:
                export_df = (
                    event_filtered_df.copy()
                )

            else:
                export_df = (
                    fetch_all_filtered(F)
                )


            if "About" in export_df.columns:
                export_df[
                    "How Did You Hear About Event?"
                ] = export_df["About"]


            cols = [
                c
                for c
                in selected_download_columns
                if c in export_df.columns
            ]


            export_df = (
                export_df[cols]
                .copy()
            )


            st.session_state.prepared_export = {
                "csv": (
                    export_df
                    .to_csv(
                        index=False
                    )
                    .encode(
                        "utf-8-sig"
                    )
                ),

                "xlsx": (
                    make_excel(
                        export_df
                    )
                ),

                "rows": len(
                    export_df
                ),

                "columns": cols,
            }


    except Exception as e:
        st.error(
            "Could not prepare the filtered export."
        )

        st.exception(e)


if st.session_state.get(
    "prepared_export"
):
    ex = (
        st.session_state
        .prepared_export
    )


    st.success(
        f"Export ready: "
        f"{ex['rows']:,} rows • "
        f"{len(ex['columns'])} selected columns"
    )


    x1, x2 = st.columns(2)


    with x1:
        st.download_button(
            "⬇️ Download Excel (.xlsx)",
            ex["xlsx"],
            file_name=(
                "hidevs_unified_people_filtered.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            use_container_width=True,
        )


    with x2:
        st.download_button(
            "⬇️ Download CSV (.csv)",
            ex["csv"],
            file_name=(
                "hidevs_unified_people_filtered.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )


st.markdown(
    '<div style="text-align:center;color:#94a3b8;padding:20px;">'
    'HiDevs Data Explorer • Unified Luma + Master • Supabase'
    '</div>',
    unsafe_allow_html=True,
)
