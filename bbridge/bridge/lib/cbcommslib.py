#!/usr/bin/env python
# cbcommslib.py
# Copyright (C) ContinuumBridge Limited, 2013-2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
"""
self.status must be set by each app & adaptor to report back to the manager. Allowable values:
idle            Initial value at the start
configured      Should be set to indicate successful configuration
running         Indicates normal operation
please_restart  Something wrong. Requests the manager to restart the app
timeout         Not usually set by user apps
running should be set at least every 10 seconds as a heartbeat
"""

ModuleName = "cbcommslib" 
TIME_TO_MONITOR_STATUS = 60     # Time to wait before sending status messages to manager
SEND_STATUS_INTERVAL = 30       # Interval between sending status messages to manager
REACTOR_STOP_DELAY = 2          # Time to wait between telling app/adt to stop & stopping reactor

import sys
import os.path
import time
import json
import logging
import procname
sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../../bridge/lib')))
from cbconfig import *
from twisted.internet.protocol import Protocol, Factory
from twisted.internet.protocol import ClientFactory
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import LineReceiver
from twisted.internet import task
from twisted.internet import threads
from twisted.internet import defer
from twisted.internet import reactor
LineReceiver.MAX_LENGTH = 262143

def isotime():
    t = time.time()
    gmtime = time.gmtime(t)
    milliseconds = '%03d' % int((t - int(t)) * 1000)
    now = time.strftime('%Y-%m-%dT%H:%M:%S.', gmtime) + milliseconds +"Z"
    return now

class CbAdaptor:
    """This should be sub-classed by any app."""
    ModuleName = "CbAdaptor           " 

    def __init__(self, argv):
        logging.basicConfig(filename=CB_LOGFILE,level=CB_LOGGING_LEVEL,format='%(asctime)s %(levelname)s: %(message)s')
        self.doStop = False
        self.status = "ok"
        self.configured = False
        self.cbFactory = {}
        self.appInstances = []

        if len(argv) < 3:
            logging.error("%s cbAdaptor improper number of arguments", ModuleName)
            exit(1)
        managerSocket = argv[1]
        self.id = argv[2]
        logging.info("%s Hello from %s", ModuleName, self.id)

        initMsg = {"id": self.id,
                   "type": "adt",
                   "status": "req-config"} 
        self.managerFactory = CbClientFactory(self.processManager, initMsg)
        reactor.connectUNIX(managerSocket, self.managerFactory, timeout=2)

        reactor.callLater(TIME_TO_MONITOR_STATUS, self.sendStatus)
        reactor.run()

    def onConfigureMessage(self, config):
        """The adaptor should overwrite this and do all configuration in it."""
        logging.info("%s %s does not have onConfigureMessage", ModuleName, self.id)

    def onAppInit(self, message):
        """This should be overridden by the actual adaptor."""
        logging.warning("%s %s should subclass onAppInit method", ModuleName, self.id)

    def onAction(self, action):
        """This should be overridden by the actual adaptor."""
        logging.warning("%s %s should subclass onAction method", ModuleName, self.id)

    def onAppRequest(self, message):
        """This should be overridden by the actual adaptor."""
        logging.warning("%s %s should subclass onAppRequest method", ModuleName, self.id)

    def onZwaveMessage(self, message):
        """This should be overridden by a Z-wave adaptor."""
        pass

    def onAppMessage(self, message):
        if "request" in message:
            if message["request"] == "init":
                self.onAppInit(message)
            elif message["request"] == "service": 
                self.onAppRequest(message)
            elif message["request"] == "command": 
                self.onAppCommand(message)
            else:
                logging.warning("%s %s Unexpected message from app: %s", ModuleName, self.id, message)
        else:
            logging.warning("%s %s No request field in message from app: %s", ModuleName, self.id, message)
 
    def onStop(self):
        """The adapotor should overwrite this if it needs to do any tidying-up before stopping"""
        pass

    def sendStatus(self):
        """ Send status to the manager at regular intervals as a heartbeat. """
        msg = {"id": self.id,
               "status": self.status}
        self.sendManagerMessage(msg)
        reactor.callLater(SEND_STATUS_INTERVAL, self.sendStatus)

    def cbLog(self, level, log):
        msg = {"id": self.id,
               "status": "log",
               "level": level,
               "body": log}
        self.sendManagerMessage(msg)

    def cbConfigure(self, config):
        """Config is based on what apps are available."""
        #logging.debug("%s %s Configuration: %s ", ModuleName, self.id, config)
        self.name = config["name"]
        self.friendly_name = config["friendly_name"]
        self.device = config["btAdpt"]
        self.addr = config["btAddr"]
        self.sim = int(config["sim"])
        for app in config["apps"]:
            iName = app["id"]
            if iName not in self.appInstances:
                # configureig may be called again with updated config
                name = app["name"]
                adtSoc = app["adtSoc"]
                self.appInstances.append(iName)
                self.cbFactory[iName] = CbServerFactory(self.onAppMessage)
                reactor.listenUNIX(adtSoc, self.cbFactory[iName])
        if "zwave_socket" in config:
            initMsg = {"id": self.id,
                       "request": "init"}
            self.zwaveFactory = CbClientFactory(self.onZwaveMessage, initMsg)
            reactor.connectUNIX(config["zwave_socket"], self.zwaveFactory, timeout=30)
        self.onConfigureMessage(config)
        self.configured = True

    def processManager(self, cmd):
        #logging.debug("%s %s Received from manager: %s ", ModuleName, self.id, cmd)
        if cmd["cmd"] == "stop":
            self.onStop()
            self.doStop = True
            msg = {"id": self.id,
                   "status": "stopping"}
            #Adaptor must stop within REACTOR_STOP_DELAY seconds
            reactor.callLater(REACTOR_STOP_DELAY, self.stopReactor)
        elif cmd["cmd"] == "config":
            #Call in thread in case user code hangs
            reactor.callInThread(self.cbConfigure, cmd["config"]) 
            msg = {"id": self.id,
                   "status": "ok"}
        elif cmd["cmd"] == "action":
            #Call in thread in case user code hangs
            reactor.callInThread(self.onAction, cmd["action"]) 
            msg = {"id": self.id,
                   "status": "ok"}
        else:
            msg = {"id": self.id,
                   "status": self.status}
        self.sendManagerMessage(msg)
        # The adaptor must set self.status back to "running" as a heartbeat
        if self.status == "running":
            self.status = "timeout"

    def stopReactor(self):
        try:
            reactor.stop()
        except:
            logging.debug("%s %s stopReactor. Reactor was not running", ModuleName, self.id)
        logging.debug("%s Bye from %s", ModuleName, self.id)
        sys.exit

    def sendMessage(self, msg, iName):
        self.cbFactory[iName].sendMsg(msg)

    def sendManagerMessage(self, msg):
        self.managerFactory.sendMsg(msg)

    def sendZwaveMessage(self, msg):
        self.zwaveFactory.sendMsg(msg)

