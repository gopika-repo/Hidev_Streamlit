import streamlit as st
import pandas as pd
from supabase import create_client
from io import BytesIO
import math
import re
import unicodedata
from difflib import SequenceMatcher
from collections import Counter
from datetime import date, timedelta


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="HiDevs Data Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at 10% 10%, rgba(99,102,241,.10), transparent 30%),
            radial-gradient(circle at 90% 20%, rgba(14,165,233,.10), transparent 30%),
            #f8fafc;
    }

    .main-title {
        font-size: 38px;
        font-weight: 800;
        letter-spacing: -1px;
        margin-bottom: 2px;
        color: #111827;
    }

    .subtitle {
        font-size: 16px;
        color: #64748b;
        margin-bottom: 25px;
    }

    .section-title {
        font-size: 24px;
        font-weight: 750;
        color: #111827;
        margin-top: 25px;
        margin-bottom: 15px;
    }

    .metric-card {
        background: rgba(255,255,255,.92);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 5px 18px rgba(15,23,42,.06);
        min-height: 115px;
    }

    .metric-label {
        font-size: 13px;
        color: #64748b;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .metric-value {
        font-size: 28px;
        font-weight: 800;
        color: #111827;
    }

    .info-card {
        background: rgba(255,255,255,.92);
        border: 1px solid #dbeafe;
        border-left: 5px solid #6366f1;
        border-radius: 14px;
        padding: 14px 16px;
        margin: 8px 0 18px 0;
        color: #334155;
    }

    section[data-testid="stSidebar"] {
        display: none !important;
    }
    button[data-testid="stSidebarCollapsedControl"] {
        display: none !important;
    }

    section[data-testid="stSidebar"] label {
        color: #ffffff !important;
    }

    /* Sidebar selected values must remain visible */
    section[data-testid="stSidebar"] div[data-baseweb="select"],
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div *,
    section[data-testid="stSidebar"] div[data-baseweb="select"] span,
    section[data-testid="stSidebar"] div[data-baseweb="select"] div[role="combobox"] {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }

    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }

    section[data-testid="stSidebar"] input[type="text"] {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        background-color: #ffffff !important;
        caret-color: #111827 !important;
        opacity: 1 !important;
    }

    section[data-testid="stSidebar"] input[type="text"]::placeholder {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        opacity: 1 !important;
    }

    div[data-baseweb="popover"],
    div[data-baseweb="popover"] * {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }

    div[data-baseweb="popover"] div[role="option"] {
        background-color: #ffffff !important;
        color: #111827 !important;
    }

    div[data-baseweb="popover"] div[role="option"]:hover {
        background-color: #eef2ff !important;
    }

    .stDownloadButton button {
        border-radius: 10px;
        font-weight: 700;
    }

    .footer {
        text-align: center;
        color: #94a3b8;
        font-size: 13px;
        margin-top: 40px;
        padding: 20px;
    }
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
    st.error("❌ Could not create Supabase connection.")
    st.exception(e)
    st.stop()


# ============================================================
# HEADER / NAVIGATION
# ============================================================

st.markdown(
    '<div class="main-title">📊 HiDevs Data Explorer</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">Single Unified Dashboard &nbsp;•&nbsp; Luma + Master &nbsp;•&nbsp; Unique People Only &nbsp;•&nbsp; Supabase Connected</div>',
    unsafe_allow_html=True,
)

# ============================================================
# HELPERS
# ============================================================

def clean_values(series):
    values = series.dropna().astype(str).str.strip()
    values = values[(values != "") & (~values.str.lower().isin(["nan", "none", "null"]))]
    return sorted(values.unique().tolist(), key=lambda x: x.lower())


def safe_unique(df, column):
    if column not in df.columns:
        return []
    return clean_values(df[column])


def metric_card(label, value):
    try:
        shown = f"{int(value):,}"
    except Exception:
        shown = str(value)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{shown}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def make_excel(df, sheet_name="Data"):
    export_df = df.copy()
    for col in export_df.columns:
        if pd.api.types.is_datetime64tz_dtype(export_df[col].dtype):
            export_df[col] = export_df[col].dt.tz_localize(None)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buffer.getvalue()


@st.cache_data(ttl=300, show_spinner=False)
def load_table(table_name, order_column=None):
    """Load a Supabase table with deterministic pagination.

    IMPORTANT: PostgREST range pagination without an ORDER BY is not stable.
    That can cause later pages to repeat some rows and skip others even when
    the final DataFrame length looks correct. For Luma we therefore paginate
    in ascending primary-key order (id).
    """
    all_rows = []
    page_size = 1000
    start = 0

    while True:
        query = (
            supabase
            .table(table_name)
            .select("*")
        )

        if order_column:
            query = query.order(order_column, desc=False)

        response = (
            query
            .range(start, start + page_size - 1)
            .execute()
        )

        rows = response.data or []
        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < page_size:
            break

        start += page_size
        if start >= 100000:
            break

    result = pd.DataFrame(all_rows)

    # Defensive check for the Luma primary key. If pagination ever returns
    # overlapping pages, keep one row per id rather than allowing duplicate
    # pages to distort filter counts.
    if order_column == "id" and "id" in result.columns:
        result = result.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)

    return result


def apply_exact_filter(df, column, selected):
    if selected == "All" or column not in df.columns:
        return df
    return df[df[column].fillna("").astype(str).str.strip() == str(selected).strip()]


