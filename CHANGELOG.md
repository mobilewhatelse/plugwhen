# Changelog

## 0.9.0 - 2026-11-14 - trips from a calendar, plans written into evcc, a stock

- **Sharing, new text (version 2):** the weekly statistics now use a random id that changes every month (the fixed id of
  older versions is deleted on the service once), plus a rough class of how long Plugwhen has been running. New: with a wallbox in the mode *Direct*, how fast and how reliably it takes a new value (per model and
  firmware, no names), and per whole day parked the loss of charge (no date, like the trip days). The text names every purpose,
  also summaries passed on to research or partners, always from at least 10 installations. The text is shorter: what is sent,
  never, what for, deleting; the details are on the privacy page. The service keeps the weekly data at most 60 days.
  *Deutsch:* Teilen mit neuem Text (Version 2): Die Wochenstatistik hat jetzt eine zufällige Kennung, die jeden Monat wechselt
  (die feste Kennung früherer Versionen wird am Dienst einmal gelöscht), dazu grob, wie lange Plugwhen schon läuft. Neu: bei einer Wallbox in der Betriebsart *Direkt*, wie schnell und verlässlich sie einen neuen
  Wert übernimmt (je Modell und Firmware, ohne Namen), und je ganzem Standtag der Ladungsverlust (ohne Datum, wie die Fahrtage).
  Der Text nennt alle Zwecke, auch Zusammenfassungen für Forschung oder Partner, immer aus mindestens 10 Installationen. Er ist
  kürzer: gesendet, nie, wofür, löschen; die Einzelheiten stehen auf der Datenschutzseite. Der Dienst behält die Wochendaten
  höchstens 60 Tage.

- **Review before the release (three fixes):** (1) The mode *direct* (and writing the plan into evcc) now also acts in the
  regular run every five minutes, not only when a sensor changes: a sleeping car at night does not report for hours, and the
  window of the plan begins at a time. Without a peak guard the wallbox could miss the start of the window. (2) "The learn mode
  is through" is remembered for good; it fell out after eight other messages and came again every week or two. (3) With a
  wallbox controlled by start/stop buttons, switching to *off* or *learn* now presses stop if Plugwhen had started charging.
  *Deutsch:* Durchsicht vor der Release, drei Korrekturen: (1) Die Betriebsart *Direkt* (und das Schreiben des Plans in evcc)
  handelt jetzt auch im regelmäßigen Lauf alle fünf Minuten, nicht nur, wenn sich ein Sensor ändert – ein schlafendes Auto meldet
  sich nachts stundenlang nicht, das Fenster des Plans beginnt aber zu einer Uhrzeit. (2) „Der Lernmodus ist durch“ wird dauerhaft
  gemerkt und kommt nicht mehr alle ein bis zwei Wochen. (3) Bei einer Wallbox mit Start/Stopp-Knöpfen drückt der Wechsel auf
  *Aus* oder *Lernen* Stopp, wenn Plugwhen das Laden gestartet hatte.
- **Create dashboard answers with the dashboard itself:** the whole response from the developer tools can be pasted into the
  raw configuration editor as it is (before it held the YAML text and the dashboard side by side, which the editor did not take).
- **The heads-up also in the dashboard (from feedback):** the evening notification "charge tomorrow" (with the sun, or when
  charging is needed) was only on the phone. The charge plan sensor now has the attribute `tip` with the same text, and the
  dashboard shows it under the state of the car: from the morning before, and on the day itself until the sun window is over
  ("Today it pays to charge ahead with the sun ..."). Also without a notify service. Create the dashboard again to get the line.
- **A drive home after midnight is not a departure (from feedback):** a first trip between 0:00 and 4:00 belongs to the evening
  before when that weekday mostly starts by day. Two drives home shortly after midnight had set the early departure on Sundays to
  0:00 (and the heads-up said "before the departure Sun 00:00"); 0.8.1 only caught trips already running before midnight. A
  weekday that mostly starts at night (shift work) keeps its night departures. The kilometres still count for the day.
- **Addresses with door, staircase or floor are found (from feedback):** OpenStreetMap does not find "Hauptstraße 5/2/7, Stiege 2,
  1010 Wien" as written. Plugwhen now tries the street without door, staircase and floor, then postcode and town alone (good enough
  for the kilometres). A location found nowhere is not asked again for a week.
- **Consumption per km is learned (it was not before):** from the falls of the state of charge on days with at least 30 km
  (times the capacity), median of the last 20 days; until 3 days are known the typed-in value. Attributes `consumption_source`,
  `consumption_days_with_temp`, `departure_temp_c` on the learned week sensor.
