#!/usr/bin/env bash

SELF=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/name" -H "Metadata-Flavor: Google")
gcloud compute instances delete "$SELF"