def unique_email_count(df):
    if "email_clean" in df.columns:
        s = df["email_clean"]
    elif "email" in df.columns:
        s = df["email"]
    else:
        return len(df)
    s = s.dropna().astype(str).str.strip().str.lower()
    s = s[(s != "") & (~s.isin(["nan", "none", "null"]))]
    return s.nunique()


def _text_key(value):
    """Comparable lowercase key used by Master-data cleaners."""
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = re.sub(r"\s+", " ", text)
    return text.lower()


MASTER_CITY_ALIASES = {
    # Bengaluru
    "bangalore": "Bengaluru",
    "banglore": "Bengaluru",
    "bangaluru": "Bengaluru",
    "bengalore": "Bengaluru",
    "bengluru": "Bengaluru",
    "bamgalore": "Bengaluru",
    "banaglore": "Bengaluru",
    "banagmore": "Bengaluru",
    "banagluru": "Bengaluru",
    "benagluru": "Bengaluru",
    "bengalaru": "Bengaluru",
    "begaluru": "Bengaluru",
    "banglalore": "Bengaluru",
    "benguluru": "Bengaluru",
    "bengaluru urban": "Bengaluru",

    # Bengaluru localities
    "whitefield": "Bengaluru",
    "marathahalli": "Bengaluru",
    "marathalli": "Bengaluru",
    "koramangala": "Bengaluru",
    "hsr": "Bengaluru",
    "hsr layout": "Bengaluru",
    "electronic city": "Bengaluru",
    "btm": "Bengaluru",
    "btm layout": "Bengaluru",
    "banashankari": "Bengaluru",
    "jayanagar": "Bengaluru",
    "indiranagar": "Bengaluru",
    "hebbal": "Bengaluru",
    "yelahanka": "Bengaluru",
    "mahadevapura": "Bengaluru",
    "adugodi": "Bengaluru",
    "devarbisanahalli": "Bengaluru",
    "bommanahalli": "Bengaluru",
    "boomanahalli": "Bengaluru",
    "boomanhali": "Bengaluru",
    "attiguppe": "Bengaluru",
    "dasarhali": "Bengaluru",
    "dasarahalli": "Bengaluru",
    "hulimavu": "Bengaluru",
    "madiwala": "Bengaluru",

    # Hyderabad + localities
    "hydrabad": "Hyderabad",
    "hyderbad": "Hyderabad",
    "hydrebad": "Hyderabad",
    "secunderabad": "Hyderabad",
    "secunderābād": "Hyderabad",
    "gachibowli": "Hyderabad",
    "madhapur": "Hyderabad",
    "hitech city": "Hyderabad",
    "financial district": "Hyderabad",
    "kukatpally": "Hyderabad",
    "serilingampally": "Hyderabad",
    "banjara hills": "Hyderabad",
    "bachupalle": "Hyderabad",
    "khairatabad": "Hyderabad",
    "l.b.nagar": "Hyderabad",
    "nizampet": "Hyderabad",
    "shamshabad": "Hyderabad",

    # Pune + localities
    "hinjewadi": "Pune",
    "wakad": "Pune",
    "kharadi": "Pune",
    "akurdi": "Pune",
    "baner gaon": "Pune",

    # Mumbai + localities
    "bombay": "Mumbai",
    "worli": "Mumbai",
    "andheri": "Mumbai",
    "bandra": "Mumbai",
    "powai": "Mumbai",
    "borivali": "Mumbai",

    # Common Indian spelling variants
    "gurgaon": "Gurugram",
    "mysore": "Mysuru",
    "mangalore": "Mangaluru",
    "mangluru": "Mangaluru",
    "belgaum": "Belagavi",
    "belgavi": "Belagavi",
    "calcutta": "Kolkata",
    "cochin": "Kochi",
    "trivandrum": "Thiruvananthapuram",
    "thiruvanthapuram": "Thiruvananthapuram",
    "vizag": "Visakhapatnam",
    "visakhapatanam": "Visakhapatnam",
    "ahemdabad": "Ahmedabad",
    "ahmadabad": "Ahmedabad",
    "bhubaneshwar": "Bhubaneswar",
    "gandhi nagar": "Gandhinagar",
    "chinthamani": "Chintamani",
    "chintamni": "Chintamani",
    "chikballapur": "Chikkaballapur",
    "chickballapur": "Chikkaballapur",
    "chikaballapur": "Chikkaballapur",
    "chitoor": "Chittoor",
    "chittor": "Chittoor",
    "ballabgarh": "Ballabhgarh",
    "madanapalli": "Madanapalle",
    "madanapally": "Madanapalle",

    # International spelling / duplicate variants
    "new york city": "New York",
    "nyc": "New York",
    "ny": "New York",
    "bankok": "Bangkok",
    "bangkok city": "Bangkok",
    "san josé": "San Jose",
}


MASTER_CITY_NOT_CITY = {
    # Countries
    "india", "united states", "usa", "us", "united kingdom", "uk",
    "canada", "australia", "singapore country",

    # Indian states / regions
    "karnataka", "maharashtra", "gujarat", "rajasthan", "kerala",
    "telangana", "tamil nadu", "tamilnadu", "uttar pradesh",
    "madhya pradesh", "andhra pradesh", "west bengal", "punjab",
    "haryana", "odisha", "bihar", "assam", "uttarakhand", "uttrakhand",

    # Non-city business/profile values seen in Master data
    "banking", "financial services", "software development",
    "information technology & services", "it services and it consulting",
    "remote", "remote (india)", "world university centre",
    "dharmaram college", "technology, information and internet",
    "partnership (data analytics software)",
}


