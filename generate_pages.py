#!/usr/bin/env python3
"""
The Broker Index — page generator (Sept 2026 UX round).
Generates: broker-<slug>.html (one per broker), business-brokers-in-<state>.html,
business-brokers-by-state.html, and sitemap.xml. All files land flat in the repo root.

Run locally:            python3 generate_pages.py --local brokers.json
Run in GitHub Actions:  python3 generate_pages.py --from-supabase

Every generated page uses the shared shell (_shell.js renders the nav/footer,
_app.js renders the live score block) so nav changes never require regenerating.
"""
import json, html, collections, sys, os, re, datetime, urllib.request

SUPABASE_URL = 'https://qnxmvzrotgnsgyafewbo.supabase.co'
SUPABASE_KEY = 'sb_publishable_jx_rlrzcPGOWtuimIAw2eA_l46TedX8'  # publishable: safe in public code
SITE = 'https://ratemybusinessbroker.com'
REVIEWS_BY, TIERS = {}, {}
PARAM_NAMES = [('professionalism','Professionalism'),('transparency','Transparency'),('consistency','Consistency'),('collaboration','Collaboration'),('command','Command of the deal'),('documentation','Quality of documentation')]
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
            SUPABASE_URL + '/rest/v1/brokers?select=id,slug,name,firm,city,state,specialty,photo,website,linkedin,logo,phone,claimed_by,bio&order=name&limit=5000',
            headers={'apikey': SUPABASE_KEY, 'Authorization': 'Bearer ' + SUPABASE_KEY})
        rows = json.load(urllib.request.urlopen(req, timeout=60))
    else:
        src = sys.argv[sys.argv.index('--local')+1] if '--local' in sys.argv else 'brokers.json'
        rows = json.load(open(src))
    global REVIEWS_BY, TIERS
    REVIEWS_BY, TIERS = {}, {}
    if '--from-supabase' in sys.argv:
        try:
            rq = urllib.request.Request(SUPABASE_URL + '/rest/v1/reviews?select=broker_id,author_id,ratings,side,stage,industry,deal_size,text,created_at&status=eq.published&limit=10000',
                                        headers={'apikey': SUPABASE_KEY, 'Authorization': 'Bearer ' + SUPABASE_KEY})
            for r in json.load(urllib.request.urlopen(rq, timeout=60)):
                REVIEWS_BY.setdefault(r['broker_id'], []).append(r)
            pq = urllib.request.Request(SUPABASE_URL + '/rest/v1/profiles?select=id,username,tier&limit=10000',
                                        headers={'apikey': SUPABASE_KEY, 'Authorization': 'Bearer ' + SUPABASE_KEY})
            for pr in json.load(urllib.request.urlopen(pq, timeout=60)): TIERS[pr['id']] = pr
        except Exception as e:
            print('warning: reviews not fetched, pages will carry scores via JS only:', e)
    clean = []
    for raw in rows:
        b = {k: (str(raw.get(k) or '')).strip() for k in ('slug','name','firm','city','state','specialty','photo','website','linkedin','logo','phone','claimed_by','bio')}
        b['id'] = str(raw.get('id') or '')
        if b['slug'] and b['name'] and re.fullmatch(r'[a-z0-9\-]+', b['slug']):
            clean.append(b)
    return clean

