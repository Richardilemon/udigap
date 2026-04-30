#!/usr/bin/env python3
"""
UDIGAP Database Setup Script

Sets up PostGIS database with all required tables.
Works with Docker or local PostgreSQL installation.

Usage:
    python setup_database.py
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

# Database connection settings
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'udigap',
    'user': 'postgres',
    'password': 'udigap2024'
}

def connect_db():
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Docker container is running: docker ps")
        print("2. Check connection: docker exec -it udigap-db psql -U postgres -d udigap")
        sys.exit(1)

def enable_postgis(conn):
    """Enable PostGIS extensions"""
    print("\n📍 Enabling PostGIS extensions...")
    
    cur = conn.cursor()
    
    extensions = [
        "CREATE EXTENSION IF NOT EXISTS postgis;",
        "CREATE EXTENSION IF NOT EXISTS postgis_topology;",
    ]
    
    for ext in extensions:
        try:
            cur.execute(ext)
            conn.commit()
            print(f"  ✓ {ext}")
        except Exception as e:
            print(f"  ⚠️  {ext} - {e}")
    
    # Verify PostGIS
    cur.execute("SELECT PostGIS_version();")
    version = cur.fetchone()
    print(f"\n✅ PostGIS {version[0]} enabled successfully!")
    
    cur.close()

def create_tables(conn):
    """Create all UDIGAP tables"""
    print("\n🏗️  Creating tables...")
    
    cur = conn.cursor()
    
    tables = [
        # Admin Boundaries
        """
        CREATE TABLE IF NOT EXISTS admin_boundaries (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            level VARCHAR(50) NOT NULL,
            state_name VARCHAR(100),
            lga_name VARCHAR(100),
            population BIGINT,
            area_sqkm DECIMAL(10, 2),
            geom GEOMETRY(MultiPolygon, 4326),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        
        # Fiber Infrastructure
        """
        CREATE TABLE IF NOT EXISTS fiber_infrastructure (
            id SERIAL PRIMARY KEY,
            provider VARCHAR(100),
            name VARCHAR(255),
            infrastructure_type VARCHAR(50),
            operator VARCHAR(100),
            status VARCHAR(50) DEFAULT 'active',
            street_name VARCHAR(255),
            area_name VARCHAR(255),
            state_name VARCHAR(100),
            lga_name VARCHAR(100),
            source VARCHAR(100),
            osm_id BIGINT,
            provider_id VARCHAR(100),
            geom GEOMETRY(Geometry, 4326),
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        
        # Population Grid
        """
        CREATE TABLE IF NOT EXISTS population_grid (
            id SERIAL PRIMARY KEY,
            grid_id VARCHAR(50) UNIQUE,
            state_name VARCHAR(100),
            lga_name VARCHAR(100),
            population INTEGER,
            population_density DECIMAL(10, 2),
            settlement_type VARCHAR(50),
            source VARCHAR(100),
            year INTEGER,
            geom GEOMETRY(Polygon, 4326),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        
        # Public Facilities
        """
        CREATE TABLE IF NOT EXISTS public_facilities (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            facility_type VARCHAR(100),
            state_name VARCHAR(100),
            lga_name VARCHAR(100),
            source VARCHAR(100),
            osm_id BIGINT,
            geom GEOMETRY(Point, 4326),
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        
        # Coverage Analysis
        """
        CREATE TABLE IF NOT EXISTS coverage_analysis (
            id SERIAL PRIMARY KEY,
            state_name VARCHAR(100),
            lga_name VARCHAR(100),
            total_population BIGINT,
            fiber_km DECIMAL(10, 2),
            fiber_points INTEGER,
            coverage_ratio DECIMAL(10, 4),
            facilities_within_5km INTEGER,
            facilities_total INTEGER,
            facility_coverage_pct DECIMAL(5, 2),
            analysis_date DATE DEFAULT CURRENT_DATE,
            geom GEOMETRY(MultiPolygon, 4326)
        );
        """,
        
        # Data Sources Metadata
        """
        CREATE TABLE IF NOT EXISTS data_sources (
            id SERIAL PRIMARY KEY,
            source_name VARCHAR(100) UNIQUE,
            source_type VARCHAR(50),
            description TEXT,
            url TEXT,
            last_updated TIMESTAMP,
            update_frequency VARCHAR(50),
            record_count INTEGER,
            status VARCHAR(50) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    ]
    
    for i, table_sql in enumerate(tables, 1):
        try:
            cur.execute(table_sql)
            conn.commit()
            # Extract table name
            table_name = table_sql.split("TABLE IF NOT EXISTS")[1].split("(")[0].strip()
            print(f"  ✓ {i}. {table_name}")
        except Exception as e:
            print(f"  ❌ Table {i} failed: {e}")
    
    cur.close()
    print("\n✅ All tables created successfully!")

def create_indexes(conn):
    """Create spatial indexes"""
    print("\n📊 Creating spatial indexes...")
    
    cur = conn.cursor()
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_admin_geom ON admin_boundaries USING GIST(geom);",
        "CREATE INDEX IF NOT EXISTS idx_fiber_geom ON fiber_infrastructure USING GIST(geom);",
        "CREATE INDEX IF NOT EXISTS idx_pop_geom ON population_grid USING GIST(geom);",
        "CREATE INDEX IF NOT EXISTS idx_facility_geom ON public_facilities USING GIST(geom);",
        "CREATE INDEX IF NOT EXISTS idx_coverage_geom ON coverage_analysis USING GIST(geom);",
        
        "CREATE INDEX IF NOT EXISTS idx_fiber_provider ON fiber_infrastructure(provider);",
        "CREATE INDEX IF NOT EXISTS idx_fiber_state ON fiber_infrastructure(state_name);",
        "CREATE INDEX IF NOT EXISTS idx_admin_state ON admin_boundaries(state_name);",
        "CREATE INDEX IF NOT EXISTS idx_pop_state ON population_grid(state_name);",
    ]
    
    for idx in indexes:
        try:
            cur.execute(idx)
            conn.commit()
            print(f"  ✓ {idx.split('idx_')[1].split(' ')[0]}")
        except Exception as e:
            print(f"  ⚠️  Index creation warning: {e}")
    
    cur.close()
    print("\n✅ Indexes created successfully!")

def create_views(conn):
    """Create useful views"""
    print("\n👁️  Creating views...")
    
    cur = conn.cursor()
    
    # State summary view
    view_sql = """
    CREATE OR REPLACE VIEW state_summary AS
    SELECT
        ab.state_name,
        ab.population,
        COUNT(DISTINCT fi.id) as fiber_features,
        SUM(CASE WHEN ST_GeometryType(fi.geom) = 'ST_LineString'
            THEN ST_Length(fi.geom::geography) / 1000 ELSE 0 END) as fiber_km,
        CASE WHEN ab.population > 0
            THEN COUNT(DISTINCT fi.id)::float / (ab.population / 1000000.0)
            ELSE 0 END as features_per_million,
        ab.geom
    FROM admin_boundaries ab
    LEFT JOIN fiber_infrastructure fi ON ab.state_name = fi.state_name
    WHERE ab.level = 'state'
    GROUP BY ab.state_name, ab.population, ab.geom;
    """
    
    try:
        cur.execute(view_sql)
        conn.commit()
        print("  ✓ state_summary")
    except Exception as e:
        print(f"  ⚠️  View creation warning: {e}")

    coverage_gaps_sql = """
    CREATE OR REPLACE VIEW coverage_gaps AS
    SELECT
        ab.state_name,
        ab.lga_name,
        ab.population,
        COUNT(DISTINCT fi.id) AS fiber_count,
        CASE WHEN ab.population > 0
            THEN COUNT(DISTINCT fi.id)::float / (ab.population / 100000.0)
            ELSE 0 END AS fiber_per_100k,
        CASE
            WHEN COUNT(DISTINCT fi.id) = 0 THEN 'No Coverage'
            WHEN COUNT(DISTINCT fi.id)::float / NULLIF(ab.population, 0) * 100000 < 1 THEN 'Critical Gap'
            WHEN COUNT(DISTINCT fi.id)::float / NULLIF(ab.population, 0) * 100000 < 5 THEN 'Low Coverage'
            ELSE 'Adequate'
        END AS coverage_category
    FROM admin_boundaries ab
    LEFT JOIN fiber_infrastructure fi ON ab.state_name = fi.state_name AND ab.lga_name = fi.lga_name
    WHERE ab.level = 'lga'
    GROUP BY ab.state_name, ab.lga_name, ab.population;
    """
    try:
        cur.execute(coverage_gaps_sql)
        conn.commit()
        print("  ✓ coverage_gaps")
    except Exception as e:
        print(f"  ⚠️  View creation warning: {e}")
    
    cur.close()
    print("\n✅ Views created successfully!")

def verify_setup(conn):
    """Verify database setup"""
    print("\n🔍 Verifying setup...")
    
    cur = conn.cursor()
    
    # Check PostGIS version
    cur.execute("SELECT PostGIS_version();")
    version = cur.fetchone()
    print(f"  ✓ PostGIS: {version[0]}")
    
    # Count tables
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
    """)
    table_count = cur.fetchone()
    print(f"  ✓ Tables: {table_count[0]}")
    
    # List tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = cur.fetchall()
    print(f"\n  📋 Tables created:")
    for table in tables:
        print(f"     • {table[0]}")
    
    cur.close()

def main():
    print("="*60)
    print("🗺️  UDIGAP DATABASE SETUP")
    print("="*60)
    
    # Connect
    print("\n🔌 Connecting to database...")
    conn = connect_db()
    print("✅ Connected successfully!")
    
    try:
        # Setup steps
        enable_postgis(conn)
        create_tables(conn)
        create_indexes(conn)
        create_views(conn)
        verify_setup(conn)
        
        print("\n" + "="*60)
        print("✅ DATABASE SETUP COMPLETE!")
        print("="*60)
        print("\n🎯 Next steps:")
        print("  1. Run: python3 etl/extract_osm_fiber.py")
        print("  2. Load data: python3 etl/load_data.py")
        print("  3. Start dashboard: streamlit run dashboard/app.py")
        print("\n💾 Connection string:")
        print("  postgresql://postgres:udigap2024@localhost:5432/udigap")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()