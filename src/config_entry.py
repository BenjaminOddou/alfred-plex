import os
import sys
import json
from utils import display_notification, servers_file, addReturnbtn, parse_time, parse_duration, get_size_string, history_days, default_element
from plexapi.server import PlexServer

def makeHistory(h, lName):
    if h.type == 'movie':
        hName = f'{h.title} ({h.originallyAvailableAt.year})'
    elif h.type == 'episode':
        hName = f'{h.grandparentTitle} ǀ {h.title} ǀ {h.seasonEpisode}'
    elif h.type == 'track':
        hName = f'{h.grandparentTitle} ǀ {h.title} ({h.album().year})'
    else:
        hName = h.title
    items.append({
        'title': hName,
        'subtitle': f'{friendlyName} ǀ {lName} ǀ {h.type} ǀ {parse_time(h.viewedAt)} ǀ {plex_instance.systemAccount(h.accountID).name} ǀ {plex_instance.systemDevice(h.deviceID).name}, {plex_instance.systemDevice(h.deviceID).platform}',
        'valid': False,
        'icon': {
            'path': 'icons/history.webp',
        }
    })

try:
    query = sys.argv[1]
except IndexError:
    query = ''

data = servers_file()

items = [
    {
        'title': 'Add a new plex media server',
        'subtitle': 'Connect a new plex media server to the workflow',
        'arg': '_new',
        'icon': {
            'path': 'icons/new.webp',
        },
    },
]

level = 0

try:
    serverID, level, _type, _key = os.environ['_lib'].split(';')
    level = int(level)
except:
    pass

