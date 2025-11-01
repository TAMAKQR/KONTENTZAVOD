"""
Debug script to check all configured Airtable tables
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

tables_to_check = {
    "MAIN": os.getenv("AIRTABLE_TABLE_ID"),
    "VIDEO": os.getenv("AIRTABLE_VIDEO_TABLE_ID"),
    "ANIMATION": os.getenv("AIRTABLE_ANIMATION_TABLE_ID"),
    "PHOTO": os.getenv("AIRTABLE_PHOTO_TABLE_ID"),
    "AI_PHOTO": os.getenv("AIRTABLE_AI_PHOTO_TABLE_ID"),
}

if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID]):
    print("❌ Missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID")
    exit(1)

headers = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

url = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"

print("🔍 Проверка всех настроенных таблиц...\n")

try:
    resp = requests.get(url, headers=headers)
    
    if resp.status_code != 200:
        print(f"❌ Error: {resp.status_code}")
        print(f"Response: {resp.text}")
        exit(1)
    
    data = resp.json()
    tables = {table['id']: table for table in data.get('tables', [])}
    
    for table_type, table_id in tables_to_check.items():
        if not table_id:
            print(f"⚠️  {table_type}: не настроена (переменная окружения пуста)")
            continue
        
        if table_id not in tables:
            print(f"❌ {table_type} ({table_id}): не найдена")
            continue
        
        table = tables[table_id]
        print(f"✅ {table_type}: {table['name']}")
        print(f"   ID: {table_id}")
        print(f"   Поля:")
        for field in table.get('fields', []):
            print(f"     • {field['name']:<30} ({field.get('type', 'unknown')})")
        print()

except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
