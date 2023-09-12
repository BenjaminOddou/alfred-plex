import os
import sys
import json
import time
from utils import display_notification, servers_file_path, servers_file, data_folder, get_plex_account

try:
    _type, _origin, _input = sys.argv[1].split(';')
except IndexError:
    display_notification('🚨 Error !', 'Something went wrong, please create a GitHub issue')
    exit()

if _type == '_delete':
    data = servers_file()
    element = 'machineIdentifier' if _origin == 'server' else 'account_uuid'
    items_to_remove = []
    for item in data['items']:
        if item.get(element) == _input:
            items_to_remove.append(item)
    for item in items_to_remove:
        data['items'].remove(item)
        time.sleep(0.5)
        display_notification('✅ Success !', f'The plex server {item.get("title")} is removed')
elif _type == '_new':
    plex_account = get_plex_account(uuid=_input)
    data = servers_file() if servers_file() else {'items': []}
    for s in plex_account.resources():
        if not s.accessToken:
            continue
        try:
            baseURL = s.connect(timeout=2)._baseurl
        except:
            display_notification('🚨 Error !', f'Failed to connect to the plex server {s.name}')
            continue
        replace = False
        json_obj = {
            'title': f'{s.name} ({plex_account.title})',
            'subtitle': f'Device: {s.device} ǀ Version: {s.platformVersion}',
            'machineIdentifier': s.clientIdentifier,
            'baseURL': baseURL,
            'plexToken': s.accessToken,
            'account_uuid': plex_account.uuid,
            'owner': s.owned
        }
        if data.get('items'):
            for idx, obj in enumerate(data['items']):
                if obj.get('machineIdentifier') == s.clientIdentifier:
                    replace = True
                    data['items'][idx] = json_obj
                    display_notification('✅ Sucess !', f'The plex server {s.name} informations were updated')
                    break
        if not replace:
            data['items'].append(json_obj)
            display_notification('✅ Sucess !', f'The plex server {s.name} is added')

if not os.path.exists(data_folder):
    os.makedirs(data_folder)

try:
    with open(servers_file_path, 'w') as file:
        json.dump(data, file, indent=4)
except:
    display_notification('🚨 Error !', 'Data can\'t be written in servers.json')