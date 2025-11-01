import os
import shutil

airtable_files = [
    'airtable_animation_integration.py',
    'AIRTABLE_EXAMPLE.py',
    'airtable_logger.py',
    'airtable_photo_ai_integration.py',
    'airtable_photo_integration.py',
    'airtable_video_integration.py'
]

for file in airtable_files:
    if os.path.exists(file):
        print(f'Found: {file}')
        shutil.move(file, f'integrations/airtable/{file}')
        print(f'✅ Moved to integrations/airtable/')
    else:
        print(f'Not found: {file}')

print('Done!')
