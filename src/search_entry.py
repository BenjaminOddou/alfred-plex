import os
import sys
import json
from utils import limit_number, parse_time, parse_duration, servers_file, alias_file, delist, default_element, display_notification, default_view, addReturnbtn, addMenuBtn, short_nested_search, short_web, short_stream, short_mtvsearch, media_player, custom_logger
from plexapi import utils
from plexapi.server import PlexServer

query_dict = {}
items = []

try:
    query = sys.argv[1]
    try:
        if '=' in query:
            new_query_items = []
            for item in query.split('/'):
                key, value = item.split('=', 1)
                test_key = alias_file(_testkey=key, _type='alias_and_long')
                if not test_key:
                    delist('invalid_FILTERS', items)
                    break
                elif test_key == 'advancedFilters':
                    try:
                        value = eval(value)
                    except:
                        value = {}
                else:
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                query_dict[test_key] = value
                libtype = query_dict.get('libtype')
                advancedFilters = query_dict.get('advancedFilters')
                kwargs = {key: value for key, value in query_dict.items() if key not in ['advancedFilters', 'server', 'section']}
    except:
        pass
except IndexError:
    query = ''

base_dict = {key: value for key, value in default_view.items() if key not in ['server', 'section']}
query_dict = default_view if query == '' else query_dict

_level = int(os.getenv('_lib1', 0))
_type = os.getenv('_lib2')
_keys = os.getenv('_lib3')
if _keys and 'ǀ' in _keys:
    _machineID, _media_type, _media_id =  _keys.split('ǀ')
else:
    _machineID = _media_type = _media_id = ''

