import sys
import webbrowser
from utils import servers_file, display_notification, downloads_folder, custom_logger
from plexapi.server import PlexServer

try:
    serverID, _type, _key, _msg = sys.argv[1].split(';')
except IndexError as e:
    display_notification('🚨 Error !', 'Something went wrong, check the logs and create a GitHub issue')
    custom_logger('error', e)
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
    except Exception as e:
        display_notification('🚨 Error !', f'Failed to connect to the plex server {obj.get("title")}')
        custom_logger('error', e)
        exit()
    try:
        if _type == 'version':
            webbrowser.open(plex_instance.checkForUpdate().downloadURL)
            custom_logger('info', f'A new plex version was downloaded at {plex_instance.checkForUpdate().downloadURL}')
        elif _type == 'terminateSession':
            plex_instance.query(f'/status/sessions/terminate?sessionId={_key}&reason={_msg}')
            display_notification('✅ Sucess !', 'The session terminated correctly with your message')
            custom_logger('info', f'The session {_key} terminated with the message {_msg}')
        elif _type == 'logs&databases':
            display_notification('⏳ 1/2 Please wait !', f'Downloading {serverName} logs...')
            plex_instance.downloadLogs(savepath=downloads_folder)
            display_notification('⏳ 2/2 Please wait !', f'Downloading {serverName} database...')
            plex_instance.downloadDatabases(savepath=downloads_folder)
            message = f'{serverName} logs and databases are downloaded under {downloads_folder}'
            display_notification('✅ Sucess !', message)
            custom_logger('info', message)
        elif _type in ['scan', 'refresh']:
            if _key != 'all':
                libraryName = plex_instance.library.sectionByID(int(_key)).title
                if _type == 'scan':
                    plex_instance.library.sectionByID(int(_key)).update()
                elif _type == 'refresh':
                    plex_instance.library.sectionByID(int(_key)).refresh()
                message = f'{_type.capitalize()} started for {libraryName} on {serverName}'
                display_notification('✅ Sucess !', message)
                custom_logger('info', message)
            else:
                if _type == 'scan':
                    plex_instance.library.update()
                elif _type == 'refresh':
                    plex_instance.library.refresh()
                message = f'{_type.capitalize()} started for all librairies on {serverName}'
                display_notification('✅ Sucess !', message)
                custom_logger('info', message)
    except Exception as e:
        display_notification('🚨 Error !', 'Something went wrong, check the logs and create a GitHub issue')
        custom_logger('error', e)
        exit()