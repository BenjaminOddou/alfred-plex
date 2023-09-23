import os
import sys
import json
import secrets
from utils import presets_file, display_notification, presets_file_path, custom_logger

try:
    query = sys.argv[1].split(';')
    _type, _input = query[0], query[1]
except IndexError as e:
    display_notification('🚨 Error !', 'Something went wrong, check the logs and create a GitHub issue')
    custom_logger('error', e)
    exit()

data = presets_file() if presets_file().get('items') else {'items':[]}
try:
    if _type == '_delete':
        for item in data['items']:
            if item.get('id') == _input:
                data['items'].remove(item)
                break
    elif _type == '_new':
        value = os.environ['_new_preset']
        title, subtitle = _input.split('/')[0], _input.split('/')[1]
        json_obj = {
            'title': title,
            'subtitle': subtitle,
            'arg': value,
            'id': secrets.token_hex(16)
        }
        data['items'].append(json_obj)
    elif _type == '_modify':
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
except Exception as e:
    display_notification('🚨 Error !', 'Invalid input, check the logs')
    custom_logger('error', e)
    exit()

with open(presets_file_path, 'w') as file:
    json.dump(data, file, indent=4)
