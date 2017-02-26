#!/usr/bin/env python
# zwavectrl_a.py
# Copyright (C) ContinuumBridge Limited, 2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
ModuleName = "z-wave_ctrl"

import sys
import time
import os
import json
import requests
import procname
from pprint import pprint
sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../lib')))
from cbconfig import *
from twisted.internet import task
from twisted.internet import threads
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.task import deferLater
from cbcommslib import CbClientProtocol
from cbcommslib import CbClientFactory
from cbcommslib import CbServerProtocol
from cbcommslib import CbServerFactory

ZWAVE_DEVICES_FILE   = "zwave_devices.json"
DISCOVER_TIME        = 40.0
INCLUDE_WAIT_TIME    = 5.0
MIN_DELAY            = 0.5
IPADDRESS            = "localhost"
PORT                 = "8083"
baseUrl              = "http://" + IPADDRESS + ":" + PORT +"/"
dataUrl              = baseUrl + 'ZWaveAPI/Data/'
startIncludeUrl      = baseUrl + "ZWaveAPI/Run/controller.AddNodeToNetwork(1)"
stopIncludeUrl       = baseUrl + "ZWaveAPI/Run/controller.AddNodeToNetwork(0)"
startExcludeUrl      = baseUrl + "ZWaveAPI/Run/controller.RemoveNodeFromNetwork(1)"
stopExcludeUrl       = baseUrl + "ZWaveAPI/Run/controller.RemoveNodeFromNetwork(0)"
postUrl              = baseUrl + "ZWaveAPI/Run/devices["
getURL               = baseUrl + "Run/devices[DDD].instances[III].commandClasses[CCC].Get()"
resetUrl             = baseUrl + "ZWaveAPI/Run/SerialAPISoftReset()"
authUrl              = baseUrl + "ZAutomation/api/v1/login"
 