class CbApp:
    """
    This should be sub-classed by any app.
    """
    ModuleName = "cbApp" 

    def __init__(self, argv):
        logging.basicConfig(filename=CB_LOGFILE,level=CB_LOGGING_LEVEL,format='%(asctime)s %(message)s')
        self.appClass = "none"       # Should be overwritten by app
        self.cbFactory = {}
        self.adtInstances = []
        self.doStop = False
        self.friendlyLookup = {}
        self.configured = False
        self.status = "ok"
        self.bridge_id = "unconfigured"

        if len(argv) < 3:
            logging.error("%s cbApp improper number of arguments", ModuleName)
            exit(1)
        managerSocket = argv[1]
        self.id = argv[2]
        logging.info("%s Hello from %s", ModuleName, self.id)
        procname.setprocname(self.id)

        initMsg = {"id": self.id,
                   "type": "app",
                   "status": "req-config"} 
        self.managerFactory = CbClientFactory(self.processManager, initMsg)
        reactor.connectUNIX(managerSocket, self.managerFactory, timeout=2)

        reactor.callLater(TIME_TO_MONITOR_STATUS, self.sendStatus)
        reactor.run()

    def onConcMessage(self, message):
        """This should be overridden by the actual app."""

    def onConfigureMessage(self, config):
        """The app should overwrite this and do all configuration in it."""
        logging.warning("%s %s should subclass onConfigureMessage method", ModuleName, self.id)

    def onStop(self):
        """The app should overwrite this and do all configuration in it."""
        pass

    def onManagerStatus(self, status):
        """The app should overwrite this if it needs to use manager status messages."""
        pass

    def onAdaptorService(self, message):
        """This should be overridden by the actual app."""
        logging.warning("%s %s should subclass onAdaptorService method", ModuleName, self.id)

    def onAdaptorData(self, message):
        """This should be overridden by the actual app."""
        logging.warning("%s %s should subclass onAdaptorData method", ModuleName, self.id)

    def onAdaptorMessage(self, message):
        if message["content"] == "service":
            self.onAdaptorService(message)
        else:
            self.onAdaptorData(message)
 
    def cbLog(self, level, log):
        msg = {"id": self.id,
               "status": "log",
               "level": level,
               "body": log}
        self.sendManagerMessage(msg)

    def sendStatus(self):
        """ Send status to the manager at regular intervals as a heartbeat. """
        msg = {"id": self.id,
               "status": self.status}
        self.sendManagerMessage(msg)
        reactor.callLater(SEND_STATUS_INTERVAL, self.sendStatus)

    def cbConfigure(self, config):
        """Config is based on what adaptors are available."""
        #logging.debug("%s %s Config: %s", ModuleName, self.id, json.dumps(config, indent=4))
        # Connect to socket for each adaptor
        self.bridge_id = config["bridge_id"]
        self.onConfigureMessage(config)  # Before adaptor sockets because adaptor messages were sometimes arriving first
        for adaptor in config["adaptors"]:
            iName = adaptor["id"]
            initMsg = {
                "id": self.id,
                "appClass": self.appClass,
                "request": "init"
            }
            if iName not in self.adtInstances:
                # Allows for adding extra adaptors on the fly
                name = adaptor["name"]
                adtSoc = adaptor["adtSoc"]
                friendly_name = adaptor["friendly_name"]
                self.friendlyLookup.update({iName: friendly_name})
                self.adtInstances.append(iName)
                self.cbFactory[iName] = CbClientFactory(self.onAdaptorMessage, initMsg)
                reactor.connectUNIX(adtSoc, self.cbFactory[iName], timeout=30)
            else:
                self.sendMessage(initMsg, iName)
        # Connect to Concentrator socket
        if not self.configured:
            # Connect to the concentrator
            concSocket = config["concentrator"]
            initMsg = {"msg": "init",
                       "appID": self.id
                      }
            self.cbFactory["conc"] = CbClientFactory(self.onConcMessage, initMsg)
            reactor.connectUNIX(concSocket, self.cbFactory["conc"], timeout=30)
            self.configured = True
            reactor.callFromThread(self.onManagerStatus, config["connected"])

    def processManager(self, cmd):
        #logging.debug("%s %s Received from manager: %s", ModuleName, self.id, cmd)
        if cmd["cmd"] == "stop":
            self.onStop()
            self.doStop = True
            msg = {"id": self.id,
                   "status": "stopping"}
            #App must stop within REACTOR_STOP_DELAY seconds
            reactor.callLater(REACTOR_STOP_DELAY, self.stopReactor)
        elif cmd["cmd"] == "config":
            #Call in thread in case user code hangs
            reactor.callInThread(self.cbConfigure, cmd["config"]) 
            msg = {"id": self.id,
                   "status": "ok"}
        elif cmd["cmd"] == "status":
            if "status" in cmd:
                self.onManagerStatus(cmd["status"])
            msg = {"id": self.id,
                   "status": self.status}
        self.sendManagerMessage(msg)
        # The app must set self.status back to "running" as a heartbeat
        if self.status == "running":
            self.status = "timeout"

    def stopReactor(self):
        try:
            reactor.stop()
        except:
            self.cbLog("warning", "stopReactor when reactor not running")
        self.cbLog("debug", "Bye")
        sys.exit

    def sendMessage(self, msg, iName):
        self.cbFactory[iName].sendMsg(msg)

    def sendManagerMessage(self, msg):
        self.managerFactory.sendMsg(msg)

