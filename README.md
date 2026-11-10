<p align="center"><img src="brand/logo.png" alt="Plugwhen" width="420"></p>

# Plugwhen

> **Status: version 0.7.0 in development** (learned week, need, charge plan with sun first and the rest spread, warning,
> recorded plug-in times, potential calculator, ready-made dashboard, learn mode). It **plans and shows**, it does not control the
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
Result: *worth it*, *setting is enough* (the wallbox's own function gets almost the same without missing the
departure), *little* (less than 1 kW difference), *too little data* (fewer than 14 days or 5 sessions) or *data missing*.

**Prices.** Monthly cost = (peak up to the threshold x price up to the threshold + rest above x price above) / 12; per year =
the average of the months x 12. The peak of a month = the highest hour of the house plus 0.7 kW (how far a quarter hour lies
above its hourly mean) plus the car in that way of charging. The prices come from the Plugwhen settings (demand charge per kW and
year up to the threshold, above it, the threshold; 0 = one price) or, if empty, from the chosen peak guard. **Without any prices
only kW are shown**; the verdict still works because it depends on kW. It is an estimate from hourly values, not a bill.

## Trips from a calendar, stock

- **Calendar with trips** (per car, optional): every event in a calendar of Home Assistant is a trip. Start = departure. Kilometres written
  in the title or description ("Linz 200 km") win; otherwise the route from home to the event's location via the **Waze travel time**
  integration (switch, default off; add the integration once, no account; home and destination go to Waze), there and back unless it says
  "one way". Range at departure = kilometres plus 15 %, at least the reserve. The trip replaces the learned departure of its day.
- **Stock** (per car, minimum state of charge, default off): Plugwhen never plans below it, for unplanned trips.

## With evcc (optional)

- evcc is **optional** and only **read**, through its address (evcc may run anywhere on the network). The address comes from the
  quarter-hour peak guard or is entered in Plugwhen's settings; an evcc on the same machine (add-on) is suggested.
- Odometer and state of charge stay the car's own sensors: Plugwhen cannot calculate without them (evcc usually asks the car only
  while it is plugged in, so it cannot tell the kilometres per day).
- Adding a vehicle offers evcc's cars (the one at a loadpoint first) and fills in name, capacity and the charging power of the loadpoint.
  Plugged in and charging come from evcc as long as no sensor is set for them; a sensor always wins.
