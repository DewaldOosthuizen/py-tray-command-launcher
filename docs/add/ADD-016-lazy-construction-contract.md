# ADD-016-lazy-construction-contract.md

## Title

Lazy construction of TrayApp feature modules

## Status

Accepted

## Context

`TrayApp.__init__` previously constructed every feature module eagerly. This
delayed first tray display and defeated startup-time goals.

## Decision

Replace eager attributes with `Optional[FeatureModule] = None` fields and
explicit lazy factory accessors. Defer MenuBuilder construction of heavy items
to first tray-icon interaction (`aboutToShow`). Guard cleanup and hotkey
re-registration with `is not None`. No transparent proxy.

## Consequences

Startup time reduced; features still load on demand. AppServices contract
unchanged.
