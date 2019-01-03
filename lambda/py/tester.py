#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
テストスクリプト
"""

import argparse
import os
from lambda_local.main import call
from lambda_local.context import Context
import lambda_function


parser = argparse.ArgumentParser()
parser.add_argument("-e", "--event", help="event json file", type=str)
args = parser.parse_args()
if not args.event:
    parser.print_help()
    exit(1)

event = open(args.event, 'rt', encoding='utf-8').read()

environment_variables = {
    'LOG_LEVEL': 'DEBUG',
    'SKILL_NAME': 'おうちサーバー'
}

call(lambda_function.lambda_handler, event, 8, environment_variables=environment_variables)