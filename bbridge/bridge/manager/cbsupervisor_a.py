#!/usr/bin/env python
# cbsupervisor.py
# Copyright (C) ContinuumBridge Limited, 2014-2015 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
"""
"""
ModuleName = "Supervisor"

import sys
import signal
import time
import os
import glob
import procname
from subprocess import call
from subprocess import Popen
from subprocess import check_output
from twisted.internet import threads
from twisted.internet import reactor, defer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../lib')))
from cbcommslib import CbServerProtocol
from cbcommslib import CbServerFactory
from cbconfig import *
sys.path.insert(0, CB_BRIDGE_ROOT + "/conman")
import conman

#CB_BID = os.getenv('CB_BID', 'unconfigured')
print("cbsupervisor, CB_CIB: {}".format(CB_BID))

MANAGER_START_TIME = 3            # Time to allow for manager to start before starting to monitor it (secs)
WATCHDOG_INTERVAL = 30            # Time between manager checks (secs)
REBOOT_WAIT = 10                  # Time to allow bridge to stop before rebooting
RESTART_INTERVAL = 10             # Time between telling manager to stop and starting it again
EXIT_WAIT = 2                     # On SIGINT, time to wait before exit after manager signalled to stop
SAFETY_INTERVAL = 300             # Delay before rebooting if manager failed to start
NTP_UPDATE_INTERVAL = 12*3600     # How often to run ntpd to sync time
FIVE_MINUTES = 5*60               # As it says on the tin

