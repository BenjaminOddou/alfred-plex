import sys
import subprocess
from utils import display_notification, servers_file, media_player, custom_logger
from plexapi.server import PlexServer

result = subprocess.Popen(['mdfind', f'kMDItemContentType == "com.apple.application-bundle" && kMDItemFSName == "{media_player.upper()}.app"'], stdout=subprocess.PIPE)
output = result.stdout.read().decode().strip()

if output:
    try:
        _machineID, _type, _key, _media_index, _part_index = sys.argv[1].split(';')[1:]
    except IndexError as e:
        display_notification('🚨 Error !', 'Something went wrong, check the logs and create a GitHub issue')
        custom_logger('error', e)
        exit()
    data = servers_file()
    for obj in data['items']:
        if obj.get('machineIdentifier') == _machineID:
            baseURL = obj.get('baseURL')
            plexToken = obj.get('plexToken')
            try:
                plex_instance = PlexServer(baseURL, plexToken)
            except Exception as e:
                display_notification('🚨 Error !', f'Failed to connect to the plex server {obj.get("title")}')
                custom_logger('error', e)
                exit()
            media = plex_instance.fetchItem(_key)
            if _type == 'album':
                streamURLs = [f'{baseURL}{track.media[0].parts[0].key}?X-Plex-Token={plexToken}' for track in media.tracks()]
                streamTitles = [f'{media.parentTitle} ǀ {media.title} ({media.year}) ǀ {track.title} {track.trackNumber} / {len(media.tracks())}' for track in media.tracks()]
            else:
                streamURLs = [f'{baseURL}{media.media[int(_media_index)].parts[int(_part_index)].key}?X-Plex-Token={plexToken}']
                if _type == 'episode':
                    streamTitles = [f'{media.grandparentTitle} ǀ {media.title} ǀ {media.seasonEpisode}']
                elif _type == 'movie':
                    streamTitles = [f'{media.title} ({media.year})']
                elif _type == 'track':
                    streamTitles = [f'{media.grandparentTitle} ǀ {media.parentTitle} ({media.album().year}) ǀ {media.title} {media.trackNumber} / {len(media.album().tracks())}']
                elif _type == 'clip':
                    streamTitles = [media.title]
            mp_args = [media_player]
            if media_player == 'vlc':
                mp_args.extend(['-I', 'macosx', '--no-xlib', '--no-video-title-show', '--video-on-top'])
                command = '--meta-title' if _type in ['track', 'album'] else '--input-title-format'
                for url, title in zip(streamURLs, streamTitles):
                    mp_args.extend([command, title, url])
            elif media_player == 'iina':
                mp_args.extend(['--music-mode']) if _type in ['track', 'album'] else None
                for url, title in zip(streamURLs, streamTitles):
                    mp_args.extend([url, f'--mpv-force-media-title={title}', '--no-stdin'])
            mp_instance = subprocess.Popen(mp_args)
            break
else:
    warn = f'Can\'t locate the {media_player} app'
    display_notification('⚠️ Warning !', warn)
    custom_logger('warning', warn)