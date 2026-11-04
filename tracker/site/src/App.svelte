<script lang="ts">
  import { LABELS, type RowTuple, type SectionData, type Status, type TrackerData } from './lib/types';
  import { isEmpty, parseQuery, rowMatches, sectionMatches, toggleIs } from './lib/filter';
  import { emptyCounts, pct, tally } from './lib/progress';
  import Ring from './lib/Ring.svelte';

  const fallback: TrackerData = { edit: false, commit: '', repo: null, statuses: [], sections: [], recent: [] };
  const data: TrackerData = $state(window.TRACKER_DATA ?? fallback);
  const STATUSES: Status[] = ['unknown', 'not_implemented', 'partial', 'implemented', 'fully_functional', 'not_planned'];
  const PAGE = 150;

  function readHash(): string {
    const m = /^#q=(.*)$/.exec(location.hash);
    return m ? decodeURIComponent(m[1]) : '';
  }
  let text = $state(readHash());
  let theme = $state(localStorage.getItem('tracker-theme') ?? 'dark');
  let open: Record<string, boolean> = $state({});
  let shown: Record<string, number> = $state({});
  let error = $state('');

  $effect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('tracker-theme', theme);
  });
  $effect(() => {
    const want = text.trim() ? `#q=${encodeURIComponent(text)}` : '';
    if (location.hash !== want) history.replaceState(null, '', want || location.pathname + location.search);
  });
  window.addEventListener('hashchange', () => (text = readHash()));

  const query = $derived(parseQuery(text));
  const active = $derived(!isEmpty(query));
  const all = $derived(data.sections.flatMap((s) => s.rows));
  const overall = $derived(tally(all));
  const perSection = $derived(Object.fromEntries(data.sections.map((s) => [s.id, tally(s.rows)])));
  const view = $derived(
    data.sections
      .map((s) => ({ s, rows: sectionMatches(query, s) ? s.rows.filter((r) => rowMatches(query, r)) : [] }))
      .filter((v) => !active || v.rows.length > 0),
  );
  const matchCount = $derived(view.reduce((n, v) => n + v.rows.length, 0));

  const isOpen = (s: SectionData) => open[s.id] ?? active;
  function toggle(s: SectionData) {
    open[s.id] = !isOpen(s);
  }
  function expandAll(on: boolean) {
    for (const s of data.sections) open[s.id] = on;
  }
  const limit = (id: string) => shown[id] ?? PAGE;

  function linkHref(link: string): string {
    if (/^https?:/.test(link)) return link;
    return data.repo ? `${data.repo}/blob/main/${link}` : '';
  }

  async function setStatus(r: RowTuple, status: Status, note: string, link: string) {
    error = '';
    const before: [Status, string, string] = [r[3], r[4], r[5]];
    r[3] = status;
    r[4] = note;
    r[5] = link;
    try {
      const res = await fetch('/api/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: r[0], status, note, link }),
      });
      const body = await res.json();
      if (!body.ok) throw new Error(body.error);
    } catch (e) {
      [r[3], r[4], r[5]] = before;
      error = `${r[0]}: ${e instanceof Error ? e.message : e}`;
    }
  }

  const SHORT: Record<Status, string> = {
    unknown: 'Unknown',
    not_implemented: 'Not impl.',
    partial: 'Partial',
    implemented: 'Implemented',
    fully_functional: 'Fully',
    not_planned: 'Not planned',
  };
</script>

