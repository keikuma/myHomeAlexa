#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
楽曲データのJSONから、Alexaのmodelとスキル用のデータベースを生成します
"""

import re
import unicodedata
import argparse
import json
import pickle
from collections import defaultdict
from simstring.feature_extractor.character_ngram import CharacterNgramFeatureExtractor
from simstring.database.dict import DictDatabase

parser = argparse.ArgumentParser()
parser.add_argument("-s", "--skill", help="skill invocationName", type=str)
parser.add_argument("-i", "--input", help="music json file", type=str)
parser.add_argument("-o", "--output", help="output languageModel json file", type=str)
parser.add_argument("-d", "--database", help="output database for skill json file", type=str)
parser.add_argument("-p", "--pickle", help="output for SimString pickled database", type=str)
parser.add_argument("--debug", help="for debug", action='count')
args = parser.parse_args()

if (not args.input) or (not args.output) or (not args.skill):
    parser.print_help()
    exit(1)
MY_NAME = args.skill

with open(args.input, encoding='utf-8') as f:
    mdb = json.load(f)

re_hiragana = re.compile(r'[ぁ-ゔ]')
def yomi_normalize(s):
    """ かな読みの正規化を行う """
    s = ''.join([i for i in list(s) if re.match(r"^(L|N)", unicodedata.category(i)[0])])
    s = re_hiragana.sub(lambda x: chr(ord(x.group(0)) + ord('ァ') - ord('ぁ')), s)
    s = re.sub(r'ー', r'', s)
    s = re.sub(r'ヰ', r'イ', s)
    s = re.sub(r'ヱ', r'エ', s)
    s = re.sub(r'ヂ', r'ジ', s)
    s = re.sub(r'ヅ', r'ズ', s)
    s = re.sub(r'ヮ', r'ア', s)
    s = re.sub(r'(ツ|テ)ィ', r'チ', s)
    s = re.sub(r'ク(サ|シ|ス|ソ)', r'キ\1', s)
    s = re.sub(r'ヴ(ァ|ア)', r'バ', s)
    s = re.sub(r'ヴ(ィ|イ)', r'ビ', s)
    s = re.sub(r'ヴ(ェ|エ)', r'ベ', s)
    s = re.sub(r'ヴ(ォ|オ)', r'ボ', s)
    s = re.sub(r'ファ', r'ハ', s)
    s = re.sub(r'フィ', r'ヒ', s)
    s = re.sub(r'フェ', r'ヘ', s)
    s = re.sub(r'フォ', r'ホ', s)
    s = re.sub(r'グァ', r'ガ', s)
    s = re.sub(r'シェ', r'セ', s)
    s = re.sub(r'ジェ', r'ゼ', s)
    s = re.sub(r'トゥ', r'ト', s)
    s = re.sub(r'ツ', r'ト', s)
    s = re.sub(r'ドゥ', r'ド', s)
    s = re.sub(r'デュ', r'ジュ', s)
    s = re.sub(r'テュ', r'チュ', s)
    s = re.sub(r'イェ', r'エ', s)
    s = re.sub(r'ッ', r'', s)
    return s

artistdict = mdb['artist']
albumdict = mdb['album']
titledict = mdb['title']
musicdict = mdb['music']
artistid = {}
albumid = {}
titleid = {}
artistYomiDict = {}
albumYomiDict = {}
titleYomiDict = {}

# model用の辞書と一緒に、読み検索用の辞書を作る
for i, d, y in zip([artistid, albumid, titleid],
                   [artistdict, albumdict, titledict],
                   [artistYomiDict, albumYomiDict, titleYomiDict]):
    for name, v in d.items():
        item_id = v['id']
        idarr = item_id.split("/")
        for pri, k in enumerate([name, v['yomi'], yomi_normalize(name), yomi_normalize(v['yomi'])]):
            for j in idarr:
                if not k in y:
                    # 最小プライオリティのものだけ書けば良い
                    y[k] = {'id': j, 'priority': pri}
        if len(item_id) > 100:
            item_id = idarr[0]
        yomi = v['yomi'][:140]
        name = name[:140]
        if item_id in i:
            if not 'synonyms' in i[item_id]['name']:
                i[item_id]['name']['synonyms'] = []
            if not name in i[item_id]['name']['synonyms']:
                i[item_id]['name']['synonyms'].append(name)
            if name != yomi:
                i[item_id]['name']['synonyms'].append(yomi)
        else:
            i[item_id] = {'id': item_id, 'name': {'value': name}}
            if name != yomi:
                if 'synonyms' in i[item_id]['name']:
                    i[item_id]['name'].append(yomi)
                else:
                    i[item_id]['name']['synonyms'] = [yomi]

model = {
    'languageModel':{
        'invocationName': args.skill,
        'intents':[
            {
                "name": "AMAZON.CancelIntent",
                "slots": [],
                "samples": []
            },
            {
                "name": "AMAZON.HelpIntent",
                "slots": [],
                "samples": []
            },
            {
                "name": "AMAZON.StopIntent",
                "slots": [],
                "samples": []
            },
            {
                "name": "AMAZON.PauseIntent",
                "slots": [],
                "samples": []
            },
            {
                "name": "AMAZON.ResumeIntent",
                "slots": [],
                "samples": []
            },
            {
                "name": "PlayMusicIntent",
                "slots": [
                    {
                        "name": "Artist",
                        "type": "ArtistList"
                    },
                    {
                        "name": "Album",
                        "type": "AlbumList"
                    },
                    {
                        "name": "Title",
                        "type": "TitleList"
                    }
                ],
                "samples": [
                    MY_NAME + "で {Artist} の曲をかけて",
                    MY_NAME + "で {Artist} の曲を再生して",
                    MY_NAME + "で {Album} をかけて",
                    MY_NAME + "で {Album} を再生して",
                    MY_NAME + "で {Artist} のアルバム {Album} をかけて",
                    MY_NAME + "で {Artist} のアルバム {Album} を再生して",
                    MY_NAME + "で {Artist} のアルバム {Album} をシャッフル再生して",
                    MY_NAME + "で {Title} をかけて",
                    MY_NAME + "で {Title} を再生して",
                    MY_NAME + "で {Artist} の {Title} をかけて",
                    MY_NAME + "で {Artist} の {Title} を再生して",
                ]
            }
        ],
        "types": [
            {
                "name": "ArtistList",
                "values": [{'id': k, **v} for k, v in artistid.items()]
            },
            {
                "name": "AlbumList",
                "values": [{'id': k, **v} for k, v in albumid.items()]
            },
            {
                "name": "TitleList",
                "values": [{'id': k, **v} for k, v in titleid.items()]
            }
        ]
    },
    "dialog": {
        "intents": [
            {
                "name": "PlayMusicIntent",
                "confirmationRequired": False,
                "prompts": {},
                "slots": [
                    {
                        "name": "Artist",
                        "type": "ArtistList",
                        "confirmationRequired": False,
                        "elicitationRequired": False,
                        "prompts": {
                            "elicitation": "Elicit.Intent-PlayMusic.IntentSlot-Artist"
                        }
                    },
                    {
                        "name": "Album",
                        "type": "AlbumList",
                        "confirmationRequired": False,
                        "elicitationRequired": False,
                        "prompts": {
                            "elicitation": "Elicit.Intent-PlayMusic.IntentSlot-Album"
                        }
                    },
                    {
                        "name": "Title",
                        "type": "TitleList",
                        "confirmationRequired": False,
                        "elicitationRequired": False,
                        "prompts": {
                            "elicitation": "Elicit.Intent-PlayMusic.IntentSlot-Title"
                        }
                    }
                ]
            }
        ]
    },
    "prompts": [
        {
            "id": "Elicit.Intent-PlayMusic.IntentSlot-Artist",
            "variations": [
                {
                    "type": "PlainText",
                    "value": "誰の曲を再生しますか?"
                }
            ]
        },
        {
            "id": "Elicit.Intent-PlayMusic.IntentSlot-Album",
            "variations": [
                {
                    "type": "PlainText",
                    "value": "どのアルバムを再生しますか?"
                }
            ]
        },
        {
            "id": "Elicit.Intent-PlayMusic.IntentSlot-Title",
            "variations": [
                {
                    "type": "PlainText",
                    "value": "どの曲を再生しますか?"
                }
            ]
        }
    ]
}

with open(args.output, 'wt', encoding='utf-8', newline='\n') as f:
    if args.debug:
        json.dump(model, f, ensure_ascii=False, sort_keys=False, indent=4)
    else:
        json.dump(model, f, ensure_ascii=False, sort_keys=False)

if args.database:
    # idからインデックスする辞書として、musicdbを作る
    musicdb = {'artist': defaultdict(lambda: {'name':'', 'album': set(), 'title': set()}),
               'album': defaultdict(lambda: {'name': '', 'title': set()}),
               'title': {}}
    for item_id, entry in artistid.items():
        musicdb['artist'][item_id] = {'name': entry['name'], 'album': set(), 'title': set()}
    for item_id, entry in albumid.items():
        musicdb['album'][item_id] = {'name': entry['name'], 'title': set()}
    for artist in mdb['music'].values():
        for album in artist['album'].values():
            if album['albumartist_id']:
                musicdb['artist'][album['albumartist_id']]['album'].add(album['id'])
            for name, title in album['title'].items():
                musicdb['title'][title['id']] = title
                musicdb['title'][title['id']]['title'] = name
                musicdb['artist'][title['artist_id']]['title'].add(title['id'])
                if 'album_id' in title:
                    musicdb['album'][title['album_id']]['title'].add(title['id'])
    # listに詰め直し
    for entry in musicdb['artist'].values():
        entry['album'] = list(entry['album'])
        entry['title'] = list(entry['title'])
    for entry in musicdb['album'].values():
        sort_temp = sorted(entry['title'], key=lambda id: musicdb['title'][id]['track'])
        entry['title'] = sorted(sort_temp, key=lambda id: musicdb['title'][id]['disc'])

    # json出力
    output = {'artist': artistYomiDict,
              'album': albumYomiDict,
              'title': titleYomiDict,
              'music': musicdb}
    with open(args.database, 'wt', encoding='utf-8', newline='\n') as f:
        if args.debug:
            json.dump(output, f, ensure_ascii=False, sort_keys=False, indent=4)
        else:
            json.dump(output, f, ensure_ascii=False, sort_keys=False)

    # SimString 辞書
    if args.pickle:
        with open(args.pickle, "wb") as fw_simstring:
            artist_db = DictDatabase(CharacterNgramFeatureExtractor(2))
            for yomi in artistYomiDict.keys():
                artist_db.add(yomi)
            album_db = DictDatabase(CharacterNgramFeatureExtractor(2))
            for yomi in albumYomiDict.keys():
                album_db.add(yomi)
            title_db = DictDatabase(CharacterNgramFeatureExtractor(2))
            for yomi in titleYomiDict.keys():
                title_db.add(yomi)
            simstring_dict = { 'artist': artist_db, 'album': album_db, 'title': title_db}
            pickle.dump(simstring_dict, fw_simstring, pickle.HIGHEST_PROTOCOL)

