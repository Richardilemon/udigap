#!/usr/bin/env python3
"""
MTN Fiber Coverage Selenium Scraper

Uses Selenium to interact with the MTN website like a real browser,
bypassing API restrictions by using the page's own session.

Installation:
    pip install selenium webdriver-manager

Usage:
    python extract_mtn_selenium.py --headless  # Run in background
    python extract_mtn_selenium.py             # Show browser (for debugging)
"""

import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
import argparse
from dataclasses import dataclass, asdict
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mtn_selenium_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class Street:
    """Data model for a street with fiber coverage"""
    street_id: str
    street_name: str
    area_id: str
    area_name: str
    state_id: str
    state_name: str
    active: str


class MTNSeleniumScraper:
    """Scrapes MTN Fiber coverage using Selenium to bypass API restrictions"""
    
    def __init__(self, headless: bool = True):
        """
        Initialize Selenium scraper
        
        Args:
            headless: Run browser in headless mode (no GUI)
        """
        self.headless = headless
        self.driver = None
        self.all_streets = []
        self._setup_driver()
    
    def _setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        logger.info("Setting up Chrome driver...")
        
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # Additional options for stability
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set a realistic user agent
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Enable network interception
        self.driver.execute_cdp_cmd('Network.enable', {})
        
        logger.info("✓ Chrome driver initialized")
    
    def _inject_interceptor(self):
        """Inject JavaScript to intercept API responses"""
        interceptor_script = """
        // Storage for captured data
        window.mtnCapturedData = {
            areas: new Map(),
            streets: [],
            lastCapture: null
        };
        
        // Intercept fetch
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            const response = await originalFetch.apply(this, args);
            const clonedResponse = response.clone();
            
            try {
                const url = args[0];
                
                if (url.includes('getstateareas')) {
                    const data = await clonedResponse.json();
                    if (data.status === 'success' && data.areas) {
                        data.areas.forEach(function(area) {
                            window.mtnCapturedData.areas.set(area.id, area);
                        });
                        window.mtnCapturedData.lastCapture = {
                            type: 'areas',
                            count: data.areas.length,
                            timestamp: Date.now()
                        };
                    }
                }
                
                if (url.includes('getareastreet')) {
                    const data = await clonedResponse.json();
                    if (data.status === 'success' && data.streets) {
                        // Extract area_id from request
                        var areaId = null;
                        if (args[1] && args[1].body) {
                            const formData = args[1].body;
                            if (formData instanceof FormData) {
                                areaId = formData.get('area_id');
                            }
                        }
                        
                        const area = window.mtnCapturedData.areas.get(areaId);
                        
                        data.streets.forEach(function(street) {
                            window.mtnCapturedData.streets.push({
                                street_id: street.id,
                                street_name: street.street_name,
                                area_id: areaId,
                                area_name: area ? area.area_name : 'Unknown',
                                state_id: area ? area.state_id : 'Unknown',
                                active: street.active
                            });
                        });
                        
                        window.mtnCapturedData.lastCapture = {
                            type: 'streets',
                            count: data.streets.length,
                            areaId: areaId,
                            timestamp: Date.now()
                        };
                    }
                }
            } catch (error) {
                console.error('Intercept error:', error);
            }
            
            return response;
        };
        
        // Intercept XMLHttpRequest as backup
        const originalXHR = window.XMLHttpRequest.prototype.open;
        window.XMLHttpRequest.prototype.open = function(method, url) {
            this.addEventListener('load', function() {
                if (url.includes('getstateareas') || url.includes('getareastreet')) {
                    try {
                        const data = JSON.parse(this.responseText);
                        // Similar logic as fetch interception
                    } catch (e) {}
                }
            });
            return originalXHR.apply(this, arguments);
        };
        
        return true;
        """
        
        try:
            result = self.driver.execute_script(interceptor_script)
            logger.info("✓ JavaScript interceptor injected")
            return result
        except Exception as e:
            logger.error(f"Failed to inject interceptor: {e}")
            return False
    
    def _get_captured_data(self) -> Dict:
        """Retrieve captured data from browser"""
        try:
            script = """
            return {
                streets: window.mtnCapturedData?.streets || [],
                areasCount: window.mtnCapturedData?.areas?.size || 0,
                lastCapture: window.mtnCapturedData?.lastCapture
            };
            """
            return self.driver.execute_script(script)
        except Exception as e:
            logger.error(f"Failed to get captured data: {e}")
            return {'streets': [], 'areasCount': 0}
    
    def load_page(self, url: str = "https://apps.mtn.ng/fibre/"):
        """Load the MTN fiber page and inject interceptor"""
        logger.info(f"Loading {url}...")
        self.driver.get(url)
        
        # Wait for page to load
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.info("✓ Page loaded")
            
            # Wait a bit more for dynamic content
            time.sleep(3)
            
            # Inject interceptor
            self._inject_interceptor()
            
            # Wait for interceptor to be ready
            time.sleep(1)
            
            return True
            
        except TimeoutException:
            logger.error("Page load timeout")
            return False
    
    def trigger_state_requests(self, state_ids: List[int]):
        """
        Trigger API requests by programmatically calling the page's functions
        
        Args:
            state_ids: List of state IDs to query
        """
        logger.info(f"Triggering requests for {len(state_ids)} states...")
        
        for state_id in state_ids:
            try:
                # Execute the page's own API call function
                script = f"""
                var callback = arguments[arguments.length - 1];
                fetch('https://apps.mtn.ng/fibre/home/getstateareas', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest'
                    }},
                    body: new URLSearchParams({{state_id: '{state_id}'}})
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    if (data.status === 'success') {{
                        callback({{success: true, areasCount: data.areas ? data.areas.length : 0}});
                    }} else {{
                        callback({{success: false}});
                    }}
                }})
                .catch(function(e) {{
                    callback({{success: false, error: e.message}});
                }});
                """
                
                result = self.driver.execute_async_script(script)
                
                if result.get('success'):
                    logger.info(f"  ✓ State {state_id}: {result.get('areasCount', 0)} areas")
                    
                    # Now get streets for each area
                    data = self._get_captured_data()
                    
                    # Small delay between states
                    time.sleep(2)
                else:
                    logger.warning(f"  ✗ State {state_id}: No data")
                
            except Exception as e:
                logger.error(f"  ✗ State {state_id}: {e}")
            
            time.sleep(1)  # Rate limiting
    
    def trigger_area_streets(self, area_ids: List[str]):
        """
        Trigger street requests for specific areas
        
        Args:
            area_ids: List of area IDs
        """
        logger.info(f"Fetching streets for {len(area_ids)} areas...")
        
        for area_id in area_ids:
            try:
                script = f"""
                var callback = arguments[arguments.length - 1];
                fetch('https://apps.mtn.ng/fibre/home/getareastreet', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest'
                    }},
                    body: new URLSearchParams({{area_id: '{area_id}'}})
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    if (data.status === 'success') {{
                        callback({{success: true, streetsCount: data.streets ? data.streets.length : 0}});
                    }} else {{
                        callback({{success: false}});
                    }}
                }})
                .catch(function(e) {{
                    callback({{success: false, error: e.message}});
                }});
                """
                
                result = self.driver.execute_async_script(script)
                
                if result.get('success'):
                    logger.info(f"  ✓ Area {area_id}: {result.get('streetsCount', 0)} streets")
                else:
                    logger.warning(f"  ✗ Area {area_id}: No data")
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.error(f"  ✗ Area {area_id}: {e}")
    
    def scrape_all(self) -> List[Dict]:
        """
        Complete scraping workflow
        
        Returns:
            List of street dictionaries
        """
        logger.info("Starting Selenium-based scraping...")
        
        # Load page
        if not self.load_page():
            logger.error("Failed to load page")
            return []
        
        # Try all possible state IDs
        state_ids = list(range(1, 38))  # Nigeria's 36 states + FCT
        self.trigger_state_requests(state_ids)
        
        # Get captured data after state requests
        data = self._get_captured_data()
        logger.info(f"Captured {data['areasCount']} unique areas")
        
        # Now get streets for all captured areas
        if data['areasCount'] > 0:
            # Extract area IDs from captured data
            area_ids_script = """
            return Array.from(window.mtnCapturedData.areas.keys());
            """
            area_ids = self.driver.execute_script(area_ids_script)
            
            logger.info(f"Fetching streets for {len(area_ids)} areas...")
            self.trigger_area_streets(area_ids)
        
        # Final data retrieval
        final_data = self._get_captured_data()
        streets = final_data['streets']
        
        logger.info(f"✓ Scraping complete: {len(streets)} streets captured")
        
        return streets
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")


def export_data(streets: List[Dict], output_path: Path):
    """Export scraped data to JSON"""
    output = {
        "metadata": {
            "extracted_at": datetime.now().isoformat(),
            "source": "MTN Nigeria Fiber Coverage API",
            "method": "Selenium Automation",
            "project": "UDIGAP",
            "total_streets": len(streets)
        },
        "streets": streets
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ Data exported to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Scrape MTN Fiber coverage using Selenium'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/mtn_coverage_raw.json'),
        help='Output JSON file path'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (no GUI)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("MTN SELENIUM SCRAPER")
    logger.info("=" * 60)
    
    scraper = None
    try:
        scraper = MTNSeleniumScraper(headless=args.headless)
        streets = scraper.scrape_all()
        
        if streets:
            export_data(streets, args.output)
            
            # Summary
            logger.info("=" * 60)
            logger.info("SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total streets: {len(streets)}")
            logger.info(f"Output: {args.output}")
            logger.info("=" * 60)
        else:
            logger.error("No data captured. Check logs for details.")
    
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    
    finally:
        if scraper:
            scraper.close()


if __name__ == "__main__":
    main()