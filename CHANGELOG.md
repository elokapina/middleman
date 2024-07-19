# Changelog

## unreleased

### Added

* Add config option `mention_only_always_for_named` to allow treating rooms
  that look like named rooms (named or with alias) as mention only automatically.

* Allow editing outbound replies and messages. If a previous `!edit` or `!message`
  command is edited, it will be sent out as an edit replacing the original outbound
  reply or message. ([issue](https://github.com/elokapina/middleman/issues/12))

* When receiving an event the bot cannot decrypt, the event will now be stored for
  later. When keys are received later matching any stored encrypted events, a new attempt
  will be made to decrypt them.

* Add possibility to log to a Matrix room.

* Add config option to replace confirmation messages with reactions. ([issue](https://github.com/elokapina/middleman/issues/9))

* Added support for relaying media. ([issue](https://github.com/elokapina/middleman/pull/26))

### Changed

* Don't send a welcome message to non-dm rooms on join.

* Use `pip-tools` to lock dependencies.

* Refactor Dockerfile and rename main launcher from `middleman-bot` to `main.py`.
  This was done to unify the two Elokapina bots, Bubo and Middleman.

* Exit loudly if we fail to join the management room.

* Notify sender to try again if we fail to relay a message to the management room.

### Fixed

* Ensure case is ignored when looking for display name mentions ([issue](https://github.com/elokapina/middleman/issues/21))

* Better duplicate events cache control in callbacks to avoid ram usage growth over time.

* Management room commands now ignore any reply prefix on the message, allowing fixing command typos.

* Force `charset_normalizer` dependency logs to `warning` level to avoid spammy info
  logs about probing the chaos when the Matrix server is unavailable.

* Fix issue where replying to a previous `!reply` would send the reply to the
  room that the replied to reply originally targeted.

## v0.2.0 - 2021-08-20

### Added

* Allow configuring mention only rooms. This allows joining Middleman to
  rooms with lots of discussion. Messages in a room in this list will only
  be relayed to the management room if the Middleman user is mentioned in the
  message.
  
* Add a new command `!message` to send messages to other rooms. This can only be used
  in the management room. Works with both ID and alias.

* Ensure `m.notice` messages are also relayed (ref #18)
  
### Changed

* Messages relayed into the management room and replies to the senders
  are now standard text messages, not notices.
  
* Messages relayed into the management room now also have the room
  name if there is one.
  
* When joining a room the bot will now also message the management room about the join.

* Don't format relayed messages in italic since it breaks formatting of relayed messages (ref #16)

### Fixed

* Move the welcome message logic from the invite to a member joined event (ref #1)

* Don't resend welcome message on display name change (ref #14)

* Fix some Markdown rendering issues by switching to CommonMark module (ref #11)

* Send error message back to management room on unknown room ID (ref #13)

## v0.1.0 - 2020-12-19

Initial version with the following features

* Messages to bot are relayed to management room
* Management room users can reply by replying to the messages prefixing with `!reply`
* Sender messages can be configured as anonymous
* Configurable welcome message when bot is invited to a room
