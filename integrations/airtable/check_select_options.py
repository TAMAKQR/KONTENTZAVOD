"""
Проверка допустимых опций для select полей
"""
import os
import requests
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
            if field.get('type') == 'singleSelect':
                print(f"📋 {field['name']}:")
                for option in field.get('options', {}).get('choices', []):
                    print(f"   - {option['name']}")
                print()