if data.get('items'):
    if level == 0:
        items.append({
            'title': 'Remove the access to a server',
            'subtitle': 'Remove the access of this workflow to the plex media server',
            'arg': '_rerun;None;1;delete;None',
            'icon': {
                'path': 'icons/delete.webp',
            },
        })
        for server in data.get('items'):
            items.append({
                'title': server.get('title'),
                'subtitle': server.get('subtitle'),
                'arg': f'_rerun;{server.get("machineIdentifier")};1;server;None',
                'icon': {
                    'path': 'icons/server.webp'
                },
            })
    else:
        items = []
        rArg = f'{serverID};{level - 1};{_type};{_key}'
        addReturnbtn(rArg, items)

        if level == 1 and _type == 'delete':
                
                for server in data.get('items'):
                    items.append({
                        'title': server.get('title'),
                        'subtitle': server.get('subtitle'),
                        'arg': f'_delete;{server.get("machineIdentifier")}',
                        'icon': {
                            'path': 'icons/server.webp'
                        },
                    })
                    
        else:

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

            if level == 1:

                sTitle = 'Your server is up to date'
                sSubtitle = f'Actual version: {plex_instance.version}'
                sArg = None
                sVersionType = 'ok'
                try:
                    if not plex_instance.isLatest():
                        sTitle = 'Update to the latest version'
                        sSubtitle += f' -> New version: {plex_instance.checkForUpdate().version}'
                        sArg = f'_run;{serverID};version;None'
                        sVersionType = 'update'
                    for elem in [
                        {
                            'title': sTitle,
                            'subtitle': sSubtitle,
                            'arg': sArg,
                            'valid': False if sArg is None else True,
                            'icon': {
                                'path': f'icons/{sVersionType}.webp',
                            },
                        },
                        {
                            'title': 'Download logs and databases',
                            'subtitle': 'Backup your plex media server logs and databases',
                            'arg': f'_run;{serverID};logs&databases;None',
                            'icon': {
                                'path': 'icons/download.webp',
                            },
                        },
                    ]: 
                        items.append(elem)
                    for option in [
                        {
                            'title': 'Accounts',
                            'subtitle': 'List of connected accounts to this server',
                            'type': 'person'
                        },
                        {
                            'title': 'Devices',
                            'subtitle': 'List of connected devices to this server',
                            'type': 'device'
                        },
                        {
                            'title': 'Sessions',
                            'subtitle': 'List of running sessions on this server',
                            'type': 'watch'
                        },
                        {
                            'title': 'Library Sections',
                            'subtitle': 'Perform actions and show statistics of server library sections',
                            'type': 'library'
                        },
                        {
                            'title': 'Settings',
                            'subtitle': 'Modify your plex media server settings',
                            'type': 'setting'
                        },
                    ]:
                        items.append({
                            'title': option.get('title'),
                            'subtitle': option.get('subtitle'),
                            'arg': f'_rerun;{serverID};{level + 1};{option.get("type")};group',
                            'icon': {
                                'path': f'icons/{option.get("type")}.webp',
                            },
                        })
                except:
                    default_element('Unauthorized', items)

            elif level == 2:

                if _type == 'person':
                    for account in plex_instance.systemAccounts():
                        items.append({
                            'title': account.name,
                            'subtitle': f'Default Audio: {account.defaultAudioLanguage} ǀ Default Subtitles: {account.defaultSubtitleLanguage} ǀ ID: {account.id}',
                            'valid': False,
                            'icon': {
                                'path': 'icons/person.webp',
                            },
                        })

                elif _type == 'device':
                    ids = []
                    for device in plex_instance.myPlexAccount().devices():
                        ids.append(device.clientIdentifier)
                    for device in plex_instance.systemDevices():
                        if device.clientIdentifier in ids:
                            dName = device.name if device.name else 'Anonymous'
                            items.insert(1, {
                                'title': dName,
                                'subtitle': f'Platform: {device.platform} ǀ Created At: {parse_time(device.createdAt)} ǀ ID: {device.id}',
                                'valid': False,
                                'icon': {
                                    'path': 'icons/device.webp',
                                },
                            })

                elif _type == 'watch':
                    for session in plex_instance.sessions():
                        if session:
                            users = ', '.join([u for u in session.usernames])
                            sName = f'{session.title} ({session.year})' if session.type == 'movie' else f'{session.grandparentTitle} ǀ {session.title} ǀ {session.seasonEpisode}' if session.type == 'episode' else session.title
                            items.append({
                                'title': sName,
                                'subtitle': f'{session.player.product} - {session.player.device} {session.player.platform} ǀ {users} ǀ {parse_duration(session.viewOffset)} {session.player.state}',
                                'valid': False,
                                'icon': {
                                    'path': 'icons/watch.webp',
                                },
                                'mods':({
                                    'cmd': {
                                        'subtitle': 'Press ⏎ to terminate this session',
                                        'arg': f'_run;{serverID};terminateSession;{session.session.id};{sName}',
                                        'icon': {
                                            'path': 'icons/delete.webp',
                                        },
                                    }
                                })
                            })

                elif _type == 'setting':
                    for group in plex_instance.settings.groups():
                        if group == '':
                            continue
                        title = group.capitalize()
                        eCount = 0
                        for elem in plex_instance.settings.group(group):
                            if elem.hidden == False:
                                eCount += 1
                        items.append({
                            'title': title,
                            'subtitle': f'Display {title} settings ǀ {eCount} element(s)',
                            'arg': f'_rerun;{serverID};3;setting;{group}',
                            'icon': {
                                'path': 'icons/setting.webp',
                            },
                        })

                elif _type in ['library', 'history']:
                    isRefresh = False if any(s.refreshing == False for s in plex_instance.library.sections()) else True
                    sUpdatedAt = []
                    for s in plex_instance.library.sections():
                        sUpdatedAt.append(parse_time(s.updatedAt))
                    lastUpdate = max(sUpdatedAt)
                    for elem in [
                        {
                            'title': 'Scan All Library Sections',
                            'subtitle': f'Scan all sections for new media ǀ Scaning: {isRefresh}',
                            'arg': f'_run;{serverID};scan;all',
                            'icon': {
                                'path': 'icons/scan.webp',
                            }
                        },
                        {
                            'title': 'Refresh All Library Sections',
                            'subtitle': f'Forces a download of fresh media infos from the internet ǀ Last Refresh: {lastUpdate}',
                            'arg': f'_run;{serverID};refresh;all',
                            'icon': {
                                'path': 'icons/refresh.webp',
                            }
                        },
                        {
                            'title': 'Library Sections History',
                            'subtitle': 'History for all library sections',
                            'arg': f'_rerun;{serverID};3;history;all',
                            'icon': {
                                'path': 'icons/history.webp',
                            } 
                        }
                    ]:
                        items.append(elem)
                    for s in plex_instance.library.sections():
                        items.append({
                            'title': s.title,
                            'subtitle': f'{plex_instance.friendlyName} ǀ Scanner: {s.scanner} ǀ Agent: {s.agent}',
                            'arg': f'_rerun;{serverID};3;library;{s.key}',
                            'icon': {
                                'path': f'icons/{s.type}.webp',
                            },
                        })

            elif level == 3:

                if _type == 'setting':
                    for setting in plex_instance.settings.group(_key):
                        if setting.hidden == False:
                            sSumm = f'ǀ {setting.summary}' if setting.summary != '' else ''
                            items.append({
                                'title': setting.label,
                                'subtitle': f'{setting.id}: {setting.value} ǀ Type: {setting.type} ǀ Default: {setting.default} {sSumm}',
                                'arg': f'_setting;{serverID};{setting.id};{setting.type};{setting.default};{setting.value}',
                                'action': {
                                    'text': f'ID: {setting.id}\nValue: {setting.value}\nType: {setting.type}\nDefault: {setting.default}\nSummary: {setting.summary}',
                                },
                                'icon': {
                                    'path': 'icons/setting.webp',
                                },
                            })

                elif _type == 'history' and _key == 'all':
                    for h in plex_instance.history(mindate=history_days()):
                        try:
                            lName = plex_instance.library.sectionByID(h.librarySectionID).title
                        except:
                            lName = 'Deleted Library'
                        makeHistory(h, lName)

                elif _type in ['library', 'history']:
                    sectionID = int(_key)
                    sectionBase = plex_instance.library.sectionByID(sectionID)
                    lType = sectionBase.type
                    lTitle = sectionBase.title
                    isRefresh = sectionBase.refreshing
                    lastUpdate = parse_time(sectionBase.updatedAt)
                    lByte = get_size_string(sectionBase.totalStorage)
                    lSize = f'{sectionBase.totalViewSize(libtype=lType, includeCollections=False)} {lType}(s)'
                    if lType in ('show', 'artist'):
                        subtypes = {'show': ['season', 'episode'], 'artist': ['album', 'track']}
                        lSize += ', ' + ', '.join([f"{sectionBase.totalViewSize(libtype=subtype, includeCollections=False)} {subtype}(s)" for subtype in subtypes[lType]])
                    for elem in [
                        {
                            'title': f'Scan {lTitle} Library',
                            'subtitle': f'Scan this section for new media ǀ Scaning: {isRefresh}',
                            'arg': f'_run;{serverID};scan;{sectionID}',
                            'icon': {
                                'path': 'icons/scan.webp',
                            }
                        },
                        {
                            'title': f'Refresh {lTitle} Section',
                            'subtitle': f'Forces a download of fresh media infos from the internet ǀ Last Refresh: {lastUpdate}',
                            'arg': f'_run;{serverID};refresh;{sectionID}',
                            'icon': {
                                'path': 'icons/refresh.webp',
                            }
                        },
                        {
                            'title': f'{lTitle} History',
                            'subtitle': f'History for the {lTitle} section',
                            'arg': f'_rerun;{serverID};4;history;{sectionID}',
                            'icon': {
                                'path': 'icons/history.webp',
                            } 
                        },
                        {
                            'title': f'{lTitle} Section Size',
                            'subtitle': f'{lSize} ǀ {lByte}',
                            'valid': False,
                            'icon': {
                                'path': 'icons/info.webp',
                            }
                        },
                    ]: 
                        items.append(elem)

            elif level == 4:

                if _type == 'history':
                    for h in plex_instance.library.sectionByID(int(_key)).history(mindate=history_days()):
                        lName = plex_instance.library.sectionByID(h.librarySectionID).title
                        makeHistory(h, lName)

print(json.dumps({'items': items}))