// Monthly feedback email to verified (claimed) brokers. Run by .github/workflows/monthly-digest.yml.
// Env: SUPABASE_SERVICE_KEY (service_role — server only, never in the browser),
//      RESEND_API_KEY, DIGEST_FROM (e.g. "The Broker Index <reports@ratemybusinessbroker.com>")
// Rules (from the spec, section 10): skip brokers with no change and no new reviews;
// suppress the composite below the minimum; never editorialise; one-click unsubscribe.
// Test one broker: Actions tab → Monthly broker digest → Run workflow → enter a slug.

const SUPA_URL = 'https://qnxmvzrotgnsgyafewbo.supabase.co';
const SITE = 'https://ratemybusinessbroker.com';
const MIN_SCORE = 3;   // keep in sync with MIN.score in _app.js
const PARAMS = [['professionalism','Professionalism'],['transparency','Transparency'],['consistency','Consistency'],['collaboration','Collaboration'],['command','Command of the deal'],['documentation','Quality of documentation']];

async function sq(path, key) {
  const r = await fetch(`${SUPA_URL}/rest/v1/${path}`, { headers: { apikey: key, Authorization: 'Bearer ' + key } });
  if (!r.ok) throw new Error(`supabase ${r.status} on ${path}`);
  return r.json();
}
const to10 = v => v * 2;
function stats(reviews, tiers, until) {
  const now = until.getTime(), rows = reviews.filter(r => new Date(r.created_at).getTime() <= now);
  if (!rows.length) return null;
  let W = 0, S = 0; const P = {};
  for (const r of rows) {
    const vals = Object.values(r.ratings || {}).map(Number).filter(v => v >= 1 && v <= 5);
    if (!vals.length) continue;
    const overall = vals.reduce((a, b) => a + b, 0) / vals.length;
    const months = Math.max(0, (now - new Date(r.created_at).getTime()) / (30.44 * 864e5));
    const w = (tiers[r.author_id] === 'verified' ? 1 : 0.55) * Math.pow(0.5, months / 18);
    W += w; S += overall * w;
    for (const [k] of PARAMS) if (r.ratings[k]) { P[k] = P[k] || [0, 0]; P[k][0] += w; P[k][1] += r.ratings[k] * w; }
  }
  const params = {}; for (const k in P) params[k] = to10(P[k][1] / P[k][0]);
  return { count: rows.length, score: to10(S / W), params };
}
const fmt = v => v.toFixed(1);
const arrow = d => d == null ? '' : Math.abs(d) < 0.1 ? ' (no change)' : d > 0 ? ` (▲ ${fmt(d)})` : ` (▼ ${fmt(-d)})`;

function render(b, cur, prev, newRevs, rankInState, nInState, unsubUrl) {
  const first = b.name.split(' ')[0];
  const showScore = cur && cur.count >= MIN_SCORE;
  const rows = showScore ? PARAMS.map(([k, l]) => `<tr><td style="padding:6px 0">${l}</td><td style="padding:6px 0;text-align:right;font-weight:700">${cur.params[k] != null ? fmt(cur.params[k]) : '—'}</td><td style="padding:6px 0 6px 10px;color:#71809a">${prev && prev.params[k] != null && cur.params[k] != null ? arrow(cur.params[k] - prev.params[k]) : ''}</td></tr>`).join('') : '';
  const weakest = showScore ? PARAMS.map(([k, l]) => ({ l, v: cur.params[k] })).filter(x => x.v != null).sort((a, b) => a.v - b.v)[0] : null;
  return `<!doctype html><html><body style="font-family:Inter,Arial,sans-serif;color:#101c2c;max-width:600px;margin:0 auto;padding:24px">
  <div style="background:#14293f;color:#f2ede2;border-radius:12px;padding:20px 22px">
    <div style="font-size:12px;letter-spacing:.6px;text-transform:uppercase;opacity:.7">Monthly client feedback</div>
    <div style="font-family:Georgia,serif;font-size:24px;margin-top:4px">${b.name}</div>
    ${showScore ? `<div style="margin-top:14px;font-family:Georgia,serif;font-size:40px;line-height:1">${fmt(cur.score)}<span style="font-size:14px;opacity:.7"> / 10</span><span style="font-size:15px;margin-left:8px;color:#dfa920">${prev && prev.count >= MIN_SCORE ? arrow(cur.score - prev.score) : ''}</span></div><div style="font-size:13px;opacity:.75;margin-top:4px">${cur.count} reviews · ${rankInState ? `#${rankInState} of ${nInState} scored brokers in ${b.state}` : ''}</div>`
      : `<div style="margin-top:14px;font-size:15px">${cur ? cur.count : 0} review${cur && cur.count === 1 ? '' : 's'} so far. Your score appears at ${MIN_SCORE}.</div>`}
  </div>
  ${showScore ? `<h3 style="margin:22px 0 6px">The six parameters</h3><table style="width:100%;border-collapse:collapse;font-size:14px">${rows}</table>
  ${weakest ? `<p style="font-size:14px;color:#3c4a5e;margin-top:14px"><b>One thing to work on:</b> ${weakest.l.toLowerCase()} is your lowest parameter this month at ${fmt(weakest.v)}.</p>` : ''}` : ''}
  ${newRevs.length ? `<h3 style="margin:22px 0 6px">New this month (${newRevs.length})</h3>${newRevs.map(r => `<div style="border:1px solid #efece5;border-radius:10px;padding:12px 14px;margin-bottom:8px;font-size:14px"><div style="font-size:12px;color:#71809a;margin-bottom:4px">${r.side === 'seller' ? 'Seller' : 'Buyer'} · ${r.stage || ''}</div>${(r.text || '').replace(/</g, '&lt;')}</div>`).join('')}` : ''}
  <p style="font-size:14px;margin-top:20px"><a href="${SITE}/broker-${b.slug}.html" style="color:#b8860b;font-weight:700">See your full profile →</a></p>
  <p style="font-size:12px;color:#71809a;margin-top:26px">You receive this because you claimed ${first === b.name ? 'this' : 'your'} profile on The Broker Index. Scores use verification weighting, recency decay and shrinkage — <a href="${SITE}/methodology.html" style="color:#71809a">methodology</a>. <a href="${unsubUrl}" style="color:#71809a">Unsubscribe</a>.</p>
  </body></html>`;
}