MASTER_CITY_BAD_KEYWORDS = (
    "university", " college", "college ", "school", "institute",
    "technologies", "technology", "software", "solutions", "services",
    "consulting", "private limited", "pvt ltd", " corporation",
    "company", "hostel", "apartment", "building", "road no",
    "street", "near ", "opposite ", "floor", "campus",
)


def canonical_master_city(value):
    """Return one city name or Not Specified.

    The Master City filter intentionally excludes Not Specified, so addresses,
    states, countries, companies, industries and malformed strings never become
    dropdown options.
    """
    if value is None or pd.isna(value):
        return "Not Specified"

    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = re.sub(r"\s+", " ", text)

    if not text:
        return "Not Specified"

    # Encoding corruption / URLs / email / numeric addresses.
    if "�" in text or "http://" in text.lower() or "https://" in text.lower() or "@" in text:
        return "Not Specified"
    if re.search(r"\d{4,}", text):
        return "Not Specified"

    key = text.lower().strip(" .,-_/")

    if not key or key in MASTER_CITY_NOT_CITY:
        return "Not Specified"

    if any(keyword in f" {key} " for keyword in MASTER_CITY_BAD_KEYWORDS):
        return "Not Specified"

    # Known aliases/localities first.
    if key in MASTER_CITY_ALIASES:
        return MASTER_CITY_ALIASES[key]

    # Remove state/country suffixes.  Example:
    # Hyderabad, Telangana, India -> Hyderabad
    # Bhilwara, Rajasthan -> Bhilwara
    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if len(parts) >= 2:
            first_key = parts[0].lower().strip(" .,-_/")
            if first_key in MASTER_CITY_ALIASES:
                return MASTER_CITY_ALIASES[first_key]
            if (
                first_key
                and first_key not in MASTER_CITY_NOT_CITY
                and not any(k in f" {first_key} " for k in MASTER_CITY_BAD_KEYWORDS)
                and not re.search(r"\d", first_key)
            ):
                text = parts[0].strip()
                key = first_key

    # Remove obvious "<city> state/country" suffixes without commas.
    state_suffixes = (
        " karnataka", " maharashtra", " gujarat", " rajasthan",
        " telangana", " tamil nadu", " tamilnadu", " uttar pradesh",
        " madhya pradesh", " andhra pradesh", " west bengal",
        " punjab", " haryana", " odisha", " bihar", " kerala",
        " india",
    )
    for suffix in state_suffixes:
        if key.endswith(suffix) and len(key) > len(suffix):
            text = text[: len(text) - len(suffix)].strip(" ,.-")
            key = text.lower()
            break

    if key in MASTER_CITY_ALIASES:
        return MASTER_CITY_ALIASES[key]

    if key in MASTER_CITY_NOT_CITY:
        return "Not Specified"

    # Reject strings that still look like addresses / descriptions.
    if re.search(r"\d", text):
        return "Not Specified"
    if len(text) > 42:
        return "Not Specified"
    if len(text.split()) > 5:
        return "Not Specified"

    # Normalize all-uppercase/lowercase duplicates.
    # Keep normal title punctuation such as "Gometz-la-Ville".
    cleaned = " ".join(word.capitalize() for word in text.split())

    # Restore common canonical forms.
    canonical_case = {
        "Bengaluru": "Bengaluru",
        "Bhubaneswar": "Bhubaneswar",
        "Gandhinagar": "Gandhinagar",
        "New York": "New York",
        "San Francisco": "San Francisco",
        "San Jose": "San Jose",
        "Los Angeles": "Los Angeles",
        "Abu Dhabi": "Abu Dhabi",
        "Ho Chi Minh City": "Ho Chi Minh City",
        "Kuala Lumpur": "Kuala Lumpur",
        "Hong Kong": "Hong Kong",
    }
    return canonical_case.get(cleaned, cleaned)


