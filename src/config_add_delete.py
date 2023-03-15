import sys
import json
sys.path.insert(0, './lib')
from lib.plexapi.server import PlexServer
from utils import display_notification, servers_file_path, servers_file
from urllib.parse import urlparse, parse_qs

query = sys.argv[1].split(';')[0]

if query == '_delete':
    data = servers_file()
    for item in data['items']:
        if item.get('machineIdentifier') == sys.argv[1].split(';')[1]:
            data['items'].remove(item)
            display_notification('✅ Sucess !', f'The Plex Media Server {item.get("title")} is removed')
            break
else:
    try:
        parsed_url = urlparse(query)        
        baseURL = f'{parsed_url.scheme}://{parsed_url.netloc}'
        plexToken = parse_qs(parsed_url.query).get("X-Plex-Token", [None])[0]
        try:
            plex_instance = PlexServer(baseURL, plexToken)
            data = servers_file() if servers_file() else {'items': []}
            if data.get('items'):
                for obj in data['items']:
                    if obj.get('machineIdentifier') == plex_instance.machineIdentifier:
                        display_notification('⚠️ Warning !', 'Plex Media Server exists already, Plex Token updated')
                        exit()
            json_obj = {
                'title': plex_instance.friendlyName,
                'subtitle': f'{plex_instance.myPlexUsername} ǀ Plex Pass: {plex_instance.myPlexSubscription}',
                'machineIdentifier': plex_instance.machineIdentifier,
                'baseURL': baseURL,
                'plexToken': plexToken,
            }
            data['items'].append(json_obj)
            display_notification('✅ Sucess !', f'The Plex Media Server {plex_instance.friendlyName} is added')
        except:
            display_notification('🚨 Error !', 'Failed to connect to the Plex server. Check the IP and token')
            exit()
    except ValueError:
        display_notification('🚨 Error !', 'Invalid URL format')
        exit()

with open(servers_file_path, 'w') as file:
    json.dump(data, file, indent=4)