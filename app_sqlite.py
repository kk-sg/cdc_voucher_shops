#!/usr/bin/env python3
"""
CDC Voucher Merchant Search UI (SQLite Version)
A Streamlit app for searching and filtering CDC voucher merchants.
Loads data from SQLite database instead of CSV.
"""

import pandas as pd
import streamlit as st
import sqlite3

# Page configuration
st.set_page_config(
    page_title="CDC Voucher Search",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better mobile experience
st.markdown("""
<style>
    /* Mobile-friendly cards */
    @media (max-width: 768px) {
        .stColumns {
            gap: 1rem !important;
        }
    }

    /* Search bar styling */
    div[data-testid="stTextInput"] {
        padding: 1rem 0;
    }

    /* Card hover effect */
    .merchant-card {
        transition: transform 0.2s;
        cursor: pointer;
    }
    .merchant-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* Rating stars */
    .rating-stars {
        color: #FFD700;
    }

    /* Category badges */
    .category-badge {
        background: #2563eb;
        color: #ffffff;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 500;
        display: inline-block;
        margin: 0.125rem;
    }
</style>
""", unsafe_allow_html=True)

# Cache data loading
@st.cache_data
def load_data():
    """Load merchant data from SQLite database on Google Drive."""
    import tempfile
    import requests

    try:
        # Google Drive file ID from secrets
        file_id = st.secrets["gdrive"]["file_id"]
        db_url = f"https://drive.google.com/uc?id={file_id}"

        # Download database file with progress
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("📥 Downloading database from Google Drive (0%)...")
        response = requests.get(db_url, timeout=60, stream=True)
        response.raise_for_status()

        # Download in chunks
        total_size = int(response.headers.get('content-length', 0))
        chunk_size = 8192
        downloaded = 0

        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    tmp_file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = min(downloaded / total_size, 1.0)
                        progress_bar.progress(progress)
                        status_text.text(f"📥 Downloading database... ({int(progress*100)}%)")

            tmp_path = tmp_file.name

        progress_bar.progress(1.0)
        status_text.text("⚙️ Processing database...")

        # Connect and query
        conn = sqlite3.connect(tmp_path)
        query = "SELECT * FROM merchants"
        df = pd.read_sql_query(query, conn)
        conn.close()

        # Clean up temp file
        import os
        os.unlink(tmp_path)

        status_text.text("🔧 Converting data types...")

        # Convert data types
        df['google_rating'] = pd.to_numeric(df['google_rating'], errors='coerce')
        df['review_count'] = pd.to_numeric(df['review_count'], errors='coerce')
        df['price_level'] = pd.to_numeric(df['price_level'], errors='coerce')

        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()

        return df

    except Exception as e:
        st.error(f"Error loading database: {e}")
        st.stop()

# Initialize session state for filters
if 'filters' not in st.session_state:
    st.session_state.filters = {
        'search_query': '',
        'category': 'All',
        'min_rating': 0.0,
        'max_price': 4,
        'postal_code': ''
    }


# Load data
df = load_data()

# ==================== HEADER ====================
st.title("🛒 CDC Voucher Merchant Search")
st.markdown("**Find eligible merchants near you** - Search across hundreds of CDC voucher-friendly businesses")

# ==================== FILTERS IN SIDEBAR ====================
st.sidebar.header("🔍 Search & Filters")

# Text search
search_query = st.sidebar.text_input(
    "Search merchants",
    placeholder="Name, keywords, or address...",
    value=st.session_state.filters['search_query']
)

# Category filter
st.sidebar.subheader("📂 Category")
# Filter out None values before sorting
valid_categories = [cat for cat in df['primary_type'].unique() if pd.notna(cat)]
categories = ['All'] + sorted(valid_categories)
category = st.sidebar.selectbox(
    "Business Type",
    categories,
    index=0
)

# Location filters
st.sidebar.subheader("📍 Location")
postal_code = st.sidebar.text_input(
    "Postal Code",
    placeholder="e.g., 150079",
    value=st.session_state.filters['postal_code']
)

# Rating filter
st.sidebar.subheader("⭐ Rating")
min_rating = st.sidebar.slider(
    "Minimum Rating",
    min_value=0.0,
    max_value=5.0,
    value=st.session_state.filters['min_rating'],
    step=0.5
)

# Price level filter
st.sidebar.subheader("💰 Price Level")
max_price = st.sidebar.selectbox(
    "Maximum Price",
    options=["Any", "$ (Inexpensive)", "$$ (Moderate)", "$$$ (Expensive)", "$$$$ (Very Expensive)"],
    index=0
)

price_map = {"Any": 4, "$ (Inexpensive)": 1, "$$ (Moderate)": 2, "$$$ (Expensive)": 3, "$$$$ (Very Expensive)": 0}
max_price_level = price_map[max_price]

# Apply filters button
apply_filters = st.sidebar.button("🔍 Apply Filters", use_container_width=True)

# Update session state
if apply_filters:
    st.session_state.filters['search_query'] = search_query
    st.session_state.filters['category'] = category
    st.session_state.filters['postal_code'] = postal_code
    st.session_state.filters['min_rating'] = min_rating
    st.session_state.filters['max_price'] = max_price_level
    st.rerun()

# ==================== MAIN CONTENT AREA ====================

# Filter data
filtered_df = df.copy()

# Apply search filter
if search_query:
    search_lower = search_query.lower()
    filtered_df = filtered_df[
        filtered_df['name'].str.lower().str.contains(search_lower, na=False) |
        filtered_df['address'].str.lower().str.contains(search_lower, na=False) |
        filtered_df['all_types'].str.lower().str.contains(search_lower, na=False)
    ]

# Apply category filter
if category != 'All':
    filtered_df = filtered_df[filtered_df['primary_type'] == category]

# Apply rating filter
filtered_df = filtered_df[filtered_df['google_rating'] >= min_rating]

# Apply price filter
if max_price_level < 4:
    filtered_df = filtered_df[filtered_df['price_level'] <= max_price_level]

# Apply postal code filter
if postal_code:
    filtered_df = filtered_df[filtered_df['postal_code'] == postal_code]

# Show results count
st.info(f"📊 Showing {len(filtered_df)} merchants (powered by SQLite)")

st.subheader("🏪 Merchant Results")

if not filtered_df.empty:
    # Sort options
    sort_by = st.selectbox(
        "Sort by",
        ["Rating (High to Low)", "Rating (Low to High)", "Name (A-Z)", "Review Count"]
    )

    # Apply sorting
    if sort_by == "Rating (High to Low)":
        filtered_df = filtered_df.sort_values('google_rating', ascending=False)
    elif sort_by == "Rating (Low to High)":
        filtered_df = filtered_df.sort_values('google_rating', ascending=True)
    elif sort_by == "Name (A-Z)":
        filtered_df = filtered_df.sort_values('name')
    elif sort_by == "Review Count":
        filtered_df = filtered_df.sort_values('review_count', ascending=False)

    # Display merchant cards
    for idx, row in filtered_df.head(50).iterrows():  # Show first 50 results
        with st.container():
            # Card header
            col1, col2 = st.columns([4, 1])

            with col1:
                # Merchant name and type
                st.markdown(f"### {row['name']}")

                # Category badges - show all types
                all_types = row['all_types']
                if pd.notna(all_types) and all_types != 'N/A':
                    categories = [cat.strip() for cat in all_types.split(',')]
                    badges_html = " ".join([
                        f"<span class='category-badge'>{cat.replace('_', ' ').title()}</span>"
                        for cat in categories[:5]  # Limit to first 5 badges
                    ])
                    st.markdown(badges_html, unsafe_allow_html=True)

                # Rating and price
                rating = row['google_rating'] if pd.notna(row['google_rating']) else "N/A"
                reviews = row['review_count'] if pd.notna(row['review_count']) else 0

                if rating != "N/A":
                    stars = "⭐" * round(rating)
                    st.markdown(f"{stars} **{rating}** ({int(reviews)} reviews)")
                else:
                    st.markdown("No ratings yet")

                # Price level
                if pd.notna(row['price_level']):
                    price_symbols = "💰" * int(row['price_level'] + 1)
                    st.caption(price_symbols)

                # Address
                st.caption(f"📍 {row['formatted_address']}")

                # Contact info
                col_phone, col_web = st.columns(2)

                with col_phone:
                    if pd.notna(row['phone_number']) and row['phone_number'] != 'N/A':
                        st.markdown(f"📞 {row['phone_number']}")

                with col_web:
                    if pd.notna(row['website']) and row['website'] != 'N/A':
                        st.markdown(f"🌐 [Website]({row['website']})")

            with col2:
                # Action buttons
                if pd.notna(row['website']) and row['website'] != 'N/A':
                    st.link_button("🌐 Visit", row['website'], use_container_width=True)

            st.markdown("---")  # Divider between cards

    if len(filtered_df) > 50:
        st.info(f"💡 Showing first 50 of {len(filtered_df)} results. Refine your search to see more specific results.")

else:
    st.warning("😕 No merchants found with the current filters.")

# ==================== FOOTER ====================
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <p>🛒 CDC Voucher Merchant Search (SQLite Version)</p>
        <p style='font-size: 0.8rem;'>Data sourced from Google Places API • Powered by SQLite • Built with Streamlit</p>
    </div>
    """,
    unsafe_allow_html=True
)
