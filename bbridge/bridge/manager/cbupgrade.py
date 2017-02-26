#!/usr/bin/env python
# cbupgrade.py
# Copyright (C) ContinuumBridge Limited, 2015 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
"""
This script is executed when a bridge is upgraded.
It is included in the bridge_clone that has just been downloaded and called
by the previous version of the bridge while it is still running.
"""
ModuleName = "Upgrader"
import logging
import subprocess
CB_LOGFILE = "../../thisbridge/bridge.log"

logging.basicConfig(filename=CB_LOGFILE,level=logging.DEBUG,format='%(asctime)s %(levelname)s: %(message)s')
try:
    subprocess.call(["cp", "../scripts/cb", "/usr/bin/cb"])
    logging.info("%s Upgrade script run successfully", ModuleName)
    exit(0)
except Exception as ex:
    logging.warning("%s Problem running upgrade script", ModuleName)
    logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
    exit(1)
