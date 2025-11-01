import os

files = [
    'src/handlers/video_handler.py',
    'src/handlers/animation_handler.py', 
    'src/handlers/photo_ai_handler.py'
]

for filepath in files:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        updated = content.replace(
            'from workflow_tracker import',
            'from src.workflow_tracker import'
        ).replace(
            'import workflow_tracker',
            'import src.workflow_tracker'
        )
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(updated)
        
        print(f'✅ Updated: {filepath}')
    else:
        print(f'❌ Not found: {filepath}')

print('\n✨ Done!')
