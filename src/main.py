"""Alfred Plex entry point (called by every script of the workflow).

Keep this file compatible with old Pythons: it only checks the version and
hands over to the ``alfred_plex`` package.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "lib"))
sys.path.insert(0, ROOT)

MIN_PYTHON = (3, 10)


def python_too_old():
    version = "%d.%d" % sys.version_info[:2]
    title = "Python %d.%d+ is required (found %s)" % (MIN_PYTHON + (version,))
    subtitle = "Install it with 'brew install python' or from python.org, then retry"
    return json.dumps({"items": [{"title": title, "subtitle": subtitle, "valid": False,
                                  "icon": {"path": "icons/base/info.webp"}}]})


if __name__ == "__main__":
    if sys.version_info < MIN_PYTHON:
        sys.stdout.write(python_too_old())
        sys.exit(0)
    from alfred_plex.cli import main

    sys.exit(main())
