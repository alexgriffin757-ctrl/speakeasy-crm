import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Speakeasy CRM",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Supabase config
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}


@st.cache_data(ttl=30)
def load_leads(filters=None):
    """Load leads from Supabase."""
    params = 'select=*&order=icp_tier.asc.nullslast,followers.desc.nullslast&limit=5000'
    if filters:
        params += filters
    r = requests.get(f'{SUPABASE_URL}/rest/v1/venues?{params}', headers=HEADERS)
    if r.status_code == 200:
        return r.json()
    return []


def update_lead(lead_id, data):
    """Update a lead in Supabase."""
    data['updated_at'] = datetime.utcnow().isoformat()
    r = requests.patch(
        f'{SUPABASE_URL}/rest/v1/venues?id=eq.{lead_id}',
        headers={**HEADERS, 'Prefer': 'return=minimal'},
        json=data
    )
    return r.status_code in (200, 204)


def get_stats():
    """Get dashboard stats."""
    stats = {}
    queries = {
        'total': '',
        'with_ig': '&instagram=not.is.null&instagram=neq.',
        'with_dm': '&decision_maker=not.is.null&decision_maker=neq.',
        'followed': '&followed=eq.true',
        'dm_sent': '&dm_sent=eq.true',
        'replied': '&replied=eq.true',
        'meeting_booked': '&meeting_booked=eq.true',
    }
    for key, q in queries.items():
        r = requests.get(
            f'{SUPABASE_URL}/rest/v1/venues?select=id{q}',
            headers={**HEADERS, 'Prefer': 'count=exact', 'Range-Unit': 'items', 'Range': '0-0'}
        )
        stats[key] = int(r.headers.get('content-range', '*/0').split('/')[-1])
    return stats


# --- UI ---

