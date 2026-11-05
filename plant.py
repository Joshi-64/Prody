"""Prody the plant: growth/mood state from study data, and a procedural SVG renderer.

Everything is deterministic: the same user + the same data always draws the same plant.
"""
import logging
import apptime
import os
import itertools
import math
import random
from datetime import date, datetime, timedelta

import json

from markupsafe import Markup, escape

from helpers import as_dt, query, user_sessions, user_todos

STAGES = [('Seed', 0.0), ('Sprout', 0.06), ('Sapling', 0.2), ('Leafy', 0.4), ('Bloom', 0.62), ('Flourishing', 0.85)]
STAGE_BLURB = {
    'Seed': 'Tucked into fresh soil. One focus session wakes it up.',
    'Sprout': 'First leaves are out. Keep the sessions coming.',
    'Sapling': 'A real stem now, and its first branch.',
    'Leafy': 'Filling out nicely. Each class is growing its own branch.',
    'Bloom': 'First flowers. Your semester is showing.',
    'Flourishing': 'Tall, full and fruiting. This is what consistency looks like.',
}
_ids = itertools.count(1)


# ------------------------------------------------------------------ state
def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def growth_for(hours, progress):
    """0..1 growth from study hours (most weight) and course progress."""
    return _clamp(0.58 * min(hours / 45.0, 1.0) ** 0.85 + 0.42 * progress)


def stage_for(g):
    idx = max(i for i, (_, t) in enumerate(STAGES) if g >= t)
    nxt = STAGES[idx + 1] if idx + 1 < len(STAGES) else None
    lo = STAGES[idx][1]
    to_next = int(100 * (g - lo) / (nxt[1] - lo)) if nxt else 100
    return idx, STAGES[idx][0], (nxt[0] if nxt else None), _clamp(to_next, 0, 100)


def mood_for(days_idle):
    if days_idle is None:
        return 'okay', 0.85
    vit = _clamp(1 - (days_idle - 1) / 4.0)  # full for a day, wilted after ~5 idle days
    return ('happy' if vit >= 0.8 else 'okay' if vit >= 0.45 else 'thirsty'), vit


def plant_state(user_id, today=None):
    today = today or apptime.today_local()
    sessions = user_sessions(user_id)
    hours = sum(int(s['minutes']) for s in sessions) / 60.0
    last = max((as_dt(s['started_at']) for s in sessions if as_dt(s['started_at'])), default=None)
    days_idle = (today - apptime.local_date(last)).days if last else None

    courses = query('SELECT course_id, course_name, color FROM usercourses WHERE id = %s ORDER BY course_id', (user_id,))
    per = {}
    for s in sessions:
        if s['course_id']:
            per[s['course_id']] = per.get(s['course_id'], 0) + int(s['minutes'])
    ids = [c['course_id'] for c in courses]
    dls = query('SELECT deadline_date, is_completed FROM coursedeadlines WHERE course_id IN (%s)'
                % ','.join(str(int(i)) for i in ids), ()) if ids else []
    todos = user_todos(user_id)
    u = query('SELECT created_at FROM users WHERE id = %s', (user_id,), one=True) or {}
    # fraction of the semester elapsed: from sign-up (or first deadline) to the last deadline, ~16 weeks by default
    dates = [as_dt(d['deadline_date']) for d in dls if as_dt(d['deadline_date'])]
    start = as_dt(u.get('created_at')) or apptime.now_utc_naive()
    if dates:
        start = min(start, min(dates) - timedelta(days=7))
    end = max(dates) if dates else start + timedelta(weeks=16)
    if end <= start + timedelta(days=14):
        end = start + timedelta(weeks=16)
    elapsed = _clamp((datetime.combine(today, datetime.min.time()) - start) / (end - start)) if courses else 0.0
    items = [d['is_completed'] for d in dls] + [t['is_completed'] for t in todos]
    completed = sum(1 for x in items if x) / len(items) if items else 0.0
    progress = 0.5 * elapsed + 0.5 * completed if (courses or items) else 0.0

    g = growth_for(hours, progress)
    idx, stage, nxt, to_next = stage_for(g)
    mood, vit = mood_for(days_idle)
    try:  # watering today perks the plant up a notch (lazy import: profiles imports plant)
        from profiles import last_cared
        if last_cared(user_id) == today.strftime('%Y-%m-%d'):
            vit = _clamp(vit + 0.25)
            mood = 'happy' if vit >= 0.8 else 'okay' if vit >= 0.45 else 'thirsty'
    except Exception:
        pass
    p = query('SELECT pot_key, acc_keys, scene_key, plant_name FROM userprofiles WHERE user_id = %s', (user_id,), one=True) or {}
    return {
        'seed': int(user_id), 'hours': round(hours, 1), 'progress': round(progress, 3), 'elapsed': round(elapsed, 3),
        'completed': round(completed, 3), 'growth': round(g, 4), 'stage_idx': idx, 'stage': stage, 'next_stage': nxt,
        'to_next': to_next, 'blurb': STAGE_BLURB[stage], 'days_idle': days_idle, 'mood': mood, 'vitality': vit,
        'name': (p.get('plant_name') or 'Prody'),
        'branches': [{'name': c['course_name'], 'color': c['color'], 'minutes': per.get(c['course_id'], 0)} for c in courses],
        'pot': p.get('pot_key') or 'pot_terracotta', 'accs': [a for a in (p.get('acc_keys') or '').split(',') if a],
        'scene': p.get('scene_key') or '',
    }


