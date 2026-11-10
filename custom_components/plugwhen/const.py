"""Constants of Plugwhen."""

from datetime import timedelta

DOMAIN = "plugwhen"
PLATFORMS = ["number", "select", "sensor", "switch"]
UPDATE_INTERVAL = timedelta(minutes=5)      # recompute the need from the current state of charge
HISTORY_INTERVAL = timedelta(hours=1)       # read the long-term statistics again
HISTORY_DAYS = 120

SUBENTRY_VEHICLE = "vehicle"

# general options (entry.options): optional connections to other integrations, by entity
O_WAECHTER = "waechter_entry"             # the quarter-hour peak guard (a config entry): its load forecast is found automatically
O_LOAD = "load_entity"                    # sensor with the expected house load (attributes `hours`, `target_kw`), e.g. of the peak guard
O_AVAIL = "availability_entity"          # sensor of the availability interface (attributes `schema`, `valid_until`, `forecast`)
O_SOLAR = "use_solar_forecast"            # take the solar forecast of the Energy dashboard as available power (default on)
O_SOLAR_DEDUCT = "solar_deduct_kw"        # kW taken off the solar forecast first (house, home battery)
DEFAULT_SOLAR_DEDUCT = 0.5
SOLAR_REFRESH = timedelta(minutes=15)
O_EVCC_URL = "evcc_url"                    # optional: address of evcc (anywhere on the network); empty = the guard's address
O_ROUTE_WAZE = "route_waze"                # kilometres of calendar trips from the Waze travel time integration (sends home and destination to Waze)
O_EVCC_PASSWORD = "evcc_password"          # optional: only if evcc asks for one
O_GRID_ENERGY = "grid_energy_entity"       # grid import energy counter (for the potential calculator); taken from the guard if chosen
O_PRICE_LOW = "price_low"                  # demand charge per kW and year (up to the threshold); taken from the guard if empty
O_PRICE_HIGH = "price_high"                # ... above the threshold
O_PRICE_THRESHOLD = "price_threshold"      # kW, 0 = one price

# vehicle settings (subentry data)
V_NAME = "name"
V_ODOMETER = "odometer_entity"            # sensor, kilometres (miles are converted)
V_SOC = "soc_entity"                      # sensor, state of charge in percent
V_CAPACITY = "capacity_kwh"
V_RESERVE = "reserve_km"                  # start value of the reserve (the number entity can change it later)
V_CONSUMPTION = "consumption_kwh_100"     # kWh per 100 km until the car's own values are known
V_SOC_MAX_AGE = "soc_max_age_h"             # a state of charge older than this (hours) counts as unknown, 0 = no limit
V_PLUGGED = "plugged_entity"              # optional: on = car is plugged in
V_CHARGING = "charging_entity"            # optional: on = car is charging
V_WALLBOX_ENERGY = "wallbox_energy_entity"  # optional: wallbox energy counter (tells home from away charging)
V_DEPARTURE = "departure_entity"          # optional: time or date-time of the next departure (replaces the learned one)
V_CHARGE_MAX = "charge_kw_max"            # what the wallbox can deliver
V_CHARGE_MIN = "charge_kw_min"            # lowest charging power (1 phase, 6 A = 1.4 kW)
V_CHARGE_PREF = "charge_kw_pref"          # preferred lowest power: spread no flatter than this (the car's charger wastes more below)
DEFAULT_CHARGE_PREF = 4.0
CALIBRATE_INTERVAL = timedelta(hours=24)  # learn the house-specific numbers again (quarter add, base load, solar accuracy)
V_NOTIFY = "notify_service"               # optional: e.g. notify.mobile_app_phone
V_CALENDAR = "trip_calendar"               # optional: calendar whose events are trips of this car (start = departure, km in the title or from the location)
V_STOCK = "stock_soc"                      # optional: never plan below this state of charge (a stock for unplanned trips), 0 = off
V_EVCC_VEHICLE = "evcc_vehicle"            # optional: the car's name in evcc (plugged in / charging when no sensor is set)
V_NOTIFY_HOUR = "notify_hour"             # the warning is sent from this hour of the evening on

DEFAULT_SOC_MAX_AGE_H = 12.0
DEFAULT_RESERVE_KM = 100
DEFAULT_CONSUMPTION_100 = 20.0
DEFAULT_CAPACITY_KWH = 60.0
DEFAULT_CHARGE_MAX = 11.0
DEFAULT_CHARGE_MIN = 1.4
DEFAULT_NOTIFY_HOUR = 19

POTENTIAL_DAYS = 90
POTENTIAL_INTERVAL = timedelta(hours=24)
POTENTIAL_FIXED_KW = 4.1                   # "ready by" of the wallbox with 6 A on three phases
POTENTIAL_QUARTER_ADD_KW = 0.7             # how far the house goes above its hourly mean within an hour (measured 0.68 kW)
POTENTIAL_STATES = ["worth_it", "setting_enough", "little", "too_little_data", "no_data"]
MODES = ["off", "learn", "evcc"]               # evcc: the plan is written into evcc (only for a car linked to evcc); "direct" follows
LEARNING_MODES = ("learn", "evcc")               # modes in which Plugwhen writes down what it would switch and compares
DEFAULT_MODE = "learn"
WOULD_STATES = ["charge", "pause", "none", "off"]
LEARNING_STATES = ["learning_helps", "departure_helps", "reserve_enough", "little", "too_little_data"]
PLAN_STATES = ["planned", "not_needed", "infeasible", "no_departure", "unknown_soc"]
READINESS_STATES = ["ready", "plug_in", "low", "too_late", "not_reachable", "unknown"]
