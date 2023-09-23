import os
import sys
import json
from utils import presets_file, filters_bool, alias_file, display_notification, addReturnbtn, addMenuBtn, custom_logger

try:
    query = sys.argv[1]
except IndexError:
    query = ''

data = presets_file()

level = 0

if os.getenv('_lib'):
    level, _type, _key = os.environ['_lib'].split(';')
    level = int(level)
else:
    pass

items = []

if level == 0:
    addMenuBtn(items)
    for elem in [
        {
            'title': 'Add a new preset',
            'subtitle': 'Create a new preset with custom filters and/or sorts',
            'arg': '_new',
            'icon': {
                'path': 'icons/base/new.webp',
            },
        },
        {
            'title': 'Delete a preset',
            'subtitle': 'Erase a preset from the list below',
            'arg': '_rerun;1;delete;None',
            'icon': {
                'path': 'icons/base/delete.webp',
            },
        }
    ]:
        items.append(elem)
    for preset in data.get('items'):
        p_valid = True
        title = preset.get('title')
        subtitle = preset.get('subtitle')
        arg = preset.get('arg')
        nArg = '_search;0;'
        if not filters_bool:
            nArg += arg
        else:
            for param in arg.split('/'):
                try:
                    key, value = param.split('=', 1)
                except:
                    key, value = ['None', 'None']
                    pass
                test_key = alias_file(_testkey=key, _type='alias')
                if not test_key:
                    p_valid = False
                    custom_logger('warning', f'Key : {key} is not valid in the preset : {title}')
                    test_key = key
                nArg += f'{test_key}={value}/'
            nArg = nArg[:-1]
            if p_valid is False:
                display_notification('⚠️ Warning !', f'The preset {title} has invalid parameters')
        items.append({
            'title': title,
            'subtitle': subtitle,
            'arg': nArg,
            'icon': {
                'path': 'icons/base/preset.webp',
            },
            'mods': {
                'cmd': {
                    'subtitle': 'Press ⏎ to modify the preset',
                    'arg': f'_rerun;1;modify;{preset.get("id")}',
                    'icon': {
                        'path': 'icons/base/modify.webp',
                    },
                }
            }
        })
else:
    rArg = f'{level - 1};{_type};{_key}'
    addReturnbtn(rArg, items)
    if level == 1:
        if _type == 'delete':
            for preset in data.get('items'):
                items.append({
                    'title': preset.get('title'),
                    'subtitle': preset.get('subtitle'),
                    'arg': f'_delete;{preset.get("id")}',
                    'icon': {
                        'path': 'icons/base/preset.webp'
                    },
                })
        if _type == 'modify':
            for preset in data.get('items'):
                if _key == preset.get('id'):
                    title = preset.get('title')
                    subtitle = preset.get('subtitle')
                    value = preset.get('arg')
                    titlesub = f'{title}/{subtitle}'
                    break
            for elem in [
                {
                    'title': 'Modify the Preset\'s Title/Subtitle',
                    'subtitle': f'Current Title: {title} ǀ Current Subtitle: {subtitle}',
                    'arg': f'_modify;tl&sb;Title and/or Subtitle;{titlesub};{_key}',
                    'icon': {
                        'path': 'icons/base/preset.webp'
                    },
                },
                {
                    'title': 'Modify the Preset\'s Value',
                    'subtitle': f'Current Value: {value}',
                    'arg': f'_modify;arg;Value;{value};{_key}',
                    'icon': {
                        'path': 'icons/base/preset.webp'
                    },
                }
            ]:
                items.append(elem)

print(json.dumps({'items': items}))