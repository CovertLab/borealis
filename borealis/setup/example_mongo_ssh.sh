#!/usr/bin/env bash
# Open a secure ssh connection to a MongoDB server machine in Google Compute
# Engine (GCE) and tunnel to its MongoDB service port.
#
# COMMAND LINE ARGUMENTS:
#   ARG1 (optional): "bg" to run the ssh command in a background process.
#   ARG2 (optional): The MongoDB host name in GCE to ssh to. Default = "mongodb".
#
# This uses the Google Cloud SDK (https://cloud.google.com/sdk/docs), letting
# its `gcloud` command handle user access control. (Alternatively, you could set
# up your MongoDB service to be accessible on the open Internet and rely on
# MongoDB access control, in which case you won't need an ssh tunnel.)
#
# After you install MongoDB in GCE, copy this file to your project and edit the
# GCE HOST variable to that VM name. Then put `host: localhost` and the
# tunnel's source port $PORT in your my_launchpad.yaml file.
#
# NOTE: For port forwarding, this uses the explicit IPv4 local address 127.0.0.1
# rather than localhost so if the port is in use ssh will fail and exit rather
# than just warning about it and switching to an IPv6 local address, which
# doesn't seem to work for example_my_launchpad.yaml.

set -eu

HOST=${2:-mongodb}
ZONE=$(gcloud config get-value compute/region)
PORT=27017
TUNNEL=127.0.0.1:$PORT:localhost:$PORT

if [ "${1-}" == bg ]
then
    gcloud compute ssh "$HOST" --zone="$ZONE" -- \
        -o ExitOnForwardFailure=yes -L $TUNNEL -nNT &
    ssh_pid="$!"

    echo "ssh port forwarding to $HOST in the background process: pid ${ssh_pid}"
    echo "Do 'kill ${ssh_pid}' to stop it."
else
    gcloud compute ssh "$HOST" --zone="$ZONE" -- \
        -o ExitOnForwardFailure=yes -L $TUNNEL
fi
