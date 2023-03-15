import sys
import time
import subprocess
from utils import display_notification

# Get stream_url from user input
stream_url = sys.argv[1]

# Get stream_title from plex (avoid exposing plex_token)
stream_title = sys.argv[2]

# Run the shell command to find the VLC app path
result = subprocess.Popen(['mdfind', 'kMDItemContentType == "com.apple.application-bundle" && kMDItemFSName == "VLC.app"'], stdout=subprocess.PIPE)
output = result.stdout.read().decode().strip()

# If VLC app is found, pass stream_url to VLC and bring it to the front
if output:
    vlc_instance = subprocess.Popen(['vlc', '-I', 'macosx', '--no-xlib', '--no-video-title-show', '--meta-title', stream_title, stream_url])
    time.sleep(1)
    # Bring VLC to the front using AppleScript
    subprocess.call(['osascript', '-e', 'tell application "System Events" to set frontmost of process "VLC" to true'])
else:
    display_notification('🚨 Error !', 'Can\'t locate the VLC app')