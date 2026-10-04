# Regenerates the SVG artwork in assets/ (cards, stats strip, section headers). Run: python assets/generate_assets.py
import os
A='/home/user/cdth/assets'
SANS="font-family=\"'Segoe UI',Inter,Helvetica,Arial,sans-serif\""
MONO="font-family=\"'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace\""
BG='#07090D'; INK='#E8ECEF'; MUTED='#8A96A3'; CORAL='#FF5A4E'; AUR='#2FD8A0'

def aurora(w,h,c1,c2,seed=0,anim=True):
    # vertical light curtains
    import random; r=random.Random(seed); s=[]
    for i in range(46):
        x=r.uniform(0,w); bw=r.uniform(6,26); top=r.uniform(-20,h*0.25); bh=r.uniform(h*0.35,h*0.8)
        col=c1 if r.random()<0.8 else c2; op=r.uniform(0.06,0.22)
        dur=r.uniform(4,9); d=r.uniform(0,4)
        a=f'<animate attributeName="opacity" values="{op:.2f};{op*0.35:.2f};{op:.2f}" dur="{dur:.1f}s" begin="-{d:.1f}s" repeatCount="indefinite"/>' if anim else ''
        s.append(f'<rect x="{x:.0f}" y="{top:.0f}" width="{bw:.0f}" height="{bh:.0f}" fill="{col}" opacity="{op:.2f}" filter="url(#blur)">{a}</rect>')
    return '\n'.join(s)

def stars(w,h,n,seed):
    import random; r=random.Random(seed)
    return ''.join(f'<circle cx="{r.uniform(0,w):.0f}" cy="{r.uniform(0,h*0.6):.0f}" r="{r.uniform(0.4,1.1):.1f}" fill="#fff" opacity="{r.uniform(0.15,0.6):.2f}"/>' for _ in range(n))

ICONS={
'ship':'''<path d="M-46 14 L46 14 L34 34 L-36 34 Z" /><path d="M-26 14 V-4 H14 V14" /><path d="M-8 -4 V-22 H6 V-4"/>
 <path d="M-62 46 q10 -8 20 0 t20 0 t20 0 t20 0 t20 0 t20 0" opacity=".6"/>
 <path d="M30 -40 a40 40 0 0 1 40 40" opacity=".5"/><path d="M30 -58 a58 58 0 0 1 58 58" opacity=".3"/>''',
'drone':'''<rect x="-14" y="-10" width="28" height="20" rx="5"/><path d="M-14 -6 L-42 -30 M14 -6 L42 -30 M-14 6 L-42 30 M14 6 L42 30"/>
 <ellipse cx="-42" cy="-30" rx="18" ry="4"/><ellipse cx="42" cy="-30" rx="18" ry="4"/><ellipse cx="-42" cy="30" rx="18" ry="4"/><ellipse cx="42" cy="30" rx="18" ry="4"/>
 <circle cx="0" cy="0" r="62" stroke-dasharray="4 7" opacity=".45"/><path d="M-70 0 H-56 M56 0 H70 M0 -70 V-56 M0 56 V70" opacity=".6"/>''',
'sat':'''<rect x="-10" y="-10" width="20" height="20" transform="rotate(45)"/><rect x="-54" y="-9" width="34" height="18"/><rect x="20" y="-9" width="34" height="18"/>
 <path d="M-37 -9 V9 M37 -9 V9"/><path d="M0 14 V26"/>
 <path d="M-22 44 a32 32 0 0 0 44 0" opacity=".8"/><path d="M-36 56 a52 52 0 0 0 72 0" opacity=".5"/><path d="M-50 68 a72 72 0 0 0 100 0" opacity=".3"/>''',
'fire':'''<path d="M0 -50 C 22 -22 40 -8 36 18 C 32 42 14 52 0 52 C -14 52 -32 42 -36 18 C -40 -4 -22 -14 -14 -34 C -8 -18 -4 -12 0 -10 C 4 -22 4 -36 0 -50 Z"/>
 <path d="M0 6 C 10 18 16 28 12 38 C 8 46 -8 46 -12 38 C -16 28 -8 20 0 6 Z" opacity=".7"/>
 <path d="M-70 64 H70" opacity=".5"/><path d="M-56 64 v-10 h10 v10 M40 64 v-14 h12 v14" opacity=".5"/>''',
}