class ZwaveCtrl():
    def __init__(self, argv):
        procname.setprocname('cbzwavectrl')
        self.status = "ok"
        self.state = "stopped"
        self.include = False
        self.exclude = False
        self.getting = False
        self.resetBoard = False
        self.getStrs = []
        self.cbFactory = {}
        self.adaptors = [] 
        self.found = []
        self.listen = []
        self.postToUrls = []
        if len(argv) < 3:
            print("error, Improper number of arguments")
            exit(1)
        managerSocket = argv[1]
        self.id = argv[2]
        self.fromTime = str(int(time.time()) - 1)

        # Connection to manager
        initMsg = {"id": self.id,
                   "type": "zwave",
                   "status": "req-config"} 
        self.managerFactory = CbClientFactory(self.onManagerMessage, initMsg)
        self.managerConnect = reactor.connectUNIX(managerSocket, self.managerFactory, timeout=10)
        reactor.run()
 
    def sendMessage(self, msg, iName):
        self.cbFactory[iName].sendMsg(msg)

    def cbSendManagerMsg(self, msg):
        self.managerFactory.sendMsg(msg)

    def cbLog(self, level, log):
        msg = {"id": self.id,
               "status": "log",
               "level": level,
               "body": log}
        self.cbSendManagerMsg(msg)

    def logThread(self, level, log):
        reactor.callFromThread(self.cbLog, level, log)

    def readDevices(self):
        self.cbLog("info", "Hello")
        self.zwave_devices = []    # In case file doesn't load
        try:
            with open(ZWAVE_DEVICES_FILE, 'r') as configFile:
                self.zwave_devices = json.load(configFile)
                self.cbLog("info", 'Read zwave devices file')
        except:
            self.cbLog("error", 'No zwave devices file exists or file is corrupt')

    def setState(self, action):
        self.state = action
        self.cbLog("debug", "state: " + self.state)
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.cbSendManagerMsg(msg)

    def sendParameter(self, data, timeStamp, a, commandClass, instance, value):
        msg = {"id": "zwave",
               "content": "data",
               "commandClass": commandClass,
               "instance": instance,
               "value": value,
               "data": data,
               "timeStamp": timeStamp}
        reactor.callFromThread(self.sendMessage, msg, a)

    def checkAllProcessed(self, appID):
        self.processedApps.append(appID)
        found = True
        for a in self.appInstances:
            if a not in self.processedApps:
                found = False
        if found:
            self.setState("inUse")

    def zway(self):
        """ Include works as follow:
            Send the include URL. includeState = "waitInclude".
            Wait for the wait time. includeState = "waitInclude".
            Check if there's a new device there.
            If not wait again and repeat until time-out. includeState = "waitInclude".
            If there is check that vendor string is not null. includeState = "checkData"
            If it is wait and check again until time-out. includeState = "checkData"
            If vendor string is there, send information back to manager. includeState = "notIncluding"
            includeTick keeps tract of time in increments of INCLUDE_WAIT_TIME.
            Don't change the "from" time when getting data until all data has been retrieved.
        """
        # Try to authenticate
        url = "http://localhost:8083/ZAutomation/api/v1/login"
        self.logThread("debug", "Authenticating")
        payload = {"form": True, "login": "admin", "password": CB_ZWAVE_PASSWORD, "keepme": False, "default_ui": 1}
        headers = {'Content-Type': 'application/json'}
        r = requests.post(authUrl, headers=headers, data=json.dumps(payload))
        self.logThread("debug", "Authentication response: " + str(r.text))
        self.logThread("debug", "Authentication cookies: " + str(r.cookies))
        if r.status_code == 200:
            self.logThread("debug", "Authenticated")
            self.authenticated = True
            self.cookies = {"ZWAYSession": r.cookies["ZWAYSession"]}
        else:
            self.authenticated = False
            self.logThread("debug", "Not authenticated")
        includeState = "notIncluding"
        excludeState = "notExcluding"
        found = []
        posting = False
        error_count = 0
        count404 = 0
        while self.state != "stopping" and error_count < 4:
            if self.include:
                if includeState == "notIncluding":
                    foundDevice = False
                    foundData = False
                    losEndos = False
                    waitForVendorString = 0
                    nodeInfoFrameFound = False
                    includeState = "waitInclude"
                    incStartTime = str(int(time.time()))
                    includedDevice = ""
                    self.endMessage = "Unexpected behavour. Most likely Z-Wave device did not finish interview"
                    URL = startIncludeUrl
                    body = []
                    includeTick = 0
                    self.logThread("debug", "started including")
                elif includeState == "waitInclude":
                    #self.logThread("debug", "waitInclude, includeTick: " + str(includeTick) + ", foundData: " + str(foundData))
                    URL = dataUrl + incStartTime
                    if foundData:
                        includeState = "tidyUp"
                    elif foundDevice:
                        includeTick = 0
                        includeState = "checkData"
                        msg = {"id": self.id,
                               "status": "discovering"
                              }
                        reactor.callFromThread(self.cbSendManagerMsg, msg)
                    elif includeTick > 3:
                        self.endMessage = "No Z-Wave device found."
                        includeState = "tidyUp"
                    else:
                        includeTick += 1
                        time.sleep(INCLUDE_WAIT_TIME)
                elif includeState == "checkData":
                    self.logThread("debug", "checkData, includeTick: " + str(includeTick) + ", foundData" + str(foundData))
                    URL = dataUrl + incStartTime
                    if foundData:
                        includeState = "tidyUp"
                    elif includeTick > 4:
                        # Assume we're never going to get a vendorString and use zwave name
                        losEndos = True
                        includeState = "losEndos"
                    else:
                        includeTick += 1
                        time.sleep(INCLUDE_WAIT_TIME)
                elif includeState == "losEndos":
                    time.sleep(MIN_DELAY)
                    self.logThread("debug", "losEndos, foundData: " + str(foundData))
                    losEndos = False
                    includeState = "tidyUp"
                elif includeState == "tidyUp":
                    self.logThread("debug", "tidyUp, includeTick: " + str(includeTick) + ", foundData: " + str(foundData))
                    self.include = False
                    URL = stopIncludeUrl
                    includeState = "notIncluding"
                    reactor.callFromThread(self.stopDiscover)
                    time.sleep(INCLUDE_WAIT_TIME)
                else:
                    URL = stopIncludeUrl
                    includeState = "notIncluding"
            elif self.exclude:
                if excludeState == "notExcluding":
                    foundDevice = False
                    excludeState = "waitExclude"
                    incStartTime = str(int(time.time()))
                    excludedDevice = ""
                    URL = startExcludeUrl
                    excludeTick = 0
                    self.logThread("debug", "started excluding")
                elif excludeState == "waitExclude":
                    self.logThread("debug", "waitExclude, excludeTick: " + str(excludeTick))
                    URL = dataUrl + incStartTime
                    if foundDevice or excludeTick > 4:
                        excludeState = "notExcluding"
                        self.exclude = False
                        msg = {"id": self.id,
                               "status": "excluded",
                               "body": excludedDevice
                              }
                        reactor.callFromThread(self.cbSendManagerMsg, msg)
                        URL = stopExcludeUrl
                    else:
                        excludeTick += 1
                        time.sleep(INCLUDE_WAIT_TIME)
            elif self.resetBoard:
                URL = resetUrl
                #reactor.callFromThread(self.setState, "stopping")
                self.resetBoard = False
                self.logThread("debug", "Resetting RazBerry board")
            elif self.postToUrls:
                posting = True
                URL = self.postToUrls.pop() 
            elif self.getting:
                self.getting = False
            else:
                URL = dataUrl + self.fromTime
            #self.logThread("debug", "authenticated: " + str(self.authenticated) + ", URL: " + URL)
            try:
                if self.authenticated:
                    r = requests.get(URL, headers={'Content-Type': 'application/json'}, cookies=self.cookies)
                else:
                    r = requests.get(URL, headers={'Content-Type': 'application/json'})
            except Exception as ex:
                error_count += 1
                self.logThread("error", "error in accessing z-way. URL: " + URL + ", error_count: " + str(error_count))
                self.logThread("error", "Exception: " + str(type(ex)) + " " +  str(ex.args))
            else:
                error_count = 0
                if r.status_code == 404:
                    count404 += 1
                elif r.status_code != 200:
                    self.logThread("debug", "non-200 response: " + str(r.status_code))
                else:
                    count404 = 0
                    try:
                        dat = r.json()
                        #self.logThread("debug", "dat: {}".format(json.dumps(dat, indent=4)))
                    except:
                        try:
                            self.logThread("warning", "Could not load JSON in response, text: " + str(r.text) + ", URL: " + URL)
                            self.fromTime = str(int(time.time() - 1))
                        except Exception as ex:
                            self.logThread("error", "error in accessing z-way")
                            self.logThread("error", "Exception: " + str(type(ex)) + " " +  str(ex.args))
                            self.fromTime = str(int(time.time() - 1))
                    else:
                        if dat:
                            if "updateTime" in dat:
                                self.fromTime = str(dat["updateTime"])
                            if self.exclude:
                                if "controller.data.lastExcludedDevice" in dat:
                                    excludedDevice = str(dat["controller.data.lastExcludedDevice"]["value"])
                                    if excludedDevice != "None" and excludedDevice != 0:
                                        self.logThread("debug", "found excludedDevice; " + str( excludedDevice))
                                        foundDevice = True
                            if self.include:
                                if "controller.data.lastIncludedDevice" in dat:
                                    includedDevice = str(dat["controller.data.lastIncludedDevice"]["value"])
                                    if includedDevice != "None":
                                        foundDevice = True
                                    self.logThread("debug", "includedDevice " + includedDevice)
                                if "devices" in dat:
                                    self.logThread("debug", "devices in dat")
                                    for d in dat["devices"].keys():
                                        self.logThread("debug", "device: " + d)
                                        if d == includedDevice:
                                            for k in dat["devices"][d].keys():
                                                for j in dat["devices"][d][k].keys():
                                                    if j == "nodeInfoFrame":
                                                        command_classes = dat["devices"][d][k][j]["value"]
                                                        nodeInfoFrameFound = True
                                                        self.logThread("debug", "command_classes: " + str(command_classes))
                                                    elif j == "vendorString":
                                                        vendorString = dat["devices"][d][k][j]["value"]
                                                        self.logThread("debug", "vendorString: " + vendorString) 
                                                    elif j == "deviceTypeString":
                                                        deviceTypeString = dat["devices"][d][k][j]["value"]
                                                        self.logThread("debug", "zwave name: " + deviceTypeString)
                                                    elif j == "manufacturerProductId":
                                                        manufacturerProductId = dat["devices"][d][k][j]["value"]
                                                        self.logThread("debug", "manufacturerProductId: " + str(manufacturerProductId))
                                                    elif j == "manufacturerProductType":
                                                        manufacturerProductType = dat["devices"][d][k][j]["value"]
                                                        self.logThread("debug", "manufacturerProductType : " + str(manufacturerProductType))
                                            if nodeInfoFrameFound and not foundData:
                                                if vendorString == "":
                                                    if waitForVendorString == 3:
                                                        self.logThread("debug", "found device with no vendorString")
                                                        for dev in self.zwave_devices:
                                                            self.logThread("debug", "found device: " + str(command_classes))
                                                            self.logThread("debug", "comparing found device to: " + str(dev))
                                                            if str(command_classes) != None:
                                                                if len(dev["command_classes"]) != len(command_classes):
                                                                    self.logThread("debug", "lengths do not match")
                                                                    found = False
                                                                else:
                                                                    self.logThread("debug", "lengths match")
                                                                    found = True
                                                                    for c in dev["command_classes"]:
                                                                        self.logThread("debug", "command_class: " + str(c))
                                                                        if c not in command_classes:
                                                                            found = False
                                                                            break
                                                                    if found:
                                                                        name = dev["name"]
                                                                        self.logThread("debug", "matched device. name: " +  name)
                                                                        self.endMessage = "Found Z-Wave device: " + name
                                                                        break
                                                            else:
                                                                self.logThread("debug", "Incomplete Z-Wave interview")
                                                                self.endMessage = "Problem interviewing Z-Wave device. Please Z-exclude & try again"
                                                        if not found:
                                                            self.logThread("debug", "not found")
                                                            name = ""
                                                            self.endMessage = "No known Z-Wave device found"
                                                        foundData = True
                                                    else:
                                                        waitForVendorString += 1
                                                else:
                                                    name = vendorString + " " + str(manufacturerProductId) + " " + str(manufacturerProductType)
                                                    self.logThread("debug", "found device with vendorString: " + name)
                                                    self.endMessage = "Found Z-Wave device: " + name
                                                    foundData = True
                                                if foundData:
                                                    self.logThread("debug", "found name: " + name)
                                                    # Botch because different versions of the device have different vendor strings
                                                    if name == "Aeotec 100 2":
                                                        self.logThread("info", "Changing name from Aeotec 100 2 to Aeon Labs 100 2")
                                                        name = "Aeon Labs 100 2"
                                                    self.found.append({"protocol": "zwave",
                                                                       "name": name,
                                                                       #"mac_addr": "XXXXX" + str(d),
                                                                       "address": str(d),
                                                                       "manufacturer_name": vendorString,
                                                                       "model_number": manufacturerProductId,
                                                                       #"command_classes": command_classes
                                                                      })
                            else: # not including
                                for g in self.getStrs:
                                    if g["match"] in dat:
                                        #self.logThread("debug", "found: " + g["address"] + ", " +  g["commandClass"])
                                        self.sendParameter(dat[g["match"]], time.time(), g["address"], g["commandClass"], g["instance"], g["value"])
            if posting:
                posting = False
            else:
                time.sleep(MIN_DELAY)
            if count404 > 5:
                self.logThread("warning", "count404 > 5. Off down the pub. (Probably z-wave.me installed, but not Razberry board)")
                msg = {
                    "id": self.id,
                    "status": "no_zwave"
                }
                reactor.callFromThread(self.cbSendManagerMsg, msg)
                break

    def sendUserMessage(self):
        msg = {"id": self.id,
                "status": "user_message",
                "body": self.endMessage
               }
        self.cbSendManagerMsg(msg)

    def stopDiscover(self):
        self.include = False
        d = {"status": "discovered",
             "id": "zwave",
             "body": self.found
            }
        self.cbLog("debug", "sendDiscoveredResults: " + str(json.dumps(d, indent=4)))
        self.cbSendManagerMsg(d)
        reactor.callLater(1.0, self.sendUserMessage)
        del self.found[:]

    def discover(self):
        self.cbLog("debug", "starting discovery")
        self.include = True

    def startExclude(self):
        self.cbLog("debug", "starting exclude")
        self.exclude = True

    def onAdaptorMessage(self, msg):
        #self.cbLog("debug", "onAdaptorMessage: {}".format(json.dumps(msg, indent=4)))
        if "request" in msg:
            if msg["request"] == "init":
                resp = {"id": "zwave",
                        "content": "init"}
                self.sendMessage(resp, msg["id"])
            elif not "address" in msg:
                self.cbLog("warning", "Message received with no address: " + str(json.dumps(msg, indent=4)))
            elif msg["request"] == "check":
                postToUrl = postUrl + msg["address"] + "].SendNoOperation()"
                self.postToUrls.insert(0, postToUrl)
            elif msg["request"] == "force_interview":
                postToUrl = postUrl + msg["address"] + "].InterviewForce()"
                self.postToUrls.insert(0, postToUrl)
            elif not "instance" in msg or not "commandClass" in msg:
                self.cbLog("warning", "instance and commandClass expected in msg: " + str(json.dumps(msg, indent=4)))
            elif msg["request"] == "getc":
                g = "devices." + msg["address"] + ".data.isFailed"
                getStr = {"address": msg["id"],
                          "match": g, 
                          "commandClass": msg["commandClass"],
                          "value": "",
                          "instance": msg["instance"]
                         }
                self.cbLog("debug", "New getStr (check): " + str(json.dumps(getStr, indent=4)))
                self.getStrs.append(getStr)
            elif msg["request"] == "get":
                g = "devices." + msg["address"] + ".instances." + msg["instance"] + \
                    ".commandClasses." + msg["commandClass"] + ".data"
                if "value" in msg:
                    g += "." + msg["value"]
                    value = msg["value"]
                else: 
                    value = ""
                if "name" in msg:
                    g += "." + msg["name"]
                getStr = {"address": msg["id"],
                          "match": g, 
                          "commandClass": msg["commandClass"],
                          "value": value,
                          "instance": msg["instance"]
                         }
                self.cbLog("debug", "New getStr: " + str(json.dumps(getStr, indent=4)))
                self.getStrs.append(getStr)
            elif not "action" in msg or not "value" in msg:
                self.cbLog("warning", "action and value expected in post msg: " + str(json.dumps(msg, indent=4)))
            elif msg["request"] == "post":
                postToUrl = postUrl + msg["address"] + "].instances[" + msg["instance"] + \
                            "].commandClasses[" + msg["commandClass"] + "]." + msg["action"] + "(" + \
                            msg["value"] + ")"
                #self.cbLog("debug", "postToUrl: " + str(postToUrl))
                self.postToUrls.insert(0, postToUrl)
        else:
            self.cbLog("debug", "onAdaptorMessage without request: " + str(json.dumps(msg, indent=4)))

    def processConfig(self, config):
        self.cbLog("debug", "processConf: " + str(json.dumps(config, indent=4)))
        if config != "no_zwave":
            for a in config:
                if a["id"] not in self.adaptors:
                    # Allows for reconfig on the fly
                    self.adaptors.append({"adt": a["id"],
                                          "address": a["address"]
                                        })
                    self.cbFactory[a["id"]] = CbServerFactory(self.onAdaptorMessage)
                    self.listen.append(reactor.listenUNIX(a["socket"], self.cbFactory[a["id"]]))
        # Start zway even if there are no zway devices, in case we want to discover some
        reactor.callInThread(self.zway)

    def doStop(self):
        # Stop listening on all ports (to prevent nasty crash on exit)
        for l in self.listen:
            l.stopListening()
        try:
            reactor.stop()
        except:
            self.cbLog("warning", "stopReactor when reactor not running")
        sys.exit

    def onManagerMessage(self, cmd):
        #self.cbLog("debug", "Received from manager: " + str(json.dumps(cmd, indent=4)))
        if cmd["cmd"] == "discover":
            self.discover()
            msg = {"id": self.id,
                   "status": "ok"}
        elif cmd["cmd"] == "exclude":
            self.startExclude()
            msg = {"id": self.id,
                   "status": "ok"}
        elif cmd["cmd"] == "stop":
            msg = {"id": self.id,
                   "status": "stopping"}
            reactor.callLater(2.5, self.doStop)
        elif cmd["cmd"] == "action":
            if "action" in cmd:
                if cmd["action"] == "reset":
                    self.resetBoard = True
            msg = {"id": self.id,
                   "status": "resetting"}
        elif cmd["cmd"] == "config":
            self.processConfig(cmd["config"])
            msg = {"id": self.id,
                   "status": "ready"}
            # read devices here because we know we are connected to manager for logging
            self.readDevices()
        else:
            msg = {"id": self.id,
                   "status": "ok"}
        self.cbSendManagerMsg(msg)

if __name__ == '__main__':
    zwaveCtrl = ZwaveCtrl(sys.argv)
