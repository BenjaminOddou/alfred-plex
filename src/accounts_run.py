import sys
from utils import display_notification, get_plex_account, custom_logger

try:
    _type, _subtype, accountUUID, _key, _msg, _query = sys.argv[1].split(";")
    plex_account = get_plex_account(uuid=accountUUID)
    if _type == "_delete" and _subtype == "device":
        if _query.lower() != "yes":
            display_notification("⚠️ Warning !", "Action canceled")
            print(f"_rerun;{accountUUID};3;device;{_key}", end="")
        else:
            if _msg == "true":
                print(f"_delete;account;{accountUUID}", end="")
            else:
                print(f"_rerun;{accountUUID};2;device;None", end="")
            device = plex_account.device(clientId=_key)
            device.delete()
            message = f"The device '{device.name} - {device.platform} {device.platformVersion}' is removed"
            display_notification("✅ Success !", message)
            custom_logger("info", message)
    elif _type == "_watchlist":
        ratingKey = _key.rsplit("/", 1)[-1]
        if _query == "account":
            print(f"_rerun;{accountUUID};2;watchlist;None", end="")
        if _query in ["discover", "search"]:
            print(_query, end="")
        if _subtype == "delete":
            plex_account.query(
                f"{plex_account.METADATA}/actions/removeFromWatchlist?ratingKey={ratingKey}",
                method=plex_account._session.put,
            )
        elif _subtype == "add":
            plex_account.query(
                f"{plex_account.METADATA}/actions/addToWatchlist?ratingKey={ratingKey}",
                method=plex_account._session.put,
            )
        display_notification("✅ Success !", _msg)
        custom_logger("info", _msg)
except IndexError as e:
    display_notification(
        "🚨 Error !", "Something went wrong, check the logs and create a GitHub issue"
    )
    custom_logger("error", e)
