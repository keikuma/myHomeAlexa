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
    if loglevel:
        logger.setLevel(loglevel)
    return logger

RE_HIRAGANA = re.compile(r'[ぁ-ゔ]')
def yomi_normalize(s):
    """ かな読みの正規化を行う """
    s = ''.join([i for i in list(s) if re.match(r"^(L|N)", unicodedata.category(i)[0])])
    s = RE_HIRAGANA.sub(lambda x: chr(ord(x.group(0)) + ord('ァ') - ord('ぁ')), s)
    s = re.sub(r'ー', r'', s)
    s = re.sub(r'ヰ', r'イ', s)
    s = re.sub(r'ヱ', r'エ', s)
    s = re.sub(r'ヂ', r'ジ', s)
    s = re.sub(r'ヅ', r'ズ', s)
    s = re.sub(r'ヮ', r'ア', s)
    s = re.sub(r'(ツ|テ)ィ', r'チ', s)
    s = re.sub(r'ク(サ|シ|ス|ソ)', r'キ', s)
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
