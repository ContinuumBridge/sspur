#!/usr/bin/env python
# discovery.py
# Copyright (C) ContinuumBridge Limited, 2013 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#

""" A very simple discovery program for BTLE devices.
    All it does it look for addresses and append them to a list. """

ModuleName = "Discovery"
DISCOVERY_TIME = 12  # Time to scan before reporting results

import sys
import time
import os
import pexpect
import json
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../lib')))
from cbconfig import *

if __name__ == '__main__':
    logging.basicConfig(filename=CB_LOGFILE,level=CB_LOGGING_LEVEL,format='%(asctime)s %(message)s')
    if len(sys.argv) < 4:
        logging.error('%s Usage: discover <protocol> <sim> <CB_CONFIG_DIR>', ModuleName)
        exit(1)
    protocol = sys.argv[1]
    sim = sys.argv[2]
    CB_CONFIG_DIR = sys.argv[3]
    if sim == "1":
        discoverySimFile = CB_CONFIG_DIR + 'discovery.sim'
        with open(discoverySimFile, 'r') as f:
            s = f.read()
        if s.endswith('\n'):
            s = s[:-1]
        simStep = int(s)
    discoveredAddresses = []
    names = []
    manufacturers = []
    protocols = []
    try:
        cmd = "hcitool lescan"
        p = pexpect.spawn(cmd)
    except:
        logging.error('%s lescan failed to spawn', ModuleName)
        d = {"status": "error"}        
        print json.dumps(d)
        sys.exit()
    try:
        p.expect('\r\n', timeout=3)
        p.expect('\r\n', timeout=3)
    except:
        logging.error('%s Nothing returned from pexpect', ModuleName)
        d = {"status": "error"}        
        print json.dumps(d)
        sys.exit()
    startTime = time.time()
    endTime = startTime + DISCOVERY_TIME
    while time.time() < endTime:
        try:
            p.expect('\r\n', timeout=10)
            raw = p.before.split()
            logging.debug('%s raw data: %s', ModuleName, raw)
            addr = raw[0]
            name = ""
            for i in range(1, len(raw)):
                name += raw[i] + " "
            name = name[:-1]
            if name != "(unknown)":
                logging.debug('%s name: %s', ModuleName, name)
                found = False
                if len(discoveredAddresses) == 0:
                    discoveredAddresses.append(addr)
                    names.append(name)
                    protocols.append("ble")
                    manufacturers.append("")
                else:
                    for a in discoveredAddresses:
                        if addr == a:
                            found = True
                    if found == False:
                        discoveredAddresses.append(addr)
                        names.append(name)
                        protocols.append("ble")
                        manufacturers.append("")
        except:
            logging.debug('%s lescan skip', ModuleName)
    try:
        p.sendcontrol("c")
    except:
        logging.debug('%s Could not kill lescan process', ModuleName)
    d = {}
    d["status"] = "discovered"
    d["body"] = []
    for a in range (len(discoveredAddresses)):
        d["body"].append({"name": names[a], 
                          #"manufacturer_name": manufacturers[a], 
                          "protocol": protocols[a],
                          "address": discoveredAddresses[a]})
    print json.dumps(d)
