"""One-off: learn mode in the Home Assistant layer: coordinator, constants (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"


def edit(name, pairs):
    p = ROOT / name
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{name}: {a[:70]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit("const.py", [
    ('PLATFORMS = ["number", "sensor", "switch"]', 'PLATFORMS = ["number", "select", "sensor", "switch"]'),
    ('PLAN_STATES = ', 'MODES = ["off", "learn"]                       # "switch" follows when the wallbox can be switched (0.6)\nDEFAULT_MODE = "learn"\nWOULD_STATES = ["charge", "pause", "none", "off"]\nPLAN_STATES = '),
])

edit("coordinator.py", [
    ("from .plan import make_plan\n", "from .plan import make_plan\nfrom .shadow import Decision, ShadowLog, decide\n"),
    ("    DEFAULT_CHARGE_MAX, DEFAULT_CHARGE_MIN,", "    DEFAULT_CHARGE_MAX, DEFAULT_CHARGE_MIN, DEFAULT_MODE,"),
    ("    plug_seeding: bool = False               # the recorder history is being read: do not write meanwhile\n",
     "    plug_seeding: bool = False               # the recorder history is being read: do not write meanwhile\n"
     "    mode: str = DEFAULT_MODE                 # \"off\" or \"learn\" (nothing is switched in either)\n"
     "    decision: Decision | None = None         # what would be switched now (learn mode)\n"
     "    shadow: ShadowLog = field(default_factory=ShadowLog)\n"),
    ('        self._plug_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.plugs")\n',
     '        self._plug_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.plugs")\n'
     '        self._shadow_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.shadow")\n'),
    ('        plugs = (await self._plug_store.async_load() or {}).get("vehicles", {})\n',
     '        plugs = (await self._plug_store.async_load() or {}).get("vehicles", {})\n'
     '        shadows = (await self._shadow_store.async_load() or {}).get("vehicles", {})\n'
     '        for v in self.vehicles.values():\n'
     '            v.shadow = ShadowLog(shadows.get(v.sub_id))\n'),
    ("    def _compute(self, v: Vehicle, now: datetime) -> None:\n",
     "    def _compute(self, v: Vehicle, now: datetime) -> None:\n"
     "        self._compute_plan(v, now)\n"
     "        self._shadow_step(v, now)\n\n"
     "    def _shadow_step(self, v: Vehicle, now: datetime) -> None:\n"
     '        """Learn mode: the decision Plugwhen would take now, written down and compared with the real wallbox. Nothing is switched."""\n'
     '        if v.mode != "learn":\n'
     "            v.decision = None\n"
     "            return\n"
     "        v.decision = decide(v.charge_plan, now, v.plugged, v.soc is not None)\n"
     "        charging = self._is_on(v.cfg.get(V_CHARGING)) if v.cfg.get(V_CHARGING) else None\n"
     "        energy = None\n"
     "        wb = v.cfg.get(V_WALLBOX_ENERGY)\n"
     "        if wb:\n"
     "            energy = to_kwh(self._float(wb), self._unit(wb))\n"
     "        if v.shadow.update(now, v.decision, charging, energy):\n"
     "            self._shadow_store.async_delay_save(\n"
     '                lambda: {"vehicles": {x.sub_id: x.shadow.to_dict() for x in self.vehicles.values()}}, 30)\n\n'
     "    def _compute_plan(self, v: Vehicle, now: datetime) -> None:\n"),
])
print("ok")
