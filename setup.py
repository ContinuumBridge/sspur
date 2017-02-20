#!/usr/bin/env python
from distutils.core import setup
setup(name='snappy-spur',
      version='0.1.2',
      author='Peter Claydon',
      author_email='peter.claydon@continuumbridge.com',
      py_modules=['spur'],
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
              'spur=spur:main'
           ]
      },
      )