async function main() {
  const key = process.env.SUPABASE_SERVICE_KEY, resend = process.env.RESEND_API_KEY, from = process.env.DIGEST_FROM || 'The Broker Index <reports@ratemybusinessbroker.com>';
  if (!key || !resend) { console.error('SUPABASE_SERVICE_KEY / RESEND_API_KEY not configured'); process.exit(1); }
  const only = process.env.ONLY_SLUG || null;
  const brokers = (await sq('brokers?select=id,slug,name,state,claimed_by&claimed_by=not.is.null', key)).filter(b => !only || b.slug === only);
  if (!brokers.length) { console.log('no claimed brokers'); return; }
  const ids = brokers.map(b => b.id);
  const reviews = await sq(`reviews?select=broker_id,author_id,ratings,side,stage,text,created_at&status=eq.published&broker_id=in.(${ids.join(',')})`, key);
  const profiles = await sq('profiles?select=id,tier', key); const tiers = {}; for (const p of profiles) tiers[p.id] = p.tier;
  const owners = await sq(`profiles?select=id,digest_opt_out&id=in.(${brokers.map(b => b.claimed_by).join(',')})`, key).catch(() => []);
  const optOut = new Set(owners.filter(o => o.digest_opt_out).map(o => o.id));
  // ranks within state (this month) — across all scored brokers in the state, not only claimed ones
  const allState = await sq(`reviews?select=broker_id,author_id,ratings,created_at&status=eq.published`, key);
  const byB = {}; for (const r of allState) (byB[r.broker_id] = byB[r.broker_id] || []).push(r);
  const stateOf = {}; for (const b of await sq('brokers?select=id,state', key)) stateOf[b.id] = b.state;
  const now = new Date(), monthAgo = new Date(now.getTime() - 30 * 864e5);
  const scoresNow = {}; for (const id in byB) { const s = stats(byB[id], tiers, now); if (s && s.count >= MIN_SCORE) scoresNow[id] = s.score; }
  let sent = 0, skipped = 0;
  for (const b of brokers) {
    if (optOut.has(b.claimed_by)) { skipped++; continue; }
    const mine = reviews.filter(r => r.broker_id === b.id);
    const cur = stats(mine, tiers, now), prev = stats(mine, tiers, monthAgo);
    const newRevs = mine.filter(r => new Date(r.created_at) > monthAgo);
    const changed = cur && prev ? Math.abs(cur.score - prev.score) >= 0.1 : !!cur !== !!prev;
    if (!newRevs.length && !changed) { skipped++; continue; }   // rule: never send "nothing happened"
    const peers = Object.keys(scoresNow).filter(id => stateOf[id] === b.state).sort((x, y) => scoresNow[y] - scoresNow[x]);
    const rank = peers.indexOf(b.id) + 1;
    const owner = await sq(`auth_email?id=eq.${b.claimed_by}`, key).catch(() => null);   // see DEPLOY-NOTES: create this view
    const to = owner && owner[0] && owner[0].email; if (!to) { skipped++; continue; }
    const unsub = `${SITE}/account.html?digest=off`;
    const html = render(b, cur, prev, newRevs, rank || null, peers.length, unsub);
    const r = await fetch('https://api.resend.com/emails', { method: 'POST', headers: { 'content-type': 'application/json', Authorization: 'Bearer ' + resend },
      body: JSON.stringify({ from, to, subject: `${b.name}: your client feedback for ${now.toLocaleString('en-US', { month: 'long' })}`, html }) });
    if (r.ok) sent++; else skipped++;
  }
  console.log(`sent ${sent}, skipped ${skipped}`);
}
main().catch(e => { console.error(e); process.exit(1); });
