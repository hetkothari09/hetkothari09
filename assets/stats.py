"""Draw the profile's GitHub stats card from the GitHub API (no third-party service).

Run by the "Profile art" workflow:  GITHUB_TOKEN=... python assets/stats.py <user> assets/stats.svg
"""
import json, math, os, sys, urllib.request
from datetime import date

USER = sys.argv[1] if len(sys.argv) > 1 else 'hetkothari09'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'assets/stats.svg'
TOKEN = os.environ['GITHUB_TOKEN']

CYAN, VIOLET, PINK, AMBER, INK = '#22D3EE', '#8B5CF6', '#EC4899', '#F59E0B', '#E6EDF3'
FONT = "'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', 'Fira Code', Consolas, 'Courier New', monospace"

QUERY = '''
query($login: String!, $after: String) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        forkCount
        languages(first: 10, orderBy: { field: SIZE, direction: DESC }) { edges { size node { name color } } }
      }
    }
  }
}'''


def gql(variables):
    req = urllib.request.Request(
        'https://api.github.com/graphql',
        data=json.dumps({'query': QUERY, 'variables': variables}).encode(),
        headers={'Authorization': f'bearer {TOKEN}', 'Content-Type': 'application/json', 'User-Agent': 'profile-stats'},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if 'errors' in body:
        raise SystemExit(body['errors'])
    return body['data']['user']


def fetch():
    first = gql({'login': USER, 'after': None})
    repos = list(first['repositories']['nodes'])
    page = first['repositories']['pageInfo']
    while page['hasNextPage']:
        nxt = gql({'login': USER, 'after': page['endCursor']})
        repos += nxt['repositories']['nodes']
        page = nxt['repositories']['pageInfo']
    return first, repos


def streaks(days):
    today = date.today().isoformat()
    counts = [(d['date'], d['contributionCount']) for d in days if d['date'] <= today]
    longest = cur = 0
    for _, c in counts:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)
    current = 0
    for i, (d, c) in enumerate(reversed(counts)):
        if c > 0:
            current += 1
        elif i == 0:
            continue  # today without contributions yet does not break the streak
        else:
            break
    return current, longest


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def main():
    user, repos = fetch()
    cc = user['contributionsCollection']
    weeks = cc['contributionCalendar']['weeks']
    days = [d for w in weeks for d in w['contributionDays']]
    current, longest = streaks(days)
    stars = sum(r['stargazerCount'] for r in repos)
    langs = {}
    for r in repos:
        for e in r['languages']['edges']:
            n = e['node']['name']
            langs.setdefault(n, [0, e['node']['color'] or '#8B949E'])
            langs[n][0] += e['size']
    total = sum(v[0] for v in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]

    W, H = 1200, 360
    metrics = [
        ('Contributions', cc['contributionCalendar']['totalContributions'], 'last 12 months', CYAN),
        ('Commits', cc['totalCommitContributions'] + cc['restrictedContributionsCount'], 'last 12 months', VIOLET),
        ('Current streak', current, 'days', AMBER),
        ('Longest streak', longest, 'days', PINK),
        ('Repositories', user['repositories']['totalCount'], 'public, own', CYAN),
        ('Pull requests', user['pullRequests']['totalCount'], 'all time', VIOLET),
        ('Active days', sum(1 for d in days if d['contributionCount'] > 0), 'last 12 months', AMBER),
        ('Languages', len(langs), 'written in', PINK),
    ]
    tiles = ''
    for i, (label, value, sub, col) in enumerate(metrics):
        x = 40 + (i % 4) * 172
        y = 92 + (i // 4) * 118
        delay = 0.08 * i
        tiles += f'''<g transform="translate({x},{y})" opacity="0">
<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur=".6s" fill="freeze"/>
<animateTransform attributeName="transform" type="translate" from="{x},{y + 14}" to="{x},{y}" begin="{delay:.2f}s" dur=".6s" fill="freeze"/>
<rect width="160" height="104" rx="16" fill="#ffffff" fill-opacity=".04" stroke="#ffffff" stroke-opacity=".09"/>
<rect x="16" y="16" width="22" height="3" rx="1.5" fill="{col}"/>
<text x="16" y="58" font-family="{FONT}" font-size="34" font-weight="800" fill="{INK}">{value:,}</text>
<text x="16" y="80" font-family="{FONT}" font-size="13" font-weight="600" fill="#C9D1D9">{label}</text>
<text x="16" y="95" font-family="{MONO}" font-size="10" fill="#8B949E">{sub}</text>
</g>'''

    # languages: stacked bar + legend
    lx, ly, lw = 760, 96, 400
    bar, legend, acc = '', '', 0.0
    for i, (name, (size, color)) in enumerate(top):
        share = size / total
        w = lw * share
        bar += (f'<rect x="{lx + acc:.1f}" y="{ly}" width="0" height="12" fill="{color}">'
                f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{.3 + .1 * i:.2f}s" dur=".9s" fill="freeze"/></rect>')
        acc += w
        cx = lx + (i % 2) * 200
        cy = ly + 42 + (i // 2) * 26
        legend += (f'<circle cx="{cx + 6}" cy="{cy - 4}" r="5" fill="{color}"/>'
                   f'<text x="{cx + 18}" y="{cy}" font-family="{FONT}" font-size="13.5" fill="#C9D1D9">{esc(name)}'
                   f'<tspan fill="#8B949E" font-family="{MONO}" font-size="11.5">  {share * 100:.1f}%</tspan></text>')

    # weekly contributions sparkline
    weekly = [sum(d['contributionCount'] for d in w['contributionDays']) for w in weeks][-52:]
    peak = max(weekly) or 1
    sx, sy, sw, sh = 760, 244, 400, 70
    pts = [(sx + sw * i / (len(weekly) - 1), sy + sh - sh * v / peak) for i, v in enumerate(weekly)]
    line = 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)
    area = line + f' L{sx + sw} {sy + sh} L{sx} {sy + sh} Z'
    length = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {USER}">
<defs>
<clipPath id="frame"><rect width="{W}" height="{H}" rx="28"/></clipPath>
<linearGradient id="spark" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset=".6" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>
<linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{VIOLET}" stop-opacity=".45"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></linearGradient>
<filter id="blur40"><feGaussianBlur stdDeviation="40"/></filter>
</defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="#06060F"/>
<g filter="url(#blur40)" opacity=".45"><circle cx="180" cy="60" r="140" fill="{VIOLET}"/><circle cx="1040" cy="320" r="140" fill="#0EA5E9"/></g>
<text x="40" y="58" font-family="{MONO}" font-size="13" letter-spacing="3" fill="{CYAN}">&gt; GITHUB.STATS(&quot;{USER}&quot;)</text>
<text x="760" y="58" font-family="{MONO}" font-size="13" letter-spacing="3" fill="{CYAN}">&gt; TOP LANGUAGES</text>
{tiles}
<rect x="{lx}" y="{ly}" width="{lw}" height="12" rx="6" fill="#ffffff" fill-opacity=".06"/>
{bar}
{legend}
<text x="{sx}" y="{sy - 14}" font-family="{MONO}" font-size="11" letter-spacing="2" fill="#8B949E">CONTRIBUTIONS PER WEEK · 52 WEEKS</text>
<path d="{area}" fill="url(#fill)" opacity="0"><animate attributeName="opacity" from="0" to="1" begin="1.2s" dur="1s" fill="freeze"/></path>
<path d="{line}" fill="none" stroke="url(#spark)" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}">
<animate attributeName="stroke-dashoffset" from="{length:.0f}" to="0" begin=".4s" dur="2.2s" fill="freeze"/></path>
<text x="{W - 40}" y="{H - 18}" text-anchor="end" font-family="{MONO}" font-size="10" fill="#6E7681">updated {date.today().isoformat()}</text>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="27" fill="none" stroke="#ffffff" stroke-opacity=".08"/>
</g></svg>'''
    open(OUT, 'w', encoding='utf-8').write(svg)
    print(f'wrote {OUT}: {len(svg)} bytes, {len(repos)} repos, {len(top)} languages')


if __name__ == '__main__':
    main()