def register_elements(database: list):
    def get_title(media):
        title_funcs = {
            'movie': lambda: f'{media.title} ({media.year})',
            'show': lambda: f'{media.title} ({media.year})',
            'season': lambda: f'{media.parentTitle} ǀ {media.title}',
            'episode': lambda: f'{media.grandparentTitle} ǀ {media.title} ǀ {media.seasonEpisode}',
            'artist': lambda: media.title,
            'album': lambda: f'{media.title} ({media.year})',
            'track': lambda: f'{media.grandparentTitle} ǀ {media.title} ({media.album().year})',
            'photoalbum': lambda: media.title,
            'photo': lambda: f'{media.parentTitle} ǀ {media.title}',
            'clip': lambda: media.title,
            'playlist': lambda: f'{media.title} ({parse_time(media.addedAt)})',
            'collection': lambda: f'{media.title} ({media.minYear} - {media.maxYear})',
            'actor': lambda: media.tag,
            'director': lambda: media.tag,
            'genre': lambda: f'{media.tag} ({media.librarySectionTitle})',
        }
        title_func = title_funcs.get(media_type, lambda: '')
        return f'{title_func()}'
    
    def get_subtitle(media):
        subtitle_funcs = {
            'movie': lambda: f'{parse_duration(media.duration)} ǀ Studio: {media.studio} ǀ Director(s): {", ".join([d.tag for d in media.directors])}',
            'show': lambda: f'{media.childCount} season(s) ǀ Studio: {media.studio}',
            'season': lambda: f'Studio: {media.parentStudio}', 
            'episode': lambda: f'{parse_duration(media.duration)} ǀ {parse_time(media.originallyAvailableAt)} ǀ Director(s): {", ".join([d.tag for d in media.directors])}',
            'artist': lambda: f'ID: {media.index}',
            'album': lambda: f'Artist(s): {media.parentTitle} ǀ {len(media.tracks())} track(s) ǀ Studio: {media.studio}',
            'track': lambda: f'{parse_duration(media.duration)} ǀ Album: {media.parentTitle} - {media.trackNumber} / {len(media.album().tracks())}',
            'photoalbum': lambda: f'{len(media.albums())} album(s) ǀ {len(media.photos())} photo(s)',
            'photo': lambda: f'{media.year}',
            'clip': lambda: f'{media.year} ǀ Rating: {media.rating}/10',
            'playlist': lambda: f'{media.playlistType} ǀ {len(media.items())} element(s)',
            'collection': lambda: f'{media.childCount} element(s) ǀ ID: {media.index}',
            'actor': lambda: f'ID: {media.id}',
            'director': lambda: f'ID: {media.id}',
            'genre': lambda: f'ID: {media.id}',
        }
        subtitle_func = subtitle_funcs.get(media_type, lambda: '')
        return f'{friendlyName} ǀ {media_type}{" ǀ " if subtitle_func() else ""}{subtitle_func()}'
    
    class_media_map = {
        'Movie': ('movie', 'movie'),
        'Show': ('show', 'show'),
        'Season': ('season', 'show'),
        'Episode': ('episode', 'show'),
        'Artist': ('artist', 'person'),
        'Album': ('album', 'artist'),
        'Track': ('track', 'artist'),
        'Photoalbum': ('photoalbum', 'photo'),
        'Photo': ('photo', 'photo'),
        'Clip': ('clip', 'clip'),
        'Playlist': ('playlist', 'playlist'),
        'Collection': ('collection', 'collection'),
        'Role': ('actor', 'person'),
        'Director': ('director', 'person'),
        'Genre': ('genre', 'genre'),
    }
    
    for media in database:
        
        media_type, image_type = class_media_map.get(type(media).__name__, (None, None))
    
        if media_type is None:
            continue
    
        media_arg = None
        media_mod = {}

        if media_type in ['artist', 'album', 'show', 'season', 'actor', 'director', 'collection', 'genre'] and short_nested_search != '':
            if media_type in ['artist', 'album', 'show', 'season']:
                search_map = {'artist': 'album', 'album': 'track', 'show': 'season', 'season': 'episode'}
                title = media.title.replace("'", "\\'")
                if media_type in ['season', 'album']:
                    parentTitle = media.parentTitle.replace("'", "\\'")
                if media_type == 'season':
                    media_filter = f'{{\'season.index\': {media.index}, \'show.title=\': \'{parentTitle}\'}}'
                elif media_type == 'album':
                    media_filter = f'{{\'album.title=\': \'{title}\', \'artist.title=\': \'{parentTitle}\'}}'
                else:    
                    media_filter = f'{{\'{media_type}.title=\': \'{title}\'}}'
                nested_search = f'_rerun;0;filter;{alias_file(_testkey="libtype", _type="alias_or_long")}={search_map[media_type]}/{alias_file(_testkey="advancedFilters", _type="alias_or_long")}={media_filter}'
            elif media_type in ['actor', 'director', 'collection']:
                media_id = media.index if media_type == 'collection' else media.id
                nested_search = f'_rerun;0;filter;{alias_file(_testkey=media_type, _type="alias_or_long")}={media_id}'
            elif media_type == 'genre':
                nested_search = f'_rerun;0;filter;{alias_file(_testkey="libtype", _type="alias_or_long")}={utils.reverseSearchType(media.librarySectionType)}/{alias_file(_testkey="genre", _type="alias_or_long")}={media.id}'
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
        if media_type not in ['genre', 'photo'] and short_web:
            urlElem = media.getWebURL() if media_type not in ['actor', 'director'] else f'https://app.plex.tv/desktop/#!/provider/tv.plex.provider.discover/details?key=%2Flibrary%2Fpeople%2F{media.tagKey}&context=search'
            webArg = f'_web;{urlElem}'
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
        if media_type in ['movie', 'episode', 'album', 'track', 'clip'] and short_stream:
            sArg = f'_rerun;1;streams;{plex_instance.machineIdentifier}ǀ{media_type}ǀ{media.key}' if media_type not in ['album', 'track'] and len(media.media) > 1 else f'_stream;{plex_instance.machineIdentifier};{media_type};{media.key};0;0'
            if short_stream == 'arg':
                media_arg = sArg
            else:
                media_mod.update({
                    f'{short_stream}': {
                        'subtitle': f'Press ⏎ to play the media in a {media_player.upper()} instance',
                        'arg': sArg,
                        'icon': {
                            'path': f'icons/base/{media_player}.webp',
                        },
                    }
                })
        if media_type in ['movie', 'show'] and short_mtvsearch:
            mtvArg = f'_mtvsearch;{plexUUID};{media_type};{media.guid.split("/")[-1]}'
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

        json_obj = {
            'title': get_title(media),
            'subtitle': get_subtitle(media),
            'icon': {
                'path': f'icons/base/{image_type}.webp',
            },
            'mods': media_mod,
            'valid': False,
            'key': f'{get_title(media)}&{get_subtitle(media)}'
        }

        if media_arg:
            json_obj['arg'] = media_arg
            json_obj['valid'] = True

        existing_item = next((item for item in items if item.get('key') == json_obj.get('key')), None)
        if not existing_item:
            items.append(json_obj)

