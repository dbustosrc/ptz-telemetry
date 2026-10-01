# Changelog

## 0.1.1

- Publish bounded measured destination intervals with optional opaque destination labels for temporal geometry consumers.
- Expose the beginning of the confirmed pair of fresh readings without extrapolating arrival outside that interval.
- Clear observation state when a request is cancelled and retain the last requested destination for bounded recovery consumers.

## 0.1.0

- Adds read-only PTZ position telemetry for compatible Reolink cameras.
- Adds a bounded destination-confirmation action based on consecutive physical
  position readings, with explicit timeout and unavailable results.
