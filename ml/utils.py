#!/usr/bin/env python3
"""
UDIGAP ML Utilities

Common utilities for the ML pipeline.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'udigap',
    'user': 'postgres',
    'password': 'udigap2024'
}


def get_db_connection(dict_cursor=True):
    """Create database connection with optional dict cursor"""
    if dict_cursor:
        return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    return psycopg2.connect(**DB_CONFIG)


def execute_query(query, params=None, fetch=True):
    """Execute a query and optionally fetch results"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(query, params)
        if fetch:
            results = cur.fetchall()
            return [dict(row) for row in results]
        conn.commit()
        return None
    except Exception as e:
        conn.rollback()
        logger.error(f"Query failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def table_exists(table_name):
    """Check if a table exists in the database"""
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = %s
        );
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, (table_name,))
    exists = cur.fetchone()[0]
    cur.close()
    conn.close()
    return exists


def get_model_path():
    """Get the path to the saved model"""
    import os
    return os.path.join(os.path.dirname(__file__), 'models', 'priority_model.pkl')


def get_metrics_path():
    """Get the path to the saved metrics"""
    import os
    return os.path.join(os.path.dirname(__file__), 'models', 'model_metrics.json')


def get_feature_importance_path():
    """Get the path to the saved feature importance"""
    import os
    return os.path.join(os.path.dirname(__file__), 'models', 'feature_importance.json')
