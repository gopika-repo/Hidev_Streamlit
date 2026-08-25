import streamlit as st
import pandas as pd
from supabase import create_client
from io import BytesIO
import math
from datetime import date, timedelta


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="HiDevs Data Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
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
        background: linear-gradient(180deg, #0f172a 0%, #172554 100%);
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
    '<div class="subtitle">Luma Registration & Master Data Dashboard &nbsp;•&nbsp; Supabase Connected</div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    """
    <h2 style="margin-bottom:5px;">HiDevs</h2>
    <p style="opacity:0.75;">Data Explorer</p>
    """,
    unsafe_allow_html=True,
)

dashboard = st.sidebar.radio(
    "Dashboard",
    ["Luma Registration Data", "Master Data"],
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
def load_table(table_name):
    all_rows = []
    page_size = 1000
    start = 0

    while True:
        response = (
            supabase
            .table(table_name)
            .select("*")
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

    return pd.DataFrame(all_rows)


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


# ============================================================
# LUMA REGISTRATION DATA
# ============================================================

if dashboard == "Luma Registration Data":

    st.markdown(
        '<div class="section-title">👥 Luma Registration Dashboard</div>',
        unsafe_allow_html=True,
    )

    # Manual refresh addresses the CEO's data-freshness concern.
    refresh_col, info_col = st.columns([1, 4])
    with refresh_col:
        if st.button("🔄 Refresh Luma Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    try:
        with st.spinner("Loading cleaned Luma data from Supabase..."):
            df = load_table("luma_registrations_clean")
    except Exception as e:
        st.error("Could not load cleaned Luma Data from Supabase.")
        st.exception(e)
        st.stop()

    if df.empty:
        st.warning('The "luma_registrations_clean" table returned no records.')
        st.stop()

    # --------------------------------------------------------
    # DATA TYPES / BASIC NORMALIZATION
    # --------------------------------------------------------
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

    if "event_date_clean" in df.columns:
        df["event_date_clean"] = pd.to_datetime(df["event_date_clean"], errors="coerce").dt.date

    if "imported_at" in df.columns:
        df["imported_at_dt"] = pd.to_datetime(df["imported_at"], errors="coerce", utc=True)
    else:
        df["imported_at_dt"] = pd.NaT

    latest_import = df["imported_at_dt"].max()
    latest_event_date = df["event_date_clean"].max() if "event_date_clean" in df.columns else None

    with info_col:
        latest_import_text = (
            latest_import.strftime("%d %b %Y, %I:%M %p UTC")
            if pd.notna(latest_import)
            else "Unavailable"
        )
        st.markdown(
            f"""
            <div class="info-card">
                <b>Clean Luma source:</b> luma_registrations_clean<br>
                <b>Records:</b> {len(df):,} &nbsp; • &nbsp;
                <b>Latest event date:</b> {latest_event_date or 'Unavailable'} &nbsp; • &nbsp;
                <b>Dataset imported:</b> {latest_import_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # SIDEBAR FILTERS
    # --------------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔎 Luma Filters")
    st.sidebar.caption("Filters use the cleaned Supabase fields.")

    # Date filter
    date_mode = st.sidebar.selectbox(
        "Event Date",
        ["All Dates", "Today", "Last 7 Days", "Last 30 Days", "This Month", "Custom Date Range"],
        key="luma_date_mode",
    )

    min_date = df["event_date_clean"].min() if "event_date_clean" in df.columns else None
    max_date = df["event_date_clean"].max() if "event_date_clean" in df.columns else None

    date_start = None
    date_end = None

    if date_mode == "Today":
        date_start = date.today()
        date_end = date.today()
    elif date_mode == "Last 7 Days":
        date_end = date.today()
        date_start = date_end - timedelta(days=6)
    elif date_mode == "Last 30 Days":
        date_end = date.today()
        date_start = date_end - timedelta(days=29)
    elif date_mode == "This Month":
        today = date.today()
        date_start = today.replace(day=1)
        date_end = today
    elif date_mode == "Custom Date Range" and min_date is not None and max_date is not None:
        selected_range = st.sidebar.date_input(
            "Choose custom range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="luma_custom_date",
        )
        if isinstance(selected_range, (tuple, list)) and len(selected_range) == 2:
            date_start, date_end = selected_range

    # Category
    selected_category = st.sidebar.selectbox(
        "User Category",
        ["All"] + safe_unique(df, "user_category_clean"),
        key="luma_user_category",
    )

    # Event
    event_options = ["All"] + safe_unique(df, "luma_event_name_clean")
    selected_event = st.sidebar.selectbox(
        "Event",
        event_options,
        key="luma_event",
    )

    # Event Type is dependent on the selected event so an invalid combination
    # cannot silently reduce the result set.
    event_type_source = df
    if selected_event != "All":
        event_type_source = event_type_source[
            event_type_source["luma_event_name_clean"].fillna("").astype(str).str.strip() == selected_event
        ]

    event_type_options = ["All"] + safe_unique(event_type_source, "luma_event_type_clean")
    selected_event_type = st.sidebar.selectbox(
        "Event Type",
        event_type_options,
        key="luma_event_type",
        help="When an Event is selected, only event types belonging to that event are shown.",
    )

    # Mode can also depend on selected event + type.
    mode_source = event_type_source
    if selected_event_type != "All":
        mode_source = mode_source[
            mode_source["luma_event_type_clean"].fillna("").astype(str).str.strip() == selected_event_type
        ]

    selected_event_mode = st.sidebar.selectbox(
        "Event Mode",
        ["All"] + safe_unique(mode_source, "event_mode_clean"),
        key="luma_event_mode",
    )

    selected_city = st.sidebar.selectbox(
        "City",
        ["All"] + safe_unique(df, "city_clean"),
        key="luma_city",
    )

    selected_designation = st.sidebar.selectbox(
        "Designation",
        ["All"] + safe_unique(df, "designation_clean_filter"),
        key="luma_designation",
    )

    selected_are_you = st.sidebar.selectbox(
        "Are You",
        ["All"] + safe_unique(df, "are_you_clean"),
        key="luma_are_you",
    )

    selected_domain_group = st.sidebar.selectbox(
        "Email Domain",
        ["All"] + safe_unique(df, "email_domain_group"),
        key="luma_email_domain_group",
        help="Gmail = @gmail.com. Other Domain = every other valid email domain.",
    )

    # Existing source flag - clearly named so it is not confused with the
    # future external email verification workflow.
    selected_valid_email = st.sidebar.selectbox(
        "Existing Valid Email Flag",
        ["All"] + safe_unique(df, "valid_email_clean"),
        key="luma_valid_email",
        help=(
            "This is the existing value present in the source Luma dataset. "
            "It is not the new external email-verification result."
        ),
    )

    selected_verification = st.sidebar.selectbox(
        "External Verification Status",
        ["All"] + safe_unique(df, "email_verification_status"),
        key="luma_external_verification",
        help="This will be updated when the externally verified CSV workflow is connected.",
    )

    search_text = st.sidebar.text_input(
        "Search",
        placeholder="Search name, email, company or LinkedIn",
        key="luma_search",
    )

    # --------------------------------------------------------
    # APPLY FILTERS ON CLEAN COLUMNS
    # --------------------------------------------------------
    filtered_df = df.copy()

    if date_start is not None and date_end is not None and "event_date_clean" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["event_date_clean"].notna()
            & (filtered_df["event_date_clean"] >= date_start)
            & (filtered_df["event_date_clean"] <= date_end)
        ]

    filtered_df = apply_exact_filter(filtered_df, "user_category_clean", selected_category)
    filtered_df = apply_exact_filter(filtered_df, "luma_event_name_clean", selected_event)
    filtered_df = apply_exact_filter(filtered_df, "luma_event_type_clean", selected_event_type)
    filtered_df = apply_exact_filter(filtered_df, "event_mode_clean", selected_event_mode)
    filtered_df = apply_exact_filter(filtered_df, "city_clean", selected_city)
    filtered_df = apply_exact_filter(filtered_df, "designation_clean_filter", selected_designation)
    filtered_df = apply_exact_filter(filtered_df, "are_you_clean", selected_are_you)
    filtered_df = apply_exact_filter(filtered_df, "email_domain_group", selected_domain_group)
    filtered_df = apply_exact_filter(filtered_df, "valid_email_clean", selected_valid_email)
    filtered_df = apply_exact_filter(filtered_df, "email_verification_status", selected_verification)

    if search_text.strip():
        search = search_text.strip().lower()
        searchable_columns = [
            "first_name",
            "last_name",
            "email",
            "email_clean",
            "company_name",
            "linkedin",
            "designation",
            "designation_clean_filter",
        ]

        mask = pd.Series(False, index=filtered_df.index)
        for col in searchable_columns:
            if col in filtered_df.columns:
                mask |= (
                    filtered_df[col]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.contains(search, regex=False, na=False)
                )
        filtered_df = filtered_df[mask]

    # --------------------------------------------------------
    # OVERVIEW
    # --------------------------------------------------------
    st.markdown('<div class="section-title">📈 Overview</div>', unsafe_allow_html=True)

    total_records = len(df)
    unique_users = unique_email_count(df)

    category_counts_series = (
        df["user_category_clean"].fillna("No Category").astype(str).str.strip().value_counts()
        if "user_category_clean" in df.columns
        else pd.Series(dtype="int64")
    )

    founder_count = int(category_counts_series.get("Founder", 0))
    investor_count = int(category_counts_series.get("Investor", 0))
    student_count = int(category_counts_series.get("Student", 0))
    professional_count = int(category_counts_series.get("Professional", 0))

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Total Registrations", total_records)
    with c2:
        metric_card("Unique Users", unique_users)
    with c3:
        metric_card("Founders", founder_count)

    c4, c5, c6 = st.columns(3)
    with c4:
        metric_card("Investors", investor_count)
    with c5:
        metric_card("Students", student_count)
    with c6:
        metric_card("Professionals", professional_count)

    # Email domain analytics requested in CEO review.
    st.markdown('<div class="section-title">📧 Email Domain Overview</div>', unsafe_allow_html=True)
    domain_counts = (
        df["email_domain_group"].fillna("Unknown").value_counts()
        if "email_domain_group" in df.columns
        else pd.Series(dtype="int64")
    )
    d1, d2, d3 = st.columns(3)
    with d1:
        metric_card("Gmail", int(domain_counts.get("Gmail", 0)))
    with d2:
        metric_card("Other Domains", int(domain_counts.get("Other Domain", 0)))
    with d3:
        metric_card("No Email", int(domain_counts.get("No Email", 0)))

    # Actual cleaned categories
    st.markdown('<div class="section-title">📊 Actual User Categories</div>', unsafe_allow_html=True)
    category_counts = (
        df["user_category_clean"]
        .fillna("No Category")
        .astype(str)
        .str.strip()
        .value_counts()
        .rename_axis("Category")
        .reset_index(name="Records")
    )
    st.dataframe(category_counts, use_container_width=True, hide_index=True)

    # Filter summary
    st.markdown('<div class="section-title">🔎 Filtered Results</div>', unsafe_allow_html=True)
    matching_records = len(filtered_df)
    matching_unique = unique_email_count(filtered_df)

    r1, r2 = st.columns(2)
    with r1:
        metric_card("Matching Records", matching_records)
    with r2:
        metric_card("Matching Unique Users", matching_unique)

    # Visible active-filter summary helps verify CEO filter behavior.
    active_filters = []
    if date_mode != "All Dates":
        active_filters.append(f"Date: {date_mode}")
    for label, value in [
        ("Category", selected_category),
        ("Event", selected_event),
        ("Event Type", selected_event_type),
        ("Event Mode", selected_event_mode),
        ("City", selected_city),
        ("Designation", selected_designation),
        ("Are You", selected_are_you),
        ("Email Domain", selected_domain_group),
        ("Existing Valid Email", selected_valid_email),
        ("External Verification", selected_verification),
    ]:
        if value != "All":
            active_filters.append(f"{label}: {value}")
    if search_text.strip():
        active_filters.append(f"Search: {search_text.strip()}")

    if active_filters:
        st.info("Active filters → " + " | ".join(active_filters))

    # Pagination
    rows_per_page = st.selectbox(
        "Rows per page",
        [25, 50, 100, 250],
        index=1,
        key="luma_rows",
    )
    total_pages = max(1, math.ceil(matching_records / rows_per_page))
    page = st.number_input(
        f"Page (1 - {total_pages})",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key="luma_page",
    )

    start = (page - 1) * rows_per_page
    end = start + rows_per_page
    page_df = filtered_df.iloc[start:end].copy()

    preferred_display_columns = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "linkedin",
        "city_clean",
        "designation_clean_filter",
        "company_name",
        "luma_event_name_clean",
        "luma_event_type_clean",
        "event_mode_clean",
        "event_date_clean",
        "user_category_clean",
        "are_you_clean",
        "email_domain",
        "email_domain_group",
        "valid_email_clean",
        "email_verification_status",
        "email_verified_at",
        "source",
        "source_sheet",
    ]
    preferred_display_columns = [c for c in preferred_display_columns if c in page_df.columns]

    st.caption(f"Page {page} of {total_pages} • Showing {len(page_df):,} rows")
    st.dataframe(
        page_df[preferred_display_columns],
        use_container_width=True,
        hide_index=True,
    )

    # Export
    st.markdown('<div class="section-title">📥 Export Luma Data</div>', unsafe_allow_html=True)
    excel_data = make_excel(filtered_df.drop(columns=["imported_at_dt"], errors="ignore"), "Luma Data")
    st.download_button(
        "⬇️ Download Filtered Excel",
        data=excel_data,
        file_name="hidevs_luma_filtered.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_luma",
    )