- **Consumption by outdoor temperature (optional):** with an outdoor temperature (own option or taken from the Wächter) each
  day gets its mean temperature. The need for a departure uses the temperature expected then (hourly weather forecast, else the
  sensor's current value within a day): the car's own line once 8 days over 8 K are known (colder never costs less), before that
  a rule of thumb (about 1 % per kelvin below 18 deg C, at most +40 %); a typed-in value only ever gets more. Without a
  temperature nothing changes.

- **Special trips are not learned:** the days of the events in the car's trip calendar are left out of the learned week (a single
  trip to Linz must not raise the kilometres of every Thursday). Attribute `trip_days_skipped` on the learned week sensor.
- **Share anonymous data, voluntary (default off):** asked in the last step of the set-up, afterwards the switch *Share
  anonymous data*. Weekly a usage statistic: a random id, versions, country and language, kinds of devices and the integrations
  their entities come from; switching off requests its deletion. Once a day the **trip days** (days with at least 30 km): car
  model, battery size, km, kWh per km, the day's mean outdoor temperature and the odometer only as a 10,000 km step; for days
  charged only at home the wallbox energy per full charge (charging losses, battery ageing). Without date, place or id (they
  cannot be deleted, they belong to no one). The service files the car under a model of a public list (open data) and says
  which; a car it does not know keeps its own name, and a model added to the list later is filed correctly without an update. Never names, entity ids, places or passwords. **Feedback:** a text field and a button on the device,
  and the action `send_feedback`.
- **Fleet values:** with sharing on, Plugwhen fetches the consumption of many cars of the same model (from 5 cars, else all cars)
  and uses it while the car has no values of its own: own curve, own model, all cars, start values. Attribute `fleet` on the
  learned days sensor; while sharing is off, a quiet card on the tab *Learning* says what the fleet values would bring.
  Sending or fetching never disturbs Plugwhen (service off, no network: everything as before, next try the next day).
- **Odometer and state of charge found through evcc:** evcc reports both for the car at its loadpoint; the car form proposes the
  sensors of Home Assistant that show the same values (the car's own integration before a copy of evcc's value, the state of charge only
  from the same device as the odometer, nothing when it is not unambiguous).
