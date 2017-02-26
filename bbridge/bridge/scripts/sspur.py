#!/usr/bin/env python
# sspur.py
# Copyright (C) ContinuumBridge Limited, 2017 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../manager')))
from cbsupervisor_a import Supervisor

def sspur():
    print("Snappy Spur Starting")
    print("This is sspur.py in bridge/scripts")
    Supervisor()

if __name__ == '__main__':
    sspur()

