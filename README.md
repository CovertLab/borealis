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

**[FireWorks](https://materialsproject.github.io/fireworks/)** is open-source
software for defining, managing, and executing workflows. Among the many
workflow systems, FireWorks is exceptionally straightforward, lightweight, and
adaptable. It's well tested and supported. The only shared services it needs are
a MongoDB server and a file store.

**Borealis** lets you spin up as many temporary worker machines as you want in
the [Google Cloud Platform](https://cloud.google.com/docs/) and run your
workflow there. That means pay-per-use and no contention with other workflows.


## What's different about running on Google Compute Engine?

**TL;DR:** Spin up worker machines when you need them, deploy the task code to
workers in Docker Images, and a different kind of shared storage.


**Worker VMs:** As a _cloud computing_ platform, [Google Compute
Engine](https://cloud.google.com/compute/) (GCE) has a vast number of machines
available. You can spin up lots of GCE "instances" (also called Virtual Machines
or VMs) to run your workflow, change the code, re-run some tasks, then let the
workers shut down. There's no resource contention with other workflows and
Google will charge you based on usage.

Borealis provides the `ComputeEngine` class and its command line wrapper `gce`
to create, adjust, and delete groups of worker VMs.

Borealis provides the `fireworker` Python script to run as a worker. It's a
wrapper around FireWorks' `rlaunch` feature.

You can mix Fireworkers running both on and off GCE, as long as all the
workers can connect to your FireWorks "LaunchPad" server and your data store.


**Docker:** You need to deploy your task code to those GCE VMs. The payload
might be Python source code but it also needs the right runtime environment:
Python 2.7 or 3.something, Python pip packages, Linux apt packages, compiled
Cython code, data files, and environment variable settings. A GCE VM starts up
from a "Disk Image" which _could_ have all that preinstalled (with or without
the Python source code) but it'd be hard to keep it up to date and easy to get
into the situation where you can't tell a collaborator how to reproduce it.

This is what Docker Images are designed for. You write a `Dockerfile` containing
repeatable instructions to build your payload Image. You can use Google Cloud
Build servers to build the Image and store it in the Google Container Registry.

Borealis provides a Firetask called `DockerTask` to run just such a payload. It
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


**Google Cloud Storage:** Although you _can_ set up an NFS shared file service
for the workers' files, the native storage service is _Google Cloud Storage_
(GCS). GCS costs literally 1/10th as much as NFS service and it scales up
better. GCS lets you archive your files in yet lower cost tiers designed for
infrequent access. GCS connects to all the other cloud services. E.g., you can
use Pub/Sub to trigger an action on a particular upload to GCS.

But Cloud Storage is not a file system. It's an _object store_ with a lighter
weight protocol to fetch/store/list whole "blobs" (files). It does not support
simultaneous readers and writers, rather, the last "store" to a blob wins. Blob
pathnames can contain `/` characters but GCS doesn't have actual directory objects,
so e.g. there's no way to atomically rename a directory.

`DockerTask` supports Cloud Storage by fetching the task's input files from GCS
and storing its output files to GCS.

Some of the ways to access your GCS data are the `gsutil` command line tool, the
[gcsfuse](https://github.com/GoogleCloudPlatform/gcsfuse) mounting tool, and the
Storage Browser in the Google Cloud Platform web console.


**Logging:** `fireworker` sets up Python logging to write to Google's
"StackDriver" logging service so you can watch all your workers running in real
time.


**Projects:** With Google Cloud Platform, you set up a _project_ for your team
to use. All services, data, and access controls are contained within the
project.


## Borealis Components

**gce:**
Borealis provides the `ComputeEngine` class and its command line wrapper `gce`
to create, tweak, and delete a group of worker VMs. `ComputeEngine` will pass in
the needed launch parameters such as the LaunchPad connection details. After you
generate a workflow description (DAG), call FireWorks' `LaunchPad.add_wf()`
method or run FireWorks' `lpad add` command line tool to upload it to the
LaunchPad. Then you can call the `ComputeEngine.create()` method or the `gce`
command line tool to launch a bunch of worker VMs to run the workflow.

`ComputeEngine` and `gce` are also useful for immediately deleting a batch of
worker VMs or asking them to quit cleanly between Firetasks, although on their
own they'll shut down after an idle timeout.

`ComputeEngine` and `gce` can also set GCE metadata fields on a batch of
workers, and this is used to implement the `--quit-soon` feature.


**fireworker:**
Borealis provides the `fireworker` Python script to run as a worker.
`fireworker` gets the worker launch parameters and calls the FireWorks library
to "rapidfire" launch your FireWorks task "rockets." It handles server shutdown.

`fireworker` sets up Python logging and connects it to Google Cloud's
StackDriver logging so you can watch all your worker machines in real time.

To run `fireworker` on GCE VMs, you'll need to create a GCE Disk Image that
contains Python, the borealis-fireworks pip, and such. See the instructions in
[how-to-install-gce-server.txt](borealis/setup/how-to-install-gce-server.txt).

The `fireworker` command can also run on your local computer for easier
debugging. For that, you'll need to install the `borealis-fireworks` pip and set
up your computer to access the right Google Cloud Project.


**DockerTask:**
The `DockerTask` Firetask will pull a named Docker Image, start up a Docker
Container, run a given shell command in that Container, and stop the container.
This is a reliable way to deploy your payload code packaged up with its runtime
environment to the workers. It also isolates the payload from the Fireworker and
from all other Firetasks.

If you want that shell command inside the container to run a Firetask, include a
little Python script `runTask` that takes a Firetask name and a JSON dictionary
as shell command arguments, instantiates the Firetask with those arguments, and
calls the `run_task()` method.

`DockerTask` supports Google Cloud Storage (GCS) by fetching the task's input
files from GCS, mapping it into the Docker Container, and storing the task's
output files to GCS. This requires you to declare the input and output paths.
(Given this information, a workflow builder can compute the task-to-task
dependencies that FireWorks needs.) Any path ending with a `/` denotes a whole
"tree" of files.

When storing task outputs, `DockerTask` creates blobs with names ending in `/`
which act as "directory placeholders" to speed up tree-oriented list-blob
requests. This means you can run
[gcsfuse](https://github.com/GoogleCloudPlatform/gcsfuse) without using the
`--implicit-dirs` flag, resulting in mounted directories that are 10x faster to
access.

`DockerTask` imposes a given timeout on the shell command so it can't loop
forever.

`DockerTask` logs the Container's stdout and stderr to a file and to Python
logging (which `fireworker` connects to StackDriver).


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
