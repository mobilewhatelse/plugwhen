"""Constants of Plugwhen."""

from datetime import timedelta

DOMAIN = "plugwhen"
PLATFORMS = ["number", "sensor", "switch"]
UPDATE_INTERVAL = timedelta(minutes=5)      # recompute the need from the current state of charge
HISTORY_INTERVAL = timedelta(hours=1)       # read the long-term statistics again
HISTORY_DAYS = 120

SUBENTRY_VEHICLE = "vehicle"

# general options (entry.options): optional connections to other integrations, by entity
O_LOAD = "load_entity"                    # sensor with the expected house load (attributes `hours`, `target_kw`), e.g. of the peak guard
O_AVAIL = "availability_entity"           # sensor of the availability interface (attributes `schema`, `valid_until`, `forecast`)

# vehicle settings (subentry data)
V_NAME = "name"
V_ODOMETER = "odometer_entity"            # sensor, kilometres (miles are converted)
V_SOC = "soc_entity"                      # sensor, state of charge in percent
V_CAPACITY = "capacity_kwh"
V_RESERVE = "reserve_km"                  # start value of the reserve (the number entity can change it later)
V_CONSUMPTION = "consumption_kwh_100"     # kWh per 100 km until the car's own values are known
V_PLUGGED = "plugged_entity"              # optional: on = car is plugged in
V_CHARGING = "charging_entity"            # optional: on = car is charging
V_WALLBOX_ENERGY = "wallbox_energy_entity"  # optional: wallbox energy counter (tells home from away charging)
V_DEPARTURE = "departure_entity"          # optional: time or date-time of the next departure (replaces the learned one)
V_CHARGE_MAX = "charge_kw_max"            # what the wallbox can deliver
V_CHARGE_MIN = "charge_kw_min"            # lowest charging power (1 phase, 6 A = 1.4 kW)
V_NOTIFY = "notify_service"               # optional: e.g. notify.mobile_app_phone
V_NOTIFY_HOUR = "notify_hour"             # the warning is sent from this hour of the evening on

DEFAULT_RESERVE_KM = 100
DEFAULT_CONSUMPTION_100 = 20.0
DEFAULT_CAPACITY_KWH = 60.0
DEFAULT_CHARGE_MAX = 11.0
DEFAULT_CHARGE_MIN = 1.4
DEFAULT_NOTIFY_HOUR = 19

PLAN_STATES = ["planned", "not_needed", "infeasible", "no_departure"]
READINESS_STATES = ["ready", "plug_in", "low", "too_late", "not_reachable"]
