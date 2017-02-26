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
import os
CB_LOGFILE = "/var/log/cbridge.log"

logging.basicConfig(filename=CB_LOGFILE,level=logging.DEBUG,format='%(asctime)s %(levelname)s: %(message)s')
try:
    subprocess.call(["cp", "../../bridge_clone/scripts/cb", "/usr/bin/cb"])
    subprocess.call(["cp", "../../bridge_clone/scripts/cbridge", "/etc/init.d/cbridge"])
    subprocess.call(["update-rc.d", "-f", "ntp", "remove"])
    subprocess.call(["pkill", "ntpd"])
    subprocess.call(["cp", "../../bridge_clone/scripts/fstab", "/etc/fstab"])
    subprocess.call(["cp", "../../bridge_clone/scripts/rsyslog.logrotate", "/etc/logrotate.d/rsyslog"])
    subprocess.call(["cp", "../../bridge_clone/scripts/cbshell.logrotate", "/etc/logrotate.d/cbshell"])
    if os.path.exists("/opt/z-way-server/ZDDX"):
        subprocess.call(["../../bridge_clone/scripts/cbUpdateXMLs.sh"])
        logging.info("%s Updated z-way-server XMLs", ModuleName)
    else:
        logging.info("%s No z-way-server. Did not update z-way-server XMLs", ModuleName)

    logging.info("Processing thisbridge.sh to add CB_SFTP_PASSWORD")
    i = open("/opt/cbridge/thisbridge/thisbridge.sh", 'r')
    o = open("thisbridge.tmp", 'w') 
    found = False
    for line in i:
        if "CB_SFTP_PASSWORD" in line:
            found = True
        o.write(line)
    if not found:
        o.write("export CB_SFTP_PASSWORD=\"DTfC,3[!7kB[AfxB\"")
    i.close()
    o.close()
    subprocess.call(["mv", "thisbridge.tmp", "/opt/cbridge/thisbridge/thisbridge.sh"])

    if not os.path.exists("../../bridge_clone/node_modules"):
        subprocess.call(["cp", "-r", "../../bridge/node_modules", "../../bridge_clone/node_modules"])
        logging.info("%s Copied old node_modules", ModuleName)
    else:
        logging.info("%s New node_modules", ModuleName)
    logging.info("%s Upgrade script run successfully", ModuleName)
    exit(0)
except Exception as ex:
    logging.warning("%s Problem running upgrade script", ModuleName)
    logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
    exit(1)
