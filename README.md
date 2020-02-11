# Borealis

Runs [FireWorks workflows](https://materialsproject.github.io/fireworks/) on
[Google Compute Engine](https://cloud.google.com/compute/) (GCE).

See the repo [Borealis](https://github.com/CovertLab/borealis).

* _Borealis_ is the git repo name.
* _borealis-fireworker_ is the PyPI package name.
* _borealis-fireworker.service_ is the name of the systemd service.
* _fireworker_ is the recommended process username and home directory name.


## Background

You can launch as many FWorker nodes as you want as Google Compute Engine (GCE) VM
instances, and/or run local workers, as long as they can all connect to the LaunchPad
server running MongoDB. Metadata parameters and the worker's `my_launchpad.yaml` file
supply the MongoDB host, port, and DB name. Users can share a MongoDB server, and each
user can have multiple DB names -- each an independent space for workflows and worker
nodes.

Workers get Fireworks from the LaunchPad, run them in "rapidfire" mode, and eventually
time out and shut themselves down.

Workers can run any Firetasks that are loaded on their disk images, but the best fit
is to run the DockerTask Firetask. DockerTask pulls task input files from
Google Cloud Storage (GCS), runs a payload task as a shell command within a Docker
container, and pushes task output files to GCS.

DockerTask parameters include the Docker image to pull, the command shell tokens to
run in the Docker container, and its input and output files and directories.

DockerTask pulls the inputs from and pushes the outputs to Google Cloud Storage (GCS).
This avoids needing a shared NFS file service which costs 10x as much as GCS storage
and doesn't scale as well.

Using a Docker image lets you bundle up the payload task with its entire runtime,
e.g. Python version, pips, Linux apts, and config files. Your workflow can use one or
more Docker images, and they're isolated from the FWorker.


## Team Setup

TODO:
Install & configure dev tools,
create a GCP project,
auth stuff,
install MongoDB on a GCE VM or set up Google-managed MongoDB,
create a Fireworker disk image & image family,
...


## Individual Developer Setup

TODO:
Install & configure dev tools,
make a storage bucket with a globally-unique name,
build a Docker image to run,
...


## Run

TODO
