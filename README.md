<p align="center"><img src="brand/logo.png" alt="Plugwhen" width="420"></p>

# Plugwhen

> **Status: version 0.4.0 in development** (learned week, need, charge plan with sun first and the rest spread, warning,
> recorded plug-in times, potential calculator, ready-made dashboard). It **plans and shows**, it does not control the
> wallbox yet. Private repository. German guide: [docs/ANLEITUNG.md](docs/ANLEITUNG.md).

*Plugwhen*: it works out **when to plug in**, so the car is ready when you leave.

## What is this for?

A Home Assistant integration that makes the electric car **ready at departure with as little grid power as possible and
without load peaks**. Unlike a hand-made schedule it **learns from the car**: how many kilometres it drives per weekday,
when it leaves and **where** it is charged (at home or away). From that it plans the charging until the next departure.

- **For whom:** anyone with an EV and Home Assistant, in any country, with or without solar, with any wallbox and any car
  that Home Assistant can read. It works on its own and can cooperate with the *Viertelstunden-Wächter* (quarter-hour peak
  guard) by choosing it in the settings.
- **What you get:** per car the energy still needed, the target state of charge, the expected departure, a charge plan,
  *Ready for departure* with a warning on the phone, the learned week, how the car is really plugged in, and a calculator that
  shows from your own history what spreading the charging would bring. A ready-made dashboard.
- **What it is not:** no replacement for evcc, no wallbox or car drivers (it reads Home Assistant entities only), no tariff
  comparison, no planning of fast charging on the road.

## What it needs

Only entities, from any integration:

| Entity | Required | Used for |
|---|---|---|
| Odometer (km or miles, with long-term statistics) | yes | learning trips per weekday, departure times |
| State of charge (%) | yes | the energy still needed |
| Plug sensor (car plugged in) | recommended | warning *plug in*, recorded plug-in times |
| Wallbox energy counter | recommended | home or away charging, potential calculator |
| Charging sensor | optional | a state of charge that is old while charging is not believed |
| Departure (time or date-time entity) | optional | replaces the learned departure |
| Notify services (comma list) | optional | the warning (for example two phones) |

Per car you set capacity, reserve (km), consumption until the car's own value is learned, and the **wallbox power** (highest
and lowest, for example 11 or 22 kW and 1.4 kW for one phase at 6 A). Nothing assumes a brand.

## How it plans

1. **Need:** the reserve is the floor of the range the car leaves with; with *Learn kilometres per weekday* on, a weekday's learned
   high value raises it when needed. Target state of charge = state of charge needed for that range; energy = what is missing,
   with charging losses.
2. **Sun first:** while the car is at home, the expected solar surplus is used first. It comes from the **solar forecast of the
   Energy dashboard** (any forecast set up there: Forecast.Solar, Solcast, Open-Meteo ...) minus a deduction for the house and a
   home battery (default 0.5 kW). An *availability* sensor (for example an energy community or a tariff signal, attributes
   `schema`, `valid_until`, `forecast`) can be added; per quarter hour the larger value counts.
3. **The rest spread:** what the sun does not cover is spread over the parking time with the **lowest even grid import**: house and
   car are topped up to one common level, quiet quarter hours get more, busy ones less or nothing, never above the peak target.
   Quarter hours where the car would get less than the wallbox minimum are dropped. Without solar only this step remains.
4. **Honest:** if the target cannot be reached by departure the plan says how much is missing.

Why spreading: a wallbox "ready by" at full power charges late and hard (for example 10 kW from 4 to 6 in the morning) and
sets the monthly peak. Spread over the night the same energy needs 2-3 kW.

## Plug-in times

Home Assistant keeps the history of a plug sensor only for a few days and binary sensors have no long-term statistics, so
Plugwhen writes the plug-in and unplug times down itself (about a year; the first start takes what the recorder still has).
The sensor *Ready for departure* shows them in the attribute `plugging`: plug-ins and nights plugged in over four weeks, the
typical plug-in and unplug time. **Nobody has to plug in every day:** the warning *plug in* only comes when the reserve would
not last until the next departure.

## The warning

