import streamlit as st
import pandas as pd
from supabase import create_client
from io import BytesIO
import math


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="HiDevs Data Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    /* ========================================================
       GLOBAL
       ======================================================== */

    .stApp {
        background:
            radial-gradient(
                circle at 10% 10%,
                rgba(99, 102, 241, 0.10),
                transparent 30%
            ),
            radial-gradient(
                circle at 90% 20%,
                rgba(14, 165, 233, 0.10),
                transparent 30%
            ),
            #f8fafc;
    }


    /* ========================================================
       HEADER
       ======================================================== */

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


    /* ========================================================
       SECTION TITLE
       ======================================================== */

    .section-title {
        font-size: 24px;
        font-weight: 750;
        color: #111827;
        margin-top: 25px;
        margin-bottom: 15px;
    }


    /* ========================================================
       KPI CARDS
       ======================================================== */

    .metric-card {
        background: rgba(255,255,255,0.90);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 5px 18px rgba(15,23,42,0.06);
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


    /* ========================================================
       CATEGORY
       ======================================================== */

    .category-card {
        background: white;
        border-radius: 14px;
        padding: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 12px rgba(15,23,42,0.05);
    }


    /* ========================================================
       SIDEBAR
       ======================================================== */

    section[data-testid="stSidebar"] {
        background: linear-gradient(
            180deg,
            #0f172a 0%,
            #172554 100%
        );
    }

    section[data-testid="stSidebar"] label {
        color: #ffffff !important;
    }


    /* ========================================================
       IMPORTANT:
       LUMA SELECTBOX SELECTED VALUE VISIBILITY
       ======================================================== */

    /* Main selectbox container */
    section[data-testid="stSidebar"]
    div[data-baseweb="select"] {
        color: #111827 !important;
    }


    /* The visible selectbox */
    section[data-testid="stSidebar"]
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #111827 !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }


    /* ALL children inside the visible selectbox */
    section[data-testid="stSidebar"]
    div[data-baseweb="select"] > div * {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }


    /* Selected value specifically */
    section[data-testid="stSidebar"]
    div[data-baseweb="select"]
    div[role="combobox"] {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }


    /* Selected text / span */
    section[data-testid="stSidebar"]
    div[data-baseweb="select"]
    span {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        opacity: 1 !important;
    }


    /* Input element used internally by selectbox */
    section[data-testid="stSidebar"]
    div[data-baseweb="select"]
    input {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        background-color: transparent !important;
        opacity: 1 !important;
    }


    /* Input placeholder */
    section[data-testid="stSidebar"]
    div[data-baseweb="select"]
    input::placeholder {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        opacity: 1 !important;
    }


    /* Dropdown popup */
    div[data-baseweb="popover"] {
        background-color: #ffffff !important;
        color: #111827 !important;
    }


    /* Everything inside dropdown */
    div[data-baseweb="popover"] * {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }


    /* Dropdown options */
    div[data-baseweb="popover"]
    div[role="option"] {
        background-color: #ffffff !important;
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }


    /* Dropdown hover */
    div[data-baseweb="popover"]
    div[role="option"]:hover {
        background-color: #eef2ff !important;
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }


    /* ========================================================
       SIDEBAR SEARCH INPUT
       ======================================================== */

    section[data-testid="stSidebar"]
    input[type="text"] {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        background-color: #ffffff !important;
        caret-color: #111827 !important;
        opacity: 1 !important;
    }


    section[data-testid="stSidebar"]
    input[type="text"]:focus {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        background-color: #ffffff !important;
        caret-color: #111827 !important;
    }


    section[data-testid="stSidebar"]
    input[type="text"]::placeholder {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        opacity: 1 !important;
    }


    /* ========================================================
       BUTTON
       ======================================================== */

    .stDownloadButton button {
        border-radius: 10px;
        font-weight: 700;
    }


    /* ========================================================
       FOOTER
       ======================================================== */

    .footer {
        text-align: center;
        color: #94a3b8;
        font-size: 13px;
        margin-top: 40px;
        padding: 20px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SUPABASE CONNECTION
# ============================================================

try:

    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

except Exception as e:

    st.error("❌ Could not create Supabase connection.")
    st.exception(e)
    st.stop()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">📊 HiDevs Data Explorer</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Luma Registration & Master Data Dashboard'
    ' &nbsp;•&nbsp; Supabase Connected'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.markdown(
    """
    <h2 style="margin-bottom:5px;">HiDevs</h2>
    <p style="opacity:0.75;">Data Explorer</p>
    """,
    unsafe_allow_html=True
)

dashboard = st.sidebar.radio(
    "Dashboard",
    [
        "Luma Registration Data",
        "Master Data"
    ]
)


# ============================================================
# HELPERS
# ============================================================

def clean_values(series):

    values = (
        series
        .dropna()
        .astype(str)
        .str.strip()
    )

    values = values[
        values != ""
    ]

    return sorted(
        values.unique().tolist(),
        key=lambda x: x.lower()
    )


def safe_unique(df, column):

    if column not in df.columns:
        return []

    return clean_values(df[column])


def metric_card(label, value):

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value:,}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def make_excel(df, sheet_name="Data"):

    buffer = BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name=sheet_name[:31]
        )

    return buffer.getvalue()