# ---------------------------------------------------------------- shared shell
def head(title, desc, fname, jsonld='', ogimg=None, extra_css='', nav=''):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}/{fname}">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Broker Index">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE}/{fname}">
<meta property="og:image" content="{esc(ogimg) if ogimg else SITE + '/og-image.png'}">
<meta name="twitter:card" content="summary_large_image">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-KTQ1BWRBJC"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-KTQ1BWRBJC');</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,650&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/_shared.css">
{('<style>' + extra_css + '</style>') if extra_css else ''}
{jsonld}
</head>
<body{(' data-nav="' + nav + '"') if nav else ''}>
<div id="site-header"></div>
'''

FOOT = '''
<div id="site-footer"></div>
<div id="modals"></div><div class="toast" id="toast"></div>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>
<script src="/_shell.js"></script>
<script src="/_app.js"></script>
</body>
</html>
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
    first = name.split(' ')[0].strip('‘’“”\'"')
    firm_txt = f' of {firm}' if firm and firm != 'Independent' else ''

    title = f"{name} — Business Broker{' in ' + loc if loc else ''} | Reviews & Ratings | The Broker Index"
    desc = (f"How sellers and buyers rate {name}{firm_txt}" + (f", business broker in {loc_long}" if loc_long else '') +
            f". Independent reviews on professionalism, transparency, negotiation and paperwork" + (f"; focus on {spec}" if spec else '') +
            f". Worked with {first}? Add your review.")

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
    # (AggregateRating is appended below once reviews are known)

    face = (f'<img class="face" src="{esc(b["photo"])}" alt="{esc(name)}, business broker" onerror="this.outerHTML=\'<div class=&quot;ph&quot;>{initials}</div>\'">'
            if b['photo'] else f'<div class="ph">{initials}</div>')
    logo = f'<img src="{esc(b["logo"])}" alt="{esc(firm)} logo" loading="lazy" onerror="this.remove()">' if b['logo'] else ''
    chips = ''
    if loc_long: chips += f'<span class="chip loc">{esc(loc_long)}</span>'
    for s in [x.strip() for x in b['specialty'].split('|') if x.strip() and x.strip() != '—'][:4]:
        chips += f'<span class="chip">{esc(s)}</span>'
    plinks = []
    if b['website']: plinks.append(f'<a href="{esc(b["website"])}" target="_blank" rel="noopener nofollow">Website</a>')
    if b['linkedin']: plinks.append(f'<a href="{esc(b["linkedin"])}" target="_blank" rel="noopener nofollow">LinkedIn</a>')
    if b['phone']: plinks.append(f'<a href="tel:{esc(re.sub(r"[^0-9+]","",b["phone"]))}">{esc(b["phone"])}</a>')
    verified = ' <span class="vpill" title="This broker has claimed and verified their profile">✓ Verified</span>' if b['claimed_by'] else ''
    state_link = (f' They are one of <a href="/business-brokers-in-{state_slug(st_name)}.html">{n_state} business brokers listed in {st_name}</a> on The Broker Index.' if st_name else '')
    spec_sent = f' Their listed focus areas include {esc(spec)}.' if spec else ''
    firm_sent = f' with {esc(firm)}' if firm and firm != 'Independent' else (' operating independently' if firm == 'Independent' else '')
    review_url = f'/write-a-review.html?broker={b["slug"]}'
    revs = sorted(REVIEWS_BY.get(b['id'], []), key=lambda r: r.get('created_at',''), reverse=True)
    static_live, agg_ld = static_reviews_block(b, revs, first, review_url)
    claim_html = '' if b['claimed_by'] else (
        '<div class="claimbox"><h3>Are you ' + esc(name) + '?</h3>'
        '<p><a href="/claim.html?broker=' + b['slug'] + '"><b>Claim this profile</b></a> — free — to confirm your details, show a Verified mark, '
        'and get a monthly report of how clients rate you. Claiming never changes reviews or scores. Then share this page with past clients '
        '— all of them, not just the happy ones.</p></div>')

    body = f'''
<main class="wide app">
  <div class="crumb"><a href="/">Home</a> › <a href="/business-brokers-by-state.html">Brokers by state</a>{' › <a href="/business-brokers-in-' + state_slug(st_name) + '.html">' + esc(st_name) + '</a>' if st_name else ''} › {esc(name)}</div>

  <div class="phero">
    {face}
    <div style="min-width:0">
      <h1>{esc(name)}{verified}</h1>
      <div class="firm">{logo}<span>{esc(firm)}</span></div>
      <div class="chips">{chips}</div>
      <div class="plinks">{''.join(plinks) if plinks else '<span style="color:var(--mut);font-weight:400">No contact details on file</span>'}</div>
    </div>
    <div class="pacts">
      <a class="btn gold" href="{review_url}">Write a review</a>
      <a class="btn line" id="save-list" href="/account.html">☆ Save to My List</a>
    </div>
  </div>

  <div id="live">{static_live}</div>

  <div class="panel section">
    <h2 style="font-size:20px">About this listing</h2>
    <p style="margin-top:8px;font-size:15px;line-height:1.6;color:var(--ink2)">{esc(name)} is a business broker{firm_sent}{' based in ' + esc(loc_long) if loc_long else ''}.{spec_sent}{state_link} Clients who have worked with {esc(first)} rate the experience on six parameters — professionalism, transparency, consistency, collaboration, command of the deal, and quality of documentation — separately as buyers and as sellers, under our <a href="/methodology.html">published methodology</a>. Listings are free, rankings cannot be bought, and every review is screened before publication.</p>
    <p style="margin-top:10px;font-size:14px;color:var(--ink2)">Choosing a broker? <a href="/find-my-perfect-broker.html">Get matched</a> on location, industry and what matters to you; price your business first with the <a href="/business-valuation-calculator.html">valuation calculator</a>; and run any candidate past <a href="/can-i-trust-my-ma-broker.html">the 12 red flags</a> before signing an exclusive listing.</p>
  </div>

  {claim_html}

  <div class="cta">
    <h4>Worked with {esc(first)}? Rate the experience</h4>
    <p>Three minutes, six parameters, screened for authenticity. Good or bad, your review is what makes broker quality visible to the next owner.</p>
    <a href="{review_url}">Write a review →</a>
  </div>
</main>
<script>document.addEventListener('DOMContentLoaded',function(){{ var t=setInterval(function(){{ if(window.TBI){{ clearInterval(t); TBI.ready.then(function(){{ TBI.renderBrokerLive({json.dumps(b['slug'])}, document.getElementById('live')); }}); }} }},30); }});</script>'''
    if agg_ld: jsonld += '\n<script type="application/ld+json">\n' + json.dumps(agg_ld, ensure_ascii=False) + '\n</script>'
    return head(title, desc, fname, jsonld, ogimg=b['photo'] or None) + body + FOOT