def mood_line(st):
    if st['mood'] == 'thirsty':
        return f"{st['name']} is a little thirsty. One focus session perks it right back up."
    if st['mood'] == 'okay' and st['days_idle'] is not None:
        return f"{st['name']} misses you a bit. It's been {st['days_idle']} days."
    if st['days_idle'] is None:
        return f"{st['name']} is waiting for its first focus session."
    return f"{st['name']} is happy and soaking up the light."


# ------------------------------------------------------------------ geometry helpers
def _hex(c):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    a, b = _hex(a), _hex(b)
    return '#%02x%02x%02x' % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _f(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def _smooth(pts, move=True):
    d = (f'M{_f(pts[0][0])},{_f(pts[0][1])}' if move else '')
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f' C{_f(c1[0])},{_f(c1[1])} {_f(c2[0])},{_f(c2[1])} {_f(p2[0])},{_f(p2[1])}'
    return d


def _ribbon(pts, w0, w1):
    """Closed tapered shape along a polyline (a stem that is thicker at the base)."""
    n = len(pts)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        w = (w0 + (w1 - w0) * (i / (n - 1)) ** 0.8) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    tip = pts[-1]
    return _smooth(left) + f' Q{_f(tip[0])},{_f(tip[1])} {_f(right[-1][0])},{_f(right[-1][1])}' + \
        _smooth(right[::-1], move=False) + ' Z'


def _quad(p0, c, p1, n=8):
    out = []
    for i in range(n):
        t = i / (n - 1)
        out.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1]))
    return out


def _droop(angle, d):
    """Pull a direction (degrees, SVG coords) toward pointing down by factor d."""
    delta = ((90 - angle + 180) % 360) - 180
    return angle + delta * d * 0.85


def _leaf(x, y, ang, ln, w, base, light, vein, rnd=1.0):
    """Two-tone almond leaf with a midrib. ang: degrees, 0 = pointing right."""
    top = (f'M0,0 C{_f(ln * .28)},{_f(-w * 1.05 * rnd)} {_f(ln * .72)},{_f(-w * 1.0 * rnd)} {_f(ln)},0')
    bot = (f' C{_f(ln * .72)},{_f(w * .92 * rnd)} {_f(ln * .28)},{_f(w * .95 * rnd)} 0,0Z')
    return (f'<g transform="translate({_f(x)},{_f(y)}) rotate({_f(ang)})">'
            f'<path d="{top}{bot}" fill="{base}"/>'
            f'<path d="{top} C{_f(ln * .7)},{_f(-w * .1)} {_f(ln * .3)},{_f(-w * .05)} 0,0Z" fill="{light}"/>'
            f'<path d="M{_f(ln * .06)},0 Q{_f(ln * .5)},{_f(-w * .08)} {_f(ln * .86)},0" stroke="{vein}" stroke-width="{_f(max(.7, w * .12))}" '
            f'fill="none" stroke-linecap="round" opacity=".75"/></g>')


def _flower(x, y, r, petal, centre, rot=0, open_=1.0):
    out = [f'<g transform="translate({_f(x)},{_f(y)}) rotate({_f(rot)})">']
    for k in range(5):
        a = k * 72
        out.append(f'<ellipse cx="0" cy="{_f(-r * .62 * open_)}" rx="{_f(r * .42)}" ry="{_f(r * .62)}" '
                   f'transform="rotate({a})" fill="{petal}"/>')
    out.append(f'<circle r="{_f(r * .34)}" fill="{centre}"/><circle r="{_f(r * .13)}" cx="{_f(-r*.08)}" cy="{_f(-r*.08)}" fill="#fff" opacity=".45"/></g>')
    return ''.join(out)


def _fruit(x, y, r, color, stalk):
    return (f'<g><path d="M{_f(x)},{_f(y - r - 4)} q1,2 0,{_f(4)}" stroke="{stalk}" stroke-width="1.3" fill="none"/>'
            f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r)}" fill="{color}"/>'
            f'<circle cx="{_f(x - r * .35)}" cy="{_f(y - r * .35)}" r="{_f(r * .28)}" fill="#fff" opacity=".5"/></g>')


# ------------------------------------------------------------------ pots, scenes, accessories
POTS = {
    # key: (body, rim, face, pattern)
    'pot_terracotta': ('#C46A43', '#B35B36', '#2B241E', None),
    'pot_cream': ('#EFE7D8', '#E2D7C3', '#2B241E', 'stripes'),
    'pot_speckle': ('#E6D6B8', '#D8C6A4', '#2B241E', 'speckle'),
    'pot_sage': ('#9DB59A', '#86A083', '#22301F', 'drip'),
    'pot_wave': ('#F2ECE0', '#E5DCCB', '#2B241E', 'wave'),
    'pot_basket': ('#D2B48A', '#BE9C6E', '#2B241E', 'weave'),
    'pot_forest': ('#2F5D46', '#264D3A', '#F4EEE2', 'glaze'),
    'pot_kintsugi': ('#3A3A36', '#2E2E2A', '#F4EEE2', 'gold'),
}
RIM_Y, BODY_TOP, BODY_BOT = 206, 224, 288
BODY = 'M70,224 L170,224 L161,280 Q159.5,288 151,288 L89,288 Q80.5,288 79,280 Z'


