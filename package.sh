#!/usr/bin/sh

ZIPPROG="/c/Program Files/7-Zip/7z.exe"

rm -f package.zip package.zip.tmp
cd .venv/Lib/site-packages
"$ZIPPROG" a ../../../package.zip . -xr!__pycache__ -xr!*.exe -xr!*.pyc -xr!*.pyd -x!pylint* -x!boto* -x!awscli* -x!*.dist_info
cd ../../..
cd lambda/py
"$ZIPPROG" u ../../package.zip . -xr!__pycache__ -xr!*-debug.* -xr!*.pyc -xr!*.pyd
