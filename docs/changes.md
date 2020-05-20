# Change Log

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
