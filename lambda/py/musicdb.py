#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
音楽ライブラリからの検索を行う
"""

import json
import os
import util
import pickle
from simstring.measure.jaccard import JaccardMeasure
from simstring.database.dict import DictDatabase
from simstring.searcher import Searcher

LOGGER = util.get_logger(__name__)

class MusicDb:
    """
    database.json の実体化
    """
    def __init__(self):
        """ initialize """
        dirname = os.path.dirname(__file__)
        path = os.path.join(dirname, 'data', 'database.json')
        with open(path, 'rt', encoding='utf-8') as file_pointer:
            self.data_base = json.load(file_pointer)
        path = os.path.join(dirname, 'data', 'simstring.db')
        with open(path, 'rb') as db_file_pointer:
            self.simstring_db = pickle.load(db_file_pointer)
        print(type(self.simstring_db))
        self.sercher = {}
        for item in ['artist', 'album', 'title']:
            self.sercher[item] = Searcher(self.simstring_db[item], JaccardMeasure())
        return

    def get_db(self):
        """ dbアクセサ """
        return self.data_base

    def get_title_by_id(self, title_id):
        """ Title ID から Titleの情報を得る """
        title = self.data_base['music']['title'].get(title_id, None)
        if not title:
            return
        return title

    def get_artist_by_id(self, artist_id):
        """ Artist ID から Artistの情報を得る """
        artist = self.data_base['music']['artist'].get(artist_id, None)
        if not artist:
            return
        return artist

    def get_album_by_id(self, album_id):
        """ Album ID から Albumの情報を得る """
        album = self.data_base['music']['album'].get(album_id, None)
        if not album:
            return
        return album

    def get_titie_list_by_album_id(self, album_id):
        """ Album ID から タイトルIDのリストを得る """
        album = self.data_base['music']['album'].get(album_id, None)
        if not album:
            return
        
        return album

    def get_entry_by_name(self, entry_type, entry_name, level=0):
        """ 名前からIDを得る """

        # 完全マッチ
        entry_dict = self.data_base[entry_type]
        entry = entry_dict.get(entry_name, None)
        if entry:
            return entry['id']
        if level > 3:
            return None

        # 読み正規化マッチ
        norm_name = util.yomi_normalize(entry_name)
        entry = entry_dict.get(norm_name, None)
        if entry:
            return entry['id']
        if level > 2:
            return None

        # SimString検索
        indexes = self.sercher[entry_type].ranked_search(entry_name, 0.3)
        if indexes:
            return entry_dict[indexes[0][1]]['id']
        if level > 1:
            return None

        # 全文検索
        min_priority = 99
        entry_id = None
        for key, value in entry_dict.items():
            if entry_name in key:
                if value['priority'] < min_priority:
                    entry_id = value['id']
                    min_priority = value['priority']
            if norm_name in key:
                if value['priority'] + 10 < min_priority:
                    entry_id = value['id']
                    min_priority = value['priority'] + 10
            if min_priority == 0:
                return entry_id
        return entry_id

    def get_artist_by_name(self, artist_name):
        """ アーティスト名から Artist ID を得る """
        return self.get_entry_by_name('artist', artist_name)

    def get_album_by_name(self, album_name):
        """ アルバム名から Album ID を得る """
        return self.get_entry_by_name('album', album_name)

    def get_title_by_name(self, title_name):
        """ タイトル名から Title ID を得る """
        return self.get_entry_by_name('title', title_name)

def module_test():
    music_db = MusicDb()
    print(music_db.get_title_by_id('d7a1d8dc-16c9-4a8e-a654-a7fdbf47aa15'))
    print(music_db.get_title_by_id('TTL00007297'))
    print(music_db.get_artist_by_name('パバロッティ'))
    print(music_db.get_artist_by_name('サチモス'))
    print(music_db.get_album_by_name('まどか☆マギカ'))
    print(music_db.get_album_by_name('魔法少女まどかマギルベスト'))
    print(music_db.get_title_by_name('コネクト'))

if __name__ == '__main__':
    module_test()