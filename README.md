# Borealis

Runs [FireWorks workflows](https://materialsproject.github.io/fireworks/) on
[Google Compute Engine](https://cloud.google.com/compute/) (GCE).

See the repo [Borealis](https://github.com/CovertLab/borealis).

* _Borealis_ is the git repo name.
* _borealis-fireworks_ is the PyPI package name.
* _borealis-fireworker.service_ is the name of the systemd service.
* _fireworker_ is the recommended process username and home directory name.


## Background

You can launch as many Fireworker nodes as you want as Google Compute Engine (GCE) VM
instances, and/or run local workers, as long as they can all connect to the LaunchPad
server running MongoDB. Metadata parameters and the worker's `gce_my_launchpad.yaml`
file (if that file doesn't exist, then `my_launchpad.yaml`) configure the
MongoDB host, port, and DB name. Users can have their own DB names on a shared
MongoDB server, and each user can have multiple DB names -- each an independent
launchpad space for workflows and their Fireworker nodes.

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
more Docker images, and they're isolated from the Fireworker.


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


# Change Log

## v0.3.3
* Timestamp the captured log files to keep them all from multiple runs and `ls`
  sorts in time order.

## v0.3.2 - 2020-02-17
* Add info to the logs.

## v0.3.1 - 2020-02-17
* Python 2 compatibility fixes.
* Explain the `ConnectionError` that arises when `fireworker` can't contact the Docker server.

## v0.3.0 - 2020-02-14
* Move the setup files from `borealis/installation/` to `borealis/setup/`.
* Add a `fireworker --setup` option to print the setup path to simplify the
  steps to copy those files when setting up a server Disk Image.
* Add a `fireworker -l <launchpad_filename>` option for compatibility with
 `lpad`. The default is back to `my_launchpad.yaml`.
* Add a `gce -l <launchpad_filename>` option, like `lpad`, to read the db name,
  username, and password when creating VMs. The default is `my_launchpad.yaml`.

## v0.2.1 - 2020-02-13
* Bug fix in the `gce_my_launchpad.yaml` fallback code.

## v0.2.0 - 2020-02-13
* Read launchpad config info from `gce_my_launchpad.yaml` if possible, falling
  back to `my_launchpad.yaml` for compatibility with previous releases. This
  lets people use one launchpad config file for their GCE workflows and another
  one for their other workflows.
* Improve the server installation steps and augment the `fireworker --help` text
  to display its directory.

## v0.1.1 - 2020-02-13
* Correct the pip name in `startup.sh`.
* Use `print()` instead of `logging` in gce.py so the messages aren't filtered by the log level.
* Refine the installation instructions.

## v0.1.0 - 2020-02-10
* Initial dev build.
