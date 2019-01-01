#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
おうちサーバースキルの実装
"""

import boto3
import os
import re
import logging
import json
from urllib.parse import urljoin

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk.standard import StandardSkillBuilder
from ask_sdk_core.dispatch_components import (
    AbstractRequestHandler, AbstractExceptionHandler,
    AbstractRequestInterceptor, AbstractResponseInterceptor)
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model.slu.entityresolution.status_code import StatusCode
from ask_sdk_model.ui import SimpleCard
from ask_sdk_model import (Response, ui)
from ask_sdk_model.interfaces.audioplayer import (
    PlayDirective, PlayBehavior, AudioItem,
    ClearQueueDirective, StopDirective,
    AudioPlayerState, PlayerActivity)
from ask_sdk_model.interfaces.audioplayer.audio_item_metadata import AudioItemMetadata
from ask_sdk_model.interfaces.audioplayer.stream import Stream

import util
import musicsearch

SKILL_NAME = 'おうちサーバー'
HELP_MESSAGE = 'おうちサーバーの楽曲を再生することができます。'
EXCEPTION_MESSAGE = 'わかりません。'
HELP_REPROMPT = "何を再生しましょうか?"
STOP_MESSAGE = "またね!"
FALLBACK_MESSAGE = "今はまだできません。"
FALLBACK_REPROMPT = '何を再生しましょうか?'
EXCEPTION_MESSAGE = "ごめんなさい。いまはまだできません。"

# =============================================================================
# Editing anything below this line might break your skill.
# =============================================================================
#loglevel = getattr(logging, os.environ.get('LOG_LEVEL', '').upper(), logging.INFO)
#logging.basicConfig(level=loglevel)
LOGGER = util.get_logger(__name__)
LOGGER.info("MusicSearch instance: start")
MUSICSEARCH = musicsearch.MusicSearch()
MUSIC_DB = MUSICSEARCH.get_db()
LOGGER.info("MusicSearch instance: end")
MUSIC_URL_BASE = os.environ.get('MUSIC_URL_BASE', '')

sb = StandardSkillBuilder(table_name="alexa-music-play")


def get_value_and_id(slots, attr_name):
    """ スロットから、valueとid を取り出す """
    slot = slots.get(attr_name, None)
    value = slot.value
    resolution_id = None
    if slot.resolutions and slot.resolutions.resolutions_per_authority:
        for resolution in slot.resolutions.resolutions_per_authority:
            if resolution.status.code == StatusCode.ER_SUCCESS_MATCH:
                for value in resolution.values:
                    if value.value.id:
                        resolution_id = value.value.id
                        break
    return value, resolution_id

def build_ssml_from_item_name(item_name):
    """ 英語っぽいところをlangタグで囲む """
    ssml = re.sub(r"([0-9A-Za-z][0-9A-Za-z\s.\-'!\?]*)", r'<lang xml:"en-US">\1</lang>', item_name)
    return ssml

# Built-in Intent Handlers
class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch and GetNewFact Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        response_builder = handler_input.response_builder
        speech = 'おうちサーバーへようこそ。「誰 の どの 曲をかけて」と、言ってみてください。'
        response_builder.speak(speech)
        return handler_input.response_builder.response

class PlayMusicHandler(AbstractRequestHandler):
    """ Handler for PlayMusicIntent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("PlayMusicIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        LOGGER.debug("In PlayMusicHandler")
        #LOGGER.debug("request_envelope: %s", str(handler_input.request_envelope))
        #LOGGER.debug("request_attributes: %s", str(handler_input.attributes_manager.request_attributes))
        #LOGGER.debug("session_attributes: %s", str(handler_input.attributes_manager.session_attributes))

        # slotの値を取り出す
        slots = handler_input.request_envelope.request.intent.slots
        artist_name, artist_id = get_value_and_id(slots, 'Artist')
        album_name, album_id = get_value_and_id(slots, 'Album')
        title_name, title_id = get_value_and_id(slots, 'Title')

        play_list = MUSICSEARCH.get_play_list(artist_id=artist_id, album_id=album_id, title_id=title_id,
                                              artist_name=artist_name, album_name=album_name, title_name=title_name)
        #LOGGER.debug("play_list: %s", str(play_list))
        response_builder = handler_input.response_builder
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        if not play_list:
            speech = 'ごめんなさい。わかりません。'
            response_builder.speak(speech)
        elif play_list['type'] == 'artist':
            if play_list['list']:
                speech = '{} の楽曲をシャッフル再生します。'.format(build_ssml_from_item_name(play_list['artist']['name']['value']))
                response_builder.speak(speech)
                # list: 再生リスト
                # index: 現在再生中のリスト中のインデックス
                # type: 再生しているコンテンツのタイプ (artist, album, title)
                # can_shuffle: シャッフル可能かどうか
                # is_shffled: リストがシャッフルされているかどうか
                # 197はマジックナンバー。適当でキリの良い数。
                play_queue = {
                    'queue': play_list['list'][:197],
                    'index': 0,
                    'type': 'artist',
                    'can_shuffle': False,
                    'is_shffled': True,
                    'state': 'PLAY_REQUEST',
                    'playback_failure_count': 0
                }
            else:
                speech = '{} の楽曲は見つかりませんでした。'
                response_builder.speak(speech)
        elif play_list['type'] == 'album':
            if play_list['list']:
                speech = 'アルバム {} を再生します。'.format(build_ssml_from_item_name(play_list['album']['name']['value']))
                response_builder.speak(speech)
                play_queue = {
                    'queue': play_list['list'],
                    'index': 0,
                    'type': 'album',
                    'can_shuffle': True,
                    'is_shffled': False,
                    'state': 'PLAY_REQUEST',
                    'list': play_list['list'],
                    'playback_failure_count': 0
                }
            else:
                speech = 'アルバム {} は見つかりませんでした。'.format(build_ssml_from_item_name(play_list['album']['name']['value']))
                response_builder.speak(speech)
        elif play_list['type'] == 'item':
            if play_list['list']:
                play_queue = {
                    'queue': play_list['list'],
                    'index': 0,
                    'type': 'album',
                    'can_shuffle': False,
                    'is_shffled': False,
                    'state': 'PLAY_REQUEST',
                    'playback_failure_count': 0
                }
        else:
            speech = 'ごめんなさい。わかりません。'
            response_builder.speak(speech)
        if 'play_queue' in locals():
            LOGGER.debug("play_queue: {}".format(str(play_queue)))
            title_id = play_queue['queue'][play_queue['index']]
            title_info = MUSIC_DB.get_title_by_id(title_id)
            meta_data = AudioItemMetadata(title=title_info['title'], subtitle=title_info['artist'])
            response_builder.add_directive(
                PlayDirective(
                    play_behavior=PlayBehavior.REPLACE_ALL,
                    audio_item=AudioItem(
                        Stream(
                            token=title_id,
                            url=urljoin(MUSIC_URL_BASE, title_info['path'])
                        ),
                        metadata=meta_data
                    )
                )
            )
            persistent_attributes['play_queue'] = play_queue
            handler_input.attributes_manager.save_persistent_attributes()
        return handler_input.response_builder.response

class QueryTitleIntentHandler(AbstractRequestHandler):
    """ Handler for QueryTitleIntent. """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("QueryTitleIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        response_builder = handler_input.response_builder
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        play_queue = persistent_attributes.get('play_queue', {})
        title_id = play_queue.get('list', {}).get(play_queue['index'], None)
        if title_id:
            title_info = MUSIC_DB.get_title_by_id(title_id)
            album_info = MUSIC_DB.get_album_by_id(title_info['album_id'])
            artist_info = MUSIC_DB.get_artist_by_id(title_info['artist_id'])
            speech = ""
            if artist_info:
                speech += build_ssml_from_item_name(artist_info['name']['value']) + " で、"
            if album_info:
                speech += build_ssml_from_item_name(album_info['name']['value']) + " に収録の、"
            if title_info:
                speech += build_ssml_from_item_name(title_info['title']) + " です。"
            response_builder.speak(speech)
        return handler_input.response_builder.response

class HelpIntentHandler(AbstractRequestHandler):
    """ Handler for Help Intent. """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        LOGGER.info("In HelpIntentHandler")

        handler_input.response_builder.speak(HELP_MESSAGE).ask(
            HELP_REPROMPT).set_card(SimpleCard(
                SKILL_NAME, HELP_MESSAGE))
        return handler_input.response_builder.response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """ Single handler for Cancel and Stop Intent. """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        LOGGER.info("In CancelOrStopIntentHandler")

        handler_input.response_builder.add_directive(ClearQueueDirective())
        handler_input.response_builder.add_directive(StopDirective())
        handler_input.response_builder.speak(STOP_MESSAGE)
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    """ Handler for Fallback Intent.

    AMAZON.FallbackIntent is only available in en-US locale.
    This handler will not be triggered except in that locale,
    so it is safe to deploy on any locale.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        LOGGER.info("In FallbackIntentHandler")

        handler_input.response_builder.speak(FALLBACK_MESSAGE).ask(
            FALLBACK_REPROMPT)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """ Handler for Session End. """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        LOGGER.info("In SessionEndedRequestHandler")

        LOGGER.info("Session ended reason: %s", handler_input.request_envelope.request.reason)
        return handler_input.response_builder.response


# AudioPlayer Handler
class PauseIntentHandler(AbstractRequestHandler):
    """ AudioPlayer PauseIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.PauseIntent")

    def handle(self, handler_input):
        """ 一時停止を実装 """
        response_builder = handler_input.response_builder
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        audio_player_state = handler_input.audio_player_state
        play_queue = persistent_attributes.get('play_queue', None)
        if play_queue:
            play_queue['offset_in_milliseconds'] = audio_player_state['offset_in_milliseconds']
            play_queue['state'] = 'PAUSED'
            response_builder.add_directive(StopDirective())
            handler_input.attributes_manager.save_persistent_attributes()
        return handler_input.response_builder.response

class ResumeIntentHandler(AbstractRequestHandler):
    """ AudioPlayer ResumeIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.ResumeIntent")

    def handle(self, handler_input):
        """ 再開を実装 """
        response_builder = handler_input.response_builder
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        audio_player_state = handler_input.audio_player_state
        play_queue = persistent_attributes.get('play_queue', None)
        if play_queue:
            if play_queue['state'] and play_queue['state'] == 'PAUSED':
                title_id = play_queue['queue'][play_queue['index']]
                title_info = MUSIC_DB.get_title_by_id(title_id)
                meta_data = AudioItemMetadata(title=title_info['title'], subtitle=title_info['artist'])
                response_builder.add_directive(
                    PlayDirective(
                        play_behavior=PlayBehavior.REPLACE_ALL,
                        audio_item=AudioItem(
                            Stream(
                                token=title_id,
                                url=urljoin(MUSIC_URL_BASE, title_info['path']),
                                offset_in_milliseconds=play_queue['offset_in_milliseconds'] - 1000
                            ),
                            metadata=meta_data
                        )
                    )
                )
                play_queue['state'] = 'PLAY_REQUEST'
                handler_input.attributes_manager.save_persistent_attributes()
        return handler_input.response_builder.response

class LoopOffIntentIntentHandler(AbstractRequestHandler):
    """ AudioPlayer LoopOffIntentlIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.LoopOffIntent")

    def handle(self, handler_input):
        return handler_input.response_builder.response

class LoopOnIntentIntentHandler(AbstractRequestHandler):
    """ AudioPlayer LoopOnIntentlIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.LoopOnIntent")

    def handle(self, handler_input):
        return handler_input.response_builder.response

class NextIntentHandler(AbstractRequestHandler):
    """ AudioPlayer NextIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.NextIntent")

    def handle(self, handler_input):
        """ 次の曲へ """
        response_builder = handler_input.response_builder
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        audio_player_state = handler_input.audio_player_state
        play_queue = persistent_attributes.get('play_queue', None)
        if play_queue:
            play_queue['index'] += 1
            play_queue['index'] %= play_queue['list'].len()
            title_id = play_queue['queue'][play_queue['index']]
            title_info = MUSIC_DB.get_title_by_id(title_id)
            meta_data = AudioItemMetadata(title=title_info['title'], subtitle=title_info['artist'])
            response_builder.add_directive(
                PlayDirective(
                    play_behavior=PlayBehavior.REPLACE_ALL,
                    audio_item=AudioItem(
                        Stream(
                            token=title_id,
                            url=urljoin(MUSIC_URL_BASE, title_info['path'])
                        ),
                        metadata=meta_data
                    )
                )
            )
            play_queue['state'] = 'PLAY_REQUEST'
            handler_input.attributes_manager.save_persistent_attributes()
        return handler_input.response_builder.response

class PreviousIntentHandler(AbstractRequestHandler):
    """ AudioPlayer PreviousIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.PreviousIntent")

    def handle(self, handler_input):
        """ 前の曲へ """
        response_builder = handler_input.response_builder
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        audio_player_state = handler_input.audio_player_state
        play_queue = persistent_attributes.get('play_queue', None)
        if play_queue:
            play_queue['index'] = play_queue['index'] + play_queue['list'].len() - 1
            play_queue['index'] %= play_queue['list'].len()
            title_id = play_queue['queue'][play_queue['index']]
            title_info = MUSIC_DB.get_title_by_id(title_id)
            meta_data = AudioItemMetadata(title=title_info['title'], subtitle=title_info['artist'])
            response_builder.add_directive(
                PlayDirective(
                    play_behavior=PlayBehavior.REPLACE_ALL,
                    audio_item=AudioItem(
                        Stream(
                            token=title_id,
                            url=urljoin(MUSIC_URL_BASE, title_info['path'])
                        ),
                        metadata=meta_data
                    )
                )
            )
            play_queue['state'] = 'PLAY_REQUEST'
            handler_input.attributes_manager.save_persistent_attributes()
        return handler_input.response_builder.response

class RepeatIntentHandler(AbstractRequestHandler):
    """ AudioPlayer RepeatIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.RepeatIntent")

    def handle(self, handler_input):
        return handler_input.response_builder.response

class ShuffleOffIntentHandler(AbstractRequestHandler):
    """ AudioPlayer ShuffleOffIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.ShuffleOffIntent")

    def handle(self, handler_input):
        return handler_input.response_builder.response

class ShuffleOnIntentHandler(AbstractRequestHandler):
    """ AudioPlayer ShuffleOnIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.ShuffleOnIntent")

    def handle(self, handler_input):
        return handler_input.response_builder.response

class StartOverIntentHandler(AbstractRequestHandler):
    """ AudioPlayer StartOverIntentHandler """
    def can_handle(self, handler_input):
        return is_request_type("AMAZON.StartOverIntent")

    def handle(self, handler_input):
        """ 再生を停止する (queueをどうするか) """
        # TODO: Queue を削除した方が良いかどうか検討する
        handler_input.response_builder.add_directive(ClearQueueDirective())
        handler_input.response_builder.add_directive(StopDirective())
        handler_input.response_builder.speak(STOP_MESSAGE)
        return handler_input.response_builder.response

class PlaybackFailedHandler(AbstractRequestHandler):
    """ AudioPlayer PlaybackFailedHandler """
    def can_handle(self, handler_input):
        return is_request_type("AudioPlayer.PlaybackFailed")

    def handle(self, handler_input):
        """ 再生失敗 """
        response_builder = handler_input.response_builder
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        audio_player_state = handler_input.audio_player_state
        play_queue = persistent_attributes.get('play_queue', None)
        if play_queue and play_queue['playback_failure_count']:
            play_queue['playback_failure_count'] += 1
        if play_queue['playback_failure_count'] > 5:
            handler_input.response_builder.add_directive(ClearQueueDirective())
            handler_input.response_builder.add_directive(StopDirective())
            handler_input.response_builder.speak('再生できませんでした')
        elif play_queue:
            play_queue['index'] += 1
            play_queue['index'] %= play_queue['list'].len()
            title_id = play_queue['queue'][play_queue['index']]
            title_info = MUSIC_DB.get_title_by_id(title_id)
            meta_data = AudioItemMetadata(title=title_info['title'], subtitle=title_info['artist'])
            response_builder.add_directive(
                PlayDirective(
                    play_behavior=PlayBehavior.REPLACE_ALL,
                    audio_item=AudioItem(
                        Stream(
                            token=title_id,
                            url=urljoin(MUSIC_URL_BASE, title_info['path'])
                        ),
                        metadata=meta_data
                    )
                )
            )
            play_queue['state'] = 'PLAY_REQUEST'
        handler_input.attributes_manager.save_persistent_attributes()
        return handler_input.response_builder.response

class PlaybackNearlyFinishedHandler(AbstractRequestHandler):
    """ AudioPlayer PlaybackNearlyFinishedHandler """
    def can_handle(self, handler_input):
        return is_request_type("AudioPlayer.PlaybackNearlyFinished")

    def handle(self, handler_input):
        """ 次の曲をQueueに積む """
        # TODO: queue の整合性チェック
        response_builder = handler_input.response_builder
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        audio_player_state = handler_input.audio_player_state
        play_queue = persistent_attributes.get('play_queue', None)
        if play_queue:
            expected_previous_token = play_queue['index']
            play_queue['index'] += 1
            play_queue['index'] %= play_queue['list'].len()
            title_id = play_queue['queue'][play_queue['index']]
            title_info = MUSIC_DB.get_title_by_id(title_id)
            meta_data = AudioItemMetadata(title=title_info['title'], subtitle=title_info['artist'])
            response_builder.add_directive(
                PlayDirective(
                    play_behavior=PlayBehavior.ENQUEUE,
                    audio_item=AudioItem(
                        Stream(
                            token=title_id,
                            url=urljoin(MUSIC_URL_BASE, title_info['path']),
                            expected_previous_token=expected_previous_token
                        ),
                        metadata=meta_data
                    )
                )
            )
            play_queue['state'] = 'PLAY_REQUEST'
            handler_input.attributes_manager.save_persistent_attributes()
        return handler_input.response_builder.response


# Exception Handler
class CatchAllExceptionHandler(AbstractExceptionHandler):
    """ Catch all exception handler, log exception and
    respond with custom message.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        LOGGER.info("In CatchAllExceptionHandler")
        LOGGER.error(exception, exc_info=True)

        handler_input.response_builder.speak(EXCEPTION_MESSAGE).ask(
            HELP_REPROMPT)

        return handler_input.response_builder.response


# Request and Response loggers
class RequestLogger(AbstractRequestInterceptor):
    """ Log the alexa requests. """
    def process(self, handler_input):
        # type: (HandlerInput) -> None
        LOGGER.debug("Alexa Request: %s", str(handler_input.request_envelope.request))


class ResponseLogger(AbstractResponseInterceptor):
    """ Log the alexa responses. """
    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        LOGGER.debug("Alexa Response: %s", str(response))


# Register intent handlers
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(PlayMusicHandler())
sb.add_request_handler(QueryTitleIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(PauseIntentHandler())
sb.add_request_handler(ResumeIntentHandler())
sb.add_request_handler(LoopOffIntentIntentHandler())
sb.add_request_handler(LoopOnIntentIntentHandler())
sb.add_request_handler(NextIntentHandler())
sb.add_request_handler(PreviousIntentHandler())
sb.add_request_handler(RepeatIntentHandler())
sb.add_request_handler(ShuffleOffIntentHandler())
sb.add_request_handler(ShuffleOnIntentHandler())
sb.add_request_handler(StartOverIntentHandler())
sb.add_request_handler(PlaybackFailedHandler())
sb.add_request_handler(PlaybackNearlyFinishedHandler())

# Register exception handlers
sb.add_exception_handler(CatchAllExceptionHandler())

# TODO: Uncomment the following lines of code for request, response logs.
#sb.add_global_request_interceptor(RequestLogger())
#sb.add_global_response_interceptor(ResponseLogger())

# Handler name that is used on AWS lambda
lambda_handler = sb.lambda_handler()
