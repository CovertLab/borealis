# Borealis

Runs [FireWorks workflows](https://materialsproject.github.io/fireworks/) on
[Google Compute Engine](https://cloud.google.com/compute/) (GCE).

See the repo [Borealis](https://github.com/1fish2/borealis).

* _Borealis_ is the git repo name.
* _fireworker_ is the descriptive name, process username, and home directory name.
* _borealis-fireworker.service_ is the name of the systemd service.


## Background

Instead of a FireWorks worker queue, Borealis launches as many worker nodes as you want
as Google Compute Engine (GCE) VM instances. Metadata parameters and a
`my_launchpad.yaml` file tell the workers what FireWorks LaunchPad to connect
to -- mainly a MongoDB host, port, and DB name. The workers pull and run Fireworks in
"rapidfire" mode and eventually time out and shut themselves down.

Workers should also be able to fetch task input files from Google Cloud Storage (GCS)
and store task output files back to GCS. This avoids needing a shared NFS file service,
which costs 10x as much as GCS storage.

Workers should be able to run their payload tasks in Docker containers to isolate the
worker from the tasks' runtime environments and code.