<header class="top">
  <div class="wrap bar">
    <h1>PoE2 private server <span class="muted">· progress</span></h1>
    <span class="grow"></span>
    {#if data.edit}<span class="tag">editing tracker/status.toml</span>{/if}
    <button class="ghost" onclick={() => (theme = theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">
      {theme === 'dark' ? 'Light' : 'Dark'}
    </button>
  </div>
</header>

<main class="wrap">
  <section class="overall card" aria-label="Overall progress">
    <div class="headline">
      <span class="label">Progress</span>
      <span class="big">{pct(overall.percent)}</span>
      <div class="bar-track" role="progressbar" aria-valuenow={Math.round(overall.percent)} aria-valuemin="0" aria-valuemax="100">
        <div class="bar-fill" style:width="{overall.percent}%"></div>
      </div>
      <span class="muted">of {overall.total.toLocaleString()} rows</span>
    </div>
    <div class="counters">
      {#each STATUSES as st}
        <button
          class="counter st-{st}"
          class:on={query.is.includes(st)}
          onclick={() => (text = toggleIs(text, st))}
          title="Filter: is:{st}"
        >
          <b>{overall.counts[st].toLocaleString()}</b>
          <span>{LABELS[st]}</span>
        </button>
      {/each}
    </div>
    <div class="cards">
      {#each data.sections as s (s.id)}
        {@const t = perSection[s.id] ?? { percent: 0, counts: emptyCounts(), total: 0, done: 0 }}
        <button class="mini" onclick={() => { text = `in:${s.id}`; open[s.id] = true; }} title={s.description}>
          <Ring percent={t.percent} />
          <span class="mini-text"><span class="mini-title">{s.title}</span><span class="faint">{pct(t.percent)} · {t.total.toLocaleString()}</span></span>
        </button>
      {/each}
    </div>
  </section>

  <div class="tools">
    <input
      class="search"
      type="search"
      placeholder="Search…  fireball  is:implemented  -is:fully_functional  in:gems"
      aria-label="Search rows"
      bind:value={text}
    />
    <button class="ghost" onclick={() => expandAll(true)} title="Expand all" aria-label="Expand all">+</button>
    <button class="ghost" onclick={() => expandAll(false)} title="Collapse all" aria-label="Collapse all">−</button>
  </div>
  {#if active}<p class="muted hint">{matchCount.toLocaleString()} matching rows in {view.length} sections.</p>{/if}
  {#if error}<p class="err">{error}</p>{/if}

  <div class="layout">
    <div class="list">
      {#each view as { s, rows } (s.id)}
        {@const t = perSection[s.id]}
        <section class="sec card">
          <button class="sec-head" onclick={() => toggle(s)} aria-expanded={isOpen(s)}>
            <span class="chev" class:open={isOpen(s)}>›</span>
            <span class="sec-title">{s.title}</span>
            <span class="muted count">{t.counts.implemented + t.counts.fully_functional + t.counts.partial}/{t.total.toLocaleString()}</span>
            <span class="mini-bar"><span style:width="{t.percent}%"></span></span>
            <span class="pct">{pct(t.percent)}</span>
          </button>
          {#if isOpen(s)}
            {#if s.description}<p class="desc muted">{s.description}</p>{/if}
            {@const cap = limit(s.id)}
            <ul class="rows">
              {#each rows.slice(0, cap) as r, i (r[0])}
                {#if i === 0 || rows[i - 1][1] !== r[1]}
                  <li class="group">{r[1]}</li>
                {/if}
                <li class="row" title={r[4] || undefined}>
                  {#if data.edit && !r[6]}
                    <select class="pill st-{r[3]}" value={r[3]} onchange={(e) => setStatus(r, e.currentTarget.value as Status, r[4], r[5])}>
                      {#each STATUSES as st}<option value={st}>{LABELS[st]}</option>{/each}
                    </select>
                  {:else}
                    <span class="pill st-{r[3]}">{LABELS[r[3]]}</span>
                  {/if}
                  <span class="name">{r[2]}{#if r[6]}<span class="faint auto"> · automatic</span>{/if}</span>
                  {#if data.edit && !r[6]}
                    <input class="note-in" placeholder="note" value={r[4]} onchange={(e) => setStatus(r, r[3], e.currentTarget.value, r[5])} />
                    <input class="link-in" placeholder="link (docs/…)" value={r[5]} onchange={(e) => setStatus(r, r[3], r[4], e.currentTarget.value)} />
                  {:else}
                    {#if r[4]}<span class="note muted">{r[4]}</span>{/if}
                    {#if r[5] && linkHref(r[5])}<a class="lnk" href={linkHref(r[5])} target="_blank" rel="noopener">docs</a>{/if}
                  {/if}
                </li>
              {/each}
            </ul>
            {#if rows.length > cap}
              <div class="more">
                <button class="ghost" onclick={() => (shown[s.id] = cap + 200)}>Show {Math.min(200, rows.length - cap)} more</button>
                <button class="ghost" onclick={() => (shown[s.id] = rows.length)}>Show all {rows.length.toLocaleString()}</button>
              </div>
            {/if}
            {#if rows.length === 0}<p class="muted desc">No rows.</p>{/if}
          {/if}
        </section>
      {/each}
      {#if view.length === 0}<p class="muted">Nothing matches.</p>{/if}
    </div>

    <aside class="recent card" aria-label="Recent changes">
      <h2>Recent changes</h2>
      {#if data.recent.length === 0}
        <p class="muted hint">No status has changed in git yet.</p>
      {/if}
      <ul>
        {#each data.recent as c}
          <li>
            <span class="rname">{c.name}</span>
            <span class="rchange"><span class="dot st-{c.old}">{SHORT[c.old]}</span> → <span class="dot st-{c.new}">{SHORT[c.new]}</span></span>
            <span class="faint">{c.date} · {#if data.repo}<a href="{data.repo}/commit/{c.commit}" target="_blank" rel="noopener">{c.commit}</a>{:else}{c.commit}{/if}</span>
          </li>
        {/each}
      </ul>
      {#if data.commit}<p class="faint hint">Built from {data.commit}.</p>{/if}
    </aside>
  </div>
</main>
