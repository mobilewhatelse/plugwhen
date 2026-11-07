# Changelog

## 0.6.0 (unreleased) - honest numbers

- **The plan aims at the early departure** (20th percentile of the weekday's first trips) instead of the median: a car that is ready at
  the median departure is late on about half of the early days. The check *Does learning help?* shows both as bars (ready in time:
  plan until the usual departure against plan until the early departure).
- **Preferred lowest charging power** (setting per car, default 4 kW): the rest is spread no flatter than this, because the car's charger
  wastes more energy at very low power; down to the wallbox minimum only if the energy does not fit. Attribute `spread_floor_kw`.
- **House-specific numbers learned instead of set** (daily, defaults until enough data, overridable): charging losses from days with
  home charging only; the deduction from the solar forecast from the night-time base load (the setting is optional now); the
  quarter-hour add of the potential calculator from the 5-minute statistics of the peak guard's grid import (was a fixed 0.7 kW measured
  in one house). Attributes `efficiency`, `efficiency_learned`, `solar_deduct_kw`, `solar_deduct_source`, `quarter_add_kw`.
- **Accuracy of the solar forecast**: predicted against measured solar energy per day (production statistic of the Energy dashboard);
  the median ratio of the last 30 days scales the forecast before the plan uses it (0.5 to 1.5). Attribute `solar_factor`.
- Dashboard: one line under the plan chart says which numbers are learned, set or default.

## 0.5.1 (unreleased) - does the learning help, two charts

- **Sensor "Does learning help?"**: walks through the history of the car day by day (the model only knows the days before each day):
  how many days the range would have been enough with the fixed reserve alone and with the learned value, and how often the departure
  hour was guessed right (within one hour) per weekday. Verdict: *learning helps*, *reserve is enough*, *little difference*, *too little
  data* (fewer than 21 days).
- **Two charts as SVG** (attribute `chart`, shown by a normal markdown card, no custom card): the check above (two bars and one bar per
  weekday) and, in learn mode, plan against reality per day (green = agreed, red = differed). German and English labels.
- Dashboard: card *Does learning help?* with the verdict in plain words and the chart; the learn mode card has its chart.
- **Three more charts** (attribute `chart` / `plug_chart`): the charge plan as a timeline from now to the departure (windows as bars,
  yellow = sun, blue = grid, departure marked), the potential as one bar per way of charging (highest quarter hour, demand charge,
  how often not ready), the plug-in times of the last 14 days as one strip per day.
- **Dashboard cleaned up, graphics first** (user feedback): fewer cards, charts instead of text and tables, one short line where a number
  needs words, settings stay. Left out: range needed and target state of charge (in the status line), the plan tile and text, the
  table of the learned week (the learning check shows it as a chart), explanation texts.

## 0.5.0 (unreleased) - learn mode

- **Mode per car** (select, *Off* or *Learn*, default Learn, the last choice survives a restart) and the sensor **Would switch**:
  in learn mode Plugwhen switches nothing, it works out what it *would* do (charge, pause, no decision, with the reason, until when,
  planned power) and writes it down. Unknown state of charge, a car that is not plugged in, nothing to charge or no departure are never
  decisions; a target that cannot be reached gives *charge* at once.
- **Comparison with reality** (needs the charging entity and/or the wallbox energy counter): per day how long decision and wallbox
  agreed, hours the wallbox charged although Plugwhen would have paused and the energy that came in, and the other way round; journal of
  the last decisions; both kept in a small store (60 days). Gaps longer than 20 minutes (restart, outage) are not attributed.
- Dashboard: card *Learn mode* (decision with reason, comparison of the last 7 days, journal, mode). Documentation: section *Learn mode*.
- Preparation for switching (planned): the log is the evidence on which it can be offered; switching itself is not built yet.

## 0.4.0 (unreleased) - sun first, the rest spread, real plug-in times

- **Sun first, the rest spread** (one logic for every household): the plan takes the expected solar surplus first while the
  car is at home, and spreads what is left over the parking time with the lowest even grid import (house plus car topped
  up to one level; quiet quarter hours get more). Before, the rest went into the quietest quarter hours at full power and,
  without a load forecast, bunched at the end like a wallbox "ready by" at full current. Without solar the rest is simply
  spread. Quarter hours below the wallbox minimum are dropped and the rest filled again.
