/* ============================================================================
   The Broker Index — site shell
   ONE source of truth for the header nav, mobile menu, footer and the
   first-visit entry modal. Every page includes:
     <div id="site-header"></div>  ...page...  <div id="site-footer"></div>
     <script src="/_shell.js"></script>
   Adding or renaming a nav item = editing NAV below, nowhere else.
   ========================================================================== */
(function () {
  'use strict';

  var NAV = [
    { href: '/prospective-sellers.html', label: 'Prospective Sellers', key: 'sellers' },
    { href: '/prospective-buyers.html',  label: 'Prospective Buyers',  key: 'buyers'  },
    { href: '/tools.html',               label: 'Tools',               key: 'tools'   },
    { href: '/methodology.html',         label: 'Methodology',         key: 'method'  },
    { href: '/account.html',             label: 'My List',             key: 'account' }
  ];
  var CTA = { href: '/find-my-perfect-broker.html', label: 'Find My Perfect Broker', key: 'quiz' };

  var FOOTER = [
    { h: 'For sellers', links: [
      ['/find-my-perfect-broker.html', 'Find a broker'],
      ['/write-a-review.html', 'Write a review'],
      ['/prospective-sellers.html', 'Guides for sellers'],
      ['/business-valuation-calculator.html', 'What is my business worth?'] ] },
    { h: 'For buyers', links: [
      ['/', 'Browse brokers'],
      ['/write-a-review.html', 'Write a review'],
      ['/prospective-buyers.html', 'Guides for buyers'],
      ['/account.html', 'My List & deal tracker'] ] },
    { h: 'Tools', links: [
      ['/find-my-perfect-broker.html', 'Find My Perfect Broker'],
      ['/business-valuation-calculator.html', 'Valuation calculator'],
      ['/brokerage-rankings.html', 'Brokerage rankings'],
      ['/business-brokers-by-state.html', 'Brokers by state'],
      ['/tools.html', 'All tools'] ] },
    { h: 'Company', links: [
      ['/about.html', 'About'],
      ['/methodology.html', 'Methodology'],
      ['/articles.html', 'Articles'],
      ['/claim.html', 'Brokers: claim your page'],
      ['/broker-dashboard.html', 'Brokers: manage your page'],
      ['mailto:hello@ratemybusinessbroker.com', 'Contact'] ] }
  ];

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); }

  var active = (document.body.getAttribute('data-nav') || '').trim();

  function header() {
    var links = NAV.map(function (n) {
      return '<a class="nl' + (n.key === active ? ' on' : '') + '" href="' + n.href + '"' + (n.key === active ? ' aria-current="page"' : '') + '>' + esc(n.label) + '</a>';
    }).join('');
    var mob = NAV.concat([]).map(function (n) { return '<a href="' + n.href + '">' + esc(n.label) + '</a>'; }).join('')
      + '<a class="solid" href="' + CTA.href + '">' + esc(CTA.label) + '</a>'
      + '<a href="/write-a-review.html">Write a review</a>'
      + '<a href="#" data-auth-mobile>Sign in</a>';
    return '<header>'
      + '<div class="wrap hbar">'
      + '<button class="burger" type="button" aria-label="Menu" aria-expanded="false" data-burger>'
      + '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>'
      + '<a class="brand" href="/"><span class="mark">B</span><b>The Broker Index</b></a>'
      + '<nav class="nav" aria-label="Primary">' + links
      + '<a class="hbtn solid" href="' + CTA.href + '">' + esc(CTA.label) + '</a>'
      + '<span id="authzone"><a class="hbtn ghost" href="#" data-auth>Sign in</a></span>'
      + '</nav></div>'
      + '<div class="mnav" data-mnav>' + mob + '</div>'
      + '</header>';
  }

  function footer() {
    var cols = FOOTER.map(function (c) {
      return '<div><h5>' + esc(c.h) + '</h5>' + c.links.map(function (l) { return '<a href="' + l[0] + '">' + esc(l[1]) + '</a>'; }).join('') + '</div>';
    }).join('');
    return '<footer class="site"><div class="wrap">'
      + '<div class="fcols"><div><div class="fbrand">The Broker Index</div>'
      + '<div class="fdesc">Independent ratings of M&amp;A business brokers from the buyers and sellers who worked with them. Six parameters. No pay-to-play. Ratings reflect the opinions of individual reviewers, not the site.</div></div>'
      + cols + '</div>'
      + '<div class="fbot"><span>&copy; ' + new Date().getFullYear() + ' The Broker Index &middot; ratemybusinessbroker.com</span>'
      + '<span><a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a><a href="/methodology.html#moderation">How reviews are moderated</a></span></div>'
      + '</div></footer>';
  }

  // ---- entry modal (homepage, first visit only, delayed so it is not an interstitial on load)
  function entryModal() {
    if (document.body.getAttribute('data-entry') !== 'home') return;
    try { if (localStorage.getItem('tbi.entry.seen')) return; } catch (e) { return; }
    var el = document.createElement('div');
    el.className = 'entry';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-modal', 'true');
    el.setAttribute('aria-labelledby', 'entry-h');
    el.innerHTML = '<div class="box">'
      + '<button class="x" type="button" aria-label="Close" data-close>&#10005;</button>'
      + '<div class="ic"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#dfa920" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg></div>'
      + '<h2 id="entry-h" class="serif">Are you a prospective seller looking for the perfect broker?</h2>'
      + '<p>Take a two-minute quiz and we’ll find them for you — matched on your location, industry, and what matters most to you.</p>'
      + '<a class="btn gold wide" href="/find-my-perfect-broker.html">Take the quiz</a>'
      + '<div class="foot"><button type="button" class="lnk" data-close style="color:var(--mut)">Not right now</button>'
      + '<a href="/claim.html">Are you a broker? Claim your page</a></div>'
      + '</div>';
    function close() { try { localStorage.setItem('tbi.entry.seen', '1'); } catch (e) {} el.remove(); document.removeEventListener('keydown', onKey); }
    function onKey(e) { if (e.key === 'Escape') close(); }
    el.addEventListener('click', function (e) { if (e.target === el || e.target.closest('[data-close]')) close(); });
    el.querySelector('a.btn').addEventListener('click', function () { try { localStorage.setItem('tbi.entry.seen', '1'); } catch (e) {} });
    document.addEventListener('keydown', onKey);
    setTimeout(function () { if (!document.querySelector('.overlay')) document.body.appendChild(el); }, 2500);
  }

  function mount() {
    var h = document.getElementById('site-header');
    var f = document.getElementById('site-footer');
    if (h) h.outerHTML = header();
    if (f) f.outerHTML = footer();
    var burger = document.querySelector('[data-burger]'), mnav = document.querySelector('[data-mnav]');
    if (burger && mnav) burger.addEventListener('click', function () {
      var open = mnav.classList.toggle('open');
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    entryModal();
    document.dispatchEvent(new CustomEvent('tbi:shell-ready'));
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();

  window.TBI_SHELL = { NAV: NAV, CTA: CTA, esc: esc };
})();