class CbClient():
    """
    aid is to ID of the app.
    cid is the client ID that the app is to communicate with.
    keep is the number of message bodies to keep if messages are not acknowleged by the client.
    CBClient will attempt to resend message bodies that are kept.
    """
    def __init__(self, aid , cid, keep=50):
        self.aid = aid
        self.cid = cid
        self.keep = keep
        self.onClientMessage = None
        self.count = 0
        self.bodies = []
        self.saveFile =  CB_CONFIG_DIR + self.aid + ".save"

    def loadSaved(self):
        try:
            if os.path.isfile(self.saveFile):
                with open(self.saveFile, 'r') as f:
                    self.bodies = json.load(f)
            for c in self.bodies:
                if c["n"] > self.count:
                    self.count = c["n"]
            self.cbLog("debug", "Loaded saved unsent messages. count: " + str(self.count))
        except Exception as ex:
            self.cbLog("warning", "Problem loading unsent messages. Exception. Type: " + str(type(ex)) + "exception: " +  str(ex.args))
        finally:
            try:
                os.remove(self.saveFile)
                self.cbLog("debug", "deleted saved messages file")
            except Exception as ex:
                self.cbLog("debug", "Cannot remove unsent messages file. Exception. Type: " + str(type(ex)) + "exception: " +  str(ex.args))

    def send(self, body):
        body["n"] = self.count
        self.count += 1
        self.bodies.append(body)
        if len(self.bodies) > self.keep:
            del self.bodies[0]
        message = {
                   "source": self.aid,
                   "destination": self.cid,
                   "body": self.bodies
                  }
        self.sendMessage(message, "conc")
        #self.cbLog("debug", "sending message: " + str(message))

    def receive(self, message):
        try:
            #self.cbLog("debug", "Message from client: " + str(message))
            rx_n = 0
            sendAck = False
            if "body" in message:
                for b in message["body"]:
                    if "n" in b:
                        if rx_n < b["n"]:
                            rx_n = b["n"]
                        del b["n"]
                        sendAck = True
                    if "a" in b:
                        if b["a"] == 0:
                            self.bodies = []
                        else:
                            #self.cbLog("debug", "bodies before removal: " + str(self.bodies))
                            removeList = []
                            for sent in self.bodies:
                                #self.cbLog("debug", "sent_n: " + str(sent["n"]) + ", b_a: " + str(b["a"]))
                                if sent["n"] <= b["a"]:
                                    removeList.append(sent)
                            for r in removeList:
                                self.bodies.remove(r)
                                #self.cbLog("debug", "Removed body " + str(r) + " from queue")
                                #self.cbLog("debug", "bodies " + str(self.bodies))
                    elif self.onClientMessage:
                        self.onClientMessage(b)
                if sendAck:
                    ack = {
                           "source": self.aid,
                           "destination": self.cid,
                           "body": [{"a": rx_n}]
                           }
                    self.sendMessage(ack, "conc")
            elif not "status" in message:
                self.cbLog("warning", "Received message from client with no body or status")
        except Exception as ex:
            self.cbLog("warning", "Client receive exception. Type: " + str(type(ex)) + "exception: " +  str(ex.args))

    def save(self):
        try:
            if self.bodies:
                with open(self.saveFile, 'w') as f:
                    json.dump(self.bodies, f)
                    self.cbLog("info", "Saved unsent messages")
                    self.cbLog("debug", "saving bodies:: " + str(self.bodies))
        except Exception as ex:
            self.cbLog("warning", "Problem saving unsent messages exception. Type: " + str(type(ex)) + "exception: " +  str(ex.args))