def static_reviews_block(b, revs, first, review_url):
    """Static HTML for the score + reviews so crawlers see the unique content without JS.
    Plain (unweighted) averages here; _app.js swaps in the weighted score on load."""
    def overall(r):
        v = [float(x) for x in (r.get('ratings') or {}).values() if 1 <= float(x) <= 5]
        return (sum(v) / len(v)) * 2 if v else None
    ov = [x for x in (overall(r) for r in revs) if x is not None]
    if not ov:
        return (f'<div class="panel"><div class="scorebox"><div class="lab">Overall</div><div class="big" style="font-size:22px;color:var(--mut)">Not yet rated</div><div class="n">Be the first to rate {esc(first)}</div></div></div>'
                f'<div class="section"><div class="sechead"><h2>Reviews <span class="chip">0</span></h2><a class="btn gold" href="{review_url}">Write a review</a></div><p class="hint">No reviews yet. Worked with {esc(first)}? Your review starts their record.</p></div>', None)
    avg = sum(ov) / len(ov)
    def side_avg(side):
        xs = [overall(r) for r in revs if r.get('side') == side]; xs = [x for x in xs if x is not None]
        return (sum(xs) / len(xs), len(xs)) if xs else None
    sa, ba = side_avg('seller'), side_avg('buyer')
    box = lambda lab, v, n, cls='': (f'<div class="panel {cls}"><div class="scorebox"><div class="lab">{lab}</div>' + (f'<div class="big">{v:.2f}<small>/ 10</small></div><div class="n">{n} review{"" if n==1 else "s"}</div>' if v is not None else '<div class="big" style="font-size:18px;color:var(--mut)">Not yet rated</div>') + '</div></div>')
    html_out = '<div class="cols3">' + box('Overall', avg, len(ov), 'navy') + box('Rated by sellers', sa[0] if sa else None, sa[1] if sa else 0) + box('Rated by buyers', ba[0] if ba else None, ba[1] if ba else 0) + '</div>'
    # parameter averages
    prow = ''
    for k, lab in PARAM_NAMES:
        vs = [float((r.get('ratings') or {}).get(k, 0)) for r in revs if (r.get('ratings') or {}).get(k)]
        if vs:
            m = sum(vs) / len(vs) * 2
            prow += f'<div class="prow"><span>{lab}</span><span class="bar"><i style="width:{m*10:.0f}%"></i></span><b>{m:.2f}</b></div>'
    if prow: html_out += f'<div class="panel section"><h2 style="font-size:20px">Rated parameters</h2><div class="params">{prow}</div></div>'
    items = ''
    for r in revs[:20]:
        o = overall(r); p = TIERS.get(r.get('author_id'), {})
        when = (r.get('created_at') or '')[:10]
        try: when = datetime.date.fromisoformat(when).strftime('%b %Y')
        except Exception: pass
        side = r.get('side') or ''
        items += (f'<div class="rev"><div class="rtop"><span class="who">{esc(p.get("username") or "Member")}</span>'
                  + ('<span class="vbadge">Verified</span>' if p.get('tier') == 'verified' else '')
                  + (f'<span class="sidetag {"sell" if side=="seller" else "buy"}">{side.title()}</span>' if side in ('seller','buyer') else '')
                  + (f'<span class="rscore">{o:.2f}<small style="color:var(--mut);font-weight:400"> /10</small></span>' if o is not None else '')
                  + f'<time>{esc(when)}</time></div>'
                  + (f'<div class="rtxt">{esc(r.get("text") or "")}</div>' if r.get('text') else '')
                  + f'<div class="rctx">{esc(" · ".join(x for x in (r.get("stage"), r.get("industry"), r.get("deal_size")) if x))}</div></div>')
    html_out += f'<div class="section"><div class="sechead"><h2>Reviews <span class="chip">{len(revs)}</span></h2><a class="btn gold" href="{review_url}">Write a review</a></div>{items}</div>'
    agg = {"@context":"https://schema.org","@type":"Person","name":b['name'],"url":f"{SITE}/{broker_fname(b)}",
           "aggregateRating":{"@type":"AggregateRating","ratingValue":round(avg,2),"bestRating":10,"worstRating":0,"ratingCount":len(ov)},
           "review":[{"@type":"Review","author":{"@type":"Person","name":TIERS.get(r.get('author_id'),{}).get('username') or 'Member'},
                      "datePublished":(r.get('created_at') or '')[:10],"reviewBody":(r.get('text') or '')[:500],
                      "reviewRating":{"@type":"Rating","ratingValue":round(overall(r),2),"bestRating":10,"worstRating":0}}
                     for r in revs[:10] if overall(r) is not None]}
    return html_out, agg

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
    return f'''<div class="bcard">
  <div class="top">{face}<div><div class="nm"><a href="/{fname}">{esc(b['name'])}</a>{' <span class="vpill">✓</span>' if b['claimed_by'] else ''}</div><div class="fm">{esc(b['firm'])}</div></div></div>
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
    title = f'Business Brokers in {name} ({n} Listed) — Reviews & Ratings | The Broker Index'
    desc = f'Compare {n} business {plural} in {name} by independent client reviews: how sellers and buyers rated each one, firms, specialties and contact links. Get matched to the right {name} broker for your sale.'
    itemlist = {"@context":"https://schema.org","@type":"ItemList","name":f"Business Brokers in {name}","numberOfItems":n,
        "itemListElement":[{"@type":"ListItem","position":i+1,"name":b['name'],"url":f"{SITE}/{broker_fname(b)}"} for i, b in enumerate(brokers)]}
    faq = {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
        {"@type":"Question","name":f"How many business brokers are there in {name}?",
         "acceptedAnswer":{"@type":"Answer","text":f"The Broker Index currently lists {n} M&A business {plural} operating in {name}, compiled from public professional directory data. Each listing carries independent client ratings once reviews are submitted."}},
        {"@type":"Question","name":f"How do I check a business broker's reputation in {name}?",
         "acceptedAnswer":{"@type":"Answer","text":"Search the broker on The Broker Index to see client ratings across six parameters, split by whether the reviewer was a buyer or a seller, then verify their license if your state requires one, ask for references from closed deals, and check how long they've been brokering in your industry."}},
        {"@type":"Question","name":f"How much do business brokers charge in {name}?",
         "acceptedAnswer":{"@type":"Answer","text":"Fees in every state follow the same national patterns: roughly 8-12% success fees for main-street businesses under $2M (10% is most common), and tiered Double Lehman formulas on larger deals. Minimum fees of $10,000-$25,000 are common."}}]}
    jsonld = ('<script type="application/ld+json">\n' + json.dumps(itemlist, ensure_ascii=False) + '\n</script>\n'
              '<script type="application/ld+json">\n' + json.dumps(faq, ensure_ascii=False) + '\n</script>')
    cards = '\n'.join(broker_card(b) for b in brokers)
    body = f'''
