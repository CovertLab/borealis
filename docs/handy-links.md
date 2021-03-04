# Handy Links

## Google Cloud Platform

* [Google Cloud Platform](https://cloud.google.com/) (GCP) home page.  
  We're using only a few of these services.

* [Cloud Console](https://console.cloud.google.com/home/dashboard) -- web console to
  manage your GCP project components.

  **NOTE:** Open the ☰ menu (pronounced "hamburger") in the top left corner to access
  all the sub-console pages.  
  The relevant sub-consoles are: Compute Engine, Storage, Logging, Container Registry,
  IAM, and Cloud Build.

  **Tip:** Pin the
  [Compute Engine VM instances](https://console.cloud.google.com/compute/instances),
  [Storage Browser](https://console.cloud.google.com/storage/browser), and
  [Logging - Logs Explorer](https://console.cloud.google.com/logs/)
  sub-consoles to the top of the ☰ menu.

  **Tip:** Bookmark a [Logs Explorer query](https://console.cloud.google.com/logs/query;query=resource.labels.instance_id:%22fireworker%22%20severity%3E%3DINFO)
  like this link to the Logs Explorer with a Fireworker query
  `resource.labels.instance_id:"fireworker" severity>=INFO`

* [GCP documentation](https://cloud.google.com/docs): 

  * [GCP Overview](https://cloud.google.com/docs/overview) -- the basic concepts

  * [Enterprise onboarding checklist](https://cloud.google.com/docs/enterprise/onboarding-checklist)
  -- a checklist with expandable details for all the setup that's useful for
  an "enterprise"  
    **NOTE:** For our purposes, you'll at least need **a Google account** and
    **a GCP project** with **billing enabled**. The project does not need to be part
    of an organization.

  * [Google Cloud SDK documentation](https://cloud.google.com/sdk/docs) -- development
  tools including the `gcloud` and `gsutil` command line tools
    * [gcloud command line reference](https://cloud.google.com/sdk/gcloud/reference)
    * [Google Cloud Client Libraries](https://cloud.google.com/sdk/cloud-client-libraries)

  * [Compute Engine documentation](https://cloud.google.com/compute/docs) (GCE) --
  Compute Engine lets you create and run virtual machines on Google infrastructure.  
  (GCP also offers specialized ways to run code including App Engine,
  Cloud Functions, and Cloud Run. Those don't seem sufficiently general purpose
  for our purposes, e.g. tasks that need many GB of RAM and disk space.)

    * [GCE VM Instances](https://console.cloud.google.com/compute/instances) console

  * [Cloud Storage documentation](https://cloud.google.com/storage/docs) (GCS) -- GCP's
  native way to store data.
    * [Cloud Filestore documentation](https://cloud.google.com/filestore/docs) -- NFS
    file servers  
    You can use this if you need full NFS file servers but it costs 10x as much as GCS
    and it's less scalable.

  * [Cloud Build documentation](https://cloud.google.com/cloud-build/docs) -- a
  service that can build your Docker containers

  * [Container Registry documentation](https://cloud.google.com/container-registry/docs)
  -- stores your Docker Images

  * [Cloud IAM](https://cloud.google.com/iam/docs) -- Identity and Access Management
  to manage access permissions for Google Cloud resources

  * [Cloud Billing](https://cloud.google.com/billing/docs)


## Other tools

* [Docker desktop](https://www.docker.com/products/docker-desktop) for building
  and running Docker Container Images on your desktop.
* [gcsfuse](https://github.com/GoogleCloudPlatform/gcsfuse) is a tool for mounting
  GCS buckets onto your computer's file system.
  It's the easiest and most flexible way to access GCS files.
  You'll need to [install it](https://github.com/GoogleCloudPlatform/gcsfuse/blob/master/docs/installing.md)
  and
  [setup to authenticate for gcsfuse](https://github.com/CovertLab/borealis/blob/master/docs/developer-setup.md#setup-to-authenticate-for-gcsfuse).
