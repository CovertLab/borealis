# Developer Setup

After someone does the [Team Setup](/team-setup.md) steps, each developer can do the
following steps to set up to run FireWorks workflows on Google Cloud Platform.

Also see [Handy Links](handy-links.md).


## Steps

1. Have the team setup administrator add your account to the project
or do the [Team Setup](/team-setup.md) steps and create the project.

1. [Install the dev tools](install-tools.md).

1. Use the [Storage Browser](https://console.cloud.google.com/storage/browser) or
the `gsutil` command line tool to create your storage bucket.

   (It's fine to share storage buckets but having each developer create their own
bucket makes it easier to track usage, clean up when a developer leaves the project,
and customize ACLs.)

   Every bucket needs a globally-unique name.

TODO:
build a Docker image to run,
...


xxxxx to connect to the LaunchPad MongoDB server. Metadata parameters and the
worker's `my_launchpad.yaml` file configure the Fireworker's
MongoDB host, port, DB name, and idle timeout durations. Users can have their own DB names on a shared
MongoDB server, and each user can have multiple DB names -- each an independent
launchpad space for workflows and their Fireworker nodes.
