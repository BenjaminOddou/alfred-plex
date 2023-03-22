#!/bin/bash

# Install platform agnostic version of plexapi (put the script inside the workflow folder)
mkdir -p lib
pip3 install plexapi -t lib --platform macosx-10.9-x86_64 --only-binary=:all: --upgrade