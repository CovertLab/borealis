# Change Log

## v0.10.0
* Update `startup.sh` and the installation instructions for `pyenv` changes and to install the monitoring agent.
* The gce API and CLI now support `=` and `,` characters in metadata and options such as MongoDB `host` URLs with query parameters `...?retryWrites=true&w=majority`. Using the CLI, change `gce -m KEY=VALUE,KEY2=VAL2` to `gce -m KEY=VALUE -m KEY2=VAL2`.
* Make `example_mongo_ssh.sh` take an optional HOST name arg.
* Update & simplify the installation instructions to use Debian, a smaller disk, newer machine type, and no Ubuntu `snap` steps.

## v0.9.1
* Add dnspython to requirements.txt so pymongo can access server clusters.
* Update other pips in requirements.txt for good measure.

## v0.9.0
* Let the GCE VM metadata override the MongoDB host, including is_uri mode.
* Add gce.py help text for using the `-o network-interface=no-address` option to creates VMs without External IP addresses.
* Update to Fireworks 1.9.7.
* Improve the how-to docs.

## v0.8.0
* Make Python 3.8 the minimum version.
* Require google-cloud-logging>=2.0.0 which changed the API. We recommend other pip updates, esp. FireWorks>=1.9.7 which fixes the `lpad webgui` bug on Python 3.8+ on macOS.
* Don't auto-upgrade the pips when the Fireworker starts up. We need to be able to manually approve pip version upgrades. (`lpad webgui` in FireWorks 1.9.7 requires MongoDB server 3.4+.)
* Detect out-of-memory without relying on Docker's `OOMKilled` status.
* On out-of-memory, log instructions to allocate GCE VMs with more RAM or with swap space.
* Log more Firetask context info like the storage root, workflow name, mongo DB name, host name, the task completion timestamp, and exception details.
* If asked to create more GCE VMs than the max, just limit the number and print a warning rather than raising `AssertionError`. The limit is there to avoid expensive accidents.
* When creating GCE VMs, don't set the `subnet=default` option since that'd interferece with the `-o network-interface=no-address` option to create VMs no External IP address.
  Fireworkers without an External IP are more secure but you'll want to set up Cloud NAT so they can access Docker repositories and Identity Aware Proxy (IAP) so you can ssh in.
* Update the docs since Cloud Console's Logs Explorer replaced its Logs Viewer.
* In `CloudStorage`, add the `list_blobs()` `star=True/False` glob option.
* Use ruamel.yaml's newer API so it'll continue working on ruamel.yaml 0.17+.

## v0.7.0
* Log fireworker & firetask start/end at the INFO rather than WARNING level.
Log task console output and other details at the DEBUG level.
* Don't log console blank lines since the Cloud Log Viewer now handles them strangely.
* Add tips & workarounds to the docs, e.g. use Python 3.7 so `gsutil -m` will work.

## v0.6.6
* Log an Error rather than a Warning on DockerTask failure.

## v0.6.0 - v0.6.5
* Clarify DockerTask exception messages.
* Add `example_mongo_ssh.sh`.
* More documentation progress.
* Refine CLI help text.
* Patch `README.md` relative links to form absolute links for the PyPI description.

## v0.5.1
* Fix the `setup.py` link to `changes.md`.
* Documentation progress.

## v0.5.0
* Improved documentation.
* gce.py: More flexible `--metadata` and `--options` CLI args.
* storage.py: Faster directory placeholder creation using the new `if_generation_match=0` API feature.

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