def build_master_city_filter(series):
    """
    STRICT dashboard city cleaner.

    Goal: show only useful, canonical CITY names in the dashboard.
    - Normalizes common variants such as Bangalore/Bengaluru.
    - Converts a small number of obvious locality/region variants.
    - Rejects countries, states, industries, mixed-city strings, and noise.
    - Uses a curated allow-list so the dropdown stays compact.
    """

    # Canonical aliases observed in the uploaded Luma + Master workbooks.
    aliases = {
        # India
        "bangalore": "Bengaluru",
        "bangaluru": "Bengaluru",
        "bengaluru": "Bengaluru",
        "banglore": "Bengaluru",
        "bangalore urban": "Bengaluru",
        "bengaluru urban": "Bengaluru",
        "bangalore karnataka": "Bengaluru",
        "bengaluru karnataka": "Bengaluru",
        "devarbisanahalli": "Bengaluru",
        "panathur": "Bengaluru",
        "k r puram": "Bengaluru",
        "kr puram": "Bengaluru",
        "mahadevapura": "Bengaluru",
        "sarvajna nagar": "Bengaluru",
        "gurgaon": "Gurugram",
        "gurugram": "Gurugram",
        "new delhi": "Delhi",
        "delhi": "Delhi",
        "delhi india": "Delhi",
        "pune maharashtra india": "Pune",
        "pune maharashtra": "Pune",
        "hyderabad telangana india": "Hyderabad",
        "hyderabad telangana": "Hyderabad",
        "gandhinagar gujarat": "Gandhinagar",
        "ernakulam": "Kochi",
        # Global common variants
        "new york city": "New York",
        "ny": "New York",
        "san francisco california": "San Francisco",
        "st louis": "St. Louis",
        "st louis missouri": "St. Louis",
        "houstun": "Houston",
    }

    # Deliberately compact: only main/useful cities retained.
    allowed_cities = {
        # India
        "Bengaluru", "Mumbai", "Pune", "Gurugram", "Delhi",
        "Chennai", "Hyderabad", "Noida", "Ahmedabad", "Kolkata", "Jaipur",
        "Thane", "Vadodara", "Indore", "Navi Mumbai", "Kochi", "Chandigarh",
        "Ludhiana", "Coimbatore", "Surat", "Nagpur", "Mohali", "Nashik",
        "Bhubaneswar", "Faridabad", "Lucknow", "Ghaziabad", "Gandhinagar",
        "Rajkot", "Aurangabad", "Raipur",
        # Major international cities actually represented in the uploaded data
        "Singapore", "New York", "San Francisco", "Chicago", "Dubai", "Boston",
        "Seattle", "Houston", "Atlanta", "Austin", "Los Angeles", "San Jose",
        "Dallas", "Jakarta", "Washington", "San Diego", "Riyadh", "London",
        "Bangkok", "Denver", "Philadelphia", "Vienna", "Miami", "Baltimore",
        "Cincinnati", "Minneapolis", "Columbus", "Portland", "Abu Dhabi",
        "Charlotte", "Phoenix", "Mountain View", "Redwood City", "Irvine",
        "Madison", "Princeton", "Kuala Lumpur", "Palo Alto", "Salt Lake City",
        "Montreal", "Istanbul", "Sunnyvale", "Nashville", "Orlando", "Toronto",
        "Dublin", "Tokyo", "Munich", "Brussels", "Amsterdam", "Melbourne",
        "Milan", "Paris", "St. Louis",
    }

    # Direct canonical lookup ignoring case.
    canonical_lookup = {c.lower(): c for c in allowed_cities}

    def normalize_key(value):
        if pd.isna(value):
            return ""
        s = unicodedata.normalize("NFKD", str(value))
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = s.strip().lower()
        s = re.sub(r"[|;/]+", " ", s)
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def clean_one(value):
        key = normalize_key(value)
        if not key:
            return "Not Specified"

        # Explicitly reject mixed-city / non-city values instead of guessing.
        if re.search(r"\b(and|or)\b", key):
            return "Not Specified"

        if key in aliases:
            result = aliases[key]
            return result if result in allowed_cities else "Not Specified"

        if key in canonical_lookup:
            return canonical_lookup[key]

        # Handle safe "City, State, Country" style values only when the FIRST
        # component itself is one of our curated cities.
        raw = str(value).strip()
        first = re.split(r"[,|;/]", raw)[0].strip()
        first_key = normalize_key(first)
        if first_key in aliases:
            result = aliases[first_key]
            return result if result in allowed_cities else "Not Specified"
        if first_key in canonical_lookup:
            return canonical_lookup[first_key]

        return "Not Specified"

    return series.apply(clean_one)


MASTER_DESIGNATION_GARBAGE = {
    "", "nan", "none", "null", "other", "others", "n/a", "na",
    "study", "bachelors", "bacherlors", "engineering",
    "information technology", "computer science and technology",
    "exploring ai tools", "building production apps",
    "prototyping side projects", "learn mcp", "research intent",
}


MASTER_DESIGNATION_COMPANIES = {
    "accenture", "tcs", "infosys", "wipro", "cognizant", "hcl",
    "ibm", "google", "amazon", "microsoft", "oracle", "deloitte",
    "capgemini", "tech mahindra", "ltimindtree",
}


def canonical_master_designation(value):
    """Clean a Master designation while preserving legitimate specialist roles."""
    if value is None or pd.isna(value):
        return "Not Specified"

    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = re.sub(r"\s+", " ", text)

    if not text:
        return "Not Specified"

    key = text.lower().strip(" .,-_/")

    if key in MASTER_DESIGNATION_GARBAGE or key in MASTER_DESIGNATION_COMPANIES:
        return "Not Specified"

    # Years / batches / numeric junk.
    if re.fullmatch(r"\d+", key) or re.fullmatch(r"20\d{2}", key):
        return "Not Specified"
    if re.match(r"^20\d{2}\s*[-/]", key):
        return "Not Specified"

    # Student-year normalization.
    if re.search(r"\b(1|1st|first)\s*(year|yr)\b", key):
        return "1st Year"
    if re.search(r"\b(2|2nd|2rd|second)\s*(year|yr)\b", key):
        return "2nd Year"
    if re.search(r"\b(3|3rd|third)\s*(year|yr)\b", key):
        return "3rd Year"
    if re.search(r"\b(4|4th|4rth|fourth)\s*(year|yr)\b", key) or "final year" in key:
        return "4th Year"

    # Very common executive / founder variants.
    exact_map = {
        "chief executive officer": "CEO",
        "ceo": "CEO",
        "ceo.": "CEO",
        "chief technology officer": "CTO",
        "cto": "CTO",
        "chief information officer": "CIO",
        "cio": "CIO",
        "chief operating officer": "COO",
        "coo": "COO",
        "chief financial officer": "CFO",
        "cfo": "CFO",
        "chief information security officer": "CISO",
        "ciso": "CISO",
        "co founder": "Co-Founder",
        "co-founder": "Co-Founder",
        "cofounder": "Co-Founder",
        "head it": "Head of IT",
        "head - it": "Head of IT",
        "head of it": "Head of IT",
        "head of information technology": "Head of IT",
        "it head": "Head of IT",
        "it director": "IT Director",
        "director of information technology": "IT Director",
        "director it": "IT Director",
        "sde": "Software Engineer",
        "sde1": "Software Engineer",
        "sre": "Site Reliability Engineer",
        "devops": "DevOps Engineer",
        "ui ux designer": "UI/UX Designer",
        "ui/ux designer": "UI/UX Designer",
    }
    if key in exact_map:
        return exact_map[key]

    # Compound founder/executive titles.
    if ("founder" in key or "co-founder" in key or "co founder" in key) and "ceo" in key:
        return "Founder & CEO"
    if ("founder" in key or "co-founder" in key or "co founder" in key) and "cto" in key:
        return "Founder & CTO"

    # Preserve real specialist designations; normalize whitespace/casing only.
    # Avoid title-casing acronyms aggressively when the source already looks clean.
    if text.isupper() and len(text) <= 6:
        return text

    return text


