#!/usr/bin/env bash
# Run the Borealis Fireworker service.

cd "$HOME/borealis" || { echo "Failure"; exit 1; }

# init pyenv
[[ -f "$HOME/.bash_aliases" ]] && source "$HOME/.bash_aliases"

# [TODO] Auto-upgrade pips per a manually-approved requirements.txt file.
# See borealis/setup/requirements.txt in the Borealis repo or the installed pip.

fireworker
