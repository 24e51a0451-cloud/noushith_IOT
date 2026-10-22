# Mobile MQTT registration

The supported protocol is documented in [mqtt_protocol.md](mqtt_protocol.md).

1. Subscribe to `masterhub/mobile/{device_uuid}/register_ack` before registering.
2. Publish a non-retained request to `masterhub/mobile/register` with `device_uuid`,
   `requested_name`, `platform`, `app_version`, `capabilities`, and `timestamp`.
3. Wait for APPROVED, then use the returned `device_id` and `topic_prefix`.
   REJECTED includes an error; a conflicting name returns `Username already taken`.
4. Connect with a retained OFFLINE LWT on the approved `/status` topic, publish
   retained ONLINE status, and send non-retained `/heartbeat` every 10-15 seconds.
5. Receive `/command` and return correlated SUCCESS or FAILED receipts on `/ack`.

PostgreSQL stores the stable hardware UUID and unique lowercase username. A rename
updates the same identity and changes the topic prefix. Registration does not enable
remote control: the phone must publish `remote_state: ACTIVE` and fresh liveness.

Old `bci/...` topics, registration through status, and `/control` replies are removed.
Older APKs must be updated to this protocol before they can communicate with the hub.
