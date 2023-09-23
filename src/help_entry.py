import os
import sys
import json
import urllib.parse
from types import SimpleNamespace
from utils import default_element, servers_file, alias_file, filters_bool, display_notification, addReturnbtn, addMenuBtn, data_folder, cache_folder, custom_logger
from plexapi.server import PlexServer

try:
    query = sys.argv[1]
except IndexError:
    query = ''

data = servers_file()
items = []

def is_title_unique(title, items):
    for item in items:
        if item.get('title', '') == title:
            return False
    return True

try:
    level = int(os.environ['_lib'].split(';')[0])
except:
    level = 0

if level == 0:
    addMenuBtn(items)
    for elem in [
        {
            'title': 'Filters & Sort Options',
            'subtitle': 'Filters and sort options for your plex media server(s)',
            'arg': '_rerun;1;filter&sort;0',
            'icon': {
                'path': 'icons/base/filter.webp',
            },
        },
        {
            'title': 'Filter Alias',
            'subtitle': 'Manage filter alias file',
            'arg': '_rerun;1;alias;0',
            'icon': {
                'path': 'icons/base/alias.webp',
            },
        },
        {
            'title': 'Workflow Cache',
            'subtitle': 'Manage workflow\'s cache files',
            'arg': '_rerun;1;cache;0',
            'icon': {
                'path': 'icons/base/document.webp',
            },
        },
        {
            'title': 'Workflow Data',
            'subtitle': 'Manage workflows\'s data files',
            'arg': '_rerun;1;data;0',
            'icon': {
                'path': 'icons/base/data.webp',
            },
        },
        {
            'title': 'Useful Links',
            'subtitle': 'List of useful links for this workflow',
            'arg': '_rerun;1;web;0',
            'icon': {
                'path': 'icons/base/web.webp',
            },
        }
    ]:
        items.append(elem)
