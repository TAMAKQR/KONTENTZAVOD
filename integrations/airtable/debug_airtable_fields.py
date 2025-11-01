"""
Debug script to discover Airtable table fields
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID")

if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID]):
    print("❌ Missing environment variables: AIRTABLE_API_KEY, AIRTABLE_BASE_ID, or AIRTABLE_TABLE_ID")
    exit(1)

headers = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

url = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"

print(f"🔍 Fetching table structure for Base: {AIRTABLE_BASE_ID}")
print(f"   Table ID: {AIRTABLE_TABLE_ID}\n")

try:
    resp = requests.get(url, headers=headers)
    
    if resp.status_code != 200:
        print(f"❌ Error: {resp.status_code}")
        print(f"Response: {resp.text}")
        exit(1)
    
    data = resp.json()
    tables = data.get('tables', [])
    
    target_table = None
    for table in tables:
        if table['id'] == AIRTABLE_TABLE_ID:
            target_table = table
            break
    
    if not target_table:
        print(f"❌ Table {AIRTABLE_TABLE_ID} not found in base")
        print("\nAvailable tables:")
        for table in tables:
            print(f"  - {table['name']} (ID: {table['id']})")
        exit(1)
    
    print(f"✅ Table found: {target_table['name']}\n")
    print("Available fields:")
    print("-" * 50)
    
    fields = target_table.get('fields', [])
    for field in fields:
        print(f"  • {field['name']:<30} Type: {field.get('type', 'unknown')}")
    
    print("\n" + "=" * 50)
    print("Copy these field names to update FIELD_NAMES in airtable_logger.py")
    print("=" * 50)

except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