class CbClientProtocol(LineReceiver):
    def __init__(self, processMsg, initMsg):
        self.processMsg = processMsg
        self.initMsg = initMsg

    def connectionMade(self):
        self.sendLine(json.dumps(self.initMsg))

    def lineReceived(self, data):
        self.processMsg(json.loads(data))

    def sendMsg(self, msg):
        try:
            self.sendLine(json.dumps(msg))
        except:
            logging.warning("%s Message not send: %s", ModuleName, msg)

class CbClientFactory(ReconnectingClientFactory):
    def __init__(self, processMsg, initMsg):
        self.processMsg = processMsg
        self.initMsg = initMsg

    def buildProtocol(self, addr):
        self.proto = CbClientProtocol(self.processMsg, self.initMsg)
        return self.proto

    def sendMsg(self, msg):
        try:
            self.proto.sendMsg(msg)
        except:
            logging.warning("%s Message not send: %s", ModuleName, msg)

    def clientConnectionLost(self, connector, reason):
        logging.debug('%s Lost connection. Reason: %s', ModuleName, reason)
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.debug('%s Failed  connection. Reason: %s', ModuleName, reason)
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

class CbServerProtocol(LineReceiver):
    def __init__(self, processMsg):
        self.processMsg = processMsg

    def lineReceived(self, data):
        self.processMsg(json.loads(data))

    def sendMsg(self, msg):
        try:
            self.sendLine(json.dumps(msg))
        except:
            logging.warning("%s Message not send: %s", ModuleName, msg)

class CbServerFactory(Factory):
    def __init__(self, processMsg):
        self.processMsg = processMsg

    def buildProtocol(self, addr):
        self.proto = CbServerProtocol(self.processMsg)
        return self.proto

    def sendMsg(self, msg):
        self.proto.sendMsg(msg)