# Header
st.markdown("""
<div style="display:flex; align-items:center; gap:16px; margin-bottom:24px;">
    <div>
        <h1 style="margin:0; padding:0;">Speakeasy CRM</h1>
        <p style="margin:0; color:#888; font-size:14px;">Lead management & outreach tracking</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Stats bar
stats = get_stats()
col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
col1.metric("Total Leads", f"{stats['total']:,}")
col2.metric("With IG", f"{stats['with_ig']:,}")
col3.metric("Decision Makers", f"{stats['with_dm']:,}")
col4.metric("Followed", f"{stats['followed']:,}")
col5.metric("DMs Sent", f"{stats['dm_sent']:,}")
col6.metric("Replied", f"{stats['replied']:,}")
col7.metric("Meetings", f"{stats['meeting_booked']:,}")

st.divider()

# Sidebar filters
st.sidebar.header("Filters")

source_filter = st.sidebar.multiselect(
    "Source",
    ["tixr", "eventbrite", "google_maps"],
    default=[]
)

tier_filter = st.sidebar.multiselect(
    "ICP Tier",
    ["GOLD", "ORANGE", "YELLOW", "GRAY"],
    default=[]
)

status_filter = st.sidebar.selectbox(
    "Outreach Status",
    ["All", "Not Contacted", "Followed", "DM Sent", "Replied", "Meeting Booked"]
)

has_ig_filter = st.sidebar.checkbox("Has Instagram only", value=False)
has_dm_filter = st.sidebar.checkbox("Has Decision Maker only", value=False)

search = st.sidebar.text_input("Search venue name")

# Build filter string
filter_str = ''
if source_filter:
    filter_str += '&source=in.(' + ','.join(source_filter) + ')'
if tier_filter:
    filter_str += '&icp_tier=in.(' + ','.join(tier_filter) + ')'
if status_filter == "Not Contacted":
    filter_str += '&dm_sent=eq.false&followed=eq.false'
elif status_filter == "Followed":
    filter_str += '&followed=eq.true&dm_sent=eq.false'
elif status_filter == "DM Sent":
    filter_str += '&dm_sent=eq.true&replied=eq.false'
elif status_filter == "Replied":
    filter_str += '&replied=eq.true'
elif status_filter == "Meeting Booked":
    filter_str += '&meeting_booked=eq.true'
if has_ig_filter:
    filter_str += '&instagram=not.is.null&instagram=neq.'
if has_dm_filter:
    filter_str += '&decision_maker=not.is.null&decision_maker=neq.'
if search:
    filter_str += f'&name=ilike.*{search}*'

# Load data
leads = load_leads(filter_str)

if not leads:
    st.info("No leads match your filters.")
    st.stop()

df = pd.DataFrame(leads)

# Tabs
tab1, tab2, tab3 = st.tabs(["Lead List", "Lead Detail", "Pipeline View"])

with tab1:
    # Display columns
    display_cols = ['name', 'instagram', 'decision_maker', 'city', 'icp_tier', 'source',
                    'followers', 'followed', 'dm_sent', 'replied', 'meeting_booked']
    available_cols = [c for c in display_cols if c in df.columns]

    st.dataframe(
        df[available_cols],
        use_container_width=True,
        height=600,
        column_config={
            'name': st.column_config.TextColumn('Venue', width='medium'),
            'instagram': st.column_config.TextColumn('Instagram', width='small'),
            'decision_maker': st.column_config.TextColumn('Decision Maker', width='medium'),
            'city': st.column_config.TextColumn('City', width='small'),
            'icp_tier': st.column_config.TextColumn('Tier', width='small'),
            'source': st.column_config.TextColumn('Source', width='small'),
            'followers': st.column_config.NumberColumn('Followers', width='small'),
            'followed': st.column_config.CheckboxColumn('Followed', width='small'),
            'dm_sent': st.column_config.CheckboxColumn('DM Sent', width='small'),
            'replied': st.column_config.CheckboxColumn('Replied', width='small'),
            'meeting_booked': st.column_config.CheckboxColumn('Meeting', width='small'),
        },
    )
    st.caption(f"Showing {len(df)} leads")

with tab2:
    if len(df) > 0:
        # Search for specific lead
        lead_search = st.text_input("Search for a lead by name", key="detail_search")

        if lead_search:
            matches = df[df['name'].str.contains(lead_search, case=False, na=False)]
        else:
            matches = df.head(20)

        if len(matches) > 0:
            selected_name = st.selectbox("Select lead", matches['name'].tolist())
            lead = matches[matches['name'] == selected_name].iloc[0]

            col_left, col_right = st.columns(2)

            with col_left:
                st.subheader(lead['name'])
                st.write(f"**Instagram:** {lead.get('instagram', 'N/A')}")
                st.write(f"**Decision Maker:** {lead.get('decision_maker', 'N/A')}")
                st.write(f"**City:** {lead.get('city', 'N/A')}")
                st.write(f"**State:** {lead.get('state', 'N/A')}")
                st.write(f"**Tier:** {lead.get('icp_tier', 'N/A')}")
                st.write(f"**Source:** {lead.get('source', 'N/A')}")
                st.write(f"**Followers:** {lead.get('followers', 'N/A')}")
                st.write(f"**Website:** {lead.get('website', 'N/A')}")
                st.write(f"**Phone:** {lead.get('phone', 'N/A')}")
                st.write(f"**Email:** {lead.get('email', 'N/A')}")

            with col_right:
                st.write(f"**IG Bio:** {lead.get('ig_bio', 'N/A')}")
                st.write(f"**IG Category:** {lead.get('ig_category', 'N/A')}")
                st.write(f"**Description:** {(lead.get('description', '') or '')[:300]}")

                st.divider()
                st.write("**Outreach Status**")
                st.write(f"Followed: {'Yes' if lead.get('followed') else 'No'} {('(' + str(lead.get('followed_at', ''))[:10] + ')') if lead.get('followed_at') else ''}")
                st.write(f"DM Sent: {'Yes' if lead.get('dm_sent') else 'No'} {('(' + str(lead.get('dm_sent_at', ''))[:10] + ')') if lead.get('dm_sent_at') else ''}")
                st.write(f"Template: {lead.get('dm_template', 'N/A')}")
                st.write(f"Replied: {'Yes' if lead.get('replied') else 'No'}")
                st.write(f"Meeting Booked: {'Yes' if lead.get('meeting_booked') else 'No'}")

            # Update status
            st.divider()
            st.subheader("Update Status")
            update_col1, update_col2, update_col3, update_col4 = st.columns(4)

            with update_col1:
                if st.button("Mark Replied", key=f"replied_{lead['id']}"):
                    update_lead(lead['id'], {'replied': True, 'replied_at': datetime.utcnow().isoformat()})
                    st.success("Marked as replied!")
                    st.cache_data.clear()

            with update_col2:
                if st.button("Book Meeting", key=f"meeting_{lead['id']}"):
                    update_lead(lead['id'], {'meeting_booked': True, 'meeting_at': datetime.utcnow().isoformat()})
                    st.success("Meeting booked!")
                    st.cache_data.clear()

            with update_col3:
                new_notes = st.text_area("Notes", value=lead.get('notes', '') or '', key=f"notes_{lead['id']}")
                if st.button("Save Notes", key=f"save_notes_{lead['id']}"):
                    update_lead(lead['id'], {'notes': new_notes})
                    st.success("Notes saved!")
                    st.cache_data.clear()

with tab3:
    st.subheader("Outreach Pipeline")

    pipeline_data = {
        'Stage': ['Total Leads', 'Has Instagram', 'Followed', 'DM Sent', 'Replied', 'Meeting Booked'],
        'Count': [
            stats['total'],
            stats['with_ig'],
            stats['followed'],
            stats['dm_sent'],
            stats['replied'],
            stats['meeting_booked'],
        ]
    }
    pipeline_df = pd.DataFrame(pipeline_data)

    st.bar_chart(pipeline_df.set_index('Stage'))

    # Source breakdown
    st.subheader("Leads by Source")
    if 'source' in df.columns:
        source_counts = df['source'].value_counts()
        st.bar_chart(source_counts)

    # Tier breakdown
    st.subheader("Leads by ICP Tier")
    if 'icp_tier' in df.columns:
        tier_counts = df['icp_tier'].value_counts()
        st.bar_chart(tier_counts)

    # Recent activity
    st.subheader("Recent DMs Sent")
    dm_leads = df[df['dm_sent'] == True].sort_values('dm_sent_at', ascending=False).head(10) if 'dm_sent' in df.columns else pd.DataFrame()
    if len(dm_leads) > 0:
        st.dataframe(dm_leads[['name', 'instagram', 'dm_template', 'dm_sent_at', 'replied']].head(10), use_container_width=True)
    else:
        st.info("No DMs sent yet.")
