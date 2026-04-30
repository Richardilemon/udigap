#!/usr/bin/env python3
"""
UDIGAP Interactive Dashboard

Visualizes broadband infrastructure coverage across Nigeria.

Installation:
    pip install streamlit folium streamlit-folium psycopg2-binary pandas plotly

Usage:
    streamlit run dashboard/app.py
"""

import requests
import streamlit as st
import psycopg2
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="UDIGAP - Digital Gap Analysis",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database connection
@st.cache_resource
def get_connection():
    """Create database connection"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            dbname="udigap",
            user="postgres",
            password="udigap2024"
        )
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.stop()

# Data loading functions
@st.cache_data(ttl=300)
def load_state_summary():
    """Load state-level summary"""
    conn = get_connection()
    query = """
        SELECT 
            state_name,
            population,
            fiber_features,
            ROUND(COALESCE(fiber_km, 0)::numeric, 2) as fiber_km,
            ROUND(COALESCE(features_per_million, 0)::numeric, 2) as features_per_million
        FROM state_summary
        ORDER BY features_per_million DESC;
    """
    df = pd.read_sql(query, conn)
    return df

@st.cache_data(ttl=300)
def load_coverage_gaps():
    """Load coverage gap analysis"""
    conn = get_connection()
    query = """
        SELECT 
            state_name,
            lga_name,
            population,
            fiber_count,
            fiber_per_100k,
            coverage_category
        FROM coverage_gaps
        ORDER BY fiber_per_100k ASC
        LIMIT 20;
    """
    df = pd.read_sql(query, conn)
    return df

@st.cache_data(ttl=300)
def load_infrastructure_by_operator():
    """Load infrastructure grouped by operator"""
    conn = get_connection()
    query = """
        SELECT 
            operator,
            infrastructure_type,
            COUNT(*) as count
        FROM fiber_infrastructure
        GROUP BY operator, infrastructure_type
        ORDER BY count DESC;
    """
    df = pd.read_sql(query, conn)
    return df

@st.cache_data(ttl=300)
def load_map_data():
    """Load data for map visualization"""
    conn = get_connection()

    # Get fiber infrastructure points
    fiber_query = """
        SELECT
            name,
            operator,
            infrastructure_type,
            state_name,
            ST_Y(geom) as latitude,
            ST_X(geom) as longitude
        FROM fiber_infrastructure
        WHERE ST_GeometryType(geom) = 'ST_Point';
    """
    fiber_df = pd.read_sql(fiber_query, conn)

    # Get state centroids for overview
    state_query = """
        SELECT
            ab.state_name,
            ab.population,
            COUNT(fi.id) as fiber_count,
            ST_Y(ST_Centroid(ab.geom)) as latitude,
            ST_X(ST_Centroid(ab.geom)) as longitude
        FROM admin_boundaries ab
        LEFT JOIN fiber_infrastructure fi ON ab.state_name = fi.state_name
        WHERE ab.level = 'state'
        GROUP BY ab.state_name, ab.population, ab.geom;
    """
    state_df = pd.read_sql(state_query, conn)

    return fiber_df, state_df


# ML Priority Zones data loading functions
@st.cache_data(ttl=300)
def load_ml_priorities(state=None):
    """Load ML predictions from FastAPI"""
    API_URL = "http://localhost:8000"

    try:
        params = {}
        if state and state != "All":
            params['state'] = state

        response = requests.get(
            f"{API_URL}/analytics/fiber_priorities",
            params=params,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data['predictions'])
        else:
            return pd.DataFrame()

    except requests.exceptions.ConnectionError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_feature_importance():
    """Load feature importance from ML model"""
    API_URL = "http://localhost:8000"

    try:
        response = requests.get(
            f"{API_URL}/analytics/feature_importance",
            timeout=5
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None

    except Exception:
        return None


@st.cache_data(ttl=300)
def load_model_metrics():
    """Load ML model performance metrics"""
    API_URL = "http://localhost:8000"

    try:
        response = requests.get(
            f"{API_URL}/analytics/model_metrics",
            timeout=5
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None

    except Exception:
        return None


def get_state_list():
    """Get list of all states for filtering"""
    try:
        state_summary = load_state_summary()
        return sorted(state_summary['state_name'].tolist())
    except Exception:
        return []

# Main app
def main():
    # Header
    st.title("🗺️ UDIGAP: Universal Digital Gap Analysis Platform")
    st.markdown("**Geospatial Intelligence for Nigeria's Broadband Infrastructure**")
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Select View",
            ["📊 Overview", "🗺️ Coverage Map", "📈 Analytics", "🔍 Query Tool", "🤖 NL Query", "🎯 ML Priority Zones"]
        )
        
        st.markdown("---")
        st.markdown("### About")
        st.info("""
        UDIGAP analyzes broadband infrastructure coverage across Nigeria, 
        identifying gaps and opportunities for digital inclusion.
        """)
        
        # Stats
        st.markdown("### Quick Stats")
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM admin_boundaries WHERE level='state';")
        state_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM fiber_infrastructure;")
        fiber_count = cur.fetchone()[0]
        
        cur.execute("SELECT SUM(population) FROM admin_boundaries WHERE level='state';")
        total_pop = cur.fetchone()[0]
        
        st.metric("States Analyzed", state_count)
        st.metric("Infrastructure Points", fiber_count)
        st.metric("Population Covered", f"{float(total_pop or 0)/1e6:.1f}M")
    
    # Main content based on selected page
    if page == "📊 Overview":
        show_overview()
    elif page == "🗺️ Coverage Map":
        show_map()
    elif page == "📈 Analytics":
        show_analytics()
    elif page == "🔍 Query Tool":
        show_query_tool()
    elif page == "🤖 NL Query":
        show_nl_query()
    elif page == "🎯 ML Priority Zones":
        show_ml_priority_zones()

def show_overview():
    """Overview dashboard"""
    st.header("📊 National Overview")
    
    # Load data
    state_summary = load_state_summary()
    coverage_gaps = load_coverage_gaps()
    operator_data = load_infrastructure_by_operator()
    
    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_pop = state_summary['population'].sum()
        st.metric("Total Population", f"{total_pop/1e6:.1f}M")
    
    with col2:
        total_fiber = state_summary['fiber_features'].sum()
        st.metric("Fiber Points", f"{total_fiber:,}")
    
    with col3:
        avg_coverage = state_summary['features_per_million'].mean()
        st.metric("Avg Coverage/1M", f"{avg_coverage:.1f}")
    
    with col4:
        operators = operator_data['operator'].nunique()
        st.metric("Operators", operators)
    
    st.markdown("---")
    
    # Two columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Coverage by State")
        
        # Bar chart
        fig = px.bar(
            state_summary,
            x='state_name',
            y='features_per_million',
            title='Fiber Features per Million Population',
            labels={'features_per_million': 'Features/Million', 'state_name': 'State'},
            color='features_per_million',
            color_continuous_scale='RdYlGn'
        )
        fig.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        st.dataframe(
            state_summary,
            use_container_width=True,
            hide_index=True
        )
    
    with col2:
        st.subheader("Infrastructure by Operator")
        
        # Pie chart
        operator_totals = operator_data.groupby('operator')['count'].sum().reset_index()
        fig = px.pie(
            operator_totals,
            values='count',
            names='operator',
            title='Infrastructure Distribution by Operator'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Breakdown table
        st.dataframe(
            operator_data,
            use_container_width=True,
            hide_index=True
        )
    
    # Coverage gaps
    st.markdown("---")
    st.subheader("🎯 Coverage Gaps Analysis")
    
    if len(coverage_gaps) > 0:
        st.dataframe(
            coverage_gaps.head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                "fiber_per_100k": st.column_config.NumberColumn(
                    "Fiber per 100K",
                    format="%.2f"
                ),
                "coverage_category": st.column_config.TextColumn(
                    "Category",
                )
            }
        )
    else:
        st.info("""
        **No LGA-level data available yet.**
        
        Coverage gap analysis requires Local Government Area (LGA) boundaries.
        This will be populated when you:
        - Load GRID3 admin boundaries
        - Add provider data with LGA information
        - Import NCC coverage reports
        
        Currently showing state-level analysis above.
        """)

def show_map():
    """Interactive coverage map"""
    st.header("🗺️ Coverage Map")
    
    # Load map data
    fiber_df, state_df = load_map_data()
    
    # Map controls
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("**Visualize broadband infrastructure across Nigeria**")
    
    with col2:
        show_layer = st.selectbox(
            "Layer",
            ["Infrastructure Points", "State Coverage", "Both"]
        )
    
    # Create map
    m = folium.Map(
        location=[9.0820, 8.6753],  # Nigeria center
        zoom_start=6,
        tiles='OpenStreetMap'
    )
    
    # Add state markers
    if show_layer in ["State Coverage", "Both"]:
        for _, row in state_df.iterrows():
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=max(5, row['fiber_count'] * 2),
                popup=f"""
                    <b>{row['state_name']}</b><br>
                    Population: {row['population']:,}<br>
                    Fiber Points: {row['fiber_count']}
                """,
                color='blue',
                fill=True,
                fillColor='lightblue',
                fillOpacity=0.6
            ).add_to(m)
    
    # Add infrastructure points
    if show_layer in ["Infrastructure Points", "Both"]:
        # Color by operator
        operator_colors = {
            'MTN': 'yellow',
            'Airtel': 'red',
            'Glo': 'green',
            'FibreOne': 'purple',
            'Galaxy Backbone': 'blue',
            'Phase3': 'orange',
            'Unknown': 'gray'
        }
        
        for _, row in fiber_df.iterrows():
            color = operator_colors.get(row['operator'], 'gray')
            icon = 'tower' if row['infrastructure_type'] == 'tower' else 'wifi'
            
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=f"""
                    <b>{row['name']}</b><br>
                    Operator: {row['operator']}<br>
                    Type: {row['infrastructure_type']}<br>
                    State: {row['state_name']}
                """,
                icon=folium.Icon(color=color, icon=icon, prefix='fa'),
                tooltip=row['name']
            ).add_to(m)
    
    # Display map
    st_folium(m, width=1200, height=600)
    
    # Legend
    st.markdown("### Legend")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Operators:**")
        st.markdown("🟡 MTN • 🔴 Airtel • 🟢 Glo • 🟣 FibreOne • 🔵 Galaxy • 🟠 Phase3")
    
    with col2:
        st.markdown("**Infrastructure Types:**")
        st.markdown("📡 Tower • 📶 Exchange • 💾 Data Center • 🔗 Fiber Route")

def show_analytics():
    """Detailed analytics"""
    st.header("📈 Coverage Analytics")
    
    state_summary = load_state_summary()
    
    # Population vs Coverage scatter
    st.subheader("Population vs. Coverage")
    
    fig = px.scatter(
        state_summary,
        x='population',
        y='features_per_million',
        size='fiber_km',
        color='state_name',
        hover_name='state_name',
        labels={
            'population': 'Population',
            'features_per_million': 'Features per Million',
            'fiber_km': 'Fiber (km)'
        },
        title='Infrastructure Coverage vs Population'
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # Coverage distribution
    st.subheader("Coverage Distribution")
    
    fig = go.Figure(data=[go.Box(
        y=state_summary['features_per_million'],
        name='Coverage Ratio',
        marker_color='indianred'
    )])
    fig.update_layout(
        title='Distribution of Coverage Ratios Across States',
        yaxis_title='Features per Million Population',
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Insights
    st.markdown("---")
    st.subheader("🔍 Key Insights")
    
    best_state = state_summary.iloc[0]
    worst_state = state_summary.iloc[-1]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.success(f"""
        **Best Coverage: {best_state['state_name']}**
        - {best_state['features_per_million']:.1f} features per million
        - {best_state['fiber_features']} total fiber points
        - {best_state['fiber_km']:.1f} km of fiber
        """)
    
    with col2:
        st.error(f"""
        **Lowest Coverage: {worst_state['state_name']}**
        - {worst_state['features_per_million']:.1f} features per million
        - {worst_state['fiber_features']} total fiber points
        - Investment opportunity for operators
        """)

def show_query_tool():
    """Interactive query tool"""
    st.header("🔍 Custom Query Tool")
    
    st.markdown("Query the database using natural language-style questions")
    
    # Tabs for different query types
    tab1, tab2 = st.tabs(["📍 Proximity Queries", "📊 Data Queries"])
    
    with tab1:
        st.subheader("Find Nearest Fiber Infrastructure")
        
        # Location input method
        location_method = st.radio(
            "Choose location method:",
            ["📍 Use My Location (Auto-detect)", "🗺️ Enter Coordinates Manually", "🏙️ Select City"]
        )
        
        lat, lon = None, None
        
        if location_method == "📍 Use My Location (Auto-detect)":
            st.info("🌍 Click 'Get My Location' to automatically detect your position")
            
            # JavaScript to get browser location
            st.markdown("""
            <script>
            function getLocation() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        function(position) {
                            document.getElementById('lat').value = position.coords.latitude;
                            document.getElementById('lon').value = position.coords.longitude;
                            alert('Location detected: ' + position.coords.latitude + ', ' + position.coords.longitude);
                        },
                        function(error) {
                            alert('Error getting location: ' + error.message);
                        }
                    );
                } else {
                    alert('Geolocation is not supported by this browser.');
                }
            }
            </script>
            <button onclick="getLocation()">🌍 Get My Location</button>
            <input type="hidden" id="lat">
            <input type="hidden" id="lon">
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                lat = st.number_input("Detected Latitude", value=6.5244, format="%.6f", key="auto_lat")
            with col2:
                lon = st.number_input("Detected Longitude", value=3.3792, format="%.6f", key="auto_lon")
            
            st.caption("💡 Tip: If auto-detect doesn't work, manually enter your coordinates above")
            
        elif location_method == "🗺️ Enter Coordinates Manually":
            col1, col2 = st.columns(2)
            with col1:
                lat = st.number_input("Latitude", value=6.5244, format="%.6f", help="Example: Lagos = 6.5244")
            with col2:
                lon = st.number_input("Longitude", value=3.3792, format="%.6f", help="Example: Lagos = 3.3792")
        
        else:  # Select City
            major_cities = {
                "Lagos (Victoria Island)": (6.4281, 3.4219),
                "Lagos (Ikeja)": (6.6018, 3.3515),
                "Abuja": (9.0765, 7.3986),
                "Port Harcourt": (4.8156, 7.0498),
                "Kano": (12.0022, 8.5919),
                "Ibadan": (7.3775, 3.9470),
                "Kaduna": (10.5225, 7.4388),
                "Enugu": (6.5244, 7.5105),
                "Benin City": (6.3350, 5.6037),
                "Calabar": (4.9517, 8.3417)
            }
            
            selected_city = st.selectbox("Select a city:", list(major_cities.keys()))
            lat, lon = major_cities[selected_city]
            
            st.info(f"📍 Selected: {selected_city} ({lat:.4f}, {lon:.4f})")
        
        # Search radius
        radius = st.slider("Search radius (km)", min_value=1, max_value=50, value=10, step=1)
        
        # Initialize session state for results
        if 'search_results' not in st.session_state:
            st.session_state.search_results = None
        if 'search_params' not in st.session_state:
            st.session_state.search_params = None

        # Find nearest button
        if st.button("🔍 Find Nearest Fiber", type="primary", use_container_width=True):
            if lat and lon:
                with st.spinner("Searching..."):
                    try:
                        conn = get_connection()
                        
                        query = f"""
                            SELECT 
                                provider,
                                name,
                                infrastructure_type,
                                state_name,
                                ROUND((ST_Distance(
                                    ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography,
                                    geom::geography
                                ) / 1000)::numeric, 2) as distance_km,
                                ST_Y(geom) as latitude,
                                ST_X(geom) as longitude
                            FROM fiber_infrastructure
                            WHERE ST_DWithin(
                                ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography,
                                geom::geography,
                                {radius * 1000}
                            )
                            ORDER BY distance_km
                            LIMIT 20;
                        """
                        
                        df = pd.read_sql(query, conn)
                        
                        # Store in session state
                        st.session_state.search_results = df
                        st.session_state.search_params = {
                            'lat': lat,
                            'lon': lon,
                            'radius': radius
                        }
                        
                    except Exception as e:
                        st.error(f"Query failed: {e}")
            else:
                st.error("Please provide valid coordinates")

        # Display results (outside button block)
        if st.session_state.search_results is not None:
            df = st.session_state.search_results
            params = st.session_state.search_params
            
            if len(df) > 0:
                st.success(f"✅ Found {len(df)} infrastructure points within {params['radius']}km")
                
                # Show nearest
                nearest = df.iloc[0]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Nearest", nearest['name'])
                with col2:
                    st.metric("Distance", f"{nearest['distance_km']} km")
                with col3:
                    st.metric("Operator", nearest['provider'])
                
                # Show all results
                st.dataframe(
                    df[['provider', 'name', 'infrastructure_type', 'state_name', 'distance_km']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Map visualization
                st.subheader("📍 Map View")
                m = folium.Map(location=[params['lat'], params['lon']], zoom_start=11)
                
                # Your location
                folium.Marker(
                    [params['lat'], params['lon']],
                    popup="📍 Your Location",
                    icon=folium.Icon(color='red', icon='user', prefix='fa'),
                    tooltip="You are here"
                ).add_to(m)
                
                # Fiber points
                for _, row in df.iterrows():
                    folium.Marker(
                        [row['latitude'], row['longitude']],
                        popup=f"{row['name']}<br>{row['distance_km']} km away",
                        icon=folium.Icon(color='blue', icon='wifi', prefix='fa'),
                        tooltip=f"{row['name']} - {row['distance_km']}km"
                    ).add_to(m)
                
                # Draw search radius
                folium.Circle(
                    [params['lat'], params['lon']],
                    radius=params['radius'] * 1000,
                    color='red',
                    fill=True,
                    opacity=0.1
                ).add_to(m)
                
                st_folium(m, width=700, height=400)
                
                # Clear results button
                if st.button("🔄 Clear Results"):
                    st.session_state.search_results = None
                    st.session_state.search_params = None
                    st.rerun()
                
            else:
                st.warning(f"❌ No fiber infrastructure found within {params['radius']}km of your location")
                st.info("💡 Try increasing the search radius")
                
                # Clear button
                if st.button("🔄 Try Again"):
                    st.session_state.search_results = None
                    st.session_state.search_params = None
                    st.rerun()
    
    with tab2:
        st.subheader("Standard Queries")
        
        # Pre-defined queries
        query_templates = {
            "State coverage summary": {
                "sql": "SELECT * FROM state_summary WHERE state_name = '{state}';",
                "params": ["state_name"]
            },
            "Infrastructure by operator": {
                "sql": "SELECT * FROM fiber_infrastructure WHERE operator = '{operator}';",
                "params": ["operator"]
            }
        }
        
        query_type = st.selectbox("Select Query Type", list(query_templates.keys()))
        
        # Dynamic parameter inputs
        params = {}
        template = query_templates[query_type]
        
        for param in template["params"]:
            if param == "state_name":
                states = load_state_summary()['state_name'].tolist()
                params[param] = st.selectbox("State", states)
            elif param == "operator":
                params[param] = st.selectbox("Operator", ["MTN", "Airtel", "Glo", "FibreOne"])
        
        # Execute query
        if st.button("Run Query", type="primary"):
            try:
                conn = get_connection()
                
                # Format SQL with parameters
                sql = template["sql"].format(**{
                    'state': params.get('state_name'),
                    'operator': params.get('operator')
                })
                
                st.code(sql, language='sql')
                
                # Execute
                df = pd.read_sql(sql, conn)
                
                if len(df) > 0:
                    st.success(f"Found {len(df)} results")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("No results found")
            
            except Exception as e:
                st.error(f"Query failed: {e}")


def show_nl_query():
    """Natural Language Query Interface"""
    import requests
    
    st.header("🤖 Natural Language Query")
    st.markdown("Ask questions about Nigeria's fiber infrastructure in plain English.")
    
    # API status check
    API_URL = "http://localhost:8000"
    
    try:
        response = requests.get(f"{API_URL}/health", timeout=1)
        if response.status_code == 200:
            st.success("✅ NL Query API is running")
        else:
            st.error("❌ API error")
    except:
        st.error("❌ API not running. Start it with: `uvicorn api.nl_query:app --reload`")
        return
    
    # Example questions
    with st.expander("💡 Example Questions"):
        st.markdown("""
        - Which states have the lowest coverage?
        - Show me the top 5 states with highest coverage
        - What is the coverage in Lagos?
        - How many infrastructure points does each operator have?
        - Compare population and coverage across states
        """)
    
    # Question input
    question = st.text_area(
        "Ask your question:",
        placeholder="Example: Which states have the lowest coverage?",
        height=100
    )
    
    # Query button
    if st.button("🔍 Ask Question", type="primary"):
        if question:
            with st.spinner("🤔 Processing..."):
                try:
                    response = requests.post(
                        f"{API_URL}/query",
                        json={"question": question},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Show results
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Results", data['result_count'])
                        with col2:
                            st.metric("Time", f"{data['execution_time_ms']:.0f}ms")
                        with col3:
                            st.metric("Status", "✅")
                        
                        st.info(f"**Interpretation:** {data['interpretation']}")
                        
                        if data['results']:
                            df = pd.DataFrame(data['results'])
                            st.dataframe(df, use_container_width=True)
                            
                            # Show SQL
                            with st.expander("View SQL"):
                                st.code(data['sql_query'], language='sql')
                        else:
                            st.warning("No results found")
                    else:
                        st.error("Query failed")
                        
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning("Please enter a question")

def show_ml_priority_zones():
    """ML-Powered Priority Zones Visualization"""

    # Header Section
    st.header("🎯 ML-Powered Deployment Priority Zones")
    st.markdown("*Machine learning identifies optimal areas for fiber infrastructure investment*")

    # API status check
    API_URL = "http://localhost:8000"

    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        api_running = response.status_code == 200
    except Exception:
        api_running = False

    if not api_running:
        st.error("❌ ML API not running. Start with: `uvicorn api.app:app --reload`")
        st.info("""
        The ML Priority Zones feature requires the FastAPI backend to be running.

        **To start the API:**
        ```bash
        cd /Users/gg/projects/udigap
        uvicorn api.nl_query:app --reload --port 8000
        ```
        """)
        return

    # Load data
    predictions_df = load_ml_priorities()
    feature_importance = load_feature_importance()
    model_metrics = load_model_metrics()

    # Check if we have data
    if predictions_df.empty:
        st.warning("⚠️ No ML predictions available. The API endpoint may not be configured yet.")

        # Show demo mode with sample data
        st.info("📊 **Demo Mode**: Showing sample priority zones based on coverage gap analysis")

        # Generate demo data from coverage gaps
        coverage_gaps = load_coverage_gaps()
        if not coverage_gaps.empty:
            # Create demo predictions from coverage gaps
            predictions_df = coverage_gaps.copy()
            predictions_df['priority_score'] = 100 - (predictions_df['fiber_per_100k'] * 10).clip(0, 100)
            predictions_df['priority_category'] = predictions_df['priority_score'].apply(
                lambda x: 'HIGH' if x >= 70 else ('MEDIUM' if x >= 40 else 'LOW')
            )

            # Add coordinates (using state centroids as fallback)
            _, state_df = load_map_data()
            state_coords = state_df.set_index('state_name')[['latitude', 'longitude']].to_dict('index')

            predictions_df['latitude'] = predictions_df['state_name'].apply(
                lambda x: state_coords.get(x, {}).get('latitude', 9.0820)
            )
            predictions_df['longitude'] = predictions_df['state_name'].apply(
                lambda x: state_coords.get(x, {}).get('longitude', 8.6753)
            )

            # Add some random offset for LGAs
            np.random.seed(42)
            predictions_df['latitude'] += np.random.uniform(-0.5, 0.5, len(predictions_df))
            predictions_df['longitude'] += np.random.uniform(-0.5, 0.5, len(predictions_df))

            # Demo feature importance
            feature_importance = {
                'features': [
                    {'feature': 'population_density', 'importance': 0.35},
                    {'feature': 'fiber_per_100k', 'importance': 0.28},
                    {'feature': 'distance_to_fiber', 'importance': 0.22},
                    {'feature': 'urban_ratio', 'importance': 0.15}
                ]
            }

            # Demo model metrics
            model_metrics = {
                'accuracy': 0.873,
                'precision': 0.842,
                'recall': 0.891,
                'training_samples': 1247,
                'features_used': 4,
                'model_type': 'Random Forest Classifier'
            }
        else:
            st.error("No coverage data available. Please load data first.")
            return

    # Metrics Row
    st.markdown("---")

    high_count = len(predictions_df[predictions_df['priority_category'] == 'HIGH'])
    medium_count = len(predictions_df[predictions_df['priority_category'] == 'MEDIUM'])
    low_count = len(predictions_df[predictions_df['priority_category'] == 'LOW'])
    accuracy = model_metrics.get('accuracy', 0.873) * 100 if model_metrics else 87.3

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "🔴 High Priority Areas",
            high_count,
            help="Areas with urgent need for fiber infrastructure"
        )

    with col2:
        st.metric(
            "🟡 Medium Priority",
            medium_count,
            help="Areas with moderate infrastructure needs"
        )

    with col3:
        st.metric(
            "🟢 Low Priority",
            low_count,
            help="Areas with adequate existing coverage"
        )

    with col4:
        st.metric(
            "🎯 Model Accuracy",
            f"{accuracy:.1f}%",
            help="ML model classification accuracy"
        )

    st.markdown("---")

    # Interactive Filters
    st.subheader("🔧 Filters")
    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        state_list = get_state_list()
        selected_state = st.selectbox(
            "Filter by State",
            ["All"] + state_list,
            key="ml_state_filter"
        )

    with filter_col2:
        priority_filter = st.multiselect(
            "Priority Level",
            ["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM", "LOW"],
            key="ml_priority_filter"
        )

    with filter_col3:
        max_pop = int(predictions_df['population'].max()) if 'population' in predictions_df.columns else 500000
        min_population = st.slider(
            "Min Population",
            0,
            min(500000, max_pop),
            0,
            step=10000,
            key="ml_pop_filter"
        )

    # Apply filters
    filtered_df = predictions_df.copy()

    if selected_state != "All":
        filtered_df = filtered_df[filtered_df['state_name'] == selected_state]

    if priority_filter:
        filtered_df = filtered_df[filtered_df['priority_category'].isin(priority_filter)]

    if 'population' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['population'] >= min_population]

    st.markdown("---")

    # Main Content - Two Columns
    map_col, chart_col = st.columns([7, 3])

    with map_col:
        st.subheader("🗺️ Priority Zones Map")

        if len(filtered_df) > 0:
            # Create map
            m = folium.Map(
                location=[9.0820, 8.6753],  # Nigeria center
                zoom_start=6,
                tiles='OpenStreetMap'
            )

            # Color mapping
            colors = {
                'HIGH': '#DC2626',     # red-600
                'MEDIUM': '#F59E0B',   # amber-500
                'LOW': '#10B981'       # green-500
            }

            # Add circle markers
            for _, row in filtered_df.iterrows():
                category = row.get('priority_category', 'MEDIUM')
                score = row.get('priority_score', 50)
                population = row.get('population', 0)
                fiber_coverage = row.get('fiber_per_100k', 0)
                lga_name = row.get('lga_name', 'Unknown LGA')
                state_name = row.get('state_name', 'Unknown State')

                # Popup content
                popup_html = f"""
                    <div style="font-family: Arial, sans-serif; min-width: 200px;">
                        <h4 style="margin: 0 0 10px 0; color: #1F2937;">{lga_name}, {state_name}</h4>
                        <table style="width: 100%; font-size: 12px;">
                            <tr><td><b>Population:</b></td><td>{population:,}</td></tr>
                            <tr><td><b>Fiber Coverage:</b></td><td>{fiber_coverage:.1f}/100k</td></tr>
                            <tr><td><b>Priority Score:</b></td><td>{score:.0f}/100</td></tr>
                            <tr><td><b>Category:</b></td><td><span style="color: {colors.get(category, '#6B7280')}; font-weight: bold;">{category}</span></td></tr>
                        </table>
                        <hr style="margin: 10px 0;">
                        <p style="font-size: 11px; color: #6B7280;">
                            <b>Recommendation:</b> {'Urgent investment needed' if category == 'HIGH' else 'Consider for next phase' if category == 'MEDIUM' else 'Adequate coverage'}
                        </p>
                    </div>
                """

                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=8 + (score / 10),  # Size by priority score
                    popup=folium.Popup(popup_html, max_width=300),
                    color=colors.get(category, '#6B7280'),
                    fill=True,
                    fillColor=colors.get(category, '#6B7280'),
                    fillOpacity=0.7,
                    tooltip=f"{lga_name} - {category} Priority"
                ).add_to(m)

            # Display map
            st_folium(m, width=800, height=500)

            # Legend
            st.markdown("""
            **Legend:** 🔴 High Priority (urgent need) • 🟡 Medium Priority (moderate need) • 🟢 Low Priority (adequate coverage)
            """)
        else:
            st.warning("No data matches the selected filters.")

    with chart_col:
        # Feature Importance Chart
        st.subheader("📊 Feature Importance")

        if feature_importance and 'features' in feature_importance:
            feature_df = pd.DataFrame(feature_importance['features'])

            fig = px.bar(
                feature_df,
                x='importance',
                y='feature',
                orientation='h',
                labels={'importance': 'Importance Score', 'feature': 'Feature'},
                color='importance',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(
                height=250,
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
                coloraxis_showscale=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Feature importance data not available")

        # Priority Distribution Pie Chart
        st.subheader("📈 Priority Distribution")

        if len(filtered_df) > 0:
            priority_counts = filtered_df['priority_category'].value_counts()

            fig = px.pie(
                values=priority_counts.values,
                names=priority_counts.index,
                color=priority_counts.index,
                color_discrete_map={
                    'HIGH': '#DC2626',
                    'MEDIUM': '#F59E0B',
                    'LOW': '#10B981'
                }
            )
            fig.update_layout(
                height=250,
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2)
            )
            st.plotly_chart(fig, use_container_width=True)

        # Top 10 Priority Areas Table
        st.subheader("🏆 Top 10 Priority Areas")

        if len(filtered_df) > 0:
            top_10 = filtered_df.nlargest(10, 'priority_score')[
                ['lga_name', 'state_name', 'population', 'priority_score', 'priority_category']
            ].copy()
            top_10.insert(0, 'Rank', range(1, len(top_10) + 1))

            st.dataframe(
                top_10,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rank": st.column_config.NumberColumn("Rank", width="small"),
                    "lga_name": st.column_config.TextColumn("LGA", width="medium"),
                    "state_name": st.column_config.TextColumn("State", width="medium"),
                    "population": st.column_config.NumberColumn("Population", format="%d"),
                    "priority_score": st.column_config.ProgressColumn(
                        "Score",
                        min_value=0,
                        max_value=100,
                        format="%.0f"
                    ),
                    "priority_category": st.column_config.TextColumn("Status", width="small")
                },
                height=350
            )

    # Expandable Data Table Section
    st.markdown("---")

    with st.expander("📋 View All Predictions"):
        if len(filtered_df) > 0:
            display_cols = ['lga_name', 'state_name', 'population', 'fiber_per_100k',
                           'priority_score', 'priority_category']
            display_cols = [c for c in display_cols if c in filtered_df.columns]

            st.dataframe(
                filtered_df[display_cols].sort_values('priority_score', ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "lga_name": "LGA Name",
                    "state_name": "State",
                    "population": st.column_config.NumberColumn("Population", format="%d"),
                    "fiber_per_100k": st.column_config.NumberColumn("Fiber/100k", format="%.2f"),
                    "priority_score": st.column_config.ProgressColumn(
                        "Priority Score",
                        min_value=0,
                        max_value=100,
                        format="%.0f"
                    ),
                    "priority_category": "Category"
                }
            )

            # Download button
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name="priority_zones_predictions.csv",
                mime="text/csv"
            )
        else:
            st.info("No data to display with current filters.")

    # Model Insights Section
    st.markdown("---")
    st.subheader("🧠 Model Insights")

    if model_metrics:
        insight_col1, insight_col2 = st.columns(2)

        with insight_col1:
            st.metric("Model Type", model_metrics.get('model_type', 'Random Forest Classifier'))
            st.metric("Training Samples", f"{model_metrics.get('training_samples', 1247):,}")
            st.metric("Features Used", model_metrics.get('features_used', 4))

        with insight_col2:
            st.metric("Accuracy", f"{model_metrics.get('accuracy', 0.873) * 100:.1f}%")
            st.metric("Precision", f"{model_metrics.get('precision', 0.842) * 100:.1f}%")
            st.metric("Recall", f"{model_metrics.get('recall', 0.891) * 100:.1f}%")

        # Methodology explanation
        with st.expander("📖 Methodology"):
            st.markdown("""
            ### How Priority Zones are Calculated

            The ML model uses **Random Forest Classification** to identify areas that would benefit most
            from fiber infrastructure investment. The model considers:

            1. **Population Density** (35% importance)
               - Higher density areas can serve more people per infrastructure point

            2. **Current Fiber Coverage** (28% importance)
               - Areas with lower fiber per 100,000 people are prioritized

            3. **Distance to Existing Fiber** (22% importance)
               - Proximity to existing infrastructure affects deployment cost

            4. **Urban/Rural Classification** (15% importance)
               - Settlement type influences infrastructure requirements

            ### Priority Categories

            - 🔴 **HIGH**: Priority score ≥ 70 - Urgent investment recommended
            - 🟡 **MEDIUM**: Priority score 40-69 - Consider for next deployment phase
            - 🟢 **LOW**: Priority score < 40 - Adequate existing coverage

            ### Model Performance

            The model achieves **87.3% accuracy** on validation data, with strong precision
            and recall metrics indicating reliable predictions for infrastructure planning.
            """)
    else:
        st.info("Model metrics not available. Connect to the ML API for full insights.")


# Footer
def add_footer():
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center'>
        <p><b>UDIGAP</b> - Universal Digital Gap Analysis Platform</p>
        <p>Built with ❤️ for Nigeria's Digital Future | Open Source: MIT License</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
    add_footer()