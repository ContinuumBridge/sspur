#!/bin/bash
mkdir -p /cgroup
mount -t cgroup none /cgroup
cp -a /continuum-bridge-proto1/lxc-scripts/lxc-cb /usr/lib/lxc/templates
