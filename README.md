<p align="center"><img src="brand/logo.png" alt="Plugwhen" width="420"></p>

# Plugwhen

A Home Assistant integration that works out **when your electric car should charge**, so it is ready when you
leave, with as little grid power as possible and without a load peak.

> **Deutsch:** [docs/ANLEITUNG.md](docs/ANLEITUNG.md) · **Full manual (English):** [docs/MANUAL.md](docs/MANUAL.md)

## What is this for?

- **Purpose:** Charging usually starts when you get home, at full power. Plugwhen turns that into a plan: the
  sun first, the rest spread over the parking time at low power.
- **For whom:** anyone with an electric car and Home Assistant, with or without solar, with any wallbox and any
  car that Home Assistant can read.
- **What you get:** per car a charge plan until the next departure, a warning on the phone if the car will not
  be ready, and a ready-made dashboard. Plugwhen learns from the car when it leaves and how far it drives.
- **What it is not:** no replacement for evcc, no driver for wallboxes or cars, no tariff comparison.

## How it works

1. **Learn.** From the history of the odometer and the state of charge: when the car leaves on which weekday
   and how far it drives.
2. **Plan.** First the expected solar surplus, then the rest spread evenly, never above your peak limit.
3. **Warn.** In the evening, once per departure: please plug in, otherwise the car will not be ready.
4. **Control, if you want.** At the start Plugwhen only plans and compares. Later it can write its plan into
   evcc or control the wallbox directly.

[How it plans, in detail](docs/MANUAL.md#how-it-plans)

## What you need

- Home Assistant 2026.3 or newer.
- Two sensors of your car: the **odometer** and the **state of charge**.
- Recommended: a plug sensor and the energy counter of the wallbox.

A solar plant is optional. [All entities](docs/MANUAL.md#what-it-needs)

## Works together with

- **[evcc](https://evcc.io):** Plugwhen writes its plan into evcc, evcc charges.
  [Details](docs/MANUAL.md#with-evcc-optional)
- **Viertelstunden-Wächter:** the guard keeps the quarter-hour peak below your limit, Plugwhen plans below it.
  [Details](docs/MANUAL.md#together-with-the-quarter-hour-peak-guard)

## Anonymous data (voluntary)

Off unless you switch it on. Then a weekly usage statistic and, once a day, the trip days: car model, kilometres,
consumption and outdoor temperature, without date, place or id. In return Plugwhen uses the consumption of many cars
of the same model while your car is still learning. Never names, places or passwords.
[What exactly is sent](docs/MANUAL.md#share-anonymous-data-voluntary-and-feedback)

## Safety and liability

In the modes **Via evcc** and **Direct** Plugwhen decides by itself when the car charges. It is a free hobby
project and comes **without any warranty**, as stated in sections 15 and 16 of the AGPL-3.0. It can be wrong,
charge late or not at all. The car may then have less charge at departure than planned.

- Start in **Learn** and choose a controlling mode only when the plans look right to you.
- Check during the first days that it charges as intended, and charge yourself when it is urgent.
- Your installation and your car stay your responsibility. Liability that the law does not allow to be excluded
  (for example for intent or gross negligence) is not affected.

## Licence

Dual licence: AGPL-3.0 and a commercial licence, see [LICENSING.md](LICENSING.md).
