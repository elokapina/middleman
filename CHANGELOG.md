# Changelog

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
