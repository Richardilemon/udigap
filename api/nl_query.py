#!/usr/bin/env python3
"""
UDIGAP Natural Language Query API

Converts natural language questions into SQL queries using LangChain.
Enables non-technical users to explore spatial data.

Installation:
    pip install fastapi uvicorn langchain langchain-community langchain-openai python-dotenv sqlalchemy psycopg2-binary

Usage:
    uvicorn api.nl_query:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="UDIGAP API",
    description="Natural Language to SQL interface and ML Analytics for geospatial queries",
    version="1.0.0"
)

# Import and mount ML endpoints
try:
    from api.ml_endpoints import router as ml_router
    app.include_router(ml_router, prefix="/analytics", tags=["ML Analytics"])
    logger.info("ML endpoints mounted at /analytics")
except ImportError as e:
    logger.warning(f"ML endpoints not available: {e}")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'udigap',
    'user': 'postgres',
    'password': 'udigap2024'
}

# Request/Response models
class NLQueryRequest(BaseModel):
    question: str
    
class NLQueryResponse(BaseModel):
    question: str
    sql_query: str
    results: List[Dict[str, Any]]
    result_count: int
    execution_time_ms: float
    interpretation: str

# Database helper
def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

# Schema information for LLM context
DATABASE_SCHEMA = """
Database Schema:

1. fiber_infrastructure
   - id: integer (primary key)
   - provider: varchar (MTN, Airtel, Glo, etc.)
   - name: varchar (site name)
   - infrastructure_type: varchar (tower, exchange, data_center, fiber_route)
   - operator: varchar
   - state_name: varchar
   - lga_name: varchar
   - geom: geometry (Point or LineString)
   
2. admin_boundaries
   - id: integer
   - name: varchar (boundary name)
   - level: varchar (state, lga, ward)
   - state_name: varchar
   - population: bigint
   - area_sqkm: decimal
   - geom: geometry (MultiPolygon)

3. population_grid
   - id: integer
   - state_name: varchar
   - lga_name: varchar
   - population: integer
   - population_density: decimal
   - settlement_type: varchar (urban, rural, peri-urban)

4. coverage_analysis
   - state_name: varchar
   - total_population: bigint
   - fiber_points: integer
   - coverage_ratio: decimal (fiber points per million population)
   - fiber_km: decimal

