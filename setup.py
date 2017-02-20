#!/usr/bin/env python
from distutils.core import setup
setup(name='snappy-spur',
      version='0.1.1',
      author='Peter Claydon',
      author_email='peter.claydon@continuumbridge.com',
      py_modules=['snappy-spur'],
      install_requires=[
          'Twisted',
          'httplib2',
          'pysftp,'
          'dropbox',
          'procname',
          'requests',
          'flask-peewee',
          'Twisted',
          'pexpect',
          'pyserial'
      ],
      entry_points={
          'console_scripts': [
              'snappy-spur = bridge/scripts/snappy-cbridge'
           ]
      },
      )