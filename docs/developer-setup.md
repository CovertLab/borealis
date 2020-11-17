# Developer Setup

After someone does the [Team Setup](team-setup.md) steps, each developer can do the
following steps to set up to run FireWorks workflows on Google Cloud Platform.

Also see [Handy Links](handy-links.md).


## Main setup

1. Have the team setup administrator add your account to the project
or do the [Team Setup](team-setup.md) steps and create the project.

1. [Install the development tools](install-tools.md).

1. Use the [Storage Browser](https://console.cloud.google.com/storage/browser) or
the `gsutil` command line tool to create your storage bucket.

   (It's fine to share storage buckets but having each developer create their own
bucket makes it easier to track usage, clean up when a developer leaves the project,
and customize ACLs.)

   **NOTE:** Every storage bucket needs a **globally-unique name**, that is,
   different from every
   other GCS bucket in the world. One technique is to pick an unusual prefix for
   buckets in your project and combine that with your name.
   The bucket-creation command will fail if the bucket name is in use.

   **BEWARE:** Bucket names are publicly visible so don't include login IDs, email
   addresses, project names, project numbers, or personally identifiable
   information (PII).

   Pick:
   * a unique name,
   * the same Region used with Compute Engine
   (run `gcloud info` or `gcloud config list` for info),
   * `Standard` storage class,
   * the default access control.

   **Tip:** Store the bucket name in an environment variable, e.g.
   `export WORKFLOW_STORAGE_ROOT="xyzzy-esther"`, so your team's software can
   determine the bucket to use.

1. Assuming your MongoDB LaunchPad server is running on the port `27017` on
a server named `mongodb`
in the Google Compute Engine zone `us-west1-b`,
you can open an ssh tunnel to it like this
[see the file `setup/example_mongo_ssh.sh` for a richer example]:

   ```shell script
   gcloud compute ssh mongodb --zone=us-west1-b -- \
       -o ExitOnForwardFailure=yes -L 127.0.0.1:27017:localhost:27017
   ```

   (See `setup/example_mongo_ssh.sh` for why this uses the source IPv4 address
   `127.0.0.1` rather than `localhost`.)

   (If you can connect directly to your MongoDB server on the Internet, you
   won't need an ssh tunnel but you will need strong MongoDB login credentials.)

1. Create your `my_launchpad.yaml` file describing how to contact the
MongoDB LaunchPad server. Given an ssh tunnel, FireWorks commands on your
local computer will access it at the tunnel's origin `127.0.0.1:27017` or
`localhost:27017`:

   ```yaml
   host: localhost
   name: noether
   username: null
   password: null
   port: 27017
   strm_lvl: INFO
   ```

   Each developer needs a unique DB `name` (`noether` in this example) within
   the shared MongoDB server. That's an independent LaunchPad scope for
   workflows and their Fireworkers.

   If you're using MongoDB login authentication credentials, put the
   `username` and `password` in this yaml file.

1. Create, initialize, and reset your LaunchPad database using the Fireworks
`lpad` command line utility:

   ```shell script
   lpad reset
   ```

   You can reset it whenever you want to clear out all the workflow tasks.

See [Building Your Docker Image](docker-build.md).


## Setup to authenticate for gcsfuse

If you want to use [gcsfuse](https://github.com/GoogleCloudPlatform/gcsfuse),
you'll need a credentials key file for a Google Cloud service account.
The steps to get one are in the next section.


## If you want to run Fireworker locally

If you want to run a Fireworker locally on your development computer, you'll
need a service account credentials key file to avoid quota warnings and limits.
(You'll also need to install Docker.)

1. **Prerequisite:** The team (administrator) setup
[how-to-install-gce-server.txt](../borealis/setup/how-to-install-gce-server.txt)
must've created the "fireworker" Service Account and granted it at least
these permissions:
    * Logs Writer
    * Storage Object Admin

1. Get a service account credentials key as a json file and append an `export`
statement to your shell `.profile` or `.bash_profile` file:

   ```bash
   PROJECT="$(gcloud config get-value core/project)"
   FIREWORKER_KEY="${HOME}/bin/fireworker.json"
   gcloud iam service-accounts keys create "${FIREWORKER_KEY}" \
       --iam-account "fireworker@${PROJECT}.iam.gserviceaccount.com"
   chmod 400 $GOOGLE_APPLICATION_CREDENTIALS  # owner-only since it contains a private key

   echo "export GOOGLE_APPLICATION_CREDENTIALS=${FIREWORKER_KEY}" >> ~/.profile
   ```

   Then run that `export` command or create a new shell.

1. In a fresh development directory, install Python 3.8, create a Python
virtual environment, and install the borealis-fireworks pip.

1. Create or augment your `my_launchpad.yaml` file:

    ```yaml
    host: localhost
    name: noether
    username: null
    password: null
    port: 27017
    strm_lvl: INFO
    idle_for_rockets: 60
    idle_for_waiters: 90
    ```

The last two fields let you set how long Fireworker will idle (in seconds)
before exiting. Short times are convenient when running Fireworker on your
local computer. In contrast, launching a GCE VM takes around a minute and we
want those Fireworkers to wait a while for new work before exiting.

Fireworker will idle `idle_for_rockets` seconds (default 15 * 60) for any
READY-to-run rockets to appear in the queue or `idle_for_waiters` seconds
(default 60 * 60, >= idle_for_rockets) for WAITING rockets to become READY,
that is for queued rockets that are just waiting on other upstream rockets to
finish.

The `idle_*` fields have defaults so you don't have to add them, but the
defaults are designed for Compute Engine server nodes which take much longer
to start and stop.
