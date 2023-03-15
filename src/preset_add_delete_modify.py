import os
import sys
import json
import secrets
from utils import presets_file, display_notification, presets_file_path

query = sys.argv[1]
_type = os.environ['split1']
data = presets_file() if presets_file().get('items') else {'items':[]}
if _type == '_delete':
    for item in data['items']:
        if item.get('id') == query:
            data['items'].remove(item)
            display_notification('✅ Sucess !', f'The Preset {item.get("title")} is removed')
            break
elif _type == '_new':
    try:
        value = os.environ['_new_preset']
        title, subtitle = query.split('/')[0], query.split('/')[1]
    except:
        display_notification('🚨 Error !', 'Invalid input')
        exit()
    json_obj = {
        'title': title,
        'subtitle': subtitle,
        'arg': value,
        'id': secrets.token_hex(16)
    }
    data['items'].append(json_obj)
    display_notification('✅ Sucess !', f'The Preset {title} is added')
elif _type == '_modify':
    try:
        _subtype = os.environ['modif2']
        _key = os.environ['modif5']
        for item in data['items']:
            if item.get('id') == _key:
                title = item.get('title')
                break
        if _subtype == 'tl&sb':
            title, subtitle = query.split('/')[0], query.split('/')[1]
            for item in data['items']:
                if item.get('id') == _key:
                    item['title'] = title
                    item['subtitle'] = subtitle
        elif _subtype == 'arg':
            for item in data['items']:
                if item.get('id') == _key:
                    item['arg'] = query
        display_notification('✅ Sucess !', f'The Preset {title} is modified')
    except:
        display_notification('🚨 Error !', 'Invalid input')
        exit()

with open(presets_file_path, 'w') as file:
    json.dump(data, file, indent=4)
