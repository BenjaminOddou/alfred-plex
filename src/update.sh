#!/bin/bash
# Refresh the bundled pure-python dependencies (run from the workflow folder: ./update.sh).
# plexapi >= 4.18 requires Python 3.10+.
set -euo pipefail
cd "$(dirname "$0")"
rm -rf lib
python3 -m pip install plexapi -t lib --upgrade --no-compile \
  --platform macosx-10.9-x86_64 --python-version 3.10 --only-binary=:all:
rm -rf lib/bin
find lib -name "__pycache__" -prune -exec rm -rf {} +
