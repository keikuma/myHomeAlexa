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
    """
    楽曲セレクタ
    """
    def __init__(self):
        """ initialize """
        self.music_db = musicdb.MusicDb()
        return

    def get_albumlist_by_id(self, album_id):
        album = self.music_db.get_album_by_id(album_id)



    def get_play_list(self, artist_id=None, album_id=None, title_id=None,
                      artist_name=None, album_name=None, title_name=None):
        """
        楽曲選択を行う
        """
        return_value = {}
        if title_id:
            title = self.music_db.get_title_by_id(title_id)
            if title:
                return_value['playone'] = {'id': title_id}
        elif album_id:
            album = self.music_db.get_album_by_id(album_id)

            
                
        print()

def module_test():
    """
    module test
    """
    play_music = PlayMusic();
    parser = argparse.ArgumentParser()
    parser.add_argument("--artistid", help="ArtistId", type=str)
    parser.add_argument("--albumid", help="AlbumId", type=str)
    parser.add_argument("--titleid", help="TitleId", type=str)
    parser.add_argument("--artistname", help="ArtistName", type=str)
    parser.add_argument("--albumname", help="AlbumName", type=str)
    parser.add_argument("--titlename", help="TitleName", type=str)
    args = parser.parse_args()
    result_dict = play_music.get_play_list(artist_id=args.artistid, album_id=args.albumid, title_id=args.titleid,
                                           artist_name=args.artistname, album_name=args.albumname, title_name=args.titlename)

if __name__ == '__main__':
    module_test()

