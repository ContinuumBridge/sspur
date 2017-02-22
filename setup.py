#!/usr/bin/env python
from distutils.core import setup
setup(name='spur',
      version='0.1.4',
      author='Peter Claydon',
      author_email='peter.claydon@continuumbridge.com',
      py_modules=['spur'],
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
              'spur = spur:main'
           ]
      },
      )
