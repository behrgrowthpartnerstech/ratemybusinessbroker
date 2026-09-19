#!/usr/bin/env python3
"""
The Broker Index — page generator.
Generates: broker-<slug>.html (one per broker), business-brokers-in-<state>.html,
business-brokers-by-state.html, and sitemap.xml. All files land flat in the repo root.

Run locally:            python3 generate_pages.py --local brokers.json
Run in GitHub Actions:  python3 generate_pages.py --from-supabase
(the Action fetches the live broker list from Supabase, so newly added brokers
get pages automatically with zero manual work)
"""
import json, html, collections, sys, os, re, datetime, urllib.request

SUPABASE_URL = 'https://qnxmvzrotgnsgyafewbo.supabase.co'
SUPABASE_KEY = 'sb_publishable_jx_rlrzcPGOWtuimIAw2eA_l46TedX8'  # publishable: safe in public code
SITE = 'https://ratemybusinessbroker.com'
OUT = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()

STATES = {
'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado',
'CT':'Connecticut','DE':'Delaware','DC':'Washington, D.C.','FL':'Florida','GA':'Georgia','HI':'Hawaii',
'ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana',
'ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi',
'MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey',
'NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma',
'OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota',
'TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington',
'WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming'
}

def esc(s): return html.escape(s or '', quote=True)
def state_slug(name): return name.lower().replace(', d.c.','-dc').replace(' ','-').replace('.','').replace(',','')

def load_brokers():
    if '--from-supabase' in sys.argv:
        req = urllib.request.Request(
            SUPABASE_URL + '/rest/v1/brokers?select=slug,name,firm,city,state,specialty,photo,website,linkedin,logo,phone&order=name&limit=5000',
            headers={'apikey': SUPABASE_KEY, 'Authorization': 'Bearer ' + SUPABASE_KEY})
        rows = json.load(urllib.request.urlopen(req, timeout=60))
    else:
        src = sys.argv[sys.argv.index('--local')+1] if '--local' in sys.argv else 'brokers.json'
        rows = json.load(open(src))
    clean = []
    for b in rows:
        b = {k: (b.get(k) or '').strip() for k in ('slug','name','firm','city','state','specialty','photo','website','linkedin','logo','phone')}
        if b['slug'] and b['name'] and re.fullmatch(r'[a-z0-9\-]+', b['slug']):
            clean.append(b)
    return clean

# ---------------------------------------------------------------- shared shell
def head(title, desc, fname, jsonld='', ogimg=None, extra_css=''):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}/{fname}">
<link rel="icon" type="image/png" href="/favicon.png">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE}/{fname}">
<meta property="og:image" content="{esc(ogimg) if ogimg else SITE + '/favicon.png'}">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-KTQ1BWRBJC"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-KTQ1BWRBJC');</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,650&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/_shared.css">
<style>{extra_css}</style>
{jsonld}
</head>
<body>

<header>
  <div class="wrap hbar">
    <a class="brand" href="/"><span class="mark">B</span><b>The Broker Index</b></a>
    <span class="hspace"></span>
    <a class="hbtn" href="/articles.html">Articles</a>
    <a class="hbtn solid" href="/">Browse brokers</a>
  </div>
</header>
'''

FOOT = '''
<footer>
  <div class="wrap">
    <p><a href="/">The Broker Index</a> · <a href="/business-brokers-by-state.html">Brokers by state</a> · <a href="/business-valuation-calculator.html">Valuation calculator</a> · <a href="/methodology.html">Methodology</a> — Independent ratings and reviews of M&amp;A business brokers. Listing details compiled from publicly available directory information; corrections welcome via the request form on the home page.</p>
  </div>
