import sys
from utils import display_notification, get_plex_account

try:
    _plex_uuid, _type, _uuid = sys.argv[1].split(';')[1:]
except IndexError:
    display_notification('🚨 Error !', 'Something went wrong, please create a GitHub issue')
    exit()

plex_account = get_plex_account(uuid=_plex_uuid)
_list = plex_account._toOnlineMetadata(plex_account.fetchItem(f'https://metadata.provider.plex.tv/library/metadata/{_uuid}'))[0].guids
mQUERY = 'm' if _type == 'movie' else 't'
mGUID = next((guid.id.split('://')[1] for guid in _list if 'tmdb' in guid.id), None)
print(f'{mQUERY}:{mGUID}', end='')