def build_master_designation_filter(master_df):
    """
    Convert thousands of raw designation strings into a compact set of useful
    main roles. Random company names, sentences, volunteer labels and noise are
    intentionally excluded as Not Specified.
    """

    if "Designation" not in master_df.columns:
        return pd.Series("Not Specified", index=master_df.index)

    def norm(value):
        if pd.isna(value):
            return ""
        s = unicodedata.normalize("NFKD", str(value))
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = s.lower().strip()
        s = re.sub(r"[^a-z0-9+#/& -]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def classify(value):
        s = norm(value)
        if not s or s in {"none", "nan", "na", "n/a", "other", "not specified"}:
            return "Not Specified"

        # Student years — preserve the four CEO-requested canonical values.
        if re.search(r"\b(1|1st|first)\s*(year|yr)\b", s):
            return "1st Year"
        if re.search(r"\b(2|2nd|2rd|second)\s*(year|yr)\b", s):
            return "2nd Year"
        if re.search(r"\b(3|3rd|third)\s*(year|yr)\b", s):
            return "3rd Year"
        if re.search(r"\b(4|4th|4rth|fourth)\s*(year|yr)\b", s) or "final year" in s:
            return "4th Year"

        # Generic student / intern.
        if re.search(r"\b(student|intern|internship|trainee|fresher|undergraduate|graduate student)\b", s):
            return "Student / Intern"

        # Founders / ownership.
        if re.search(r"\b(co[- ]?founder|founder|entrepreneur)\b", s):
            return "Founder / Co-Founder"

        # C-suite — keep the main executive roles distinct.
        if re.search(r"\b(chief executive officer|group ceo|ceo)\b", s):
            return "CEO"
        if re.search(r"\b(chief technology officer|chief technical officer|group cto|field cto|cto)\b", s):
            return "CTO"
        if re.search(r"\b(chief information officer|group cio|cio)\b", s):
            return "CIO"
        if re.search(r"\b(chief operating officer|chief operations officer|coo)\b", s):
            return "COO"
        if re.search(r"\b(chief financial officer|cfo)\b", s):
            return "CFO"
        if re.search(r"\b(chief information security officer|ciso)\b", s):
            return "CISO"
        if re.search(r"\b(chief product officer|chief product & technology officer|chief product and technology officer)\b", s):
            return "Chief Product Officer"
        if re.search(r"\b(chief people officer|chief human resources officer|chro)\b", s):
            return "Chief People / HR Officer"
        if re.search(r"\bchief (digital|innovation|risk|business|data|marketing|strategy|growth) officer\b", s):
            return "Other C-Suite"

        # Senior leadership.
        if re.search(r"\b(managing director|joint managing director|\\bmd\\b)\b", s):
            return "Managing Director"
        if re.search(r"\b(executive vice president|senior vice president|associate vice president|assistant vice president|vice president|vp|svp|avp)\b", s):
            return "Vice President"
        if re.search(r"\b(chairman|chairperson|president)\b", s):
            return "President / Chairman"
        if re.search(r"\b(director|executive director)\b", s):
            return "Director"
        if re.search(r"\b(head of|global head|regional head|department head|business head|technology head|engineering head|product head|sales head|marketing head|hr head|people head)\b", s):
            return "Head"

        # Investors / partners.
        if re.search(r"\b(investor|venture capitalist|angel investor)\b", s):
            return "Investor"
        if re.search(r"\b(managing partner|general partner|venture partner|partner)\b", s):
            return "Partner"

        # Core technology / product / data roles.
        if re.search(r"\b(ai engineer|artificial intelligence engineer|machine learning engineer|ml engineer|genai engineer|generative ai engineer|prompt engineer)\b", s):
            return "AI / ML Engineer"
        if re.search(r"\b(data scientist|data science)\b", s):
            return "Data Scientist"
        if re.search(r"\b(data analyst|analytics analyst)\b", s):
            return "Data Analyst"
        if re.search(r"\b(software engineer|software developer|sde|full stack|fullstack|frontend|front end|backend|back end|application developer|web developer)\b", s):
            return "Software Engineer / Developer"
        if re.search(r"\b(solution architect|solutions architect|software architect|enterprise architect|cloud architect|technical architect|architect)\b", s):
            return "Architect"
        if re.search(r"\b(engineering manager|manager engineering|engineering lead|tech lead|technical lead|team lead)\b", s):
            return "Engineering / Tech Lead"
        if re.search(r"\b(it manager|information technology manager|manager it|chief manager it)\b", s):
            return "IT Manager"
        if re.search(r"\b(product manager|product management|product owner)\b", s):
            return "Product Manager"
        if re.search(r"\b(project manager|program manager|programme manager|delivery manager)\b", s):
            return "Project / Program Manager"
        if re.search(r"\b(business analyst)\b", s):
            return "Business Analyst"
        if re.search(r"\b(consultant|consulting|advisor|adviser)\b", s):
            return "Consultant / Advisor"
        if re.search(r"\b(human resources|\\bhr\\b|talent acquisition|recruiter|people operations)\b", s):
            return "HR / People"
        if re.search(r"\b(sales|business development|account executive|revenue)\b", s):
            return "Sales / Business Development"
        if re.search(r"\b(marketing|growth|brand|content|social media)\b", s):
            return "Marketing / Growth"
        if re.search(r"\b(manager|senior manager|general manager)\b", s):
            return "Manager"

        # Generic professional labels only if clearly a role, not arbitrary text.
        if re.fullmatch(r"(tech|technology|it) professional", s):
            return "Technology Professional"

        return "Not Specified"

    return master_df["Designation"].apply(classify)


# ============================================================
# UNIFIED LUMA + MASTER PEOPLE DASHBOARD
# ============================================================

st.markdown(
    '<div class="section-title">👥 Unified People Dashboard</div>',
    unsafe_allow_html=True,
)

refresh_col, info_col = st.columns([1, 5])
with refresh_col:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    with st.spinner("Loading unified people data from Supabase..."):
        people_df = load_table("unified_people_dashboard", order_column="person_key")
        event_df = load_table("person_event", order_column="person_event_id")
except Exception as e:
    st.error("Could not load unified dashboard data from Supabase.")
    st.exception(e)
    st.stop()

if people_df.empty:
    st.warning('The "unified_people_dashboard" table returned no records.')
    st.stop()

for frame in [people_df, event_df]:
    for col in frame.columns:
        if frame[col].dtype == "object":
            frame[col] = frame[col].apply(
                lambda x: x.strip() if isinstance(x, str) else x
            )

if "event_date" in event_df.columns:
    event_df["event_date"] = pd.to_datetime(
        event_df["event_date"], errors="coerce"
    ).dt.date

# Strict canonical dashboard values derived from the uploaded Luma + Master data.
people_df["_city_filter"] = (
    build_master_city_filter(people_df["City"])
    if "City" in people_df.columns
    else "Not Specified"
)
people_df["_designation_filter"] = build_master_designation_filter(people_df)

# For CEO-facing display/export, show the cleaned values rather than noisy originals.
people_df["City Clean"] = people_df["_city_filter"]
people_df["Designation Clean"] = people_df["_designation_filter"]

with info_col:
    unique_events = (
        event_df["luma_event_name"].nunique()
        if "luma_event_name" in event_df.columns else 0
    )
    st.markdown(
        f"""
        <div class="info-card">
            <b>Unified Luma + Master</b> &nbsp;•&nbsp;
            <b>{len(people_df):,}</b> unique people &nbsp;•&nbsp;
            <b>{unique_events:,}</b> Luma events
        </div>
        """,
        unsafe_allow_html=True,
    )

CATEGORY_TO_FLAG = {
    "Founder": "is_founder",
    "Investor": "is_investor",
    "Student / Intern": "is_student_intern",
    "Professional": "is_professional",
    "Senior Leadership / C-Suite": "is_senior_leadership",
    "Director / VP / Senior Professional": "is_director_vp",
    "Other / Blank": "is_other_blank",
}

city_options = clean_values(
    people_df.loc[people_df["_city_filter"].ne("Not Specified"), "_city_filter"]
)
designation_options = clean_values(
    people_df.loc[
        people_df["_designation_filter"].ne("Not Specified"),
        "_designation_filter",
    ]
)

# ============================================================
# HORIZONTAL FILTERS
# - Data Source filter removed
# - Designation filter removed
# - Custom Date Range appears immediately when selected
# - Actual filtering still happens only after Apply Filters
# ============================================================

st.markdown(
    '<div class="section-title">🔎 Filters</div>',
    unsafe_allow_html=True,
)
st.caption("Choose the filters you need, then click Apply Filters.")

# Event Date is intentionally OUTSIDE the form.
# Changing it may rerun the UI, but it does NOT apply filters.
date_col1, date_col2 = st.columns([1.2, 2.8])

with date_col1:
    f_date_mode = st.selectbox(
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

event_dates = (
    event_df["event_date"].dropna()
    if "event_date" in event_df.columns
    else pd.Series(dtype="object")
)
min_d = event_dates.min() if not event_dates.empty else date.today()
max_d = event_dates.max() if not event_dates.empty else date.today()

with date_col2:
    if f_date_mode == "Custom Date Range":
        f_custom_dates = st.date_input(
            "Custom Date Range",
            value=(min_d, max_d),
            min_value=min_d,
            max_value=max_d,
            key="pending_custom_dates",
        )
    else:
        f_custom_dates = None

HIDDEN_EVENT_TYPES = {
    "giveaway",
    "orientation",
    "hiring mela",
    "not specified",
    "not-specified",
    "not_specified",
}

def clean_event_type_options(df):
    values = safe_unique(df, "luma_event_type")
    return [
        value for value in values
        if str(value).strip().lower() not in HIDDEN_EVENT_TYPES
        and str(value).strip().lower() not in {"", "nan", "none", "null"}
    ]

event_type_options = clean_event_type_options(event_df)

with st.form("unified_filter_form", clear_on_submit=False):

    r1c1, r1c2, r1c3 = st.columns(3)

    with r1c1:
        f_category = st.selectbox(
            "Category",
            ["All"] + list(CATEGORY_TO_FLAG.keys()),
        )

    with r1c2:
        f_event = st.selectbox(
            "Event",
            ["All"] + safe_unique(event_df, "luma_event_name"),
        )

    with r1c3:
        f_event_type = st.selectbox(
            "Event Type",
            ["All"] + event_type_options,
        )

    r2c1, r2c2, r2c3 = st.columns(3)

    with r2c1:
        f_event_mode = st.selectbox(
            "Event Mode",
            ["All"] + safe_unique(event_df, "event_mode"),
        )

    with r2c2:
        f_city = st.selectbox(
            "City",
            ["All"] + city_options,
        )

    with r2c3:
        f_domain = st.selectbox(
            "Email Domain",
            ["All"] + safe_unique(people_df, "email_domain_group"),
        )

    f_search = st.text_input(
        "Search",
        placeholder="Name, email, company, LinkedIn...",
    )

    apply_filters = st.form_submit_button(
        "🔍 Apply Filters",
        type="primary",
        use_container_width=True,
    )

if "applied_filters" not in st.session_state:
    st.session_state.applied_filters = {
        "category": "All",
        "event": "All",
        "event_type": "All",
        "event_mode": "All",
        "city": "All",
        "domain": "All",
        "date_mode": "All Dates",
        "custom_dates": None,
        "search": "",
    }

if apply_filters:
    st.session_state.applied_filters = {
        "category": f_category,
        "event": f_event,
        "event_type": f_event_type,
        "event_mode": f_event_mode,
        "city": f_city,
        "domain": f_domain,
        "date_mode": f_date_mode,
        "custom_dates": f_custom_dates,
        "search": f_search.strip(),
    }

F = st.session_state.applied_filters
filtered_people = people_df.copy()

# People-level filters.
if F["category"] != "All":
    flag = CATEGORY_TO_FLAG[F["category"]]
    if flag in filtered_people.columns:
        filtered_people = filtered_people[
            filtered_people[flag].fillna(False).astype(bool)
        ]

if F["city"] != "All":
    filtered_people = filtered_people[
        filtered_people["_city_filter"] == F["city"]
    ]

if F["domain"] != "All":
    filtered_people = apply_exact_filter(
        filtered_people,
        "email_domain_group",
        F["domain"],
    )

# Event/date filters use person_event.
date_start = date_end = None

if F["date_mode"] == "Today":
    date_start = date_end = date.today()
elif F["date_mode"] == "Last 7 Days":
    date_end = date.today()
    date_start = date_end - timedelta(days=6)
elif F["date_mode"] == "Last 30 Days":
    date_end = date.today()
    date_start = date_end - timedelta(days=29)
elif F["date_mode"] == "This Month":
    date_end = date.today()
    date_start = date_end.replace(day=1)
elif F["date_mode"] == "Custom Date Range" and F["custom_dates"]:
    rng = F["custom_dates"]
    if isinstance(rng, (tuple, list)) and len(rng) == 2:
        date_start, date_end = rng

event_filter_active = (
    F["event"] != "All"
    or F["event_type"] != "All"
    or F["event_mode"] != "All"
    or F["date_mode"] != "All Dates"
)

if event_filter_active:
    event_matches = event_df.copy()

    if (
        date_start is not None
        and date_end is not None
        and "event_date" in event_matches.columns
    ):
        event_matches = event_matches[
            event_matches["event_date"].notna()
            & (event_matches["event_date"] >= date_start)
            & (event_matches["event_date"] <= date_end)
        ]

    if F["event"] != "All":
        event_matches = apply_exact_filter(
            event_matches,
            "luma_event_name",
            F["event"],
        )

    if F["event_type"] != "All":
        event_matches = apply_exact_filter(
            event_matches,
            "luma_event_type",
            F["event_type"],
        )

    if F["event_mode"] != "All":
        event_matches = apply_exact_filter(
            event_matches,
            "event_mode",
            F["event_mode"],
        )

    event_keys = set(
        event_matches["person_key"].dropna().astype(str)
    )

    filtered_people = filtered_people[
        filtered_people["person_key"].astype(str).isin(event_keys)
    ]

# Search applies only after Apply Filters.
if F["search"]:
    q = F["search"].lower()
    search_cols = [
        "FirstName",
        "LastName",
        "Email",
        "Phone",
        "Linkedin",
        "About",
        "Company Name",
        "Reason to join our event",
        "Are You?",
        "Data Source",
        "City Clean",
        "Designation Clean",
    ]

    mask = pd.Series(False, index=filtered_people.index)

    for col in search_cols:
        if col in filtered_people.columns:
            mask |= (
                filtered_people[col]
                .fillna("")
                .astype(str)
                .str.lower()
                .str.contains(q, regex=False, na=False)
            )

    filtered_people = filtered_people[mask]


# ============================================================
# OVERVIEW
# ============================================================

def bool_count(df, col):
    return int(df[col].fillna(False).astype(bool).sum()) if col in df.columns else 0

st.markdown('<div class="section-title">📈 Unique People Overview</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1: metric_card("Total Unique People", len(people_df))
with c2: metric_card("Founders", bool_count(people_df, "is_founder"))
with c3: metric_card("Investors", bool_count(people_df, "is_investor"))
with c4: metric_card("Students / Intern", bool_count(people_df, "is_student_intern"))

c5, c6, c7, c8 = st.columns(4)
with c5: metric_card("Professionals", bool_count(people_df, "is_professional"))
with c6: metric_card("Senior Leadership", bool_count(people_df, "is_senior_leadership"))
with c7: metric_card("Director / VP", bool_count(people_df, "is_director_vp"))
with c8: metric_card("Other / Blank", bool_count(people_df, "is_other_blank"))

st.markdown('<div class="section-title">🔎 Filtered Results</div>', unsafe_allow_html=True)
metric_card("Matching Unique Users", len(filtered_people))

active = []
for label, key in [
    ("Category", "category"),
    ("Event", "event"),
    ("Event Type", "event_type"),
    ("Event Mode", "event_mode"),
    ("City", "city"),
    ("Email Domain", "domain"),
]:
    if F[key] != "All":
        active.append(f"{label}: {F[key]}")

if F["date_mode"] != "All Dates":
    if (
        F["date_mode"] == "Custom Date Range"
        and F["custom_dates"]
        and isinstance(F["custom_dates"], (tuple, list))
        and len(F["custom_dates"]) == 2
    ):
        active.append(
            f"Event Date: {F['custom_dates'][0]} to {F['custom_dates'][1]}"
        )
    else:
        active.append(f"Event Date: {F['date_mode']}")

if F["search"]:
    active.append(f"Search: {F['search']}")

if active:
    st.info("Applied filters → " + " | ".join(active))

# ============================================================
# TABLE
# ============================================================

rows_per_page = st.selectbox("Rows per page", [25, 50, 100, 250], index=1)
total_pages = max(1, math.ceil(len(filtered_people) / rows_per_page))
page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
start = (page - 1) * rows_per_page
page_df = filtered_people.iloc[start:start + rows_per_page].copy()

# Keep CEO-requested names, but City/Designation now display cleaned main values.
page_df["City"] = page_df["City Clean"]
page_df["Designation"] = page_df["Designation Clean"]

# CEO-facing category display:
# If a specific Category filter is applied, show ONLY that selected
# category in the "Are You?" column. The underlying multi-category
# membership flags remain unchanged for correct cross-category filtering.
if F["category"] != "All" and "Are You?" in page_df.columns:
    page_df["Are You?"] = F["category"]

DISPLAY_COLUMNS = [
    "FirstName", "LastName", "Event Date", "Email", "Phone", "Linkedin",
    "About", "City", "Designation", "Company Name", "Reason to join our event",
    "Valid Email", "Luma Event Name", "Luma Event Type", "Event Mode",
    "source_spreadsheet_url", "Are You?", "event_date", "Data Source",
]
DISPLAY_COLUMNS = [c for c in DISPLAY_COLUMNS if c in page_df.columns]

st.caption(f"Page {page} of {total_pages} • Showing {len(page_df):,} unique people")
st.dataframe(page_df[DISPLAY_COLUMNS], use_container_width=True, hide_index=True)

# ============================================================
# DOWNLOAD — SELECTIVE COLUMNS WITH CHECKBOXES
# ============================================================

st.markdown(
    '<div class="section-title">📥 Download Filtered Data</div>',
    unsafe_allow_html=True,
)

export_df = filtered_people.copy()
export_df["City"] = export_df["City Clean"]
export_df["Designation"] = export_df["Designation Clean"]

if F["category"] != "All" and "Are You?" in export_df.columns:
    export_df["Are You?"] = F["category"]

DOWNLOADABLE_COLUMNS = [
    "FirstName",
    "LastName",
    "Event Date",
    "Email",
    "Phone",
    "Linkedin",
    "About",
    "City",
    "Designation",
    "Company Name",
    "Reason to join our event",
    "Valid Email",
    "Luma Event Name",
    "Luma Event Type",
    "Event Mode",
    "source_spreadsheet_url",
    "Are You?",
    "event_date",
    "Data Source",
]

DOWNLOADABLE_COLUMNS = [
    c for c in DOWNLOADABLE_COLUMNS
    if c in export_df.columns
]

st.caption("Select only the columns you want in the downloaded files.")

with st.expander("✅ Choose Download Columns", expanded=True):

    default_selected = {
        "FirstName",
        "LastName",
        "Email",
        "Phone",
    }

    selected_download_columns = []
    checkbox_cols = st.columns(4)

    for i, col in enumerate(DOWNLOADABLE_COLUMNS):
        with checkbox_cols[i % 4]:
            checked = st.checkbox(
                col,
                value=(col in default_selected),
                key=f"download_col_{re.sub(r'[^a-zA-Z0-9_]+', '_', col)}",
            )
            if checked:
                selected_download_columns.append(col)

if not selected_download_columns:
    st.warning("Select at least one column to enable downloads.")
else:
    download_df = export_df[selected_download_columns].copy()

    x1, x2 = st.columns(2)

    with x1:
        excel_data = make_excel(download_df, "Unified People")
        st.download_button(
            "⬇️ Download Excel (.xlsx)",
            data=excel_data,
            file_name="hidevs_unified_people_filtered.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with x2:
        csv_data = download_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Download CSV (.csv)",
            data=csv_data,
            file_name="hidevs_unified_people_filtered.csv",
            mime="text/csv",
            use_container_width=True,
        )


st.markdown(
    '<div class="footer">HiDevs Data Explorer • Unified Luma + Master • Unique People Only</div>',
    unsafe_allow_html=True,
)
