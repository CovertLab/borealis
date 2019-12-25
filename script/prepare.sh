#!/usr/bin/env bash
# Set up the machine to run as a Borealis worker.
#
### TODO: This is not finished or tested! ###
### TODO: Configure auth stuff via GCE VM creation parameters? ###
### Once fully created, stop the VM and make a GCE disk image from its disk,
###   e.g. called "fireworker-v0" in the disk image family "fireworker".

set -eu

apt update
apt install -y docker.io
apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev \
    libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python-openssl git

adduser fireworker
su -l fireworker
cd

curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
echo 'export PATH="/home/fireworker/.pyenv/bin:$PATH"' >> ~/.bash_aliases
exec $SHELL

git clone https://github.com/1fish2/borealis.git
cd /home/fireworker/borealis

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
echo Edit my_launchpad.yaml to access your MongoDB instance.

gcloud auth activate-service-account sisyphus@allen-discovery-center-mcovert.iam.gserviceaccount.com --key-file ~/.cloud.json
gcloud auth configure-docker
cat .cloud.json | docker login -u _json_key --password-stdin https://gcr.io
