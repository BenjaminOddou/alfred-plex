import sys
import json
sys.path.insert(0, './lib')
from lib.plexapi.server import PlexServer
from lib.plexapi import utils
from utils import limit_number, parse_time, parse_duration, servers_file, aliases_file, delist, default_element, display_notification, default_view

# full query
try:
    query = sys.argv[1]
except IndexError:
    query = ''

# Full list of filters
query_dict = {}

# Items that will be displayed in alfred
items = []

def register_elements(database: list):
    for media in database:
        mType = media.TYPE if media.TYPE else utils.reverseTagType(media.TAGTYPE) if media.TAGTYPE else ''
        iType = 'show' if mType in ['season', 'episode'] else 'artist' if mType in ['album', 'track'] else 'person' if mType in ['role', 'director', 'producer', 'artist'] else mType
        fType = 'actor' if mType == 'role' else mType
        mFilter = aliases_file(fType, 'alias_or_long')
        mDuration = f'{parse_duration(media.duration)}' if mType in ['movie', 'episode', 'track'] else ''
        mRealeaseDate = f'{parse_time(media.originallyAvailableAt)}' if mType in ['movie', 'episode', 'clip'] else ''
        eCount = len(media.episodes()) if mType in ['show', 'season'] else ''
        mDirectorNames = ", ".join([d.tag for d in media.directors]) if mType in ['movie', 'episode'] else ''
        mSubtitle = f'{media._server.friendlyName} {f"ǀ {mType}" if mType != "" else ""}'
        mChild = media.childCount if mType in ['show', 'collection'] else ''
        mTitle = ''
        mArg = f'_web;{media.getWebURL()}' if mType not in ['role', 'director', 'genre', ''] else ''

        if mType == 'episode':
            mTitle = f'{media.grandparentTitle} ǀ {media.title} ǀ {media.seasonEpisode}'
            mSubtitle += f' ǀ {mDuration} ǀ {mRealeaseDate} ǀ Director(s): {mDirectorNames}'

        elif mType == 'track':
            mTitle = f'{media.grandparentTitle} ǀ {media.title} ({media.album().year})'
            mSubtitle += f' ǀ {mDuration} ǀ Album: {media.parentTitle} - {media.trackNumber} / {len(media.album().tracks())}'
        
        elif mType == 'artist':
            mTitle = media.title
            mSubtitle += f' ǀ ID: {media.index}'
            mArg = f'_rerun;{aliases_file("libtype", "alias_or_long")}=album/{aliases_file("advancedFilters", "alias_or_long")}={{\'artist.title\': \'{media.title}\'}}'

        elif mType == 'season':
            mTitle = f'{media.parentTitle} ǀ {media.title}'
            mSubtitle += f' ǀ {eCount} episode(s)'

        elif mType in ['show', 'movie', 'album']:
            mTitle = f'{media.title} ({media.year})'
            if mType == 'show':
                mSubtitle += f' ǀ {mChild} season(s), {eCount} episode(s) ǀ Studio: {media.studio}'
            elif mType == 'movie':
                mSubtitle += f' ǀ {mDuration} ǀ Studio: {media.studio} ǀ Director(s): {mDirectorNames}'
            elif mType == 'album':
                mSubtitle += f' ǀ Artist(s): {media.parentTitle} ǀ {len(media.tracks())} track(s) ǀ Studio: {media.studio}'

        elif mType in ['collection', 'role', 'director']:
            if mType == 'collection':
                mTitle = f'{media.title} ({media.minYear} - {media.maxYear})'
                mSubtitle += f' ǀ {mChild} element(s) ǀ ID: {media.index}'
            else:
                mTitle = media.tag
                mSubtitle += f' ǀ ID: {media.id}'

            mId = media.index if mType == 'collection' else media.id
            mArg = f'_rerun;{mFilter}={mId}'
        
        elif mType == 'genre':
            mTitle = f'{media.tag} ({media.librarySectionTitle})'
            mSubtitle += f' ǀ ID: {media.id}'
            sFilter = aliases_file('libtype', 'alias_or_long')
            mArg = f'_rerun;{mFilter}={media.id}/{sFilter}={utils.reverseSearchType(media.librarySectionType)}'
        
        elif mType == 'playlist':
            mTitle = f'{media.title} ({parse_time(media.addedAt)})'
            mSubtitle += f' ǀ {media.playlistType} ǀ {len(media.items())} element(s)'
        
        elif mType in ['photo', 'clip']:
            newType = 'photoalbum' if media.TAG == 'Directory' else mType
            if newType == 'photoalbum':
                mTitle = media.title
                mSubtitle = f'{media._server.friendlyName} ǀ {newType} ǀ {len(media.albums())} album(s) ǀ {len(media.photos())} photo(s)'
            else:
                if newType == 'photo':
                    mTitle = f'{media.parentTitle} ǀ {media.title}'
                elif newType == 'clip':
                    mTitle = media.title
                mSubtitle += f' ǀ {media.year} ǀ Rating: {media.userRating} ǀ Type: {media.media[0].container}'

        json_obj = {
            'title': mTitle,
            'subtitle': mSubtitle,
            'arg': mArg,
            'icon': {
                'path': f'icons/{iType}.webp',
            },
            'mods': {}
        }
        if mType in ['movie', 'episode', 'track', 'clip']:
            streamURL = media.getStreamURL() if mType == 'track' else media.getStreamURL(protocol="dash")
            json_obj['mods'].update({
                'cmd': {
                    'subtitle': 'Press ⏎ to play the media in a VLC instance',
                    'arg': f'_stream;{streamURL};{mTitle}',
                    'icon': {
                        'path': 'icons/vlc.webp',
                    },
                }
            })
        if mType in ['movie', 'show']:
            json_obj['mods'].update({
                'shift': {
                    'subtitle': 'Press ⏎ to get media infos using Movie and TV Show Search workflow',
                    'arg': f'_mtvsearch;{plex_instance.machineIdentifier};{media.librarySectionID};{mType};{media.key}',
                    'icon': {
                        'path': 'icons/movie_and_tv_show_search.webp',
                    },
                }
            })
        items.append(json_obj)

data = servers_file()
if data.get('items'):
    for obj in data['items']:
        plex_baseurl = obj.get('baseURL')
        plex_token = obj.get('plexToken')
        try:
            plex_instance = PlexServer(plex_baseurl, plex_token)
        except:
            display_notification('🚨 Error !', f'Failed to connect to the Plex server \'{obj.get("title")}\'. Check the IP and token')
            exit()
        if '=' in query:
            try:
                for item in query.split('/'):
                    key, value = item.split('=', 1)
                    test_key = aliases_file(key, 'alias_and_long')
                    if not test_key:
                        delist('invalid_FILTERS', items)
                        break
                    elif test_key == 'advancedFilters':
                        value = eval(value)
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
    if not items:
        if not '=' in query:
            delist('no_ELEM', items)
        else:
            delist('invalid_FILTERS', items)
else:
    delist('no_PMS', items)

for item in items:
    if 'skip' in item:
        _type = item.get('skip')
        items = []
        default_element(_type, items, query, query_dict)

output = {
    'items': items
}

print(json.dumps(output))