#!/usr/bin/env python3
"""
UDIGAP Sample Data Loader

Loads sample/demo data to get UDIGAP working immediately.
This creates realistic test data based on known infrastructure patterns.

Usage:
    python3 load_sample_data.py
"""

import psycopg2
import json
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'udigap',
    'user': 'postgres',
    'password': 'udigap2024'
}

def load_sample_admin_boundaries(conn):
    """Load sample state boundaries"""
    print("\n📍 Loading administrative boundaries...")
    
    cur = conn.cursor()
    
    # Sample Nigerian states with approximate boundaries and population
    states = [
        {
            'name': 'Lagos',
            'population': 15000000,
            'area_sqkm': 3577,
            # Simple bounding box polygon for Lagos
            'bbox': [3.1, 6.4, 3.7, 6.7]
        },
        {
            'name': 'FCT-Abuja',
            'population': 3500000,
            'area_sqkm': 7315,
            'bbox': [6.9, 8.7, 7.7, 9.3]
        },
        {
            'name': 'Rivers',
            'population': 7000000,
            'area_sqkm': 11077,
            'bbox': [6.7, 4.5, 7.2, 5.2]
        },
        {
            'name': 'Kano',
            'population': 13000000,
            'area_sqkm': 20131,
            'bbox': [8.2, 11.5, 8.8, 12.2]
        },
        {
            'name': 'Kaduna',
            'population': 8000000,
            'area_sqkm': 46053,
            'bbox': [7.2, 9.8, 8.0, 11.2]
        }
    ]
    
    for state in states:
        # Create simple polygon from bbox
        bbox = state['bbox']
        polygon_wkt = f"MULTIPOLYGON((({bbox[0]} {bbox[1]}, {bbox[2]} {bbox[1]}, {bbox[2]} {bbox[3]}, {bbox[0]} {bbox[3]}, {bbox[0]} {bbox[1]})))"
        
        cur.execute("""
            INSERT INTO admin_boundaries (name, level, state_name, population, area_sqkm, geom)
            VALUES (%s, 'state', %s, %s, %s, ST_GeomFromText(%s, 4326))
            ON CONFLICT DO NOTHING;
        """, (state['name'], state['name'], state['population'], state['area_sqkm'], polygon_wkt))
    
    conn.commit()
    print(f"  ✓ Loaded {len(states)} states")
    cur.close()


def load_sample_fiber_infrastructure(conn):
    """Load sample fiber infrastructure"""
    print("\n🌐 Loading fiber infrastructure...")
    
    cur = conn.cursor()
    
    # Sample fiber infrastructure based on known patterns
    infrastructure = [
        # Lagos - High density
        {'name': 'MTN Lagos Core', 'type': 'fiber_route', 'operator': 'MTN', 'state': 'Lagos', 'coords': [3.3792, 6.5244]},
        {'name': 'Airtel VI Hub', 'type': 'tower', 'operator': 'Airtel', 'state': 'Lagos', 'coords': [3.4280, 6.4281]},
        {'name': 'Glo Ikeja Exchange', 'type': 'exchange', 'operator': 'Glo', 'state': 'Lagos', 'coords': [3.3515, 6.6018]},
        {'name': 'FibreOne Lekki Route', 'type': 'fiber_route', 'operator': 'FibreOne', 'state': 'Lagos', 'coords': [3.4700, 6.4500]},
        
        # Abuja - Medium density
        {'name': 'MTN Abuja Hub', 'type': 'tower', 'operator': 'MTN', 'state': 'FCT-Abuja', 'coords': [7.4951, 9.0765]},
        {'name': 'Airtel Central Exchange', 'type': 'exchange', 'operator': 'Airtel', 'state': 'FCT-Abuja', 'coords': [7.4676, 9.0579]},
        {'name': 'Galaxy Backbone NOC', 'type': 'data_center', 'operator': 'Galaxy Backbone', 'state': 'FCT-Abuja', 'coords': [7.5200, 9.0800]},
        
        # Rivers - Port area
        {'name': 'MTN Port Harcourt', 'type': 'tower', 'operator': 'MTN', 'state': 'Rivers', 'coords': [7.0134, 4.8156]},
        {'name': 'Airtel Trans-Amadi', 'type': 'exchange', 'operator': 'Airtel', 'state': 'Rivers', 'coords': [7.0353, 4.8396]},
        
        # Kano - Northern hub
        {'name': 'MTN Kano Central', 'type': 'tower', 'operator': 'MTN', 'state': 'Kano', 'coords': [8.5167, 11.9833]},
        {'name': 'Airtel Kano Exchange', 'type': 'exchange', 'operator': 'Airtel', 'state': 'Kano', 'coords': [8.5264, 12.0022]},
        
        # Kaduna
        {'name': 'MTN Kaduna Hub', 'type': 'tower', 'operator': 'MTN', 'state': 'Kaduna', 'coords': [7.4389, 10.5225]},
        {'name': 'Phase3 Kaduna Node', 'type': 'fiber_route', 'operator': 'Phase3', 'state': 'Kaduna', 'coords': [7.4500, 10.5300]},
    ]
    
    for infra in infrastructure:
        point_wkt = f"POINT({infra['coords'][0]} {infra['coords'][1]})"
        
        cur.execute("""
            INSERT INTO fiber_infrastructure 
            (provider, name, infrastructure_type, operator, state_name, source, geom)
            VALUES (%s, %s, %s, %s, %s, 'sample_data', ST_GeomFromText(%s, 4326));
        """, (infra['operator'], infra['name'], infra['type'], infra['operator'], 
              infra['state'], point_wkt))
    
    conn.commit()
    print(f"  ✓ Loaded {len(infrastructure)} infrastructure points")
    cur.close()


