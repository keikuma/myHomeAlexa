#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
beets の出力から、可能な限りの情報を収集して、後処理用のJSONファイルを生成する
"""

import re
import os
import codecs
import argparse
import json
import unicodedata
import itertools

# pylint: disable-msg=C0301

# iTunes music title list format:
#
# [path]\t[albumartist]\t[album]\t[artist]\t[disc]\t[track]\t[title]\t[mb_albumartistid]\t[mb_albumid]\t[mb_artistid]\t[mb_trackid]\n
#
# https://github.com/beetbox/beets
# beet import -CWA "$HOME/Music/iTunes/iTunes Media/Music/"
# fmt=`echo -e '$path\t$albumartist\t$album\t$artist\t$disc\t$track\t$title\t$mb_albumartistid\t$mb_albumid\t$mb_artistid\t$mb_trackid'`
# beet list -f "$fmt"

# pylint: enable-msg=C0301

def isReadable(s):
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^\s*", "", s)
    s = re.sub(r"\s*$", "", s)
    if not len(s):
        return False
    conv = codecs.encode(s, 'cp932', errors='replace')
    conv2 = codecs.decode(conv, 'cp932')
    n = len(re.findall(r'\?', conv2)) - len(re.findall(r'\?', s))
    if n > len(s) * 0.2:
        return False
    return True

def split_path(path):
    pathlist = []
    head, tail = path_parser.split(path)
    while tail:
        pathlist.insert(0, tail)
        head, tail = path_parser.split(head)
    return pathlist

def word_trim(w):
    w = re.sub(r"^\d+:\d+:\d+$", "", w)
    w = re.sub(r"^[\s~<>\"\(\)\[\]{}\\\-_;:,]+", "", w)
    w = re.sub(r"[\s~<>\"\(\)\[\]{}\\\-_;:]+$", "", w)
    w = re.sub(r"[~<>\"\(\)\[\]{}\\\-_;:]", " ", w)
    w = re.sub(r"^[\s!\?]*$", "", w)
    return w.split()

artistId = 0
albumId = 0
titleId = 0

parser = argparse.ArgumentParser()
parser.add_argument("-l", "--list", help="file of iTunes music title list.", type=str)
parser.add_argument("-d", "--dict", help="file of word to kana dictionary.", type=str)
parser.add_argument("-o", "--output", help="output json file", type=str)
parser.add_argument("--path_parser", help="select path parser", type=str, choices=['posix', 'win'])
parser.add_argument("--pathdrop", help="drop leading path", type=int, default=6)
args = parser.parse_args()

if (not args.list) or (not args.output):
    parser.print_help()
    exit(1)

if args.path_parser == 'posix':
    import posixpath
    path_parser = posixpath
elif args.path_parser == 'win':
    import ntpath
    path_parser = ntpath
else:
    path_parser = os.path

musicList = []
artistDict = {}
albumDict = {}
titleDict = {}
musicDict = {}

with open(args.list, "rt", encoding='utf-8') as f:
    for line in f:
        line = line.rstrip('\n')
        line = line.rstrip('\r')
        (path, albumartist, album, artist, disc, track, title,
         albumartist_id, album_id, artist_id, title_id) = line.split('\t')
        path = unicodedata.normalize('NFC', path)
        path_list = split_path(path)
        if args.pathdrop:
            path_list = path_list[args.pathdrop:]
        path = path_parser.join(*path_list)
        dirname, fname = path_parser.split(path)
        base, ext = path_parser.splitext(fname)
        res = re.match(r"^([0-9\-]+)\s", fname)
        if res:
            track_from_name = res.group(0)
        if not isReadable(title):
            title = base
            title = re.sub(r"^([0-9\-]+)\s", "", title)
        if not track and track_from_name:
            track = track_from_name
        if not isReadable(albumartist):
            albumartist = path_list[0]
        if not isReadable(album):
            album = path_list[1]
        title = re.sub(r"\s\d{4}\-\d{2}\-\d{2}\s\d{2}:\d{2}:\d{2}$", "", title)
        if isReadable(title):
            albumartist = unicodedata.normalize('NFKC', albumartist)
            artist = unicodedata.normalize('NFKC', artist)
            if not artist:
                artist = albumartist
            album = unicodedata.normalize('NFKC', album)
            title = unicodedata.normalize('NFKC', title)
            musicList.append({'path': path, 'albumartist': albumartist, 'album': album, 'artist': artist,
                              'disc': disc, 'track': track, 'title':title, 'albumartist_id': albumartist_id,
                              'album_id': album_id, 'artist_id': artist_id, 'title_id': title_id})
            if (albumartist_id and albumartist and not albumartist_id in artistDict):
                artistDict[albumartist] = {'id': albumartist_id}
            if (artist_id and not artist_id in artistDict):
                artistDict[artist] = {'id': artist_id}
            if (album_id and not album_id in albumDict):
                albumDict[album] = {'id': album_id}
            if (title_id and not title_id in titleDict):
                titleDict[title] = {'id': title_id}

for m in musicList:
    if not m['albumartist_id']:
        if m['albumartist'] in artistDict:
            m['albumartist_id'] = artistDict[m['albumartist']]['id']
        else:
            m['albumartist_id'] = 'ART{:08d}'.format(artistId)
            artistId += 1
    if not m['artist_id']:
        if m['artist'] in artistDict:
            m['artist_id'] = artistDict[m['artist']]['id']
        else:
            m['artist_id'] = 'ART{:08d}'.format(artistId)
            artistId += 1
    if not m['albumartist'] in musicDict:
        artistDict[m['albumartist']] = {'id': m['albumartist_id']}
        musicDict[m['albumartist']] = {'id': m['albumartist_id'], 'album': {}}
    albums = musicDict[m['albumartist']]['album']
    if not m['album_id']:
        if m['album'] in albums:
            m['album_id'] = albums[m['album']]['id']
        else:
            m['album_id'] = 'ALB{:08d}'.format(albumId)
            albumId += 1
    if not m['album'] in albums:
        albumDict[m['album']] = {'id': m['album_id']}
        albums[m['album']] = {
            'id': m['album_id'], 'albumartist_id': m['albumartist_id'], 'title':{}
        }
    titles = albums[m['album']]['title']
    if not m['title_id']:
        if m['title'] in titles:
            m['title_id'] = titles[m['title']]['id']
        else:
            m['title_id'] = 'TTL{:08d}'.format(titleId)
            titleId += 1
    if not m['title'] in titles:
        titleDict[title] = {'id': m['title_id']}
        if re.match(r"(Karaoke|karaoke|KARAOKE|less vocal|カラオケ)", m['title']):
            iskaraoke = True
        else:
            iskaraoke = False
        titles[m['title']] = {
            'id': m['title_id'], 'artist': m['artist'], 'artist_id': m['artist_id'],
            'disc': m['disc'], 'track': m['track'], 'karaoke':iskaraoke, 'path': m['path'],
            'album_id': m['album_id'], 'albumartist_id': m['albumartist_id']
        }

if not args.dict:
    words = set()
    for name in artistDict.keys() | albumDict.keys() | titleDict.keys():
        arr = re.findall(r"[!-~]+", name)
        for w in arr:
            words |= set(word_trim(w))
    with open(args.output, "wt", encoding='utf-8', newline='\n') as f:
        json.dump(list(words), f, ensure_ascii=False, sort_keys=True, indent=4)
else:
    with open(args.dict, encoding='utf-8') as f:
        yomidic = json.load(f)
    for name, entry in itertools.chain(artistDict.items(), albumDict.items(), titleDict.items()):
        def repl(matchobj):
            arr = word_trim(matchobj.group(0))
            return " ".join([yomidic.get(w, w) for w in arr])
        yomi = re.sub(r"[!-~]+", repl, name)
        entry['yomi'] = yomi
    data = {'artist': artistDict, 'album': albumDict, 'title': titleDict, 'music': musicDict}
    with open(args.output, "wt", encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True)
