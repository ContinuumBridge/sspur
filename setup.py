#!/usr/bin/env python
from distutils.core import setup
setup(name='sspur',
      version='0.1.5',
      author='Peter Claydon',
      author_email='peter.claydon@continuumbridge.com',
      py_modules=['sspur'],
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
