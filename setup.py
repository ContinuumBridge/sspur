#!/usr/bin/env python
from distutils.core import setup
setup(name='snappy-spur',
      version='0.1.3',
      author='Peter Claydon',
      author_email='peter.claydon@continuumbridge.com',
      py_modules=['snappy-spur'],
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
              'snappy-spur=snappy-spur:main'
           ]
      },
      )
