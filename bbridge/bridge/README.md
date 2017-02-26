ContinuumBridge cbridge Source
==============================

This is the source code for cbridge. The recmommended development methodology is as follows:

* git clone this repo in your home directory on a Raspberry pi. Eg: in /home/bridge.
* Create a corresponding /home/bridge/thisbridge directory and put a thisbridge.sh file in that.
* If you're developing apps and adaptors on the same bridge, follow the instructions on readme.io for doing that.
* Copy /etc/init.d/cbridge to /etc/init.d/cbdevel. Edit this to reflect the copies you have made above.
* Do sudo update-rc.d -f cbridge remove to stop cbridge starting automatically on reboot.
* You may like to sudo update-rc.d cbdevel defaults to make your development code start automatically.

Once you have made changes and tested them, proceed as follows:

* add and commit the changed repo.
* Create and push a tag for the version. Eg: git tag -a v0.8.22 -m "A sensible comment", then git push --tags.
* git clone https://github.com/ContinuumBridge/bridge_admin.git into /home/bridge.
* In /home/bridge, type: ./bridge_admin/scripts/makebridge.
* This will create two .tar.gz files and two .md5 files.
* Go to https://github.com/ContinuumBridge/cbridge.
* Click on releases and then edit Development Release.
* Delete the binary files: bridge_clone_inc.md5 and bridge_clone_inc.tar.gz.
* Press Update Release, edit it again and add the new bridge_clone_inc.md5 and bridge_clone_inc.tar.gz that you've just created.
* Run cbridge on a bridge (it could be your development bridge, but remember to stop cbdevel and start cbridge (code in /opt/cbridge).
* On the portal, type upgrade dev.
* Check that the upgrade was successful and made any changes necessary.
* Go back to https://github.com/ContinuumBridge/cbridge and repeat the process you did on the Development Release on the incremental and full releases. For the full release, use bridge_clone.md5 and bridge_clone.tar.gz, not the incremental versions.

That's all there is to it!

