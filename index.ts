// Supabase Edge Function: screen a review's free text before publication.
// Deploy:  supabase functions deploy screen-review --no-verify-jwt
// Secret:  supabase secrets set ANTHROPIC_API_KEY=sk-ant-...
// POST { text, side } → { ok:true } | { ok:false, issues:[...] } ; 503 → client holds review as 'pending'
const SYSTEM = `You screen reviews of business brokers before publication on an independent review site.
The goal is to PROTECT THE REVIEWER (from defamation exposure) and THIRD PARTIES (from being identified), not to soften criticism. Harsh, negative, specific reviews of the broker's own conduct are fine and should pass.
Flag ONLY these:
1. Allegations of crimes or fraud stated as established fact rather than the reviewer's experience or opinion (e.g. "he stole", "she committed fraud"). Opinion framing ("I felt misled", "in my experience they were dishonest about fees") is fine.
2. Names or identifying details of third parties who are not the broker: other buyers, sellers, employees, family members, the specific business sold if named, exact street addresses.
3. Details that would identify the reviewer themselves (their full name, their company name).
4. Contact details, email addresses, phone numbers or links.
5. Content that is clearly not a first-hand experience with this broker (spam, unrelated, copied marketing).
Respond with JSON only: {"ok": true} or {"ok": false, "issues": ["short, specific, actionable instruction to the reviewer, quoting the phrase", ...]}. Max 4 issues.`;

const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type', 'Access-Control-Allow-Methods': 'POST, OPTIONS' };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { ...CORS, 'content-type': 'application/json' } });

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });
  if (req.method !== 'POST') return json({ error: 'POST only' }, 405);
  const key = Deno.env.get('ANTHROPIC_API_KEY');
  if (!key) return json({ ok: null, error: 'screening not configured' }, 503);
  let text = '', side = '';
  try { ({ text = '', side = '' } = await req.json()); } catch { return json({ error: 'bad json' }, 400); }
  text = String(text).slice(0, 2000);
  if (text.trim().length < 20) return json({ ok: true });
  try {
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({ model: Deno.env.get('SCREEN_MODEL') || 'claude-haiku-4-5-20251001', max_tokens: 400, system: SYSTEM,
        messages: [{ role: 'user', content: `Reviewer role: ${side || 'unknown'}\n\nReview text:\n"""\n${text}\n"""` }] })
    });
    if (!r.ok) return json({ ok: null, error: 'upstream ' + r.status }, 503);
    const data = await r.json();
    const raw = (data.content || []).map((c: { text?: string }) => c.text || '').join('');
    const m = raw.match(/\{[\s\S]*\}/);
    const out = m ? JSON.parse(m[0]) : { ok: true };
    if (out.ok !== false) return json({ ok: true });
    return json({ ok: false, issues: (out.issues || []).slice(0, 4).map(String) });
  } catch { return json({ ok: null, error: 'screen failed' }, 503); }
});
