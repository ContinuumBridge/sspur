#!/usr/bin/env python
# cbanager_a.py
# Copyright (C) ContinuumBridge Limited, 2013-15 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
START_DELAY = 0.2                          # Delay between starting each adaptor or app
CONDUIT_WATCHDOG_MAXTIME = 120             # Max time with no message before notifying supervisor
CONDUIT_MAX_DISCONNECT_COUNT = 10          # Max number of messages before notifying supervisor
ELEMENT_WATCHDOG_INTERVAL = 120            # Interval at which to check apps/adaptors have communicated
ELEMENT_POLL_INTERVAL = 30                 # Delay between polling each element
APP_STOP_DELAY = 3                         # Time to allow apps/adaprts to stop before killing them
MIN_DELAY = 1                              # Min time to wait when a delay is needed
CONNECTION_WATCHDOG_INTERVAL = 60*60*1.5   # Reboot if no messages received for this time
CONNECTION_WATCHDOG_INTERVAL_1 = 60*10     # Startup to first connection watchdog check
WATCHDOG_CID = "CID65"                     # Client ID to send watchdog messages to
WATCHDOG_SEND_INTERVAL = 60*30             # How often to send messages to watchdog client
WATCHDOG_START_DELAY = 120                 # How long to wait before sending first watchdog message
ZWAYLOGFILE = "/var/log/z-way-server.log"  # Log file (used to delete if it grows very quickly
MAX_ZWAY_LOG_SIZE = 20000000               # If bigger than this, log will be delted

ModuleName = "Manager"
id = "manager"

import sys
import time
import os
import logging
import logging.handlers
import subprocess
import json
import urllib
import pexpect
# Try to use sftp first
try:
    import pysftp
    useSFTP = True
except:
    useSFTP = False
import ftplib
from twisted.internet import threads
from twisted.internet import reactor, defer
from twisted.internet import task
sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../lib')))
from cbcommslib import CbClientProtocol
from cbcommslib import CbClientFactory
from cbcommslib import CbServerProtocol
from cbcommslib import CbServerFactory
from cbcommslib import isotime
from cbconfig import *
import procname
if CB_RASPBERRY:
    import RPi.GPIO as GPIO
if CB_SIM_LEVEL == '1':
    from simdiscover import SimDiscover

CB_INC_UPGRADE_URL = 'https://github.com/ContinuumBridge/cbridge/releases/download/Incremental/bridge_clone_inc.tar.gz'
CB_INC_MD5_URL = 'https://github.com/ContinuumBridge/cbridge/releases/download/Incremental/bridge_clone_inc.md5'
CB_FULL_UPGRADE_URL = 'https://github.com/ContinuumBridge/cbridge/releases/download/Full/bridge_clone.tar.gz'
CB_FULL_MD5_URL = 'https://github.com/ContinuumBridge/cbridge/releases/download/Full/bridge_clone.md5'
CB_DEV_UPGRADE_URL = 'https://github.com/ContinuumBridge/cbridge/releases/download/Dev/bridge_clone_inc.tar.gz'
CB_DEV_MD5_URL = 'https://github.com/ContinuumBridge/cbridge/releases/download/Dev/bridge_clone_inc.md5'
CONCENTRATOR_PATH = CB_BRIDGE_ROOT + "/concentrator/concentrator.py"
ZWAVE_PATH = CB_BRIDGE_ROOT + "/manager/z-wave-ctrl.py"
USB_DEVICES_FILE = CB_BRIDGE_ROOT + "/manager/usb_devices.json"

