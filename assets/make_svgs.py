"""Generate the animated SVGs for the GitHub profile README.

GitHub renders SVGs as images: no JavaScript, but CSS and SMIL animation work. All 3D here is
real projection math done ahead of time; each frame is a keyframe in an SMIL `values` list, so
the browser interpolates smoothly between them.
"""
import math, os, random, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else 'assets'
os.makedirs(OUT, exist_ok=True)
random.seed(9)

CYAN, VIOLET, PINK, AMBER, INK = '#22D3EE', '#8B5CF6', '#EC4899', '#F59E0B', '#E6EDF3'
FONT = "'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', 'Fira Code', Consolas, 'Courier New', monospace"


def f(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def path(points, closed=False):
    if not points:
        return ''
    d = 'M' + ' L'.join(f'{f(x)} {f(y)}' for x, y in points)
    return d + (' Z' if closed else '')


# --------------------------------------------------------------------------- globe
class Globe:
    def __init__(self, cx, cy, r, tilt_deg=22):
        self.cx, self.cy, self.r = cx, cy, r
        self.tilt = math.radians(tilt_deg)

    def project(self, lat, lon):
        x = math.cos(lat) * math.cos(lon)
        y = math.sin(lat)
        z = math.cos(lat) * math.sin(lon)
        y2 = y * math.cos(self.tilt) - z * math.sin(self.tilt)
        z2 = y * math.sin(self.tilt) + z * math.cos(self.tilt)
        return self.cx + self.r * x, self.cy - self.r * y2, z2

    def meridian_halves(self, lon, n=26):
        """Front and back half of the meridian at `lon` (each always a semicircle)."""
        # z along the meridian: z(t) with lat=t; find where it crosses zero
        def z(t):
            return self.project(t, lon)[2]
        # sample the full great circle t in [-pi, pi) (lat beyond +-pi/2 runs over the pole)
        def pt(t):
            # a great circle through the poles: lat = t, but past the pole the longitude flips
            if t > math.pi / 2:
                return self.project(math.pi - t, lon + math.pi)
            if t < -math.pi / 2:
                return self.project(-math.pi - t, lon + math.pi)
            return self.project(t, lon)
        # find t0 where depth goes from negative to positive
        best, steps = None, 720
        prev = pt(-math.pi)[2]
        for i in range(1, steps + 1):
            t = -math.pi + 2 * math.pi * i / steps
            cur = pt(t)[2]
            if prev <= 0 < cur:
                best = t
                break
            prev = cur
        if best is None:
            best = 0.0
        front = [pt(best + math.pi * k / (n - 1))[:2] for k in range(n)]
        back = [pt(best + math.pi + math.pi * k / (n - 1))[:2] for k in range(n)]
        return front, back

    def parallel(self, lat, n=90):
        pts = [self.project(lat, 2 * math.pi * k / n) for k in range(n + 1)]
        front, back, cur, cur_side = [], [], [], None
        for x, y, z in pts:
            side = z >= 0
            if cur_side is None or side == cur_side:
                cur.append((x, y))
            else:
                (front if cur_side else back).append(cur)
                cur = [cur[-1], (x, y)]
            cur_side = side
        (front if cur_side else back).append(cur)
        return front, back


def globe_layers(g, meridians=14, frames=10, seg_dur=4.0, spin=1):
    """Animated meridians: rotating by one meridian spacing per loop gives a seamless spin."""
    step = 2 * math.pi / meridians
    fronts, backs = [], []
    for m in range(meridians):
        fr, bk = [], []
        for k in range(frames + 1):
            lon = m * step + spin * step * k / frames
            a, b = g.meridian_halves(lon)
            fr.append(path(a))
            bk.append(path(b))
        fronts.append(fr)
        backs.append(bk)

    def anim(ds):
        return f'<animate attributeName="d" dur="{seg_dur}s" repeatCount="indefinite" values="{";".join(ds)}"/>'

    back = ''.join(f'<path d="{bk[0]}">{anim(bk)}</path>' for bk in backs)
    front = ''.join(f'<path d="{fr[0]}">{anim(fr)}</path>' for fr in fronts)
    pf, pb = '', ''
    for lat in (-60, -30, 0, 30, 60):
        a, b = g.parallel(math.radians(lat))
        pf += ''.join(f'<path d="{path(s)}"/>' for s in a if len(s) > 1)
        pb += ''.join(f'<path d="{path(s)}"/>' for s in b if len(s) > 1)
    return back + pb, front + pf


def surface_points(g, count, full_dur, frames=72, seed=3):
    """Glowing data points riding on the globe; hidden behind it, bright in front."""
    rnd = random.Random(seed)
    out = ''
    for i in range(count):
        lat = math.radians(rnd.uniform(-55, 60))
        lon0 = rnd.uniform(0, 2 * math.pi)
        xs, ys, ops, rs = [], [], [], []
        for k in range(frames + 1):
            x, y, z = g.project(lat, lon0 + 2 * math.pi * k / frames)
            xs.append(f(x)); ys.append(f(y))
            o = max(0.0, min(1.0, z * 3 + 0.15))
            ops.append(f'{o:.2f}')
            rs.append(f'{2.2 + 1.6 * max(z, 0):.2f}')
        col = [CYAN, PINK, AMBER, '#A7F3D0'][i % 4]
        anims = (
            f'<animate attributeName="cx" dur="{full_dur}s" repeatCount="indefinite" values="{";".join(xs)}"/>'
            f'<animate attributeName="cy" dur="{full_dur}s" repeatCount="indefinite" values="{";".join(ys)}"/>'
            f'<animate attributeName="opacity" dur="{full_dur}s" repeatCount="indefinite" values="{";".join(ops)}"/>'
            f'<animate attributeName="r" dur="{full_dur}s" repeatCount="indefinite" values="{";".join(rs)}"/>'
        )
        out += f'<circle cx="{xs[0]}" cy="{ys[0]}" r="3" fill="{col}" filter="url(#glow)">{anims}</circle>'
    return out


def orbit(g, radius_k, incline_deg, node_deg, dur, color, frames=72, phase=0.0, sat_r=4.5):
    """A tilted orbit ring around the globe with a satellite that passes behind it."""
    inc, node = math.radians(incline_deg), math.radians(node_deg)

    def point(t):
        # circle in the orbit plane, rotated by inclination and node, then the globe's view tilt
        x = math.cos(t) * radius_k
        z = math.sin(t) * radius_k
        y = z * math.sin(inc)
        z = z * math.cos(inc)
        x, z = x * math.cos(node) - z * math.sin(node), x * math.sin(node) + z * math.cos(node)
        y2 = y * math.cos(g.tilt) - z * math.sin(g.tilt)
        z2 = y * math.sin(g.tilt) + z * math.cos(g.tilt)
        return g.cx + g.r * x, g.cy - g.r * y2, z2

    ring = [point(2 * math.pi * k / 160) for k in range(161)]
    front, back, cur, side = [], [], [], None
    for x, y, z in ring:
        s = z >= 0
        if side is None or s == side:
            cur.append((x, y))
        else:
            (front if side else back).append(cur)
            cur = [cur[-1], (x, y)]
        side = s
    (front if side else back).append(cur)

    xs, ys, ops = [], [], []
    for k in range(frames + 1):
        t = phase + 2 * math.pi * k / frames
        x, y, z = point(t)
        xs.append(f(x)); ys.append(f(y))
        # behind the globe disc -> hidden
        behind = z < 0 and math.hypot(x - g.cx, y - g.cy) < g.r
        ops.append('0' if behind else '1')
    sat = (
        f'<g><circle r="{sat_r}" fill="{color}" filter="url(#glow)">'
        f'<animate attributeName="cx" dur="{dur}s" repeatCount="indefinite" values="{";".join(xs)}"/>'
        f'<animate attributeName="cy" dur="{dur}s" repeatCount="indefinite" values="{";".join(ys)}"/>'
        f'<animate attributeName="opacity" dur="{dur}s" repeatCount="indefinite" calcMode="discrete" values="{";".join(ops)}"/>'
        f'</circle></g>'
    )
    back_d = ''.join(f'<path d="{path(s)}"/>' for s in back if len(s) > 1)
    front_d = ''.join(f'<path d="{path(s)}"/>' for s in front if len(s) > 1)
    return (
        f'<g fill="none" stroke="{color}" stroke-width="1.2" opacity=".28">{back_d}</g>',
        f'<g fill="none" stroke="{color}" stroke-width="1.6" opacity=".85">{front_d}</g>',
        sat,
    )


def stars(w, h, n, seed=5):
    rnd = random.Random(seed)
    out = ''
    for _ in range(n):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        r = rnd.choice([0.6, 0.8, 1.0, 1.3])
        d = rnd.uniform(2.5, 6)
        b = rnd.uniform(0, 5)
        out += (
            f'<circle cx="{f(x)}" cy="{f(y)}" r="{r}" fill="#fff">'
            f'<animate attributeName="opacity" values=".15;.9;.15" dur="{d:.1f}s" begin="{b:.1f}s" repeatCount="indefinite"/></circle>'
        )
    return out


DEFS = f'''
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="softglow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="6"/></filter>
<filter id="blur40"><feGaussianBlur stdDeviation="40"/></filter>
<linearGradient id="wire" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset=".55" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>
<radialGradient id="body" cx=".38" cy=".32" r=".75"><stop offset="0" stop-color="#2A2470"/><stop offset=".55" stop-color="#14123A"/><stop offset="1" stop-color="#07071A"/></radialGradient>
<radialGradient id="rim" cx=".5" cy=".5" r=".5"><stop offset=".82" stop-color="{VIOLET}" stop-opacity="0"/><stop offset=".97" stop-color="{CYAN}" stop-opacity=".55"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>
<linearGradient id="name" x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
  <stop offset="0" stop-color="#FFFFFF"/><stop offset=".35" stop-color="{CYAN}"/><stop offset=".65" stop-color="{VIOLET}"/><stop offset="1" stop-color="#FFFFFF"/>
  <animateTransform attributeName="gradientTransform" type="translate" values="-1 0;1 0" dur="6s" repeatCount="indefinite"/>
</linearGradient>
<linearGradient id="nameBase" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#C7D2FE"/></linearGradient>
'''


def hero():
    W, H = 1200, 440
    g = Globe(905, 220, 150, tilt_deg=23)
    back_lines, front_lines = globe_layers(g, meridians=14, frames=10, seg_dur=3.2)
    o1 = orbit(g, 1.42, 72, 25, 14, CYAN, phase=0.4)
    o2 = orbit(g, 1.68, 58, -40, 22, AMBER, phase=2.2, sat_r=3.8)
    o3 = orbit(g, 1.25, 84, 110, 10, PINK, phase=4.0, sat_r=3.4)
    points = surface_points(g, 9, full_dur=round(3.2 * 14, 1))

    roles = ['Full-stack engineer', 'FinTech &amp; trading systems', 'AI · Data · Automation']
    role_dur = 9
    role_svg = ''
    n = len(roles)
    fade = 0.03
    for i, text in enumerate(roles):
        start, end = i / n, (i + 1) / n
        if i == 0:
            kt, vals = f'0;{end - fade:.3f};{end:.3f};{1 - fade:.3f};1', '1;1;0;0;1'
        else:
            kt = f'0;{start - fade:.3f};{start:.3f};{end - fade:.3f};{end:.3f};1' if end < 1 else f'0;{start - fade:.3f};{start:.3f};{end - fade:.3f};1'
            vals = '0;0;1;1;0;0' if end < 1 else '0;0;1;1;0'
        role_svg += (
            f'<text x="0" y="0" opacity="{1 if i == 0 else 0}">{text}'
            f'<animate attributeName="opacity" dur="{role_dur}s" repeatCount="indefinite" keyTimes="{kt}" values="{vals}"/></text>'
        )

    chips = ['Next.js', 'Python', 'TypeScript', 'AI / ML', 'Trading APIs']
    chip_svg, x = '', 0
    for c in chips:
        w = 18 + 8.2 * len(c)
        chip_svg += (
            f'<g transform="translate({f(x)},0)"><rect width="{f(w)}" height="30" rx="15" fill="#ffffff" fill-opacity=".06" stroke="#ffffff" stroke-opacity=".14"/>'
            f'<text x="{f(w / 2)}" y="20" text-anchor="middle">{c}</text></g>'
        )
        x += w + 10

    blobs = (
        f'<g filter="url(#blur40)" opacity=".55">'
        f'<circle cx="250" cy="120" r="170" fill="{VIOLET}"><animateTransform attributeName="transform" type="translate" values="0 0;60 30;0 0" dur="18s" repeatCount="indefinite"/></circle>'
        f'<circle cx="620" cy="380" r="150" fill="#0EA5E9" opacity=".7"><animateTransform attributeName="transform" type="translate" values="0 0;-50 -30;0 0" dur="22s" repeatCount="indefinite"/></circle>'
        f'<circle cx="980" cy="90" r="140" fill="{PINK}" opacity=".45"><animateTransform attributeName="transform" type="translate" values="0 0;-40 40;0 0" dur="16s" repeatCount="indefinite"/></circle>'
        f'</g>'
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Het Kothari. Full-stack engineer building FinTech, AI and automation systems.">
<defs>{DEFS}
<clipPath id="frame"><rect width="{W}" height="{H}" rx="28"/></clipPath>
<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#ffffff" stroke-opacity=".045"/></pattern>
</defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="#06060F"/>
{blobs}
<rect width="{W}" height="{H}" fill="url(#grid)"/>
{stars(W, H, 70)}

<!-- globe -->
{o1[0]}{o2[0]}{o3[0]}
<g fill="none" stroke="url(#wire)" stroke-width="1" opacity=".22">{back_lines}</g>
<circle cx="{g.cx}" cy="{g.cy}" r="{g.r + 18}" fill="{VIOLET}" opacity=".25" filter="url(#softglow)"/>
<circle cx="{g.cx}" cy="{g.cy}" r="{g.r}" fill="url(#body)" opacity=".92"/>
<g fill="none" stroke="url(#wire)" stroke-width="1.4" stroke-linecap="round" opacity=".9">{front_lines}</g>
<circle cx="{g.cx}" cy="{g.cy}" r="{g.r + 4}" fill="url(#rim)"/>
{points}
{o1[1]}{o2[1]}{o3[1]}
{o1[2]}{o2[2]}{o3[2]}

<!-- text -->
<g font-family="{MONO}" font-size="15" fill="{CYAN}" letter-spacing="3">
  <text x="72" y="118">&gt; HELLO WORLD, I AM<tspan fill="{CYAN}"><animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/>_</tspan></text>
</g>
<text x="68" y="200" font-family="{FONT}" font-size="82" font-weight="800" letter-spacing="-2" fill="url(#nameBase)">Het Kothari</text>
<text x="68" y="200" font-family="{FONT}" font-size="82" font-weight="800" letter-spacing="-2" fill="url(#name)" opacity=".9">Het Kothari</text>
<g transform="translate(72,252)" font-family="{FONT}" font-size="27" font-weight="600" fill="{INK}">
  <rect x="-2" y="-22" width="4" height="28" rx="2" fill="{AMBER}"/>
  <g transform="translate(16,0)">{role_svg}</g>
</g>
<text x="72" y="300" font-family="{FONT}" font-size="17" fill="#9AA4B2">I build production systems where data, money and automation meet.</text>
<g transform="translate(72,330)" font-family="{FONT}" font-size="13.5" font-weight="600" fill="#C9D1D9">{chip_svg}</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="27" fill="none" stroke="#ffffff" stroke-opacity=".08"/>
</g>
</svg>'''
    open(os.path.join(OUT, 'hero.svg'), 'w', encoding='utf-8').write(svg)
    return len(svg)


# --------------------------------------------------------------------------- data cube
def cube():
    W = H = 360
    cx, cy, s = W / 2, H / 2 - 8, 78
    pts = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if sum(1 for i in range(3) if pts[a][i] != pts[b][i]) == 1]
    tilt = math.radians(-28)
    frames, dur = 24, 8.0

    def proj(p, ang, scale):
        x, y, z = p
        x, z = x * math.cos(ang) - z * math.sin(ang), x * math.sin(ang) + z * math.cos(ang)
        y, z = y * math.cos(tilt) - z * math.sin(tilt), y * math.sin(tilt) + z * math.cos(tilt)
        k = 3.6 / (3.6 + z * 0.55)  # perspective
        return cx + x * scale * k, cy + y * scale * k

    def cube_paths(scale, spin_dir, inner=False):
        per_edge = []
        for a, b in edges:
            vals = []
            for k in range(frames + 1):
                ang = spin_dir * (math.pi / 2) * k / frames + math.radians(20)
                (x1, y1), (x2, y2) = proj(pts[a], ang, scale), proj(pts[b], ang, scale)
                vals.append(f'M{f(x1)} {f(y1)} L{f(x2)} {f(y2)}')
            per_edge.append(f'<path d="{vals[0]}"><animate attributeName="d" dur="{dur}s" repeatCount="indefinite" values="{";".join(vals)}"/></path>')
        return ''.join(per_edge)

    def verts(scale, spin_dir, color):
        out = ''
        for p in pts:
            xs, ys = [], []
            for k in range(frames + 1):
                ang = spin_dir * (math.pi / 2) * k / frames + math.radians(20)
                x, y = proj(p, ang, scale)
                xs.append(f(x)); ys.append(f(y))
            out += (f'<circle r="3.4" fill="{color}" filter="url(#glow)">'
                    f'<animate attributeName="cx" dur="{dur}s" repeatCount="indefinite" values="{";".join(xs)}"/>'
                    f'<animate attributeName="cy" dur="{dur}s" repeatCount="indefinite" values="{";".join(ys)}"/></circle>')
        return out

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Rotating 3D data cube">
<defs>{DEFS}<clipPath id="frame"><rect width="{W}" height="{H}" rx="28"/></clipPath></defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="#06060F"/>
<g filter="url(#blur40)" opacity=".5"><circle cx="120" cy="110" r="110" fill="{VIOLET}"/><circle cx="260" cy="270" r="100" fill="#0EA5E9" opacity=".7"/></g>
{stars(W, H, 26, seed=11)}
<ellipse cx="{cx}" cy="{H - 46}" rx="110" ry="16" fill="{CYAN}" opacity=".14" filter="url(#softglow)"/>
<g fill="none" stroke="url(#wire)" stroke-width="1.6" stroke-linecap="round">{cube_paths(s * 1.0, 1)}</g>
<g fill="none" stroke="{AMBER}" stroke-width="1.3" opacity=".9">{cube_paths(s * 0.48, -1, True)}</g>
{verts(s * 1.0, 1, CYAN)}{verts(s * 0.48, -1, AMBER)}
<text x="{cx}" y="{H - 22}" text-anchor="middle" font-family="{MONO}" font-size="12" letter-spacing="3" fill="#8B949E">DATA · MODELS · MARKETS</text>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="27" fill="none" stroke="#ffffff" stroke-opacity=".08"/>
</g></svg>'''
    open(os.path.join(OUT, 'cube.svg'), 'w', encoding='utf-8').write(svg)
    return len(svg)


# --------------------------------------------------------------------------- section headers
def heading(name, label, index):
    """Section header on its own dark strip, so it reads on GitHub's light and dark themes."""
    W, H = 1200, 76
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">
<defs><linearGradient id="l" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset=".5" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PINK}" stop-opacity="0"/></linearGradient>
<linearGradient id="pulse" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<clipPath id="c"><rect width="{W}" height="{H}" rx="18"/></clipPath></defs>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="#06060F"/>
<circle cx="80" cy="0" r="90" fill="{VIOLET}" opacity=".18"/>
<text x="28" y="46" font-family="{MONO}" font-size="15" fill="{CYAN}" letter-spacing="2">{index:02d} /</text>
<text x="88" y="48" font-family="{FONT}" font-size="28" font-weight="800" fill="{INK}">{label}</text>
<rect x="0" y="{H - 3}" width="{W}" height="3" fill="url(#l)" opacity=".8"/>
<rect x="0" y="{H - 4}" width="160" height="4" rx="2" fill="url(#pulse)"><animate attributeName="x" values="-160;{W}" dur="4.5s" begin="{index * .6:.1f}s" repeatCount="indefinite"/></rect>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="17.5" fill="none" stroke="#ffffff" stroke-opacity=".08"/>
</g></svg>'''
    open(os.path.join(OUT, f'h-{name}.svg'), 'w', encoding='utf-8').write(svg)


# --------------------------------------------------------------------------- footer
def footer():
    W, H = 1200, 200

    def wave(amp, length, y):
        pts = [(i, y + amp * math.sin(2 * math.pi * i / length)) for i in range(-length, W + length + 1, 10)]
        return path(pts) + f' L{W + length} {H} L{-length} {H} Z'

    layers = ''
    for col, op, amp, ln, y, dur in [(VIOLET, .45, 22, 520, 92, 8), (CYAN, .35, 18, 380, 112, 6), ('#0B0B1A', 1, 14, 460, 140, 10)]:
        layers += (f'<path fill="{col}" opacity="{op}" d="{wave(amp, ln, y)}">'
                   f'<animateTransform attributeName="transform" type="translate" values="0 0;{ln} 0" dur="{dur}s" repeatCount="indefinite"/></path>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Thanks for visiting">
<defs>{DEFS}<clipPath id="frame"><rect width="{W}" height="{H}" rx="28"/></clipPath></defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="#06060F"/>
{stars(W, 110, 40, seed=21)}
{layers}
<text x="{W / 2}" y="60" text-anchor="middle" font-family="{FONT}" font-size="26" font-weight="800" fill="url(#nameBase)">Thanks for stopping by</text>
<text x="{W / 2}" y="60" text-anchor="middle" font-family="{FONT}" font-size="26" font-weight="800" fill="url(#name)" opacity=".85">Thanks for stopping by</text>
<text x="{W / 2}" y="176" text-anchor="middle" font-family="{MONO}" font-size="13" letter-spacing="3" fill="#C9D1D9" opacity=".8">BUILD SYSTEMS, NOT SCRIPTS</text>
</g></svg>'''
    open(os.path.join(OUT, 'footer.svg'), 'w', encoding='utf-8').write(svg)


if __name__ == '__main__':
    print('hero', hero())
    print('cube', cube())
    for i, (n, l) in enumerate([('about', 'About me'), ('stack', 'Tech stack'), ('work', 'Featured work'), ('activity', 'Activity in 3D'), ('stats', 'GitHub stats'), ('connect', "Let's connect")], 1):
        heading(n, l, i)
    footer()
    print('ok')
