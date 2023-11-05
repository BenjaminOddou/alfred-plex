# this file is used to perform tests. Should be placed in the root folder of the workflow

from utils import servers_file, accounts_file, get_plex_account
from plexapi import utils
from plexapi.server import PlexServer

data2 = accounts_file()

server = servers_file()['items'][0] # first server used
account = accounts_file()['items'][0] # first account used
try:
    plex_instance = PlexServer(server.get('baseURL'), server.get('plexToken'))
    plex_account = get_plex_account(uuid=account.get('uuid'))
except:
    print('error')
    exit()

test = plex_account.resources()
print(utils.toJson(test))

test = plex_instance.search('Harry Potter', mediatype='movie')
print(f'{plex_instance._baseurl}{test[0].media[0].parts[0].key}?download=1&X-Plex-Token={plex_instance._token}')