Views:
- state_summary: Aggregated state-level statistics
- coverage_gaps: LGA-level coverage analysis with categories
"""

# Query templates for common questions
QUERY_TEMPLATES = {
    "states_lowest_coverage": """
        SELECT state_name, total_population, fiber_points, 
               ROUND(coverage_ratio::numeric, 2) as coverage_ratio
        FROM coverage_analysis
        ORDER BY coverage_ratio ASC
        LIMIT {limit};
    """,
    
    "states_highest_coverage": """
        SELECT state_name, total_population, fiber_points,
               ROUND(coverage_ratio::numeric, 2) as coverage_ratio
        FROM coverage_analysis
        ORDER BY coverage_ratio DESC
        LIMIT {limit};
    """,
    
    "infrastructure_by_operator": """
        SELECT operator, infrastructure_type, COUNT(*) as count
        FROM fiber_infrastructure
        GROUP BY operator, infrastructure_type
        ORDER BY count DESC;
    """,
    
    "coverage_in_state": """
        SELECT state_name, total_population, fiber_points, 
               ROUND(coverage_ratio::numeric, 2) as coverage_ratio,
               ROUND(COALESCE(fiber_km, 0)::numeric, 2) as fiber_km
        FROM coverage_analysis
        WHERE LOWER(state_name) LIKE LOWER('%{state}%')
        LIMIT 1;
    """,
    
    "infrastructure_count_by_state": """
        SELECT state_name, COUNT(*) as infrastructure_count,
               COUNT(DISTINCT provider) as provider_count
        FROM fiber_infrastructure
        GROUP BY state_name
        ORDER BY infrastructure_count DESC
        LIMIT {limit};
    """,
    
    "fiber_within_distance": """
        SELECT name, operator, infrastructure_type,
               ROUND(ST_Distance(
                   geom::geography,
                   ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography
               ) / 1000) as distance_km
        FROM fiber_infrastructure
        WHERE ST_DWithin(
            geom::geography,
            ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography,
            {radius} * 1000
        )
        ORDER BY distance_km
        LIMIT {limit};
    """,
    
    "population_vs_coverage": """
        SELECT state_name, total_population, fiber_points,
               ROUND(coverage_ratio::numeric, 2) as coverage_ratio,
               CASE 
                   WHEN coverage_ratio < 10 THEN 'Very Low'
                   WHEN coverage_ratio < 50 THEN 'Low'
                   WHEN coverage_ratio < 100 THEN 'Medium'
                   ELSE 'High'
               END as coverage_category
        FROM coverage_analysis
        ORDER BY total_population DESC;
    """
}

class NLQueryEngine:
    """Natural Language to SQL query engine"""
    
    def __init__(self):
        self.schema = DATABASE_SCHEMA
        self.templates = QUERY_TEMPLATES
    
    def parse_question(self, question: str) -> Dict[str, Any]:
        """Parse natural language question and generate SQL"""
        
        question_lower = question.lower()
        
        # Pattern matching for common queries
        patterns = [
            # Coverage queries
            {
                "patterns": ["lowest coverage", "worst coverage", "least coverage", "poorest coverage"],
                "template": "states_lowest_coverage",
                "params": {"limit": self._extract_limit(question, default=10)},
                "interpretation": "States with lowest fiber infrastructure coverage per capita"
            },
            {
                "patterns": ["highest coverage", "best coverage", "most coverage", "top coverage"],
                "template": "states_highest_coverage",
                "params": {"limit": self._extract_limit(question, default=10)},
                "interpretation": "States with highest fiber infrastructure coverage per capita"
            },
            
            # State-specific queries
            {
                "patterns": ["coverage in", "coverage for", "how much coverage"],
                "template": "coverage_in_state",
                "params": {"state": self._extract_state(question)},
                "interpretation": f"Coverage statistics for {self._extract_state(question)}"
            },
            
            # Operator queries
            {
                "patterns": ["by operator", "by provider", "operator", "provider"],
                "template": "infrastructure_by_operator",
                "params": {},
                "interpretation": "Infrastructure distribution by telecom operator"
            },
            
            # Infrastructure count
            {
                "patterns": ["infrastructure count", "how many", "count"],
                "template": "infrastructure_count_by_state",
                "params": {"limit": self._extract_limit(question, default=10)},
                "interpretation": "Infrastructure count by state"
            },
            
            # Population vs coverage
            {
                "patterns": ["population", "vs coverage", "compared to population"],
                "template": "population_vs_coverage",
                "params": {},
                "interpretation": "Population vs infrastructure coverage analysis"
            },
            
            # Proximity queries
            {
                "patterns": ["near", "within", "around", "close to"],
                "template": "fiber_within_distance",
                "params": {
                    "lat": self._extract_coordinate(question, "lat"),
                    "lon": self._extract_coordinate(question, "lon"),
                    "radius": self._extract_radius(question),
                    "limit": self._extract_limit(question, default=20)
                },
                "interpretation": "Fiber infrastructure within specified distance"
            }
        ]
        
        # Find matching pattern
        for pattern_group in patterns:
            if any(pattern in question_lower for pattern in pattern_group["patterns"]):
                template_name = pattern_group["template"]
                params = pattern_group["params"]
                interpretation = pattern_group["interpretation"]
                
                # Generate SQL from template
                sql = self.templates[template_name].format(**params)
                
                return {
                    "sql": sql.strip(),
                    "interpretation": interpretation,
                    "matched_pattern": template_name
                }
        
        # Fallback: Generic query
        return self._generate_fallback_query(question)
    
    def _extract_limit(self, question: str, default: int = 10) -> int:
        """Extract result limit from question"""
        import re
        
        # Look for numbers
        numbers = re.findall(r'\b(\d+)\b', question)
        if numbers:
            return int(numbers[0])
        
        # Look for "top N" or "first N"
        top_match = re.search(r'top (\d+)|first (\d+)', question.lower())
        if top_match:
            return int(top_match.group(1) or top_match.group(2))
        
        return default
    
    def _extract_state(self, question: str) -> str:
        """Extract state name from question"""
        import re
        
        # Nigerian states
        states = [
            'Lagos', 'Kano', 'Rivers', 'Kaduna', 'Oyo', 'FCT', 'Abuja',
            'Anambra', 'Delta', 'Ogun', 'Edo', 'Kwara', 'Enugu', 'Bauchi'
        ]
        
        question_lower = question.lower()
        for state in states:
            if state.lower() in question_lower:
                return state
        
        # Try to extract word after "in" or "for"
        match = re.search(r'(?:in|for)\s+(\w+)', question_lower)
        if match:
            return match.group(1).title()
        
        return "Lagos"  # Default
    
    def _extract_coordinate(self, question: str, coord_type: str) -> float:
        """Extract latitude or longitude from question"""
        import re
        
        # Look for coordinate patterns
        coords = re.findall(r'-?\d+\.\d+', question)
        
        if len(coords) >= 2:
            if coord_type == "lat":
                return float(coords[0])
            else:
                return float(coords[1])
        
        # Default to Lagos coordinates
        return 6.5244 if coord_type == "lat" else 3.3792
    
    def _extract_radius(self, question: str) -> float:
        """Extract search radius from question"""
        import re
        
        # Look for "within X km"
        match = re.search(r'within (\d+)\s*k', question.lower())
        if match:
            return float(match.group(1))
        
        return 10.0  # Default 10km
    
    def _generate_fallback_query(self, question: str) -> Dict[str, Any]:
        """Generate a safe fallback query"""
        
        return {
            "sql": """
                SELECT state_name, total_population, fiber_points,
                       ROUND(coverage_ratio::numeric, 2) as coverage_ratio
                FROM coverage_analysis
                ORDER BY coverage_ratio DESC
                LIMIT 5;
            """.strip(),
            "interpretation": "Top 5 states by coverage (default query - try being more specific!)",
            "matched_pattern": "fallback"
        }

# Initialize query engine
query_engine = NLQueryEngine()

@app.get("/")
def root():
    """API root endpoint"""
    return {
        "name": "UDIGAP Natural Language Query API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "query": "/query",
            "examples": "/examples",
            "schema": "/schema"
        }
    }

@app.get("/examples")
def get_examples():
    """Get example queries"""
    return {
        "examples": [
            "Which states have the lowest coverage?",
            "Show me the top 5 states with highest coverage",
            "What is the coverage in Lagos?",
            "How many infrastructure points does each operator have?",
            "Show infrastructure count by state",
            "Compare population and coverage across states",
            "Find fiber infrastructure within 10km of 6.5244, 3.3792"
        ]
    }

@app.get("/schema")
def get_schema():
    """Get database schema information"""
    return {
        "schema": DATABASE_SCHEMA,
        "tables": ["fiber_infrastructure", "admin_boundaries", "population_grid", "coverage_analysis"],
        "views": ["state_summary", "coverage_gaps"]
    }

@app.post("/query", response_model=NLQueryResponse)
async def query_natural_language(request: NLQueryRequest):
    """
    Process natural language query and return results
    
    Example:
        POST /query
        {
            "question": "Which states have the lowest coverage?"
        }
    """
    
    start_time = datetime.now()
    
    try:
        # Parse question and generate SQL
        parsed = query_engine.parse_question(request.question)
        sql_query = parsed["sql"]
        interpretation = parsed["interpretation"]
        
        logger.info(f"Question: {request.question}")
        logger.info(f"Generated SQL: {sql_query}")
        
        # Execute query
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(sql_query)
        results = cur.fetchall()
        
        # Convert to list of dicts
        results_list = [dict(row) for row in results]
        
        cur.close()
        conn.close()
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return NLQueryResponse(
            question=request.question,
            sql_query=sql_query,
            results=results_list,
            result_count=len(results_list),
            execution_time_ms=round(execution_time, 2),
            interpretation=interpretation
        )
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "question": request.question,
                "tip": "Try rephrasing your question or use /examples to see sample queries"
            }
        )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)