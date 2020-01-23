#!/usr/bin/env bash
# Set up the machine to run as a Borealis Fireworker.
#
### TODO: This is untested and unfinished! ###
#
# PREREQUISITES:
# * Create a Google Cloud Platform project.
# * In the Google Cloud Platform Console > IAM > Service Accounts
#   https://console.cloud.google.com/iam-admin/serviceaccounts create a
#   Service Account "fireworker" and grant it access to your Cloud project.
# * In the Google Cloud Platform Console > IAM
#   https://console.cloud.google.com/iam-admin/iam grant these permissions to
#   your Compute Engine default service account and to the fireworker service
#   account:
#       Service Account User
#       Compute Instance Admin v1
#       Logs Writer
#       Storage Object Admin  -- [need Storage Admin to delete VMs and disks?]
#       Project Viewer
#       [More broadly: Compute Admin? Storage Admin?]
# * Create a Compute Engine VM instance (to create a Disk Image)
#   https://console.cloud.google.com/compute/instancesAdd
#     Name: fireworker
#     Region & Zone: <where you want to run everything>
#     Machine family/series: N1 n1-standard-1 [or other. You'll be able to use the
#       resulting Disk Image for any machine type you want.]
#     Boot disk: New 200 GB Standard persistent disk, Ubuntu 19.10 (Debian?
#       Not COS) [You can pick a size and resize it later, but changing the OS
#       image requires creating a new VM from scratch. Container-Optimized
#       OS doesn't have a package manager and is not intended to install s/w.]
#     Identity and API access: "Compute Engine default service account" or
#       the "fireworker" service account. [TODO: Which is better practice?]
#     Access scopes: set access for each API [figure out these details]
#       Cloud Debugger Enabled?
#       Compute Engine Read Write?
#       Service Control Enabled
#       Service Management Read Write? [Read Only?]
#       Stackdriver Logging Write Only
#       Stackdriver Monitoring Write Only
#       Stackdriver Trace Write Only
#       Storage Read Write
#   Management > Description: Fireworks worker
#
#   or use a command line similar to this:
#     gcloud beta compute instances create fireworker --description="Fireworks worker" --machine-type=n1-standard-1 --subnet=default --network-tier=PREMIUM --maintenance-policy=MIGRATE --scopes=https://www.googleapis.com/auth/cloud_debugger,https://www.googleapis.com/auth/compute,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/devstorage.read_write --image=ubuntu-1910-eoan-v20200107 --image-project=ubuntu-os-cloud --boot-disk-size=200GB --boot-disk-type=pd-standard --boot-disk-device-name=fireworker --reservation-affinity=any
#
# Then access it via `gcloud compute ssh fireworker` and do the steps below.
#
### TODO: Remove the scopes from the gce.py script now that the service account has them?

set -eu

sudo apt update
sudo apt upgrade
sudo apt autoremove

sudo apt install -y docker.io
sudo apt install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev \
    libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python-openssl git

### NOTE: This is a good time to `sudo reboot` and ssh to the GCE VM again.

# Reinstall gcloud per https://cloud.google.com/sdk/docs/downloads-interactive
# so it can install the docker-credential-gcr component. (The snap, apt, and yum
# packages don't support that.)
sudo snap remove google-cloud-sdk

curl https://sdk.cloud.google.com > install.sh
sudo mkdir /usr/local/bin/sdk
sudo chgrp ubuntu /usr/local/bin/sdk
sudo chmod g+ws /usr/local/bin/sdk
bash install.sh --install-dir=/usr/local/bin/sdk --disable-prompts

### Add these lines to your .profile file, then source .profile or restart your shell:
#     . /usr/local/bin/sdk/google-cloud-sdk/path.bash.inc
#     . /usr/local/bin/sdk/google-cloud-sdk/completion.bash.inc

echo y | gcloud components install docker-credential-gcr

# Put the SDK's main executables on the path for all users.
sudo ln -s /usr/local/bin/sdk/google-cloud-sdk/bin/gcloud /usr/local/bin/
sudo ln -s /usr/local/bin/sdk/google-cloud-sdk/bin/docker-credential-gcloud /usr/local/bin/
sudo ln -s /usr/local/bin/sdk/google-cloud-sdk/bin/docker-credential-gcr /usr/local/bin/

sudo systemctl enable docker
sudo systemctl start docker

# Add yourself [and all `ubuntu` group members?] to the `docker` group so
# so you won't have to run docker commands under `sudo`.
sudo usermod -aG docker $USER

echo Test docker:
docker --version
docker info
docker pull python:2.7.16

# Set gcloud to authenticate to Docker repositories.
docker-credential-gcr configure-docker


sudo adduser --disabled-password fireworker  # How to suppress promptss for inputs?
sudo usermod -aG docker fireworker
sudo su -l fireworker

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

### TODO?: `docker-credential-gcr configure-docker`? Same as `gcloud auth configure-docker`?

cp example_my_launchpad.yaml my_launchpad.yaml
echo TO DO: Edit my_launchpad.yaml to access your MongoDB instance and
echo optionally set a logdir like /home/fireworker/fw/logs to enable Fireworks logging.

### Set gcloud config parameters?: compute/region, compute/zone, core/project

### TODO: Skip this and let ADC use the default service account?
PROJECT="$(gcloud config get-value core/project)"
mkdir -p "${HOME}/bin/"
FIREWORKER_KEY="${HOME}/bin/fireworker.json"
gcloud iam service-accounts keys create "${FIREWORKER_KEY}" --iam-account "fireworker@${PROJECT}.iam.gserviceaccount.com"
EXPORT="export GOOGLE_APPLICATION_CREDENTIALS=${FIREWORKER_KEY}"
echo "" >> ~/.profile
echo $EXPORT >> ~/.profile
$EXPORT

### TODO: Proper args?
gcloud auth activate-service-account fireworker@${PROJECT}.iam.gserviceaccount.com --key-file "${FIREWORKER_KEY}"
gcloud auth configure-docker
cat "${FIREWORKER_KEY}" | docker login -u _json_key --password-stdin https://gcr.io
### TODO: Re-run `gcloud init`? `gcloud auth login`?

echo
echo TO DO: Follow the instructions in borealis-fireworker.service to set up the systemd service.

echo TO DO: Make a disk image in the disk image family "fireworker".
### Once fully created, stop the VM and make a GCE disk image from its disk,
###   e.g. called "fireworker-v0" in the disk image family "fireworker".
### To make a disk image, run `sudo shutdown -h now`, wait for the GCE VM to stop, then find the
### disk on the Google Compute Engine > Images page, click CREATE IMAGE, and fill in the form.
###     Family: fireworker      # <=== MUST SET THIS ===
