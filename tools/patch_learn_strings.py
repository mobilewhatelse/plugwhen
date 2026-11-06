"""One-off: texts of learn mode (kept for the record)."""
from pathlib import Path

g = Path(__file__).resolve().parents[1] / "tools" / "gen_strings.py"
s = g.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


rep('sd_name="Create the dashboard",',
    'm_mode="Mode", m_off="Off", m_learn="Learn", s_would="Would switch", w_charge="charge", w_pause="pause", w_none="no decision", w_off="off",\n'
    '    sd_name="Create the dashboard",')
rep('sd_name="Dashboard erstellen",',
    'm_mode="Betriebsart", m_off="Aus", m_learn="Lernen", s_would="Würde schalten", w_charge="laden", w_pause="pausieren", w_none="keine Entscheidung", w_off="aus",\n'
    '    sd_name="Dashboard erstellen",')
rep('                "potential": {"name": L["s_pot"],',
    '                "would_switch": {"name": L["s_would"], "state": {"charge": L["w_charge"], "pause": L["w_pause"], "none": L["w_none"], "off": L["w_off"]}},\n'
    '                "potential": {"name": L["s_pot"],')
rep('"number": {"reserve_km": {"name": L["n_res"]}},',
    '"number": {"reserve_km": {"name": L["n_res"]}},\n'
    '            "select": {"mode": {"name": L["m_mode"], "state": {"off": L["m_off"], "learn": L["m_learn"]}}},')
g.write_text(s, encoding="utf-8")
print("ok")
