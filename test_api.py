import requests
import json

print("Testing CofICab Platform API endpoints...\n")

# Test the root endpoint
try:
    response = requests.get('http://127.0.0.1:8001/')
    print('✅ Root endpoint:')
    print(json.dumps(response.json(), indent=2))
    print()
except Exception as e:
    print(f'❌ Error testing root endpoint: {e}')

# Test the health endpoint
try:
    response = requests.get('http://127.0.0.1:8001/api/health')
    print('✅ Health endpoint:')
    print(json.dumps(response.json(), indent=2))
    print()
except Exception as e:
    print(f'❌ Error testing health endpoint: {e}')

# Test KPI endpoint (used by dashboard)
try:
    response = requests.get('http://127.0.0.1:8001/api/metrics/kpi')
    print('✅ KPI endpoint (dashboard):')
    print(json.dumps(response.json(), indent=2))
    print()
except Exception as e:
    print(f'❌ Error testing KPI endpoint: {e}')

# Test live tracking endpoint (used by dashboard)
try:
    response = requests.get('http://127.0.0.1:8001/api/tracking/live')
    print('✅ Live tracking endpoint (dashboard):')
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f'❌ Error testing live tracking endpoint: {e}')

# Test the transports endpoint
try:
    response = requests.get('http://127.0.0.1:8001/api/data/transports')
    print('✅ Transports endpoint:')
    data = response.json()
    print(f"Total transports: {data.get('total', 'N/A')}")
    transports = data.get('transports', [])
    if transports:
        print(f"Sample transport: {transports[0]}")
    else:
        print("No transports found (database empty)")
except Exception as e:
    print(f'❌ Error testing transports endpoint: {e}')

print("\nAPI testing complete!")