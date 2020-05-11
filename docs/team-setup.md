# Team Setup

These are the setup steps for a team to set up to run FireWorks workflows on
Google Cloud Platform using Borealis.

After this, each developer can follow the [Developer Setup](developer-setup.md) steps.

Also see [Handy Links](handy-links.md).


## Steps

1. You'll need a Google account. It can be in Cloud Identity or G Suite, but
any Gmail account should suffice to create personal projects.

   Expand the
   [Enterprise onboarding checklist](https://cloud.google.com/docs/enterprise/onboarding-checklist)
   items for details.

1. Create your GCP project and enable billing using the
[Cloud Console](https://console.cloud.google.com/home/dashboard).

1. For the other developer on your team, add their accounts to the project and
grant them relevant permissions.

   **TODO:** Which permissions?

1. Pick a [Zone](https://cloud.google.com/compute/docs/regions-zones) for your
Compute Engine VMs and your Cloud Storage buckets.
This choice impacts service prices, network latency, and available services.
See [Cloud Billing](https://cloud.google.com/billing/docs).

1. Follow the [Install the dev tools](install-tools.md) page to install, log in
to the `gcloud` command line tool, and configure your default project and zone.

1. Create a Google Compute Engine VM instance
([GCE console](https://console.cloud.google.com/compute/instances)) and install
MongoDB on it.
Alternatively, set up Google-managed MongoDB service or use an external
instance of MongoDB that's accessible to GCE VMs.

   (Google Cloud offers [Cloud VPN](https://cloud.google.com/vpn/docs) if you need to
connect your on-premises network to Google's network through an IPsec VPN tunnel.

   TODO: Tips on the VM detail choices.

1. Follow the instructions in
[how-to-install-gce-server.txt](../borealis/setup/how-to-install-gce-server.txt)
to create your Fireworker Compute Engine Disk Image and its Service Account.
This Image will have the software needed to instantiate your Fireworker VMs.
