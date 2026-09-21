/* ============================================================================
   The Broker Index — core app module (shared by every page)
   Requires: supabase-js UMD loaded before this file, _shell.js on the page.
   Exposes window.TBI.
   ========================================================================== */
(function () {
  'use strict';

  /* ------------------------------------------------------------ config */
  var SUPA_URL = 'https://qnxmvzrotgnsgyafewbo.supabase.co';
  var SUPA_KEY = 'sb_publishable_jx_rlrzcPGOWtuimIAw2eA_l46TedX8';
  var sb = window.supabase.createClient(SUPA_URL, SUPA_KEY, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });

  // The six parameters. Buyers and sellers rate the same six; #3 is worded per side.
  var PARAMS = [
    ['professionalism', 'Professionalism', 'Responsive, prepared, respectful'],
    ['transparency', 'Transparency', 'Honest about fees, value & counterparties'],
    ['consistency', 'Consistency', 'Same story & effort start to finish'],
    ['collaboration', 'Collaboration', 'Worked with you, not around you'],
    ['command', 'Command of the deal', 'Controlled process & negotiations'],
    ['documentation', 'Quality of documentation', 'CIMs, financials, paperwork']
  ];

  // Minimum review counts before a number is shown. A broker is ranked from the
  // first review (owner decision, Sept 20). Raise these once volume allows — one place.
  var MIN = { score: 1, side: 1, rank: 1, firm: 3, firmAgents: 1 };
  var STAT_FLOOR = 25;   // hero counters hide below this (never show "0 reviews" in the hero)
  var GATE = 100;        // brokers visible on the homepage before sign-in

  var INDUSTRIES = ['Manufacturing', 'Professional services', 'Healthcare', 'Restaurants & hospitality', 'Construction & trades', 'Technology & SaaS', 'Retail & e-commerce', 'Transportation & logistics', 'Distribution & wholesale', 'Home services', 'Other'];
  var DEAL_SIZES = ['Under $1M', '$1M – $2M', '$2M – $5M', '$5M – $10M', '$10M – $25M', 'Over $25M'];
  var STAGES = ['Closed', 'Under LOI', 'Listed, no offers yet', 'Fell through', 'Engaged, not yet listed'];
  var LABELS = ['First-time seller', 'Repeat seller', 'First-time buyer', 'Serial acquirer', 'Search fund', 'PE-backed', 'Family office', 'SBA-financed', 'Strategic acquirer', 'Advisor / CPA / attorney'];
  var HEADLINES = ['Prospective seller', 'Prospective buyer', 'Buyer & seller', 'Business broker', 'Advisor'];

  /* ------------------------------------------------------------ utils */
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); };
  function toast(m) { var t = $('#toast'); if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; document.body.appendChild(t); } t.textContent = m; t.classList.add('show'); clearTimeout(t._h); t._h = setTimeout(function () { t.classList.remove('show'); }, 3400); }
  var initials = function (n) { return String(n || '').split(/\s+/).slice(0, 2).map(function (w) { return w[0] || ''; }).join('').toUpperCase() || 'B'; };
  var specsOf = function (b) { return String(b.specialty || '').split('|').map(function (x) { return x.trim(); }).filter(function (x) { return x && x.length <= 30; }); };
  var fmtDate = function (d) { return new Date(d).toLocaleDateString('en-US', { month: 'short', year: 'numeric' }); };
  var qs = function (k) { return new URLSearchParams(location.search).get(k); };
  var to10 = function (v) { return v * 2; };   // 1–5 star input → 0–10 display scale

  function modal(html, small) {
    var m = $('#modals'); if (!m) { m = document.createElement('div'); m.id = 'modals'; document.body.appendChild(m); }
    m.innerHTML = '<div class="overlay" onclick="if(event.target===this)TBI.closeModal()"><div class="modal ' + (small ? 'sm' : '') + '" role="dialog" aria-modal="true">' + html + '</div></div>';
    document.body.style.overflow = 'hidden';
  }
  function closeModal() { var m = $('#modals'); if (m) m.innerHTML = ''; document.body.style.overflow = ''; }
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeModal(); });

  /* ------------------------------------------------------------ state */
  var T = {
    sb: sb, PARAMS: PARAMS, MIN: MIN, GATE: GATE, STAT_FLOOR: STAT_FLOOR,
    INDUSTRIES: INDUSTRIES, DEAL_SIZES: DEAL_SIZES, STAGES: STAGES, LABELS: LABELS, HEADLINES: HEADLINES,
    brokers: [], reviews: [], profilesById: {}, scores: {}, votes: {}, myVote: new Map(),
    user: null, me: null, myList: [], unread: 0,
    esc: esc, toast: toast, modal: modal, closeModal: closeModal, initials: initials, specsOf: specsOf, fmtDate: fmtDate, qs: qs, to10: to10, $: $
  };

  /* ------------------------------------------------------------ auth (BUG-2 fix)
     The old code painted "Sign in" and popped the username dialog whenever the
     profile fetch had not resolved yet (back/forward navigation restores the
     page before the session check finishes). Now:
       - the last known profile is cached, so restored pages paint signed-in state
         immediately from cache and only re-verify in the background
       - the username prompt opens ONLY after a successful profile fetch that
         positively returns username = null — never on a failed or pending fetch
       - pageshow (bfcache) triggers a silent re-check instead of a re-prompt   */
  var CACHE_KEY = 'tbi.profile.v1';
  function readCache() { try { return JSON.parse(localStorage.getItem(CACHE_KEY) || 'null'); } catch (e) { return null; } }
  function writeCache(p) { try { p ? localStorage.setItem(CACHE_KEY, JSON.stringify(p)) : localStorage.removeItem(CACHE_KEY); } catch (e) {} }

  var authListeners = [];
  T.onAuth = function (fn) { authListeners.push(fn); if (authResolved) fn(T.user, T.me); };
  var authResolved = false;

  function paintAuth() {
    var zone = $('#authzone'); if (!zone) return;
    if (T.user) {
      var name = (T.me && T.me.username) || 'Account';
      zone.innerHTML = '<a class="uchip" href="/account.html" title="My account"><span class="av">' + esc(initials(name).slice(0, 2)) + '</span>' + esc(name) + (T.unread ? ' <span class="pendtag" style="background:var(--gold2);color:#14293f">' + T.unread + '</span>' : '') + (T.me && T.me.is_admin ? ' <span class="pendtag">admin</span>' : '') + '</a>';
    } else {
      zone.innerHTML = '<a class="hbtn ghost" href="#" data-auth>Sign in</a>';
    }
    document.querySelectorAll('[data-auth]').forEach(function (a) { a.onclick = function (e) { e.preventDefault(); T.openAuth(); }; });
    document.querySelectorAll('[data-auth-mobile]').forEach(function (a) { if (T.user) { a.textContent = 'My account'; a.href = '/account.html'; a.onclick = null; } else { a.onclick = function (e) { e.preventDefault(); T.openAuth(); }; } });
  }

  async function onUser(u, opts) {
    opts = opts || {};
    T.user = u;
    if (u) {
      var cached = readCache();
      if (cached && cached.id === u.id) { T.me = cached; paintAuth(); }
      var res = await sb.from('profiles').select('*').eq('id', u.id).maybeSingle();
      if (!res.error && res.data) {
        T.me = res.data; writeCache(res.data);
        if (!res.data.username && !opts.silent) openUsername();
      } else if (!T.me) {
        T.me = { id: u.id };   // fetch failed: keep signed-in state, never re-prompt
      }
      var n = await sb.from('notifications').select('id', { count: 'exact', head: true }).eq('user_id', u.id).eq('read', false);
      T.unread = (n && n.count) || 0;
    } else { T.me = null; T.unread = 0; T.myList = []; writeCache(null); }
    paintAuth();
    authResolved = true;
    authListeners.forEach(function (fn) { try { fn(T.user, T.me); } catch (e) { console.error(e); } });
  }

  T.openAuth = function (title) {
    modal('<div class="mhead"><h3>' + esc(title || 'Sign in or join') + '</h3><button class="x" onclick="TBI.closeModal()">&#10005;</button></div>'
      + '<div class="mbody">'
      + '<button class="gbtn" onclick="TBI.googleSignIn()"><svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.3 6.1 29.4 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.3 6.1 29.4 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 40.4 44 35 44 24c0-1.3-.1-2.6-.4-3.9z"/></svg>Continue with Google</button>'
      + '<div class="ordiv"><span>or</span></div>'
      + '<p class="hint">No password needed — we email you a one-time sign-in link.</p>'
      + '<label class="fl" for="au-email">Email</label><input class="fi" id="au-email" type="email" placeholder="you@example.com" onkeydown="if(event.key===\'Enter\')TBI.sendLink()">'
      + '<div class="msg" id="au-msg"></div>'
      + '<div style="margin-top:16px"><button class="btn navy wide" id="au-btn" onclick="TBI.sendLink()">Email me a sign-in link</button></div></div>', true);
    setTimeout(function () { var i = $('#au-email'); if (i) i.focus(); }, 50);
  };
  T.googleSignIn = async function () {
    var r = await sb.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: location.origin + location.pathname + location.search } });
    if (r.error) { var m = $('#au-msg'); m.className = 'msg err'; m.textContent = 'Google sign-in isn’t enabled yet — use the email link below.'; }
  };
  T.sendLink = async function () {
    var email = $('#au-email').value.trim(), m = $('#au-msg');
    if (!/.+@.+\..+/.test(email)) { m.className = 'msg err'; m.textContent = 'Enter a valid email.'; return; }
    $('#au-btn').disabled = true;
    var r = await sb.auth.signInWithOtp({ email: email, options: { emailRedirectTo: location.origin + location.pathname + location.search } });
    $('#au-btn').disabled = false;
    if (r.error) { m.className = 'msg err'; m.textContent = r.error.message; return; }
    m.className = 'msg ok'; m.textContent = 'Link sent. Check your inbox (and spam) and click it to sign in.';
  };
  function openUsername() {
    modal('<div class="mhead"><h3>Pick your username</h3></div><div class="mbody">'
      + '<p class="hint" style="margin-top:-4px">Shown publicly on your reviews and profile. Your email stays private.</p>'
      + '<label class="fl" for="un-name">Username</label><input class="fi" id="un-name" maxlength="24" placeholder="e.g. TexasAcquirer">'
      + '<label class="fl" for="un-role">I’m primarily a…</label><select class="fi" id="un-role"><option value="seller">Seller</option><option value="buyer">Buyer</option><option value="both">Both</option><option value="broker">Business broker</option><option value="other">Other</option></select>'
      + '<div class="msg" id="un-msg"></div><div style="margin-top:16px"><button class="btn navy wide" onclick="TBI.saveUsername()">Save</button></div></div>', true);
  }
  T.saveUsername = async function () {
    var name = $('#un-name').value.trim(), m = $('#un-msg');
    if (name.length < 3) { m.className = 'msg err'; m.textContent = 'At least 3 characters.'; return; }
    var r = await sb.from('profiles').update({ username: name, role: $('#un-role').value }).eq('id', T.user.id);
    if (r.error) { m.className = 'msg err'; m.textContent = r.error.code === '23505' ? 'That username is taken.' : r.error.message; return; }
    T.me.username = name; T.me.role = $('#un-role').value; writeCache(T.me); closeModal(); paintAuth(); toast('Welcome, ' + name + '!');
  };
  T.signOut = async function () { await sb.auth.signOut(); writeCache(null); closeModal(); toast('Signed out'); if (/account|admin/.test(location.pathname)) location.href = '/'; };
  T.requireUser = function (why) { if (T.user) return true; T.openAuth(why || 'Sign in to continue'); return false; };

  /* ------------------------------------------------------------ data */
  var loaded = null;
  T.load = function (opts) {
    opts = opts || {};
    if (loaded && !opts.force) return loaded;
    loaded = (async function () {
      var lim = opts.limitBrokers ? sb.from('brokers').select('*').order('name').limit(opts.limitBrokers) : sb.from('brokers').select('*').limit(5000);
      var res = await Promise.all([
        lim,
        sb.from('reviews').select('*').eq('status', 'published').limit(10000),
        sb.from('profiles').select('id,username,tier,headline,role').limit(10000),
        sb.from('review_votes').select('review_id,voter_id,value').limit(50000)
      ]);
      if (res[0].error) throw res[0].error;
      T.brokers = res[0].data || []; T.reviews = res[1].data || [];
      T.profilesById = {}; (res[2].data || []).forEach(function (p) { T.profilesById[p.id] = p; });
      T.votes = {}; T.myVote = new Map();
      (res[3].data || []).forEach(function (x) { var v = x.value == null ? 1 : x.value; T.votes[x.review_id] = (T.votes[x.review_id] || 0) + v; if (T.user && x.voter_id === T.user.id) T.myVote.set(x.review_id, v); });
      computeScores();
      return T;
    })();
    return loaded;
  };
  T.stats = async function () { var r = await sb.rpc('site_stats'); return r.data || null; };

  /* ------------------------------------------------------------ scoring
     Composite = mean of the six parameters, 0–10. Per-review weights:
     verified reviewer 1.0 vs member 0.55, recency half-life 18 months.
     Bayesian shrinkage toward the site prior so 2 glowing reviews cannot
     outrank 40 solid ones. Seller and buyer sides computed separately; the
     overall is volume-weighted, not the average of the two sides.          */
  function shrink(list, prior, M) {
    if (!list.length) return null;
    var W = 0, raw = 0; list.forEach(function (x) { W += x.w; raw += x.overall * x.w; }); raw /= W;
    var score = (W * raw + M * prior) / (W + M);
    var params = {};
    PARAMS.forEach(function (p) { var k = p[0], sw = 0, s = 0; list.forEach(function (x) { if (x.r[k]) { sw += x.w; s += x.r[k] * x.w; } }); if (sw) params[k] = to10(s / sw); });
    return { score: to10(score), W: W, count: list.length, params: params, conf: W < 1.2 ? 'Provisional' : W < 3 ? 'Early' : 'Established' };
  }
  function computeScores() {
    var now = Date.now(), by = {};
    T.reviews.forEach(function (r) {
      var vals = Object.keys(r.ratings || {}).map(function (k) { return Number(r.ratings[k]); }).filter(function (v) { return v >= 1 && v <= 5; });
      if (!vals.length || !r.broker_id) return;
      var overall = vals.reduce(function (a, b) { return a + b; }, 0) / vals.length;
      var tier = (T.profilesById[r.author_id] || {}).tier === 'verified' ? 1.0 : 0.55;
      var months = Math.max(0, (now - new Date(r.created_at).getTime()) / (30.44 * 864e5));
      var w = tier * Math.pow(0.5, months / 18);
      (by[r.broker_id] = by[r.broker_id] || []).push({ overall: overall, w: w, side: r.side || '', r: r.ratings || {}, at: r.created_at });
    });
    var sw = 0, sww = 0; Object.keys(by).forEach(function (k) { by[k].forEach(function (x) { sw += x.overall * x.w; sww += x.w; }); });
    var prior = sww ? sw / sww : 4.0, M = 2.5;
    T.scores = {};
    Object.keys(by).forEach(function (bid) {
      var l = by[bid], o = shrink(l, prior, M);
      o.seller = shrink(l.filter(function (x) { return x.side === 'seller' || x.side === 'both'; }), prior, M);
      o.buyer = shrink(l.filter(function (x) { return x.side === 'buyer' || x.side === 'both'; }), prior, M);
      var cutoff = now - 365 * 864e5; o.recent = l.filter(function (x) { return new Date(x.at).getTime() > cutoff; }).length;
      // 6-month trend: mean of the last 6 months vs the 6 before, only when both halves have ≥2 reviews
      var h6 = now - 182 * 864e5, h12 = now - 365 * 864e5;
      var a = l.filter(function (x) { return new Date(x.at).getTime() > h6; }), b = l.filter(function (x) { var t = new Date(x.at).getTime(); return t <= h6 && t > h12; });
      var mean = function (xs) { return xs.reduce(function (s, x) { return s + x.overall; }, 0) / xs.length; };
      o.trend = (a.length >= 2 && b.length >= 2) ? to10(mean(a)) - to10(mean(b)) : null;
      T.scores[bid] = o;
    });
  }
  T.computeScores = computeScores;
  // What may be shown, given the minimum thresholds
  T.shown = function (sc) { return sc && sc.count >= MIN.score ? sc : null; };
  T.shownSide = function (sc, side) { var s = sc && sc[side]; return s && s.count >= MIN.side ? s : null; };
  T.modeScore = function (bid, mode) { var s = T.scores[bid]; if (!s) return null; return mode === 'overall' ? T.shown(s) : T.shownSide(s, mode); };
  T.fmt = function (v) { return v.toFixed(2); };
  T.confClass = function (c) { return c === 'Established' ? 'est' : c === 'Early' ? 'early' : 'prov'; };
  T.reviewOverall = function (r) { var v = Object.keys(r.ratings || {}).map(function (k) { return Number(r.ratings[k]); }).filter(function (x) { return x >= 1; }); return v.length ? to10(v.reduce(function (a, b) { return a + b; }, 0) / v.length) : null; };

  /* firm-level aggregation (rankings page & brokerage reports)
     firm score 70% (volume-weighted mean of ranked agents) + consistency 20%
     (inverse spread between agents) + coverage 10% (share of agents with a score) */
  T.firms = function () {
    var by = {};
    T.brokers.forEach(function (b) { var f = (b.firm || 'Independent').trim(); if (!f || f === 'Independent' || f === '—') return; (by[f] = by[f] || []).push(b); });
    return Object.keys(by).map(function (f) {
      var agents = by[f], scored = agents.map(function (b) { return { b: b, s: T.scores[b.id] }; }).filter(function (x) { return x.s && x.s.count >= MIN.score; });
      var reviews = agents.reduce(function (n, b) { return n + ((T.scores[b.id] || {}).count || 0); }, 0);
      if (!scored.length) return { firm: f, agents: agents, scored: scored, reviews: reviews, eligible: false };
      var W = 0, s = 0; scored.forEach(function (x) { W += x.s.W; s += x.s.score * x.s.W; });
      var mean = s / W;
      var vals = scored.map(function (x) { return x.s.score; }), spread = Math.max.apply(null, vals) - Math.min.apply(null, vals);
      var consistency = scored.length > 1 ? Math.max(0, 1 - spread / 4) : 0.75;   // 4 points of spread = zero consistency
      var coverage = scored.length / agents.length;
      var composite = mean * 0.7 + (consistency * 10) * 0.2 + (coverage * 10) * 0.1;
      var states = {}; agents.forEach(function (b) { if (b.state && b.state !== '—') states[b.state] = 1; });
      var trends = scored.map(function (x) { return x.s.trend; }).filter(function (t) { return t != null; });
      return { firm: f, agents: agents, scored: scored, reviews: reviews, mean: mean, consistency: consistency, coverage: coverage, composite: composite, spread: spread,
        states: Object.keys(states), eligible: reviews >= MIN.firm && scored.length >= MIN.firmAgents,
        trend: trends.length ? trends.reduce(function (a, b) { return a + b; }, 0) / trends.length : null,
        top: scored.slice().sort(function (a, b) { return b.s.score - a.s.score; })[0] };
    });
  };

  /* ------------------------------------------------------------ reviews UI */
  T.renderReview = function (r, opts) {
    opts = opts || {};
    var p = T.profilesById[r.author_id] || {}, ov = T.reviewOverall(r), mine = T.user && r.author_id === T.user.id;
    var who = opts.brokerLink ? '<a class="who" href="/broker-' + esc(opts.brokerLink) + '.html">' + esc(opts.brokerName || 'Broker') + '</a>' : '<a class="who" href="/account.html?u=' + esc(p.username || '') + '">' + esc(p.username || 'Member') + '</a>';
    return '<div class="rev" id="rev-' + r.id + '"><div class="rtop">' + who
      + (p.tier === 'verified' ? '<span class="vbadge">Verified</span>' : '')
      + (r.side === 'seller' ? '<span class="sidetag sell">Seller</span>' : r.side === 'buyer' ? '<span class="sidetag buy">Buyer</span>' : '')
      + (r.status === 'pending' ? '<span class="pendtag">Pending</span>' : '')
      + (ov != null ? '<span class="rscore">' + T.fmt(ov) + '<small style="color:var(--mut);font-weight:400"> /10</small></span>' : '')
      + '<time>' + fmtDate(r.created_at) + '</time></div>'
      + (r.text ? '<div class="rtxt">' + esc(r.text) + '</div>' : '')
      + '<div class="rctx">' + esc([r.stage, r.industry, r.deal_size, r.ctx].filter(Boolean).join(' · ')) + '</div>'
      + '<div class="ract">' + T.voteWidget(r.id)
      + (mine ? '<a href="/write-a-review.html?edit=' + r.id + '">Edit</a>' : '<button onclick="TBI.reportReview(\'' + r.id + '\')">Report</button>')
      + (T.me && T.me.is_admin ? '<button class="danger" onclick="TBI.adminRemoveReview(\'' + r.id + '\')">Remove (admin)</button>' : '')
      + '</div></div>';
  };
  T.voteWidget = function (rid) {
    var net = T.votes[rid] || 0, mv = T.myVote.get(rid) || 0;
    return '<span class="votes" id="vote-' + rid + '"><button class="vbtn up ' + (mv === 1 ? 'on' : '') + '" title="Helpful" onclick="TBI.vote(\'' + rid + '\',1)">&#9650;</button><b class="vnet ' + (net > 0 ? 'pos' : net < 0 ? 'neg' : '') + '">' + (net > 0 ? '+' + net : net) + '</b><button class="vbtn down ' + (mv === -1 ? 'on' : '') + '" title="Not helpful" onclick="TBI.vote(\'' + rid + '\',-1)">&#9660;</button><span class="vlbl">helpful?</span></span>';
  };
  T.vote = async function (rid, dir) {
    if (!T.requireUser('Sign in to vote on reviews')) return;
    var cur = T.myVote.get(rid) || 0, r;
    if (cur === dir) { r = await sb.from('review_votes').delete().eq('review_id', rid).eq('voter_id', T.user.id); if (r.error) return toast(r.error.message); T.myVote.delete(rid); T.votes[rid] = (T.votes[rid] || 0) - dir; }
    else { r = await sb.from('review_votes').upsert({ review_id: rid, voter_id: T.user.id, value: dir }, { onConflict: 'review_id,voter_id' }); if (r.error) return toast(r.error.message); T.votes[rid] = (T.votes[rid] || 0) - cur + dir; T.myVote.set(rid, dir); }
    var el = document.getElementById('vote-' + rid); if (el) el.outerHTML = T.voteWidget(rid);
  };
  T.reportReview = async function (rid) {
    if (!T.requireUser('Sign in to report a review')) return;
    var reason = prompt('Why are you reporting this review? (e.g. not first-hand, names a third party, wrong broker)'); if (!reason) return;
    var r = await sb.from('reports').insert({ review_id: rid, reporter_id: T.user.id, reason: reason.slice(0, 200) });
    toast(r.error ? r.error.message : 'Reported — a moderator will take a look.');
  };
  T.adminRemoveReview = async function (rid) {
    if (!confirm('Remove this review from the site?')) return;
    var r = await sb.from('reviews').update({ status: 'removed' }).eq('id', rid); if (r.error) return toast(r.error.message);
    toast('Review removed'); location.reload();
  };

  /* ------------------------------------------------------------ badges: shields, earned only (no points) */
  function shield(fill, inner) { return '<svg viewBox="0 0 44 50" aria-hidden="true"><path d="M22 2l18 6v14c0 12-8 20-18 26C12 42 4 34 4 22V8z" fill="' + fill + '"/>' + inner + '</svg>'; }
  T.badgesFor = function (uid) {
    var rs = T.reviews.filter(function (r) { return r.author_id === uid; });
    var helpful = 0, detailed = 0; rs.forEach(function (r) { helpful += Math.max(0, T.votes[r.id] || 0); if ((r.text || '').length >= 200) detailed++; });
    var p = T.profilesById[uid] || (T.me && T.me.id === uid ? T.me : {});
    var sides = {}; rs.forEach(function (r) { if (r.side) sides[r.side] = 1; });
    var all = [
      { label: 'Verified member', on: p.tier === 'verified', svg: shield('#14293f', '<path d="M14 25l5 5 11-12" fill="none" stroke="#dfa920" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>') },
      { label: 'First review', on: rs.length >= 1, svg: shield('#b8860b', '<text x="22" y="30" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="16" fill="#14293f">1</text>') },
      { label: '5 reviews', on: rs.length >= 5, svg: shield('#dfa920', '<text x="22" y="30" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="16" fill="#14293f">5</text>') },
      { label: '15 reviews', on: rs.length >= 15, svg: shield('#101c2c', '<text x="22" y="30" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="15" fill="#dfa920">15</text>') },
      { label: 'Both sides of the table', on: sides.buyer && sides.seller, svg: shield('#3b5a7a', '<path d="M12 22h20M26 16l6 6-6 6M18 28l-6-6 6-6" fill="none" stroke="#f2ede2" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>') },
      { label: 'Detailed reviewer', on: detailed >= 3, svg: shield('#1c7c4a', '<path d="M14 18h16M14 24h16M14 30h10" fill="none" stroke="#f2ede2" stroke-width="2.6" stroke-linecap="round"/>') },
      { label: 'Found helpful', on: helpful >= 10, svg: shield('#1d5fa8', '<path d="M22 12l3 7h7l-5.5 4.5 2 7.5-6.5-4.5-6.5 4.5 2-7.5L12 19h7z" fill="#f2ede2"/>') }
    ];
    return all.filter(function (b) { return b.on; });
  };
  T.renderShields = function (uid) {
    var b = T.badgesFor(uid);
    if (!b.length) return '<p class="hint">No badges yet — the first review earns one.</p>';
    return '<div class="shields">' + b.map(function (x) { return '<div class="shield" title="' + esc(x.label) + '">' + x.svg + '<span>' + esc(x.label) + '</span></div>'; }).join('') + '</div>';
  };

  /* ------------------------------------------------------------ My List (ranked) */
  T.loadMyList = async function () {
    if (!T.user) { T.myList = []; return T.myList; }
    var r = await sb.from('watchlists').select('broker_id,rank,note,created_at').eq('user_id', T.user.id).order('rank').order('created_at');
    T.myList = r.data || []; return T.myList;
  };
  T.inList = function (bid) { return T.myList.some(function (x) { return x.broker_id === bid; }); };
  T.toggleList = async function (bid) {
    if (!T.requireUser('Sign in to save brokers to My List')) return false;
    if (T.inList(bid)) { await sb.from('watchlists').delete().eq('user_id', T.user.id).eq('broker_id', bid); T.myList = T.myList.filter(function (x) { return x.broker_id !== bid; }); toast('Removed from My List'); }
    else { var rank = T.myList.length + 1; var r = await sb.from('watchlists').insert({ user_id: T.user.id, broker_id: bid, rank: rank }); if (r.error) return toast(r.error.message); T.myList.push({ broker_id: bid, rank: rank, note: '' }); toast('Saved to My List (#' + rank + ')'); }
    return true;
  };
  T.saveListOrder = async function () {
    for (var i = 0; i < T.myList.length; i++) { T.myList[i].rank = i + 1; }
    await Promise.all(T.myList.map(function (x) { return sb.from('watchlists').update({ rank: x.rank }).eq('user_id', T.user.id).eq('broker_id', x.broker_id); }));
  };

  /* ------------------------------------------------------------ broker profile "live" block (generated pages) */
  T.renderBrokerLive = async function (slug, el) {
    try { await T.load(); } catch (e) { el.innerHTML = '<p class="hint">Live ratings unavailable right now.</p>'; return; }
    var b = T.brokers.find(function (x) { return x.slug === slug; });
    if (!b) { el.innerHTML = '<p class="hint">This listing is not in the live directory right now.</p>'; return; }
    var sc = T.scores[b.id], full = T.shown(sc), s = T.shownSide(sc, 'seller'), u = T.shownSide(sc, 'buyer');
    var revs = T.reviews.filter(function (r) { return r.broker_id === b.id; }).sort(function (a, c) { return new Date(c.created_at) - new Date(a.created_at); });
    var first = b.name.split(' ')[0];
    var box = function (lab, x, cls, who) { return '<div class="panel ' + (cls || '') + '"><div class="scorebox"><div class="lab">' + lab + '</div>' + (x ? '<div class="big' + (who === 'buy' ? ' gold' : '') + '">' + T.fmt(x.score) + '<small>/ 10</small></div><div class="n">' + x.count + ' review' + (x.count === 1 ? '' : 's') + (who ? ' from ' + who + 's' : ' · ' + x.conf) + '</div>' : '<div class="big" style="font-size:22px;color:var(--mut)">Not yet rated</div><div class="n">Be the first to rate ' + esc(first) + '</div>') + '</div></div>'; };
    var cmp = '';
    if (s || u) {
      cmp = '<div class="panel section"><div class="sechead"><div><h2>How buyers and sellers see ' + esc(first) + '</h2><p class="sub">Same six parameters, rated separately by each side of the table.</p></div><div class="legend"><span><i></i>Sellers</span><span><i class="buy"></i>Buyers</span></div></div>'
        + PARAMS.map(function (p) { var sv = s && s.params[p[0]], bv = u && u.params[p[0]]; return '<div class="cmprow"><div class="lab">' + p[1] + '</div><div class="bars"><div class="bar"><i style="width:' + (sv ? sv * 10 : 0) + '%"></i></div><div class="bar buy"><i style="width:' + (bv ? bv * 10 : 0) + '%"></i></div></div><div class="vals"><span>' + (sv ? T.fmt(sv) : '—') + '</span><span class="b">' + (bv ? T.fmt(bv) : '—') + '</span></div></div>'; }).join('')
        + (function () { if (!(s && u)) return '<p class="hint" style="margin-top:8px">' + (s ? 'No buyer' : 'No seller') + ' reviews yet — the comparison fills in once both sides have rated ' + esc(first) + '.</p>'; var gaps = PARAMS.map(function (p) { return { l: p[1], d: (s.params[p[0]] || 0) - (u.params[p[0]] || 0) }; }).sort(function (a, c) { return Math.abs(c.d) - Math.abs(a.d); }); var g = gaps[0]; if (Math.abs(g.d) < 0.5) return '<p class="hint" style="margin-top:8px">Buyers and sellers largely agree.</p>'; return '<div class="notice blue" style="margin-top:10px"><span><b>Biggest gap:</b> ' + (g.d > 0 ? 'sellers' : 'buyers') + ' rate ' + g.l.toLowerCase() + ' ' + T.fmt(Math.abs(g.d)) + ' points higher than ' + (g.d > 0 ? 'buyers' : 'sellers') + ' do.</span></div>'; })()
        + '</div>';
    } else if (full) {
      cmp = '<div class="panel section"><h2>Rated parameters</h2><div class="params">' + PARAMS.filter(function (p) { return full.params[p[0]]; }).map(function (p) { return '<div class="prow"><span>' + p[1] + '</span><span class="bar"><i style="width:' + (full.params[p[0]] * 10) + '%"></i></span><b>' + T.fmt(full.params[p[0]]) + '</b></div>'; }).join('') + '</div></div>';
    }
    var bio = b.bio ? '<div class="panel section"><h2 style="font-size:20px">About ' + esc(first) + '</h2><p style="margin-top:8px;font-size:15px;line-height:1.6;color:var(--ink2);white-space:pre-wrap">' + esc(b.bio) + '</p><p class="hint" style="margin-top:8px">Written by the broker. Reviews and scores are independent.</p></div>' : '';
    el.innerHTML = '<div class="cols3">' + box('Overall', full, 'navy') + box('Rated by sellers', s, '', 'seller') + box('Rated by buyers', u, '', 'buyer') + '</div>' + cmp + bio
      + '<div class="section"><div class="sechead"><h2>Reviews <span class="chip">' + revs.length + '</span></h2><a class="btn gold" href="/write-a-review.html?broker=' + esc(slug) + '">Write a review</a></div>'
      + (revs.length ? revs.map(function (r) { return T.renderReview(r); }).join('') : '<p class="hint">No reviews yet. Worked with ' + esc(first) + '? Your review starts their record.</p>') + '</div>'
      + '<div id="listings"></div>';
    T.renderListings(b, document.getElementById('listings'));
    var save = document.getElementById('save-list'); if (save) { await T.loadMyList(); var paint = function () { save.textContent = T.inList(b.id) ? '★ Saved to My List' : '☆ Save to My List'; }; paint(); save.onclick = async function (e) { e.preventDefault(); if (await T.toggleList(b.id)) paint(); }; }
  };


  /* ------------------------------------------------------------ broker listings (claimed pages only; compact, below reviews) */
  T.renderListings = async function (b, el) {
    if (!el || !b.claimed_by) return;
    var r = await sb.from('listings').select('id,title,industry,state,price_label,summary,url,contact_email').eq('broker_id', b.id).eq('status', 'active').order('created_at');
    var ls = r.data || []; if (!ls.length) return;
    var first = b.name.split(' ')[0];
    el.innerHTML = '<details class="section" style="border:1px solid var(--line2);border-radius:14px;background:var(--card);padding:0 20px">'
      + '<summary style="cursor:pointer;padding:16px 0;font-weight:700;color:var(--ink);display:flex;justify-content:space-between;align-items:center"><span>Businesses ' + esc(first) + ' is currently representing <span class="chip">' + ls.length + '</span></span><span class="hint">Posted by the broker</span></summary>'
      + '<div class="rlist" style="padding-bottom:16px">' + ls.map(function (l) {
        return '<div class="rrow" style="align-items:flex-start"><div style="flex:1;min-width:0"><div class="nm">' + esc(l.title) + '</div><div class="mt">' + esc([l.industry, l.state, l.price_label].filter(Boolean).join(' \u00b7 ')) + '</div>' + (l.summary ? '<div class="mt" style="margin-top:4px;color:var(--ink2)">' + esc(l.summary) + '</div>' : '') + '</div>'
          + '<div style="display:flex;gap:6px;flex-shrink:0">' + (l.url ? '<a class="btn line sm" target="_blank" rel="noopener nofollow" href="' + esc(l.url) + '">Details</a>' : '') + '<button class="btn navy sm" onclick="TBI.inquire(\'' + l.id + '\',\'' + esc(l.title).replace(/'/g, '&#39;') + '\')">Inquire</button></div></div>';
      }).join('') + '</div><p class="hint" style="padding-bottom:14px">Listings are posted by the broker and don\u2019t affect their rating. Your inquiry goes to the broker only.</p></details>';
  };
  T.inquire = function (lid, title) {
    modal('<div class="mhead"><h3>Inquire about this listing</h3><button class="x" onclick="TBI.closeModal()">&#10005;</button></div><div class="mbody">'
      + '<p class="hint">' + esc(title) + '</p>'
      + '<label class="fl" for="iq-name">Your name</label><input class="fi" id="iq-name" maxlength="80" value="' + esc((T.me && T.me.username) || '') + '">'
      + '<label class="fl" for="iq-email">Email</label><input class="fi" id="iq-email" type="email" value="' + esc((T.user && T.user.email) || '') + '">'
      + '<label class="fl" for="iq-msg">Message</label><textarea class="fi" id="iq-msg" maxlength="800" style="min-height:90px" placeholder="What you\u2019d like to know, and a line about you as a buyer."></textarea>'
      + '<div class="msg" id="iq-m"></div><div style="margin-top:14px"><button class="btn navy wide" onclick="TBI.sendInquiry(\'' + lid + '\')">Send to the broker</button></div></div>', true);
  };
  T.sendInquiry = async function (lid) {
    var m = $('#iq-m'), name = $('#iq-name').value.trim(), email = $('#iq-email').value.trim();
    if (!name || !/.+@.+\..+/.test(email)) { m.className = 'msg err'; m.textContent = 'Name and a valid email are required.'; return; }
    var r = await sb.from('listing_inquiries').insert({ listing_id: lid, user_id: T.user ? T.user.id : null, name: name, email: email, message: $('#iq-msg').value.trim() });
    if (r.error) { m.className = 'msg err'; m.textContent = r.error.message; return; }
    closeModal(); toast('Sent. The broker will reply to your email.');
  };

  /* ------------------------------------------------------------ boot */
  sb.auth.onAuthStateChange(function (ev, session) { if (ev === 'INITIAL_SESSION') return; onUser(session ? session.user : null, { silent: ev === 'TOKEN_REFRESHED' }); });
  window.addEventListener('pageshow', function (e) { if (e.persisted) sb.auth.getSession().then(function (r) { onUser(r.data.session ? r.data.session.user : null, { silent: true }); }); });
  T.ready = (async function () {
    var cached = readCache(); if (cached) { T.me = cached; T.user = { id: cached.id }; }
    document.addEventListener('tbi:shell-ready', paintAuth);
    if (document.getElementById('authzone')) paintAuth();
    var r = await sb.auth.getSession();
    await onUser(r.data.session ? r.data.session.user : null);
    return T;
  })();

  window.TBI = T;
})();
