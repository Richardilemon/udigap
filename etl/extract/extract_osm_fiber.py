#!/usr/bin/env python3
"""
OpenStreetMap Fiber Route Extractor for Nigeria

Extracts fiber optic infrastructure data from OpenStreetMap using Overpass API.
This data is completely open and free to use.

Installation:
    pip install requests geopandas shapely

Usage:
    python extract_osm_fiber.py --output data/raw/osm_fiber_routes.geojson
"""

import requests
import json
import time
import logging
from pathlib import Path
from typing import Dict, List
import argparse
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('osm_fiber_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class OSMFiberExtractor:
    """Extract fiber optic infrastructure from OpenStreetMap"""
    
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    
    # Nigeria bounding box: [min_lat, min_lon, max_lat, max_lon]
    NIGERIA_BBOX = [4.0, 2.5, 14.0, 15.0]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'UDIGAP-Research (richardilupeju@gmail.com)'
        })
    
    def build_query(self, bbox: List[float]) -> str:
        """
        Build Overpass QL query for fiber infrastructure
        
        Args:
            bbox: Bounding box [min_lat, min_lon, max_lat, max_lon]
            
        Returns:
            Overpass QL query string
        """
        # Query for various fiber-related tags
        query = f"""
        [out:json][timeout:180];
        (
          // Fiber optic cables
          way["man_made"="communications_tower"]({{bbox}});
          way["telecom"="fiber_optic"]({{bbox}});
          way["telecom"="line"]({{bbox}});
          way["cable"="fibre_optic"]({{bbox}});
          
          // Telecommunications infrastructure
          node["telecom"="exchange"]({{bbox}});
          node["telecom"="data_center"]({{bbox}});
          node["man_made"="communications_tower"]({{bbox}});
          
          // Internet service providers
          way["operator"~"MTN|Airtel|Glo|9mobile|Spectranet|FibreOne"]({{bbox}});
          node["operator"~"MTN|Airtel|Glo|9mobile|Spectranet|FibreOne"]({{bbox}});
        );
        out geom;
        """
        
        bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
        return query.replace("{bbox}", bbox_str)
    
    def extract_data(self, bbox: List[float] = None) -> Dict:
        """
        Extract fiber data from OSM
        
        Args:
            bbox: Optional custom bounding box, defaults to Nigeria
            
        Returns:
            GeoJSON-like dictionary
        """
        if bbox is None:
            bbox = self.NIGERIA_BBOX
        
        logger.info(f"Querying OSM for fiber data in bbox: {bbox}")
        
        query = self.build_query(bbox)
        
        try:
            logger.info("Sending request to Overpass API...")
            response = self.session.post(
                self.OVERPASS_URL,
                data={'data': query},
                timeout=300
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✓ Received {len(data.get('elements', []))} elements from OSM")
            
            return data
            
        except requests.exceptions.Timeout:
            logger.error("Request timed out. Try a smaller bounding box.")
            return {'elements': []}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {'elements': []}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            return {'elements': []}
    
    def extract_by_states(self, state_bboxes: Dict[str, List[float]]) -> Dict:
        """
        Extract data state-by-state for better performance
        
        Args:
            state_bboxes: Dictionary of state names to bounding boxes
            
        Returns:
            Combined GeoJSON data
        """
        all_elements = []
        
        for state_name, bbox in state_bboxes.items():
            logger.info(f"Extracting {state_name}...")
            data = self.extract_data(bbox)
            
            # Add state info to each element
            for element in data.get('elements', []):
                if 'tags' not in element:
                    element['tags'] = {}
                element['tags']['extracted_state'] = state_name
                all_elements.append(element)
            
            logger.info(f"  → {len(data.get('elements', []))} features from {state_name}")
            time.sleep(2)  # Rate limiting
        
        return {'elements': all_elements}
    
    def convert_to_geojson(self, osm_data: Dict) -> Dict:
        """
        Convert OSM data to GeoJSON format
        
        Args:
            osm_data: Raw OSM Overpass API response
            
        Returns:
            GeoJSON FeatureCollection
        """
        features = []
        
        for element in osm_data.get('elements', []):
            feature = self._element_to_feature(element)
            if feature:
                features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "metadata": {
                "generated": datetime.now().isoformat(),
                "source": "OpenStreetMap",
                "query": "Overpass API",
                "project": "UDIGAP",
                "total_features": len(features)
            },
            "features": features
        }
        
        logger.info(f"✓ Converted to GeoJSON: {len(features)} features")
        return geojson
    
    def _element_to_feature(self, element: Dict) -> Dict:
        """Convert OSM element to GeoJSON feature"""
        elem_type = element.get('type')
        tags = element.get('tags', {})
        
        # Build geometry
        geometry = None
        
        if elem_type == 'node':
            geometry = {
                "type": "Point",
                "coordinates": [element['lon'], element['lat']]
            }
        
        elif elem_type == 'way':
            if 'geometry' in element:
                coords = [[node['lon'], node['lat']] for node in element['geometry']]
                geometry = {
                    "type": "LineString",
                    "coordinates": coords
                }
        
        if not geometry:
            return None
        
        # Build properties
        properties = {
            'osm_id': element.get('id'),
            'osm_type': elem_type,
            'name': tags.get('name', 'Unknown'),
            'operator': tags.get('operator', 'Unknown'),
            'telecom': tags.get('telecom'),
            'man_made': tags.get('man_made'),
            'cable': tags.get('cable'),
            'infrastructure': tags.get('infrastructure'),
            'location': tags.get('location'),
            'extracted_state': tags.get('extracted_state')
        }
        
        # Clean None values
        properties = {k: v for k, v in properties.items() if v is not None}
        
        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": properties
        }


