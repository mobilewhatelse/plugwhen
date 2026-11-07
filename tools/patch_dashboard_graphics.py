"""One-off: the shipped dashboard, cleaned up and graphics first (kept for the record).

User 07.11.2026: fewer cards, graphics instead of text and tables; settings stay on the dashboard.
"""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen" / "dashboard.py"
s = p.read_text(encoding="utf-8")
a = s.index("def _vehicle_section(")
b = s.index("def build_views(")

NEW = '''def _chart(entity_id: str, attribute: str = "chart") -> str:
    """A markdown card body that shows the SVG chart of an attribute (nothing while it is missing)."""
    return ("{% set c = state_attr('" + entity_id + "', '" + attribute + "') %}"
            "{% if c %}![](data:image/svg+xml;utf8,{{ c | urlencode }}){% endif %}")


def _vehicle_section(ids: dict[str, str], t: dict[str, str], name: str, multi: bool) -> list[dict[str, Any]]:
    """Graphics first, one short line of text where a number needs words; settings stay on the dashboard."""
    need = _s(ids["need_charge"]) + ".attributes"
    status = (
        "{% set at = " + need + " %}"
        f"**{t['soc']}:** {{{{ at.soc if at.soc is not none else '–' }}}} % · "
        f"**{t['plugged']}:** {{{{ '{t['yes']}' if at.plugged else ('{t['no']}' if at.plugged is false else '{t['unknown']}') }}}} · "
        f"**{t['goal']}:** {{{{ at.target_soc }}}} % ({{{{ at.range_km }}}} km)"
        f"{{% if at.reachable is false %}}\\n\\n**{t['unreachable']}**{{% endif %}}"
    )
    pot_line = (
        "{% set a = " + _s(ids["potential"]) + ".attributes %}"
        f"{{% if a.saving_spread_per_year is not none %}}**{t['saving']}:** {{{{ a.saving_spread_per_year | int }}}} {t['per_year']}"
        f"{{% if a.saving_spread_vs_guard_per_year is not none %}}, {{{{ a.saving_spread_vs_guard_per_year | int }}}} {t['vs_guard']}{{% endif %}}{{% endif %}}"
    )
    plugs_line = (
        "{% set p = state_attr('" + ids["readiness"] + "', 'plugging') %}"
        f"{{% if p %}}**{t['now']}:** {{{{ '{t['plugged_in']}' if p.plugged_now else '{t['not_plugged']}' }}}}"
        f"{{% else %}}{t['no_plug']}{{% endif %}}"
    )
    reasons = "{" + ", ".join(f"'{k}': '{t['r_' + k]}'" for k in (
        "in_window", "waiting_for_window", "plan_done", "cannot_reach_target", "unknown_soc", "not_plugged", "not_needed", "no_plan")) + "}"
    would_names = "{" + ", ".join(f"'{k}': '{t['w_' + k]}'" for k in ("charge", "pause", "none", "off")) + "}"
    learn_line = (
        "{% set a = " + _s(ids["would_switch"]) + ".attributes %}{% set st = states('" + ids["would_switch"] + "') %}"
        "{% set rs = " + reasons + " %}{% set wn = " + would_names + " %}"
        f"{{% if st == 'off' %}}{t['lm_off']}{{% else %}}"
        f"**{t['would']}:** {{{{ wn.get(st, st) }}}} · {{{{ rs.get(a.reason, a.reason) }}}}"
        f"{{% if a.until %}} · {t['until_t']} {{{{ (a.until | as_datetime | as_local).strftime('%H:%M') }}}}{{% endif %}}{{% endif %}}"
    )
    lc_id = ids["learning_check"]
    lc_line = (
        "{% set a = " + _s(lc_id) + ".attributes %}{% set st = states('" + lc_id + "') %}"
        f"{{% if st == 'too_little_data' %}}{t['lc_few_a']} {{{{ a.days }}}} {t['lc_few_b']}"
        f"{{% elif st == 'learning_helps' %}}**{t['lc_yes']}** {t['lc_helps_a']} {{{{ a.gain_points }}}} {t['lc_helps_b']}."
        f"{{% elif st == 'reserve_enough' %}}**{t['lc_no']}** {t['lc_enough']}."
        f"{{% else %}}**{t['lc_some']}** {t['lc_helps_a']} {{{{ a.gain_points }}}} {t['lc_helps_b']}.{{% endif %}}"
    )
    head = (lambda h: f"{name} · {h}") if multi else (lambda h: h)
    return [
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["next"]), "icon": "mdi:car-clock"},
            {"type": "tile", "entity": ids["departure"], "name": t["departure"]},
            {"type": "tile", "entity": ids["need_charge"], "name": t["charge"]},
            {"type": "tile", "entity": ids["readiness"], "name": t["ready"]},
            {"type": "markdown", "content": status},
            {"type": "heading", "heading": head(t["plan_h"]), "icon": "mdi:calendar-clock"},
            {"type": "markdown", "content": _chart(ids["charge_plan"])},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["pot_h"]), "icon": "mdi:chart-bell-curve-cumulative"},
            {"type": "tile", "entity": ids["potential"], "name": t["pot"]},
            {"type": "markdown", "content": _chart(ids["potential"])},
            {"type": "markdown", "content": pot_line},
            {"type": "heading", "heading": head(t["plugs_h"]), "icon": "mdi:ev-plug-type2"},
            {"type": "markdown", "content": _chart(ids["readiness"], "plug_chart")},
            {"type": "markdown", "content": plugs_line},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["learn_h"]), "icon": "mdi:school-outline"},
            {"type": "tile", "entity": ids["would_switch"], "name": t["would"]},
            {"type": "entities", "show_header_toggle": False, "entities": [{"entity": ids["mode"], "name": t["mode_name"]}]},
            {"type": "markdown", "content": learn_line},
            {"type": "markdown", "content": _chart(ids["would_switch"])},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["lc_h"]), "icon": "mdi:school-outline"},
            {"type": "tile", "entity": ids["learning_check"], "name": t["lc_tile"]},
            {"type": "markdown", "content": lc_line},
            {"type": "markdown", "content": _chart(lc_id)},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["settings"]), "icon": "mdi:tune"},
            {"type": "entities", "show_header_toggle": False, "entities": [
                {"entity": ids["reserve_km"], "name": t["reserve"]},
                {"entity": ids["learn_km"], "name": t["learn"]},
                {"entity": ids["notice_enabled"], "name": t["notice"]},
            ]},
        ]},
    ]


'''
s = s[:a] + NEW + s[b:]
p.write_text(s, encoding="utf-8")
print("ok")
