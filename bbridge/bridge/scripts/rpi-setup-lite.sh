#!/bin/bash

## Script Start ##

sudo apt-get install -y rpi-update
sudo apt-get update -y
sudo apt-get upgrade -y

if ask "Would you like to setup the WiFi? You will need an SSID and WPA Shared Key for the network [y/N]"; then
    echo "Set up the WiFi please"
    setup_wifi
else
    echo "No thanks to the WiFi"
fi

sudo apt-get install -y vim

# From Andy's notes
sudo apt-get install -y lxc
sudo apt-get install -y busybox-static
sudo apt-get install -y swig

sudo apt-get install -y python-dev
sudo apt-get install -y python-pip
sudo apt-get install -y python-software-properties
sudo apt-get install -y nodejs npm node-semver
sudo apt-get install -y python-pexpect

sudo apt-get install python-twisted

# For Bluetooth LE
sudo apt-get install -y libglib2.0-dev 
sudo apt-get install -y libdbus-1-dev 
sudo apt-get install -y libusb-dev 
sudo apt-get install -y libudev-dev 
sudo apt-get install -y libical-dev
sudo apt-get install -y systemd 
sudo apt-get install -y libreadline-dev

mkdir /home/bridge/src
cd /home/bridge/src
wget https://www.kernel.org/pub/linux/bluetooth/bluez-5.7.tar.gz
tar xvfz bluez-5.7.tar.gz
cd bluez-5.7
./configure --prefix=/usr --mandir=/usr/share/man --sysconfdir=/etc --localstatedir=/var --disable-systemd
sudo make
sudo make install

# sqlite front-end
pip install dataset
pip install httplib2
