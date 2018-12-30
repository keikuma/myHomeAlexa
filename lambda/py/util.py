#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
ユーティリティ
"""

import logging
import os
import re
import unicodedata

def get_logger(name, level=None):
    """ loggerを得る """
    loglevel = getattr(logging, os.environ.get('LOG_LEVEL', '').upper(), logging.INFO)
    logging.basicConfig(level=loglevel)
    logger = logging.getLogger(name)
    if level:
        logger.setLevel(level)
    return logger

re_hiragana = re.compile(r'[ぁ-ゔ]')
def yomi_normalize(s):
    """ かな読みの正規化を行う """
    s = ''.join([i for i in list(s) if re.match(r"^(L|N)", unicodedata.category(i)[0])])
    s = re_hiragana.sub(lambda x: chr(ord(x.group(0)) + ord('ァ') - ord('ぁ')), s)
    s = re.sub(r'ー', '', s)
    s = re.sub(r'ヰ', 'イ', s)
    s = re.sub(r'ヱ', 'エ', s)
    s = re.sub(r'ヂ', 'ジ', s)
    s = re.sub(r'ヅ', 'ズ', s)
    s = re.sub(r'ヮ', 'ア', s)
    s = re.sub(r'ツィ', 'チ', s)
    s = re.sub(r'ティ', 'チ', s)
    s = re.sub(r'ク(サ|シ|ス|ソ)', 'キ\1', s)
    s = re.sub(r'ヴ(ァ|ア)', 'バ', s)
    s = re.sub(r'ヴ(ィ|イ)', 'ビ', s)
    s = re.sub(r'ヴ(ェ|エ)', 'ベ', s)
    s = re.sub(r'ヴ(ォ|オ)', 'ボ', s)
    s = re.sub(r'ファ', 'ハ', s)
    s = re.sub(r'フィ', 'ヒ', s)
    s = re.sub(r'フェ', 'ヘ', s)
    s = re.sub(r'フォ', 'ホ', s)
    s = re.sub(r'グァ', 'ガ', s)
    s = re.sub(r'シェ', 'セ', s)
    s = re.sub(r'ジェ', 'ゼ', s)
    s = re.sub(r'ファ', 'ハ', s)
    s = re.sub(r'トゥ', 'ト', s)
    s = re.sub(r'ツ', 'ト', s)
    s = re.sub(r'ドゥ', 'ド', s)
    s = re.sub(r'ドゥ', 'ズ', s)
    s = re.sub(r'デュ', 'ジュ', s)
    s = re.sub(r'テュ', 'チュ', s)
    s = re.sub(r'イェ', 'エ', s)
    s = re.sub(r'ッ', '', s)
    return s