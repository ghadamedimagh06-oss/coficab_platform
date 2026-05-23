#!/usr/bin/env python3
"""
Test Script for Option 4: Split Assisté par Workflow de Validation
Tests the complete workflow from detection to decision

Usage:
  python test_split_workflow.py --base-url http://localhost:8000 --token YOUR_TOKEN
"""

import requests
import json
import argparse
from datetime import datetime
import time

BASE_URL = "http://localhost:8000"
TOKEN = None

def set_headers():
    """Generate request headers with auth token"""
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return headers


def test_propose_split(delivery_id=1):
    """
    Test 1: Propose split for an oversized delivery
    POST /api/planning/oversized/{delivery_id}/propose-split
    """
    print(f"\n{'='*60}")
    print(f"TEST 1: Propose split for delivery {delivery_id}")
    print(f"{'='*60}")
    
    url = f"{BASE_URL}/api/planning/oversized/{delivery_id}/propose-split"
    
    try:
        response = requests.post(url, headers=set_headers())
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if data.get("status") == "proposed":
            print(f"✓ Proposal created with audit_id: {data.get('audit_id')}")
            return data.get('proposal'), data.get('audit_id')
        
        return None, None
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return None, None


def test_get_pending_splits():
    """
    Test 2: Get pending splits awaiting decision
    GET /api/planning/oversized/pending
    """
    print(f"\n{'='*60}")
    print(f"TEST 2: Get pending splits")
    print(f"{'='*60}")
    
    url = f"{BASE_URL}/api/planning/oversized/pending"
    
    try:
        response = requests.get(url, headers=set_headers())
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Pending count: {data.get('pending_count')}")
        
        pending_splits = data.get('pending_splits', [])
        for split in pending_splits:
            print(f"  - Delivery #{split['delivery_id']}: {split['quantity']} units, "
                  f"{len(split['proposal']['proposed_sub_deliveries'])} splits")
        
        return pending_splits
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return []


def test_validate_split(delivery_id=1):
    """
    Test 3: Validate split proposal (accept as-is)
    POST /api/planning/oversized/{delivery_id}/decision
    """
    print(f"\n{'='*60}")
    print(f"TEST 3: Validate split for delivery {delivery_id}")
    print(f"{'='*60}")
    
    url = f"{BASE_URL}/api/planning/oversized/{delivery_id}/decision"
    
    decision_payload = {
        "delivery_id": delivery_id,
        "action": "VALIDATE",
        "reason": "Split standard conforme aux contraintes métier"
    }
    
    print(f"Sending decision:")
    print(json.dumps(decision_payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(url, json=decision_payload, headers=set_headers())
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if data.get("status") == "validated":
            print(f"✓ Split VALIDATED! {data.get('sub_deliveries_created')} sub-deliveries created")
            print(f"  Sub-delivery IDs: {data.get('sub_delivery_ids')}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return None


def test_modify_split(delivery_id=2):
    """
    Test 4: Modify split quantities
    POST /api/planning/oversized/{delivery_id}/decision
    """
    print(f"\n{'='*60}")
    print(f"TEST 4: Modify split quantities for delivery {delivery_id}")
    print(f"{'='*60}")
    
    url = f"{BASE_URL}/api/planning/oversized/{delivery_id}/decision"
    
    # Example: 3 splits with modified quantities
    decision_payload = {
        "delivery_id": delivery_id,
        "action": "MODIFY",
        "reason": "Ajustement selon disponibilité véhicules 18T",
        "modified_quantities": [10000, 10000, 8000]  # Sum = 28000
    }
    
    print(f"Sending modified decision:")
    print(json.dumps(decision_payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(url, json=decision_payload, headers=set_headers())
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if data.get("status") == "modified":
            print(f"✓ Split MODIFIED! {data.get('sub_deliveries_created')} sub-deliveries created")
            print(f"  Modified quantities: {data.get('modified_quantities')}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return None


def test_reject_split(delivery_id=3):
    """
    Test 5: Reject split proposal (exceptional transport)
    POST /api/planning/oversized/{delivery_id}/decision
    """
    print(f"\n{'='*60}")
    print(f"TEST 5: Reject split for delivery {delivery_id}")
    print(f"{'='*60}")
    
    url = f"{BASE_URL}/api/planning/oversized/{delivery_id}/decision"
    
    decision_payload = {
        "delivery_id": delivery_id,
        "action": "REJECT",
        "reason": "Localisation spéciale - équipement de déchargement non disponible, location transport spécialisé requise"
    }
    
    print(f"Sending rejection decision:")
    print(json.dumps(decision_payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(url, json=decision_payload, headers=set_headers())
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if data.get("status") == "rejected":
            print(f"✓ Split REJECTED - Exception alert created")
            print(f"  Exception alert ID: {data.get('exception_alert_id')}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return None


def test_get_audit(delivery_id=1):
    """
    Test 6: Get audit trail for a delivery
    GET /api/planning/oversized/{delivery_id}/audit
    """
    print(f"\n{'='*60}")
    print(f"TEST 6: Get audit trail for delivery {delivery_id}")
    print(f"{'='*60}")
    
    url = f"{BASE_URL}/api/planning/oversized/{delivery_id}/audit"
    
    try:
        response = requests.get(url, headers=set_headers())
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Audit records: {data.get('audit_count')}")
        
        for i, audit in enumerate(data.get('audits', []), 1):
            print(f"\nAudit #{i}:")
            print(f"  State: {audit.get('state')}")
            print(f"  Detected: {audit.get('detected_at')}")
            print(f"  Decision: {audit.get('decision_action')} by user {audit.get('decided_by')}")
            print(f"  Reason: {audit.get('decision_reason')}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return None


def run_complete_workflow():
    """Run complete workflow test"""
    print("\n" + "="*60)
    print("OPTION 4: SPLIT ASSISTÉ - COMPLETE WORKFLOW TEST")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Test sequence
    print("\n--- SCENARIO 1: VALIDATE (Accept) ---")
    proposal1, audit_id1 = test_propose_split(delivery_id=1)
    time.sleep(1)
    result1 = test_validate_split(delivery_id=1)
    
    print("\n--- SCENARIO 2: MODIFY (Adjust quantities) ---")
    proposal2, audit_id2 = test_propose_split(delivery_id=2)
    time.sleep(1)
    result2 = test_modify_split(delivery_id=2)
    
    print("\n--- SCENARIO 3: REJECT (Exceptional transport) ---")
    proposal3, audit_id3 = test_propose_split(delivery_id=3)
    time.sleep(1)
    result3 = test_reject_split(delivery_id=3)
    
    # Get pending (should be empty or fewer)
    print("\n--- Check pending splits ---")
    pending = test_get_pending_splits()
    
    # Get audit trails
    print("\n--- Audit trails ---")
    audit1 = test_get_audit(delivery_id=1)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✓ Propose split: {'✓' if proposal1 else '✗'}")
    print(f"✓ Validate split: {'✓' if result1 and result1.get('status') == 'validated' else '✗'}")
    print(f"✓ Modify split: {'✓' if result2 and result2.get('status') == 'modified' else '✗'}")
    print(f"✓ Reject split: {'✓' if result3 and result3.get('status') == 'rejected' else '✗'}")
    print(f"✓ Get pending: {'✓' if isinstance(pending, list) else '✗'}")
    print(f"✓ Get audit: {'✓' if audit1 and audit1.get('audit_count') else '✗'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test Option 4: Split Assisté Workflow"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--token",
        help="Authorization token (JWT)"
    )
    
    args = parser.parse_args()
    BASE_URL = args.base_url
    TOKEN = args.token
    
    run_complete_workflow()
