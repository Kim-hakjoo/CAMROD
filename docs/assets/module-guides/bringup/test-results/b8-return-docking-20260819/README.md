# B8 entry and return integration result

## Result

`PASS` on the 2026-08-19 amd64 ROS 2 simulation with that run's user-provided map.

Observed sequence:

`CRAB_IN -> ROTATE_180 -> UNLOAD_WAIT -> WAIT_RETURN -> ALIGN_RETRACE_YAW -> CRAB_OUT -> DONE`

The same run first completed a `3.73 m` normal Nav2 route with measured maximum
command `|linear.y| = 0.000 m/s`, below the `0.02 m/s` crab selector. It also
measured `/localization/pose` at `20.00 Hz`, wheel odometry at `10 Hz`, and all
configured radar channels at `10 Hz`. The UI manual Return endpoint returned
`site_exit_then_return`: no drop-zone route was published before campsite
`DONE`, and planning began only after the shared lane anchor was recovered. The
controller published both IN/OUT paths; IN recorded 102 lateral samples and OUT
recorded 89 lateral plus 13 straight anchor-correction samples, with no
mixed-axis command. The selected docking telemetry lease created exactly seven
dynamic subscriptions.

## Files

- `b8-entry-return-report.json`: machine-readable `sim_validation_runner` output.
- `result-summary.json`: release-critical values extracted from canonical YAML.
- [Static integration summary](../../../control/test-results/campsite-return-docking-20260819/b8-same-anchor-return.png): canonical controller-owned image of this same run.
- [Phase animation](../../../control/test-results/campsite-return-docking-20260819/b8-entry-return-sequence.gif): canonical controller-owned animation of this same run.
- `SHA256SUMS`: artifact integrity hashes.

This does not claim physical charger, AprilTag depth, radar-noise, or Jetson
resource acceptance. Those remain field checks.
