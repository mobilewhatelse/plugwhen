# EV Planner (working title)

> **Status: idea and design, nothing built yet. Private repository.** The name is a placeholder.

## What is this for?

A Home Assistant integration that makes the electric car **ready at departure with as little grid power as possible and
without load peaks**. Unlike a hand-made schedule it **learns from the car**: how many kilometres it drives per weekday,
when it leaves and **where** it is charged (at home or away). From that it plans the charging quarter hours for the next day.

- **For whom:** anyone with an EV and Home Assistant, in any country. It works on its own and can cooperate with the
  *Viertelstunden-Wächter* (quarter-hour peak guard) through entities.
- **What you get (first version, show only):** a weekly plan per car (expected kilometres, departure, charging place),
  the energy needed for tomorrow (a configurable base reserve plus the learned need), a dashboard view.
- **What it is not:** no replacement for evcc, no wallbox drivers (it talks to wallboxes and cars only through Home
  Assistant entities), no tariff comparison.

The design is in [docs/ZUSCHNITT.md](docs/ZUSCHNITT.md) (German).

## Licence

Dual licence: AGPL-3.0 and a commercial licence, see [LICENSING.md](LICENSING.md).
