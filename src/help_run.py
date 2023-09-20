import os
import sys
import json
from utils import display_notification, alias_file, alias_file_path

_action, _categ, _pos, _query = sys.argv[1].split(';')

_res = _query.lower()

if _action in ['delete', 'reset']:
    verb = f'deleted' if _action == 'delete' else _action
    if _res == 'yes':
        if os.path.exists(_pos):
            if os.path.isfile(_pos):
                os.remove(_pos)
            elif os.path.isdir(_pos):
                for filename in os.listdir(_pos):
                    file_path = os.path.join(_pos, filename)
                    if os.path.isfile(file_path) and not filename.endswith(".app"):
                        os.remove(file_path)
            display_notification('✅ Sucess !', f'{_categ.capitalize()} have been {verb}')
            print(f'1;{_categ.split(" ")[0]};0', end='')
        else:
            display_notification('🚨 Error !', f'{_categ.capitalize()} doesn\'t exists or can\'t be {verb}')
    else:
        display_notification('⚠️ Warning !', 'Action canceled')
elif _action == 'modify':
    data = alias_file(_testkey=None, _type=None, _file=True)
    for item in data:
        if item["short_key"] == _query:
            display_notification('🚨 Error !', f'The alias {_query} is already used for {item["long_key"]}')
            print(f'1;alias;0', end='')
            exit()
        else:
            if item["long_key"] == _categ:
                item["short_key"] = _query
    try:
        with open(alias_file_path, 'w') as file:
            json.dump(data, file, indent=4)
        display_notification('✅ Sucess !', f'Alias of {_categ} have been modified to {_query}')
        print(f'1;alias;0', end='')
    except:
        display_notification('🚨 Error !', 'Something went wrong, please create a GitHub issue')


