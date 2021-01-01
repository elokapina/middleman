# Changelog

## unreleased

### Added

* Allow configuring mention only rooms. This allows joining Middleman to
  rooms with lots of discussion. Messages in a room in this list will only
  be relayed to the management room if the Middleman user is mentioned in the
  message.

## v0.1.0 - 2020-12-19

Initial version with the following features

* Messages to bot are relayed to management room
* Management room users can reply by replying to the messages prefixing with `!reply`
* Sender messages can be configured as anonymous
* Configurable welcome message when bot is invited to a room
