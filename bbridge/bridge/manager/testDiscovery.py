#!/usr/bin/env python
# testDiscovery.py
# Copyright (C) ContinuumBridge Limited, 2013 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#

""" A very simple discovery program for BTLE devices.
    All it does it look for addresses and append them to a list. """

ModuleName = "Discovery           "

import sys
import time
import os
import json

if __name__ == '__main__':
    time.sleep(2)
    d = {}
    d["status"] = "discovered"
    d["devices"] = []
    d["devices"].append({"method": "btle",
                         "name": "SensorTag", 
                         "addr": "22.22.22.22.22.22"})
    d["devices"].append({"method": "btle",
                         "manufacturer_name": "Texas Instruments",
                         "name": "Test Device 1", 
                         "addr": "33.33.33.33.33.33"})
    d["devices"].append({"method": "btle",
                         "name": "SensorTag", 
                         "addr": "44.44.44.44.44.44"})
    print json.dumps(d)
