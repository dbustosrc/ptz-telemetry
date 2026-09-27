# PTZ Telemetry

Read-only physical pan/tilt telemetry for Home Assistant. The first supported
provider is a Reolink camera exposing PTZ position through `reolink-aio`.
Other brands are not yet supported; ONVIF movement indicators are not used as
arrival evidence.

Install this repository as a custom integration in HACS, restart Home Assistant,
then add **PTZ Telemetry** in Devices & Services. Supply a camera host, camera
credentials, telemetry port and channel. The default port is 9000; TCP is
selected by default. Credentials are stored in the Home Assistant config
entry, not in this repository. Each configured camera creates one diagnostic
sensor with the last measured pan, tilt and measurement time. Those attributes
are historical diagnostics, not proof of the camera's current position; use
the action response for arrival decisions.

The `ptz_telemetry.confirm_destination` action is read-only. It returns
`confirmed: true` only after two consecutive fresh readings agree with the
requested coordinates within the selected tolerance. A timeout, lost connection
or superseded request returns `confirmed: false`; callers must not publish an
arrival state in those cases. The action does not command PTZ movement or infer
presence. It reads rapidly only while the action is running.

```yaml
- action: ptz_telemetry.confirm_destination
  data:
    entity_id: sensor.example_ptz_telemetry
    pan: 100
    tilt: 200
    tolerance: 25
    timeout: 12
  response_variable: ptz_confirmation
- condition: template
  value_template: "{{ ptz_confirmation.confirmed }}"
```

Use your camera's actual coordinates; these values are only an example.

Run the deterministic check with `PYTHONPATH=custom_components python -m
unittest discover -s tests`.
