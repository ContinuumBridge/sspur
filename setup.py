#!/usr/bin/env python
from distutils.core import setup
setup(name='sspur',
      version='0.1.7',
      author='Peter Claydon',
      author_email='peter.claydon@continuumbridge.com',
      packages=['bridge', 'apps_dev', 'adaptors_dev'],
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