def _pot(key, pid):
    body, rim, face, pat = POTS.get(key, POTS['pot_terracotta'])
    defs, over = '', ''
    clip = f'<clipPath id="{pid}c"><path d="{BODY}"/></clipPath>'
    if pat == 'stripes':
        over = ''.join(f'<rect x="60" y="{y}" width="120" height="3" fill="#2F5D46" opacity=".55"/>' for y in (236, 272))
    elif pat == 'speckle':
        r = random.Random(11)
        over = ''.join(f'<circle cx="{_f(r.uniform(72, 168))}" cy="{_f(r.uniform(228, 286))}" r="{_f(r.uniform(.7, 1.6))}" '
                       f'fill="#7A6247" opacity=".55"/>' for _ in range(46))
    elif pat == 'drip':
        over = ('<path d="M60,224 L180,224 L180,234 Q170,246 162,236 Q154,250 146,236 Q136,244 128,234 Q118,252 108,236 '
                'Q98,246 90,234 Q80,248 72,236 L60,238 Z" fill="#6F8E6C"/>')
    elif pat == 'wave':
        over = ''.join(f'<path d="M64,{y} q7,-6 14,0 t14,0 t14,0 t14,0 t14,0 t14,0 t14,0 t14,0" stroke="#C46A43" '
                       f'stroke-width="2.2" fill="none"/>' for y in (240, 274))
    elif pat == 'weave':
        over = ''.join(f'<rect x="60" y="{y}" width="120" height="2" fill="#A4845A" opacity=".7"/>' for y in range(230, 288, 8)) + \
            ''.join(f'<rect x="{x}" y="224" width="2" height="66" fill="#A4845A" opacity=".35"/>' for x in range(74, 170, 10))
    elif pat == 'glaze':
        over = '<path d="M78,230 Q84,262 92,284" stroke="#fff" stroke-width="5" opacity=".12" fill="none" stroke-linecap="round"/>'
    elif pat == 'gold':
        over = ('<path d="M84,226 l8,14 l-5,12 l10,10 l-2,26 M150,226 l-6,18 l9,9 l-8,14 l4,21 M110,288 l6,-12 l14,-6" '
                'stroke="#C9A24A" stroke-width="1.8" fill="none" stroke-linejoin="round"/>')
    hl = '<path d="M80,232 Q83,256 89,282" stroke="#fff" stroke-width="4" opacity=".14" fill="none" stroke-linecap="round"/>'
    svg = (f'<ellipse cx="120" cy="290" rx="56" ry="5" fill="#1d1a14" opacity=".13"/>'
           f'<path d="{BODY}" fill="{body}"/><g clip-path="url(#{pid}c)">{over}{hl}'
           f'<rect x="60" y="224" width="120" height="5" fill="#000" opacity=".08"/></g>'
           f'<rect x="62" y="{RIM_Y}" width="116" height="20" rx="6" fill="{rim}"/>'
           f'<rect x="62" y="{RIM_Y}" width="116" height="4" rx="2" fill="#fff" opacity=".12"/>'
           f'<ellipse cx="120" cy="{RIM_Y + 2}" rx="52" ry="4.2" fill="#4E3B2C"/>')
    return clip, svg, face


def _face(mood, color, vit):
    eye_y, my = 250, 262
    cheeks = ('<ellipse cx="96" cy="259" rx="7" ry="4" fill="#E9977A" opacity=".45"/>'
              '<ellipse cx="144" cy="259" rx="7" ry="4" fill="#E9977A" opacity=".45"/>')
    if mood == 'thirsty':
        eyes = (f'<path d="M100,{eye_y} q6,4 12,0 M128,{eye_y} q6,4 12,0" stroke="{color}" stroke-width="2.4" '
                f'fill="none" stroke-linecap="round"/>')
        mouth = f'<path d="M112,{my + 3} q8,-6 16,0" stroke="{color}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
        drop = '<path d="M150,236 q4,6 0,9 q-4,-3 0,-9z" fill="#8FB3C4"/>'
        return f'<g class="pl-face">{eyes}{mouth}{drop}</g>'
    eyes = (f'<ellipse cx="106" cy="{eye_y}" rx="3.4" ry="4" fill="{color}"/><ellipse cx="134" cy="{eye_y}" rx="3.4" ry="4" fill="{color}"/>'
            f'<circle cx="107.2" cy="{eye_y - 1.4}" r="1.1" fill="#fff" opacity=".8"/><circle cx="135.2" cy="{eye_y - 1.4}" r="1.1" fill="#fff" opacity=".8"/>')
    curve = 6 if mood == 'happy' else 2.5
    mouth = (f'<path d="M113,{my} q7,{curve} 14,0" stroke="{color}" stroke-width="2.4" fill="none" stroke-linecap="round"/>')
    return f'<g class="pl-face"><g class="pl-eyes">{eyes}</g>{mouth}{cheeks if mood == "happy" else ""}</g>'