<div class="wide">
  <div class="crumb"><a href="/">Home</a> › <a href="/business-brokers-by-state.html">Brokers by state</a> › {name}</div>
  <h1>Business Brokers in {name}</h1>
  <p style="max-width:720px">The Broker Index lists <strong>{n} M&amp;A business {plural} in {name}</strong>{city_txt}.{firm_txt} Every broker below has a profile page and is rated by clients on six parameters — separately by buyers and by sellers — using the <a href="/methodology.html">same published methodology</a>. Listings are free and cannot be bought; ratings come only from members.</p>
  <p style="max-width:720px;font-size:14px">Selling in {name}? <a href="/find-my-perfect-broker.html">Get matched to a broker</a> in two minutes, price realistically with the <a href="/business-valuation-calculator.html">free valuation calculator</a>, and read <a href="/how-business-brokers-get-paid.html">how broker fees work</a> before you sign. See also the <a href="/brokerage-rankings.html?state={st}">best-rated brokerages in {name}</a>.</p>

  <div class="bgrid">
{cards}
  </div>
  <p style="font-size:12.5px;color:var(--mut)">Worked with one of these brokers? <a href="/write-a-review.html">Write a review</a> — it takes three minutes and helps the next seller. Broker details compiled from publicly available directory information; brokers can <a href="/claim.html">claim their profile</a> to correct a listing.</p>

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
    <a href="/write-a-review.html">Write a review →</a>
  </div>
