# Changelog

## 0.2.0 (unreleased) - plan, warning, connections

- **Charge plan** per vehicle (sensor *Charge plan*): in which quarter hours to charge until the departure. Available power
  (sun, community, tariff) first, then the quietest quarter hours under the peak target. The attributes `windows`,
  `needed_kwh`, `planned_kwh`, `departure`, `target_soc` are the interface other integrations read.
- **Warning that the car will not be ready** (sensor *Ready for departure*, switch, message through any notify service,
  from a chosen evening hour on, once per departure and kind): *plug in*, *too late* (not enough time even at full power),
  *not reachable*, or *too low* when the plug state is unknown. A plan does not silence the warning while the car is not
  plugged in. German and English texts.
- **Connections (options, all optional, Plugwhen also works alone):** the load forecast of the quarter-hour peak guard
  (found automatically and suggested) and a sensor of the *availability interface* (`schema`, `valid_until`, `forecast`).
- **Departure from an entity** (time or date-time) replaces the learned one; wallbox power (max/min), a *charging* entity.
- Reacts at once when the car is plugged in, starts charging or a watched entity changes, not only every five minutes.
- Installation test extended to 43 checks (plan, warning once, worse warning, switch off, connections, restart).

## 0.1.0 (unreleased) - show only

- First Home Assistant layer: one config entry, vehicles as subentries (odometer, state of charge, capacity, reserve,
  consumption, optional plug and wallbox energy counter).
- Learns per weekday from the long-term statistics (kilometres, departure hour, share of charging at home).
- Per vehicle: *Energy to charge*, *Range needed*, *Target state of charge*, *Expected departure*, *Learned days*
  (attribute `week`), the number *Reserve* and the switch *Learn kilometres per weekday* (default on).
- Pure-Python modules with tests: `learning`, `history`, `need`, `plan`, `notice` (plan and notice are not wired up yet).
- Installation test in Docker (`tests/install`).
