import sys
import webbrowser
sys.path.insert(0, './lib')
from lib.plexapi.server import PlexServer
from utils import servers_file, display_notification, downloads_folder

try:
    query = sys.argv[1].split(';')
    serverID, _type, _key = query[0], query[1], query[2]
except IndexError:
    exit()

data = servers_file()

if data.get('items'):
    for obj in data['items']:
        if obj.get('machineIdentifier') == serverID:
            baseURL = obj.get('baseURL')
            plexToken = obj.get('plexToken')
            friendlyName = obj.get('title')
    try:
        plex_instance = PlexServer(baseURL, plexToken)
        serverName = plex_instance.friendlyName
    except:
        display_notification('🚨 Error !', f'Failed to connect to the Plex server \'{obj.get("title")}\'. Check the IP and token')
        exit()
    try:
        if _type == 'version':
            webbrowser.open(plex_instance.checkForUpdate().downloadURL)
        elif _type == 'logs&databases':
            display_notification('⏳ 1/2 Please wait !', f'Downloading Logs of {serverName}...')
            plex_instance.downloadLogs(savepath=downloads_folder)
            display_notification('⏳ 2/2 Please wait !', f'Downloading Databases of {serverName}...')
            plex_instance.downloadDatabases(savepath=downloads_folder)
            display_notification('✅ Sucess !', f'{serverName} Logs and Databases are located under {downloads_folder}')
        elif _type in ['scan', 'refresh']:
            if _key != 'all':
                libraryName = plex_instance.library.sectionByID(int(_key)).title
                if _type == 'scan':
                    plex_instance.library.sectionByID(int(_key)).update()
                elif _type == 'refresh':
                    plex_instance.library.sectionByID(int(_key)).refresh()
                display_notification('✅ Sucess !', f'{_type.capitalize()} started for {libraryName} on {serverName}')
            else:
                if _type == 'scan':
                    plex_instance.library.update()
                elif _type == 'refresh':
                    plex_instance.library.refresh()
                display_notification('✅ Sucess !', f'{_type.capitalize()} started for all librairies on {serverName}')
    except:
        display_notification('🚨 Error !', 'Internal error')
        exit()