"""Constants of Plugwhen."""

from datetime import timedelta

DOMAIN = "plugwhen"
PLATFORMS = ["number", "sensor", "switch"]
UPDATE_INTERVAL = timedelta(minutes=5)      # recompute the need from the current state of charge
HISTORY_INTERVAL = timedelta(hours=1)       # read the long-term statistics again
HISTORY_DAYS = 120

SUBENTRY_VEHICLE = "vehicle"

# vehicle settings (subentry data)
V_NAME = "name"
V_ODOMETER = "odometer_entity"            # sensor, kilometres (miles are converted)
V_SOC = "soc_entity"                      # sensor, state of charge in percent
V_CAPACITY = "capacity_kwh"
V_RESERVE = "reserve_km"                  # start value of the reserve (the number entity can change it later)
V_CONSUMPTION = "consumption_kwh_100"     # kWh per 100 km until the car's own values are known
V_PLUGGED = "plugged_entity"              # optional: on = car is plugged in
V_WALLBOX_ENERGY = "wallbox_energy_entity"  # optional: wallbox energy counter (tells home from away charging)

DEFAULT_RESERVE_KM = 100
DEFAULT_CONSUMPTION_100 = 20.0
DEFAULT_CAPACITY_KWH = 60.0
