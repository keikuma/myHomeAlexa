#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
おうちサーバースキルの実装
"""

import boto3
import os
import random
import re
import sys
import logging
import itertools
import json
import traceback
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
    values = []
    slot = slots.get(attr_name, None)
    slot_value = None
    if slot and slot.resolutions and slot.resolutions.resolutions_per_authority:
        slot_value = slot.value
        for resolution in slot.resolutions.resolutions_per_authority:
            if resolution.status.code == StatusCode.ER_SUCCESS_MATCH:
                for value in resolution.values:
                    v = {}
                    if value.value.id:
                        v['id'] = value.value.id
                    if value.value.name:
                        v['name'] = value.value.name
                        if v['name'] == slot_value:
                            slot_value = None
                    if v:
                        values.append(v)
    if slot_value:
        values.append({'name': slot_value})
    return values

def build_ssml_from_item_name(item_name):
    """ 英語っぽいところをlangタグで囲む """
    ssml = re.sub(r"([0-9A-Za-z][0-9A-Za-z\s.\-'!\?]*)", r'<lang xml:lang="en-US">\1</lang>', item_name)
    return ssml

def get_play_queue(handler_input):
    try:
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        play_queue = persistent_attributes['play_queue']
    except NameError:
        return
    play_queue['index'] = int(play_queue['index'])
    return play_queue

def play_from_queue(handler_input, play_behavior=PlayBehavior.REPLACE_ALL, offset_in_milliseconds=0, expected_previous_token=None):
    play_queue = get_play_queue(handler_input)
    title_id = play_queue['list'][play_queue['index']]
    title_info = MUSIC_DB.get_title_by_id(title_id)
    meta_data = AudioItemMetadata(title=title_info['title'], subtitle=title_info['artist'])
    response_builder = handler_input.response_builder
    if play_behavior == PlayBehavior.ENQUEUE:
        stream = Stream(
            token=title_id,
            url=urljoin(MUSIC_URL_BASE, title_info['path']),
            offset_in_milliseconds=offset_in_milliseconds,
            expected_previous_token=expected_previous_token
        )
    else:
        stream = Stream(
            token=title_id,
            url=urljoin(MUSIC_URL_BASE, title_info['path']),
            offset_in_milliseconds=offset_in_milliseconds
        )
        play_queue['state'] = 'PLAY_REQUEST'
    response_builder.add_directive(
        PlayDirective(
            play_behavior=play_behavior,
            audio_item=AudioItem(
                stream,
                metadata=meta_data
            )
        )
    )
    return


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

        response_builder = handler_input.response_builder

        try:
            # slotの値を取り出す
            slots = handler_input.request_envelope.request.intent.slots
            slots_artist = get_value_and_id(slots, 'Artist')
            slots_album = get_value_and_id(slots, 'Album')
            slots_title = get_value_and_id(slots, 'Title')

            # 最優秀候補を選ぶ
            play_list = None
            max_reliability = -1
            for slots in [slots_artist, slots_album, slots_title]:
                if len(slots) == 0:
                    slots.append({'id': None, 'name': None})
            for slot_artist, slot_album, slot_title in itertools.product(slots_artist, slots_album, slots_title):
                candidate = MUSICSEARCH.get_play_list(artist_id=slot_artist.get('id', None), artist_name=slot_artist.get('name', None),
                                                    album_id=slot_album.get('id', None), album_name=slot_album.get('name', None),
                                                    title_id=slot_title.get('id', None), title_name=slot_title.get('name', None))
                if candidate and candidate['reliability'] > max_reliability:
                    play_list = candidate
                    max_reliability = candidate['reliability']
                    if max_reliability == 10:
                        break

            LOGGER.debug("play_list: %s", str(play_list))
            persistent_attributes = handler_input.attributes_manager.persistent_attributes
            if not play_list:
                speech = 'ごめんなさい。わかりません。'
                response_builder.speak(speech)
            else:
                MUSICSEARCH.expansion_list(play_list)
                if play_list['list']:
                    play_queue = {'info': play_list, 'list': play_list['list'], 'index': 0, 'state': 'PLAY_REQUEST', 'playback_failure_count': 0}
                if play_list['type'] == 'artist':
                    yomi = play_list['artist']['name'].get('yomi', None)
                    if not yomi:
                        yomi = build_ssml_from_item_name(play_list['artist']['name']['value'])
                    if play_list['list']:
                        speech = '{} の楽曲をシャッフル再生します。'.format(yomi)
                        response_builder.speak(speech)
                    else:
                        speech = '{} の楽曲は見つかりませんでした。'.format(yomi)
                        play_queue = None
                        response_builder.speak(speech)
                elif play_list['type'] == 'album':
                    yomi = play_list['album']['name'].get('yomi', None)
                    if not yomi:
                        yomi = build_ssml_from_item_name(play_list['album']['name']['value'])
                    if play_list['list']:
                        speech = 'アルバム {} を再生します。'.format(yomi)
                        response_builder.speak(speech)
                    else:
                        speech = 'アルバム {} は見つかりませんでした。'.format(yomi)
                        response_builder.speak(speech)
                elif play_list['type'] == 'title':
                    if play_list['list']:
                        "do nothing."
                else:
                    speech = 'ごめんなさい。わかりません。'
                    response_builder.speak(speech)
            if 'play_queue' in locals() and play_queue:
                LOGGER.debug("play_queue: {}".format(str(play_queue)))
                persistent_attributes['play_queue'] = play_queue
                play_from_queue(handler_input)
                handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        return handler_input.response_builder.response

class QueryTitleIntentHandler(AbstractRequestHandler):
    """ Handler for QueryTitleIntent. """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("QueryTitleIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        LOGGER.debug("In QueryTitleIntentHandler")
        response_builder = handler_input.response_builder
        try:
            play_queue = get_play_queue(handler_input)
            title_id = play_queue.get('now_playing', None)
            if title_id and play_queue['state'] == 'PLAYING':
                title_info = MUSIC_DB.get_title_by_id(title_id)
                album_info = MUSIC_DB.get_album_by_id(title_info['album_id'])
                artist_info = MUSIC_DB.get_artist_by_id(title_info['artist_id'])
                speech = ""
                if artist_info:
                    artist_yomi = artist_info['name'].get('yomi', None)
                    if not artist_yomi:
                        artist_yomi = build_ssml_from_item_name(artist_info['name']['value'])
                    speech += artist_yomi + " で、"
                if album_info:
                    album_yomi = album_info['name']['yomi']
                    if not album_yomi:
                        album_yomi = build_ssml_from_item_name(album_info['name']['value'])
                    speech += album_yomi + " に収録の、"
                if title_info:
                    speech += build_ssml_from_item_name(title_info['title']) + " です。"
                response_builder.speak(speech)
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))

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
        try:
            persistent_attributes = handler_input.attributes_manager.persistent_attributes
            persistent_attributes['play_queue'] = {}
            handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
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
class PlaybackStartedHandler(AbstractRequestHandler):
    """ AudioPlayer PlaybackStartedHandler """
    def can_handle(self, handler_input):
        return is_request_type("AudioPlayer.PlaybackStarted")(handler_input)

    def handle(self, handler_input):
        LOGGER.debug("In PlaybackStartedHandler")
        try:
            play_queue = get_play_queue(handler_input)
            play_queue['state'] = 'PLAYING'
            play_queue['now_playing'] = handler_input.request_envelope.request.token
            handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        return handler_input.response_builder.response

class PlaybackFinishedHandler(AbstractRequestHandler):
    """ AudioPlayer PlaybackFinishedHandler """
    def can_handle(self, handler_input):
        return is_request_type("AudioPlayer.PlaybackFinished")(handler_input)

    def handle(self, handler_input):
        LOGGER.debug("In PlaybackFinished")
        try:
            play_queue = get_play_queue(handler_input)
            play_queue['state'] = 'STOPPED'
            handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        return handler_input.response_builder.response

class PlaybackStoppedHandler(AbstractRequestHandler):
    """ AudioPlayer PlaybackStoppedHandler """
    def can_handle(self, handler_input):
        return is_request_type("AudioPlayer.PlaybackStopped")(handler_input)

    def handle(self, handler_input):
        LOGGER.debug("In PlaybackStoppedHandler")
        return handler_input.response_builder.response

class PauseIntentHandler(AbstractRequestHandler):
    """ AudioPlayer PauseIntentHandler """
    def can_handle(self, handler_input):
        return (is_intent_name("AMAZON.PauseIntent")(handler_input)
            or is_intent_name("PlaybackController.PauseCommandIssued")(handler_input))

    def handle(self, handler_input):
        """ 一時停止を実装 """
        LOGGER.debug("In PauseIntentHandler")
        response_builder = handler_input.response_builder
        try:
            audio_player_state = handler_input.request_envelope.context.audio_player
            if audio_player_state.player_activity != PlayerActivity.PLAYING:
                return handler_input.response_builder.response
            play_queue = get_play_queue(handler_input)
            play_queue['offset_in_milliseconds'] = audio_player_state.offset_in_milliseconds
            play_queue['state'] = 'PAUSED'
            handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        response_builder.add_directive(StopDirective())
        return handler_input.response_builder.response

class ResumeIntentHandler(AbstractRequestHandler):
    """ AudioPlayer ResumeIntentHandler """
    def can_handle(self, handler_input):
        return (is_intent_name("AMAZON.ResumeIntent")(handler_input)
            or is_intent_name("PlaybackController.PlayCommandIssued")(handler_input))

    def handle(self, handler_input):
        """ 再開を実装 """
        LOGGER.debug("In ResumeIntentHandler")
        response_builder = handler_input.response_builder
        try:
            audio_player_state = handler_input.request_envelope.context.audio_player
            if audio_player_state.player_activity != PlayerActivity.PAUSED:
                return handler_input.response_builder.response
            play_queue = get_play_queue(handler_input)
            if play_queue['state'] and play_queue['state'] == 'PAUSED':
                play_from_queue(handler_input, offset_in_milliseconds=play_queue['offset_in_milliseconds'])
                handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        return handler_input.response_builder.response

class LoopOffIntentIntentHandler(AbstractRequestHandler):
    """ AudioPlayer LoopOffIntentlIntentHandler """
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.LoopOffIntent")(handler_input)

    def handle(self, handler_input):
        LOGGER.debug("In LoopOffIntentlIntentHandler")
        return handler_input.response_builder.response

class LoopOnIntentIntentHandler(AbstractRequestHandler):
    """ AudioPlayer LoopOnIntentlIntentHandler """
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.LoopOnIntent")(handler_input)

    def handle(self, handler_input):
        LOGGER.debug("In LoopOnIntentlIntentHandler")
        return handler_input.response_builder.response

class NextIntentHandler(AbstractRequestHandler):
    """ AudioPlayer NextIntentHandler """
    def can_handle(self, handler_input):
        return (is_intent_name("AMAZON.NextIntent")(handler_input)
            or is_intent_name("PlaybackController.NextCommandIssued")(handler_input))

    def handle(self, handler_input):
        """ 次の曲へ """
        LOGGER.debug("In NextIntentHandler")
        response_builder = handler_input.response_builder
        try:
            audio_player_state = handler_input.request_envelope.context.audio_player
            if audio_player_state.player_activity != PlayerActivity.PLAYING:
                return handler_input.response_builder.response
            play_queue = get_play_queue(handler_input)
            now_playing = play_queue.get('now_playing', None)
            if now_playing:
                try:
                    index = play_queue['list'].index(now_playing)
                except ValueError:
                    index = None
                if index:
                    play_queue['index'] = index + 1
                    play_queue['index'] %= len(play_queue['list'])
                    play_from_queue(handler_input)
            handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        return handler_input.response_builder.response

class PreviousIntentHandler(AbstractRequestHandler):
    """ AudioPlayer PreviousIntentHandler """
    def can_handle(self, handler_input):
        return (is_intent_name("AMAZON.PreviousIntent")(handler_input)
            or is_intent_name("PlaybackController.PreviousCommandIssued")(handler_input))

    def handle(self, handler_input):
        """ 前の曲へ """
        LOGGER.debug("In PreviousIntentHandler")
        response_builder = handler_input.response_builder
        try:
            audio_player_state = handler_input.request_envelope.context.audio_player
            if audio_player_state.player_activity != PlayerActivity.PLAYING:
                return handler_input.response_builder.response
            play_queue = get_play_queue(handler_input)
            now_playing = play_queue.get('now_playing', None)
            if now_playing:
                try:
                    index = play_queue['list'].index(now_playing)
                except ValueError:
                    index = None
                if index:
                    play_queue['index'] = index + len(play_queue['list']) - 1
                    play_queue['index'] %= len(play_queue['list'])
                    play_from_queue(handler_input)
            handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        return handler_input.response_builder.response

class RepeatIntentHandler(AbstractRequestHandler):
    """ AudioPlayer RepeatIntentHandler """
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.RepeatIntent")(handler_input)

    def handle(self, handler_input):
        LOGGER.debug("In RepeatIntentHandler")
        return handler_input.response_builder.response

class ShuffleOffIntentHandler(AbstractRequestHandler):
    """ AudioPlayer ShuffleOffIntentHandler """
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.ShuffleOffIntent")(handler_input)

    def handle(self, handler_input):
        LOGGER.debug("In ShuffleOffIntentHandler")
        try:
            play_queue = get_play_queue(handler_input)
            if play_queue.get('is_shuffle', False):
                play_queue['list'] = list(play_queue['info']['list'])
                play_queue['is_shuffle'] = False
                play_queue['index'] = 0
                play_from_queue(handler_input)
                handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        return handler_input.response_builder.response

class ShuffleOnIntentHandler(AbstractRequestHandler):
    """ AudioPlayer ShuffleOnIntentHandler """
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.ShuffleOnIntent")(handler_input)

    def handle(self, handler_input):
        LOGGER.debug("In ShuffleOnIntent")
        try:
            play_queue = get_play_queue(handler_input)
            if play_queue['info']['can_shuffle'] and not play_queue.get('is_shuffle', False):
                play_queue['list'] = list(play_queue['info']['list'])
                random.shuffle(play_queue['list'])
                play_queue['is_shuffle'] = True
                play_queue['index'] = 0
                play_from_queue(handler_input)
                handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        return handler_input.response_builder.response

class StartOverIntentHandler(AbstractRequestHandler):
    """ AudioPlayer StartOverIntentHandler """
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.StartOverIntent")(handler_input)

    def handle(self, handler_input):
        """ 再生を停止する """
        LOGGER.debug("In StartOverIntentHandler")
        handler_input.response_builder.add_directive(ClearQueueDirective())
        handler_input.response_builder.add_directive(StopDirective())
        handler_input.response_builder.speak(STOP_MESSAGE)
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        persistent_attributes['play_queue'] = {}
        handler_input.attributes_manager.save_persistent_attributes()
        return handler_input.response_builder.response

class PlaybackFailedHandler(AbstractRequestHandler):
    """ AudioPlayer PlaybackFailedHandler """
    def can_handle(self, handler_input):
        return is_request_type("AudioPlayer.PlaybackFailed")(handler_input)

    def handle(self, handler_input):
        """ 再生失敗 """
        LOGGER.debug("In PlaybackFailedHandler")
        response_builder = handler_input.response_builder
        try:
            play_queue = get_play_queue(handler_input)
            if play_queue and play_queue['playback_failure_count']:
                play_queue['playback_failure_count'] += 1
            if play_queue['playback_failure_count'] > 5:
                handler_input.response_builder.add_directive(ClearQueueDirective())
                handler_input.response_builder.add_directive(StopDirective())
                handler_input.response_builder.speak('再生できませんでした')
            elif play_queue:
                # 失敗した楽曲を削除
                play_queue['list'].remove(handler_input.request_envelope.request.token)
                play_queue['index'] %= len(play_queue['list'])
                play_from_queue(handler_input)
                play_queue['state'] = 'PLAY_REQUEST'
            handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
        return handler_input.response_builder.response

class PlaybackNearlyFinishedHandler(AbstractRequestHandler):
    """ AudioPlayer PlaybackNearlyFinishedHandler """
    def can_handle(self, handler_input):
        return is_request_type("AudioPlayer.PlaybackNearlyFinished")(handler_input)

    def handle(self, handler_input):
        """ 次の曲をQueueに積む """
        LOGGER.debug("In PlaybackNearlyFinishedHandler")
        # TODO: queue の整合性チェック
        response_builder = handler_input.response_builder
        try:
            play_queue = get_play_queue(handler_input)
            expected_previous_token = play_queue['index']
            play_queue['index'] += 1
            play_queue['index'] %= len(play_queue['list'])
            play_from_queue(handler_input, play_behavior=PlayBehavior.ENQUEUE, expected_previous_token=expected_previous_token)
            handler_input.attributes_manager.save_persistent_attributes()
        except:
            LOGGER.error("Unexpected error: {}".format(traceback.format_exc()))
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

sb.add_request_handler(PlaybackStartedHandler())
sb.add_request_handler(PlaybackFinishedHandler())
sb.add_request_handler(PlaybackStoppedHandler())
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
sb.add_global_request_interceptor(RequestLogger())
sb.add_global_response_interceptor(ResponseLogger())

# Handler name that is used on AWS lambda
lambda_handler = sb.lambda_handler()