- Card **Plan for evcc**: the plan Plugwhen would write into evcc for the **first departure that needs charging** (from the look-ahead,
  so early, e.g. "34 % by Friday 07:00" already on Monday, and adjusted as things change), plus **repeating plans per weekday** from the
  learned week (evcc's `repeatingPlans`, equal times and targets grouped), each next to what evcc has now and whether they are the same. Nothing is written yet (learn mode). A plan set in evcc by hand that differs is shown as
  your own plan, which Plugwhen would never overwrite. **Without evcc** Plugwhen will switch the wallbox itself later; in learn mode
  *Would switch* shows what it would do.
- **Mode "Via evcc"** (per car, next to off and learn, only for a car linked to evcc; kept over a restart; only one ever switches, evcc or later Plugwhen directly, you choose): the plan for the first needed departure is written into evcc and kept up to date;
  only plans Plugwhen wrote itself are changed, a plan set in evcc by hand is never touched.
- Card **Where the data comes from**: for every value whether it is a sensor, evcc or learned, the evcc connection, and what the car
  was set up with (guard, evcc, by hand).
- Several cars: each car has its own plan and its own proposal for evcc. Two cars sharing one wallbox are not planned together yet.

## Together with the quarter-hour peak guard

Both stay fully usable alone. Choosing the other integration in the settings is enough, no entities have to be picked:

- Plugwhen reads the guard's **load forecast** (expected import and peak target), its grid counter, prices and limit. These follow the
  guard: change the limit there and Plugwhen uses it at once.
- **Little to set:** if the guard is installed when Plugwhen is set up, it is connected right away. Adding a vehicle fills in the form
  with what the guard knows about the car and the wallbox (name, state of charge, capacity, charging power, plug sensor, notification, plus
  the odometer and energy counter on the same device). These are copied once, so Plugwhen keeps working if the guard is removed later.
  The departure is not taken over on purpose: a fixed departure time of the wallbox would replace the learned departures.
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

## Honest numbers: what is learned instead of set

Every number that depends on the house or the car has a default that works everywhere, and Plugwhen replaces it with a learned
value as soon as there is enough data (daily, in the background; the dashboard says which one is in use):

| Number | Default | Learned from |
|---|---|---|
| departure the plan aims at | learned median hour | the **early** departure (20th percentile of the weekday's first trips): a car ready at the median is late on about half of the early days |
| preferred lowest charging power | 4 kW (setting per car) | the plan spreads no flatter than this; the car's charger wastes more below a few kW; down to the minimum only if the energy does not fit |
| charging losses | 10 % | days with home charging only: rise of the state of charge x capacity against the wallbox energy (clamped 2 to 25 %) |
| deduction from the solar forecast | 0.5 kW | the night-time base load (median of the hours 1 to 5 of the grid import counter); a setting overrides it |
| quarter-hour add of the potential calculator | 0.7 kW | the 5-minute statistics of the grid import of the chosen peak guard, **for the house alone** (hours in which the wallbox delivered nothing) and **by load level** (quiet, medium, high hours): highest quarter hour above its hour's mean, 80th percentile; a level needs 12 hours, until then 0.7 kW applies there; the hours are collected for good |
| accuracy of the solar forecast | 1.0 | predicted against measured solar energy per day (the Energy dashboard's production statistic), median ratio of the last 30 days, 0.5 to 1.5; the plan uses the scaled forecast |

## Looking ahead: when must I charge at the latest?

The plan reaches the next departure; on the same day it is often too late. The **look-ahead** goes up to **fourteen days and ten
departures** ahead and answers, **for normal behaviour** (the learned trips): *until when does the charge last, and by when must
charging start at the latest?* For every departure it works out the energy that is missing (the car must leave with at least the range
the need asks for, after each trip it has used the expected energy) and the **latest start**: the departure minus the time needed
at the preferred power and at full power.

- **Charge ahead with the sun** (with a solar forecast, e.g. of the Energy dashboard): sun that is left over in an earlier window (for
  example the weekend) is used for the grid energy of a later departure (for example Wednesday), as far as the battery stays below
  80 % and the sun lasts. Example: *Saturday 10 to 13 h, 14 kWh, replaces grid energy before Wednesday 07:00.* The chart *The next
  departures* shows where the energy of each departure comes from: sun in the same window (yellow), sun charged ahead (orange), grid (blue).
- **A heads-up on the evening before:** from the evening hour of the warning on, Plugwhen tells you that **tomorrow** charging will be
  needed (with the latest start) or that charging ahead with the sun pays tomorrow. Once per day and kind. Charging that has to happen
  today is the job of the plug-in warning.
- **Sun windows:** a strip chart for the next five days: grey where the car is expected at home (red tick = departure), yellow where the
  sun delivers power in that time, an **orange frame where plugging in pays** (it covers a need or replaces grid energy before a later
  departure). Below it: *Best: Sat 10:00-13:00, up to 12 kWh.* Sun without a need is shown without a frame. Without a solar forecast the
  chart says so; nothing else in Plugwhen needs a plant. A recommendation only, nothing is switched. The data is in the attribute
  `sun_windows` (and `best_sun_window`) of the look-ahead.
- **Without a solar plant** nothing is pre-charged; the look-ahead then only says what each departure needs from the grid and by when.
- It **recommends only; nothing is switched.** Assumptions are open: the time the car is away follows from the length of the trip (3 h
  plus 1 h per 12 km, 3 to 10 h) until it is learned from the plug-in times; the trips are the typical ones. The solar forecast reaches as
  far as the forecast provider delivers it, beyond that the look-ahead counts on the grid.
- The plan chart shows the latest start at full power as a dashed line.

## When do you charge? (the charging habit)

Sensor **Charging habit** (the share of the energy charged at night, 20 to 7 h, over the last 90 days) and a chart per weekday: the
energy on an average Monday, Tuesday and so on, **during the day (9 to 17 h)**, **at night** and in between. It needs only the
energy counter of the wallbox, no solar plant, and it does not judge (with a night tariff, night charging is what you want). It shows where charging could
move: a weekday with much night charging is where grid energy and peaks come from. Fewer than 28 days of data give *too little data*.

## Does the learning help? (a check on your own history)

Sensor **Does learning help?** (and a card with two charts in the dashboard). It walks through the history of *your* car day by day,
and on each day the model only knows the days before it. Two questions:

- **Would the range have been enough?** With the fixed reserve alone (what a car without learning would keep) and with the reserve lifted
  by what was learned for that weekday (the larger of the reserve and the weekday's 80th percentile). Two bars show the share of days.
- **Would the car have been ready in time?** A plan that finishes at the usual (median) departure against one that finishes at the early
  departure (20th percentile), as two bars and then per weekday for the early plan. Real departures vary, so the useful number is not
  "guessed to the hour" but "ready in time"; that is why the plan aims at the early departure.

Verdict: **learning helps** (at least 5 percentage points more days covered), **helps with departure** (the kilometres hardly help,
but the early plan is ready in time on at least 10 points more days than the median plan), **reserve is enough** (less than 2 points: the reserve alone
does it, the learned value costs nothing but brings little), **little difference**, or **too little data** (fewer than 21 days could be
checked). Days without kilometres are not counted. On the author's car the reserve alone covers about 88 % of the days and with the
learned value about 90 %; the departure hour is what the history helps most with.

The learn mode card has a second chart: per day, the hours in which the plan and the wallbox agreed (green) and the hours in which they
differed (red).

## Learn mode

Per car the select *Mode* has two settings today: **Off** and **Learn** (default; the last choice is kept over a restart). In **Learn**
mode Plugwhen **switches nothing**. It only works out, for every moment, what it *would* do and writes it down:

- the sensor **Would switch** says `charge`, `pause` or `none` (no decision), with the reason (in a planned window, waiting for the next
  window, the plan is done, the target is tight so as much as possible at once, state of charge unknown, car not plugged in, nothing
  needed), when it expects the decision to change, and the planned power;
- a **journal** of the last decisions (only changes are written down);
- a **comparison with reality** per day (kept for 60 days), if you set the *charging* entity and/or the *wallbox energy counter*: how long
  the decision and the wallbox agreed, how many hours the wallbox charged although Plugwhen would have paused, and how much energy came in
  those hours, and the other way round. Example: *would have paused 3 h, but 9 kWh came in*.

Unknown things are never decisions: unknown state of charge, car not plugged in, nothing to charge, no departure give *no decision* and
the wallbox keeps doing what it does. A target that cannot be reached by departure gives `charge` at once (never wait when time is short).

This is the evidence on which switching can be offered later: only when the log shows that Plugwhen's decisions would have been right
for several days. **Switching itself is not built yet.** The dashboard has a *Learn mode* card with the decision, the comparison of the
last 7 days and the journal.

## Entities per vehicle

| Entity | |
|---|---|
| `sensor` Energy to charge, Range needed, Target state of charge, Expected departure | the need |
| `sensor` Charge plan | `planned`, `not_needed`, `infeasible`, `no_departure`, `unknown_soc`; attributes `windows`, `needed_kwh`, `planned_kwh`, `available_kwh`, `grid_kwh`, `departure`, `ready_at`, `availability_source` |
| `sensor` Ready for departure | see *The warning*; attribute `plugging` |
| `sensor` Potential of spreading the charging | see *Potential calculator* |
| `sensor` Learned days | attribute `week` |
| `sensor` Would switch | learn mode: `charge`, `pause`, `none`, `off`; attributes `reason`, `planned_kw`, `until`, `summary`, `journal` |
| `select` Mode | `off` or `learn` |
| `sensor` Charging habit | share of the energy charged at night; attributes `by_weekday`, `day_share_pct`, `weekend_share_pct`, `chart` |
| `sensor` Does learning help? | `learning_helps`, `reserve_enough`, `little`, `too_little_data`; attributes `coverage_reserve_pct`, `coverage_learned_pct`, `departure_right_pct`, `chart` |
| `number` Reserve, `switch` Learn kilometres per weekday, `switch` Warn when the car will not be ready | settings |

## Limits

It plans and shows; **carrying out the plan (controlling the wallbox) is not built yet**. The plan is based on habits and
forecasts, not a guarantee. Fast charging on the road is not planned, only recognised (the state of charge rises without the
wallbox counter).

The design is in [docs/ZUSCHNITT.md](docs/ZUSCHNITT.md) (German).

## Licence

Dual licence: AGPL-3.0 and a commercial licence, see [LICENSING.md](LICENSING.md).
