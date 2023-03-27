import sys
sys.path.insert(0, './lib')
from lib.plexapi.server import PlexServer
from utils import servers_file, display_notification

try:
    _machineID, _sectionID, _type, _key = sys.argv[1].split(';')[1:]
except IndexError:
    display_notification('🚨 Error !', 'Something went wrong, please create a GitHub issue')
    query = _machineID = _sectionID = _type = _key = ''


data = servers_file()

for obj in data['items']:
    if obj.get('machineIdentifier') == _machineID:
        baseURL = obj.get('baseURL')
        plexToken = obj.get('plexToken')
        try:
            plex_instance = PlexServer(baseURL, plexToken)
        except:
            display_notification('🚨 Error !', f'Failed to connect to the Plex server \'{obj.get("title")}\'. Check the IP and token')
            exit()
        _list = [plex_instance.library.sectionByID(int(_sectionID)).fetchItem(_key).guids]
        mQUERY = 'm' if _type == 'movie' else 't'
        mGUID = next((guid.id.split('://')[1] for guid in _list[0] if 'tmdb' in guid.id), None)
        print(f'{mQUERY}:{mGUID}', end='')
        break
        