LOGFILE_MAXBYTES    = 10000000
LOGFILE_BACKUPCOUNT = 5
logger = logging.getLogger('Logger')
logger.setLevel(CB_LOGGING_LEVEL)
handler = logging.handlers.RotatingFileHandler(CB_LOGFILE, maxBytes=LOGFILE_MAXBYTES, backupCount=LOGFILE_BACKUPCOUNT)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class ManageBridge:

    def __init__(self):
        procname.setprocname('captain')
        logger.info("%s ************************************************************", ModuleName)
        logger.info("%s Restart", ModuleName)
        logger.info("%s ************************************************************", ModuleName)
        logger.info("%s BEWARE. LOG TIMES MAY BE WRONG BEFORE TIME UPDATED VIA NTP", ModuleName)
        logger.info("%s CB_LOGGING_LEVEL =  %s", ModuleName, CB_LOGGING_LEVEL)
        try:
            versionFile =  CB_BRIDGE_ROOT + "/manager/" + "cb_version"
            with open(versionFile, 'r') as f:
                v = f.read()
            if v.endswith('\n'):
                v = v[:-1]
        except:
            v = "Unknown"
        self.version = v
        logger.info("%s Bridge version =  %s", ModuleName, v)
        logger.info("%s ************************************************************", ModuleName)
        logger.info("%s CB_NO_CLOUD = %s", ModuleName, CB_NO_CLOUD)
        self.bridge_id = CB_BID
        logger.info("%s CB_BID = %s", ModuleName, CB_BID)
        self.bridgeStatus = "ok" # Used to set status for sending to supervisor
        self.timeLastConduitMsg = time.time()  # For watchdog
        self.disconnectedCount = 0  # Used to count "disconnected" messages from conduit
        self.controllerConnected = False
        self.zwaveDiscovered = False
        self.zwaveDiscovering = False
        self.bleDiscovered = False
        self.configured = False
        self.connection = "none"
        self.restarting = False
        self.zExcluding = False
        self.zwaveShouldExcludeID = None
        self.reqSync = False
        self.state = "stopped"
        self.concNoApps = False
        self.firstWatchdog = True
        self.firstConnectionWatchdog = True
        self.elements = {}
        self.appProcs = {}
        self.concConfig = []
        self.appConfigured = []
        self.cbFactory = {} 
        self.appListen = {}
        self.zwaveDevices = []
        self.elFactory = {}
        self.elListen = {}
        self.elProc = {}
        self.batteryLevels = []
        self.idToName = {}
        self.bluetooth = False
        self.rxCount = 1  # Used for watchdog. Set to 1 to overcome NTP change on startup issues
        self.upSince = 0  # To enable reporting
        self.ledState = False

        # Setup pin 26 as indicator LED
        if CB_RASPBERRY:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(26, GPIO.OUT)
                self.useLED = True
            except Exception as ex:
                self.useLED = False
                logger.warning("Failed to set up LED. Exception: {}, {}".format(type(ex), ex.args))
        else:
            self.useLED = False
        status = self.readConfig()
        logger.info('%s Read config status: %s', ModuleName, status)
        if CB_SIM_LEVEL == '1':
            self.simDiscover = SimDiscover(self.bridge_id)
        self.initBridge()

    def setState(self, action):
        if action == "clear_error":
            self.state = "running"
        else:
            self.state = action
        logger.info('%s state = %s', ModuleName, self.state)
        self.sendControllerMsg("patch", "/api/bridge/v1/bridge/" + self.bridge_id[3:] + "/", {"status": self.state})
        #self.sendStatusMsg("Bridge state: " + self.state)

    def reconnect(self):
        logger.info('%s Reconnecting conduit', ModuleName)
        try:
            self.nodejsProc.kill()
        except:
            logger.debug('%s reconnect, no node  process to kill', ModuleName)
        self.connectConduit()
        reactor.callLater(MIN_DELAY*3, self.reconnectToConduit)

    def disconnectConduit(self):
        logger.info('%s disconnectConduit', ModuleName)
        try:
            self.nodejsProc.kill()
        except:
            logger.debug('%s reconnect, no node  process to kill', ModuleName)

    def reconnectToConduit(self):
        self.cbSendConcMsg({"cmd": "reconnect"})
        
    def connectConduit(self):
        if CB_NO_CLOUD != "True":
            logger.info('%s Starting conduit', ModuleName)
            #exe = "/opt/node/bin/node"
            exe = CB_NODE_COMMAND
            #exe = "nodejs"
            path = CB_BRIDGE_ROOT + "/nodejs/index.js"
            logger.debug("{} node exe: {}, path: {}, CB_CONTROLLER_ADDR: {}, CB_BRIDGE_EMAIL: {}, CB_BRIDGE_PASSWORD: {}".format(ModuleName, exe, path,  CB_CONTROLLER_ADDR, CB_BRIDGE_EMAIL, CB_BRIDGE_PASSWORD))
            try:
                self.nodejsProc = subprocess.Popen([exe, path,  CB_CONTROLLER_ADDR, CB_BRIDGE_EMAIL, CB_BRIDGE_PASSWORD])
            except Exception as ex:
                logger.error('%s node failed to start. exe = %s. Exception: %s, %s', ModuleName, exe, type(ex), str(ex.args))
        else:
            logger.info('%s Running without Cloud Server', ModuleName)

    def initBridge(self):
        self.connectConduit()
        # Give time for node interface to start
        reactor.callLater(START_DELAY + 1, self.startElements)
        reactor.callLater(START_DELAY + 0.5, self.manageLED)
        reactor.run()

    def manageLED(self):
        if self.useLED:
            if self.controllerConnected:
                self.ledState = True
            else:
                self.ledState = not self.ledState
            if self.ledState:
                GPIO.output(26,GPIO.HIGH)
            else:
                GPIO.output(26,GPIO.LOW)
            reactor.callLater(0.5, self.manageLED)

    def checkZwave(self):
        if CB_RASPBERRY:
            zwayFilename = "/opt/z-way-server/z-way-server"
            if os.path.isfile(zwayFilename):
                self.zwave = True
            else:
                self.zwave = False
            logger.info("%s Z-Wave installed on bridge: %s", ModuleName, self.zwave)
        else:
            self.zwave = False

    def checkBluetooth(self):
        try:
            hci0 = subprocess.check_output(["hciconfig"])
            if "hci0" in hci0:
                logger.info("%s Bluetooth dongle detected", ModuleName)
                self.bluetooth = True
                self.resetBluetooth()
            else:
                logger.info("%s No Bluetooth dongle detected", ModuleName)
                self.bluetooth = False
        except Exception as ex:
            logger.warning('%s Problem checking Bluetooth', ModuleName)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def resetBluetooth(self):
        # Called in a thread
        logger.debug("%s resetBluetooth", ModuleName)
        try:
            s = subprocess.check_output(["hciconfig", "hci0", "down"])
            if s != '':
                logger.warning("%s Problem configuring hci0 (down): %s", ModuleName, s)
            else:
                logger.debug("%s hci0 down OK", ModuleName)
            time.sleep(MIN_DELAY)
            s = subprocess.check_output(["hciconfig", "hci0", "up"])
            if s != '':
                logger.warning("%s Problem configuring hci0 (up), %s", ModuleName, s)
            else:
                logger.debug("%s hci0 up OK", ModuleName)
        except Exception as ex:
            logger.warning("%s Unable to configure hci0", ModuleName)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def listMgrSocs(self):
        mgrSocs = {}
        for d in self.devices:
            mgrSocs[d["id"]] = d["adaptor"]["mgrSoc"]
        for a in self.apps:
            mgrSocs[a["app"]["id"]] = a["app"]["mgrSoc"]
        return mgrSocs

    def startElements(self):
        # First start connection watchdog, in case anything goes wrong
        reactor.callLater(CONNECTION_WATCHDOG_INTERVAL_1, self.connectionWatchdog)
        reactor.callLater(WATCHDOG_START_DELAY, self.sendWatchdogMsg)
        # Initiate comms with supervisor, which started the manager in the first place
        s = CB_SOCKET_DIR + "SKT-SUPER-MGR"
        initMsg = {"id": "manager",
                   "msg": "status",
                   "status": "ok"} 
        try:
            self.cbSupervisorFactory = CbClientFactory(self.onSuperMessage, initMsg)
            reactor.connectUNIX(s, self.cbSupervisorFactory, timeout=60)
            logger.info('%s Opened supervisor socket %s', ModuleName, s)
        except Exception as ex:
            logger.error('%s Cannot open supervisor socket %s', ModuleName, s)
            logger.error("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

        if CB_RASPBERRY:
            try:
                reactor.callInThread(self.checkBluetooth)
            except Exception as ex:
                logger.warning("%s Unable to to call checkBluetooth, exception: %s %s", ModuleName, type(ex), str(ex.args))
        self.checkZwave()
        els = [{"id": "conc",
                "socket": "SKT-MGR-CONC",
                "exe": CONCENTRATOR_PATH
               }]
        if self.zwave:
            els.append(
               {"id": "zwave",
                "socket": "SKT-MGR-ZWAVE",
                "exe": ZWAVE_PATH
               })
        for el in els:
            s = CB_SOCKET_DIR + el["socket"]
            try:
                self.elFactory[el["id"]] = CbServerFactory(self.onClientMessage)
                self.elListen[el["id"]] = reactor.listenUNIX(s, self.elFactory[el["id"]], backlog=10)
                logger.debug('%s Opened manager socket: %s', ModuleName, s)
            except Exception as ex:
                logger.error('%s Failed to open socket: %s', ModuleName, s)
                logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
    
            # Now start the element in a subprocess
            try:
                if el["id"] == "conc":
                    self.elProc[el["id"]] = subprocess.Popen([el["exe"], s, el["id"], self.bridge_id])
                else:
                    self.elProc[el["id"]] = subprocess.Popen([el["exe"], s, el["id"]])
                logger.debug('%s Started %s', ModuleName, el["id"])
            except Exception as ex:
                logger.error('%s Failed to start %s', ModuleName, el["id"])
                logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
    
    def removeSecondarySockets(self):
        # There should be no sockets to remove if there is no config file
        # Also there are no apps and adaptors without a config file
        if self.configured:
            for a in self.apps:
                for appDev in a["device_permissions"]:
                    socket = appDev["adtSoc"]
                    try:
                        os.remove(socket) 
                        logger.debug('%s Socket %s removed', ModuleName, socket)
                    except:
                        logger.debug('%s Socket %s already removed', ModuleName, socket)
            for d in self.devices:
                if d["adaptor"]["protocol"] == "zwave":
                    socket = d["adaptor"]["zwave_socket"]
                    try:
                        os.remove(socket) 
                    except:
                        logger.debug('%s Socket %s already removed', ModuleName, socket)

    def startAll(self):
        self.configureConc()
        self.cbFactory.clear()
        mgrSocs = self.listMgrSocs()
        # Open sockets for communicating with all apps and adaptors
        for s in mgrSocs:
            if s not in self.cbFactory:
                try:
                    self.cbFactory[s] = CbServerFactory(self.onClientMessage)
                    self.appListen[s] = reactor.listenUNIX(mgrSocs[s], self.cbFactory[s], backlog=4)
                    logger.info('%s Opened manager socket %s %s', ModuleName, s, mgrSocs[s])
                except:
                    logger.info('%s Manager socket already exists %s %s', ModuleName, s, mgrSocs[s])
        delay = START_DELAY 
        # This ensures that any deleted adaptors/apps are removed from watchdog:
        self.elements = {}
        for d in self.devices:
            id = d["id"]
            self.elements[id] = False
            if not id in self.appProcs:
                exe = d["adaptor"]["exe"]
                mgrSoc = d["adaptor"]["mgrSoc"]
                friendlyName = d["friendly_name"]
                reactor.callLater(delay, self.startAdaptor, exe, mgrSoc, id, friendlyName)
                delay += START_DELAY
        # Now start all the apps
        delay += START_DELAY*4
        for a in self.apps:
            id = a["app"]["id"]
            self.elements[id] = False
            if not id in self.appProcs:
                exe = a["app"]["exe"]
                mgrSoc = a["app"]["mgrSoc"]
                reactor.callLater(delay, self.startApp, exe, mgrSoc, id)
                delay += START_DELAY
        # Start watchdog to monitor apps and adaptors (only first time through)
        if self.firstWatchdog:
            reactor.callLater(delay+ELEMENT_WATCHDOG_INTERVAL, self.elementWatchdog)
            # Give time for everything to start before we consider ourselves running
        self.setState("starting")
        reactor.callLater(5, self.checkRunning)
        logger.info('%s All adaptors and apps set to start', ModuleName)

    def startAdaptor(self, exe, mgrSoc, id, friendlyName):
        try:
            p = subprocess.Popen([id, mgrSoc, id], executable=exe)
            self.appProcs[id] = p
            logger.info('%s Started adaptor %s ID: %s', ModuleName, friendlyName, id)
        except Exception as ex:
            logger.error('%s Adaptor %s failed to start', ModuleName, friendlyName)
            logger.error('%s Params: %s %s %s', ModuleName, exe, id, mgrSoc)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def startApp(self, exe, mgrSoc, id):
        try:
            p = subprocess.Popen([exe, mgrSoc, id])
            self.appProcs[id] = p
            logger.info('%s App %s started', ModuleName, id)
        except Exception as ex:
            logger.error('%s App %s failed to start. exe: %s, socket: %s', ModuleName, id, exe, mgrSoc)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def checkRunning(self):
        logger.debug('%s checkRunning, elements: %s', ModuleName, str(self.elements))
        running = True
        for e in self.elements:
            if self.elements[e] == False:
                running = False
        if running:
            self.setState("running")
            self.upSince = time.time()
        else:
            reactor.callLater(5, self.checkRunning)
 
    def bleDiscover(self):
        self.resetBluetooth()
        self.bleDiscoveredData = [] 
        exe = CB_BRIDGE_ROOT + "/manager/discovery.py"
        protocol = "ble"
        output = subprocess.check_output([exe, protocol, str(CB_SIM_LEVEL), CB_CONFIG_DIR])
        logger.info('%s Discovery output: %s', ModuleName, output)
        try:
            discOutput = json.loads(output)
        except Exception as ex:
            logger.error('%s Unable to load output from discovery.py', ModuleName)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            reactor.callFromThread(self.sendStatusMsg, "Error. Unable to load output from discovery.py")
        else:   
            bleNames = ""
            if discOutput["status"] == "discovered":
                if self.configured:
                    for d in discOutput["body"]:
                        addrFound = False
                        if d["protocol"] == "ble":
                            if self.devices == []:
                                bleNames += d["name"] + ", "
                            else:
                                for oldDev in self.devices:
                                    if oldDev["device"]["protocol"] == "btle" or oldDev["device"]["protocol"] == "ble": 
                                        if d["address"] == oldDev["address"]:
                                            addrFound = True
                                        else:
                                            bleNames += d["name"] + ", "
                        if addrFound == False:
                            self.bleDiscoveredData.append(d)  
                else:
                    for d in discOutput["body"]:
                        self.bleDiscoveredData.append(d)  
                        bleNames += d["name"] + ", "
            else:
                logger.warning('%s Error in ble discovery', ModuleName)
            logger.info('%s Discovered devices:', ModuleName)
            logger.info('%s %s', ModuleName, self.bleDiscoveredData)
            if bleNames != "":
                bleNames= bleNames[:-2]
                logger.info('%s  BLE devices found: %s', ModuleName, bleNames)
                reactor.callFromThread(self.sendStatusMsg, "BLE devices found: " + bleNames)
            reactor.callFromThread(self.onBLEDiscovered)
            self.discovered = True
            return
    
    def usbDiscover(self):
        self.usbDiscovered = False
        usb_devices = []    # In case file doesn't load
        self.usbDiscoveredData = []
        try:
            with open(USB_DEVICES_FILE, 'r') as f:
                usb_devices = json.load(f)
                logger.info('%s Read usb devices file', ModuleName)
        except:
            logger.warning('%s No usb devices file exists or file is corrupt', ModuleName)
        lsusb = subprocess.check_output(["lsusb"])
        devs = lsusb.split("\n")
        for d in devs:
            details = d.split()
            logger.debug('%s usbDiscover. details: %s', ModuleName, details)
            if details != []:
                for known_device in usb_devices:
                    if details[5] == known_device["id"]:
                        if self.configured:
                            addrFound = False
                            address = details[3][:3]
                            for oldDev in self.devices:
                                if oldDev["device"]["protocol"] == "zwave":
                                        if address == oldDev["address"]:
                                            addrFound = True
                                            break
                            if addrFound == False:
                                self.usbDiscovered = True
                                self.usbDiscoveredData.append({"protocol": "zwave",
                                                               "name": known_device["name"],
                                                               "mac_addr": address
                                                             })
                                reactor.callFromThread(self.gatherDiscovered)
                        else:
                            self.usbDiscovered = True
                            self.usbDiscoveredData.append({"protocol": "zwave",
                                                           "name": known_device["name"],
                                                           "mac_addr": address
                                                         })
                            reactor.callFromThread(self.gatherDiscovered)
    
    def onZwaveDiscovering(self, msg):
        logger.debug('%s onZwaveDiscovering', ModuleName)
        self.zwaveDiscovering = True
        self.sendStatusMsg("Z-wave device found. Identifyiing it. This may take up to 30 seconds.")

    def onZwaveDiscovered(self, msg):
        logger.debug('%s onZwaveDiscovered', ModuleName)
        self.zwaveDiscoveredData = msg["body"]
        self.zwaveDiscovered = True
        self.gatherDiscovered()

    def onBLEDiscovered(self):
        logger.debug('%s onBLEDiscovered', ModuleName)
        self.bleDiscovered = True
        if not (self.zwaveDiscovered or self.zwaveDiscovering):
            self.gatherDiscovered()

    def gatherDiscovered(self):
        logger.debug('%s gatherDiscovered', ModuleName)
        d = {}
        d["source"] = self.bridge_id
        d["destination"] = "cb"
        d["time_sent"] = isotime()
        d["body"] = {}
        d["body"]["resource"] = "/api/bridge/v1/discovered_device/"
        d["body"]["verb"] = "patch"
        d["body"]["body"] = {}
        d["body"]["body"]["objects"] = []
        if self.usbDiscovered:
            d["body"]["body"]["objects"] = self.usbDiscoveredData
        else:
            if self.bleDiscovered and not self.zwaveDiscovered:
                if self.bleDiscoveredData:
                    for b in self.bleDiscoveredData:
                        d["body"]["body"]["objects"].append(b)
                    self.bleDiscoverPosted = True
                else:
                    self.sendStatusMsg("No Bluetooth devices found.")
            if self.zwaveDiscovered:
                for b in self.zwaveDiscoveredData:
                    d["body"]["body"]["objects"].append(b)
        logger.debug('%s Discovered: %s', ModuleName, str(d))
        if d["body"]["body"]["objects"] != []:
            msg = {"cmd": "msg",
                   "msg": d}
            self.cbSendConcMsg(msg)
        if self.zwaveDiscovered:
            self.sendControllerMsg("patch", "/api/bridge/v1/bridge/" + self.bridge_id[3:] + "/", {"zwave": "operational"})

    def discover(self):
        logger.debug('%s discover', ModuleName)
        if CB_SIM_LEVEL == '1':
            d = self.simDiscover.discover(isotime())
            msg = {"cmd": "msg",
                   "msg": d}
            logger.debug('%s simulated discover: %s', ModuleName, msg)
            self.cbSendConcMsg(msg)
            return
        # If there are peripherals report any that are not reported rather than discover
        logger.debug('%s CB_PERIPHERALS: %s', ModuleName, CB_PERIPHERALS)
        if CB_PERIPHERALS != "none":
            found = True
            newPeripheral = ''
            logger.debug('%s Checking for peripherals: %s', ModuleName, CB_PERIPHERALS)
            peripherals = CB_PERIPHERALS.split(',')
            peripherals = [p.strip(' ') for p in peripherals]
            for p in peripherals:
                for dev in self.devices:
                    logger.debug('%s peripheral: %s, device: %s', ModuleName, p, dev["adaptor"]["name"])
                    if p in dev["adaptor"]["name"] or p == "none":
                        found = False
                        break
                if found:
                    newPeripheral = p
                    break
            if found:
                d = {}
                d["source"] = self.bridge_id
                d["destination"] = "cb"
                d["time_sent"] = isotime()
                d["body"] = {}
                d["body"]["resource"] = "/api/bridge/v1/device_discovery/"
                d["body"]["verb"] = "patch"
                d["body"]["body"] = {}
                d["body"]["body"]["objects"] = []
                b = {'manufacturer_name': 0, 
                     'protocol': 'peripheral', 
                     'address': '', 
                     'name': newPeripheral,
                     'model_number': 0
                    }
                d["body"]["body"]["objects"].append(b)
                msg = {"cmd": "msg",
                       "msg": d}
                self.cbSendConcMsg(msg)
        if CB_PERIPHERALS == "none" or not found:
            if self.zwave:
                self.sendControllerMsg("patch", "/api/bridge/v1/bridge/" + self.bridge_id[3:] + "/", {"zwave": "include"})
                self.elFactory["zwave"].sendMsg({"cmd": "discover"})
                self.zwaveDiscovering = False
                self.zwaveDiscovered = False
            if self.bluetooth:
                self.bleDiscovered = False
                self.bleDiscoverPosted = False
                reactor.callInThread(self.bleDiscover)
            reactor.callInThread(self.usbDiscover)
            self.sendStatusMsg("Follow manufacturer's instructions for device to be connected now.")

    def onZwaveExcluded(self, address):
        logger.debug('%s onZwaveExclude, address: %s', ModuleName, address)
        msg = "No Z-wave device was excluded. No button pressed on device?"
        if address == "" or address == "None":
            msg= "No Z-wave device was excluded.\n Remember some devices need one click and others three. \n Also, devices need to be near the bridge to exclude."
        elif address == "0":
            msg = "Reset a device from a different Z-Wave controller"
        else:
            found = False
            for d in self.devices:
                if d["address"] == address:
                    found = True
                    excludedID = str(d["id"][3:])
                    logger.debug('%s onZwaveExclude, excludeID: %s, zwaveShouldExcludeID: %s', ModuleName, excludedID, self.zwaveShouldExcludeID)
                    if excludedID == self.zwaveShouldExcludeID:
                        self.sendControllerMsg("delete", "/api/bridge/v1/device_install/" + excludedID +"/")
                        msg = "Excluded " + d["friendly_name"]
                    elif self.zwaveShouldExcludeID == None:
                        self.sendControllerMsg("delete", "/api/bridge/v1/device_install/" + excludedID +"/")
                        msg = "Excluded " + d["friendly_name"]
                    else:
                        self.sendControllerMsg("patch", "/api/bridge/v1/device_install/" + self.zwaveShouldExcludeID +"/", {"status": "uninstall_error"})
                        reactor.callLater(0.2, self.sendControllerMsg, "delete", "/api/bridge/v1/device_install/" + excludedID +"/")
                        msg = "Excluded " + d["friendly_name"]
                    break
                self.getConfig()
            if not found:
                if self.zwaveShouldExcludeID != None:
                    self.sendControllerMsg("patch", "/api/bridge/v1/device_install/" + self.zwaveShouldExcludeID +"/", {"status": "operational"})
                msg= "Excluded Z-Wave device at address " + address
        self.sendControllerMsg("patch", "/api/bridge/v1/bridge/" + self.bridge_id[3:] + "/", {"zwave": "operational"})
        self.zExcluding = False
        self.zwaveShouldExcludeID = None
        self.sendStatusMsg(msg)

    def zwaveExclude(self):
        logger.debug('%s zwaveExclude', ModuleName)
        if self.zwave:
            if not self.zExcluding:
                self.zExcluding = True
                self.elFactory["zwave"].sendMsg({"cmd": "exclude"})
                self.sendControllerMsg("patch", "/api/bridge/v1/bridge/" + self.bridge_id[3:] + "/", {"zwave": "exclude"})
                self.sendStatusMsg("Follow manufacturer's instructions for Z-wave device to be excluded")
        else:
            self.sendStatusMsg("Bridge does not support Z-wave. Can't exclude")

    def readConfig(self):
        # BEWARE. SOMETIMES CALLED IN A THREAD.
        appRoot = CB_HOME + "/apps/"
        adtRoot = CB_HOME + "/adaptors/"
        if CB_DEV_BRIDGE:
            logger.warning('%s Development user (CB_USERNAME): %s', ModuleName, CB_USERNAME)
            self.devApps = CB_DEV_APPS.split(',')
            self.devApps = [x.strip(' ') for x in self.devApps]
            logger.debug('%s self.devApps: %s', ModuleName, self.devApps)
            self.devAdaptors = CB_DEV_ADAPTORS.split(',')
            self.devAdaptors = [x.strip(' ') for x in self.devAdaptors]
            logger.debug('%s self.devAdaptors: %s', ModuleName, self.devAdaptors)
            if CB_USERNAME == 'none':
                logger.warning('%s CB_DEV_BRIDGE=True, but CB_USERNAME not set, so apps_dev and adaptors_dev not used', ModuleName)
                appRootDev = appRoot
                adtRootDev = adtRoot
            else:   
                appRootDev = CB_HOME + "/apps_dev/"
                adtRootDev = CB_HOME + "/adaptors_dev/"
            logger.debug('%s appRootDev: %s', ModuleName, appRootDev)
            logger.debug('%s adtRootDev: %s', ModuleName, adtRootDev)
        configFile = CB_CONFIG_DIR + "/bridge.config"
        configRead = False
        try:
            with open(configFile, 'r') as f:
                config = json.load(f)
                configRead = True
                logger.info('%s Read config', ModuleName)
        except Exception as ex:
            logger.warning('%s No config file exists or file is corrupt', ModuleName)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            success= False
        if configRead:
            try:
                self.apps = config["body"]["body"]["apps"]
                self.devices = config["body"]["body"]["devices"]
                success = True
            except Exception as ex:
                logger.error('%s bridge.config appears to be corrupt. Ignoring', ModuleName)
                logger.error("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
                success = False

        if success:
            # Process config to determine routing:
            logger.info('%s Config file for bridge %s read successfully. Processing', ModuleName, self.bridge_id)
            for d in self.devices:
                d["id"] = "DID" + str(d["id"])
                socket = CB_SOCKET_DIR + "SKT-MGR-" + str(d["id"])
                d["adaptor"]["mgrSoc"] = socket
                url = d["adaptor"]["url"]
                split_url = url.split('/')
                if CB_DEV_BRIDGE and d["adaptor"]["name"] in self.devAdaptors:
                    dirName = split_url[-3]
                    d["adaptor"]["exe"] = adtRootDev + dirName + "/" + d["adaptor"]["exe"]
                else:
                    dirName = (split_url[-3] + '-' + split_url[-1])[:-7]
                    d["adaptor"]["exe"] = adtRoot + dirName + "/" + d["adaptor"]["exe"]
                logger.debug('%s exe: %s', ModuleName, d["adaptor"]["exe"])
                logger.debug('%s protocol: %s', ModuleName, d["device"]["protocol"])
                if d["device"]["protocol"] == "zwave":
                    d["adaptor"]["zwave_socket"] =  CB_SOCKET_DIR + "SKT-" + d["id"] + "-zwave"
                # Add a apps list to each device adaptor
                d["adaptor"]["apps"] = []
                if d["id"] not in self.idToName:
                    self.idToName.update({d["id"]: d["friendly_name"]})
            # Add socket descriptors to apps and devices
            for a in self.apps:
                a["app"]["id"] = "AID" + str(a["app"]["id"])
                url = a["app"]["url"]
                split_url = url.split('/')
                if CB_DEV_BRIDGE and a["app"]["name"] in self.devApps:
                    dirName = split_url[-3]
                    a["app"]["exe"] = appRootDev + dirName + "/" + a["app"]["exe"]
                else:
                    dirName = (split_url[-3] + '-' + split_url[-1])[:-7]
                    a["app"]["exe"] = appRoot + dirName + "/" + a["app"]["exe"]
                logger.debug('%s exe: %s', ModuleName, a["app"]["exe"])
                a["app"]["mgrSoc"] = CB_SOCKET_DIR + "SKT-MGR-" + str(a["app"]["id"])
                a["app"]["concSoc"] = CB_SOCKET_DIR + "SKT-CONC-" + str(a["app"]["id"])
                if a["app"]["id"] not in self.idToName:
                    self.idToName.update({a["app"]["id"]: a["app"]["name"]})
                for appDev in a["device_permissions"]:
                    uri = appDev["device_install"]
                    for d in self.devices: 
                        if d["resource_uri"] == uri:
                            socket = CB_SOCKET_DIR + "SKT-" \
                                + str(d["id"]) + "-" + str(a["app"]["id"])
                            d["adaptor"]["apps"].append(
                                                    {"adtSoc": socket,
                                                     "name": a["app"]["name"],
                                                     "id": a["app"]["id"]
                                                    }) 
                            appDev["adtSoc"] = socket
                            appDev["id"] = d["id"]
                            appDev["name"] = d["adaptor"]["name"]
                            appDev["friendly_name"] = \
                                d["friendly_name"]
                            appDev["adtSoc"] = socket
                            break
        if success:
            logger.debug("%s idToName: %s", ModuleName, str(self.idToName))
            self.configured = True
        return success

    def downloadElement(self, el):
        tarDir = CB_HOME + "/" + el["type"]
        tarFile =  tarDir + "/" + el["name"] + ".tar.gz"
        logger.debug('%s tarDir: %s, tarFile: %s', ModuleName, tarDir, tarFile)
        urllib.urlretrieve(el["url"], tarFile)
        try:
            # By default tar xf overwrites existing files
            subprocess.check_call(["tar", "xfz",  tarFile, "--overwrite", "-C", tarDir, "--transform", "s/-/-v/"])
            logger.info('%s Extracted %s', ModuleName, tarFile)
            return "ok"
        except Exception as ex:
            logger.warning('%s Error extracting %s', ModuleName, tarFile)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            return "Error extraxting " + tarFile 

    def updateElements(self):
        """
        Directoriies: CB_HOME/apps/<appname>, CB_HOME/adaptors/<adaptorname>.
        Check if appname/adaptorname exist. If not, download app/adaptor.
        If directory does exist, check version file inside & download if changed.
        """
        # THIS METHOD IS IN A THREAD
        updateList = []
        d = CB_HOME + "/adaptors"
        if not os.path.exists(d):
            os.makedirs(d)
        dirs = os.listdir(d)
        for dev in self.devices:
            if CB_DEV_BRIDGE and dev["adaptor"]["name"] in self.devAdaptors:
                logger.debug('%s updateElements. Using %s from adaptors_dev', ModuleName, dev["adaptor"]["name"])
            else:
                url = dev["adaptor"]["url"] 
                split_url = url.split('/')
                logger.debug('%s updateElements. split_url: %s', ModuleName, split_url)
                logger.debug('%s updateElements. split_url[-3]: %s', ModuleName, split_url[-3])
                name = (split_url[-3] + '-' + split_url[-1])[:-7]
                logger.debug('%s updateElements. name: %s', ModuleName, name)
                logger.debug('%s updateElements. Current updateList: %s', ModuleName, updateList)
                update = False
                if name not in dirs:
                    update = True
                    for u in updateList:
                        logger.debug('%s updateElements. u["name"]: %s', ModuleName, u["name"])
                        if u["name"] == name: 
                            update = False
                if update:
                    updateList.append({"url": url, "type": "adaptors", "name": name})
        d = CB_HOME + "/apps"
        if not os.path.exists(d):
            os.makedirs(d)
        dirs = os.listdir(d)
        for app in self.apps:
            if CB_DEV_BRIDGE and app["app"]["name"] in self.devApps:
                logger.debug('%s updateElements. Using %s from apps_dev', ModuleName, app["app"]["name"])
            else:
                url = app["app"]["url"]
                split_url = url.split('/')
                logger.debug('%s updateElements. split_url: %s', ModuleName, split_url)
                logger.debug('%s updateElements. split_url[-3]: %s', ModuleName, split_url[-3])
                name = (split_url[-3] + '-' + split_url[-1])[:-7]
                logger.debug('%s updateElements. name: %s', ModuleName, name)
                update = False
                if name not in dirs:
                    update = True
                    for u in updateList:
                        if u["name"] == name: 
                            update = False
                if update:
                    updateList.append({"url": url, "type": "apps", "name": name})

        logger.info('%s updateList: %s', ModuleName, updateList)
        for e in updateList:
            logger.debug('%s Iterating updateList', ModuleName)
            status = self.downloadElement(e)
            if status != "ok":
                reactor.callFromThread(self.sendStatusMsg, status)
        if updateList == []:
            return "Updated. All apps and adaptors already at latest versions"
        else:
            logger.debug('%s updateList != []', ModuleName)
            feedback = "Updated: "
            for a in updateList:
                feedback += " " + a["name"]
            return feedback

    def updateConfig(self, msg):
        # THIS METHOD IS IN A THREAD
        #logger.info('%s Config update received from controller', ModuleName)
        #reactor.callFromThread(self.sendStatusMsg, "Updating. This may take a minute")
        #logger.debug('%s %s', ModuleName, str(msg))
        configFile = CB_CONFIG_DIR + "/bridge.config"
        with open(configFile, 'w') as configFile:
            json.dump(msg, configFile)
        success = self.readConfig()
        logger.info('%s Update config, read config status: %s', ModuleName, success)
        if success:
            try:
                status = self.updateElements()
            except Exception as ex:
                logger.warning('%s Update config. Something went badly wrong updating apps and adaptors', ModuleName)
                logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
                status = "Something went badly wrong updating apps and adaptors"
        else:
            status = "Update failed"
            logger.warning('%s Update config. Failed to update ', ModuleName)
        reactor.callFromThread(self.sendStatusMsg, status)
        # Need to give concentrator new config if initial one was without apps
        #if self.concNoApps:
        #    req = {"status": "req-config",
        #           "type": "conc"}
        #    reactor.callFromThread(self.onClientMessage, req)
        #    self.concNoApps = False

    def getConfig(self):
        req = {"cmd": "msg",
               "msg": {"source": self.bridge_id,
                       "destination": "cb",
                       "time_sent": isotime(),
                       "body": {
                                "resource": "/api/bridge/v1/current_bridge/bridge",
                                "verb": "get"
                               }
                      }
              }
        self.cbSendConcMsg(req)

    def upgradeBridge(self, command):
        if self.state == "upgrading":
            reactor.callFromThread(self.sendStatusMsg, "Upgrade already in progress. Command ignored")
            return
        self.setState("upgrading")
        reactor.callFromThread(self.sendStatusMsg, "Upgrade in progress. Please wait")
        try:
            u = command.split()
            if len(u) == 1:
                upgradeURL = CB_INC_UPGRADE_URL
                md5URL = CB_INC_MD5_URL
            elif u[1] == "full":
                upgradeURL = CB_FULL_UPGRADE_URL
                md5URL = CB_FULL_MD5_URL
            elif u[1] == "dev":
                upgradeURL = CB_DEV_UPGRADE_URL
                md5URL = CB_DEV_MD5_URL
            else:
                self.sendStatusMsg("Unknown upgrade type. Ignoring")
                return
        except Exception as ex:
            logger.warning('%s Pooblem with upgrade command %s', ModuleName, str(command))
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            self.sendStatusMsg("Bad upgrade command. Allowed options: none|full|dev")
            return
        reactor.callFromThread(self.sendStatusMsg, "Downloading from: " + upgradeURL)
        upgradeStat = ""
        tarFile = CB_HOME + "/bridge_clone.tar.gz"
        logger.debug('%s tarFile: %s', ModuleName, tarFile)
        try:
            urllib.urlretrieve(upgradeURL, tarFile)
            urllib.urlretrieve(md5URL, "md5")
        except Exception as ex:
            logger.error('%s Cannot access GitHub file to upgrade', ModuleName)
            logger.error("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            reactor.callFromThread(self.sendStatusMsg, "Cannot access GitHub file to upgrade")
            return
        try:
            md5a = subprocess.check_output(["md5sum", tarFile])
            md5 = md5a.split()[0]
            with open("md5", "r") as f:
                md5Origa = f.read()
            md5Orig = md5Origa.split()[0]
            logger.debug("md5: %s, md5Orig: %s", md5, md5Orig)
            if md5 != md5Orig:
                reactor.callFromThread(self.sendStatusMsg, "Failed to upgrade. Checksum did not match. Reverting to previous version")
                return
        except Exception as ex:
            logger.error('%s Problems checking checksum', ModuleName)
            logger.error("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            reactor.callFromThread(self.sendStatusMsg, "Failed to upgrade. Checksum problems. Reverting to previous version")
            return
        try:
            subprocess.check_call(["tar", "xfz",  tarFile, "--overwrite", "-C", CB_HOME])
            logger.info('%s Extract tarFile: %s', ModuleName, tarFile)
        except Exception as ex:
            logger.error('%s Unable to extract tarFile %s', ModuleName, tarFile)
            logger.error("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            reactor.callFromThread(self.sendStatusMsg, "Failed to upgrade. Reverting to previous version")
            return
        try:
            status = subprocess.check_output("../../bridge_clone/scripts/cbupgrade.py")
        except Exception as ex:
            logger.error('%s Unable to run upgrade script', ModuleName)
            logger.error("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            reactor.callFromThread(self.sendStatusMsg, "Failed to upgrade. Reverting to previous version")
            return
        bridgeDir = CB_HOME + "/bridge"
        bridgeSave = CB_HOME + "/bridge_save"
        bridgeClone = CB_HOME + "/bridge_clone"
        logger.info('%s Upgrade files: %s %s %s', ModuleName, bridgeDir, bridgeSave, bridgeClone)
        try:
            subprocess.call(["rm", "-rf", bridgeSave])
        except Exception as ex:
            logger.info('%s Could not remove bridgeSave', ModuleName)
            logger.info("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
        try:
            subprocess.call(["mv", bridgeDir, bridgeSave])
            logger.info('%s Moved bridgeDir to bridgeSave', ModuleName)
            subprocess.call(["mv", bridgeClone, bridgeDir])
            logger.info('%s Moved bridgeClone to bridgeDir', ModuleName)
            reactor.callFromThread(self.sendStatusMsg, "Upgrade successful. Restarting")
            reactor.callFromThread(self.cbSendSuperMsg, {"msg": "restart_cbridge"})
        except Exception as ex:
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            reactor.callFromThread(self.sendStatusMsg, "Upgrade failed. Problems moving versions")
    
    def waitToUpgrade(self, command):
        # Call in threaad as it can take some time & watchdog still going
        reactor.callInThread(self.upgradeBridge, command)

    def uploadLog(self, logFile, ftpPlace):
        status = "Major logfile upload problem"
        try:
            subprocess.call(["cp", logFile, ftpPlace])
        except Exception as ex:
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            status = "Could not locate file for upload: " + logFile
        else:
            ftpPassword = os.getenv('CB_SFTP_PASSWORD', 'NONE')
            try:
                cnopts = pysftp.CnOpts()
                cnopts.hostkeys = None
                srv = pysftp.Connection(host="ftp.continuumbridge.com", username="bridgelogs", password=ftpPassword, cnopts=cnopts)
                srv.chdir('logs')
                srv.put(ftpPlace)
                srv.close()
                status = ftpPlace + " successfully uploaded (sftp)"
            except Exception as ex:
                logger.warning("%s Could not upload using sftp. Exception: %s %s", ModuleName, type(ex), str(ex.args))
                status = "Could not upload log file using sftp: " + logFile
                try:
                    ftp = ftplib.FTP("ftp.continuumbridge.com")
                    ftp.login("bridgelogs", ftpPassword)
                    ftp.set_pasv(True)
                    ftp.cwd("logs")
                    uploadFile = open(ftpPlace, 'r')
                    ftp.storlines("STOR " + ftpPlace, uploadFile)
                    status = ftpPlace + " successfully uploaded (ftp)"
                except:
                    logger.warning("%s Could not upload using ftp. Exception: %s %s", ModuleName, type(ex), str(ex.args))
                    status = "Could not upload log file: " + logFile
        reactor.callFromThread(self.sendStatusMsg, status)
        try:
            subprocess.call(["rm", ftpPlace])
        except Exception as ex:
            logger.info("%s Exception: could not remove copied file after ftp%s %s", ModuleName, type(ex), str(ex.args))

    def sendLog(self, path, fileName):
        ftpPlace = CB_BID + '-' + fileName
        logger.info('%s Uploading %s to %s', ModuleName, path, ftpPlace)
        reactor.callInThread(self.uploadLog, path, ftpPlace)

    def onDeviceInstall(self, msg):
        logger.debug('%s onDeviceInstall', ModuleName)
        try:
            logger.debug('%s onDeviceInstall, verb: %s', ModuleName, msg["body"]["verb"])
            if msg["body"]["verb"] == "update":
                if msg["body"]["body"]["status"] == "should_uninstall":
                    logger.debug('%s onDeviceInstall. Uninstalling: %s ', ModuleName, msg["body"]["body"]["friendly_name"])
                    if msg["body"]["body"]["device"]["protocol"] == "zwave":
                        self.zwaveShouldExcludeID = str(msg["body"]["body"]["id"])
                        self.zwaveExclude()
                    else:
                        self.sendControllerMsg("delete", msg["body"]["body"]["resource_uri"] + "/")
            elif msg["body"]["verb"] == "delete":
                pass
            elif msg["body"]["verb"] == "create":
                if msg["body"]["body"]["status"] == "should_install":
                    self.sendControllerMsg("patch", msg["body"]["body"]["resource_uri"] + "/", {"status": "operational"})
                    # Until real-time updates implemented, just get full config when delete received
                    #self.getConfig()
            else:
                logger.debug('%s onDeviceInstall, unrecognised verb: %s', ModuleName, msg["body"]["verb"])
        except Exception as ex:
            logger.warning('%s onDeviceInstall error', ModuleName)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def onAppInstall(self, msg):
        logger.debug('%s onAppInstall', ModuleName)
        try:
            logger.debug('%s onAppnstall, verb: %s', ModuleName, msg["body"]["verb"])
            if msg["body"]["verb"] == "update":
                if msg["body"]["body"]["status"] == "should_install":
                    self.sendControllerMsg("patch", msg["body"]["body"]["resource_uri"] + "/", {"status": "installing"})
                    self.sendControllerMsg("patch", msg["body"]["body"]["resource_uri"] + "/", {"status": "operational"})
                    # Until real-time updates implemented, just get full config when delete received
                    #self.getConfig()
                elif msg["body"]["body"]["status"] == "should_uninstall":
                    #self.sendControllerMsg("patch", msg["body"]["body"]["resource_uri"] + "/", {"status": "uninstalling"})
                    self.sendControllerMsg("delete", msg["body"]["body"]["resource_uri"] + "/")
                    # Until real-time updates implemented, just get full config when delete received
                    #self.getConfig()
                else:
                    logger.debug('%s onAppInstall, update. Unrecognised status: %s', ModuleName, msg["body"]["body"]["status"])
            elif msg["body"]["verb"] == "create":
                # Until real-time updates implemented, just get full config when create received
                if msg["body"]["body"]["status"] == "should_install":
                    self.sendControllerMsg("patch", msg["body"]["body"]["resource_uri"] + "/", {"status": "operational"})
                    # Until real-time updates implemented, just get full config when delete received
                    #self.getConfig()
                else:
                    logger.debug('%s onAppInstall, create. Unrecognised status: %s', ModuleName, msg["body"]["body"]["status"])
            else:
                logger.debug('%s onAppInstall, unrecognised verb: %s', ModuleName, msg["body"]["verb"])
        except Exception as ex:
            logger.warning('%s onAppInstall error', ModuleName)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def doCall(self, cmd):
        try:
            output = subprocess.check_output(cmd, shell=True)
            logger.debug('%s Output from call: %s', ModuleName, output)
        except Exception as ex:
            logger.warning('%s Error in running call: %s', ModuleName, cmd)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            output = "Error in running call"
        reactor.callFromThread(self.sendStatusMsg, output)

    def sendBatteryLevels(self):
        levels = ""
        for b in self.batteryLevels:
            for d in self.devices:
                if b["id"] == d["id"]:
                    levels = levels + d["friendly_name"] + ": " + str(b["battery_level"]) + "%\r\n"
                    break
        if levels == "":
            levels = "No battery level information available at this time"
        self.sendStatusMsg(levels)

    def forgetZwave(self):
        logger.info("%s Z-Wave not present, forgetting about it", ModuleName)
        del(self.elements["zwave"])

    def connectionWatchdog(self):
        """ The final defence. Requests a reboot if no messages received for a long time. """
        logger.debug('%s connectionWatchdog, rxCount: %s', ModuleName, self.rxCount)
        if self.firstConnectionWatchdog: # Needed because NTP may have updated time cause this to be called too soon
            self.firstConnectionWatchdog = False
        elif self.rxCount == 0:
            logger.debug('%s connectionWatchdog, rxCount: %s, sending reboot message to supervisor', ModuleName, self.rxCount)
            self.cbSendSuperMsg({"msg": "reboot"})
        else:
            self.rxCount = 0
        reactor.callLater(CONNECTION_WATCHDOG_INTERVAL, self.connectionWatchdog)

    def sendWatchdogMsg(self):
        uptime = subprocess.check_output(["uptime"])[:-1]
        msg = {"cmd": "msg",
               "msg": {"source": self.bridge_id + "/AID0",
                       "destination": WATCHDOG_CID,
                       "body": {
                                 "status": "OK",
                                 "version": self.version,
                                 "connection": self.connection,
                                 "up_since": self.upSince,
                                 "uptime": uptime
                               }
                      }
              }
        logger.debug('%s Sending watchdog message: %s', ModuleName, json.dumps(msg, indent=4))
        self.cbSendConcMsg(msg)
        reactor.callLater(WATCHDOG_SEND_INTERVAL, self.sendWatchdogMsg)
 
    def onSuperMessage(self, msg):
        #logger.debug("%s Received from supervisor: %s", ModuleName, json.dumps(msg, indent=4))
        """  watchdog. Replies with status=ok or a restart/reboot command. """
        if msg["msg"] == "stopall":
            resp = {"msg": "status",
                    "status": "stopping"
                   }
            self.cbSendSuperMsg(resp)
            self.stopApps()
            reactor.callLater(APP_STOP_DELAY, self.killAppProcs)
            reactor.callLater(APP_STOP_DELAY + MIN_DELAY, self.stopAll)
        elif msg["msg"] == "disconnect":
            self.disconnectConduit()
        elif msg["msg"] == "reconnect":
            self.reconnect()
        else:
            if "connection" in msg:
                self.connection = msg["connection"]
            if time.time() - self.timeLastConduitMsg > CONDUIT_WATCHDOG_MAXTIME and not CB_NO_CLOUD: 
                logger.info('%s Not heard from conduit for %s. Notifyinng supervisor', ModuleName, CONDUIT_WATCHDOG_MAXTIME)
                resp = {"msg": "status",
                        "status": "disconnected"
                       }
            elif self.disconnectedCount > CONDUIT_MAX_DISCONNECT_COUNT and not CB_NO_CLOUD:
                logger.info('%s Disconnected from bridge controller. Notifying supervisor', ModuleName)
                resp = {"msg": "status",
                        "status": "disconnected"
                       }
            else:
                resp = {"msg": "status",
                        "status": "ok"
                       }
            self.cbSendSuperMsg(resp)

    def processConduitStatus(self, msg):
        self.timeLastConduitMsg = time.time()
        if not "body" in msg:
            logger.warning('%s Unrecognised command received from controller', ModuleName)
            return
        else:
            if msg["body"]["connected"] == True:
                if self.controllerConnected == False:
                    self.notifyApps(True)
                self.controllerConnected = True
                self.disconnectedCount = 0
            else:
                logger.debug("%s Disconnected message from conduit", ModuleName)
                if self.controllerConnected == True:
                    self.notifyApps(False)
                self.controllerConnected = False
                self.disconnectedCount += 1
                if self.disconnectedCount > CONDUIT_MAX_DISCONNECT_COUNT and not CB_NO_CLOUD:
                    logger.info('%s Disconnected from bridge controller. Notifying supervisor', ModuleName)
                    resp = {"msg": "status",
                            "status": "disconnected"
                           }
                    self.cbSendSuperMsg(resp)
            #logger.warning('%s processConduitStatus, disconnectedCount: %d', ModuleName, self.disconnectedCount)
 
    def onResourceMsg(self, msg):
        try:
            if msg["body"]["resource"] == "/api/bridge/v1/current_bridge/bridge":
                # Call in thread to prevent problems with blocking
                reactor.callInThread(self.updateConfig, msg)
            elif msg["body"]["resource"] == "/api/bridge/v1/device_install":
                reactor.callInThread(self.onDeviceInstall, msg)
            elif msg["body"]["resource"] == "/api/bridge/v1/discovered_device":
                logger.info('%s Received discovered_device message from controller', ModuleName)
            elif msg["body"]["resource"] == "/api/bridge/v1/app_install":
                reactor.callInThread(self.onAppInstall, msg)
            else:
                logger.info('%s Unrecognised resource in message received from controller: %s', ModuleName, msg["body"]["resource"])
                #self.sendStatusMsg("Unrecognised resource in message received from controller")
        except Exception as ex:
            logger.warning('%s onResourceMsg. Problem processing message', ModuleName)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def onControlMessage(self, msg):
        if not "body" in msg: 
            logger.error('%s msg received from controller with no "body" key', ModuleName)
            self.sendStatusMsg("Error. message received from controller with no body key")
            return 
        if self.bridge_id == "unconfigured":
            if "destination" in msg:
                logger.info('%s No BID from bridge.config - used %s from incoming message', ModuleName, msg["destination"])
                self.bridge_id = msg["destination"]
        if "connected" in msg["body"]:
            self.processConduitStatus(msg)
            return
        logger.debug("%s Received from controller: %s", ModuleName, json.dumps(msg, indent=4))
        # Temporary fix because controller sometimes sends resource_uri
        if "resource_uri" in msg["body"]:
            msg["body"]["resource"] = msg["body"].pop("resource_uri")
            #logger.debug('%s resource_uri in message body, replacing: %s', ModuleName, json.dumps(msg, indent=4))
        self.rxCount += 1
        logger.debug('%s onControlMessage, rxCount: %s', ModuleName, self.rxCount)
        if "command" in msg["body"]:
            command = msg["body"]["command"]
            if command == "none":
                pass
            elif command == "start":
                if self.configured:
                    if self.state == "stopped":
                        logger.info('%s Starting adaptors and apps', ModuleName)
                        self.startAll()
                    else:
                        self.sendStatusMsg("Already starting or running. Start command ignored.")
                else:
                    logger.warning('%s Cannot start adaptors and apps. Please run discovery', ModuleName)
                    self.sendStatusMsg("Start command received with no apps and adaptors")
            elif command == "discover":
                if self.state != "stopped":
                    self.stopApps()
                    reactor.callLater(APP_STOP_DELAY, self.killAppProcs)
                    reactor.callLater(APP_STOP_DELAY + MIN_DELAY, self.discover)
                else:
                    reactor.callLater(MIN_DELAY, self.discover)
            elif command == "restart":
                logger.info('%s Received restart command', ModuleName)
                self.getConfig()  # Get latest config before restarting
                self.cbSendSuperMsg({"msg": "restart"})
                self.restarting = True
                self.setState("restarting")
                #self.sendStatusMsg("restarting")
            elif command == "reboot":
                logger.info('%s Received reboot command', ModuleName)
                self.cbSendSuperMsg({"msg": "reboot"})
                self.sendStatusMsg("Preparing to reboot")
            elif command == "stop":
                if self.state != "stopping" and self.state != "stopped":
                    self.stopApps()
                    reactor.callLater(APP_STOP_DELAY, self.killAppProcs)
                else:
                    self.sendStatusMsg("Already stopped or stopping. Stop command ignored.")
            elif command.startswith("upgrade"):
                if self.state != "stopped":
                    self.stopApps()
                reactor.callLater(APP_STOP_DELAY, self.killAppProcs)
                reactor.callLater(APP_STOP_DELAY + MIN_DELAY, self.waitToUpgrade, command)
            elif command == "sendlog" or command == "send_log":
                self.sendLog('/var/log/cbridge.log', 'cbridge.log')
            elif command == "battery":
                self.sendBatteryLevels()
            elif command.startswith("call"):
                # Need to call in thread is case it hangs
                reactor.callInThread(self.doCall, command[5:])
            elif command.startswith("upload"):
                # Need to call in thread is case it hangs
                path = command[7:]
                fileName = path.split('/')[-1]
                reactor.callInThread(self.sendLog, path, fileName)
            elif command == "update_config" or command == "update":
                self.getConfig()
            elif command == "z-exclude" or command == "z_exclude":
                self.zwaveShouldExcludeID = None
                self.zExcluding = False
                self.zwaveExclude()
            elif command.startswith("action"):
                try:
                    action = command.split()
                    found = False
                    if action[1] == "zwave":
                        self.elFactory["zwave"].sendMsg({"cmd": "action", "action": action[2]})
                        logger.debug('%s action, sent %s to zwave', ModuleName, action[2])
                        self.sendStatusMsg("Sent " + action[2] + " to " + action[1])
                    else:
                        for i in self.idToName:
                            if self.idToName[i] == action[1]:
                                found = True
                                element = i
                                break
                        if found:
                            self.cbSendMsg({"cmd": "action",
                                            "action": action[2]}, 
                                            element)
                            logger.debug('%s action, sent %s to %s', ModuleName, action[2], action[1])
                            self.sendStatusMsg("Sent " + action[2] + " to " + action[1])
                        else:
                            self.sendStatusMsg("Action requested for unrecognised app or device")
                except Exception as ex:
                    logger.warning('%s Badly formed action command %s', ModuleName, str(action))
                    logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
                    self.sendStatusMsg("Usage: action device_name action_name")
            elif command == "z-exclude" or command == "z_exclude":
                self.sendStatusMsg("Hello. This is bridge " + self.bridge_id)
            elif command == "":
                self.sendStatusMsg("Hello. Bridge " + self.bridge_id + ", software version: " + self.version)
            else:
                logger.warning('%s Unrecognised command message received from controller: %s', ModuleName, msg)
                self.sendStatusMsg("Unrecognised command message received from controller")
        elif "resource" in msg["body"]:
            self.onResourceMsg(msg)
        else:
            logger.info('%s No command or resource field in body of server message', ModuleName)
            self.sendStatusMsg("Unrecognised message received from controller")
 
    def stopApps(self):
        """ Asks apps & adaptors to clean up nicely and die. """
        if self.state != "stopped" and self.state != "stopping":
            if self.state != "restarting":
                self.setState("stopping")
            logger.info('%s Stopping apps and adaptors', ModuleName)
            mgrSocs = self.listMgrSocs()
            for a in mgrSocs:
                try:
                    self.cbSendMsg({"cmd": "stop"}, a)
                    logger.info('%s Stopping %s', ModuleName, a)
                except Exception as ex:
                    logger.warning('%s Could not send stop message to %s. Exception: %s, %s', ModuleName, a, type(ex), str(ex.args))

    def killAppProcs(self):
        # If not configured there will be no app processes & no mgrSocs
        if self.configured:
            # Stop listing on sockets
            mgrSocs = self.listMgrSocs()
            for a in mgrSocs:
                try:
                    logger.debug('%s Stop listening on %s', ModuleName, a)
                    self.appListen[a].stopListening()
                except Exception as ex:
                    logger.debug('%s Unable to stop listening on: %s', ModuleName, a)
                    logger.debug("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            # In case apps & adaptors have not shut down, kill their processes.
            for p in self.appProcs:
                try:
                    self.appProcs[p].kill()
                except:
                    logger.debug('%s No process to kill', ModuleName)
            self.appProcs = {}
            #self.removeSecondarySockets()
            # In case some adaptors have not killed gatttool processes:
            try:
                subprocess.call(["killall", "gatttool"])
            except:
                pass
            if self.state != "restarting":
                self.setState("stopped")

    def stopAll(self):
        #self.sendStatusMsg("Disconnecting. Goodbye, back soon ...")
        logger.info('%s Stopping concentrator', ModuleName)
        if self.zwave:
            self.elFactory["zwave"].sendMsg({"cmd": "stop"})
        self.cbSendConcMsg({"cmd": "stop"})
        # Give concentrator a change to stop before killing it and its sockets
        reactor.callLater(MIN_DELAY*2, self.stopManager)

    def stopManager(self):
        logger.debug('%s stopManager', ModuleName)
        for el in self.elListen:
            self.elListen[el].stopListening()
        for el in self.elProc:
            try:
                el.kill()
            except:
                logger.debug('%s No element process to kill', ModuleName)
        logger.debug('%s stopManager, killed app processes', ModuleName)
        try:
            self.nodejsProc.kill()
        except:
            logger.debug('%s No node  process to kill', ModuleName)
        logger.debug('%s stopManager, stopped node', ModuleName)
        #for soc in self.concConfig:
            #socket = soc["appConcSoc"]
            #try:
            #    os.remove(socket) 
            #    logger.debug('%s Socket %s renoved', ModuleName, socket)
            #except:
            #    logger.debug('%s Socket %s already renoved', ModuleName, socket)
        # Turn off LED
        if self.useLED:
            GPIO.output(26,GPIO.LOW)
        logger.info('%s Stopping reactor', ModuleName)
        reactor.stop()
        # touch a file so that supervisor can see we have finished
        if not os.path.exists(CB_MANAGER_EXIT):
            open(CB_MANAGER_EXIT, 'w').close()
        sys.exit

    def sendStatusMsg(self, status):
        now = str(time.strftime('%H:%M:%S', time.localtime(time.time())))
        msg = {"cmd": "msg",
               "msg": {"source": self.bridge_id,
                       "destination": "broadcast",
                       "time_sent": isotime(),
                       "body": {
                                 "status": now + ' ' + status
                               }
                      }
              }
        logger.debug('%s Sending status message: %s', ModuleName, msg)
        self.cbSendConcMsg(msg)
 
    def cbSendMsg(self, msg, iName):
        self.cbFactory[iName].sendMsg(msg)

    def cbSendConcMsg(self, msg):
        try:
            self.elFactory["conc"].sendMsg(msg)
        except Exception as ex:
            logger.warning('%s Appear to be trying to send a message to concentrator before connected: %s', ModuleName, msg)
            logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def cbSendSuperMsg(self, msg):
        self.cbSupervisorFactory.sendMsg(msg)

    def sendControllerMsg(self, verb, resource, body=None):
        try:
            req = {"cmd": "msg",
                   "msg": {"source": self.bridge_id,
                           "destination": "cb",
                           "time_sent": isotime(),
                           "body": {
                                    "resource": resource,
                                    "verb": verb
                                   }
                          }
                  }
            if body != None:
                req["msg"]["body"]["body"] = body
            logger.debug('%s sendControllerMsg, sending: %s', ModuleName, str(json.dumps(req, indent=4)))
            self.cbSendConcMsg(req)
        except Exception as ex:
            logger.warning('%s sendControllerMsg exception: %s %s', ModuleName, type(ex), str(ex.args))

    def elementWatchdog(self):
        """ Checks that all apps and adaptors have communicated within the designated interval. """
        #logger.debug('%s elementWatchdog, elements: %s', ModuleName, str(self.elements))
        if self.state == "running":
            for e in self.elements:
                if self.elements[e] == False:
                    if e != "conc":
                        logger.warning('%s %s has not communicated within watchdog interval', ModuleName, e)
                        self.sendStatusMsg("Watchdog timeout for " + e)
                        break
                else:
                    self.elements[e] = False
            if self.firstWatchdog:
                l = task.LoopingCall(self.pollElement)
                l.start(ELEMENT_POLL_INTERVAL)
                self.firstWatchdog = False
        try:
            if os.path.isfile(ZWAYLOGFILE):
                if os.path.getsize(ZWAYLOGFILE) > MAX_ZWAY_LOG_SIZE:
                    subprocess.call(["truncate", ZWAYLOGFILE, "--size", "0"])
                    logger.info("{} elementWatchDog, truncated {}".format(ModuleName, ZWAYLOGFILE))
        except Exception as ex:
            logger.warning("{} elementWatchDog, could not truncate z-way logfile, exception: {}, {}".format(ModuleName, ex, ex.args))
        reactor.callLater(ELEMENT_WATCHDOG_INTERVAL, self.elementWatchdog)

    def pollElement(self):
        for e in self.elements:
            if self.elements[e] == False:
                #logger.debug('%s pollElement, elements: %s', ModuleName, e)
                try:
                    if e == "conc":
                        self.cbSendConcMsg({"cmd": "status"})
                    elif e == "zwave":
                        self.elFactory["zwave"].sendMsg({"cmd": "status"})
                    else:
                        self.cbSendMsg({"cmd": "status"}, e)
                except Exception as ex:
                    logger.warning("%s pollElement. Could not send message to: %s", ModuleName, e)
                    logger.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def onUserMessage(self, msg):
        if "body" in msg:
            userMsg = msg["body"]
        else:
            userMsg = "No log message provided" 
            logger.warning('%s %s', ModuleName, userMsg)
        self.sendStatusMsg(userMsg)

    def onLogMessage(self, msg):
        if "level" in msg:
            level = msg["level"]
        else:
            level = "unknown"
        if "body" in msg:
            logMsg = msg["body"]
        else:
            logMsg = "No log message provided" 
        if msg["id"] == "conc" or msg["id"] == "zwave":
            name = msg["id"]
        else:
            name = self.idToName[msg["id"]]
        if level == "error":
            logger.error("%s %s", name, logMsg)
        elif level == "warning":
            logger.warning("%s %s", name, logMsg)
        elif level == "info":
            logger.info("%s %s", name, logMsg)
        elif level == "debug":
            logger.debug("%s %s", name, logMsg)
        else:
            logger.debug("Unknown logger level: %s %s", name, logMsg)

    def notifyApps(self, connected):
        for a in self.appConfigured:
            msg = {
                   "cmd": "status",
                   "status": connected
                  }
            self.cbSendMsg(msg, a)

    def configureApp(self, app):
        #logger.debug('%s configureApp: %s', ModuleName, str(app))
        try:
            id = self.apps[app]["app"]["id"]
            for c in self.concConfig:
                if c["id"] == id:
                    conc = c["appConcSoc"]
                    message = {"cmd": "config",
                               "sim": CB_SIM_LEVEL,
                               "config": {"adaptors": self.apps[app]["device_permissions"],
                                          "bridge_id": self.bridge_id,
                                          "connected": self.controllerConnected,
                                          "concentrator": conc}}
                    self.cbSendMsg(message, id)
                    self.appConfigured.append(id)
                    break
        except Exception as ex:
            logger.warning("%s ConfigureApp. Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def configureAdaptor(self, adt):
        #logger.debug('%s configureAdaptor: %s', ModuleName, str(adt))
        try:
            d = self.devices[adt]
            id = d["id"]
            message = {
                       "cmd": "config",
                       "config": 
                           {"apps": d["adaptor"]["apps"], 
                            "name": d["adaptor"]["name"],
                            "friendly_name": d["friendly_name"],
                            "btAddr": d["address"],
                            "address": d["address"],
                            "btAdpt": "hci0", 
                            "sim": CB_SIM_LEVEL
                           }
                       }
            if d["device"]["protocol"] == "zwave":
                message["config"]["zwave_socket"] = d["adaptor"]["zwave_socket"]
            #logger.debug('%s Response: %s %s', ModuleName, id, message)
            self.cbSendMsg(message, id)
        except Exception as ex:
            logger.warning("%s ConfigureAdaptor. Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def configureConc(self):
        logger.debug('%s configureConc', ModuleName)
        try:
            if self.configured:
                for a in self.apps:
                    self.concConfig.append({"id": a["app"]["id"], "appConcSoc": a["app"]["concSoc"]})
                message = {"cmd": "config",
                                  "config": {"bridge_id": self.bridge_id,
                                             "apps": self.concConfig}
                          }
            else:
                self.concNoApps = True
                message = {"cmd": "config",
                           "config": {"bridge_id": self.bridge_id}
                          }
            logger.debug('%s Sending config to conc:  %s', ModuleName, message)
            self.cbSendConcMsg(message)
        except Exception as ex:
            logger.warning("%s ConfigureConc. Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def configureZwave(self):
        logger.debug('%s configureZwave', ModuleName)
        try:
            zwaveConfig = []
            message = {"cmd": "config",
                       "config": "no_zwave"
                      }
            if self.configured:
                for d in self.devices:
                    if d["device"]["protocol"] == "zwave":
                        zwaveConfig.append({"id": d["id"], 
                                            "socket": d["adaptor"]["zwave_socket"],
                                            "address": d["address"]
                                          })
                        message["config"] = zwaveConfig 
            else:
                self.noZwave = True
            self.elFactory["zwave"].sendMsg(message)
        except Exception as ex:
            logger.warning("%s ConfigureZwave. Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def onClientMessage(self, msg):
        #logger.debug('%s Received msg; %s', ModuleName, msg)
        if not "status" in msg:
            logger.warning('%s No status key in message from client; %s', ModuleName, msg)
            return
        if msg["status"] == "control_msg":
            del msg["status"]
            self.onControlMessage(msg)
            return
        elif not "id" in msg:
            logger.warning('%s No id key in message from client; %s', ModuleName, msg)
            return
        else:
            self.elements[msg["id"]] = True
        if msg["status"] == "req-config":
            if not "type" in msg:
                logger.warning('%s No type key in message from client; %s', ModuleName, msg)
                return
            logger.info('%s %s running', ModuleName, msg["id"])
            if msg["type"] == "app":
                for a in self.apps:
                    if a["app"]["id"] == msg["id"]:
                        self.configureApp(self.apps.index(a))
                        break
            elif msg["type"] == "adt": 
                for d in self.devices:
                    if d["id"] == msg["id"]:
                        self.configureAdaptor(self.devices.index(d))
                        break
            elif msg["type"] == "conc":
                self.configureConc()
                # Only start apps & adaptors after concentrator has responded
                if self.configured:
                    self.startAll()
            elif msg["type"] == "zwave":
                self.configureZwave()
            else:
                logger.warning('%s Config req from unknown instance type: %s', ModuleName, msg['id'])
                response = {"cmd": "error"}
                self.cbSendMsg(response, msg["id"])
        elif msg["status"] == "log":
            self.onLogMessage(msg)
        elif msg["status"] == "user_message":
            self.onUserMessage(msg)
        elif msg["status"] == "discovered":
            if msg["id"] == "zwave":
                self.onZwaveDiscovered(msg)
            else:
                logger.warning('%s Discovered message from unexpected source: %s', ModuleName, msg["id"])
        elif msg["status"] == "discovering":
            if msg["id"] == "zwave":
                self.onZwaveDiscovering(msg)
            else:
                logger.warning('%s Discovering message from unexpected source: %s', ModuleName, msg["id"])
        elif msg["status"] == "excluded":
            if msg["id"] == "zwave":
                self.onZwaveExcluded(msg["body"])
            else:
                logger.warning('%s Excluded message from unexpected source: %s', ModuleName, msg["id"])
        elif msg["status"] == "state":
            if "state" in msg:
                logger.debug('%s %s %s', ModuleName, msg["id"], msg["state"])
            else:
                logger.warning('%s Received state message from %s with no state', ModuleName, msg["id"])
        elif msg["status"] == "battery_level":
            if "battery_level" in msg:
                for d in self.batteryLevels:
                    if d["id"] == msg["id"]:
                        d["battery_level"] = msg["battery_level"]
                        break
                else:
                    self.batteryLevels.append({"id": msg["id"], "battery_level": msg["battery_level"]})
            else:
                logger.warning('%s Received battery_level message from %s with no battery_level', ModuleName, msg["id"])
        elif msg["status"] == "error":
                logger.warning('%s Error status received from %s.', ModuleName, msg["id"])
                self.sendStatusMsg("Error status received from " + msg["id"])
        elif msg["status"] == "no_zwave":
            self.elFactory["zwave"].sendMsg({"cmd": "stop"})
            reactor.callLater(MIN_DELAY, self.forgetZwave)
            self.zwave = False
        elif msg["status"] != "ok":
            logger.debug('%s Message from client: %s', ModuleName, msg)
 
if __name__ == '__main__':
    m = ManageBridge()
