#!/bin/bash
# Runs cbsupervisor with local bridge controller & outputs to shell rather than log file
sudo rm ../../thisbridge/skt-*
if [ -f ../../thisbridge/thisbridge.sh ]; then
    echo 'Starting bridge'
    # Must source so that exports affect the parent script
    source ../../thisbridge/thisbridge.sh
    CB_NO_CLOUD='True' ./cbsupervisor.py
else
    echo "thisbridge.sh file does not exist"
    exit
fi