def _scene(key, pid):
    if key == 'scene_window':
        return ('<rect x="-500" y="-400" width="1240" height="700" fill="#EEE6D6"/>'
                '<rect x="26" y="18" width="188" height="200" rx="8" fill="#F8F4EC"/>'
                '<rect x="36" y="28" width="168" height="180" rx="4" fill="#DCE7E1"/>'
                '<path d="M36,150 Q80,128 120,146 T204,138 L204,208 L36,208Z" fill="#C9DACB"/>'
                '<circle cx="168" cy="66" r="16" fill="#F6EBD0"/>'
                '<rect x="117" y="28" width="6" height="180" fill="#F8F4EC"/><rect x="36" y="114" width="168" height="6" fill="#F8F4EC"/>'
                '<rect x="-500" y="272" width="1240" height="14" fill="#E2D3B8"/><rect x="-500" y="286" width="1240" height="60" fill="#D7C5A6"/>')
    if key == 'scene_desk':
        return ('<rect x="-500" y="-400" width="1240" height="700" fill="#E8E2D5"/>'
                '<rect x="24" y="40" width="58" height="72" rx="3" fill="#F7F3EA" stroke="#CDBFA6" stroke-width="3"/>'
                '<path d="M32,100 l14,-22 l10,12 l8,-8 l12,18z" fill="#A9BFA2"/>'
                '<rect x="-500" y="282" width="1240" height="60" fill="#B98E66"/><rect x="-500" y="282" width="1240" height="3" fill="#CDA27A"/>'
                '<rect x="182" y="250" width="40" height="11" rx="2" fill="#2F5D46"/><rect x="186" y="261" width="36" height="10" rx="2" fill="#C46A43"/>'
                '<rect x="180" y="271" width="44" height="11" rx="2" fill="#D9C7A3"/>'
                '<path d="M22,282 v-34 h22 v34" fill="#F4EFE6"/><path d="M44,254 q10,2 0,14" stroke="#F4EFE6" stroke-width="4" fill="none"/>')
    if key == 'scene_greenhouse':
        arches = ''.join(f'<path d="M{x},340 L{x},60 Q{x+30},20 {x+60},60 L{x+60},300" stroke="#F7F4EC" stroke-width="5" fill="none" opacity=".9"/>'
                         for x in (-240, -180, -120, -60, 0, 60, 120, 180, 240, 300, 360, 420))
        hang = ''.join(f'<path d="M{x},-400 L{x},0 Q{x+6},26 {x-2},{40+(x%3)*8}" stroke="#93AE8E" stroke-width="2" fill="none"/>'
                       f'<ellipse cx="{x-2}" cy="{44+(x%3)*8}" rx="5" ry="9" fill="#A9C2A3"/>' for x in (24, 92, 160, 214))
        return (f'<rect x="-500" y="-400" width="1240" height="700" fill="#E1EADB"/><rect x="-500" y="-400" width="1240" height="540" fill="#EBF1E6"/>{arches}'
                '<rect x="-500" y="100" width="1240" height="4" fill="#F7F4EC"/>'
                f'<rect x="-500" y="284" width="1240" height="60" fill="#CBB892"/>'
                + ''.join(f'<rect x="{x}" y="284" width="2" height="60" fill="#B8A57E"/>' for x in range(-490, 740, 30)))
    return '<circle cx="120" cy="150" r="112" fill="var(--plant-halo, #EDE6D6)" opacity=".55"/>'


def _accessories(accs, tip, canopy, face_color, lean, pid):
    out_back, out_front = [], []
    tx, ty = tip
    if 'acc_lights' in accs:
        (lx, ly), (rx, ry) = canopy
        mid = ((lx + rx) / 2, max(ly, ry) + 26)
        pts = _quad((lx, ly), mid, (rx, ry), 9)
        out_front.append(f'<path d="{_smooth(pts)}" stroke="#4A4A3E" stroke-width="1" fill="none" opacity=".7"/>')
        for i, (x, y) in enumerate(pts[1:-1]):
            out_front.append(f'<g class="pl-bulb" style="animation-delay:{i * .35:.2f}s"><circle cx="{_f(x)}" cy="{_f(y + 3)}" r="5.5" fill="#F6D88B" opacity=".35"/>'
                             f'<circle cx="{_f(x)}" cy="{_f(y + 3)}" r="2.6" fill="#F3C962"/></g>')
    if 'acc_scarf' in accs:
        out_front.append('<path d="M60,214 Q120,224 180,214 L180,226 Q120,236 60,226Z" fill="#C46A43"/>'
                         '<path d="M60,218 Q120,228 180,218" stroke="#E7B49A" stroke-width="2" fill="none" stroke-dasharray="5 5"/>'
                         '<path d="M150,226 l4,24 l10,-2 l-4,-24z" fill="#B35B36"/>'
                         '<path d="M154,250 l1,4 M158,249 l1,4 M162,248 l1,4" stroke="#B35B36" stroke-width="1.6" stroke-linecap="round"/>')
    if 'acc_sticker' in accs:
        out_front.append('<g transform="translate(140,266) rotate(-8)"><rect x="-1" y="-1" width="22" height="16" rx="5" fill="#F8F3E8" stroke="#2F5D46" stroke-width="1.2"/>'
                         '<path d="M5,5 h9 v6 h-9z M14,7 l5,-3 M5,7 q-3,0 -3,-3" fill="#8FB3C4" stroke="#2F5D46" stroke-width="1"/></g>')
    if 'acc_glasses' in accs:
        out_front.append(f'<g stroke="{face_color}" stroke-width="2" fill="#fff" fill-opacity=".18"><circle cx="106" cy="250" r="8.5"/>'
                         f'<circle cx="134" cy="250" r="8.5"/><path d="M114.5,249 q5.5,-3 11,0" fill="none"/></g>')
    if 'acc_hat' in accs:
        out_front.append(f'<g transform="translate({_f(tx)},{_f(ty - 4)}) rotate({_f(lean * 0.6 - 6)})">'
                         '<ellipse cx="0" cy="0" rx="17" ry="4.5" fill="#D9BD86"/><path d="M-9,0 Q-9,-13 0,-13 Q9,-13 9,0Z" fill="#E4CB97"/>'
                         '<path d="M-9,-3 Q0,-1 9,-3 L9,0 Q0,2 -9,0Z" fill="#2F5D46"/></g>')
    if 'acc_butterfly' in accs:
        bx, by = (canopy[1][0] + 12, min(canopy[1][1], ty) - 4)
        out_front.append(f'<g class="pl-bfly" transform="translate({_f(bx)},{_f(by)})"><g class="pl-wings">'
                         '<path d="M0,0 C-10,-12 -16,-2 -10,3 C-14,8 -6,12 0,2Z" fill="#C46A43"/>'
                         '<path d="M0,0 C10,-12 16,-2 10,3 C14,8 6,12 0,2Z" fill="#D98A63"/></g>'
                         '<path d="M0,-3 v9" stroke="#2B241E" stroke-width="1.6" stroke-linecap="round"/>'
                         '<path d="M0,-3 q-2,-4 -4,-5 M0,-3 q2,-4 4,-5" stroke="#2B241E" stroke-width=".8" fill="none"/></g>')
    return ''.join(out_back), ''.join(out_front)