# ============================================================
# LOAD SUPABASE TABLE
# ============================================================

@st.cache_data(ttl=300)
def load_table(table_name):

    all_rows = []

    page_size = 1000
    start = 0

    while True:

        response = (
            supabase
            .table(table_name)
            .select("*")
            .range(
                start,
                start + page_size - 1
            )
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


# ============================================================
# ============================================================
# LUMA REGISTRATION DATA
# ============================================================
# ============================================================

if dashboard == "Luma Registration Data":

    st.markdown(
        '<div class="section-title">👥 Luma Registration Dashboard</div>',
        unsafe_allow_html=True
    )

    try:

        df = load_table("Data Project")

    except Exception as e:

        st.error("Could not load Luma Data from Supabase.")
        st.exception(e)
        st.stop()


    if df.empty:

        st.warning(
            'The "Data Project" table returned no records.'
        )
        st.stop()


    st.success(
        f"Successfully loaded {len(df):,} records from Data Project."
    )


    # ========================================================
    # CLEAN COLUMNS
    # ========================================================

    for col in df.columns:

        if df[col].dtype == "object":

            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
                .str.strip()
            )


    # ========================================================
    # LUMA FILTERS
    # ========================================================

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔎 Luma Filters")


    # USER CATEGORY

    category_options = [
        "All"
    ] + safe_unique(
        df,
        "user_category"
    )

    selected_category = st.sidebar.selectbox(
        "User Category",
        category_options,
        key="luma_user_category"
    )


    # EVENT

    event_options = [
        "All"
    ] + safe_unique(
        df,
        "luma_event_name"
    )

    selected_event = st.sidebar.selectbox(
        "Event",
        event_options,
        key="luma_event"
    )


    # EVENT TYPE

    event_type_options = [
        "All"
    ] + safe_unique(
        df,
        "luma_event_type"
    )

    selected_event_type = st.sidebar.selectbox(
        "Event Type",
        event_type_options,
        key="luma_event_type"
    )


    # EVENT MODE

    event_mode_options = [
        "All"
    ] + safe_unique(
        df,
        "event_mode"
    )

    selected_event_mode = st.sidebar.selectbox(
        "Event Mode",
        event_mode_options,
        key="luma_event_mode"
    )


    # CITY

    city_options = [
        "All"
    ] + safe_unique(
        df,
        "city"
    )

    selected_city = st.sidebar.selectbox(
        "City",
        city_options,
        key="luma_city"
    )


    # DESIGNATION

    designation_options = [
        "All"
    ] + safe_unique(
        df,
        "designation"
    )

    selected_designation = st.sidebar.selectbox(
        "Designation",
        designation_options,
        key="luma_designation"
    )


    # ARE YOU

    are_you_options = [
        "All"
    ] + safe_unique(
        df,
        "are_you"
    )

    selected_are_you = st.sidebar.selectbox(
        "Are You",
        are_you_options,
        key="luma_are_you"
    )


    # VALID EMAIL

    valid_email_options = [
        "All"
    ] + safe_unique(
        df,
        "valid_email"
    )

    selected_valid_email = st.sidebar.selectbox(
        "Valid Email",
        valid_email_options,
        key="luma_valid_email"
    )


    # ========================================================
    # SEARCH
    # ========================================================

    search_text = st.sidebar.text_input(
        "Search",
        placeholder="Search name, email, company or LinkedIn",
        key="luma_search"
    )


    # ========================================================
    # APPLY FILTERS
    # ========================================================

    filtered_df = df.copy()


    if selected_category != "All":

        filtered_df = filtered_df[
            filtered_df["user_category"]
            .astype(str)
            .str.strip()
            == selected_category
        ]


    if selected_event != "All":

        filtered_df = filtered_df[
            filtered_df["luma_event_name"]
            .astype(str)
            .str.strip()
            == selected_event
        ]


    if selected_event_type != "All":

        filtered_df = filtered_df[
            filtered_df["luma_event_type"]
            .astype(str)
            .str.strip()
            == selected_event_type
        ]


    if selected_event_mode != "All":

        filtered_df = filtered_df[
            filtered_df["event_mode"]
            .astype(str)
            .str.strip()
            == selected_event_mode
        ]


    if selected_city != "All":

        filtered_df = filtered_df[
            filtered_df["city"]
            .astype(str)
            .str.strip()
            == selected_city
        ]


    if selected_designation != "All":

        filtered_df = filtered_df[
            filtered_df["designation"]
            .astype(str)
            .str.strip()
            == selected_designation
        ]


    if selected_are_you != "All":

        filtered_df = filtered_df[
            filtered_df["are_you"]
            .astype(str)
            .str.strip()
            == selected_are_you
        ]


    if selected_valid_email != "All":

        filtered_df = filtered_df[
            filtered_df["valid_email"]
            .astype(str)
            .str.strip()
            == selected_valid_email
        ]


    # ========================================================
    # SEARCH FILTER
    # ========================================================

    if search_text.strip():

        search = search_text.strip().lower()

        searchable_columns = [
            "first_name",
            "last_name",
            "email",
            "organization_name",
            "linkedin"
        ]

        mask = pd.Series(
            False,
            index=filtered_df.index
        )

        for col in searchable_columns:

            if col in filtered_df.columns:

                mask |= (
                    filtered_df[col]
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        search,
                        regex=False,
                        na=False
                    )
                )

        filtered_df = filtered_df[mask]


    # ========================================================
    # OVERVIEW
    # ========================================================

    st.markdown(
        '<div class="section-title">📈 Overview</div>',
        unsafe_allow_html=True
    )


    total_records = len(df)


    if "email" in df.columns:

        unique_users = (
            df["email"]
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )

    else:

        unique_users = len(df)


    founder_count = len(
        df[
            df["user_category"]
            .str.lower()
            .str.contains(
                "founder",
                na=False
            )
        ]
    )


    investor_count = len(
        df[
            df["user_category"]
            .str.lower()
            .str.contains(
                "investor",
                na=False
            )
        ]
    )


    student_count = len(
        df[
            df["user_category"]
            .str.lower()
            .str.contains(
                "student",
                na=False
            )
        ]
    )


    professional_count = len(
        df[
            df["user_category"]
            .str.lower()
            .str.contains(
                "professional",
                na=False
            )
        ]
    )


    c1, c2, c3 = st.columns(3)

    with c1:
        metric_card(
            "Total Registrations",
            total_records
        )

    with c2:
        metric_card(
            "Unique Users",
            unique_users
        )

    with c3:
        metric_card(
            "Founders",
            founder_count
        )


    c4, c5, c6 = st.columns(3)

    with c4:
        metric_card(
            "Investors",
            investor_count
        )

    with c5:
        metric_card(
            "Students",
            student_count
        )

    with c6:
        metric_card(
            "Professionals",
            professional_count
        )


    # ========================================================
    # ACTUAL USER CATEGORIES
    # ========================================================

    st.markdown(
        '<div class="section-title">📊 Actual User Categories</div>',
        unsafe_allow_html=True
    )


    category_counts = (
        df["user_category"]
        .replace("", "Blank / Uncategorized")
        .fillna("Blank / Uncategorized")
        .astype(str)
        .str.strip()
        .value_counts()
        .reset_index()
    )


    category_counts.columns = [
        "Category",
        "Records"
    ]


    st.dataframe(
        category_counts,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # FILTERED RESULTS
    # ========================================================

    st.markdown(
        '<div class="section-title">🔎 Filtered Results</div>',
        unsafe_allow_html=True
    )


    matching_records = len(filtered_df)


    if "email" in filtered_df.columns:

        matching_unique = (
            filtered_df["email"]
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )

    else:

        matching_unique = matching_records


    c1, c2 = st.columns(2)

    with c1:
        metric_card(
            "Matching Records",
            matching_records
        )

    with c2:
        metric_card(
            "Matching Unique Users",
            matching_unique
        )


    # ========================================================
    # PAGINATION
    # ========================================================

    rows_per_page = st.selectbox(
        "Rows per page",
        [
            25,
            50,
            100,
            250
        ],
        index=1,
        key="luma_rows"
    )


    total_pages = max(
        1,
        math.ceil(
            matching_records /
            rows_per_page
        )
    )


    page = st.number_input(
        f"Page (1 - {total_pages})",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key="luma_page"
    )


    start = (
        page - 1
    ) * rows_per_page


    end = (
        start +
        rows_per_page
    )


    page_df = filtered_df.iloc[
        start:end
    ]


    st.caption(
        f"Page {page} of {total_pages} • "
        f"Showing {len(page_df):,} rows"
    )


    st.dataframe(
        page_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # EXPORT LUMA
    # ========================================================

    st.markdown(
        '<div class="section-title">📥 Export Luma Data</div>',
        unsafe_allow_html=True
    )


    excel_data = make_excel(
        filtered_df,
        "Luma Data"
    )


    st.download_button(
        "⬇️ Download Filtered Excel",
        data=excel_data,
        file_name="hidevs_luma_filtered.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        key="download_luma"
    )


# ============================================================
# ============================================================
# MASTER DATA
# ============================================================
# ============================================================

else:

    st.markdown(
        '<div class="section-title">👥 Master Data Dashboard</div>',
        unsafe_allow_html=True
    )


    try:

        master_df = load_table("Data")

    except Exception as e:

        st.error(
            "Could not load Master Data from Supabase."
        )

        st.exception(e)
        st.stop()


    if master_df.empty:

        st.warning(
            'The "Data" table returned no records.'
        )

        st.stop()


    st.success(
        f"Successfully loaded "
        f"{len(master_df):,} master records from Data."
    )


    # ========================================================
    # CLEAN MASTER DATA
    # ========================================================

    for col in master_df.columns:

        if master_df[col].dtype == "object":

            master_df[col] = (
                master_df[col]
                .fillna("")
                .astype(str)
                .str.strip()
            )


    # ========================================================
    # MASTER CATEGORY
    # ========================================================

    if "master_category" in master_df.columns:

        master_df["master_category"] = (
            master_df["master_category"]
            .fillna("other/Blank")
            .astype(str)
            .str.strip()
        )

        master_df.loc[
            master_df["master_category"] == "",
            "master_category"
        ] = "other/Blank"


    # ========================================================
    # MASTER FILTERS
    # ========================================================

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔎 Master Data Filters")


    if "master_category" in master_df.columns:

        master_category_options = [
            "All"
        ] + safe_unique(
            master_df,
            "master_category"
        )

        selected_master_category = st.sidebar.selectbox(
            "Master Category",
            master_category_options,
            key="master_category_filter"
        )

    else:

        selected_master_category = "All"


    first_name_options = [
        "All"
    ] + safe_unique(
        master_df,
        "First_name"
    )

    selected_first_name = st.sidebar.selectbox(
        "First Name",
        first_name_options,
        key="master_first_name"
    )


    city_options = [
        "All"
    ] + safe_unique(
        master_df,
        "city"
    )

    selected_master_city = st.sidebar.selectbox(
        "City",
        city_options,
        key="master_city"
    )


    designation_options = [
        "All"
    ] + safe_unique(
        master_df,
        "designation"
    )

    selected_master_designation = st.sidebar.selectbox(
        "Designation",
        designation_options,
        key="master_designation"
    )


    company_column = None

    if "company_name" in master_df.columns:

        company_column = "company_name"

    elif "organization_name" in master_df.columns:

        company_column = "organization_name"


    if company_column:

        company_options = [
            "All"
        ] + safe_unique(
            master_df,
            company_column
        )

        selected_company = st.sidebar.selectbox(
            "Company",
            company_options,
            key="master_company"
        )

    else:

        selected_company = "All"


    source_options = [
        "All"
    ] + safe_unique(
        master_df,
        "source"
    )

    selected_source = st.sidebar.selectbox(
        "Source",
        source_options,
        key="master_source"
    )


    source_tab_options = [
        "All"
    ] + safe_unique(
        master_df,
        "source_tab"
    )

    selected_source_tab = st.sidebar.selectbox(
        "Source Tab",
        source_tab_options,
        key="master_source_tab"
    )


    designation_clean_options = [
        "All"
    ] + safe_unique(
        master_df,
        "designation_clean"
    )

    selected_designation_clean = st.sidebar.selectbox(
        "Designation Clean",
        designation_clean_options,
        key="master_designation_clean"
    )


    designation_normalized_options = [
        "All"
    ] + safe_unique(
        master_df,
        "designation_normalized"
    )

    selected_designation_normalized = st.sidebar.selectbox(
        "Designation Normalized",
        designation_normalized_options,
        key="master_designation_normalized"
    )


    leadership_role_options = [
        "All"
    ] + safe_unique(
        master_df,
        "leadership_role"
    )

    selected_leadership_role = st.sidebar.selectbox(
        "Leadership Role",
        leadership_role_options,
        key="master_leadership_role"
    )


    valid_email_options = [
        "All"
    ] + safe_unique(
        master_df,
        "valid_email"
    )

    selected_master_valid_email = st.sidebar.selectbox(
        "Valid Email",
        valid_email_options,
        key="master_valid_email"
    )


    master_search = st.sidebar.text_input(
        "Search Master Data",
        placeholder="Search name, email, company or LinkedIn",
        key="master_search"
    )


    # ========================================================
    # APPLY MASTER FILTERS
    # ========================================================

    filtered_master = master_df.copy()


    if (
        selected_master_category != "All"
        and "master_category" in filtered_master.columns
    ):

        filtered_master = filtered_master[
            filtered_master["master_category"]
            == selected_master_category
        ]


    if selected_first_name != "All":

        filtered_master = filtered_master[
            filtered_master["First_name"]
            == selected_first_name
        ]


    if selected_master_city != "All":

        filtered_master = filtered_master[
            filtered_master["city"]
            == selected_master_city
        ]


    if selected_master_designation != "All":

        filtered_master = filtered_master[
            filtered_master["designation"]
            == selected_master_designation
        ]


    if (
        selected_company != "All"
        and company_column
    ):

        filtered_master = filtered_master[
            filtered_master[company_column]
            == selected_company
        ]


    if selected_source != "All":

        filtered_master = filtered_master[
            filtered_master["source"]
            == selected_source
        ]


    if selected_source_tab != "All":

        filtered_master = filtered_master[
            filtered_master["source_tab"]
            == selected_source_tab
        ]


    if selected_designation_clean != "All":

        filtered_master = filtered_master[
            filtered_master["designation_clean"]
            == selected_designation_clean
        ]


    if selected_designation_normalized != "All":

        filtered_master = filtered_master[
            filtered_master["designation_normalized"]
            == selected_designation_normalized
        ]


    if selected_leadership_role != "All":

        filtered_master = filtered_master[
            filtered_master["leadership_role"]
            == selected_leadership_role
        ]


    if selected_master_valid_email != "All":

        filtered_master = filtered_master[
            filtered_master["valid_email"]
            == selected_master_valid_email
        ]


    if master_search.strip():

        search = (
            master_search
            .strip()
            .lower()
        )

        search_columns = [
            "First_name",
            "last_name",
            "email",
            "linkedin",
            "company_name",
            "organization_name",
            "designation",
            "name_field"
        ]

        mask = pd.Series(
            False,
            index=filtered_master.index
        )

        for col in search_columns:

            if col in filtered_master.columns:

                mask |= (
                    filtered_master[col]
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        search,
                        regex=False,
                        na=False
                    )
                )

        filtered_master = filtered_master[mask]


    # ========================================================
    # MASTER OVERVIEW
    # ========================================================

    st.markdown(
        '<div class="section-title">📈 Master Data Overview</div>',
        unsafe_allow_html=True
    )


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


    category_counts = pd.DataFrame(
        columns=[
            "master_category",
            "record_count"
        ]
    )


    if "master_category" in master_df.columns:

        category_counts = (
            master_df
            .groupby(
                "master_category",
                dropna=False
            )
            .size()
            .reset_index(
                name="record_count"
            )
            .sort_values(
                "record_count",
                ascending=False
            )
        )


    category_lookup = dict(
        zip(
            category_counts[
                "master_category"
            ],
            category_counts[
                "record_count"
            ]
        )
    )


    founder_count = category_lookup.get(
        "Founder",
        0
    )


    senior_count = category_lookup.get(
        "Senior Leaderships/C-Suite",
        0
    )


    director_count = category_lookup.get(
        "Director/VP/senior Proffessionals",
        0
    )


    professional_count = category_lookup.get(
        "Professionals",
        0
    )


    student_count = category_lookup.get(
        "Students/Intern",
        0
    )


    investor_count = category_lookup.get(
        "Investors",
        0
    )


    c1, c2, c3 = st.columns(3)

    with c1:
        metric_card(
            "Total Master Records",
            total_master
        )

    with c2:
        metric_card(
            "Unique Users",
            unique_master
        )

    with c3:
        metric_card(
            "Founder",
            founder_count
        )


    c4, c5, c6 = st.columns(3)

    with c4:
        metric_card(
            "Senior Leadership / C-Suite",
            senior_count
        )

    with c5:
        metric_card(
            "Director / VP / Senior Professional",
            director_count
        )

    with c6:
        metric_card(
            "Professionals",
            professional_count
        )


    c7, c8 = st.columns(2)

    with c7:
        metric_card(
            "Students / Intern",
            student_count
        )

    with c8:
        metric_card(
            "Investors",
            investor_count
        )


    # ========================================================
    # MASTER CATEGORIES
    # ========================================================

    st.markdown(
        '<div class="section-title">📊 Master Data Categories</div>',
        unsafe_allow_html=True
    )


    if not category_counts.empty:

        st.dataframe(
            category_counts,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "master_category column is not available."
        )


    # ========================================================
    # FILTERED MASTER DATA
    # ========================================================

    st.markdown(
        '<div class="section-title">🔎 Filtered Master Data</div>',
        unsafe_allow_html=True
    )


    matching_master = len(
        filtered_master
    )


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

        metric_card(
            "Matching Records",
            matching_master
        )

    with c2:

        metric_card(
            "Matching Unique Users",
            matching_unique_master
        )


    # ========================================================
    # PAGINATION
    # ========================================================

    rows_per_page = st.selectbox(
        "Rows per page",
        [
            25,
            50,
            100,
            250
        ],
        index=1,
        key="master_rows"
    )


    total_pages = max(
        1,
        math.ceil(
            matching_master /
            rows_per_page
        )
    )


    page = st.number_input(
        f"Page (1 - {total_pages})",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key="master_page"
    )


    start = (
        page - 1
    ) * rows_per_page


    end = (
        start +
        rows_per_page
    )


    master_page_df = filtered_master.iloc[
        start:end
    ]


    st.caption(
        f"Page {page} of {total_pages} • "
        f"Showing {len(master_page_df):,} rows"
    )


    st.dataframe(
        master_page_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # EXPORT MASTER DATA
    # ========================================================

    st.markdown(
        '<div class="section-title">📥 Export Master Data</div>',
        unsafe_allow_html=True
    )


    master_excel = make_excel(
        filtered_master,
        "Master Data"
    )


    st.download_button(
        "⬇️ Download Filtered Master Excel",
        data=master_excel,
        file_name="hidevs_master_filtered.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        key="download_master"
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
    unsafe_allow_html=True
)