import os
import sys
sys.path.insert(0, './lib')
import json
import math
import pickle
import shutil
import datetime
from plexapi.myplex import MyPlexAccount

data_folder = os.path.expanduser('~/Library/Application Support/Alfred/Workflow Data/com.benjamino.plex')
cache_folder = os.path.expanduser('~/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/com.benjamino.plex')
downloads_folder = os.path.expanduser('~/Downloads')
language = 'en'
sound = 'Submarine'
date_format = '%d-%m-%Y'
filters_bool = True if os.getenv('filters_bool') == '1' else False
default_view = {"sort": "originallyAvailableAt:desc"}
limit_number = 15
days_history = 15
media_player = 'vlc'
short_nested_search = 'arg'
short_web = 'cmd'
short_stream = 'alt'
short_mtvsearch = 'ctrl'

default_list = [
    {
        'title': 'data_folder',
    },
    {
        'title': 'downloads_folder',
    },
    {
        'title': 'language',
    },
    {
        'title': 'sound',
    },
    {
        'title': 'date_format',
    },
    {
        'title': 'default_view',
        'func': eval
    },
    {
        'title': 'limit_number',
        'func': int
    },
    {
        'title': 'days_history',
        'func': int
    },
    {
        'title': 'short_nested_search',
    },
    {
        'title': 'media_player',
    },
    {
        'title': 'short_web',
    },
    {
        'title': 'short_stream',
    },
    {
        'title': 'short_mtvsearch',
    }
]

for obj in default_list:
    try:
        value = os.environ.get(obj['title'])
        if not value and obj['title'] not in ['sound', 'default_view']:
            value = globals()[obj['title']]
        function = obj.get('func')
        globals()[obj['title']] = function(value) if function else value
    except:
        pass

accounts_file_path = os.path.join(data_folder, 'accounts.json') # default = ~/Library/Application Support/Alfred/Workflow Data/com.benjamino.plex/servers.jso
servers_file_path = os.path.join(data_folder, 'servers.json') # default = ~/Library/Application Support/Alfred/Workflow Data/com.benjamino.plex/servers.json
alias_file_path = os.path.join(data_folder, 'alias.json') # default = ~/Library/Application Support/Alfred/Workflow Data/com.benjamino.plex/alias.json
presets_file_path = os.path.join(data_folder, 'presets.json') # default = ~/Library/Application Support/Alfred/Workflow Data/com.benjamino.plex/presets.json

def display_notification(title: str, message: str):
    title = title.replace('"', '\\"')
    message = message.replace('"', '\\"')
    os.system(f'"{os.getcwd()}/notificator" --message "{message}" --title "{title}" --sound "{sound}"')

def parse_time(time: datetime):
    return time.strftime(date_format)

def parse_duration(time):
    total_seconds = divmod(time, 1000)[0]
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'

def history_days():
    return datetime.datetime.today() - datetime.timedelta(days=days_history)

def alias_file(_testkey: str, _type: str, _file=False):
    if not os.path.isfile(alias_file_path) or os.path.getsize(alias_file_path) == 0:
        shutil.copy('./json/alias.json', alias_file_path)
    with open(alias_file_path, 'r') as file:
        data = json.load(file)
        if _file:
            return data
    if _type == 'alias_and_long':
        for obj in data:
            if filters_bool:
                if _testkey == obj['short_key']:
                    return obj['long_key']
            else:
                if _testkey == obj['long_key']:
                    return obj['long_key']
    elif _type == 'alias_or_long':
        if filters_bool:
            for obj in data:
                if obj['long_key'] == _testkey:
                    return obj['short_key']
        else:
            return _testkey
    elif _type == 'alias':
        for obj in data:
                if obj['long_key'] == _testkey:
                    return obj['short_key']
    return None

def accounts_file():
    if os.path.isfile(accounts_file_path) and os.path.getsize(accounts_file_path) > 0:
        with open(accounts_file_path, 'r') as file:
            return json.load(file)
    else:
        return {'items': []}