def get_major_state_bboxes() -> Dict[str, List[float]]:
    """Get bounding boxes for major Nigerian states"""
    return {
        'Lagos': [6.4, 3.1, 6.7, 3.7],
        'FCT-Abuja': [8.7, 6.9, 9.3, 7.7],
        'Rivers': [4.5, 6.7, 5.2, 7.2],
        'Kano': [11.5, 8.2, 12.2, 8.8],
        'Oyo': [7.2, 3.5, 8.8, 4.5],
        'Kaduna': [9.8, 7.2, 11.2, 8.0],
        'Enugu': [6.0, 7.2, 7.0, 7.8],
        'Delta': [5.0, 5.5, 6.2, 6.5],
        'Kwara': [8.0, 4.2, 9.5, 5.8],
        'Ogun': [6.5, 2.8, 7.5, 4.0]
    }


def export_geojson(data: Dict, output_path: Path):
    """Export GeoJSON to file"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ Exported to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract fiber optic routes from OpenStreetMap'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/raw/osm_fiber_routes.geojson'),
        help='Output GeoJSON file path'
    )
    parser.add_argument(
        '--full-country',
        action='store_true',
        help='Extract full Nigeria (slower, may timeout)'
    )
    parser.add_argument(
        '--state',
        type=str,
        help='Extract single state only (e.g., "Lagos")'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("OSM FIBER INFRASTRUCTURE EXTRACTOR")
    logger.info("=" * 60)
    
    extractor = OSMFiberExtractor()
    
    # Choose extraction method
    if args.state:
        state_bboxes = get_major_state_bboxes()
        if args.state not in state_bboxes:
            logger.error(f"State '{args.state}' not found. Available: {list(state_bboxes.keys())}")
            return
        
        logger.info(f"Extracting {args.state} only...")
        osm_data = extractor.extract_data(state_bboxes[args.state])
    
    elif args.full_country:
        logger.info("Extracting full Nigeria (this may take 5-10 minutes)...")
        osm_data = extractor.extract_data()
    
    else:
        logger.info("Extracting major states (recommended)...")
        state_bboxes = get_major_state_bboxes()
        osm_data = extractor.extract_by_states(state_bboxes)
    
    # Convert to GeoJSON
    geojson = extractor.convert_to_geojson(osm_data)
    
    # Export
    export_geojson(geojson, args.output)
    
    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total features: {len(geojson['features'])}")
    logger.info(f"Output: {args.output}")
    
    # Feature breakdown
    if geojson['features']:
        points = sum(1 for f in geojson['features'] if f['geometry']['type'] == 'Point')
        lines = sum(1 for f in geojson['features'] if f['geometry']['type'] == 'LineString')
        logger.info(f"Points (towers/exchanges): {points}")
        logger.info(f"Lines (fiber routes): {lines}")
        
        # Operators
        operators = set(f['properties'].get('operator', 'Unknown') 
                       for f in geojson['features'])
        logger.info(f"Operators found: {', '.join(operators)}")
    
    logger.info("=" * 60)
    logger.info("✓ Extraction complete!")
    logger.info("\nNext steps:")
    logger.info("  1. Load into QGIS to visualize")
    logger.info("  2. Import into PostGIS: ogr2ogr -f PostgreSQL ...")
    logger.info("  3. Run transform_data.py to clean and standardize")


if __name__ == "__main__":
    main()