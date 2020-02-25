# Borealis

Runs [FireWorks workflows](https://materialsproject.github.io/fireworks/) on
[Google Compute Engine](https://cloud.google.com/compute/) (GCE).

See the repo [Borealis](https://github.com/CovertLab/borealis) and the
PyPI page [borealis-fireworks](https://pypi.org/project/borealis-fireworks/).

* _Borealis_ is the git repo name.
* _borealis-fireworks_ is the PyPI package name.
* _borealis-fireworker.service_ is the name of the systemd service.
* _fireworker_ is the recommended process username and home directory name.


## What is it?

[FireWorks](https://materialsproject.github.io/fireworks/) is open-source software
for defining, managing, and executing workflows. Among the many workflow systems,
FireWorks is notably straightforward and adaptable. It's also well tested and
supported.

_Borealis_ lets you spin up as many temporary worker machines as you want on
[Google Compute Engine](https://cloud.google.com/compute/) to run a workflow.
That means pay-per-use and no contention with other workflows.


## What's different about running on Google Compute Engine?

**TL;DR:** Spin up worker machines when you need them, deploy the task code to
workers in Docker Images, and use a different kind of shared storage.

**Worker VMs:** As a _cloud computing_ platform, Google Compute Engine
(GCE) has a vast number of machines available. You can spin up lots of instances
(also called Virtual Machines or VMs), run your workflow, change the code, re-run
some tasks, then let the workers shut down. There's no resource contention with
other workflows and Google will charge you per usage for GCE.

Borealis provides the `fireworker` Python script to run a worker.
`fireworker` gets the worker parameters such as which LaunchPad database to use,
calls the FireWorks library to "rapidfire" launch your FireWorks task ”rockets,”
and shuts down the server (if it's running on GCE).

The `fireworker` command also runs on a laptop for local runs and easier
debugging. To do that, you'll have to install the pip and set up cloud access
control.

You can mix and match GCE FireWorkers with workers running on your local
computer and elsewhere as long as all the workers can connect to your
FireWorks “LaunchPad” server (a MongoDB) and your data store.

`fireworker` also sets up Python logging to go to Google "StackDriver" logging
service (and to the console) so you can watch all your workers running in
real time.

Borealis provides the `ComputeEngine` class and the command line wrapper `gce`
to launch a batch of worker VMs, passing in the needed parameters such as the
connection details for the LaunchPad database. You can generate a workflow
description (DAG) programmatically and call the FireWorks `LaunchPad.add_wf()`
method to upload it to the LaunchPad or run the `lpad add` command line to
upload it. Similarly, you can call the `ComputeEngine.create()` method to
launch a bunch of worker VMs or use the `gce` command line tool.

`ComputeEngine` and `gce` are also useful for immediately deleting a batch of
worker VMs or asking them to quit cleanly between Firetasks, although on their
own they'll shut down after an idle timeout.

`ComputeEngine` and `gce` can also set GCE metadata fields on a batch of
workers, and this is how the `--quit-soon` feature is implemented.

`fireworker` will run any Firetasks that are available on the worker VMs, but how
to put your Firetask code on the workers?

**Docker:** You need to deploy your task payload code to all those GCE VMs.
The payload might be, for example, Python source code but it also needs the right
runtime environment: Python 2.7 or 3.something, Python pip packages, Linux
apt packages, compiled C code, data files, and environment variable settings.
A GCE VM spins up from a “Disk Image” which could have all that preinstalled
(with or without the Python source code) but it'd be a lot of work to keep it
up to date and it'd be easy to get into the situation where you can't tell a
collaborator how to reproduce it.

This is what Docker Images are designed for. You write a `Dockerfile` (or more
than one) containing repeatable instructions to build your payload Image.
You can use Google Cloud Build servers to build the Image and store it in the
Google Container Registry. Images are immutable.

Borealis provides `DockerTask` to run this kind of payload. It's a Firetask that
pulls a named Docker Image, starts up a Docker Container, runs a given shell
command in that Container, and shuts down the container. This also isolates the
payload runtime environment and side effects from the Fireworker and from other
Firetasks, including tasks running from the same Image.

`DockerTask` logs the Container's stdout + stderr to a file and to Python
logging (which `fireworker` connects to StackDriver). `DockerTask` also imposes
a given timeout on the command so it can't loop forever.

To run a Firetask inside the container, include a little Python script `runTask`
in the container. It takes a Firetask name and a JSON dictionary as shell
command args, instantiates the Firetask with those arguments, and calls its
`run_task()` method.

**Google Cloud Storage:** Although you _can_ set up an NFS shared file service for
the workers’ files, the native storage service is _Google Cloud Storage_ (GCS).
GCS costs literally 1/10th as much as NFS service and it scales up better. GCS
lets you archive your files in lower cost tiers designed for infrequent access.
GCS connects to all the other cloud services. E.g., you could use Pub/Sub to
trigger an action on a particular upload to GCS.

But Cloud Storage is not a file system. It's an _object store_ with a lighter
weight protocol to fetch/store/list whole "blobs" (files). It does not support
simultaneous readers and writers, rather, the last "store" to a blob wins. Blob
pathnames can contain `/` characters but GCS doesn't have actual directory objects,
so e.g. there's no way to atomically rename a directory.

`DockerTask` supports Cloud Storage by fetching the task's input files from GCS
then storing its output files to GCS. This requires you to declare the task's
inputs and outputs in the `DockerTask` Parameters. (With that information, a
workflow builder class can compute the task-to-task dependencies.) A pathname
ending with `/` indicates a whole "directory tree" of files.

When storing the task outputs, `DockerTask` creates little blobs with names
ending in `/` acting as directory placeholders. This speeds up tree-oriented
list requests in general. It also means you can run
[gcsfuse](https://github.com/GoogleCloudPlatform/gcsfuse) without the
`--implicit-dirs` flag, resulting in mounted directories that are much faster
to access.


## Team Setup

TODO:
Install & configure dev tools,
create a GCP project,
auth stuff,
install MongoDB on a GCE VM or set up Google-managed MongoDB,
create a Fireworker disk image & image family,
...

See [borealis/setup/how-to-install-gce-server.txt
](borealis/setup/how-to-install-gce-server.txt) for detail instructions to set
up your Compute Engine Disk Image and its "Service Account" for authorization.

xxxxx to connect to the LaunchPad MongoDB server. Metadata parameters and the
worker's `my_launchpad.yaml` file configure the Fireworker's
MongoDB host, port, DB name, and idle timeout durations. Users can have their own DB names on a shared
MongoDB server, and each user can have multiple DB names -- each an independent
launchpad space for workflows and their Fireworker nodes.


## Individual Developer Setup

TODO:
Install & configure dev tools,
make a storage bucket with a globally-unique name,
build a Docker image to run,
...


## Run

TODO


# Change Log

## v0.4.0
* DockerTask:
  * Implement task timeouts.
  * Log the elapsed runtime of the container process.
  * Timestamp the log filename also in the "Pushing outputs to GCS" message and in the local filename (prep for caching output files locally).
  * Raise an exception if a `>` or `>>` capture path parameter names a directory.
* Fireworker:
  * Allow the worker's `my_launchpad.yaml` file to set the `idle_for_waiters` and `idle_for_rockets` parameters. This is good for configuring GCE workers in the Disk Image and off-GCE local workers in the local yaml file.
  * Add a `quit=soon` feature. `gce.py` can set this metadata attribute to ask Fireworkers to quit gracefully between rockets.

## v0.3.3
* Timestamp the captured log files to keep them all from multiple runs and so `ls -l` sorts in time order.

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
