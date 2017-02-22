#!/usr/bin/env python
# sspur.py
# Copyright (C) ContinuumBridge Limited, 2017 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
import subprocess
from bridge.manager.cbsupervisor_a import Supervisor

def main():
    print("Snappy Spur Starting")
    print("This is sspur.py")
    Supervisor()

if __name__ == '__main__':
    main()

