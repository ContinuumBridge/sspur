#!/usr/bin/env python
from distutils.core import setup
setup(name='sspur',
      version='0.1.15',
      author='Peter Claydon',
      author_email='peter.claydon@continuumbridge.com',
      py_modules=['sspur'],
      packages=['bridge', 'bridge/manager', 'bridge/lib', 'bridge/scripts', 'bridge/concentrator', 'bridge/conman', 'apps_dev', 'apps_dev/spur_app', 'adaptors_dev', 'adaptors_dev/lprs_adaptor'],
      install_requires=[
          'Twisted',
          'pysftp',
          'procname',
          'requests',
          'pexpect',
          'pyserial'
      ],
      entry_points={
          'console_scripts': [
              'sspur = sspur:main'
           ]
      },
      )