- **Set-up assistant:** two steps instead of an empty page. *What is there* says what was found (the Wächter is linked right away, evcc by
  the Wächter's address or on this machine; an address is asked only if evcc was not found). *Your cars* adds one car after the other,
  each prefilled from the Wächter and evcc; what is needed per car is its odometer and its state of charge.
- **Look-ahead: departures beyond the solar forecast are grey.** A window with daylight after the end of the forecast (the free
  Forecast.Solar reaches until tomorrow) is not "no sun" but "sun not known yet": its bar is grey, the chart says until when the
  forecast reaches, and each day carries `sun_known`, the look-ahead `sun_until`. Night-only windows are never marked.
- **Trips from a calendar** (per car, optional): every event in a calendar of Home Assistant is a trip. Start = departure; kilometres
  written in the title or description ("Linz 200 km") win, otherwise the route from home to the event's location via the Waze travel time
  integration (switch, default off; home and destination go to Waze), there and back unless the event says "einfach"/"one way". The range
  to have is the trip plus 15 %, at least the reserve. A trip replaces the learned departure of its day, in the plan and in the look-ahead.
  All-day events are ignored. Card **Planned trips**.
- **Mode "Via evcc"** (the mode per car gets a third choice, only for a car linked to an evcc car; the chosen mode is kept over a restart): the plan for the first departure that needs charging is written into evcc and kept up
  to date; when it is not needed any more it is removed. Only plans Plugwhen wrote itself are changed: a plan set in evcc by hand is never
  touched. The card says whether it is written. Repeating plans are still only proposed.
- **Stock** (per car, minimum state of charge, default off): Plugwhen never plans below it, so the car is ready for an unplanned trip.
- **Fix: the solar check stayed at 0 days.** Pairing the forecast with what the plant produced ran once a day inside the calibration
  and was skipped whenever an earlier part failed (e.g. the recorder not ready after a restart). It is its own step now, every 15 minutes,
  looks back 7 days, and the charge plan shows `solar_check` (forecasts remembered, days measured, last error).
- **The mode decides who controls, and sets what belongs to it:** "direct" puts the wallbox in its sun mode (e.g. Eco) as the base
  (evcc must only read this wallbox then: "off" in evcc blocks charging, so Plugwhen does not touch evcc's loadpoint); "via evcc" puts the wallbox in its grid mode
  (e.g. Default) and lets evcc regulate; "off"/"learn" give back everything Plugwhen set. Only what Plugwhen set itself is changed back.
- **With evcc, evcc controls; without evcc, Plugwhen:** a car linked to evcc is offered "via evcc", a car without evcc "direct" - never
  both (evcc's "off" blocks charging, so Plugwhen cannot control a wallbox evcc controls).
- **"Direct" can be released early** (setting, for trying it out) before "ready to switch" is green.
- **Locations for Waze are looked up at OpenStreetMap first:** the address search of the Waze integration fails at the moment
  (a place or address gives an error, coordinates work). Plugwhen finds the coordinates at OpenStreetMap (Nominatim, only the destination
  goes there, kept for good) and asks Waze with them. Coordinates in the location are used as they are.
- **A plan in evcc whose time has passed** (evcc keeps it) counts as done, not as your own plan: Plugwhen may replace it. A valid own
  plan is still never touched.
- **Mode "Direct": Plugwhen controls the wallbox**, offered only once "Ready to switch?" is green and the wallbox can be controlled. What it
  does depends on the wallbox, found on its device without settings: (A) a wallbox with its own next-trip mode (e.g. Fronius Wattpilot
  "Next Trip"): Plugwhen fills in departure and energy for a departure within 24 hours and switches to that mode, the wallbox keeps using
  the sun first; (B) a mode select with a sun and a grid mode: grid mode during the planned grid windows; (C) only start/stop: in the windows.
  Only what Plugwhen set is changed back; if you change the wallbox in between, it is left alone. The guard keeps the last word.
- **Ready to switch?** (sensor and card at the top of the overview): a checklist when Plugwhen may switch the wallbox itself (mode
  "direct", later): trips learned on every weekday the car is used, 7 days with a comparison in learn mode, at least 80 % decided the
  same as reality, and with a solar plant 5 days of checked solar forecast; with a rough date. One message per car when it is ready.
- **Dashboard in three tabs:** *Overview* (ready for the next departure, charge plan, planned trips with a calendar view and a short how-to,
  the next departures, plan for evcc), *Learning* (learn mode, does learning help, charging habit, plug-in times), *Details* (potential,
  sun and learned values, where the data comes from, settings). The most important first.

## 0.8.1 (unreleased) - trips over midnight

- **A trip that started the evening before and is still running after midnight is not a departure of the new day.** The learned early
  departure on Sundays was 00:00 in one house (Saturday-night trips home), which also showed up in the proposed evcc plans. The kilometres
  still count for the day.

## 0.8.0 (unreleased) - little to set with the guard

- **Adding a vehicle is filled in from the quarter-hour peak guard** when it knows the car: name, state of charge, capacity, charging
  power (the car's own, else computed from the wallbox currents), plug sensor and notify services, plus the odometer next to the state
  of charge and the energy counter next to the wallbox power (same device, counters win over measurements such as the range). Copied
  once: Plugwhen keeps working without the guard. The departure is not taken over (it would replace the learned departures).
- **evcc as an optional source** (read only, through its API; evcc may run anywhere on the network): address and password come from
  the guard or an own setting, a local evcc (add-on) is suggested. Adding a vehicle offers evcc's cars (the one at a loadpoint first)
  and fills in name, capacity and the charging power of the loadpoint. Plugged in and charging come from evcc when no sensor is set.
  Odometer and state of charge stay the car's own sensors: Plugwhen cannot calculate without them.
- **Card "Plan for evcc"** per car (attribute `evcc_plan` of the charge plan): the plan Plugwhen would write into evcc for the **first
  departure of the look-ahead that needs charging** (written early, e.g. "34 % by Friday 07:00" already on Monday, and following what
  happens: more kilometres raise it, sun in between drops it, then the next needed departure), and **repeating plans per weekday** from
  the learned week (equal times and targets grouped, e.g. "Tue-Fri 07:00 33 %"), each next to what evcc has now (`plan`, `repeatingPlans`), whether both are the same, and that nothing is written yet (learn
  mode). A plan already set in evcc that differs is shown as the user's own plan, which Plugwhen would never overwrite. Without evcc the
  card says that Plugwhen will switch the wallbox itself later (see "Would switch").
- **Card "Where the data comes from"** per car (attribute `sources`): sensor, evcc or learned for each value, the evcc connection,
  whether the plan is only a recommendation, and what the car was set up with.
- **An installed guard is connected when Plugwhen is set up**, so its grid counter, prices, limit and load forecast follow without a setting.

## 0.7.5 (unreleased) - the plan says that it is not executed

- The charge plan has a new attribute **`executed`** (`false`: Plugwhen recommends, it does not switch the wallbox). The quarter-hour
  peak guard reads it: before, a plan "not needed" took the car out of the guard's forecast although the car charged whenever it
  was plugged in (expected peak 2.5 kW, real 9.1 kW in one house).

## 0.7.4 (unreleased) - weak sun

- Sun that never reaches 1 kW in a quarter hour is not counted in the look-ahead any more: a wallbox cannot charge with it. Before,
  a pre-charge could be recommended without a sun window, and the text card *The next departures* broke on it.

## 0.7.3 (unreleased) - any sensor with the right unit

- **Odometer, state of charge, wallbox energy counter and grid energy can be any sensor**, also a template sensor without a device class.
  Before, such sensors were missing from the list (the same problem was reported for the peak guard). Instead of the device class the dialog
  now checks the **unit** when saving (kilometres or miles; percent; Wh, kWh or MWh) and says what to add if it does not fit.
  A sensor without any unit is accepted where Plugwhen assumes one (kilometres, percent, kWh).

## 0.7.2 (unreleased) - learn mode says when it is still learning

- The learn-mode chart *Plan against reality* shows **"Still learning · x of 7 days with a comparison"** instead of bars until seven days
  could be compared (days on which Plugwhen decided to charge or pause). A value only when it says something.
- **Shorter tile names and states** so that nothing is cut off on a phone: *Potential* (was *Potential of spreading the charging*), *Learning useful?*,
  states *Setting is enough* and *Helps with departure*.

## 0.7.1 (unreleased) - sun windows

- **Sun windows:** when does plugging in with the sun make sense? A strip chart for the next five days (car at home, sun available, orange
  frame where charging with the sun covers a need or replaces grid energy later) and the best window as a line below. Attributes
  `sun_windows` and `best_sun_window` in the look-ahead, attribute `sun_chart` at the charge plan; a card in the dashboard under *The next
  departures*. Works without a solar plant (the chart then says there is no forecast).

## 0.7.0 (unreleased) - look ahead, charging habit, house-only add

- **Look-ahead: when must I charge at the latest?** Up to fourteen days and ten departures ahead, for normal behaviour (the learned trips):
  until when the charge lasts (`lasts_until`), the first charging that is needed (`first_need`: day, latest start at the preferred power and at
  full power) and per departure the energy that is missing. Chart *The next departures* (sun in the same window, sun charged ahead, grid).
- **Charge ahead with the sun** (needs a solar forecast, works without a plant: then nothing is pre-charged): sun left over in an earlier window
  (the weekend) covers the grid energy of a later departure (Wednesday), as far as the battery stays below 80 %. A recommendation, nothing is switched.
- **Heads-up on the evening before:** tomorrow charging is needed (with the latest start), or charging ahead with the sun pays tomorrow. Once per
  day and kind, German and English texts. The plan chart shows the latest start at full power as a dashed line.
- **Charging habit:** sensor and chart, the energy per weekday during the day (9 to 17 h), at night (20 to 7 h) and in between, from the energy
  counter of the wallbox only (no solar plant needed, no judgement).
- **The quarter-hour add is measured for the house alone and by load level.** One learned value (0.26 kW in one house) was wrong: quiet hours
  need about 0.1 kW, loaded hours several, and in loaded hours the car's own current steps and the throttling are in the grid import and are modelled
  separately. Hours without wallbox energy are collected for good (the recorder keeps 5-minute values for ten days); a load level with fewer than
  12 hours uses the default 0.7 kW.
- **Learn mode also records the energy delivered although nothing was needed** (for example charging with the sun): `kwh_needless` and
  `needless_h` in the summary, a line on the card. The automatic mode needs that number.

## 0.6.1 (unreleased) - the check says what it knows about the departure

- **The check *Does learning help?* no longer shows "departure guessed right within one hour"** (31 to 46 % in one house, which looked
  like a failure and is the wrong question, because real departures vary). It shows what the plan aims at: ready in time with the plan
  until the usual departure against the early one (52 against 85 % in that house), and per weekday for the early plan.
- **New verdict `departure_helps`** (*Learning helps for the departure*): the kilometres hardly help, but the early plan is ready in
  time on at least 10 points more days than the median plan. The card says it in two plain lines, kilometres and departure.
  Attributes `ready_median_pct`, `ready_early_pct`, `departure_gain_points`, per weekday `ready_early_pct` and `ready_median_pct`.

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
