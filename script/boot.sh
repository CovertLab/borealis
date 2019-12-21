#!/usr/bin/env bash

cd /home/fireworker/borealis
git pull origin

# TODO: A python program that uses GCE metadata to configure FireWorks, calls
#  fireworks.core.rocket_launcher.rapidfire(), then asks GCE to shut down this VM.
rlaunch rapidfire --timeout 180

/home/fireworker/borealis/script/shutdown.sh
