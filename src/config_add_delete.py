import os
import sys
import json
from urllib.parse import urlparse, parse_qs
from utils import display_notification, servers_file_path, servers_file, data_folder
from plexapi.server import PlexServer

try:
    _type, _input = sys.argv[1].split(';')
except IndexError:
    display_notification('🚨 Error !', 'Something went wrong, please create a GitHub issue')
    exit()

if _type == '_delete':
    data = servers_file()
    for item in data['items']:
        if item.get('machineIdentifier') == _input:
            data['items'].remove(item)
            message = f'The Plex Media Server {item.get("title")} is removed'
            break
elif _type == '_new':
    try:
        parsed_url = urlparse(_input)        
        baseURL = f'{parsed_url.scheme}://{parsed_url.netloc}'
        plexToken = parse_qs(parsed_url.query).get("X-Plex-Token", [None])[0]
        try:
            plex_instance = PlexServer(baseURL, plexToken)
            data = servers_file() if servers_file() else {'items': []}
            if data.get('items'):
                for obj in data['items']:
                    if obj.get('machineIdentifier') == plex_instance.machineIdentifier:
                        display_notification('⚠️ Warning !', 'Plex Media Server exists already, delete it then add it again')
                        exit()
            json_obj = {
                'title': plex_instance.friendlyName,
                'subtitle': f'{plex_instance.myPlexUsername} ǀ Plex Pass: {plex_instance.myPlexSubscription}',
                'machineIdentifier': plex_instance.machineIdentifier,
                'baseURL': baseURL,
                'plexToken': plexToken,
            }
            data['items'].append(json_obj)
            message = f'The Plex Media Server {plex_instance.friendlyName} is added'
        except:
            display_notification('🚨 Error !', 'Failed to connect to the Plex server. Check the IP and token')
            exit()
    except ValueError:
        display_notification('🚨 Error !', 'Invalid URL format')
        exit()

if not os.path.exists(data_folder):
    os.makedirs(data_folder)

try:
    with open(servers_file_path, 'w') as file:
        json.dump(data, file, indent=4)
    if message:
        display_notification('✅ Sucess !', message)
except:
    display_notification('🚨 Error !', 'Data can\'t be written in servers.json')