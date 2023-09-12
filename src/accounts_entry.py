import os
import sys
import json
from utils import display_notification, servers_file, accounts_file, addReturnbtn, addMenuBtn, get_plex_account, parse_time

try:
    query = sys.argv[1]
except IndexError:
    query = ''

data = accounts_file()

level = 0
items = []

new_account = {
    'title': 'Connect a new plex account',
    'subtitle': 'Add a plex account and the connected plex media servers',
    'arg': '_new',
    'icon': {
        'path': 'icons/base/new.webp',
    },
}

try:
    accountUUID, level, _type, _key = os.environ['_lib'].split(';')
    level = int(level)
except:
    pass

if data.get('items'):
    if level == 0:
        addMenuBtn(items)
        for elem in [
            new_account,
            {
                'title': 'Remove the access to a plex account',
                'subtitle': 'Remove a plex account and its connected plex media servers',
                'arg': '_rerun;None;1;delete;None',
                'icon': {
                    'path': 'icons/base/delete.webp',
                },
            }
        ]:
            items.append(elem)
        for account in data.get('items'):
            items.append({
                'title': account.get('title'),
                'subtitle': account.get('subtitle'),
                'arg': f'_rerun;{account.get("uuid")};1;account;None',
                'icon': {
                    'path': 'icons/base/person.webp'
                },
            })
    
    else:
        rArg = f'{accountUUID};{level - 1};{_type};{_key}'
        addReturnbtn(rArg, items)

        if level == 1 and _type == 'delete':
                
                for account in data.get('items'):
                    items.append({
                        'title': account.get('title'),
                        'subtitle': account.get('subtitle'),
                        'arg': f'_delete;account;{account.get("uuid")}',
                        'icon': {
                            'path': 'icons/base/person.webp'
                        },
                    })
        else:
            for obj in data['items']:
                if obj.get('uuid') == accountUUID:
                    account_name = obj.get('title')
            try:
                plex_account = get_plex_account(accountUUID)
            except:
                display_notification('🚨 Error !', f'Failed to connect to your plex account {account_name}')
                exit()

            if level == 1:
                items.append({
                    'title': 'Sync',
                    'subtitle': 'Refresh data from your plex account and reconnect your servers',
                    'arg': f'_run;_new;sync;{plex_account.uuid}',
                    'icon': {
                        'path': f'icons/base/refresh.webp',
                    },
                })
                for option in [
                        {
                            'title': 'Servers',
                            'subtitle': 'Plex media servers connected to your account',
                            'type': 'servers'
                        },
                        {
                            'title': 'Users',
                            'subtitle': 'Plex users connected to your account',
                            'type': 'people'
                        },
                        {
                            'title': 'Devices',
                            'subtitle': 'Manage connected devices to your account',
                            'type': 'device'
                        },
                        {
                            'title': 'Watchlist',
                            'subtitle': 'Manage your plex watchlist',
                            'type': 'watchlist'
                        }
                    ]:
                        items.append({
                            'title': option.get('title'),
                            'subtitle': option.get('subtitle'),
                            'arg': f'_rerun;{accountUUID};2;{option.get("type")};None',
                            'icon': {
                                'path': f'icons/base/{option.get("type")}.webp',
                            },
                        })

            elif level == 2:

                if _type == 'servers':
                    for server in plex_account.resources():
                        key = server.accessToken
                        if key:
                            valid = True if key in [s.get('plexToken') for s in servers_file().get('items')] else False
                            items.append({
                                'title': f'{server.name} ({plex_account.title})',
                                'subtitle': f'Device: {server.device} ǀ Version: {server.platformVersion}',
                                'arg': f'_server;{server.clientIdentifier};1;server;None',
                                'valid': valid,
                                'icon': {
                                    'path': 'icons/base/server.webp' if valid else 'icons/base/server_hide.webp'
                                },
                            })

                if _type == 'people':
                    for user in plex_account.users():
                        totalLibAccess = 0
                        for s in user.servers:
                            totalLibAccess += s.numLibraries
                        items.append({
                            'title': user.title,
                            'subtitle': f'Email: {user.email} ǀ {user.title} has access to {totalLibAccess} libraries',
                            'valid': False,
                            'icon': {
                                'path': 'icons/base/person.webp',
                            },
                        })

                elif _type == 'device':
                    for device in plex_account.devices():
                        devices_icons_folder = [file for file in os.listdir(os.path.join(os.getcwd(), 'icons/devices')) if not file.startswith('.') and file != 'plex.webp']
                        check_icons_string = f'{device.name} {device.product} {device.platform} {device.platformVersion}'.lower()
                        min_index = float('inf')
                        device_icon_path = 'icons/devices/plex.webp'
                        for filename in devices_icons_folder:
                            current_index = check_icons_string.find(os.path.splitext(filename)[0])
                            if current_index != -1 and current_index < min_index:
                                min_index = current_index
                                device_icon_path = f'icons/devices/{filename}'
                        items.append({
                            'title': f'{device.name} - {device.platform} {device.platformVersion}',
                            'subtitle': f'Product: {device.product} ǀ Device: {device.device} ǀ Created at: {parse_time(device.createdAt)}',
                            'arg': f'_rerun;{accountUUID};3;device;{device.clientIdentifier}',
                            'icon': {
                                'path': device_icon_path,
                            },
                        })
                elif _type == 'watchlist':
                    for media in plex_account.watchlist(sort='watchlistedAt:desc'):
                        items.append({
                            'title': f'{media.title} ({media.year})',
                            'subtitle': media.type,
                            'valid': False,
                            'icon': {
                                'path': f'icons/base/{media.type}_discover.webp',
                            },
                        })
            
            elif level == 3:

                if _type == 'device':
                    device = plex_account.device(clientId=_key)
                    geoip = plex_account.geoip(device.publicAddress)
                    for e in [
                        {
                            'title': 'Device Name',
                            'subtitle': f'{device.name} - {device.platform} {device.platformVersion}',
                            'valid': False,
                            'icon': {
                                'path': 'icons/base/device.webp',
                            },
                        },
                        {
                            'title': 'Device Location',
                            'subtitle': f'City : {geoip.city} ({geoip.postalCode}), {geoip.subdivisions} ǀ Country : {geoip.country}, Timezone : {geoip.timezone} ',
                            'valid': False,
                            'icon': {
                                'path': 'icons/base/location.webp',
                            },
                        },
                        {
                            'title': 'Google Maps',
                            'subtitle': 'Show the device location on Google Maps',
                            'arg': f'_maps;{",".join(map(str, geoip.coordinates))}',
                            'icon': {
                                'path': 'icons/base/map.webp',
                            },
                        }
                    ]:
                        items.append(e)
else:
    addMenuBtn(items)
    items.append(new_account)
    
print(json.dumps({'items': items}))