- **Solar forecast of the Energy dashboard** (option, default on): any forecast set up there (Forecast.Solar, Solcast,
  Open-Meteo ...) counts as available power, minus a deduction for the house and a home battery (default 0.5 kW). An
  availability entity, if chosen, is used as well (the larger value per quarter hour). Attribute `availability_source`.
- **Plug-in times are written down** (when a plug entity is set): the recorder keeps them only for a few days, so Plugwhen
  stores them itself (about a year; the first start takes what the recorder still has). The readiness sensor shows how the
  car was plugged in over four weeks (`plugging`: plug-ins, nights plugged in, typical plug-in and unplug time). Nobody
  plugs in every day: the warning *plug in* only comes when the reserve would not last.
- **Potential calculator with real parking windows:** with recorded plug-in times the window starts at plugging in and ends
  at unplugging instead of assuming "plugged in from arrival" (`sessions_with_plug_times`).
- **The dashboard comes with the integration:** service `plugwhen.create_dashboard` (administrators) builds it with the
  entities of this installation, all vehicles (headings with the vehicle name when there are several), in German or English
  and in the currency of Home Assistant: next departure, charge plan with where the power comes from, potential with the
  comparison table, plug-in times, settings, learned week. Returned as YAML and shown as a notification; it never writes into
  an existing dashboard. Weekday names follow the language.
- Documentation: detailed README (what it needs, how it plans, plug-in times, warning, potential calculator and how the prices
  are calculated with and without the peak guard, cooperation with the guard, dashboard, entities, limits) and a German guide
  `docs/ANLEITUNG.md`.

## 0.3.0 (unreleased) - potential calculator

- **Potential calculator** (sensor *Potential of spreading the charging* per vehicle, service `plugwhen.calculate_potential`):
  replays the household's own history (grid import counter, wallbox counter, odometer; 90 days) with four ways of charging -
  as it was, spread evenly over the parking time, the wallbox's own "ready by" with 4.1 kW, and the peak guard - and compares the
  monthly peak quarter hour, the demand charge and how often the car would not have been ready. Result: *worth it*, *wallbox
  setting is enough*, *little*, *too little data* or *data missing*. Read only, an estimate; it says which data it used.
- Takes grid counter, prices, limit and measured peaks from the chosen quarter-hour peak guard; for the model check only months
  the guard did not change are used. Without prices only kW are shown.
- The estimate of the car's real quarter-hour power: inside a charging block its hourly mean, at the edges the block's level
  (a car that already charges slowly is not counted as a full-power peak; that would overstate the saving).
- Options: grid import counter, demand charge per kW and year (two levels and a threshold).

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
- **Unknown state of charge** (for example while Home Assistant is starting): no energy to charge, no plan and no warning;
  the sensors say *unknown*.
- Several notify services can be named, separated by commas (one warning to every phone).
- **Connect by choosing the other integration:** in the options you choose the quarter-hour peak guard (a config entry), no entities
  by hand; its load forecast is found automatically. Suggested if exactly one is installed. The guard can do the same with Plugwhen.
  Tested with both integrations in one Home Assistant (16 checks, `tests/install/itest_both.py`).
- **Maximum age of the state of charge** (per vehicle, default 12 h, 0 = no limit; while the car is charging 90 minutes without a new
  value already count): a stale state of charge counts as unknown (no plan, no warning), for cars that send nothing while charging.
  Attributes `soc_stale`, `soc_age_h`.
- Installation test extended to 54 checks (plan, warning once, worse warning, switch off, connections, restart).

## 0.1.0 (unreleased) - show only

- First Home Assistant layer: one config entry, vehicles as subentries (odometer, state of charge, capacity, reserve,
  consumption, optional plug and wallbox energy counter).
- Learns per weekday from the long-term statistics (kilometres, departure hour, share of charging at home).
- Per vehicle: *Energy to charge*, *Range needed*, *Target state of charge*, *Expected departure*, *Learned days*
  (attribute `week`), the number *Reserve* and the switch *Learn kilometres per weekday* (default on).
- Pure-Python modules with tests: `learning`, `history`, `need`, `plan`, `notice` (plan and notice are not wired up yet).
- Installation test in Docker (`tests/install`).