def card(fn,num,title,theme,data,tasks,icon,c1,c2,seed):
    W,H=1000,280
    chips=[]; y=148
    for code,txt in tasks:
        chips.append(f'''<g transform="translate(300,{y})"><rect width="{56}" height="26" rx="13" fill="{c1}" fill-opacity=".16" stroke="{c1}" stroke-opacity=".55"/>
<text x="28" y="18" text-anchor="middle" {MONO} font-size="13" font-weight="700" fill="{c1}">{code}</text>
<text x="70" y="18" {SANS} font-size="16" fill="{INK}">{txt}</text></g>''')
        y+=36
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
 <linearGradient id="cur" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity="0"/><stop offset=".55" stop-color="currentColor"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient>
 <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
 <radialGradient id="glow" cx="0.13" cy="0.5" r="0.32"><stop offset="0" stop-color="{c1}" stop-opacity=".30"/><stop offset="1" stop-color="{c1}" stop-opacity="0"/></radialGradient>
 <linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="{BG}" stop-opacity="0"/><stop offset=".22" stop-color="{BG}" stop-opacity=".45"/><stop offset="1" stop-color="{BG}" stop-opacity=".8"/></linearGradient>
 <linearGradient id="edge" x1="0" x2="1"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}" stop-opacity=".2"/></linearGradient>
 <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#fff" stroke-opacity=".035"/></pattern>
 <clipPath id="clip"><rect width="{W}" height="{H}" rx="18"/></clipPath>
</defs>
<g clip-path="url(#clip)">
 <rect width="{W}" height="{H}" fill="{BG}"/>
 <rect width="{W}" height="{H}" fill="url(#grid)"/>
 {stars(W,H,60,seed)}
 <g>{aurora(W,H,c1,c2,seed)}</g>
 <rect width="{W}" height="{H}" fill="url(#fade)"/>
 <rect width="{W}" height="{H}" fill="url(#glow)"/>
 <rect width="{W}" height="4" fill="url(#edge)"/>
 <g transform="translate(140,145)" fill="none" stroke="{c1}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>
 <text x="140" y="262" text-anchor="middle" {MONO} font-size="13" letter-spacing="3" fill="{MUTED}">CHALLENGE {num}</text>
 <text x="300" y="58" {MONO} font-size="14" letter-spacing="4" fill="{c1}">{theme.upper()}</text>
 <text x="298" y="104" {SANS} font-size="42" font-weight="800" letter-spacing="-0.5" fill="{INK}">{title}</text>
 <text x="300" y="132" {SANS} font-size="15" fill="{MUTED}">{data}</text>
 {''.join(chips)}
 <text x="972" y="262" text-anchor="end" {MONO} font-size="13" fill="{c1}" opacity=".9">OPEN DATASHEET →</text>
 <rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="17.5" fill="none" stroke="#fff" stroke-opacity=".08" stroke-width="1.5"/>
