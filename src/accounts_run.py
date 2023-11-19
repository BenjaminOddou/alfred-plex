import sys
from utils import display_notification, get_plex_account, custom_logger

try:
    _type, _subtype, accountUUID, _key, _msg, _query = sys.argv[1].split(';')
except IndexError as e:
    display_notification('🚨 Error !', 'Something went wrong, check the logs and create a GitHub issue')
    custom_logger('error', e)
    exit()

plex_account = get_plex_account(uuid=accountUUID)
if not plex_account:
    exit()
else:
    if _type == '_delete' and _subtype == 'device':
        if _query.lower() != 'yes':
            display_notification('⚠️ Warning !', 'Action canceled')
            print(f'_rerun;{accountUUID};3;device;{_key}', end='')
        else:
            if _msg == 'true':
                print(f'_delete;account;{accountUUID}', end='')
            else:
                print(f'_rerun;{accountUUID};2;device;None', end='')
            try:
                device = plex_account.device(clientId=_key)
                device.delete()
                message = f'The device \'{device.name} - {device.platform} {device.platformVersion}\' is removed'
                display_notification('✅ Success !', message)
                custom_logger('info', message)
            except Exception as e:
                display_notification('🚨 Error !', 'Something went wrong, check the logs and create a GitHub issue')
                custom_logger('error', e)

