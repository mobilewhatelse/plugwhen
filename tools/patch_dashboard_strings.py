"""One-off: texts of the create_dashboard service (kept for the record)."""
from pathlib import Path

g = Path(__file__).resolve().parents[1] / "tools" / "gen_strings.py"
s = g.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


rep('sv_days="Days", sv_days_d="How far back (14 to 365 days, default 90).",',
    'sv_days="Days", sv_days_d="How far back (14 to 365 days, default 90).",\n'
    '    sd_name="Create the dashboard", sd_desc="Builds the Plugwhen dashboard with the entities of this installation (all vehicles) and returns it as YAML, also as a notification, to paste into a new dashboard (Edit, Raw configuration editor). Only standard cards. It never changes an existing dashboard. Administrators only.",')
rep('sv_days="Tage", sv_days_d="Wie weit zurück (14 bis 365 Tage, Standard 90).",',
    'sv_days="Tage", sv_days_d="Wie weit zurück (14 bis 365 Tage, Standard 90).",\n'
    '    sd_name="Dashboard erstellen", sd_desc="Baut das Plugwhen-Dashboard mit den Entitäten dieser Installation (alle Fahrzeuge) und gibt es als YAML zurück, auch als Benachrichtigung, zum Einfügen in ein neues Dashboard (Bearbeiten, Raw-Konfigurationseditor). Nur Standardkarten. Ein bestehendes Dashboard wird nie verändert. Nur für Administratoren.",')
rep('''"fields": {"days": {"name": L["sv_days"], "description": L["sv_days_d"]}}}}''',
    '''"fields": {"days": {"name": L["sv_days"], "description": L["sv_days_d"]}}},
                "create_dashboard": {"name": L["sd_name"], "description": L["sd_desc"]}}''')
g.write_text(s, encoding="utf-8")
print("ok")