def load_sample_population_data(conn):
    """Load sample population grid"""
    print("\n👥 Loading population data...")
    
    cur = conn.cursor()
    
    # Sample population grids for major cities
    pop_grids = [
        # Lagos urban cores
        {'state': 'Lagos', 'lga': 'Lagos Island', 'population': 250000, 'type': 'urban', 'coords': [3.3792, 6.5244, 3.4000, 6.5400]},
        {'state': 'Lagos', 'lga': 'Ikeja', 'population': 300000, 'type': 'urban', 'coords': [3.3400, 6.5900, 3.3600, 6.6100]},
        {'state': 'Lagos', 'lga': 'Lekki', 'population': 180000, 'type': 'peri-urban', 'coords': [3.4600, 6.4400, 3.4800, 6.4600]},
        
        # Abuja
        {'state': 'FCT-Abuja', 'lga': 'Central Area', 'population': 200000, 'type': 'urban', 'coords': [7.4800, 9.0700, 7.5000, 9.0900]},
        {'state': 'FCT-Abuja', 'lga': 'Garki', 'population': 150000, 'type': 'urban', 'coords': [7.4900, 9.0500, 7.5100, 9.0700]},
        
        # Port Harcourt
        {'state': 'Rivers', 'lga': 'Port Harcourt City', 'population': 300000, 'type': 'urban', 'coords': [7.0000, 4.8000, 7.0200, 4.8200]},
        
        # Kano
        {'state': 'Kano', 'lga': 'Kano Municipal', 'population': 400000, 'type': 'urban', 'coords': [8.5100, 11.9800, 8.5300, 12.0000]},
    ]
    
    for i, grid in enumerate(pop_grids, 1):
        coords = grid['coords']
        polygon_wkt = f"POLYGON(({coords[0]} {coords[1]}, {coords[2]} {coords[1]}, {coords[2]} {coords[3]}, {coords[0]} {coords[3]}, {coords[0]} {coords[1]}))"
        
        area_sqkm = (coords[2] - coords[0]) * (coords[3] - coords[1]) * 111 * 111  # Rough approximation
        density = grid['population'] / area_sqkm if area_sqkm > 0 else 0
        
        cur.execute("""
            INSERT INTO population_grid 
            (grid_id, state_name, lga_name, population, population_density, settlement_type, source, year, geom)
            VALUES (%s, %s, %s, %s, %s, %s, 'sample_data', 2024, ST_GeomFromText(%s, 4326));
        """, (f'GRID_{i:03d}', grid['state'], grid['lga'], grid['population'], 
              round(density, 2), grid['type'], polygon_wkt))
    
    conn.commit()
    print(f"  ✓ Loaded {len(pop_grids)} population grids")
    cur.close()


def load_sample_facilities(conn):
    """Load sample public facilities"""
    print("\n🏫 Loading public facilities...")
    
    cur = conn.cursor()
    
    facilities = [
        # Lagos
        {'name': 'University of Lagos', 'type': 'university', 'state': 'Lagos', 'coords': [3.4056, 6.5158]},
        {'name': 'Lagos State University', 'type': 'university', 'state': 'Lagos', 'coords': [3.1886, 6.4698]},
        {'name': 'Lagos General Hospital', 'type': 'hospital', 'state': 'Lagos', 'coords': [3.3945, 6.4541]},
        
        # Abuja
        {'name': 'University of Abuja', 'type': 'university', 'state': 'FCT-Abuja', 'coords': [7.3509, 8.9984]},
        {'name': 'National Hospital Abuja', 'type': 'hospital', 'state': 'FCT-Abuja', 'coords': [7.5062, 9.0495]},
        
        # Rivers
        {'name': 'University of Port Harcourt', 'type': 'university', 'state': 'Rivers', 'coords': [7.0114, 4.8993]},
        
        # Kano
        {'name': 'Bayero University', 'type': 'university', 'state': 'Kano', 'coords': [8.5246, 11.9753]},
    ]
    
    for facility in facilities:
        point_wkt = f"POINT({facility['coords'][0]} {facility['coords'][1]})"
        
        cur.execute("""
            INSERT INTO public_facilities 
            (name, facility_type, state_name, source, geom)
            VALUES (%s, %s, %s, 'sample_data', ST_GeomFromText(%s, 4326));
        """, (facility['name'], facility['type'], facility['state'], point_wkt))
    
    conn.commit()
    print(f"  ✓ Loaded {len(facilities)} facilities")
    cur.close()


