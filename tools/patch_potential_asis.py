"""One-off: a better estimate of the real quarter-hour power of the car (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "custom_components" / "plugwhen" / "potential.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


rep('''def find_sessions(''', '''def car_quarter_kw(car: dict[datetime, float], full_kw: float) -> dict[datetime, float]:
    """Estimated highest quarter-hour power of the car in each hour from hourly energy.

    Inside a block of charging hours the car charged at about its hourly mean (a steady 1.6 kWh per hour is 1.6 kW, not
    6.4 kW). At the edges of a block (and in blocks of one or two hours) the hour was only partly used: the car charged at
    the block's level, at most at full power. Assuming full power everywhere would overstate the peak of a car that
    already charges slowly, and with it the saving."""
    out: dict[datetime, float] = {}
    hours = sorted(t for t, v in car.items() if v > 0.05)
    blocks: list[list[datetime]] = []
    for t in hours:
        if blocks and t - blocks[-1][-1] == HOUR:
            blocks[-1].append(t)
        else:
            blocks.append([t])
    for b in blocks:
        inner = [car[t] for t in b[1:-1]]
        level = sorted(inner)[len(inner) // 2] if inner else None
        for i, t in enumerate(b):
            c = car[t]
            edge = i == 0 or i == len(b) - 1
            if not edge:
                out[t] = min(full_kw, c)
            elif level is not None:
                out[t] = min(full_kw, max(level, c))
            else:  # one or two hours: the energy came in a short burst
                out[t] = full_kw if c > 0.25 * full_kw else min(full_kw, c / 0.25)
    return out


def find_sessions(''')

rep('''    for st in strategies:
        load: dict[datetime, float] = defaultdict(float)''', '''    real_q = car_quarter_kw(car, full_kw)
    for st in strategies:
        load: dict[datetime, float] = defaultdict(float)''')

rep('''            c = load.get(t, 0.0)
            if st == "as_is" and c > 0:
                c = full_kw if c > 0.25 * full_kw else c / 0.25      # at least one quarter hour at full power''',
    '''            c = load.get(t, 0.0)
            if st == "as_is" and c > 0:
                gp = _grid_part(grid, car, t)
                share = gp / car[t] if car.get(t) else 0.0         # the part of the car's power that came from the grid
                c = real_q.get(t, c) * share''')
p.write_text(s, encoding="utf-8")

t = ROOT / "tests" / "test_potential.py"
x = t.read_text(encoding="utf-8")
x = x.replace('''        hours = {h: 40.0 / 4 for h in (3, 4, 5, 6)}                        # 40 kWh: spread needs about 3 kW, fixed 4.1 kW''',
              '''        hours = {h: 30.0 / 4 for h in (3, 4, 5, 6)}                        # 30 kWh in 9 h: spread 3.3 kW, fixed 4.1 kW''')
x = x.replace('''                car[t] = 5.0 if 11 <= h < 14 else 0.0
                grid[t] = 0.3''', '''                car[t] = 5.0 if 11 <= h < 14 else 0.0
                grid[t] = 0.0 if 11 <= h < 14 else 0.3                    # the sun covers the car and the house''')
t.write_text(x, encoding="utf-8")
print("ok")
