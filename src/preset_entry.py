import os
import sys
import time
import json
from utils import presets_file, filters_bool, aliases_file, display_notification, addReturnbtn, default_element

query = sys.argv[1]

data = presets_file()

level = 0

if '_lib' in os.environ:
    _lib_list = os.environ['_lib'].split(';')
    level, _type, _key = int(_lib_list[0]), _lib_list[1], _lib_list[2]
else:
    pass

items = [
    {
        'title': 'Add a new preset',
        'subtitle': 'Create a new preset with custom filters and/or sorts',
        'arg': '_new',
        'icon': {
            'path': 'icons/new.webp',
        },
    },
]

if data.get('items'):
    if level == 0:
        items.append({
            'title': 'Delete a preset',
            'subtitle': 'Erase a preset from the list below',
            'arg': '_rerun;1;delete;None',
            'icon': {
                'path': 'icons/delete.webp',
            },
        })
        for preset in data.get('items'):
            title = preset.get('title')
            subtitle = preset.get('subtitle')
            arg = preset.get('arg')
            nArg = '_search;'
            if not filters_bool:
                nArg += arg
            else:
                for param in arg.split('/'):
                    try:
                        key, value = param.split('=', 1)
                    except:
                        key, value = ['None', 'None']
                        pass
                    test_key = aliases_file(key, 'alias')
                    if not test_key:
                        display_notification('⚠️ Warning !', f'The preset {title} has invalid parameters')
                        time.sleep(0.2)
                        break
                    nArg += f'{test_key}={value}/'
                nArg = nArg[:-1]
            items.append({
                'title': title,
                'subtitle': subtitle,
                'arg': nArg,
                'icon': {
                    'path': 'icons/preset.webp',
                },
                'mods': {
                    'cmd': {
                        'subtitle': 'Press ⏎ to modify the preset',
                        'arg': f'_rerun;1;modify;{preset.get("id")}',
                    }
                }
            })
    else:
        items = []
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
                            'path': 'icons/preset.webp'
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
                            'path': 'icons/preset.webp'
                        },
                    },
                    {
                        'title': 'Modify the Preset\'s Value',
                        'subtitle': f'Current Value: {value}',
                        'arg': f'_modify;arg;Value;{value};{_key}',
                        'icon': {
                            'path': 'icons/preset.webp'
                        },
                    }
                ]:
                    items.append(elem)
else:
    items = []
    default_element('no_PMS', items)

filtered_items = [item for item in items if query.lower() in item['title'].lower() or query.lower() in item['subtitle'].lower()]

output = {
    'items': filtered_items
}

print(json.dumps(output))