else:
    _type, _sectionID = os.environ['_lib'].split(';')[1], int(os.environ['_lib'].split(';')[2])
    rArg = '0' if level == 1 else f'{level - 1};{_type};{_sectionID}'
    addReturnbtn(rArg, items)
    if _type == 'filter&sort':
        if data.get('items'):
            for obj in data['items']:
                baseURL = obj['baseURL']
                plexToken = obj['plexToken']
                try:
                    plex_instance = PlexServer(baseURL, plexToken)
                except Exception as e:
                    display_notification('🚨 Error !', f'Failed to connect to the plex server {obj.get("title")}')
                    custom_logger('error', e)
                    print(json.dumps({'items': items}))
                    exit()
        else:
            default_element('no_PMS', items)
            print(json.dumps({'items': items}))
            exit()
    if level == 1:
        if _type == 'filter&sort':
            for s in plex_instance.library.sections():
                items.append({
                    'title': s.title,
                    'subtitle': f'{plex_instance.friendlyName} ǀ Scanner: {s.scanner} ǀ Agent: {s.agent}',
                    'arg': f'_rerun;2;{_type};{s.key}',
                    'icon': {
                        'path': f'icons/base/{s.type}.webp',
                    },
                })
        elif _type in ['cache', 'data']:
            home_directory = os.path.expanduser("~")
            folder = cache_folder if _type == 'cache' else data_folder
            transform_path = folder.replace(home_directory, '~')
            valid = True if os.path.exists(folder) else False
            for o in [
                {
                    'title': f'Display {_type.capitalize()} Folder',
                    'subtitle': transform_path if valid else f'{_type.capitalize()} folder doesn\'t exists',
                    'arg': f'_finder;{folder}',
                    'valid': valid,
                    'icon': {
                        'path': 'icons/base/finder.webp',
                    },
                },
                {
                    'title': f'Clear {_type.capitalize()} Folder',
                    'subtitle': 'Delete workflow data files',
                    'arg': f'_run;delete;{_type} folder;{folder}',
                    'valid': valid,
                    'icon': {
                        'path': 'icons/base/delete.webp',
                    },
                },
            ]:
                items.append(o)
        elif _type == 'alias':
            items.append({
                'title': 'Reset',
                'subtitle': 'Reset the alias file',
                'arg': f'_run;reset;alias file;{data_folder}/alias.json',
                'icon': {
                    'path': 'icons/base/refresh.webp'
                },
            })
            for index, item in enumerate(alias_file(_testkey=None, _type=None, _file=True)):
                modified_item = {
                    'title': item['long_key'],
                    'subtitle': f'Alias : {item["short_key"]}',
                    'icon': {
                        'path': 'icons/base/alias.webp'
                    },
                    'valid': False,
                    'mods': {
                        'cmd': {
                            'subtitle': 'Press ⏎ to modify the alias',
                            'arg': f'_run;modify;{item["long_key"]};{item["short_key"]}',
                            'icon': {
                                'path': 'icons/base/modify.webp'
                            }
                        }
                    },
                    'short_key': item['short_key'],
                    'long_key': item['long_key']
                }
                items.append(modified_item)
        elif _type == 'web':
            for i in [
                {
                    'title': 'GitHub',
                    'url': 'https://github.com/BenjaminOddou/alfred-plex',
                    'img': 'github',
                },
                {
                    'title': 'Alfred Gallery',
                    'url': 'https://alfred.app/workflows/benjaminoddou/plex',
                    'img': 'alfred',
                }
            ]:
                items.append({
                    'title': i.get('title'),
                    'subtitle': i.get('url'),
                    'arg': f'_web;{i.get("url")}',
                    'action': {
                        'url': i.get('url'),
                    },
                    'quicklookurl': i.get('url'),
                    'icon': {
                        'path': f'icons/web/{i.get("img")}.webp'
                    },
                })
    else:
        if _type == 'filter&sort':
            library_subtypes = []
            for t in plex_instance.library.sectionByID(_sectionID).filterTypes():
                library_subtypes.append(t.type)
            library_type = plex_instance.library.sectionByID(_sectionID).type
            library_name = plex_instance.library.sectionByID(_sectionID).title
        library_filter = alias_file(_testkey='libtype', _type='alias_or_long')
        library_advancedFilter = alias_file(_testkey='advancedFilters', _type='alias_or_long')
        sort_filter = alias_file(_testkey='sort', _type='alias_or_long')
        if level == 2:
            if _type == 'filter&sort':
                for t in library_subtypes:
                    for f in plex_instance.library.sectionByID(_sectionID).listFilters(libtype=t):
                        alias = alias_file(_testkey=f.filter, _type='alias')
                        new_title = f'Filter {f.title}'
                        if is_title_unique(new_title, items):
                            items.append({
                                'title': f'Filter {f.title}',
                                'subtitle': f'{plex_instance.friendlyName} ǀ {library_name} ǀ Name: {f.filter} ǀ Alias: {alias}',
                                'arg': f'_rerun;3;{_type};{_sectionID};{f.filter};{alias};filter;{f.filterType};{f.title}',
                                'icon': {
                                    'path': f'icons/base/filter.webp',
                                },
                            })
                    for f in plex_instance.library.sectionByID(_sectionID).listFields(libtype=t):
                        if not ',' in f.key:
                            new_title = f'Field {f.title}'
                            if is_title_unique(new_title, items):
                                items.append({
                                    'title': new_title,
                                    'subtitle': f'{plex_instance.friendlyName} ǀ {library_name} ǀ Name: {f.key}',
                                    'arg': f'_rerun;3;{_type};{_sectionID};{f.key};None;field;{f.type};{f.title}',
                                    'icon': {
                                        'path': f'icons/base/field.webp',
                                    },
                                })
                    for so in plex_instance.library.sectionByID(_sectionID).listSorts(libtype=t):
                        if not ',' in so.key:
                            new_title = f'Sort {so.title}'
                            if is_title_unique(new_title, items):
                                items.append({
                                    'title': new_title,
                                    'subtitle': f'{plex_instance.friendlyName} ǀ {library_name} ǀ Name: {so.key}',
                                    'arg': f'_rerun;3;{_type};{_sectionID};{so.key};None;sort;None;None',
                                    'icon': {
                                        'path': f'icons/base/sort.webp',
                                    },
                                })
        elif level == 3:
            if _type == 'filter&sort':
                Name, Alias, Type, fType, Title = os.environ['_lib'].split(';')[3:]
                filtered_subtypes = [x for x in library_subtypes if x != 'folder']
                items.append({
                    'title': 'You can use alternative libtypes',
                    'subtitle': f'Authorized libtypes: {filtered_subtypes}',
                    'valid': False,
                    'icon': {
                        'path': 'icons/base/info.webp',
                    },
                })
                if Type == 'filter':
                    if fType == 'boolean':
                        choices = json.loads('[{"key": "1", "title": "is true"}, {"key": "0", "title": "is false"}]', object_hook=lambda d: SimpleNamespace(**d))
                    else:
                        choices = plex_instance.library.sectionByID(_sectionID).listFilterChoices(Name)
                    for p in choices:
                        dKey = urllib.parse.unquote(p.key.replace('%25', '%'))
                        pArg = f'{library_filter}={library_type}'
                        pArg += f'/{Alias}={dKey}' if filters_bool else f'/{Name}={dKey}'
                        items.append({
                            'title': p.title,
                            'subtitle': f'Press ⏎ to apply the filter: {pArg}',
                            'arg': f'_filter;0;{pArg}',
                            'icon': {
                                'path': 'icons/base/filter.webp',
                            },
                        })
                elif Type == 'field':
                    choices = plex_instance.library.sectionByID(_sectionID).listOperators(fType)
                    for obj in choices:
                        Value = 1 if obj.title == 'is true' else 0 if obj.title == 'is false' else ''
                        dict_final = {f'{Name}{obj.key[:-1]}': Value}
                        pArg = f'{library_filter}={library_type}/{library_advancedFilter}={dict_final}'
                        items.append({
                            'title': f'{Title} \'{obj.title}\'',
                            'subtitle': f'Press ⏎ to apply the advanced filter: {pArg}',
                            'arg': f'_filter;0;{pArg}',
                            'icon': {
                                'path': 'icons/base/field.webp',
                            },
                        })
                elif Type == 'sort':
                    options = [
                        {
                            'title': 'Ascending',
                            'key': 'asc'
                        },
                        {
                            'title': 'Descending',
                            'key': 'desc'
                        },
                    ]
                    for o in options:
                        soArg = f'{library_filter}={library_type}/{sort_filter}={Name}:{o.get("key")}'
                        items.append({
                            'title': o.get('title'),
                            'subtitle': f'Press ⏎ to apply the sorting: {soArg}',
                            'arg': f'_sort;0;{soArg}',
                            'icon': {
                                'path': f'icons/base/sort.webp',
                            },
                        })

print(json.dumps({'items': items}))