</div>
'''
    return fname, head(title, desc, fname, jsonld) + body + FOOT

def gen_state_index(by_state, state_files):
    fname = 'business-brokers-by-state.html'
    total = sum(len(v) for v in by_state.values())
    title = 'Business Brokers by State — Directory, Reviews & Ratings | The Broker Index'
    desc = f'Find and compare {total} M&A business brokers across {len(by_state)} states. Independent client reviews, split by buyer and seller, on transparency, professionalism and deal execution. Free to browse.'
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
  <p style="font-size:14px;color:var(--ink2);max-width:720px">Don't see your broker? <a href="/write-a-review.html">Add them with a review</a> — brokers are added from public directory information and member requests, and being listed is always free.</p>
  <div class="cta">
    <h4>Selling a business? Get matched before you pick</h4>
    <p>Four questions — location, industry, revenue, what matters to you — and five ranked brokers with the reasons.</p>
    <a href="/find-my-perfect-broker.html">Find my perfect broker →</a>
  </div>
</div>
'''
    return fname, head(title, desc, fname, jsonld, nav='tools') + body + FOOT

# ---------------------------------------------------------------- sitemap
def gen_sitemap(broker_files, state_files):
    core = [('', '1.0', 'daily'),
            ('find-my-perfect-broker.html', '0.9', 'weekly'),
            ('write-a-review.html', '0.8', 'monthly'),
            ('brokerage-rankings.html', '0.8', 'weekly'),
            ('tools.html', '0.8', 'monthly'),
            ('prospective-sellers.html', '0.8', 'monthly'),
            ('prospective-buyers.html', '0.8', 'monthly'),
            ('articles.html', '0.8', 'daily'),
            ('business-valuation-calculator.html', '0.8', None),
            ('business-brokers-by-state.html', '0.8', 'weekly'),
            ('claim.html', '0.6', None),
            ('about.html', '0.6', None), ('methodology.html', '0.6', None),
            ('privacy.html', '0.2', None), ('terms.html', '0.2', None)]
    skip = {'index.html', 'account.html', 'admin.html'} | {p for p, _, _ in core}
    articles = sorted(f for f in os.listdir(OUT) if f.endswith('.html') and f not in skip
                      and not f.startswith('broker-') and not f.startswith('business-brokers-in-')
                      and not f.startswith('google') and not f.startswith('index')   # "index (3).html" etc. are junk — delete them from the repo
                      and ' ' not in f)
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