def servers_file():
    if os.path.isfile(servers_file_path) and os.path.getsize(servers_file_path) > 0:
        with open(servers_file_path, 'r') as file:
            return json.load(file)
    else:
        return {'items': []}
    
def presets_file():
    try:
        if not os.path.isfile(presets_file_path) or os.path.getsize(presets_file_path) == 0:
            shutil.copy('./json/presets.json', presets_file_path)
        with open(presets_file_path, 'r') as file:
            return json.load(file)
    except:
        return {'items': []}

def delist(_action: str, items: list):
    items.append({'skip': _action})

def default_element(_action: str, items: list, query: str=None, query_dict: dict=None):
    if _action == 'no_PMS':
        items.append({
            'title': 'No plex media server detected',
            'subtitle': 'Press ⏎ and sign in to your plex account',
            'arg': '_login',
            'icon': {
                'path': 'icons/base/info.webp',
            },
        })
    elif _action == 'no_ACC':
        items.append({
            'title': f'No plex account connected',
            'subtitle': 'Press ⏎ and sign in to your plex account',
            'arg': '_login',
            'icon': {
                'path': 'icons/base/info.webp',
            },
        })
    elif _action == 'no_ELEM':
        items.append({
            'title': f'No media found for \'{query}\'',
            'subtitle': 'Try to search something else',
            'valid': False,
            'icon': {
                'path': 'icons/base/info.webp',
            },
        })
    elif _action == 'invalid_FILTERS':
        items.append({
            'title': f'No media found for filters={query_dict}',
            'subtitle': f'Press ⏎ to see available options. Aliases are {"activated" if filters_bool else "desactivated"}',
            'arg': '_help',
            'icon': {
                'path': 'icons/base/info.webp',
            },
        })
    elif _action == 'Unauthorized':
        items.append({
            'title': 'Unauthorized action',
            'subtitle': 'Ensure you are connected with the admin account of this server',
            'valid': False,
            'icon': {
                'path': 'icons/base/info.webp',
            },
        })

def addReturnbtn(rArg: str, items: list):
    items.append(
        {
            'title': 'Return',
            'subtitle': 'Back to previous state',
            'arg': f'_rerun;{rArg}',
            'icon': {
                'path': 'icons/base/return.webp',
            },
        }
    )

def addMenuBtn(items: list):
    items.append(
        {
            'title': 'Return',
            'subtitle': 'Back to the Menu',
            'arg': '_rerunMenu',
            'icon': {
                'path': 'icons/base/return.webp',
            },
        }
    )

def get_size_string(size: int, decimals=2):
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, decimals)
    return f"{s} {size_name[i]}"


def get_plex_account(uuid=None, username=None, password=None, otp=None):
    plex_account = None
    auth_token = None

    if plex_account is None:
        try:
            with open(f'{cache_folder}/{uuid}', 'rb') as file:
                plex_account = pickle.load(file)
        except (FileNotFoundError, pickle.UnpicklingError):
            pass

    if plex_account is None:
        for account in accounts_file().get('items'):
            if account.get('uuid') == uuid:
                auth_token = account.get('authToken')
                break
        try:
            if auth_token:
                plex_account = MyPlexAccount(token=auth_token)
            else:
                plex_account = MyPlexAccount(username=username, password=password, code=otp)
        except:
            display_notification('🚨 Error!', 'Failed to connect to your plex account')
            return None
        try:
            if not os.path.exists(cache_folder):
                os.mkdir(cache_folder)
            with open(f'{cache_folder}/{plex_account.uuid}', 'wb') as file:
                pickle.dump(plex_account, file)
        except pickle.PickleError:
            pass

    return plex_account


def lst_idx(lst: list, index: int):
    if 0 <= index < len(lst):
        return lst[index]
    else:
        return None