# ------------------------------------------------------------------ main renderer
SPRIG_HOURS = (5, 20)  # sprig_1 < 5 h <= sprig_2 < 20 h <= sprig_3


def sprig_stage(st):
    h = st.get('hours')
    if h is None:  # demo/preview states carry no hours: map clay stage index 0-5 onto 3 sprigs
        return 1 + min(2, int(st.get('stage_idx') or 0) // 2)
    return 1 if h < SPRIG_HOURS[0] else 2 if h < SPRIG_HOURS[1] else 3


def render_plant(st, size=None, scene=True, cls='', grow=False, fit=False):
    """Roots-style sprig (read-only) for Zen/Profile/Buddy/Study/Store/error pages. Same signature as the old clay renderer."""
    n = sprig_stage(st or {})
    px = int(size) if size else 120
    style = 'width:100%%;height:auto;max-width:%dpx' % px if fit else 'width:%dpx;height:%dpx' % (px, px)
    name = escape((st or {}).get('name') or 'Prody')
    if (st or {}).get('_show_pot'):
        return Markup(_sprig_in_pot(st, n, px, style, name, cls))
    return Markup(f'<img class="sprig sprig-{n} {escape(cls)}{" sprig-grow" if grow else ""}" src="/static/img/roots/sprig_{n}.svg?v=1" '
                  f'width="{px}" height="{px}" style="{style};display:block;margin:0 auto" alt="{name}, growth stage {n} of 3">')


def _sprig_in_pot(st, n, px, style, name, cls):
    """Flat Roots-style pot (trapezoid + rim) in the item's colours, with the sprig sitting in it."""
    body, rim, face, pat = POTS.get(st.get('pot'), POTS['pot_terracotta'])
    shade = _mix(body, '#3A2A1E', 0.18)
    deco = ''
    if pat == 'stripes':
        deco = ''.join(f'<rect x="34" y="{y}" width="52" height="3" fill="{rim}"/>' for y in (84, 94))
    elif pat == 'speckle':
        deco = ''.join(f'<circle cx="{x}" cy="{y}" r="1.4" fill="#8A6A4A"/>' for x, y in ((42,84),(55,92),(70,86),(78,98),(48,101),(64,104),(36,95)))
    elif pat == 'drip':
        deco = f'<path d="M33,79 H87 V85 q-4,6 -8,0 q-5,9 -10,0 q-5,7 -10,0 q-5,9 -10,0 q-5,6 -9,0 q-3,5 -7,0 Z" fill="{_mix(body, "#FFFFFF", 0.35)}"/>'
    elif pat == 'wave':
        deco = f'<path d="M35,90 q6,-5 12,0 t12,0 t12,0 t12,0" stroke="#7FA7B8" stroke-width="2.5" fill="none"/>'
    elif pat == 'weave':
        deco = ''.join(f'<path d="M{x},80 l3,30" stroke="{rim}" stroke-width="2"/>' for x in range(37, 86, 7)) + \
               ''.join(f'<rect x="34" y="{y}" width="52" height="2" fill="{shade}"/>' for y in (88, 97))
    elif pat == 'glaze':
        deco = f'<path d="M38,82 q4,12 2,24" stroke="{_mix(body, "#FFFFFF", 0.3)}" stroke-width="3" fill="none" stroke-linecap="round"/>'
    elif pat == 'gold':
        deco = '<path d="M40,80 l8,10 l-4,8 l10,12 M70,80 l-5,9 l9,7" stroke="#D9AE4A" stroke-width="2" fill="none" stroke-linejoin="round"/>'
    return (f'<svg class="sprig sprig-pot sprig-{n} {escape(cls)}" viewBox="0 0 120 120" width="{px}" height="{px}" '
            f'style="{style};display:block;margin:0 auto" role="img" aria-label="{name}, growth stage {n} of 3">'
            f'<ellipse cx="60" cy="113" rx="30" ry="3.5" fill="#3A2A1E" opacity=".12"/>'
            f'<image href="/static/img/roots/sprig_{n}.svg?v=1" x="22" y="6" width="76" height="76"/>'
            f'<path d="M33,79 H87 L80,108 Q79,112 75,112 H45 Q41,112 40,108 Z" fill="{body}"/>'
            f'{deco}'
            f'<rect x="28" y="71" width="64" height="10" rx="3" fill="{rim}"/>'
            f'<rect x="28" y="79" width="64" height="2" fill="{shade}" opacity=".5"/></svg>')


def _render_clay_plant(st, size=None, scene=True, cls='', grow=False, fit=False):
    """(Retired) Return an inline SVG Markup for a plant state dict (see plant_state)."""
    pid = f'pl{next(_ids)}'
    rng = random.Random(st['seed'] * 7919 + 13)
    g, idx, vit = st['growth'], st['stage_idx'], st['vitality']
    droop = 1 - vit
    side0 = rng.choice((-1, 1))
    lean = rng.uniform(-1, 1) * 10

    # palette: lively greens that fade toward dry olive when neglected
    def col(c):
        return _mix(c, '#B3AA7C', droop * 0.75)
    leaf_base = [col('#4E8052'), col('#5B9160'), col('#467548')]
    leaf_light = [col('#6FA36F'), col('#7DB178'), col('#62985F')]
    vein = col('#CFE3C2')
    stem_c = col('#4A7A4B')

    parts_back, parts_mid, parts_front = [], [], []
    base = (120, RIM_Y + 3)
    tip = base
    canopy = ((96, 150), (144, 150))

    if idx == 0:  # seed
        parts_mid.append('<ellipse cx="120" cy="207" rx="26" ry="5" fill="#5E4836"/>')
        parts_mid.append('<ellipse cx="118" cy="208" rx="7.5" ry="5" transform="rotate(-18 118 208)" fill="#9A7652"/>'
                         '<path d="M113,207 q5,-3 10,0" stroke="#7E5E40" stroke-width="1" fill="none"/>')
        if g > 0.02:
            parts_mid.append(f'<path d="M122,206 q-1,-12 5,-18" stroke="{stem_c}" stroke-width="3" fill="none" stroke-linecap="round"/>'
                             + _leaf(127, 188, -20, 14, 5.5, leaf_base[0], leaf_light[0], vein)
                             + _leaf(126, 189, -150, 10, 4.2, leaf_base[1], leaf_light[1], vein))
        tip = (126, 186)
    else:
        H = 28 + g * 150 if idx > 1 else 30 + g * 150
        H *= 1 - droop * 0.12

        def stem(t):
            x = base[0] + lean * math.sin(math.pi * t) * 0.7 + lean * 0.35 * t + side0 * droop * (t ** 2) * H * 0.5
            y = base[1] - H * t + droop * H * 0.55 * max(0.0, t - 0.5) ** 2 * 1.3
            return x, y

        def stem_ang(t):
            a, b = stem(max(0, t - .02)), stem(min(1, t + .02))
            return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))

        pts = [stem(i / 13) for i in range(14)]
        tip = pts[-1]
        w0 = 4.2 + g * 7
        parts_mid.append(f'<path d="{_ribbon(pts, w0, 1.8)}" fill="{stem_c}"/>')
        parts_mid.append(f'<path d="{_smooth([(x - w0 * .18 * (1 - i / 13), y) for i, (x, y) in enumerate(pts[:-2])])}" '
                         f'stroke="#fff" stroke-width="{_f(max(.8, w0 * .16))}" opacity=".13" fill="none" stroke-linecap="round"/>')

        # branches (one per class while there is room), alternating sides
        nb = 0 if idx < 2 else min(6, max(1, math.ceil((g - 0.15) * 7)))
        bp = [(rng.uniform(-.06, .06), rng.uniform(34, 52), rng.uniform(.82, 1.1), rng.random()) for _ in range(6)]
        mins = [b['minutes'] for b in st['branches']] or [0]
        mx = max(mins) or 1
        tips = []
        for i in range(nb):
            t0 = 0.3 + 0.52 * (i / max(nb - 1, 1)) + bp[i][0] if nb > 1 else 0.55
            s = side0 * (1 if i % 2 == 0 else -1)
            sx, sy = stem(t0)
            course_f = 0.8 + 0.4 * (mins[i % len(mins)] / mx) if st['branches'] else 1
            L = H * (0.58 - 0.22 * t0) * bp[i][2] * course_f * (0.7 + 0.3 * g)
            a = math.radians(bp[i][1])
            ex, ey = sx + s * L * math.cos(a), sy - L * math.sin(a) + droop * L * 0.75
            c = (sx + s * L * 0.62 * math.cos(a), sy - L * 0.12)
            bpts = _quad((sx, sy), c, (ex, ey), 7)
            parts_back.append(f'<path d="{_ribbon(bpts, 2.4 + g * 2.6, 1.1)}" fill="{stem_c}"/>')
            for k, tt in enumerate((0.45, 0.78)):
                j = int(tt * 6)
                (x1, y1), (x2, y2) = bpts[j], bpts[min(j + 1, 6)]
                ta = math.degrees(math.atan2(y2 - y1, x2 - x1))
                la = _droop(ta + (-38 if k % 2 == 0 else 38) * (1 if s > 0 else -1), droop)
                parts_back.append(_leaf(x1, y1, la, 20 + g * 12, 7.5 + g * 3.5, leaf_base[(i + k) % 3], leaf_light[(i + k) % 3], vein))
            ta = math.degrees(math.atan2(ey - bpts[-2][1], ex - bpts[-2][0]))
            if idx >= 4 and vit > 0.25:
                parts_back.append(_leaf(ex, ey, _droop(ta - 30 * s, droop), 13 + g * 6, 5 + g * 2, leaf_base[i % 3], leaf_light[i % 3], vein))
                tips.append((ex, ey, i))
            else:
                parts_back.append(_leaf(ex, ey, _droop(ta, droop), 22 + g * 10, 8 + g * 3.2, leaf_base[i % 3], leaf_light[i % 3], vein))
            if idx >= 5 and i % 2 == 0:
                mxp, myp = bpts[3]
                parts_back.append(_fruit(mxp + s * 3, myp + 9, 4.6, col('#C2603A'), stem_c))
        if tips:
            xs = sorted(tips)
            canopy = ((xs[0][0], xs[0][1]), (xs[-1][0], xs[-1][1]))
        elif nb:
            canopy = ((tip[0] - 26, tip[1] + H * .3), (tip[0] + 26, tip[1] + H * .3))
        else:
            canopy = ((tip[0] - 18, tip[1] + 14), (tip[0] + 18, tip[1] + 14))

        # leaves along the main stem
        if idx == 1:
            for s in (-1, 1):
                ang = _droop(-90 + s * 62 + lean * .4, droop)
                parts_front.append(_leaf(tip[0], tip[1] + 2, ang, 15 + g * 40, 7.5 + g * 12, leaf_base[(s + 1) // 2],
                                         leaf_light[(s + 1) // 2], vein, rnd=1.15))
        else:
            nl = 3 + int(g * 6)
            for i in range(nl):
                t = 0.14 + 0.72 * i / max(nl - 1, 1)
                s = -side0 if i % 2 == 0 else side0
                x, y = stem(t)
                sa = stem_ang(t)
                ang = _droop(sa + s * (58 - 10 * t), droop)
                ln = (25 + g * 14) * (1 - 0.35 * t) * rng.uniform(.88, 1.08)
                parts_front.append(_leaf(x, y, ang, ln, ln * .36, leaf_base[i % 3], leaf_light[i % 3], vein))
            # crown: two young leaves and a bud at the tip
            sa = stem_ang(1)
            for s in (-1, 1):
                parts_front.append(_leaf(tip[0], tip[1], _droop(sa + s * 28, droop), 12 + g * 6, 4.6 + g * 2,
                                         leaf_light[0], col('#8CBF84'), vein))
            if idx >= 4 and vit > 0.25:
                parts_front.append(_flower(tip[0], tip[1] - 2, 9 + g * 3, col('#F4DCCB'), col('#D9A04A'), rot=rng.uniform(0, 72)))
        for ex, ey, i in tips:
            parts_front.append(_flower(ex, ey, 7 + g * 3, col('#F4DCCB') if i % 2 else col('#EFC3AE'), col('#D9A04A'),
                                       rot=rng.uniform(0, 72), open_=0.7 + 0.3 * vit))

    clip, pot_svg, face_color = _pot(st.get('pot'), pid)
    accs = set(st.get('accs') or [])
    acc_back, acc_front = _accessories(accs, tip, canopy, face_color, lean, pid)
    mood_cls = f"pl-{st['mood']}"
    vb = '0 0 240 300'
    if fit:  # crop to the plant so tiny avatars still show pot, face and leaves
        top = min(150.0, min(tip[1], canopy[0][1], canopy[1][1]) - 24)
        h = 300 - top
        vb = f'{_f(120 - h * .45)} {_f(top)} {_f(h * .9)} {_f(h)}'
        scene = False
    w = f' width="{size}" height="{int(size * 1.11 if fit else size * 1.25)}"' if size else ''
    label = f"{st.get('name', 'Prody')}, a {st['stage'].lower()} plant, feeling {st['mood']}"
    svg = (f'<svg class="prody-plant {mood_cls} {"pl-grow" if grow else ""} {cls}" viewBox="{vb}"{w} role="img" aria-label="{label}">'
           f'<defs>{clip}</defs>'
           f'{("<g class=pl-scene>" + _scene(st.get("scene"), pid) + "</g>") if scene else ""}'
           f'{acc_back}<g class="pl-sway">{"".join(parts_back)}{"".join(parts_mid)}{"".join(parts_front)}</g>'
           f'{pot_svg}{_face(st["mood"], face_color, vit)}{acc_front}</svg>')
    if fit or (size and size < 140):
        return Markup(svg)
    return Markup(_wrap3d(st, svg, scene, grow, cls))


# ------------------------------------------------------------------ 3D (Three.js) progressive enhancement
PLANT3D_JS = '/static/js/plant3d.js'


def state_3d(st, scene=True, grow=False):
    """The JSON-safe subset of a plant state that static/js/plant3d.js needs."""
    return {'seed': int(st.get('seed') or 1), 'growth': float(st.get('growth') or 0), 'stage_idx': int(st.get('stage_idx') or 0),
            'vitality': float(st.get('vitality', 1)), 'mood': st.get('mood') or 'okay', 'pot': st.get('pot') or 'pot_terracotta',
            'accs': list(st.get('accs') or []), 'scene': (st.get('scene') or '') if scene else '',
            'branches': [{'minutes': int(b.get('minutes') or 0), 'color': b.get('color') or ''} for b in (st.get('branches') or [])],
            'name': st.get('name') or 'Prody', 'stage': st.get('stage') or '', 'grow': bool(grow), 'models': glb_models()}


_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'models')


def glb_models():
    """Names of the .glb files in static/models (3d design 1's Blender exports). plant3d.js only requests the ones listed,
    so a missing model never costs a 404; the code-built part is used instead."""
    try:
        return sorted(f for f in os.listdir(_MODELS_DIR) if f.endswith('.glb'))
    except OSError:
        return []


def _loader_once():
    """Emit the module script the first time a plant is drawn in a request (no base.html edit needed)."""
    try:
        from flask import g, has_request_context
        if has_request_context():
            if getattr(g, '_plant3d_loaded', False):
                return ''
            g._plant3d_loaded = True
    except Exception:
        pass
    return ('<script>window.plant3d=window.plant3d||{q:[],mount(e,s){this.q.push(["mount",e,s])},'
            'update(e,s){this.q.push(["update",e,s])},celebrate(e){this.q.push(["celebrate",e])},'
            'refresh(e){this.q.push(["refresh",e])}};</script>'
            f'<script type="module" src="{PLANT3D_JS}"></script>')


def _wrap3d(st, svg, scene, grow, cls):
    data = escape(json.dumps(state_3d(st, scene, grow), separators=(',', ':')))
    return (f'<div class="plant3d{" pl-grow" if grow else ""} {cls}" data-plant="{data}" '
            f'style="position:relative;width:100%;aspect-ratio:240/300">{svg}</div>{_loader_once()}')


def demo_state(growth, mood='happy', seed=3, pot='pot_terracotta', accs=(), scene='', courses=4):
    idx, stage, nxt, to_next = stage_for(growth)
    vit = {'happy': 1.0, 'okay': 0.6, 'thirsty': 0.05}[mood]
    return {'seed': seed, 'growth': growth, 'stage_idx': idx, 'stage': stage, 'next_stage': nxt, 'to_next': to_next,
            'vitality': vit, 'mood': mood, 'pot': pot, 'accs': list(accs), 'scene': scene, 'name': 'Prody',
            'branches': [{'name': str(i), 'color': '', 'minutes': 60 * (i + 1)} for i in range(courses)]}


# ------------------------------------------------------------------ milestones + Flask glue
def record_milestones(user_id, st):
    """Store each growth stage the first time it is reached. Returns the names of new ones.
    Never raises into the dashboard — Turso/adapter failures are logged and treated as no new milestones.
    """
    try:
        have = {r['stage'] for r in query('SELECT stage FROM plantmilestones WHERE user_id = %s', (user_id,))}
        new = []
        for name, _ in STAGES[1:st['stage_idx'] + 1]:
            if name not in have:
                query('INSERT INTO plantmilestones (user_id, stage, hours_at, reached_at) VALUES (%s, %s, %s, %s)',
                      (user_id, name, st['hours'], apptime.now_utc_naive()), commit=True)
                new.append(name)
        return new
    except Exception:
        logging.getLogger(__name__).exception(
            'record_milestones failed for user_id=%s stage_idx=%s; skipping',
            user_id, (st or {}).get('stage_idx'))
        return []


def milestones(user_id):
    return query('SELECT stage, hours_at, reached_at FROM plantmilestones WHERE user_id = %s ORDER BY reached_at, milestone_id',
                 (user_id,))


def mini_plant(user_id, size=44):
    return render_plant(plant_state(user_id), size=size, scene=False, cls='pl-mini', fit=True)


def with_item(st, key, kind):
    """A copy of a plant state with one store item tried on (for previews)."""
    s = dict(st)
    if kind == 'pot':
        s['pot'] = key
        s['_show_pot'] = True
    elif kind == 'scene':
        s['scene'] = key
    elif kind == 'acc':
        s['accs'] = list(dict.fromkeys((st.get('accs') or []) + [key]))
    return s


def register(app):
    @app.route('/plant/state')
    def plant_state_json():
        """Fresh 3D state for the signed-in user's plant (used by window.plant3d.refresh)."""
        from flask import jsonify, session
        if 'user_id' not in session:
            return jsonify(error='login required'), 401
        return jsonify(state_3d(plant_state(session['user_id'])))

    app.jinja_env.globals.update({'render_plant': render_plant, 'mini_plant': mini_plant, 'plant_state': plant_state,
                'mood_line': mood_line, 'demo_state': demo_state, 'with_item': with_item, 'state_3d': state_3d, 'PLANT_STAGES': [s for s, _ in STAGES]})



def semester_bounds(user_id):
    """Stored (semester_start, semester_end) from userprofiles, either may be None.
    None means: use the fallback in plant_state() (sign-up / first deadline - 7d -> last deadline,
    else start + 16 weeks). Not wired in yet; no behavior change."""
    row = query('SELECT semester_start, semester_end FROM userprofiles WHERE user_id = %s', (user_id,), one=True) or {}
    return row.get('semester_start'), row.get('semester_end')