# ============================================================
# MASTER DATA
# ============================================================

else:

    st.markdown(
        '<div class="section-title">👥 Master Data Dashboard</div>',
        unsafe_allow_html=True,
    )

    try:
        master_df = load_table("Data")
    except Exception as e:
        st.error("Could not load Master Data from Supabase.")
        st.exception(e)
        st.stop()

    if master_df.empty:
        st.warning('The "Data" table returned no records.')
        st.stop()

    st.success(f"Successfully loaded {len(master_df):,} master records from Data.")

    for col in master_df.columns:
        if master_df[col].dtype == "object":
            master_df[col] = master_df[col].fillna("").astype(str).str.strip()

    if "master_category" in master_df.columns:
        master_df["master_category"] = (
            master_df["master_category"]
            .fillna("other/Blank")
            .astype(str)
            .str.strip()
        )
        master_df.loc[master_df["master_category"] == "", "master_category"] = "other/Blank"

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔎 Master Data Filters")

    if "master_category" in master_df.columns:
        master_category_options = ["All"] + safe_unique(master_df, "master_category")
        selected_master_category = st.sidebar.selectbox(
            "Master Category",
            master_category_options,
            key="master_category_filter",
        )
    else:
        selected_master_category = "All"

    first_name_options = ["All"] + safe_unique(master_df, "First_name")
    selected_first_name = st.sidebar.selectbox(
        "First Name",
        first_name_options,
        key="master_first_name",
    )

    city_options = ["All"] + safe_unique(master_df, "city")
    selected_master_city = st.sidebar.selectbox(
        "City",
        city_options,
        key="master_city",
    )

    designation_options = ["All"] + safe_unique(master_df, "designation")
    selected_master_designation = st.sidebar.selectbox(
        "Designation",
        designation_options,
        key="master_designation",
    )

    company_column = None
    if "company_name" in master_df.columns:
        company_column = "company_name"
    elif "organization_name" in master_df.columns:
        company_column = "organization_name"

    if company_column:
        company_options = ["All"] + safe_unique(master_df, company_column)
        selected_company = st.sidebar.selectbox(
            "Company",
            company_options,
            key="master_company",
        )
    else:
        selected_company = "All"

    source_options = ["All"] + safe_unique(master_df, "source")
    selected_source = st.sidebar.selectbox(
        "Source",
        source_options,
        key="master_source",
    )

    source_tab_options = ["All"] + safe_unique(master_df, "source_tab")
    selected_source_tab = st.sidebar.selectbox(
        "Source Tab",
        source_tab_options,
        key="master_source_tab",
    )

    designation_clean_options = ["All"] + safe_unique(master_df, "designation_clean")
    selected_designation_clean = st.sidebar.selectbox(
        "Designation Clean",
        designation_clean_options,
        key="master_designation_clean",
    )

    designation_normalized_options = ["All"] + safe_unique(master_df, "designation_normalized")
    selected_designation_normalized = st.sidebar.selectbox(
        "Designation Normalized",
        designation_normalized_options,
        key="master_designation_normalized",
    )

    leadership_role_options = ["All"] + safe_unique(master_df, "leadership_role")
    selected_leadership_role = st.sidebar.selectbox(
        "Leadership Role",
        leadership_role_options,
        key="master_leadership_role",
    )

    valid_email_options = ["All"] + safe_unique(master_df, "valid_email")
    selected_master_valid_email = st.sidebar.selectbox(
        "Valid Email",
        valid_email_options,
        key="master_valid_email",
    )

    master_search = st.sidebar.text_input(
        "Search Master Data",
        placeholder="Search name, email, company or LinkedIn",
        key="master_search",
    )

    filtered_master = master_df.copy()

    if selected_master_category != "All" and "master_category" in filtered_master.columns:
        filtered_master = filtered_master[filtered_master["master_category"] == selected_master_category]

    if selected_first_name != "All":
        filtered_master = filtered_master[filtered_master["First_name"] == selected_first_name]

    if selected_master_city != "All":
        filtered_master = filtered_master[filtered_master["city"] == selected_master_city]

    if selected_master_designation != "All":
        filtered_master = filtered_master[filtered_master["designation"] == selected_master_designation]

    if selected_company != "All" and company_column:
        filtered_master = filtered_master[filtered_master[company_column] == selected_company]

    if selected_source != "All":
        filtered_master = filtered_master[filtered_master["source"] == selected_source]

    if selected_source_tab != "All":
        filtered_master = filtered_master[filtered_master["source_tab"] == selected_source_tab]

    if selected_designation_clean != "All":
        filtered_master = filtered_master[filtered_master["designation_clean"] == selected_designation_clean]

    if selected_designation_normalized != "All":
        filtered_master = filtered_master[filtered_master["designation_normalized"] == selected_designation_normalized]

    if selected_leadership_role != "All":
        filtered_master = filtered_master[filtered_master["leadership_role"] == selected_leadership_role]

    if selected_master_valid_email != "All":
        filtered_master = filtered_master[filtered_master["valid_email"] == selected_master_valid_email]

    if master_search.strip():
        search = master_search.strip().lower()
        search_columns = [
            "First_name",
            "last_name",
            "email",
            "linkedin",
            "company_name",
            "organization_name",
            "designation",
            "name_field",
        ]
        mask = pd.Series(False, index=filtered_master.index)
        for col in search_columns:
            if col in filtered_master.columns:
                mask |= (
                    filtered_master[col]
                    .astype(str)
                    .str.lower()
                    .str.contains(search, regex=False, na=False)
                )
        filtered_master = filtered_master[mask]

    st.markdown('<div class="section-title">📈 Master Data Overview</div>', unsafe_allow_html=True)

    total_master = len(master_df)
    if "email" in master_df.columns:
        unique_master = (
            master_df["email"]
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )
    else:
        unique_master = total_master

    category_counts = pd.DataFrame(columns=["master_category", "record_count"])
    if "master_category" in master_df.columns:
        category_counts = (
            master_df
            .groupby("master_category", dropna=False)
            .size()
            .reset_index(name="record_count")
            .sort_values("record_count", ascending=False)
        )

    category_lookup = dict(zip(category_counts["master_category"], category_counts["record_count"]))

    founder_count = category_lookup.get("Founder", 0)
    senior_count = category_lookup.get("Senior Leaderships/C-Suite", 0)
    director_count = category_lookup.get("Director/VP/senior Proffessionals", 0)
    professional_count = category_lookup.get("Professionals", 0)
    student_count = category_lookup.get("Students/Intern", 0)
    investor_count = category_lookup.get("Investors", 0)

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Total Master Records", total_master)
    with c2:
        metric_card("Unique Users", unique_master)
    with c3:
        metric_card("Founder", founder_count)

    c4, c5, c6 = st.columns(3)
    with c4:
        metric_card("Senior Leadership / C-Suite", senior_count)
    with c5:
        metric_card("Director / VP / Senior Professional", director_count)
    with c6:
        metric_card("Professionals", professional_count)

    c7, c8 = st.columns(2)
    with c7:
        metric_card("Students / Intern", student_count)
    with c8:
        metric_card("Investors", investor_count)

    st.markdown('<div class="section-title">📊 Master Data Categories</div>', unsafe_allow_html=True)
    if not category_counts.empty:
        st.dataframe(category_counts, use_container_width=True, hide_index=True)
    else:
        st.info("master_category column is not available.")

    st.markdown('<div class="section-title">🔎 Filtered Master Data</div>', unsafe_allow_html=True)

    matching_master = len(filtered_master)
    if "email" in filtered_master.columns:
        matching_unique_master = (
            filtered_master["email"]
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )
    else:
        matching_unique_master = matching_master

    c1, c2 = st.columns(2)
    with c1:
        metric_card("Matching Records", matching_master)
    with c2:
        metric_card("Matching Unique Users", matching_unique_master)

    rows_per_page = st.selectbox(
        "Rows per page",
        [25, 50, 100, 250],
        index=1,
        key="master_rows",
    )
    total_pages = max(1, math.ceil(matching_master / rows_per_page))
    page = st.number_input(
        f"Page (1 - {total_pages})",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key="master_page",
    )

    start = (page - 1) * rows_per_page
    end = start + rows_per_page
    master_page_df = filtered_master.iloc[start:end]

    st.caption(f"Page {page} of {total_pages} • Showing {len(master_page_df):,} rows")
    st.dataframe(master_page_df, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">📥 Export Master Data</div>', unsafe_allow_html=True)
    master_excel = make_excel(filtered_master, "Master Data")
    st.download_button(
        "⬇️ Download Filtered Master Excel",
        data=master_excel,
        file_name="hidevs_master_filtered.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_master",
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        HiDevs Data Explorer • Supabase-powered analytics dashboard
    </div>
    """,
    unsafe_allow_html=True,
)