#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import re
import argparse
import json
import itertools

parser = argparse.ArgumentParser()
parser.add_argument("-s", "--skill", help="skill invocationName", type=str)
parser.add_argument("-i", "--input", help="music json file", type=str)
parser.add_argument("-o", "--output", help="output languageModel json file", type=str)
args = parser.parse_args()

if (not args.input) or (not args.output) or (not args.skill):
    parser.print_help()
    exit(1)

with open(args.input, encoding='utf-8') as f:
    mdb = json.load(f)

artistdict = mdb['artist']
albumdict = mdb['album']
titledict = mdb['title']
musicdict = mdb['music']

artistid = {}
albumid = {}
titleid = {}

for i, d in (zip([artistid, albumid, titleid], [artistdict, albumdict, titledict])):
    for name, v in (d.items()):
        id = v['id']
        if len(id) > 100:
            idarr = id.split("/")
            id = idarr[0]
        yomi = v['yomi'][:140]
        name = name[:140]
        if id in i:
            if not 'synonyms' in i[id]['name']:
                i[id]['name']['synonyms'] = []
            if not name in i[id]['name']['synonyms']:
                i[id]['name']['synonyms'].append(name)
            if name != yomi:
                i[id]['name']['synonyms'].append(yomi)
        else:
            i[id] = {'id': id, 'name': { 'value': name}}
            if name != yomi:
                if 'synonyms' in i[id]['name']:
                    i[id]['name'].append(yomi)
                else:
                    i[id]['name']['synonyms'] = [ yomi ]

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
                "name": "PlayMusic",
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
                    "{Artist} の曲をかけて",
                    "{Artist} の曲を再生して",
                    "{Album} をかけて",
                    "{Album} を再生して",
                    "{Artist} のアルバム {Album} をかけて",
                    "{Artist} のアルバム {Album} を再生して",
                    "{Artist} のアルバム {Album} をシャッフル再生して",
                    "{Title} をかけて",
                    "{Title} を再生して",
                    "{Artist} の {Title} をかけて",
                    "{Artist} の {Title} を再生して",
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
                "name": "PlayMusic",
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
    json.dump(model, f, ensure_ascii=False, sort_keys=False, indent=4)
