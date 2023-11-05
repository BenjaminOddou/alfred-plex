import sys
import json
from utils import display_notification, accounts_file_path, accounts_file, lst_idx, get_plex_account, custom_logger

try:
    _type, _origin, _input = sys.argv[1].split(';')
except IndexError as e:
    display_notification('🚨 Error !', 'Something went wrong, check the logs and create a GitHub issue')
    custom_logger('error', e)
    exit()

if _type == '_delete':
    data = accounts_file()
    for item in data['items']:
        if item.get('uuid') == _input:
            data['items'].remove(item)
            print(f'_delete;{_origin};{_input}', end='')
            display_notification('✅ Sucess !', f'The account {item.get("title")} is removed')
            break
elif _type == '_new':
    if _origin == 'classic':
        credentials = _input.split('\t')
        username, password, otp = lst_idx(credentials, 0), lst_idx(credentials, 1), lst_idx(credentials, 2)
        plex_account = get_plex_account(username=username, password=password, otp=otp)
    elif _origin == 'token':
        plex_account = get_plex_account(auth_token=_input)
    elif _origin == 'sync':
        plex_account = get_plex_account(uuid=_input)
    if not plex_account:
        exit()
    data = accounts_file() if accounts_file() else {'items': []}
    replace = False
    json_obj = {
        'title': f'{plex_account.friendlyName}',
        'subtitle': f'Mail: {plex_account.email} ǀ Plex Pass: {plex_account.subscriptionDescription if plex_account.subscriptionActive else "No"}',
        'authToken': plex_account.authToken,
        'uuid': plex_account.uuid
    }
    if data.get('items'):
        for idx, obj in enumerate(data['items']):
            if obj.get('uuid') == plex_account.uuid:
                replace = True
                data['items'][idx] = json_obj
                print(f'_new;{_origin};{plex_account.uuid}', end='')
                message = f'{plex_account.friendlyName} plex account informations were updated'
                display_notification('✅ Sucess !', message)
                custom_logger('info', message)
                break
    if not replace:
        data['items'].append(json_obj)
        print(f'_new;{_origin};{plex_account.uuid}', end='')
        message = f'The account {plex_account.friendlyName} is added'
        display_notification('✅ Sucess !', message)
        custom_logger('info', message)

try:
    with open(accounts_file_path, 'w') as file:
        json.dump(data, file, indent=4)
except Exception as e:
    display_notification('🚨 Error !', 'Data can\'t be written in accounts.json')
    custom_logger('error', e)