class Supervisor:
    def __init__(self):
        procname.setprocname('cbsupervisor')
        logging.basicConfig(filename=CB_LOGFILE,level=CB_LOGGING_LEVEL,format='%(asctime)s %(levelname)s: %(message)s')
        logging.info("%s ************************************************************", ModuleName)
        if not os.path.exists(CB_SOCKET_DIR):
            os.makedirs(CB_SOCKET_DIR)
        print("cbsupervisor, CB_RASPBERRY: {}, CB_DEV_APPS: {}".format(CB_RASPBERRY, CB_DEV_APPS)) 
        self.connected = False
        self.checkingManager = False
        self.waitingToReconnect = False
        self.conduitConnectAttempt = 0
        self.timeStamp = 0
        self.managerPings = 0
        self.timeChanged = False
        signal.signal(signal.SIGINT, self.signalHandler)  # For catching SIGINT
        signal.signal(signal.SIGTERM, self.signalHandler)  # For catching SIGTERM
        reactor.callLater(0.1, self.startConman)
        if CB_RASPBERRY:
            reactor.callInThread(self.iptables)
        reactor.callLater(1, self.startManager, False)
        #reactor.callLater(120, self.disconnectTest)
        reactor.run()

    def startConman(self):
        logging.debug("%s startConman: CB_CELLULAR_PRIORITY: %s", ModuleName, CB_CELLULAR_PRIORITY)
        self.conman = conman.Conman()
        if CB_RASPBERRY:
            self.conman.start(logFile=CB_LOGFILE, logLevel=CB_LOGGING_LEVEL, cellularPriority=CB_CELLULAR_PRIORITY)

    def startManager(self, restart):
        self.starting = True
        if CB_RASPBERRY:
            self.manageNTP(False)
        # Try to remove all sockets, just in case
        for f in glob.glob(CB_SOCKET_DIR + "SKT-*"):
            os.remove(f)
        for f in glob.glob(CB_SOCKET_DIR + "SKT-*"):
            os.remove(f)
        # Remove file that signifies that manager has exited 
        if os.path.exists(CB_MANAGER_EXIT):
            os.remove(CB_MANAGER_EXIT)
        # Open a socket for communicating with the bridge manager
        s = CB_SOCKET_DIR + "SKT-SUPER-MGR"
        self.cbManagerFactory = CbServerFactory(self.onManagerMessage)
        self.mgrPort = reactor.listenUNIX(s, self.cbManagerFactory, backlog=4)

        # Start the manager in a subprocess
        exe = CB_BRIDGE_ROOT + "/manager/cbmanager.py"
        try:
            self.managerProc = Popen([exe])
            logging.info("%s Starting bridge manager", ModuleName)
            if not CB_DEV_BRIDGE:
                if not self.checkingManager:
                    reactor.callLater(3*WATCHDOG_INTERVAL, self.checkManager, time.time())
                    checkingManager = True
        except Exception as ex:
            logging.error("%s Bridge manager failed to start: %s", ModuleName, exe)
            logging.error("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            # Give developer a chance to do something before rebooting:
            reactor.callLater(SAFETY_INTERVAL, self.reboot)
        
    def cbSendManagerMsg(self, msg):
        #logging.debug("%s Sending msg to manager: %s", ModuleName, msg)
        try:
            self.cbManagerFactory.sendMsg(msg)
        except Exception as ex:
            logging.warning("%s Failed to send message to manager: %s", ModuleName, str(msg))
            logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def onManagerMessage(self, msg):
        #logging.debug("%s onManagerMessage received message: %s", ModuleName, msg)
        # Regardless of message content, timeStamp is the time when we last heard from the manager
        self.timeStamp = time.time()
        if msg["msg"] == "restart":
            logging.info("%s onManagerMessage restarting", ModuleName)
            self.cbSendManagerMsg({"msg": "stopall"})
            self.starting = True
            reactor.callLater(RESTART_INTERVAL, self.checkManagerStopped, 0)
        elif msg["msg"] == "restart_cbridge":
            logging.info("%s onManagerMessage restart_cbridge", ModuleName)
            self.starting = True
            reactor.callLater(0, self.restartCbridge)
        elif msg["msg"] == "reboot":
            logging.info("%s Reboot message received from manager", ModuleName)
            self.starting = True
            reactor.callFromThread(self.doReboot)
        elif msg["msg"] == "status":
            if msg["status"] == "disconnected":
                logging.info("%s onManagerMessage. disconnected", ModuleName)
                self.onDisconnected()
            else:
                self.conduitConnectAttempt = 0

    def disconnectTest(self):
        self.cbSendManagerMsg({"msg": "reconnect"})

    def onDisconnected(self):
        logging.debug("%s onDisconnected, self.waitingToReconnect: %s", ModuleName, str(self.waitingToReconnect))
        if not self.waitingToReconnect:
            self.waitingToReconnect = True
            d = threads.deferToThread(self.conman.checkPing)
            d.addCallback(self.checkDisconnected)

    def checkDisconnected(self, connected):
        if connected:
            logging.info("%s checkDisconnected. Manager disconnected, conman connected. conduitConnectAttempt: %s", ModuleName, self.conduitConnectAttempt)
            if self.conduitConnectAttempt == 0:
                logging.debug("%s checkDisconnected. Sending reconnect", ModuleName)
                self.reconnectConduit()
                self.conduitConnectAttempt = 1
            else:
                logging.debug("%s checkDisconnected. conduitConnectAttempt: %s", ModuleName, str(self.conduitConnectAttempt))
                self.cbSendManagerMsg({"msg": "disconnect"})
                reactor.callLater(self.conduitConnectAttempt*FIVE_MINUTES, self.reconnectConduit)
                if self.conduitConnectAttempt < 8:
                    self.conduitConnectAttempt += 1
        else:
            logging.info("%s checkDisconnected. Manager disconnected, conman disconnected. Asking conman to reconnect", ModuleName)
            self.conman.setConnected(False)

    def resetWaitingToReconnect(self):
        self.waitingToReconnect = False

    def reconnectConduit(self):
        logging.debug("%s reconnectConduit", ModuleName)
        self.cbSendManagerMsg({"msg": "reconnect"})
        reactor.callLater(10, self.resetWaitingToReconnect)  # So that we don't go around in circles

    def checkManagerStopped(self, count):
        if os.path.exists(CB_MANAGER_EXIT):
            logging.debug("%s checkManagerStopped. Manager stopped", ModuleName)
            os.remove(CB_MANAGER_EXIT)
            self.startManager(True)
        elif count < 3:
            reactor.callLater(RESTART_INTERVAL, self.checkManagerStopped, count + 1)
            logging.info("%s checkManagerStopped. Manager not stopped yet, count: %s", ModuleName, count)
        else:
            logging.warning("%s checkManagerStopped. Manager not stopped after count %s, rebooting", ModuleName, count)
            self.reboot()

    def checkManager(self, startTime):
        #logging.debug("%s checkManager, starting: %s, timeChanged: %s, timeStamp: %s, startTime: %s", ModuleName, self.starting, \
        #    self.timeChanged, self.timeStamp, startTime)
        if not self.starting and not self.timeChanged:
            # -1 is allowance for times not being sync'd (eg: separate devices)
            if self.timeStamp > startTime - 1:
                try:
                    connection = self.conman.connectedBy()
                    msg = {"msg": "status",
                           "connection": connection,
                           "status": "ok"
                          }
                    self.cbSendManagerMsg(msg)
                except Exception as ex:
                    # Caters for ntp changing time & hence doing check before manager has started
                    if self.managerPings < 2:
                        self.managerPings +=1
                        logging.warning("%s Unable to to send status message to manager, exception: %s %s", ModuleName, type(ex), str(ex.args))
                    else:
                        logging.error("%s Cannot communicate with manager. Rebooting, exception: %s %s", ModuleName, type(ex), str(ex.args))
                        self.reboot()
                finally:
                    reactor.callLater(WATCHDOG_INTERVAL, self.checkManager, time.time())
            else:
                logging.warning("%s Manager appears to be dead. Trying to restart nicely", ModuleName)
                msg = {"msg": "stopall"
                      }
                try:
                    self.cbSendManagerMsg(msg)
                    reactor.callLater(WATCHDOG_INTERVAL, self.recheckManager, time.time())
                except Exception as ex:
                    logging.warning("%s Cannot send message to manager. Rebooting", ModuleName)
                    logging.error("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
                    self.reboot()
        else:
            try:
                connection = self.conman.connectedBy()
                msg = {"msg": "status",
                       "connection": connection,
                       "status": "ok"
                      }
                self.cbSendManagerMsg(msg)
            except Exception as ex:
                logging.warning("%s Unable to to send status message to manager (1), exception: %s %s", ModuleName, type(ex), str(ex.args))
            self.starting = False
            self.timeChanged = False
            reactor.callLater(WATCHDOG_INTERVAL, self.checkManager, time.time())

    def recheckManager(self, startTime):
        logging.debug("%s recheckManager", ModuleName)
        # Whatever happened, stop listening on manager port.
        self.mgrPort.stopListening()
        # Manager responded to request to stop. Restart it.
        if self.timeStamp > startTime - 1 and os.path.exists(CB_MANAGER_EXIT):
            logging.info("%s recheckManager. Manager stopped sucessfully. Restarting ...", ModuleName)
            os.remove(CB_MANAGER_EXIT)
            self.startManager(True)
        else:
            # Manager is well and truely dead.
            logging.warning("%s Manager is well and truly dead. Rebooting", ModuleName)
            self.reboot()

    def iptables(self):
        try:
            # This is zwave.me
            ip_to_block = "46.20.244.72"
            s = check_output(["iptables", "-A", "INPUT", "-s", ip_to_block, "-j", "DROP"])
            s = check_output(["iptables", "-A", "OUTPUT", "-s", ip_to_block, "-j", "DROP"])
        except Exception as ex:
            logging.warning("%s iptables setup failed", ModuleName)
            logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def doReboot(self):
        """ Give bridge manager a chance to tidy up nicely before rebooting. """
        logging.info("%s doReboot", ModuleName)
        if CB_CELLULAR_BRIDGE:
            try:
                Popen(["/usr/bin/modem3g/sakis3g", "--sudo", "disconnect"])
            except Exception as ex:
                logging.warning("%s deReboot. sakis3g disconnect failed", ModuleName)
                logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
        try:
            self.cbSendManagerMsg({"msg": "stopall"})
        except Exception as ex:
            logging.warning("%s Cannot tell manager to stop, just rebooting", ModuleName)
            logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
        # Tidy up
        #self.mgrPort.stopListening()
        reactor.callLater(REBOOT_WAIT, self.reboot)

    def manageNTP(self, syncd):
        if not syncd:
            logging.info("%s Calling ntpd to update time, syncd: %s", ModuleName, syncd)
            d = threads.deferToThread(self.manageNTPThread)
            d.addCallback(self.manageNTP)
        else:
            reactor.callLater(NTP_UPDATE_INTERVAL, self.manageNTP, False)

    def manageNTPThread(self):
        logging.debug("%s manageNTPThread", ModuleName)
        try:
            syncd = False
            while not syncd:
                s = check_output(["sudo", "/usr/sbin/ntpd", "-p", "/var/run/ntpd.pid", "-g", "-q"])
                logging.info("%s NTP time updated %s", ModuleName, str(s))
                if "time" in str(s):
                    self.timeChanged = True
                    syncd = True
                else:
                    time.sleep(10)
            return syncd
        except Exception as ex:
            logging.warning("%s Cannot run NTP. Exception: %s %s", ModuleName, type(ex), str(ex.args))
            time.sleep(10)
            return False
        
    def reboot(self):
        logging.info("%s Rebooting", ModuleName)
        try:
            reactor.stop()
        except Exception as ex:
            logging.warning("%s Unable to stop reactor, just rebooting", ModuleName)
            logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
        if CB_SIM_LEVEL == '0':
            try:
                logging.info("%s Saving logs and rebooting now. Goodbye ...", ModuleName)
                call(['cp', CB_LOGFILE, CB_CONFIG_DIR + "cbridge.savelog"]) 
                call(['cp', "/var/log/syslog", CB_CONFIG_DIR + "syslog.savelog"]) 
                call(['cp', "/var/log/auth.log", CB_CONFIG_DIR + "auth.savelog"]) 
                call(['cp', "/var/log/daemon.log", CB_CONFIG_DIR + "daemon.savelog"]) 
                call(['cp', "/var/log/z-way-server.log", CB_CONFIG_DIR + "z-way-server.savelog"]) 
                call(['cp', "/var/log/cbshell.log", CB_CONFIG_DIR + "cbshell.savelog"]) 
            except Exception as ex:
                logging.warning("%s Unable to copy log some files. Exception: %s %s", ModuleName, type(ex), str(ex.args))
            try:
                call(["reboot"])
            except Exception as ex:
                logging.info("%s Unable to reboot, probably because bridge not run as root", ModuleName)
                logging.info("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
        else:
            logging.info("%s Would have rebooted if not in sim mode", ModuleName)

    def restartCbridge(self):
        try:
            logging.info("%s Restarting cbridge", ModuleName)
            call(["/etc/init.d/cbridge", "restart"])
        except Exception as ex:
            logging.warning("%s Unable to restart cbridge", ModuleName)
            logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))

    def signalHandler(self, signal, frame):
        logging.debug("%s signalHandler received signal", ModuleName)
        self.cbSendManagerMsg({"msg": "stopall"})
        reactor.callLater(EXIT_WAIT, self.exitSupervisor)

    def exitSupervisor(self):
        logging.info("%s exiting", ModuleName)
        reactor.stop()
        sys.exit
        
if __name__ == '__main__':
    Supervisor()
