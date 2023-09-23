import os
import sys
from utils import servers_file, display_notification, custom_logger
from plexapi.server import PlexServer

serverID = os.environ['split2']
settingID = os.environ['split3']
settingType = os.environ['split4']
old_value = os.environ['split6']

try:
    new_value = eval(sys.argv[1])
except Exception as e:
    display_notification('🚨 Error !', 'Invalid or empty input, put quotes for text')
    custom_logger('error', e)
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
    message = f'{type(new_value).__name__} is not compatible to this setting with type {settingType}'
    display_notification('🚨 Error !', message)
    custom_logger('error', message)
    exit()

if data.get('items'):
    for obj in data['items']:
        if obj.get('machineIdentifier') == serverID:
            baseURL = obj.get('baseURL')
            plexToken = obj.get('plexToken')
            friendlyName = obj.get('title')
    try:
        plex_instance = PlexServer(baseURL, plexToken)
    except Exception as e:
        display_notification('🚨 Error !', f'Failed to connect to the plex server {obj.get("title")}')
        custom_logger('error', e)
        exit()
    try:
        plex_instance.settings.get(settingID).set(new_value)
        plex_instance.settings.save()
        message = f'{settingID} value is now {new_value}'
        display_notification('✅ Success !', message)
        custom_logger('info', message)
    except Exception as e:
        display_notification('🚨 Error !', f'Can\'t attribute {new_value} to {settingID}')
        custom_logger('error', e)
        exit()
else:
    display_notification('🚨 Error !', 'Something went wrong, check the logs and create a GitHub issue')
    custom_logger('error', 'servers.json has no value or can\'t be reached')
    exit()