</footer>
</body>
</html>
'''

GRID_CSS = '''
.bgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:16px;margin:24px 0 10px}
.bcard{background:var(--card);border:1px solid var(--line2);border-radius:14px;padding:16px;box-shadow:0 1px 2px rgba(16,28,44,.05)}
.bcard .top{display:flex;gap:12px;align-items:center}
.bcard img.face{width:52px;height:52px;border-radius:50%;object-fit:cover;border:1px solid var(--line2);flex:none;background:#eee}
.bcard .nm{font-weight:700;font-size:15.5px;line-height:1.3;color:var(--ink)}
.bcard .nm a{color:var(--ink)}
.bcard .fm{font-size:12.5px;color:var(--mut);margin-top:2px;line-height:1.35}
.bcard .meta{font-size:12.5px;color:var(--ink2);margin-top:10px;line-height:1.5}
.bcard .lnks{margin-top:10px;font-size:12.5px;display:flex;flex-wrap:wrap;gap:6px 14px}
.stgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin:24px 0}
.stgrid a{display:flex;justify-content:space-between;background:var(--card);border:1px solid var(--line2);border-radius:11px;padding:11px 14px;color:var(--ink);font-weight:600;font-size:14px}
.stgrid a:hover{text-decoration:none;border-color:var(--gold2)}
.stgrid span{color:var(--mut);font-weight:400}
.wide{max-width:1060px;margin:0 auto;padding:34px 20px 40px}
@media(max-width:600px){.wide{padding:24px 14px 32px}}
'''

PROFILE_CSS = '''
.phero{display:flex;gap:20px;align-items:flex-start;background:var(--card);border:1px solid var(--line2);border-radius:16px;padding:24px;margin:24px 0;box-shadow:0 1px 2px rgba(16,28,44,.06),0 10px 28px -14px rgba(16,28,44,.18)}
.phero img.face{width:96px;height:96px;border-radius:50%;object-fit:cover;border:1px solid var(--line2);flex:none;background:#eee}
.phero .ph{width:96px;height:96px;border-radius:50%;flex:none;background:var(--navy);color:#dfa920;display:grid;place-items:center;font-family:Fraunces,Georgia,serif;font-size:34px;font-weight:650}
.phero h1{font-size:clamp(24px,4vw,32px);margin:0}
.phero .firm{display:flex;align-items:center;gap:8px;margin-top:6px;color:var(--ink2);font-weight:600;font-size:15px}
.phero .firm img{max-height:26px;max-width:120px;object-fit:contain}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
.chip{background:var(--paper);border:1px solid var(--line2);border-radius:20px;padding:3px 12px;font-size:12.5px;color:var(--ink2)}
.chip.loc{background:#fdf8ec;border-color:#efe2bd;color:#7a5c07;font-weight:600}
.plinks{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:14px;font-size:14px;font-weight:600}
.live{background:var(--navy);border-radius:14px;color:#f2ede2;padding:20px 22px;margin:22px 0;font-size:15px}
.live a{color:#dfa920}
.live .bigscore{font-family:Fraunces,Georgia,serif;font-size:30px;font-weight:650;color:#dfa920;margin-right:4px}
.live .mnote{font-size:12.5px;color:rgba(242,237,226,.65);margin-top:10px}
.claim{border:1px dashed var(--gold2);background:#fffdf6;border-radius:14px;padding:18px 20px;margin:26px 0}
.claim h3{margin:0 0 4px;font-size:16px}
@media(max-width:600px){.phero{flex-direction:column;gap:14px}}
'''

def broker_fname(b): return f"broker-{b['slug']}.html"

def specialty_text(spec):
    parts = [s.strip() for s in spec.split('|') if s.strip() and s.strip() != '—']
    if not parts: return ''
    if len(parts) == 1: return parts[0]
    return ', '.join(parts[:-1]) + ' and ' + parts[-1]

# ---------------------------------------------------------------- broker pages
def gen_broker_page(b, n_state):
    name, firm, city, st = b['name'], b['firm'], b['city'], b['state']
    st_name = STATES.get(st, '')
    fname = broker_fname(b)
    loc_bits = [x for x in (city if city != '—' else '', st_name) if x]
    loc = ', '.join(loc_bits[:1] + ([st] if city and city != '—' and st_name else ([st_name] if st_name and not (city and city != '—') else [])))
    loc_long = ', '.join(loc_bits)
    spec = specialty_text(b['specialty'])
    initials = ''.join(w[0] for w in re.findall(r'[A-Za-z]+', name)[:2]).upper() or 'B'

    title = f"{name} — Business Broker{' in ' + loc if loc else ''} | Reviews | The Broker Index"
    desc = f"Independent client ratings and reviews for {name}" + (f" of {firm}" if firm and firm != 'Independent' else '') + \
           (f", business broker in {loc_long}" if loc_long else ', business broker') + \
           ". Six-parameter ratings: professionalism, transparency, consistency, collaboration, command of the deal, documentation."

    person = {"@context":"https://schema.org","@type":"Person","name":name,"jobTitle":"Business Broker",
              "url":f"{SITE}/{fname}","description":desc}
    if firm: person["worksFor"] = {"@type":"Organization","name":firm}
    if b['photo']: person["image"] = b['photo']
    same = [u for u in (b['linkedin'], b['website']) if u]
    if same: person["sameAs"] = same
    if st_name:
        addr = {"@type":"PostalAddress","addressRegion":st}
        if city and city != '—': addr["addressLocality"] = city
        person["address"] = addr
    crumbs = {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":1,"name":"Home","item":SITE+"/"},
        {"@type":"ListItem","position":2,"name":"Brokers by state","item":SITE+"/business-brokers-by-state.html"}]}
    if st_name:
        crumbs["itemListElement"].append({"@type":"ListItem","position":3,"name":f"Business Brokers in {st_name}","item":f"{SITE}/business-brokers-in-{state_slug(st_name)}.html"})
    crumbs["itemListElement"].append({"@type":"ListItem","position":len(crumbs["itemListElement"])+1,"name":name,"item":f"{SITE}/{fname}"})
    jsonld = ('<script type="application/ld+json">\n' + json.dumps(person, ensure_ascii=False) + '\n</script>\n'
              '<script type="application/ld+json">\n' + json.dumps(crumbs, ensure_ascii=False) + '\n</script>')

    face = (f'<img class="face" src="{esc(b["photo"])}" alt="{esc(name)}, business broker" onerror="this.outerHTML=\'<div class=&quot;ph&quot;>{initials}</div>\'">'
            if b['photo'] else f'<div class="ph">{initials}</div>')
    logo = f'<img src="{esc(b["logo"])}" alt="{esc(firm)} logo" loading="lazy" onerror="this.remove()">' if b['logo'] else ''
    chips = ''
    if loc_long: chips += f'<span class="chip loc">{esc(loc_long)}</span>'
    for s in [x.strip() for x in b['specialty'].split('|') if x.strip() and x.strip() != '—'][:4]:
        chips += f'<span class="chip">{esc(s)}</span>'
    plinks = []
    if b['website']: plinks.append(f'<a href="{esc(b["website"])}" target="_blank" rel="noopener nofollow">🌐 Website</a>')
    if b['linkedin']: plinks.append(f'<a href="{esc(b["linkedin"])}" target="_blank" rel="noopener nofollow">💼 LinkedIn</a>')
    if b['phone']: plinks.append(f'<a href="tel:{esc(re.sub(r"[^0-9+]","",b["phone"]))}">📞 {esc(b["phone"])}</a>')
    rate_url = f'/?state={st}' if st_name else '/'
    state_link = (f' They are one of <a href="/business-brokers-in-{state_slug(st_name)}.html">{n_state} business brokers listed in {st_name}</a> on The Broker Index.' if st_name else '')
    spec_sent = f' Their listed focus areas include {esc(spec)}.' if spec else ''
    firm_sent = f' with {esc(firm)}' if firm and firm != 'Independent' else (' operating independently' if firm == 'Independent' else '')
    first = esc(name.split(' ')[0].strip('‘’“”\'"'))

    js_first = json.dumps(name.split(' ')[0].strip('‘’“”\'"'))
    live_js = f'''<script>
(async()=>{{
  const el=document.getElementById('live-inner');
  const KEY='{SUPABASE_KEY}', BASE='{SUPABASE_URL}/rest/v1';
  const h={{apikey:KEY,Authorization:'Bearer '+KEY}};
  const FIRST={js_first}, RATE='{rate_url}';
  try{{
    const b=await(await fetch(BASE+'/brokers?slug=eq.{b["slug"]}&select=id',{{headers:h}})).json();
    if(!b.length){{el.textContent='This listing is not in the live directory right now.';return;}}
    const rv=await(await fetch(BASE+'/reviews?broker_id=eq.'+b[0].id+'&select=ratings',{{headers:h}})).json();
    const os=rv.map(r=>{{const v=Object.values(r.ratings||{{}}).map(Number).filter(x=>x>=1&&x<=5);return v.length?v.reduce((a,c)=>a+c,0)/v.length:null}}).filter(x=>x!=null);
    if(!os.length){{el.innerHTML='<b>No reviews yet.</b> Worked with '+FIRST+'? <a href="'+RATE+'">Be the first to rate them →</a>';return;}}
    const avg=os.reduce((a,c)=>a+c,0)/os.length;
    el.innerHTML='<span class="bigscore">'+avg.toFixed(1)+'</span>★ raw average across '+os.length+' review'+(os.length>1?'s':'')+' · <a href="'+RATE+'">see ranking &amp; full breakdown →</a><div class="mnote">Directory rankings additionally apply verification weighting, recency decay and Bayesian shrinkage — see the <a href="/methodology.html">methodology</a>.</div>';
  }}catch(e){{el.innerHTML='Live ratings unavailable right now — <a href="/">open the directory</a>.';}}
}})();
</script>'''

    body = f'''
<article>
  <div class="crumb"><a href="/">Home</a> › <a href="/business-brokers-by-state.html">Brokers by state</a>{' › <a href="/business-brokers-in-' + state_slug(st_name) + '.html">' + esc(st_name) + '</a>' if st_name else ''} › {esc(name)}</div>

  <div class="phero">
    {face}
    <div style="min-width:0">
      <h1>{esc(name)}</h1>
      <div class="firm">{logo}<span>{esc(firm)}</span></div>
      <div class="chips">{chips}</div>
      <div class="plinks">{''.join(plinks) if plinks else '<span style="color:var(--mut);font-weight:400">No contact details on file</span>'}</div>
    </div>
  </div>

  <div class="live"><div id="live-inner">Checking live ratings…</div></div>

  <h2>About this listing</h2>
  <p>{esc(name)} is a business broker{firm_sent}{' based in ' + esc(loc_long) if loc_long else ''}.{spec_sent}{state_link} Clients who have worked with {first} can rate the experience on six parameters — professionalism, transparency, consistency, collaboration, command of the deal, and quality of documentation — under our <a href="/methodology.html">published methodology</a>. Listings are free, rankings cannot be bought, and reviews are moderated.</p>
  <p>Choosing a broker? Price your business first with the <a href="/business-valuation-calculator.html">free valuation calculator</a>, understand <a href="/how-business-brokers-get-paid.html">how broker fees work</a>, and run any candidate past <a href="/can-i-trust-my-ma-broker.html">the 12 red flags</a> before signing an exclusive listing agreement.</p>

  <div class="claim">
    <h3>Are you {esc(name)}?</h3>
    <p style="margin-top:6px;font-size:14px">This listing is free and was compiled from public directory information. To correct a detail, use the request form on the <a href="/">home page</a>. To build your review record, share this page with past clients — all of them, not just the happy ones. Brokers with real reviews rank above empty listings, and verified-client reviews carry roughly double weight.</p>
  </div>

  <div class="cta">
    <h4>Worked with {first}? Rate the experience</h4>
    <p>Two minutes, six parameters, moderated for authenticity. Good or bad, your review is what makes broker quality visible to the next owner.</p>
    <a href="{rate_url}">Rate this broker →</a>
  </div>
</article>
{live_js}'''
    return head(title, desc, fname, jsonld, ogimg=b['photo'] or None, extra_css=PROFILE_CSS) + body + FOOT

# ---------------------------------------------------------------- state pages
def broker_card(b):
    fname = broker_fname(b)
    face = f'<img class="face" src="{esc(b["photo"])}" alt="{esc(b["name"])}" loading="lazy" onerror="this.style.display=\'none\'">' if b['photo'] else ''
    city = b['city'] if b['city'] and b['city'] != '—' else ''
    spec = b['specialty'] if b['specialty'] and b['specialty'] != '—' else ''
    if len(spec) > 70: spec = spec[:67] + '…'
    meta = ' · '.join(esc(x) for x in (city, spec) if x)
    lnks = [f'<a href="/{fname}"><b>Profile &amp; reviews →</b></a>']
    if b['website']: lnks.append(f'<a href="{esc(b["website"])}" target="_blank" rel="noopener nofollow">Website</a>')
    if b['linkedin']: lnks.append(f'<a href="{esc(b["linkedin"])}" target="_blank" rel="noopener nofollow">LinkedIn</a>')
    if b['phone']: lnks.append(f'<span style="color:var(--mut)">{esc(b["phone"])}</span>')
    return f'''<div class="bcard">
  <div class="top">{face}<div><div class="nm"><a href="/{fname}">{esc(b['name'])}</a></div><div class="fm">{esc(b['firm'])}</div></div></div>
  <div class="meta">{meta}</div>
  <div class="lnks">{' '.join(lnks)}</div>
</div>'''

def gen_state_page(st, brokers):
    name = STATES[st]; n = len(brokers)
    fname = f'business-brokers-in-{state_slug(name)}.html'
    brokers = sorted(brokers, key=lambda b: b['name'].lower())
    cities = collections.Counter(b['city'] for b in brokers if b['city'] and b['city'] != '—')
    topcities = [c for c, _ in cities.most_common(4)]
    firms = collections.Counter(b['firm'] for b in brokers if b['firm'])
    topfirms = [f for f, c in firms.most_common(3) if c > 1]
    plural = 'broker' if n == 1 else 'brokers'
    city_txt = (f", with listings concentrated in {', '.join(topcities[:-1])} and {topcities[-1]}" if len(topcities) > 1
                else (f", based in {topcities[0]}" if topcities else ''))
    firm_txt = f" National networks like {' and '.join(topfirms[:2])} are represented alongside independent firms." if topfirms else ''
    title = f'Business Brokers in {name} ({n} Listed) — Ratings & Reviews | The Broker Index'
    desc = f'Compare {n} M&A business {plural} in {name}: firms, specialties, contact links, and independent client ratings on transparency and deal execution.'
    itemlist = {"@context":"https://schema.org","@type":"ItemList","name":f"Business Brokers in {name}","numberOfItems":n,
        "itemListElement":[{"@type":"ListItem","position":i+1,"name":b['name'],"url":f"{SITE}/{broker_fname(b)}"} for i, b in enumerate(brokers)]}
    faq = {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
        {"@type":"Question","name":f"How many business brokers are there in {name}?",
         "acceptedAnswer":{"@type":"Answer","text":f"The Broker Index currently lists {n} M&A business {plural} operating in {name}, compiled from public professional directory data. Each listing carries independent client ratings once reviews are submitted."}},
        {"@type":"Question","name":f"How do I check a business broker's reputation in {name}?",
         "acceptedAnswer":{"@type":"Answer","text":"Search the broker on The Broker Index to see client ratings across six parameters (professionalism, transparency, consistency, collaboration, command of the deal, and quality of documentation), then verify their license if your state requires one, ask for references from closed deals, and check how long they've been brokering in your industry."}},
        {"@type":"Question","name":f"How much do business brokers charge in {name}?",
         "acceptedAnswer":{"@type":"Answer","text":"Fees in every state follow the same national patterns: roughly 8-12% success fees for main-street businesses under $2M (10% is most common), and tiered Double Lehman formulas on larger deals. Minimum fees of $10,000-$25,000 are common."}}]}
    jsonld = ('<script type="application/ld+json">\n' + json.dumps(itemlist, ensure_ascii=False) + '\n</script>\n'
              '<script type="application/ld+json">\n' + json.dumps(faq, ensure_ascii=False) + '\n</script>')
    cards = '\n'.join(broker_card(b) for b in brokers)
    body = f'''
<div class="wide">
  <div class="crumb"><a href="/">Home</a> › <a href="/business-brokers-by-state.html">Brokers by state</a> › {name}</div>
  <h1>Business Brokers in {name}</h1>
  <p style="max-width:720px">The Broker Index lists <strong>{n} M&amp;A business {plural} in {name}</strong>{city_txt}.{firm_txt} Every broker below has a profile page and can be rated by clients on six parameters — professionalism, transparency, consistency, collaboration, command of the deal, and quality of documentation — using the <a href="/methodology.html">same published methodology</a>. Listings are free and cannot be bought; ratings come only from members.</p>
  <p style="max-width:720px;font-size:14px">Selling in {name}? Start with our <a href="/business-valuation-calculator.html">free valuation calculator</a> to price realistically, read <a href="/how-business-brokers-get-paid.html">how broker fees work</a> before you sign, and check <a href="/can-i-trust-my-ma-broker.html">the 12 red flags</a> before granting exclusivity.</p>

  <div class="bgrid">
{cards}
  </div>
  <p style="font-size:12.5px;color:var(--mut)">Worked with one of these brokers? <a href="/?state={st}">Leave a rating</a> — it takes two minutes and helps the next seller. Broker details compiled from publicly available directory information; to correct a listing, use the request form on the <a href="/">home page</a>.</p>

  <h2 style="margin-top:40px">FAQ</h2>
  <h3>How many business brokers are there in {name}?</h3>
  <p>The Broker Index currently lists {n} business {plural} operating in {name}. Coverage grows as brokers and members request listings.</p>
  <h3>How do I check a broker's reputation in {name}?</h3>
  <p>Look them up here for client ratings, ask for references from recently closed deals in your size range, and confirm relevant credentials (CBI, M&amp;AMI) and any state license requirements. Our guide to <a href="/can-i-trust-my-ma-broker.html">vetting an M&amp;A broker</a> walks through the full checklist.</p>
  <h3>How much do business brokers charge in {name}?</h3>
  <p>The same national patterns apply in {name}: 8–12% success fees under $2M (10% typical), Double Lehman tiers above that, and $10k–$25k minimum fees. Full breakdown in <a href="/how-business-brokers-get-paid.html">our fee guide</a>.</p>

  <div class="cta">
    <h4>Rate a {name} broker you've worked with</h4>
    <p>Reviews from real sellers and buyers are what make broker quality visible. Good or bad, your experience helps the next owner.</p>
    <a href="/?state={st}">Find your broker →</a>
  </div>
</div>
'''
    return fname, head(title, desc, fname, jsonld, extra_css=GRID_CSS) + body + FOOT

def gen_state_index(by_state, state_files):
    fname = 'business-brokers-by-state.html'
    total = sum(len(v) for v in by_state.values())
    title = 'Business Brokers by State — Directory & Ratings | The Broker Index'
    desc = f'Find and compare M&A business brokers in {len(by_state)} states: independent listings with client ratings on transparency, professionalism, and deal execution.'
    links = '\n'.join(f'<a href="/{state_files[st]}">{STATES[st]}<span>{len(by_state[st])}</span></a>'
                      for st in sorted(by_state, key=lambda s: STATES[s]))
    jsonld = '<script type="application/ld+json">\n' + json.dumps({
        "@context":"https://schema.org","@type":"CollectionPage","name":"Business Brokers by State",
        "url":f"{SITE}/{fname}","isPartOf":{"@type":"WebSite","name":"The Broker Index","url":SITE}}, ensure_ascii=False) + '\n</script>'
    body = f'''
<div class="wide">
  <div class="crumb"><a href="/">Home</a> › Brokers by state</div>
  <h1>Business brokers by state</h1>
  <p style="max-width:720px">The Broker Index lists <strong>{total} M&amp;A business brokers across {len(by_state)} states</strong>. Pick your state to see who operates there, their firms and specialties, and their independent client ratings. Listings are free and cannot be bought; scores follow our <a href="/methodology.html">published methodology</a>.</p>
  <div class="stgrid">
{links}
  </div>
  <p style="font-size:14px;color:var(--ink2);max-width:720px">Don't see your broker? Anyone can <a href="/">request a listing</a> — brokers are added from public directory information and member requests, and being listed is always free.</p>
  <div class="cta">
    <h4>Selling a business? Price it before you pick a broker</h4>
    <p>Our free calculator turns your P&amp;L into a defensible asking range in 60 seconds — SDE, add-backs, industry multiples, and the SBA financing test.</p>
    <a href="/business-valuation-calculator.html">Try the valuation calculator →</a>
  </div>
</div>
'''
    return fname, head(title, desc, fname, jsonld, extra_css=GRID_CSS) + body + FOOT

# ---------------------------------------------------------------- sitemap
def gen_sitemap(broker_files, state_files):
    core = [('', '1.0', 'daily'), ('articles.html', '0.8', 'daily'),
            ('business-valuation-calculator.html', '0.8', None),
            ('business-brokers-by-state.html', '0.8', 'weekly'),
            ('about.html', '0.6', None), ('methodology.html', '0.6', None)]
    skip = {'index.html', 'articles.html', 'about.html', 'methodology.html',
            'business-valuation-calculator.html', 'business-brokers-by-state.html'}
    articles = sorted(f for f in os.listdir(OUT) if f.endswith('.html') and f not in skip
                      and not f.startswith('broker-') and not f.startswith('business-brokers-in-')
                      and not f.startswith('google'))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    def add(path, pri, freq=None):
        cf = f'<changefreq>{freq}</changefreq>' if freq else ''
        lines.append(f' <url><loc>{SITE}/{path}</loc><lastmod>{TODAY}</lastmod>{cf}<priority>{pri}</priority></url>')
    for p, pri, freq in core: add(p, pri, freq)
    for a in articles: add(a, '0.7')
    for f in sorted(state_files.values()): add(f, '0.7', 'weekly')
    for f in sorted(broker_files): add(f, '0.5', 'monthly')
    lines.append('</urlset>')
    return '\n'.join(lines) + '\n'

# ---------------------------------------------------------------- main
def main():
    brokers = load_brokers()
    by_state = collections.defaultdict(list)
    for b in brokers:
        if b['state'] in STATES: by_state[b['state']].append(b)
    state_files = {}
    for st, lst in sorted(by_state.items()):
        fname, page = gen_state_page(st, lst)
        open(os.path.join(OUT, fname), 'w').write(page)
        state_files[st] = fname
    fname, page = gen_state_index(by_state, state_files)
    open(os.path.join(OUT, fname), 'w').write(page)
    broker_files = []
    for b in brokers:
        n_state = len(by_state.get(b['state'], []))
        open(os.path.join(OUT, broker_fname(b)), 'w').write(gen_broker_page(b, n_state))
        broker_files.append(broker_fname(b))
    open(os.path.join(OUT, 'sitemap.xml'), 'w').write(gen_sitemap(broker_files, state_files))
    print(f'generated: {len(broker_files)} broker pages, {len(state_files)} state pages + index, sitemap ({len(broker_files)+len(state_files)+2} files)')

if __name__ == '__main__':
    main()
