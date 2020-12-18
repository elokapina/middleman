# Middleman 

[![#middleman:elokapina.fi](https://img.shields.io/matrix/middleman:elokapina.fi.svg?label=%23middleman%3Aelokapina.fi&server_fqdn=matrix.elokapina.fi)](https://matrix.to/#/#middleman:elokapina.fi) [![docker pulls](https://badgen.net/docker/pulls/elokapinaorg/middleman)](https://hub.docker.com/r/elokapinaorg/middleman) [![License:Apache2](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) [![Built with nio-template](https://img.shields.io/badge/built%20with-nio--template-brightgreen)](https://github.com/anoadragon453/nio-template)

Matrix bot to act as a middleman. Useful as a feedback bot or for support purposes.

![](./demo.gif)

Features:

* Management room to receive messages to the bot
* Replies to messages by replying to them with a `!reply` command and the intended reply
* Sender messages can be configured as anonymous

## Running

Best used with Docker, find [images on Docker Hub](https://hub.docker.com/r/elokapinaorg/middleman).

An example configuration file is provided as `sample.config.yaml`.

Make a copy of that, edit as required and mount it to `/config/config.yaml` on the Docker container.

You'll also need to give the container a folder for storing state. Create a folder, ensure
it's writable by the user the container process is running as and mount it to `/data`.

Example:

```bash
cp sample.config.yaml config.yaml
# Edit config.yaml, see the file for details
mkdir data
docker run -v ${PWD}/config.docker.yaml:/config/config.yaml:ro \
    -v ${PWD}/data:/data --name middleman elokapinaorg/middleman
```

## Usage

The configured management room is the room that all messages Middleman receives in other rooms 
will be relayed to.

Normal discussion can happen in the management room. Only replies prefixed with `!reply` will be relayed
back to the room it came from.

Currently messages relayed between the rooms are limited to plain text. Images and
other non-text messages will not currently be relayed either way.

## Development

If you need help or want to otherwise chat, jump to `#middleman:elokapina.fi`!

### Releasing

* Update `CHANGELOG.md`
* Commit changelog
* Make a tag
* Push the tag
* Make a GitHub release, copy the changelog for the release there
* Build a docker image
  * `docker build -f docker/Dockerfile . -t elokapinaorg/middleman:v<version>`
* Push docker image
* Update topic in `#middleman:elokapina.fi`
* Consider announcing on `#thisweekinmatrix:matrix.org` \o/

## License

Apache2
