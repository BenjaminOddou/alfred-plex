# this file is used to perform tests. Should be placed in the root folder of the workflow

from utils import servers_file
from plexapi import utils
from plexapi.server import PlexServer

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