data = servers_file()
if data.get('items'):
        for obj in data['items']:
            if (obj['machineIdentifier'] != _machineID and _level > 0) or (query_dict.get('server') and obj['friendlyName'].lower() not in query_dict.get('server', '').lower().split(',')):
                continue
            friendlyName = obj['friendlyName']
            baseURL = obj['baseURL']
            plexToken = obj['plexToken']
            plexUUID = obj['account_uuid']
            try:
                plex_instance = PlexServer(baseURL, plexToken)
            except Exception as e:
                display_notification('🚨 Error !', f'Failed to connect to the plex server {obj["title"]}')
                custom_logger('error', e)
                addMenuBtn(items)
                print(json.dumps({'items': items}))
                exit()
            if _level == 0:
                if '=' in query:
                    try:
                        raw = []
                        for section in plex_instance.library.sections():
                            if query_dict.get('section') and section.title.lower() not in query_dict.get('section', '').lower().split(','):
                                continue
                            try:
                                if libtype and advancedFilters:
                                    raw.append(section.search(**kwargs, limit=limit_number, filters=advancedFilters))
                                else:
                                    raw.append(section.search(**kwargs, limit=limit_number))
                            except:
                                continue
                        database = [item for sublist in raw for item in sublist]
                        register_elements(database)
                    except:
                        delist('invalid_FILTERS', items)
                else:
                    try:
                        if query == '':
                            if not any(item['arg'] == '_rerunMenu' for item in items):
                                addMenuBtn(items)
                            for section in plex_instance.library.sections():
                                if query_dict.get('section') and section.title.lower() not in query_dict.get('section', '').lower().split(','):
                                    continue
                                try:
                                    database = section.search(limit=limit_number, **base_dict)
                                except:
                                    continue
                        elif not '/' in query:
                            database = plex_instance.search(query, limit=limit_number)
                        else:
                            database = plex_instance.search(query.split('/')[0], mediatype=query.split('/')[1], limit=limit_number)
                        register_elements(database)
                    except:
                        delist('no_ELEM', items)
            else:
                rArg = f'{_level - 1};return;'
                addReturnbtn(rArg, items)
                if _level == 1:
                    if _type == 'streams':
                        media = plex_instance.fetchItem(_media_id)
                        for mIndex, m in enumerate(media.media):
                            for pIndex, p in enumerate(m.parts):
                                pTitle = p.videoStreams()[0].displayTitle
                                pSub = f'Audio(s): {", ".join([a.displayTitle for a in p.audioStreams()])} ǀ Subtitle(s): {", ".join([a.displayTitle for a in p.subtitleStreams()])}'
                                items.append({
                                    'title': pTitle,
                                    'subtitle': pSub,
                                    'arg': f'_stream;{_machineID};{_media_type};{_media_id};{mIndex};{pIndex}',
                                    'icon': {
                                        'path': f'icons/base/{_media_type}.webp',
                                    },
                                })

        if not items:
            if not '=' in query:
                delist('no_ELEM', items)
            else:
                delist('invalid_FILTERS', items)
else:
    addMenuBtn(items)
    default_element('no_PMS', items)

for item in items:
    if 'skip' in item:
        _action = item['skip']
        items = []
        default_element(_action, items, query, query_dict)

print(json.dumps({'items': items}))