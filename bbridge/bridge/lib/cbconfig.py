#!/usr/bin/env python
# cbsupervisor.py
# Copyright (C) ContinuumBridge Limited, 2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
# Contains environment for a bridge

import os
import logging

def str2bool(v):
      return v.lower() in ("yes", "true", "t", "1")

CB_BRIDGE_ROOT = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
CB_HOME = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../..'))
CB_SNAPPY_DIR = (os.getenv('SNAP_DATA', 'none'))[:-3]
#CB_SNAPPY_DIR = "/home/petec/snappytmp"
CB_SOCKET_DIR = CB_SNAPPY_DIR + "/sockets/"
CB_CONFIG_DIR = CB_SNAPPY_DIR + "/thisbridge/"
CB_MANAGER_EXIT = CB_SNAPPY_DIR + "/manager_exit"
CB_SIM_LEVEL = os.getenv('CB_SIM_LEVEL', '0')
CB_NO_CLOUD = str2bool(os.getenv('CB_NO_CLOUD', 'False'))
CB_CONTROLLER_ADDR = os.getenv('CB_CONTROLLER_ADDR', '54.194.28.63')
CB_BRIDGE_EMAIL = os.getenv('CB_BRIDGE_EMAIL', 'noanemail')
CB_BRIDGE_PASSWORD = os.getenv('CB_BRIDGE_PASSWORD', 'notapassword')
CB_LOGGING_LEVEL = getattr(logging, os.getenv('CB_LOG_ENVIRONMENT', 'DEBUG').upper())
CB_LOGFILE = CB_SNAPPY_DIR + '/cbridge.log'
CB_DEV_BRIDGE = str2bool(os.getenv('CB_DEV_BRIDGE', 'False'))
CB_DEV_UPGRADE = str2bool(os.getenv('CB_DEV_UPGRADE', 'False'))
CB_WLAN_TEST = str2bool(os.getenv('CB_WLAN_TEST', 'False'))
CB_GET_SSID_TIMEOUT = int(os.getenv('CB_GET_SSID_TIMEOUT', '600'))
CB_ZWAVE_BRIDGE = str2bool(os.getenv('CB_ZWAVE_BRIDGE', 'False'))
CB_ZWAVE_PASSWORD = os.getenv('CB_ZWAVE_PASSWORD', 'admin')
CB_CELLULAR_BRIDGE = str2bool(os.getenv('CB_CELLULAR_BRIDGE', 'False'))
CB_PERIPHERALS = os.getenv('CB_PERIPHERALS', 'none')
CB_DEV_APPS = os.getenv('CB_DEV_APPS', 'none')
CB_DEV_ADAPTORS = os.getenv('CB_DEV_ADAPTORS', 'none')
CB_USERNAME = os.getenv('CB_USERNAME', 'none')
CB_BID = os.getenv('CB_BID', 'unconfigured')
CB_CELLULAR_PRIORITY = str2bool(os.getenv('CB_CELLULAR_PRIORITY', 'False'))
CB_RASPBERRY = str2bool(os.getenv('CB_RASPBERRY', 'True'))
CB_NODE_COMMAND = '/snap/sspur/current/bin/node'
print("cbconfig, CB_SNAPPY_DIR: {}, CB_RASPBERRY: {}, CB_DEV_APPS: {}, CB_DEV_ADAPTORS: {}".format(CB_SNAPPY_DIR, CB_RASPBERRY, CB_DEV_APPS, CB_DEV_ADAPTORS))
