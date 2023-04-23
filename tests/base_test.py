# this file is used to perform tests. Should be placed in the root folder of the workflow

import sys
sys.path.insert(0, './lib')
from lib.plexapi.server import PlexServer
from lib.plexapi import utils
from utils import servers_file

data = servers_file()

obj = data['items'][0] # first server used
baseURL = obj.get('baseURL')
plexToken = obj.get('plexToken')
try:
    plex_instance = PlexServer(baseURL, plexToken)
except:
    print('error')
    exit()

test = plex_instance.search('Harry Potter', mediatype='movie')
print(f'{baseURL}{test[0].media[0].parts[0].key}?download=1&X-Plex-Token={plexToken}')