def create_sample_coverage_analysis(conn):
    """Generate sample coverage analysis"""
    print("\n📊 Generating coverage analysis...")
    
    cur = conn.cursor()
    
    # Calculate coverage for each state
    cur.execute("""
        INSERT INTO coverage_analysis 
        (state_name, total_population, fiber_points, coverage_ratio, geom)
        SELECT 
            ab.state_name,
            ab.population,
            COUNT(fi.id) as fiber_points,
            ROUND((COUNT(fi.id)::numeric / NULLIF(ab.population, 0)) * 1000000, 4) as coverage_ratio,
            ab.geom
        FROM admin_boundaries ab
        LEFT JOIN fiber_infrastructure fi ON ab.state_name = fi.state_name
        WHERE ab.level = 'state'
        GROUP BY ab.state_name, ab.population, ab.geom;
    """)
    
    conn.commit()
    
    # Show results
    cur.execute("""
        SELECT state_name, total_population, fiber_points, 
               ROUND(coverage_ratio, 2) as ratio
        FROM coverage_analysis
        ORDER BY coverage_ratio DESC;
    """)
    
    results = cur.fetchall()
    print("\n  📈 Coverage by State:")
    print(f"  {'State':<15} {'Population':>12} {'Fiber Pts':>10} {'Ratio/1M':>10}")
    print(f"  {'-'*50}")
    for row in results:
        print(f"  {row[0]:<15} {row[1]:>12,} {row[2]:>10} {row[3]:>10}")
    
    cur.close()


def add_metadata(conn):
    """Add data source metadata"""
    print("\n📝 Adding metadata...")
    
    cur = conn.cursor()
    
    sources = [
        ('OSM', 'api', 'OpenStreetMap via Overpass API', 'https://overpass-api.de'),
        ('Sample Data', 'manual', 'Sample data for demo purposes', None),
        ('GRID3', 'file', 'GRID3 Population Data', 'https://grid3.org'),
    ]
    
    for source in sources:
        cur.execute("""
            INSERT INTO data_sources (source_name, source_type, description, url, last_updated, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
            ON CONFLICT (source_name) DO NOTHING;
        """, (source[0], source[1], source[2], source[3], datetime.now()))
    
    conn.commit()
    print(f"  ✓ Added {len(sources)} data sources")
    cur.close()


def main():
    print("="*60)
    print("🗺️  UDIGAP SAMPLE DATA LOADER")
    print("="*60)
    print("\nThis will load sample data to demonstrate UDIGAP capabilities")
    
    try:
        # Connect
        print("\n🔌 Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Connected!")
        
        # Load data
        load_sample_admin_boundaries(conn)
        load_sample_fiber_infrastructure(conn)
        load_sample_population_data(conn)
        load_sample_facilities(conn)
        create_sample_coverage_analysis(conn)
        add_metadata(conn)
        
        print("\n" + "="*60)
        print("✅ SAMPLE DATA LOADED SUCCESSFULLY!")
        print("="*60)
        print("\n📊 Database now contains:")
        
        cur = conn.cursor()
        tables = [
            'admin_boundaries',
            'fiber_infrastructure', 
            'population_grid',
            'public_facilities',
            'coverage_analysis'
        ]
        
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            print(f"  • {table}: {count} records")
        
        print("\n🎯 Next steps:")
        print("  1. Connect QGIS: postgresql://postgres:udigap2024@localhost:5432/udigap")
        print("  2. Query data: psql -d udigap -U postgres")
        print("  3. Build dashboard: streamlit run dashboard/app.py")
        print("  4. Run analysis: python3 etl/analyze_coverage.py")
        
        print("\n💡 Try these queries:")
        print("  SELECT * FROM state_summary;")
        print("  SELECT * FROM coverage_gaps;")
        print("  SELECT * FROM fiber_within_radius(6.5244, 3.3792, 10);")
        print("="*60)
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()