# Developer Setup

After someone does the [Team Setup](team-setup.md) steps, each developer can do the
following steps to set up to run FireWorks workflows on Google Cloud Platform.

Also see [Handy Links](handy-links.md).


## Steps

1. Have the team setup administrator add your account to the project
or do the [Team Setup](team-setup.md) steps and create the project.

1. [Install the development tools](install-tools.md).

1. Use the [Storage Browser](https://console.cloud.google.com/storage/browser) or
the `gsutil` command line tool to create your storage bucket.

   (It's fine to share storage buckets but having each developer create their own
bucket makes it easier to track usage, clean up when a developer leaves the project,
and customize ACLs.)

   **NOTE:** Every bucket needs a globally-unique name, i.e. different from every
   other GCS bucket in the world. One technique is to pick an unusual prefix for
   buckets in your project and combine that with your name.
   The bucket-creation command will fail if the bucket name is in use.

   **BEWARE:** Bucket names are publicly visible so don't include login IDs, email
   addresses, project names, project numbers, or personally identifiable
   information (PII).

   Pick:
   * a unique name,
   * the same Region used with Compute Engine (run `gcloud info` for info),
   * `Standard` storage class,
   * the default access control.

   **Tip:** Store the bucket name in an environment variable, e.g.
   `export WORKFLOW_STORAGE_ROOT="xyzzy-esther"`, so your team's software can
   determine the bucket to use.

1. If you want to run a Fireworker locally on your development computer, you'll
need to get a service account private key.
Without it, you'll hit quota warnings and limits.
(You'll also need to install Docker.)

   1. **Prerequisite:** The team (administrator) setup
   [how-to-install-gce-server.txt](../borealis/setup/how-to-install-gce-server.txt)
   must've created the "fireworker" Service Account and granted it at least
   these permissions:
       * Logs Writer
       * Storage Object Admin

   1. Get a service account private key as a json file and append an `export`
   statement to your shell `.profile` or `.bash_profile` file:

      ```bash
      PROJECT="$(gcloud config get-value core/project)"
      FIREWORKER_KEY="${HOME}/bin/fireworker.json"
      gcloud iam service-accounts keys create "${FIREWORKER_KEY}" \
          --iam-account "fireworker@${PROJECT}.iam.gserviceaccount.com"

      echo "export GOOGLE_APPLICATION_CREDENTIALS=${FIREWORKER_KEY}" >> ~/.profile
      ```

      Then run that `export` command or create a new shell.


TODO:
build a Docker image to run,
...


xxxxx to connect to the LaunchPad MongoDB server. Metadata parameters and the
worker's `my_launchpad.yaml` file configure the Fireworker's
MongoDB host, port, DB name, and idle timeout durations.
 
Each developer should have their own DB name on a shared
MongoDB server, or multiple DB names if desired. Each DB is an independent
LaunchPad space for workflows and Fireworkers.
