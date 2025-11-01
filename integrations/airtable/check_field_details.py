"""
Проверка полной информации о полях
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID")

headers = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

url = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"

resp = requests.get(url, headers=headers)
data = resp.json()

for table in data.get('tables', []):
    if table['id'] == AIRTABLE_TABLE_ID:
        print(f"Таблица: {table['name']}\n")
        for field in table.get('fields', []):
            print(f"Поле: {field['name']}")
            print(f"  ID: {field['id']}")
            print(f"  Type: {field.get('type')}")
            print(f"  Compute: {field.get('compute')}")
            print(f"  Full info: {json.dumps(field, indent=2)}")
            print()
