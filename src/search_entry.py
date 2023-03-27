import os
import sys
import json
sys.path.insert(0, './lib')
from lib.plexapi.server import PlexServer
from lib.plexapi import utils
from utils import limit_number, parse_time, parse_duration, servers_file, aliases_file, delist, default_element, display_notification, default_view, addReturnbtn, short_web, short_stream, short_mtvsearch

# full query
try:
    query = sys.argv[1]
except IndexError:
    query = ''

_level = int(os.environ.get('_lib1', 0))
_type = os.environ.get('_lib2')
_keys = os.environ.get('_lib3')
if _keys and 'ǀ' in _keys:
    _machineID, _sectionID, _media_type, _media_id =  _keys.split('ǀ')
else:
    _machineID = _sectionID = _media_type = _media_id = ''

# Full list of filters
query_dict = {}

# Items that will be displayed in alfred
items = []

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
            'show': lambda: f'{media.childCount} season(s), {len(media.episodes())} episode(s) ǀ Studio: {media.studio}',
            'season': lambda: f'{len(media.episodes())} episode(s)', 
            'episode': lambda: f'{parse_duration(media.duration)} ǀ {parse_time(media.originallyAvailableAt)} ǀ Director(s): {", ".join([d.tag for d in media.directors])}',
            'artist': lambda: f'ID: {media.index}',
            'album': lambda: f'Artist(s): {media.parentTitle} ǀ {len(media.tracks())} track(s) ǀ Studio: {media.studio}',
            'track': lambda: f'{parse_duration(media.duration)} ǀ Album: {media.parentTitle} - {media.trackNumber} / {len(media.album().tracks())}',
            'photoalbum': lambda: f'{len(media.albums())} album(s) ǀ {len(media.photos())} photo(s)',
            'photo': lambda: f'{media.year} ǀ Rating: {media.rating}/10',
            'clip': lambda: f'{media.year} ǀ Rating: {media.rating}/10',
            'playlist': lambda: f'{media.playlistType} ǀ {len(media.items())} element(s)',
            'collection': lambda: f'{media.childCount} element(s) ǀ ID: {media.index}',
            'actor': lambda: f'ID: {media.id}',
            'director': lambda: f'ID: {media.id}',
            'genre': lambda: f'ID: {media.id}',
        }
        subtitle_func = subtitle_funcs.get(media_type, lambda: '')
        return f'{media._server.friendlyName} ǀ {media_type}{" ǀ " if subtitle_func() else ""}{subtitle_func()}'
    
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
    
        if not media_type:
            continue
    
        media_arg = ''
        media_mod = {}

        if media_type == 'artist':
            media_arg = f'_rerun;0;filter;{aliases_file("libtype", "alias_or_long")}=album/{aliases_file("advancedFilters", "alias_or_long")}={{\'artist.title\': \'{media.title}\'}}'
        elif media_type in ['actor', 'director', 'genre', 'collection']:
            media_id = media.index if media_type == 'collection' else media.id
            media_arg = f'_rerun;0;filter;{aliases_file(media_type, "alias_or_long")}={media_id}'
        elif short_web != '':
            webArg = f'_web;{media.getWebURL()}'
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
        if media_type in ['movie', 'episode', 'album', 'track', 'clip'] and short_stream != '':
            sArg = f'_rerun;1;streams;{plex_instance.machineIdentifier}ǀ{media.librarySectionID}ǀ{media_type}ǀ{media.key}' if media_type not in ['album', 'track'] and len(media.media) > 1 else f'_stream;{plex_instance.machineIdentifier};{media.librarySectionID};{media_type};{media.key};0;0'
            if short_stream == 'arg':
                media_arg = sArg
            else:
                media_mod.update({
                    f'{short_stream}': {
                        'subtitle': 'Press ⏎ to play the media in a VLC instance',
                        'arg': sArg,
                        'icon': {
                            'path': 'icons/vlc.webp',
                        },
                    }
                })
        if media_type in ['movie', 'show'] and short_mtvsearch != '':
            mtvArg = f'_mtvsearch;{plex_instance.machineIdentifier};{media.librarySectionID};{media_type};{media.key}'
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
            'icon': {
                'path': f'icons/{image_type}.webp',
            },
            'mods': media_mod
        }
        items.append(json_obj)

data = servers_file()
if data.get('items'):
        for obj in data['items']:
            if obj.get('machineIdentifier') != _machineID and _level > 0:
                continue
            baseURL = obj.get('baseURL')
            plexToken = obj.get('plexToken')
            try:
                plex_instance = PlexServer(baseURL, plexToken)
            except:
                display_notification('🚨 Error !', f'Failed to connect to the Plex server \'{obj.get("title")}\'. Check the IP and token')
                exit()
            if _level == 0:
                if '=' in query:
                    try:
                        for item in query.split('/'):
                            key, value = item.split('=', 1)
                            test_key = aliases_file(key, 'alias_and_long')
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
                        kwargs = {}
                        for key, value in query_dict.items():
                            if key != 'advancedFilters':
                                kwargs[key] = value
                        raw = []
                        for section in plex_instance.library.sections():
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
                        database = plex_instance.library.search(limit=limit_number, **default_view) if query == '' else plex_instance.search(query, limit=limit_number) if not '/' in query else plex_instance.search(query.split('/')[0], mediatype=query.split('/')[1], limit=limit_number)
                        register_elements(database)
                    except:
                        delist('no_ELEM', items)
            else:
                rArg = f'{_level - 1};return;'
                addReturnbtn(rArg, items)
                if _level == 1:
                    if _type == 'streams':
                        media = plex_instance.library.sectionByID(int(_sectionID)).fetchItem(_media_id)
                        for mIndex, m in enumerate(media.media):
                            for pIndex, p in enumerate(m.parts):
                                pTitle = p.videoStreams()[0].displayTitle
                                pSub = f'Audio(s): {", ".join([a.displayTitle for a in p.audioStreams()])} ǀ Subtitle(s): {", ".join([a.displayTitle for a in p.subtitleStreams()])}'
                                items.append({
                                    'title': pTitle,
                                    'subtitle': pSub,
                                    'arg': f'_stream;{_machineID};{_sectionID};{_media_type};{_media_id};{mIndex};{pIndex}',
                                    'icon': {
                                        'path': f'icons/{_media_type}.webp',
                                    },
                                })

        if not items:
            if not '=' in query:
                delist('no_ELEM', items)
            else:
                delist('invalid_FILTERS', items)
else:
    delist('no_PMS', items)

for item in items:
    if 'skip' in item:
        _action = item.get('skip')
        items = []
        default_element(_action, items, query, query_dict)

print(json.dumps({'items': items}))