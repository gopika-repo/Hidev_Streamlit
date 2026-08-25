import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="Luma Connection Test",
    layout="wide"
)

st.title("Luma Clean Data — Connection Test")

try:
    supabase = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

    st.success("Supabase client connected.")

    response = (
        supabase
        .table("luma_registrations_clean")
        .select(
            "id,"
            "first_name,"
            "last_name,"
            "email,"
            "luma_event_name_clean,"
            "luma_event_type_clean,"
            "event_date_clean,"
            "city_clean,"
            "designation_clean_filter,"
            "are_you_clean,"
            "user_category_clean,"
            "email_domain_group"
        )
        .limit(10)
        .execute()
    )

    records = response.data

    st.success(
        f"Successfully read {len(records)} records "
        "from luma_registrations_clean."
    )

    st.dataframe(
        records,
        use_container_width=True
    )

except Exception as e:

    st.error(
        "Could not read luma_registrations_clean."
    )

    st.exception(e)