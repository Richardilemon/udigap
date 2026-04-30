#!/usr/bin/env python3
"""
Quick debug script to see what MTN API is actually returning
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import json

# Setup Chrome
chrome_options = Options()
# chrome_options.add_argument('--headless')  # Comment out to see browser

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

print("Loading MTN page...")
driver.get("https://apps.mtn.ng/fibre/")

print("Waiting for page to load...")
time.sleep(5)

print("\nTrying to make API call...")

# Try a simple API call and see full response
script = """
var callback = arguments[arguments.length - 1];

fetch('https://apps.mtn.ng/fibre/home/getstateareas', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest'
    },
    body: new URLSearchParams({state_id: '25'})
})
.then(function(response) {
    return response.text();  // Get as text first
})
.then(function(text) {
    console.log('Raw response:', text);
    try {
        var data = JSON.parse(text);
        callback({
            success: true,
            status: data.status,
            message: data.message,
            hasAreas: !!data.areas,
            areasType: typeof data.areas,
            areasValue: data.areas,
            fullResponse: data
        });
    } catch(e) {
        callback({
            success: false,
            error: 'JSON parse error: ' + e.message,
            rawText: text
        });
    }
})
.catch(function(e) {
    callback({
        success: false,
        error: e.message
    });
});
"""

result = driver.execute_async_script(script)

print("\n" + "="*60)
print("RESULT:")
print("="*60)
print(json.dumps(result, indent=2))
print("="*60)

print("\nChecking page source for clues...")
# Check if there are any error messages or redirects on the page
page_text = driver.page_source[:500]
print("Page source (first 500 chars):")
print(page_text)

print("\nChecking browser console logs...")
# Get console logs
logs = driver.get_log('browser')
for log in logs[-10:]:  # Last 10 logs
    print(f"  [{log['level']}] {log['message']}")

print("\nPress Enter to close browser...")
input()

driver.quit()