</g></svg>'''
    open(f'{A}/cards/{fn}.svg','w').write(svg)

card('01_arctic_watch','01','Arctic Watch','Maritime awareness · Canadian Arctic',
 '14 days of AIS on real Arctic routes · SAR detections · areas of interest',
 [('1A','Tell AIS ships, dark ships and clutter apart in SAR'),('1B','Flag AIS gaps, spoofing, rendezvous, MMSI cloning')],'ship','#5CC8FF','#2FD8A0',1)
card('02_eyes_on_the_sky','02','Eyes on the Sky','Airspace awareness · Counter-drone',
 '7 days of fused radar, RF-DF, ADS-B, acoustic and camera tracks · 3 Edmonton sites',
 [('2A','Drone, bird, manned aircraft or other?'),('2B','Alert on unauthorized drones in protected zones'),('2C','Find the pilot')],'drone','#2FD8A0','#5CC8FF',2)
card('03_stay_connected','03','Stay Connected','Resilient PNT · GNSS',
 '7 days of GNSS logs from fixed stations, vehicles and aircraft · central Alberta',
 [('3A','Nominal, natural, jamming or spoofing?'),('3B','Locate the interference source'),('3C','Recover the true position while spoofed')],'sat','#B48CFF','#2FD8A0',3)
card('04_ready_and_resilient','04','Ready and Resilient','Emergency response · Wildfire',
 'Two wildfire scenarios on real roads, communities, aerodromes and fuel types',
 [('4A','Which communities will the fire threaten?'),('4B','Plan the evacuation, scored by a simulator'),('4C','Nowcast the fire perimeter')],'fire','#FF7A45','#FF5A4E',4)

# stats strip
W,H=1000,150
items=[('4','PRACTICE CHALLENGES',CORAL),('11','SCORED TASKS',AUR),('11','REFERENCE LAYERS','#5CC8FF'),('69','PUBLIC DATASETS',INK)]
cells=''
for i,(n,l,c) in enumerate(items):
    cx=125+i*250
    cells+=f'<text x="{cx}" y="82" text-anchor="middle" {SANS} font-size="60" font-weight="800" fill="{c}">{n}</text><text x="{cx}" y="114" text-anchor="middle" {MONO} font-size="13" letter-spacing="3" fill="{MUTED}">{l}</text>'
    if i: cells+=f'<line x1="{i*250}" y1="34" x2="{i*250}" y2="116" stroke="#fff" stroke-opacity=".08"/>'
open(f'{A}/stats.svg','w').write(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><linearGradient id="cur" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity="0"/><stop offset=".55" stop-color="currentColor"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient>
<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>
<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}" stop-opacity=".25"/><stop offset="1" stop-color="{BG}" stop-opacity=".8"/></linearGradient>
<clipPath id="clip"><rect width="{W}" height="{H}" rx="18"/></clipPath></defs>
<g clip-path="url(#clip)"><rect width="{W}" height="{H}" fill="{BG}"/>{stars(W,H,50,9)}<g>{aurora(W,H,AUR,CORAL,9)}</g><rect width="{W}" height="{H}" fill="url(#fade)"/>{cells}
<rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="17.5" fill="none" stroke="#fff" stroke-opacity=".08" stroke-width="1.5"/></g></svg>''')

# section headers
def header(fn,eyebrow,title,c,seed):
    W,H=1000,96
    open(f'{A}/headers/{fn}.svg','w').write(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><linearGradient id="cur" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity="0"/><stop offset=".55" stop-color="currentColor"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient>
<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8"/></filter>
<linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="{BG}" stop-opacity=".96"/><stop offset=".45" stop-color="{BG}" stop-opacity=".75"/><stop offset="1" stop-color="{BG}" stop-opacity=".15"/></linearGradient>
<clipPath id="clip"><rect width="{W}" height="{H}" rx="14"/></clipPath></defs>
<g clip-path="url(#clip)"><rect width="{W}" height="{H}" fill="{BG}"/>{stars(W,H,30,seed)}<g>{aurora(W,H,c,AUR,seed)}</g><rect width="{W}" height="{H}" fill="url(#fade)"/>
<rect x="0" y="0" width="5" height="{H}" fill="{c}"/>
<text x="34" y="36" {MONO} font-size="13" letter-spacing="4" fill="{c}">{eyebrow}</text>
<text x="32" y="74" {SANS} font-size="32" font-weight="800" letter-spacing="-0.3" fill="{INK}">{title}</text>
<rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="13.5" fill="none" stroke="#fff" stroke-opacity=".08" stroke-width="1.5"/></g></svg>''')
os.makedirs(f'{A}/headers',exist_ok=True)
for k,(fn,e,t,c) in enumerate([('quickstart','01 — GET GOING','Quick start',CORAL),('challenges','02 — THE MISSIONS','The four challenges',AUR),
                 ('scoring','03 — FAIR PLAY','How scoring works','#5CC8FF'),('data','04 — FIELD NOTES','Working with the data','#B48CFF'),
                 ('licence','05 — THE FINE PRINT','Licence and questions',CORAL)]):
    header(fn,e,t,c,20+k)
