from utils import default_element, short_web, short_mtvsearch, short_nested_search, short_watchlist, language, parse_duration, limit_number, accounts_file, addMenuBtn, get_plex_account, display_notification, custom_logger, splitN
import sys
import json
import requests

query = sys.argv[1]
items = []

if not query:
    addMenuBtn(items)

def searchDiscover(query=None, libtype=None, plex_uuid=None):

    def get_title(media):
        title_funcs = {
            'movie': lambda: f'{media.get("title")} ({media.get("year")})',
            'show': lambda: f'{media.get("title")} ({media.get("year")})',
            'person': lambda: media.get("title")
        }
        title_func = title_funcs.get(media_type, lambda: '')
        return f'{title_func()}'
    
    def get_subtitle(media):
        subtitle_funcs = {
            'movie': lambda: f'{parse_duration(media.get("duration")) if media.get("duration") else "Unknown"}',
            'show': lambda: f'{media.get("childCount")} season(s)',
        }
        subtitle_func = subtitle_funcs.get(media_type, lambda: '')
        return f'{media_type}{" ǀ " if subtitle_func() else ""}{subtitle_func()}'
    
    libtypes = {'movie': 'movies', 'show': 'tv', 'people': 'people'}
    libtype = libtypes.get(libtype, 'movies,tv,people')

    headers = {
        'Accept': 'application/json'
    }

    plex_account = get_plex_account(uuid=plex_uuid)
    watchlist_guids = [elem.guid for elem in plex_account.watchlist()]

    if query:
        params1 = {
            'query': query,
            'limit': splitN(limit_number),
            'searchTypes': libtype,
            'includeMetadata': 1,
            'filterPeople': 1,
            'X-Plex-Language': language,
            'searchProviders': 'discover'
        }
        response = requests.get(f'{plex_account.DISCOVER}/library/search', params=params1, headers=headers) 
    else:
        params2 = {
            'X-Plex-Container-Size': limit_number,
            'X-Plex-Language': language,
            'X-Plex-Token': plex_account.authToken
        }
        response = requests.get(f'{plex_account.DISCOVER}/hubs/sections/home/top_watchlisted', params=params2, headers=headers)

    if response.status_code == 200:
        json_data = response.json()
        if query:
            searchResults = json_data['MediaContainer'].get('SearchResults', [])
            searchResult = [r for s in searchResults if s.get('id') in ['external', 'people'] for r in s.get('SearchResult', [])]
        else:
            searchResult = json_data['MediaContainer'].get('Metadata', [])
        for result in searchResult:
            metadata = result.get('Metadata') or result.get('Directory') if query else result
            media_type = metadata.get('type')
            media_mod = {}
            media_arg = None
            uuid = metadata.get('ratingKey') or metadata.get('metadataId')

            if short_web != '':
                webArg = f'_web;https://app.plex.tv/desktop/#!/provider/tv.plex.provider.discover/details?key=%2Flibrary%2F{"people" if media_type == "person" else "metadata"}%2F{uuid}&context=search'
                if short_web == 'arg':
                    media_arg = webArg
                else:
                    media_mod.update({
                        f'{short_web}': {
                            'subtitle': 'Press ⏎ to open the media in plex web',
                            'arg': webArg,
                            'icon': {
                                'path': 'icons/base/web.webp',
                            },
                        }
                    })
            
            obj_title = get_title(metadata)
            obj_subtitle = get_subtitle(metadata)

            if short_nested_search != '':
                if media_type in ['movie', 'show']:
                    nested_search = f'_rerun;1;guid;ǀ{media_type}ǀ{metadata.get('guid')}ǀ{obj_title}'
                else:
                    nested_search = f'_rerun;0;filter;{obj_title}'
                if short_nested_search == 'arg':
                    media_arg = nested_search
                else:
                    media_mod.update({
                        f'{short_nested_search}': {
                            'subtitle': 'Press ⏎ to trigger a nested search',
                            'arg': nested_search,
                            'icon': {
                                'path': 'icons/base/folder.webp',
                            },
                        }
                    })

            isInWatchlist = False

            if media_type in ['movie', 'show']:

                if short_mtvsearch != '':
                    mtvArg = f'_mtvsearch;{plex_uuid};{media_type};{uuid}'
                    if short_mtvsearch == 'arg':
                        media_arg = mtvArg
                    else:
                        media_mod.update({
                            f'{short_mtvsearch}': {
                                'subtitle': 'Press ⏎ to get media infos using Movie and TV Show Search workflow',
                                'arg': mtvArg,
                                'icon': {
                                    'path': 'icons/base/movie_and_tv_show_search.webp',
                                },
                            }
                        })
                if short_watchlist != '':
                    media_guid = metadata.get('guid')
                    isInWatchlist = True if media_guid in watchlist_guids else False
                    action = "delete" if isInWatchlist else "add"
                    verb = "from" if isInWatchlist else "to"
                    watchArg = f'_run;_watchlist;{action};{plex_uuid};{media_guid};{obj_title} was {"removed" if isInWatchlist else "added"} {verb} watchlist of {plex_account.friendlyName};discover'
                    if short_watchlist == 'arg':
                        media_arg = watchArg
                    else:
                        media_mod.update({
                            f'{short_watchlist}': {
                                'subtitle': f'Press ⏎ to {action} the {media_type} {verb} watchlist',
                                'arg': watchArg,
                                'icon': {
                                    'path': f'icons/base/{action}.webp',
                                },
                            }
                        })

            json_obj = {
                'title': obj_title,
                'subtitle': obj_subtitle,
                'arg': media_arg,
                'valid': False,
                'mods': media_mod,
                'icon': {
                    'path': f'icons/base/{media_type}_discover{"_bookmarked" if isInWatchlist else ""}.webp',
                },
            }

            if media_arg:
                json_obj['arg'] = media_arg
                json_obj['valid'] = True

            items.append(json_obj)

plex_account = accounts_file()
if plex_account.get('items'):
    plex_uuid = plex_account['items'][0]['uuid']
    try:
        database = searchDiscover(query=query, plex_uuid=plex_uuid) if not '/' in query else searchDiscover(query=query.split('/')[0], libtype=query.split('/')[1], plex_uuid=plex_uuid)
    except Exception as e:
        display_notification('🚨 Error !', 'An error occured, check logs')
        custom_logger('error', e)
else:
    default_element('no_ACC', items)
if items == []:
    default_element('no_ELEM', items, query)

print(json.dumps({'items': items}))
