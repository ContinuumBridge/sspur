#!/usr/bin/env python
# concentrator.py
# Copyright (C) ContinuumBridge Limited, 2013-2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
ModuleName = "Concentrator"

import sys
import time
import os
import json
import procname
from twisted.internet.protocol import Protocol, Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet import threads
from twisted.internet import defer
from twisted.internet import reactor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../lib')))
from cbcommslib import CbClientProtocol
from cbcommslib import CbClientFactory
from cbcommslib import CbServerProtocol
from cbcommslib import CbServerFactory
from cbcommslib import isotime
from cbconfig import *

class Concentrator():
    def __init__(self, argv):
        procname.setprocname('concentrator')
        self.status = "ok"
        self.readyApps = []
        self.cbFactory = {}
        self.appInstances = []
        self.sendQueue = []
        self.conc_mode = os.getenv('CB_CONCENTRATOR', 'client')

        if len(argv) < 3:
            self.cbLog("error", "Improper number of arguments")
            exit(1)
        managerSocket = argv[1]
        self.id = argv[2]
        self.bridge_id = argv[3]

        # Connection to manager
        initMsg = {"id": self.id,
                   "type": "conc",
                   "status": "req-config"} 
        self.managerFactory = CbClientFactory(self.onManager, initMsg)
        self.managerConnect = reactor.connectUNIX(managerSocket, self.managerFactory, timeout=10)
        self.connectConduit()
        reactor.callLater(0.1, self.sendMessage)  # Loop to ensure messages are not send too close together (node problem)
        reactor.run()

    def connectConduit(self, status="starting"):
        initMsg = {
            "source": self.bridge_id,
            "destination": "cb",
            "time_sent": isotime(),
            "body": {
                "verb": "patch",
                "resource": "/api/bridge/v1/bridge/" + self.bridge_id[3:] + "/",
                "body": {
                    "status": status
                }
            }
        }
        self.concFactory = CbClientFactory(self.onControllerMessage, initMsg)
        self.jsConnect = reactor.connectTCP("localhost", 5000, self.concFactory, timeout=30)

    def reconnectConduit(self):
        try:
            self.jsConnect.disconnect()
        except Exception as ex:
            self.cbLog("debug", "reconnectConduit exception: " + str(type(ex)) + " " +  str(ex.args))
        self.connectConduit(status="running")

    def onConfigure(self, config):
        """Config is based on what apps are available."""
        #self.cbLog("info", "onConfigure: " + str(config))
        if "apps" in config:
            for app in config["apps"]:
                iName = app["id"]
                if iName not in self.appInstances:
                    # Allows for reconfig on the fly
                    appConcSoc = app["appConcSoc"]
                    self.appInstances.append(iName)
                    self.cbFactory[iName] = CbServerFactory(self.onAppData)
                    reactor.listenUNIX(appConcSoc, self.cbFactory[iName])
            self.cbLog("info", "onConfigure. appInstances: " + str(self.appInstances))

    def onControllerMessage(self, msg):
        #if "body" in msg:
        #    if not "connected" in msg["body"]:
        #        self.cbLog("debug", "Received from controller: " + str(json.dumps(msg, indent=4)))
        try:
            if not "destination" in msg:
                msg["destination"] = self.bridge_id
        except Exception as inst:
            self.cbLog("warning", "onControllerMessage. Unexpected message: " + str(json.dumps(msg, indent=4)))
            self.cbLog("warning", "Exception: " + str(type(inst)) + " " +  str(inst.args))
            return
        if msg["destination"] == self.bridge_id or msg["destination"] == "broadcast":
            try:
                msg["status"] = "control_msg"
                msg["id"] = self.id
                if "message" in msg:
                    msg["type"] = msg.pop("message")
                self.cbSendManagerMsg(msg)
            except Exception as ex:
                self.cbLog("warning", "onControllerMessage. Unexpected manager message. Exception: " + str(type(ex)) + " " +  str(ex.args))
        else:
            try:
                dest = msg["destination"].split('/')
                if dest[0] == self.bridge_id:
                    if dest[1] == "AID0":
                         msg["status"] = "control_msg"
                         msg["id"] = self.id
                         self.cbSendManagerMsg(msg)
                    if dest[1] in self.appInstances:

                        msg["destination"] = dest[1]
                        if dest[1] in self.readyApps:
                            self.cbLog("debug", "onControllerMessage, sending to: " +  dest[1])
                            self.cbSendMsg(msg, dest[1])
                        else:
                            self.cbLog("info", "Received message before app ready: " + dest[1])
                else:
                    self.cbLog("warning", "onControllerMessage. Received message with desination: " + msg["destination"])
            except Exception as inst:
                self.cbLog("warning", "onControllerMessage. Unexpected app message: " + str(json.dumps(msg, indent=4)))
                self.cbLog("warning", "Exception: " + str(type(inst)) + " " +  str(inst.args))

    def sendMessage(self):
        # Send messages at regular intervals as node doesn't like them too close together
        try:
            if self.sendQueue:
                msg = self.sendQueue.pop()
                self.concFactory.sendMsg(msg)
        except Exception as ex:
            self.cbLog("warning", "Failed to send message to bridge controller: " + str(msg))
            self.cbLog("warning", "Exception: " + str(type(ex)) + " " +  str(ex.args))
        reactor.callLater(0.1, self.sendMessage)

    def queueMessage(self, msg):
        self.sendQueue.append(msg)

    def onManagerMessage(self, msg):
        #self.cbLog("debug", "Received from manager: " + str(json.dumps(msg, indent=4)))
        msg["time_sent"] = isotime()
        self.queueMessage(msg)

    def onManager(self, cmd):
        if cmd["cmd"] == "msg":
            self.onManagerMessage(cmd["msg"])
            msg = {"id": self.id,
                   "status": "ok"}
        elif cmd["cmd"] == "stop":
            msg = {"id": self.id,
                   "status": "stopping"}
            reactor.callLater(0.2, self.doStop)
        elif cmd["cmd"] == "config":
            self.onConfigure(cmd["config"])
            msg = {"id": self.id,
                   "status": "ready"}
        elif cmd["cmd"] == "reconnect":
            self.reconnectConduit()
            msg = {"id": self.id,
                   "status": "ok"}
        else:
            msg = {"id": self.id,
                   "status": "ok"}
        self.cbSendManagerMsg(msg)

    def doStop(self):
        d1 = defer.maybeDeferred(self.jsConnect.disconnect)
        d2 = defer.maybeDeferred(self.managerConnect.disconnect)
        d = defer.gatherResults([d1, d2], consumeErrors=True)
        d.addCallback(self.goodbye)

    def goodbye(self, status):
        reactor.stop()

    def cbSendMsg(self, msg, iName):
        self.cbFactory[iName].sendMsg(msg)

    def cbSendManagerMsg(self, msg):
        self.managerFactory.sendMsg(msg)

    def cbLog(self, level, log):
        msg = {"id": self.id,
               "status": "log",
               "level": level,
               "body": log}
        self.cbSendManagerMsg(msg)

    def appInit(self, appID):
        if appID not in self.readyApps:
            self.readyApps.append(appID)
            self.cbSendMsg({"status": "ready"}, appID)

    def onAppData(self, msg):
        """
        Processes requests from apps.
        Called separately for every app that can make msguests.
        """
        try:
            if "msg" in msg:
                if msg["msg"] == "init":
                    if "appID" in msg:
                        self.appInit(msg["appID"])
                    else:
                        self.cbLog("warning", "Message from app with no ID: " + str(json.dumps(msg, indent=4)))
            elif not "destination" in msg:
                self.cbLog("warning", "Message from app with no destination: " + str(json.dumps(msg, indent=4)))
            else:
                if msg["destination"].startswith("CID"):
                    msg["source"] = self.bridge_id + "/" + msg["source"]
                    self.queueMessage(msg)
                else:
                    self.cbLog("warning","Illegal desination in app message. Should be CIDn: " + str(json.dumps(msg, indent=4)))
        except Exception as ex:
            self.cbLog("warning", "Malformed message from app. Exception: Type: " + str(type(ex)) + "exception: " +  str(ex.args))
    
if __name__ == '__main__':
    Concentrator(sys.argv)
