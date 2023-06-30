import sys
import time
import subprocess
from plexapi.server import PlexServer
from utils import display_notification, servers_file

result = subprocess.Popen(['mdfind', 'kMDItemContentType == "com.apple.application-bundle" && kMDItemFSName == "VLC.app"'], stdout=subprocess.PIPE)
output = result.stdout.read().decode().strip()

if output:
    try:
        _machineID, _type, _key, _media_index, _part_index = sys.argv[1].split(';')[1:]
    except IndexError:
        display_notification('🚨 Error !', 'Something went wrong, please create a GitHub issue')
        exit()
    data = servers_file()
    for obj in data['items']:
        if obj.get('machineIdentifier') == _machineID:
            baseURL = obj.get('baseURL')
            plexToken = obj.get('plexToken')
            try:
                plex_instance = PlexServer(baseURL, plexToken)
            except:
                display_notification('🚨 Error !', f'Failed to connect to the Plex server \'{obj.get("title")}\'. Check the IP and token')
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
            vlc_args = ['vlc', '-I', 'macosx', '--no-xlib', '--no-video-title-show']
            for url, title in zip(streamURLs, streamTitles):
                if _type in ['track', 'album']:
                    command = '--meta-title'
                else:
                    command = '--input-title-format'
                vlc_args.extend([command, title, url])
            vlc_instance = subprocess.Popen(vlc_args)
            time.sleep(1)
            subprocess.call(['osascript', '-e', 'tell application "System Events" to set frontmost of process "VLC" to true'])
            break
else:
    display_notification('🚨 Error !', 'Can\'t locate the VLC app')