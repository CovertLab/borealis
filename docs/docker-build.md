# Building Your Docker Image

This page is about how to build a Docker Container Image containing your payload
code to run in a `DockerTask`.


### Dockerfile

First write a `Dockerfile` in your project directory. Example:

```Dockerfile
# The Docker Image to start from.
# The ARG lets you pick another base Image but DON'T USE AN ALPINE base since
# its floating point library produces different results; also
# see https://pythonspeed.com/articles/alpine-docker-python/
ARG from=python:3.8.6
FROM ${from}

# Install Linux packages.
# Be sure to run `apt-get update` and `apt-get install` in the same Docker layer
# so the first step can't come from an old Docker cache.
RUN apt-get update \
    && apt-get install -y swig gfortran llvm cmake nano

# Install all the pips in one Docker layer. Don't cache the downloads.
COPY requirements.txt /
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy in the application.
COPY . /app
WORKDIR /app

CMD ["/bin/bash"]
```

It's a good idea to add a `.dockerignore` file that, like your
`.gitignore` file, filters out files from `COPY`ing into the Docker build:

```gitignore
.git*
.gcloudignore
*.pyc
__pycache__
*.so
*.o
```


### Build locally

If Docker Desktop is running, you can locally build an Image tagged,
say `application101`, like this:

```shell script
docker build --tag application101 .
```

You can base it on a different "FROM" Image like this:

```shell script
docker build --build-arg from=python:3.8.1 --tag application101 .
```

but **don't use an Alpine base image** because its floating point library produces
different results. See [Using Alpine can make Python Docker builds 50×
slower](https://pythonspeed.com/articles/alpine-docker-python/) for more reasons.

[These instructions use Python examples but your workflow tasks don't have to
be written in Python.]


### Build on Google Cloud Build and upload to Google Container Registry

Add a `.gcloudignore` file to avoid unneeded files. The easiest way is to
include the `.dockerignore` file by reference:

```gitignore
#!include:.dockerignore
```

Now run:

```shell script
PROJECT="$(gcloud config get-value core/project)"
IMAGE="${USER}-application101"
gcloud builds submit --timeout=1h \
    --tag "gcr.io/${PROJECT}/${IMAGE}" \
    cloud/docker/runtime/
```

Here we put the `USER` name into the `IMAGE` name so each developer in
the project will have their own Images.

The timeout needs to be long enough for all the build steps in your `.Dockerfile`.
That can take a while if your `.Dockerfile` installs scipy from source.


### Metadata
Consider storing metadata in the Image's environment variables and labels to keep
track of the Image's contents. The `docker inspect application101` command will
show this information for the Image `application101`.
Environment variables are also accessible to programs in the container so they
can log it.

Example Dockerfile lines:

```Dockerfile
ARG git_hash=""
ARG git_branch=""
ARG timestamp=""
ENV IMAGE_GIT_HASH="$git_hash" \
	IMAGE_GIT_BRANCH="$git_branch" \
	IMAGE_TIMESTAMP="$timestamp"

LABEL application="The application name" \
    email="our-contact-name@gmail.com" \
    license="https://github.com/us/repo/blob/master/LICENSE.md" \
    organization="our organization" \
    website="https://www.us.org/"
```

Generally we don't put the git repo into the Image so we have to get the
git metadata outside the container and pass it in to `docker build --build-arg`:

```shell script
GIT_HASH=$(git rev-parse HEAD)
GIT_BRANCH=$(git symbolic-ref --short HEAD)
TIMESTAMP=$(date '+%Y%m%d.%H%M%S')

docker build --tag application101 \
  --build-arg git_hash="${GIT_HASH}" \
  --build-arg git_branch="${GIT_BRANCH}" \
  --build-arg timestamp="${TIMESTAMP}" .
```


### Splitting the Image into "runtime" and "application" layers

The application payload code changes much more often than its runtime
environment, so you can speed up your development iterations by splitting
out a base Image containing the runtime.

The runtime environment Image contains software such as Python and libraries.
When building this Image, pretty much the only files to upload are a
`Dockerfile` and `requirements.txt` (listing Python pips to install).
That build will take a while installing apts and pips.

You could use build automation to trigger building a new runtime environment
Image. Preloading this Image onto your Fireworker GCE Disk Image will save
startup time. This image could also be shared by the whole team, with some
added complexity so someone can make an experimental runtime Image without
impacting the rest of the team.

Building the application Image will upload all the application-specific and
developer-specific code such as Python sources, then generate an Image that's
a small layer "FROM" the runtime environment Image. It's quick -- like a few
minutes.

The two `Dockerfile`s have to be in different directories. You'll probably
need a Cloud Build config file.


## Tips

* [Best practices for writing Dockerfiles](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

* [Production-ready Docker packaging](https://pythonspeed.com/docker/)

* Beware that to Docker, `:latest` is merely the default tag. It does not mean the
latest image! If you pull `python:latest` or `python:3.8` or `python:oldest`,
Docker will pull the most recent Image which has that specific name and tag, if
there is one. If you pull `python`, it will pull `python:latest`, if there is one,
because that's the default tag. It will not pull a newer Image that isn't tagged
`latest`.

* If you use the Theano library, you'll need a `Dockerfile` step like the
following to avoid a file permissions problem:

  ```dockerfile
  # Since this build runs as root, set permissions so running the container
  # as some other user with no home dir will work: Theano needs to write into
  # its data dir.
  RUN (umask 000 && mkdir -p /.theano)
  ```

  This is needed because the Docker build steps run as root but `DockerTask`
  runs the process inside the Container with whatever user ID and group ID
  numbers it has as the user outside the Container so `DockerTask` can read and
  delete the files created in the container.
