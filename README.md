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
a MongoDB server (acting as the workflow "LaunchPad") and a file store.

**Borealis** lets you spin up as many temporary worker machines as you want in
the [Google Cloud Platform](https://cloud.google.com/docs/) to run your
workflow. That means pay-per-use and no contention between workflows.


## How does Borealis support workflows on Google Compute Engine?

**TL;DR:** Spin up worker machines when you need them, deploy your task code to
the workers in Docker Images, and store the data in Google Cloud Storage instead
of NFS.


**Worker VMs:** As a _cloud computing_ platform, [Google Compute
Engine](https://cloud.google.com/compute/) (GCE) has a vast number of machines
available. You can spin up lots of GCE "instances" (also called Virtual Machines
or VMs) to run your workflow, change your code, re-run some tasks, then let the
workers time out and shut down. Google will charge you based on usage and
there's no resource contention between workflows.

Borealis provides the `ComputeEngine` class and its command line wrapper `gce`
to create, tweak, and delete groups of worker VMs.

Borealis provides the `fireworker` Python script to run as the top level program
for each worker. It's a wrapper around FireWorks' `rlaunch` feature.

You can run these Fireworkers on and off GCE, or both at the same time, as long
as all the workers can connect to your FireWorks "LaunchPad" server and the
data store.


**Docker:** You need to deploy your "payload" task code to those GCE VMs. If
it's Python source code, it needs a particular runtime environment:
Python 2.7 or 3.something, Python pip packages, Linux apt packages, compiled
Cython code, data files, and environment variable settings. A GCE VM starts up
from a **GCE Disk Image** which _could_ have all that preinstalled (with or
without the Python source code) but it'd be hard to keep it up to date, hard to
share it with your team, and hard to keep track of how to reproduce it.

This is what Docker Images are designed for. You maintain a `Dockerfile` containing
repeatable instructions to build your payload Image, then run `docker` locally
or use the **Google Cloud Build** service to build the Image and store it in the
**Google Container Registry**.

Borealis provides the `DockerTask` Firetask to run just such a payload. It
pulls a named Docker Image, starts up a Docker Container, runs a given shell
command in that Container, and shuts down the Container. Running within Docker
also isolates the task's runtime environment and side effects from other tasks
and the Fireworker.

`DockerTask` logs the Container's stdout + stderr to a file and to Python
logging (which `fireworker` connects to **StackDriver**). `DockerTask` also
imposes a given timeout on the task.



**Google Cloud Storage:** Although you _can_ set up an NFS shared file service
for the workers' files, **Google Cloud Storage** (GCS) is the native storage
service. GCS costs literally 1/10th as much as NFS service and it scales up
better. GCS lets you archive your files in yet lower cost tiers intended for
infrequent access. Pretty much all of Google's cloud services revolve around GCS,
e.g., Pub/Sub can trigger an action on a particular upload to GCS.

But Cloud Storage is not a file system. It's an _object store_ with a lighter
weight protocol to fetch/store/list whole files, called "blobs." It does not
support simultaneous writers, rather, the last "store" of a blob wins. Blob
pathnames can contain `/` characters but GCS doesn't have actual directory objects,
so e.g. there's no way to atomically rename a directory.

`DockerTask` supports Cloud Storage by fetching the task's input files from GCS
and storing its output files to GCS.

You can access your GCS data via the
[gsutil](https://cloud.google.com/storage/docs/gsutil) command line tool, the
[gcsfuse](https://github.com/GoogleCloudPlatform/gcsfuse) mounting tool, and the
[Storage Browser](https://console.cloud.google.com/storage/browser) in the
[Google Cloud Platform web console](https://console.cloud.google.com/home/dashboard).


**Logging:** `fireworker` sets up Python logging to write to Google's
**StackDriver** logging service so you can watch all your workers running in real
time.


**Projects:** With Google Cloud Platform, you set up a _project_ for your team
to use. All services, VMs, data, and access controls are scoped by the project.


## Borealis Components

**gce:**
Borealis provides the `ComputeEngine` class and its command line wrapper `gce`
to create, tweak, and delete a group of worker VMs. `ComputeEngine` will pass in
the needed launch parameters such as connection details to access the LaunchPad
server. After you
generate a workflow description (DAG), call FireWorks' `LaunchPad.add_wf()`
method or run FireWorks' `lpad add` command line tool to upload it to the
LaunchPad. Then you can call the `ComputeEngine.create()` method or the `gce`
command line to launch a bunch of worker VMs to run the workflow.

`ComputeEngine` and `gce` are also useful for immediately deleting a batch of
worker VMs or asking them to quit cleanly between Firetasks, although on their
own they'll shut down after an idle timeout.
The idle timeout duration is longer if there are queued tasks that are
waiting on other tasks to finish.

`ComputeEngine` and `gce` can also set GCE metadata fields on a batch of
workers. This is used to implement the `--quit-soon` feature.


**fireworker:**
Borealis provides the `fireworker` Python script to run as a worker.
`fireworker` gets the worker launch parameters and calls the FireWorks library
to "rapidfire" launch your FireWorks "rockets." It also handles server shutdown.

`fireworker` sets up Python logging and connects it to Google Cloud's
StackDriver logging so you can watch all your worker machines in real time.

To run `fireworker` on GCE VMs, you'll need to create a GCE Disk Image that
contains Python, the borealis-fireworks pip, and such. See the instructions in
[how-to-install-gce-server.txt](borealis/setup/how-to-install-gce-server.txt).

The `fireworker` command can also run on your local computer for easier
debugging. For that, you'll need to install the `borealis-fireworks` pip and set
up your computer to access the right Google Cloud Project.

**TODO:** Document how to set up access to the GCP project.


**DockerTask:**
The `DockerTask` Firetask will pull a named Docker Image, start up a Docker
Container, run a given shell command in that Container, and stop the container.
This is a reliable way to deploy your payload code packaged up with its runtime
environment to the workers. It also isolates the payload from the Fireworker and
from all other Firetasks.

Docker always runs a shell command in the Container. If you want to run a
`Firetask` in the Container, include a little Python script to bridge the gap:
It takes a Firetask name and a JSON dictionary as command line arguments,
instantiates the Firetask with those arguments, and calls the Firetask's
`run_task()` method.

`DockerTask` supports Google Cloud Storage (GCS) by fetching the task's input
files from GCS, mapping it into the Docker Container, and storing the task's
output files to GCS. This requires you to declare the input and output paths.
(With these declarations, a workflow builder can compute the task
interdependencies that FireWorks needs.)
Any path ending with a `/` denotes a directory tree of files.

When storing task outputs, `DockerTask` creates blobs with names ending in `/`
that act as "directory placeholders" to speed up tree-oriented list-blob
requests. This means you can run
[gcsfuse](https://github.com/GoogleCloudPlatform/gcsfuse) without using the
`--implicit-dirs` flag, resulting in mounted directories that run 10x faster.

`DockerTask` imposes a given timeout on the shell command so it can't run
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
