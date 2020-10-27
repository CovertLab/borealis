# Install the development tools

Also see [Handy Links](handy-links.md).


## Install the Google Cloud SDK and log in

1. Install Python and Fireworks:

   * Install Python: `pyenv install 3.8.6`
   * Install a Python virtual environment manager like `virtualenv`,
     `pyenv-virtualenv`, and `pyenv-virtualenvwrapper`; or `venv`
   * Create a Python virtual environment in your project directory, e.g.:
     ```shell script
     pyenv local 3.8.6
     pyenv virtualenv myproject
     pyenv local myproject
     ```
   * Install the Fireworks pips:
     ```shell script
     pip install FireWorks borealis-fireworks
     pyenv rehash
     ```
     This provides command line tools `lpad`, `gce`, and more.

1. [Install the Cloud SDK](https://cloud.google.com/sdk/install) tools.

1. Setup Python for the `gcloud` and `gsutil` tools.

   **Note:** `gsutil -m` is broken in Python 3.8 so use Python 3.6 or 3.7.
   ([gsutil issue #961](https://github.com/GoogleCloudPlatform/gsutil/issues/961).)

   Install Python 3.6 or 3.7 if you don't already have one of them, e.g.
   using `pyenv`:

   ```shell script
   pyenv install 3.7.9
   ```

   Set `$CLOUDSDK_PYTHON` in your shell profile:

   ```shell script
   # Set the Python version for Cloud SDK.
   export CLOUDSDK_PYTHON=$(pyenv shell 3.7.9; pyenv which python)
   ```

   Then open a new shell (or run this `export` command).

1. Test the `gcloud` tool by running the shell command:

   ```shell script
   gcloud info
   ```

   If your shell doesn't find `gcloud`, add lines like the following
   to your shell profile file (`.profile` or `.bash_profile` or whatever),
   adjusting them if you installed the SDK somewhere besides
   `$HOME/dev/google-cloud-sdk/`.

   ```shell script
   # Update PATH for the Google Cloud SDK and gcloud CLI.
   if [ -f '$HOME/dev/google-cloud-sdk/path.bash.inc' ]; then . '$HOME/dev/google-cloud-sdk/path.bash.inc'; fi

   # The next line enables shell command completion for gcloud.
   if [ -f '$HOME/dev/google-cloud-sdk/completion.bash.inc' ]; then . '$HOME/dev/google-cloud-sdk/completion.bash.inc'; fi
   ```

   Then open a new shell and retest the `gcloud info` command.

   (The second part above adds TAB completion to the shell. E.g.
   `gcloud c<TAB>` should show multiple completions.)

1. Run `gcloud components list` to see which components are installed.
If the `docker-credential-gcr` component is not installed
[**TODO:** Do we still need it?], run

       gcloud components install docker-credential-gcr

1. Run:

   ```shell script
   gcloud init
   ```

   * If you've created a project and selected a Compute Engine zone for it,
   enter those names when `gcloud init` asks for a default project and zone.

   This will:
   * initialize `gcloud` and its SDK tools
   * run some diagnostics
   * log in using your user account credentials
   * set configuration defaults

   **Tip:** To change settings later, you can re-run `gcloud init` or run
   specific commands like `gcloud auth login`, `gcloud config set zone us-west1-a`,
   and `gcloud config set project my-favorite-project`.

   **Tip:** Detailed documentation is available via `gcloud help` and the
   [gcloud web reference](https://cloud.google.com/sdk/gcloud/reference/) for
   for [gcloud init](https://cloud.google.com/sdk/gcloud/reference/init) and
   the other gcloud subcommands.

* Afterwards, `gcloud` will occasionally prompt to install updates.
You can do it proactively via the command:

   ```shell script
   gcloud components update
   ```


## Install Docker

If you want to build and test Docker Images locally on your development computer
and/or to run a Fireworker locally, you'll need to install Docker. Without it, you
can still run these steps on Cloud Build and Compute Engine servers.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop).
1. **Optional:** Create a Docker ID [on their website](https://www.docker.com/)
   and Log in to your Docker ID from the Docker client.
1. **Optional:** Set up
   [shell completion for Docker](https://docs.docker.com/docker-for-mac/).

**Tip:** You can exit Docker Desktop when you're not using it.
