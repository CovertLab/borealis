#!/usr/bin/env bash
# Run the Borealis Fireworker service.

cd "$HOME/borealis" || { echo "Failure"; exit 1; }

# init pyenv
[[ -f "$HOME/.bash_aliases" ]] && source "$HOME/.bash_aliases"

pip install --upgrade borealis-fireworker
pyenv rehash

fireworker
