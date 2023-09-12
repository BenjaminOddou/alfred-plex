import os
import sys
import json
import secrets
from utils import presets_file, display_notification, presets_file_path

try:
    query = sys.argv[1].split(';')
    _type, _input = query[0], query[1]
except IndexError:
    display_notification('🚨 Error !', 'Something went wrong, please create a GitHub issue')
    exit()

data = presets_file() if presets_file().get('items') else {'items':[]}
if _type == '_delete':
    for item in data['items']:
        if item.get('id') == _input:
            data['items'].remove(item)
            break
elif _type == '_new':
    try:
        value = os.environ['_new_preset']
        title, subtitle = _input.split('/')[0], _input.split('/')[1]
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
elif _type == '_modify':
    try:
        _subtype = os.environ['modif2']
        _key = os.environ['modif5']
        for item in data['items']:
            if item.get('id') == _key:
                title = item.get('title')
                break
        if _subtype == 'tl&sb':
            title, subtitle = _input.split('/')[0], _input.split('/')[1]
            for item in data['items']:
                if item.get('id') == _key:
                    item['title'] = title
                    item['subtitle'] = subtitle
        elif _subtype == 'arg':
            for item in data['items']:
                if item.get('id') == _key:
                    item['arg'] = _input
    except:
        display_notification('🚨 Error !', 'Invalid input')
        exit()

with open(presets_file_path, 'w') as file:
    json.dump(data, file, indent=4)
