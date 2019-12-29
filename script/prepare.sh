#!/usr/bin/env bash
# Set up the machine to run as a Borealis Fireworker.
#
# PREREQUISITE: Use the Google Cloud Console
# https://console.cloud.google.com/iam-admin/serviceaccounts/ to create a
# Service Account "fireworker" and grant it access to your Cloud project.
#
### TODO: This is not tested and not finished! ###
### TODO: Configure auth stuff via GCE VM creation parameters? ###
### TODO: Document how to create the service account key file `.cloud.json`, and
### the scopes for the script that creates this VM instance.
###
### Once fully created, stop the VM and make a GCE disk image from its disk,
###   e.g. called "fireworker-v0" in the disk image family "fireworker".

set -eu

PROJECT="$(gcloud config get-value core/project)"

sudo apt update
sudo apt upgrade
sudo apt autoremove
sudo apt install -y docker.io
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev \
    libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python-openssl git

sudo adduser fireworker
sudo su -l fireworker
cd

curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
{
  echo 'export PATH="$HOME/.pyenv/bin:$PATH"'
  echo 'eval "$(pyenv init -)"'
  echo 'eval "$(pyenv virtualenv-init -)"'; } >> ~/.bash_aliases
source ~/.bash_aliases

git clone https://github.com/CovertLab/borealis.git
cd ~/borealis

pyenv install 3.8.0
pyenv global 3.8.0
pyenv local 3.8.0
pip install --upgrade pip setuptools virtualenv virtualenvwrapper virtualenv-clone wheel
pyenv virtualenv fireworker
pyenv local fireworker
pip install --upgrade pip setuptools virtualenv virtualenvwrapper virtualenv-clone wheel
pip install -r requirements.txt
pyenv rehash

cp example_my_launchpad.yaml my_launchpad.yaml
echo Edit my_launchpad.yaml to access your MongoDB instance and set a logdir to enable Fireworks logging.

gcloud iam service-accounts keys create ~/.cloud.json --iam-account "fireworker@${PROJECT}.iam.gserviceaccount.com"
echo '' >> ~/.profile
echo 'GOOGLE_APPLICATION_CREDENTIALS=/home/fireworker/.cloud.json' >> ~/.profile
gcloud auth activate-service-account fireworker@allen-discovery-center-mcovert.iam.gserviceaccount.com --key-file ~/.cloud.json
gcloud auth configure-docker
cat .cloud.json | docker login -u _json_key --password-stdin https://gcr.io
### TODO: Re-run `gcloud init`? `gcloud auth login`?

echo
echo Follow the instructions in borealis-fireworker.service to set up the systemd service.
