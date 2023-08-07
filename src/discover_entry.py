import sys
import json
from utils import servers_file, delist, default_element, parse_duration, limit_number, short_mtvsearch, short_web, short_nested_search, get_plex_account, language

query = sys.argv[1]

data = servers_file()
items = []

def register_elements(database: list):
    def get_title(media):
        title_funcs = {
            'movie': lambda: f'{media.title} ({media.year})',
            'show': lambda: f'{media.title} ({media.year})',
        }
        title_func = title_funcs.get(media_type, lambda: '')
        return f'{title_func()}'
    
    def get_subtitle(media):
        subtitle_funcs = {
            'movie': lambda: f'{parse_duration(media.duration) if media.duration else "Unknown"}',
            'show': lambda: f'{media.childCount} season(s)',
        }
        subtitle_func = subtitle_funcs.get(media_type, lambda: '')
        return f'{media_type}{" ǀ " if subtitle_func() else ""}{subtitle_func()}'
    
    class_media_map = {
        'Movie': ('movie', 'movie_discover'),
        'Show': ('show', 'show_discover'),
    }

    for media in database:
    
        media_type, image_type = class_media_map.get(type(media).__name__, (None, None))
        
        if media_type is None:
            continue

        media_mod = {}
        media_arg = None

        uuid = media._data.attrib['ratingKey']

        if short_web != '':
            webArg = f'_web;https://app.plex.tv/desktop/#!/provider/tv.plex.provider.discover/details?key=%2Flibrary%2Fmetadata%2F{uuid}&context=search'
            if short_web == 'arg':
                media_arg = webArg
            else:
                media_mod.update({
                    f'{short_web}': {
                        'subtitle': 'Press ⏎ to open the media in plex web',
                        'arg': webArg,
                        'icon': {
                            'path': 'icons/web.webp',
                        },
                    }
                })
        
        if short_nested_search != '':
            nested_search = f'_rerun;0;filter;{media.title}/{media_type}'
            if short_nested_search == 'arg':
                media_arg = nested_search
            else:
                media_mod.update({
                    f'{short_nested_search}': {
                        'subtitle': 'Press ⏎ to trigger a nested search',
                        'arg': nested_search,
                        'icon': {
                            'path': 'icons/folder.webp',
                        },
                    }
                })

        if media_type in ['movie', 'show'] and short_mtvsearch != '':
            mtvArg = f'_mtvsearch;{plexToken};{media_type};{uuid}'
            if short_mtvsearch == 'arg':
                media_arg = mtvArg
            else:
                media_mod.update({
                    f'{short_mtvsearch}': {
                        'subtitle': 'Press ⏎ to get media infos using Movie and TV Show Search workflow',
                        'arg': mtvArg,
                        'icon': {
                            'path': 'icons/movie_and_tv_show_search.webp',
                        },
                    }
                })
        
        json_obj = {
            'title': get_title(media),
            'subtitle': get_subtitle(media),
            'arg': media_arg,
            'valid': False,
            'mods': media_mod,
            'icon': {
                'path': f'icons/{image_type}.webp',
            },
        }

        if media_arg:
            json_obj['arg'] = media_arg
            json_obj['valid'] = True
        
        items.append(json_obj)

if data.get('items'):
    obj = data['items'][0]
    plexToken = obj['plexToken']
    
    plex_account = get_plex_account(plexToken)

    database = plex_account.searchDiscover(query, limit=limit_number, language=language) if not '/' in query else plex_account.searchDiscover(query.split('/')[0], libtype=query.split('/')[1], limit=limit_number)

    if database == []:
        delist('no_ELEM', items)
    else:
        register_elements(database)
else:
    delist('no_PMS', items)

for item in items:
    if 'skip' in item:
        _action = item['skip']
        items = []
        default_element(_action, items, query)

print(json.dumps({'items': items}))