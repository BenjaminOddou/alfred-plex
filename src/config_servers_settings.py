import os
import sys
sys.path.insert(0, './lib')
from lib.plexapi.server import PlexServer
from utils import servers_file, display_notification

serverID = os.environ['split2']
settingID = os.environ['split3']
settingType = os.environ['split4']
old_value = os.environ['split6']

try:
    new_value = eval(sys.argv[1])
except:
    display_notification('🚨 Error !', 'Invalid or empty input, put quotes for text')
    exit()

data = servers_file()

items = []

type_dict = {
    'bool': 'bool',
    'text': 'str',
    'double': 'float',
    'int': 'int'
}

if type_dict.get(settingType) != type(new_value).__name__:
    display_notification('🚨 Error !', f'{type(new_value).__name__} is not compatible to this setting with type {settingType}')
    exit()

if data.get('items'):
    for obj in data['items']:
        if obj.get('machineIdentifier') == serverID:
            baseURL = obj.get('baseURL')
            plexToken = obj.get('plexToken')
            friendlyName = obj.get('title')
    try:
        plex_instance = PlexServer(baseURL, plexToken)
    except:
        display_notification('🚨 Error !', f'Failed to connect to the Plex server \'{obj.get("title")}\'. Check the IP and token')
        exit()
    try:
        plex_instance.settings.get(settingID).set(new_value)
        plex_instance.settings.save()
        display_notification('✅ Success !', f'{settingID} value is now {new_value}')
    except:
        display_notification('🚨 Error !', f'Can\'t attribute {new_value} to {settingID}')
        exit()
else:
    display_notification('🚨 Error !', 'Internal Error')
    exit()