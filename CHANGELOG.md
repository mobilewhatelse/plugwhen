# Changelog

## 0.1.0 (unreleased) - show only

- First Home Assistant layer: one config entry, vehicles as subentries (odometer, state of charge, capacity, reserve,
  consumption, optional plug and wallbox energy counter).
- Learns per weekday from the long-term statistics (kilometres, departure hour, share of charging at home).
- Per vehicle: *Energy to charge*, *Range needed*, *Target state of charge*, *Expected departure*, *Learned days*
  (attribute `week`), the number *Reserve* and the switch *Learn kilometres per weekday* (default on).
- Pure-Python modules with tests: `learning`, `history`, `need`, `plan`, `notice` (plan and notice are not wired up yet).
- Installation test in Docker (`tests/install`).
