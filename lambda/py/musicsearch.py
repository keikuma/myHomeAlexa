#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
音楽ライブラリから状況に応じた楽曲選択を行う
"""

import argparse
import musicdb
import util

LOGGER = util.get_logger(__name__)

class PlayMusic:
    """ 楽曲セレクタ """
    def __init__(self):
        """ initialize """
        self.music_db = musicdb.MusicDb()
        return

    def get_play_list(self, artist_id=None, album_id=None, title_id=None,
                      artist_name=None, album_name=None, title_name=None):
        """ 楽曲選択を行う """

        # IDが来て、マッチすれば信頼性Max
        if title_id:
            title = self.music_db.get_title_by_id(title_id)
            if title:
                return {'type': 'title', 'title': title, 'reliability': 5}
        elif album_id:
            album = self.music_db.get_album_by_id(album_id)
            if album:
                return {'type': 'album', 'album': album, 'reliability': 5}
        elif artist_id:
            artist = self.music_db.get_artist_by_id(artist_id)
            if artist:
                return {'type': 'artist', 'artist': artist, 'reliability': 5}

        # 一致検索が次点
        elif title_name:
            title_id = self.music_db.get_title_by_name(title_name, 1)
            if title_id:
                title = self.music_db.get_title_by_id(title_id)
                return {'type': 'title', 'title': title, 'reliability': 4}
        elif album_name:
            album_id = self.music_db.get_album_by_name(album_name, 1)
            if album_id:
                album = self.music_db.get_album_by_id(album_id)
                return {'type': 'album', 'album': album, 'reliability': 4}
        elif artist_name:
            artist_id = self.music_db.get_artist_by_name(artist_name, 1)
            if artist_id:
                artist = self.music_db.get_artist_by_id(artist_id)
                return {'type': 'artist', 'artist': artist, 'reliability': 4}

        # IDでヒットしたけれど、スロットが違う
        for i, item_id in enumerate([artist_id, album_id, title_id]):
            for j, item_type in enumerate(['artist', 'album', 'title']):
                if item_id and i != j:
                    item = self.music_db.get_item_by_id(item_type, item_id)
                    if item:
                        return {'type': item_type, item_type: item, 'reliability': 3}

        # スロット関係なく部分一致
        for i, name in enumerate([artist_name, album_name, title_name]):
            if name:
                for j, item_type in enumerate(['artist', 'album', 'title']):
                    item_id = self.music_db.get_entry_by_name(item_type, name)
                    if item_id:
                        item = self.music_db.get_item_by_id(item_type, item_id)
                        return {'type': item_type, item_type: item,
                                'reliability': 2 if i == j else 1}
        # 何も見つけられなかった
        return None


def module_test():
    """ module test """
    play_music = PlayMusic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--artistid", help="ArtistId", type=str)
    parser.add_argument("--albumid", help="AlbumId", type=str)
    parser.add_argument("--titleid", help="TitleId", type=str)
    parser.add_argument("--artistname", help="ArtistName", type=str)
    parser.add_argument("--albumname", help="AlbumName", type=str)
    parser.add_argument("--titlename", help="TitleName", type=str)
    args = parser.parse_args()
    result_list = play_music.get_play_list(artist_id=args.artistid, artist_name=args.artistname,
                                           album_id=args.albumid, album_name=args.albumname,
                                           title_id=args.titleid, title_name=args.titlename)
    print(result_list)
    return True

if __name__ == '__main__':
    module_test()