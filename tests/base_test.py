# this file is used to perform tests. Should be placed in the root folder of the workflow

from plexapi import utils
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from utils import servers_file

data = servers_file()

obj = data['items'][0] # first server used
baseURL = obj.get('baseURL')
plexToken = obj.get('plexToken')
try:
    plex_account = MyPlexAccount(plexToken)
    plex_instance = PlexServer(baseURL, plexToken)
except:
    print('error')
    exit()

test = plex_instance.search('Harry Potter', mediatype='movie')
print(f'{baseURL}{test[0].media[0].parts[0].key}?download=1&X-Plex-Token={plexToken}')

headers = {
    'Accept': 'application/json'
}
params = {
    'query': 'zendaya',
    'limit': 30,
    'searchTypes': 'people',
    'includeMetadata': 1,
    'filterPeople': 1
}

test2 = plex_account.query('https://metadata.provider.plex.tv/library/search?', headers=headers, params=params)
print(test2)

test3 = plex_instance.search('zendaya')
print(test3[0]._data.attrib)