*Ready for departure* is `ready`, or what to do: `plug_in`, `low` (plug state unknown), `too_late` (not enough time even at
full power), `not_reachable`, or `unknown` (no fresh state of charge). From a chosen evening hour on, once per departure and
kind, to every notify service set. German and English texts.

## Potential calculator

Sensor *Potential of spreading the charging* and service `plugwhen.calculate_potential` (administrators): it replays your own
history (90 days of grid import counter, wallbox counter and odometer) with four ways of charging and compares the highest
quarter hour per month, the demand charge and how often the car would not have been ready:

| Way of charging | What it means |
|---|---|
| as it was | what really happened |
| peak guard only | as it was, but every quarter hour held below the guard's limit (only when the guard is chosen) |
| wallbox ready-by, low current | the wallbox's own "ready by" at 4.1 kW |
| spread | Plugwhen's way: the energy evenly over the parking window |

The parking window is the real one when plug-in times are recorded, otherwise "plugged in from arrival".
Result: *worth it*, *wallbox setting is enough* (the wallbox's own function gets almost the same without missing the
departure), *little* (less than 1 kW difference), *too little data* (fewer than 14 days or 5 sessions) or *data missing*.

**Prices.** Monthly cost = (peak up to the threshold x price up to the threshold + rest above x price above) / 12; per year =
the average of the months x 12. The peak of a month = the highest hour of the house plus 0.7 kW (how far a quarter hour lies
above its hourly mean) plus the car in that way of charging. The prices come from the Plugwhen settings (demand charge per kW and
year up to the threshold, above it, the threshold; 0 = one price) or, if empty, from the chosen peak guard. **Without any prices
only kW are shown**; the verdict still works because it depends on kW. It is an estimate from hourly values, not a bill.

## Together with the quarter-hour peak guard

Both stay fully usable alone. Choosing the other integration in the settings is enough, no entities have to be picked:

- Plugwhen reads the guard's **load forecast** (expected import and peak target), its grid counter, prices and limit.
- The guard reads Plugwhen's **charge plans** (attribute `windows`) into its forecast and, from version 0.14, shows them on its
  dashboard instead of its own plan.
- **The guard always has the last word:** if a peak would come anyway, it throttles as usual. Plugwhen compares what really
  arrived with its plan and spreads the rest again.

## Dashboard

Service **Create dashboard** (`plugwhen.create_dashboard`, administrators) builds the dashboard with the entities of *your*
installation, all vehicles, in German or English and in your currency: next departure, charge plan (where the power comes from),
potential with the comparison table, plug-in times, settings and the learned week. Only standard cards.
**How to use it:** Developer tools → Actions → *Create dashboard*, copy the YAML from the response or from the notification. Then
Settings → Dashboards → Add dashboard, open it, three dots → Edit → three dots → Raw configuration editor, paste, save. The service
**never writes into an existing dashboard**. Create it again after adding a vehicle.

## Entities per vehicle

| Entity | |
|---|---|
| `sensor` Energy to charge, Range needed, Target state of charge, Expected departure | the need |
| `sensor` Charge plan | `planned`, `not_needed`, `infeasible`, `no_departure`, `unknown_soc`; attributes `windows`, `needed_kwh`, `planned_kwh`, `available_kwh`, `grid_kwh`, `departure`, `ready_at`, `availability_source` |
| `sensor` Ready for departure | see *The warning*; attribute `plugging` |
| `sensor` Potential of spreading the charging | see *Potential calculator* |
| `sensor` Learned days | attribute `week` |
| `number` Reserve, `switch` Learn kilometres per weekday, `switch` Warn when the car will not be ready | settings |

## Limits

It plans and shows; **carrying out the plan (controlling the wallbox) is not built yet**. The plan is based on habits and
forecasts, not a guarantee. Fast charging on the road is not planned, only recognised (the state of charge rises without the
wallbox counter).

The design is in [docs/ZUSCHNITT.md](docs/ZUSCHNITT.md) (German).

## Licence

Dual licence: AGPL-3.0 and a commercial licence, see [LICENSING.md](LICENSING.md).
