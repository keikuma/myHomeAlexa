#!/usr/bin/sh

ZIPPROG="/c/Program Files/7-Zip/7z.exe"

rm -f package.zip package.zip.tmp
cd .venv/Lib/site-packages
"$ZIPPROG" a ../../../package.zip . -xr!__pycache__ -x!pylint* -x!awscli*
cd ../../..
cd lambda/py
"$ZIPPROG" u ../../package.zip . -xr!__pycache__ 