import urllib.request
import json

def test_endpoint(url):
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"✅ {url} - Success")
            return data
    except Exception as e:
        print(f"❌ {url} - Error: {e}")
        return None

# Test the data endpoints
print("Testing API endpoints...")

# Test transports endpoint
result = test_endpoint('http://127.0.0.1:8002/api/data/transports')
if result:
    print(f"  Found {result.get('total', 0)} transports")

# Test stats endpoint
result = test_endpoint('http://127.0.0.1:8002/api/data/stats')
if result:
    print(f"  Total livraisons: {result.get('total_livraisons', 0)}")

# Test ingestion history endpoint
result = test_endpoint('http://127.0.0.1:8002/api/data/ingestion-history')
if result:
    print(f"  Found {len(result.get('history', []))} history entries")

print("API testing complete!")