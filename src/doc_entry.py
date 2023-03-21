import os
import sys
import json
sys.path.insert(0, './lib')
import urllib.parse
from types import SimpleNamespace
from lib.plexapi.server import PlexServer
from utils import default_element, servers_file, aliases_file, filters_bool, display_notification, addReturnbtn

items = []

try:
    query = sys.argv[1]
except IndexError:
    query = ''

data = servers_file()

try:
    level = int(os.environ['_lib'].split(';')[0])
except:
    level = 0

if data.get('items'):
    for obj in data['items']:
        baseURL = obj.get('baseURL')
        plexToken = obj.get('plexToken')
        try:
            plex_instance = PlexServer(baseURL, plexToken)
        except:
            display_notification('🚨 Error !', f'Failed to connect to the Plex server \'{obj.get("title")}\'. Check the IP and token')
            exit()
        if level == 0:
            for s in plex_instance.library.sections():
                items.append({
                    'title': s.title,
                    'subtitle': f'{plex_instance.friendlyName} ǀ Scanner: {s.scanner} ǀ Agent: {s.agent}',
                    'arg': f'_rerun;1;{s.key}',
                    'icon': {
                        'path': f'icons/{s.type}.webp',
                    },
                })
        else:
            sectionID = int(os.environ['_lib'].split(';')[1])
            library_subtypes = []
            for t in plex_instance.library.sectionByID(sectionID).filterTypes():
                if t.type not in ['folder']:
                    library_subtypes.append(t.type)
            library_type = plex_instance.library.sectionByID(sectionID).type
            library_name = plex_instance.library.sectionByID(sectionID).title
            library_filter = aliases_file('libtype', 'alias_or_long')
            library_advancedFilter = aliases_file('advancedFilters', 'alias_or_long')
            sort_filter = aliases_file('sort', 'alias_or_long')
            rArg = '0' if level == 1 else f'1;{sectionID}'
            addReturnbtn(rArg, items)
            if level == 1:
                for f in plex_instance.library.sectionByID(sectionID).listFilters():
                    alias = aliases_file(f.filter, 'alias')
                    items.append({
                        'title': f'Filter {f.title}',
                        'subtitle': f'{plex_instance.friendlyName} ǀ {library_name} ǀ Name: {f.filter} ǀ Alias: {alias}',
                        'arg': f'_rerun;2;{sectionID};{f.filter};{alias};filter;{f.filterType};{f.title}',
                        'icon': {
                            'path': f'icons/filter.webp',
                        },
                    })
                for f in plex_instance.library.sectionByID(sectionID).listFields():
                    items.append({
                        'title': f'Field {f.title}',
                        'subtitle': f'{plex_instance.friendlyName} ǀ {library_name} ǀ Name: {f.key}',
                        'arg': f'_rerun;2;{sectionID};{f.key};None;field;{f.type};{f.title}',
                        'icon': {
                            'path': f'icons/field.webp',
                        },
                    })
                for so in plex_instance.library.sectionByID(sectionID).listSorts():
                    items.append({
                        'title': f'Sort {so.title}',
                        'subtitle': f'{plex_instance.friendlyName} ǀ {library_name} ǀ Name: {so.key}',
                        'arg': f'_rerun;2;{sectionID};{so.key};None;sort;None;None',
                        'icon': {
                            'path': f'icons/sort.webp',
                        },
                    })
            elif level == 2:
                _, _, Name, Alias, Type, fType, Title = os.environ['_lib'].split(';')
                items.append({
                    'title': 'You can use alternative libtypes',
                    'subtitle': f'Authorized libtypes: {library_subtypes}',
                    'arg': '',
                    'icon': {
                        'path': 'icons/info.webp',
                    },
                })
                if Type == 'filter':
                    if fType == 'boolean':
                        choices = json.loads('[{"key": "true", "title": "is true"}]', object_hook=lambda d: SimpleNamespace(**d))
                    else:
                        choices = plex_instance.library.sectionByID(sectionID).listFilterChoices(Name)
                    for p in choices:
                        dKey = urllib.parse.unquote(p.key.replace('%25', '%'))
                        pArg = f'{library_filter}={library_type}'
                        pArg += f'/{Alias}={dKey}' if filters_bool else f'/{Name}={dKey}'
                        items.append({
                            'title': p.title,
                            'subtitle': f'Press ⏎ to apply the filter: {pArg}',
                            'arg': f'_filter;{pArg}',
                            'icon': {
                                'path': 'icons/filter.webp',
                            },
                        })
                elif Type == 'field':
                    choices = plex_instance.library.sectionByID(sectionID).listOperators(fType)
                    for obj in choices:
                        dict_final = {f'{Name}{obj.key[:-1]}': ''}
                        pArg = f'{library_filter}={library_type}/{library_advancedFilter}={dict_final}'
                        items.append({
                            'title': f'{Title} \'{obj.title}\'',
                            'subtitle': f'Press ⏎ to apply the advanced filter: {pArg}',
                            'arg': f'_filter;{pArg}',
                            'icon': {
                                'path': 'icons/field.webp',
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
                            'arg': f'_sort;{soArg}',
                            'icon': {
                                'path': f'icons/sort.webp',
                            },
                        })
else:
    default_element('no_PMS', items)

filtered_items = [item for item in items if query.lower() in item['title'].lower() or query.lower() in item['subtitle'].lower()]

output = {
    'items': filtered_items
}

print(json.dumps(output))