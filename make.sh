#!/usr/bin/bash

#python musicdb/musiclist2json.py -l musicdb/iTunes_list.txt -o musicdb/words.json --path_parser posix
# words.json を加工して、カタカナ読みテーブル translate.json を用意する
python musicdb/musiclist2json.py -l musicdb/iTunes_list.txt -d musicdb/translate.json -o musicdb/list.json --path_parser posix
if [ ! -d lambda/py/data ]; then
    mkdir lambda/py/data
fi
python makelanguagemodel.py -i musicdb/list.json -o models/ja-JP.json -s "おうちサーバー" -d lambda/py/data/database.json
