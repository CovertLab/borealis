#!/usr/bin/env bash

cd /home/fireworker/borealis
git pull origin

# init pyenv
[[ -f $HOME/.bash_aliases ]] && source $HOME/.bash_aliases

./fireworker.py
