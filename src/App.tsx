import { Fragment, useEffect, useId, useMemo, useState, type ReactNode } from 'react';
import { Activity, ArrowDownToLine, ArrowRight, Bookmark, Check, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, CircleAlert, Clipboard, Database, FileCheck2, Focus, GitCompareArrows, Layers, Pause, Play, RotateCcw, Search, ShieldCheck, SlidersHorizontal, Users, X } from 'lucide-react';
import type { Action, Dataset, Match } from './types';
import { clamp, comparePlayers, count, csvCell, download, Empty, Field, finite, fmt, GridHeatmap, IconButton, interval, Pitch, ProfileBars, SectionHead, SourceLink, Stat, xtFeature, type SimilarityMode } from './components';

type Tab = 'recruitment' | 'match' | 'tracking' | 'evidence';
const tabs = [{ id: 'recruitment', label: 'Recruitment', icon: Users }, { id: 'match', label: 'Match lab', icon: GitCompareArrows }, { id: 'tracking', label: 'Tracking', icon: Activity }, { id: 'evidence', label: 'Evidence', icon: FileCheck2 }] as const;
const watchKey = 'touchline.watchlist.v1';
const tabFromHash = (): Tab => tabs.find(t => `#${t.id}` === window.location.hash)?.id ?? 'recruitment';

function readWatchlist(): number[] {
  try { const value: unknown = JSON.parse(localStorage.getItem(watchKey) ?? '[]'); return Array.isArray(value) ? [...new Set(value.filter(finite))] : []; } catch { return []; }
}
function validDataset(value: unknown): value is Dataset {
  if (!value || typeof value !== 'object') return false;
  const d = value as Dataset;
  return typeof d.version === 'string'
    && ['features', 'players', 'matches', 'tracking'].every(k => Array.isArray(d[k as keyof Dataset]))
    && !!d.evidence && ['providers', 'checks', 'evaluation', 'trainMatches', 'testMatches', 'xtGrid', 'xtSupport', 'limitations', 'methodology'].every(k => Array.isArray(d.evidence[k as keyof Dataset['evidence']]))
    && d.features.every(f => f && [f.key, f.group, f.label, f.unit, f.description].every(s => typeof s === 'string'))
    && d.players.every(p => p && finite(p.id) && [p.name, p.team, p.role, p.position].every(s => typeof s === 'string') && !!p.metrics && !!p.z && Array.isArray(p.style) && Array.isArray(p.matches))
    && d.matches.every(m => m && Array.isArray(m.actions) && Array.isArray(m.teamStats))
    && d.tracking.every(t => t && Array.isArray(t.frames) && Array.isArray(t.pitch) && t.pitch.length === 2 && t.pitch.every(n => finite(n) && n > 0) && Array.isArray(t.assumptions) && !!t.quality && t.frames.every(f => f && finite(f.t) && Array.isArray(f.players) && Array.isArray(f.control) && f.control.every(Array.isArray)));
}

export default function App() {
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [watchlist, setWatchlist] = useState(readWatchlist);
  const [storageError, setStorageError] = useState(false);
  const [logoLoaded, setLogoLoaded] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(new URL('data/workspace.json', document.baseURI), { signal: controller.signal, cache: 'no-cache' }).then(async response => {
      if (!response.ok) throw new Error(`Workspace unavailable (HTTP ${response.status}).`);
      let value: unknown;
      try { value = await response.json(); } catch { throw new Error('The workspace URL did not return valid JSON. Publish data/workspace.json with the aggregate pipeline build.'); }
      if (!validDataset(value)) throw new Error('Workspace does not match the Dataset contract. Rebuild the public aggregate dataset.');
      setData(value);
    }).catch(e => { if (e.name !== 'AbortError') setError(e instanceof Error ? e.message : 'Unable to read workspace.'); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => { try { localStorage.setItem(watchKey, JSON.stringify(watchlist)); setStorageError(false); } catch { setStorageError(true); } }, [watchlist]);
  useEffect(() => {
    const sync = (event: StorageEvent) => { if (event.key === watchKey) setWatchlist(readWatchlist()); };
    window.addEventListener('storage', sync); return () => window.removeEventListener('storage', sync);
  }, []);
  useEffect(() => {
    const navigate = () => setTab(tabFromHash());
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);
  const toggleWatch = (id: number) => setWatchlist(list => list.includes(id) ? list.filter(n => n !== id) : [...list, id]);
  const setView = (view: Tab) => { setTab(view); window.history.replaceState(null, '', `#${view}`); };
  const goEvidence = () => { setView('evidence'); window.scrollTo({ top: 0, behavior: 'instant' }); };

  return <div className="app-shell">
    <header className="app-header"><div className="brand"><span className="brand-mark" aria-hidden="true"><span /><span /><span /></span><strong>Touchline<span className="brand-period">.</span></strong><span className="brand-descriptor">Decision lab</span></div><div className="header-meta"><span className="status-dot" />Public-data research<span className="header-divider" /><span className="mono">{data ? `BUILD ${data.version}` : 'WORKSPACE'}</span></div></header>
    <div className="context-strip"><span><Database size={13} />{data?.evidence.competition || 'Historical competition'}<span className="context-separator">/</span>Historical scope only</span><button onClick={goEvidence}>Independent research · No current LA Galaxy affiliation<ArrowRight size={13} /></button></div>
    <nav className="tabs" aria-label="Workspace views">{tabs.map(({ id, label, icon: Icon }) => <button key={id} aria-label={label} onClick={() => setView(id)} className={tab === id ? 'active' : ''} aria-current={tab === id ? 'page' : undefined}><Icon size={17} /><span>{label}</span>{id === 'recruitment' && watchlist.length > 0 && <span className="nav-count">{watchlist.length}</span>}</button>)}<span className="nav-end">SOCCER OPERATIONS / RESEARCH</span></nav>
    <main id="main-content">
      {loading ? <div className="loading-state" role="status"><span className="loading-line" /><Database size={28} /><h1>Loading research workspace</h1><p>Reading the versioned public-data build.</p></div> : error ? <div className="load-error"><Empty title="Workspace not available" error>{error} No sample statistics have been substituted.</Empty><button className="button primary" onClick={() => setAttempt(n => n + 1)}><RotateCcw size={15} />Retry workspace</button></div> : data ? <>
        <div hidden={tab !== 'recruitment'}><Recruitment data={data} watchlist={watchlist} toggleWatch={toggleWatch} evidence={goEvidence} storageError={storageError} /></div>
        <div hidden={tab !== 'match'}><MatchLab data={data} /></div>
        <div hidden={tab !== 'tracking'}><TrackingLab data={data} active={tab === 'tracking'} /></div>
        <div hidden={tab !== 'evidence'}><EvidenceView data={data} /></div>
      </> : null}
    </main>
    <footer className="app-footer"><div className="source-credit"><span className="source-logo">{!logoLoaded && <strong>StatsBomb</strong>}{!logoFailed && <img src={new URL('data/statsbomb-logo.png', document.baseURI).href} alt={logoLoaded ? 'StatsBomb' : ''} style={{ display: logoLoaded ? 'block' : 'none' }} onLoad={() => setLogoLoaded(true)} onError={() => setLogoFailed(true)} />}</span><span>Public data attribution<SourceLink href="https://github.com/statsbomb/open-data">StatsBomb Open Data</SourceLink></span></div><p>Aggregated events only. Tracking: separate SkillCorner sample.<br />Research demonstration, not a player recommendation or calibrated forecast.</p><button className="footer-link" onClick={goEvidence}><ShieldCheck size={14} />Sources & limitations<ArrowRight size={14} /></button></footer>
  </div>;
}

function PageHead({ index, title, subtitle, children }: { index: string; title: string; subtitle: string; children?: ReactNode }) {
  return <div className="page-head"><div><div className="eyebrow page-kicker">{index} / TOUCHLINE WORKSPACE</div><h1>{title}</h1><p>{subtitle}</p></div><div className="page-actions">{children}</div></div>;
}

function Recruitment({ data, watchlist, toggleWatch, evidence, storageError }: { data: Dataset; watchlist: number[]; toggleWatch: (id: number) => void; evidence: () => void; storageError: boolean }) {
  const [referenceId, setReferenceId] = useState(data.players[0]?.id ?? 0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mode, setMode] = useState<SimilarityMode>('metric');
  const [query, setQuery] = useState('');
  const [team, setTeam] = useState('all');
  const [sameRole, setSameRole] = useState(true);
  const defaultMinutes = Math.min(270, Math.max(0, ...data.players.map(p => finite(p.minutes) ? p.minutes : 0)));
  const [minMinutes, setMinMinutes] = useState(defaultMinutes);
  const [onlySaved, setOnlySaved] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const groups = useMemo(() => [...new Set(data.features.map(f => f.group))], [data.features]);
  const teams = useMemo(() => [...new Set(data.players.map(p => p.team))].sort(), [data.players]);
  const reference = data.players.find(p => p.id === referenceId) ?? data.players[0];
  const xt = xtFeature(data.features);
  const maxMinutes = Math.max(...data.players.map(p => finite(p.minutes) ? p.minutes : 0), 0);
  const rankings = useMemo(() => reference ? data.players.filter(p => p.id !== reference.id && (!sameRole || p.role === reference.role) && p.minutes >= minMinutes && (team === 'all' || p.team === team) && (!onlySaved || watchlist.includes(p.id)) && `${p.name} ${p.team} ${p.role}`.toLowerCase().includes(query.toLowerCase().trim())).map(player => ({ player, similarity: comparePlayers(reference, player, data.features, weights, mode) })).sort((a, b) => (a.similarity?.distance ?? Infinity) - (b.similarity?.distance ?? Infinity) || b.player.minutes - a.player.minutes || a.player.id - b.player.id) : [], [data, reference, sameRole, minMinutes, team, onlySaved, watchlist, query, weights, mode]);
  const selected = rankings.find(r => r.player.id === selectedId) ?? rankings[0];
  const activeGroups = groups.filter(g => (weights[g] ?? 1) > 0).length;
  const weightSummary = groups.map(g => `${g}: ${fmt(weights[g] ?? 1, 1)}`).join('; ');
  const memo = selected && reference ? [
    `SCOUT RESEARCH NOTE | ${data.evidence.competition} | build ${data.version}`,
    `Comparison: ${selected.player.name} (${selected.player.team}, ${selected.player.role}) against ${reference.name} (${reference.team}, ${reference.role}).`,
    `Method: ${mode === 'metric' ? 'metric-profile weighted cosine on train-role-shrunken z metrics; group weights divided across features within each group' : 'spatial-style cosine on 60 published bins'}. ${selected.similarity ? `Style similarity ${(selected.similarity.cosine * 100).toFixed(1)}% (cosine x 100); cosine distance ${selected.similarity.distance.toFixed(4)}.` : 'Similarity unavailable: missing or zero-norm vectors.'} This is style similarity, NOT player quality or a transfer recommendation.`,
    mode === 'metric' ? `Group weights: ${weightSummary}.` : 'Group weights do not apply to spatial-style mode.',
    `Exposure: ${count(selected.player.minutes)} stoppage-inclusive minutes, ${count(selected.player.appearances)} appearances; reference ${count(reference.minutes)} stoppage-inclusive minutes, ${count(reference.appearances)} appearances. Minute denominators supplied by socceraction.`,
    `Unshrunk xT per 90: candidate ${fmt(xt ? selected.player.metrics[xt.key] : undefined)}; reference ${fmt(xt ? reference.metrics[xt.key] : undefined)}. Candidate 90% match-bootstrap interval: ${interval(selected.player)}; sample-limited, not a calibrated future range.`,
    `Review: inspect the largest profile differences and verify context with scouting. Event lanes are team aggregates with support >=5, not individual actions. Tracking is a separate SkillCorner match and cannot validate this player comparison.`,
    `Evidence: ${window.location.origin}${window.location.pathname}#evidence; candidate match IDs ${selected.player.matches.join(', ') || 'not published'}; reference match IDs ${reference.matches.join(', ') || 'not published'}.`,
    ...data.evidence.providers.map(p => `Source: ${p.name} | ${p.url} | ${p.license}`),
    'Historical competition only. Independent research; no current LA Galaxy affiliation.',
  ].join('\n\n') : '';
  useEffect(() => { setCopied(false); setCopyError(false); }, [memo]);
  useEffect(() => { if (!copied) return; const timer = setTimeout(() => setCopied(false), 2200); return () => clearTimeout(timer); }, [copied]);

  const exportCSV = () => {
    const rows: unknown[][] = [['rank', 'player_id', 'player', 'team', 'role', 'stoppage_inclusive_minutes', 'appearances', 'reference', 'mode', 'style_similarity_cosine_x100_NOT_quality', 'cosine_distance', 'unshrunk_xt_per90', 'xt_90pct_match_bootstrap_low', 'xt_90pct_match_bootstrap_high', 'sample_limited', 'watchlist', 'group_weights', 'competition', 'build']];
    rankings.forEach(({ player: p, similarity: s }, i) => rows.push([i + 1, p.id, p.name, p.team, p.role, p.minutes, p.appearances, reference?.name, mode === 'metric' ? 'metric-profile' : 'spatial-style', s ? s.cosine * 100 : '', s?.distance ?? '', xt ? p.metrics[xt.key] : '', p.xtInterval?.[0] ?? '', p.xtInterval?.[1] ?? '', true, watchlist.includes(p.id), mode === 'metric' ? weightSummary : 'not applied', data.evidence.competition, data.version]));
    download('touchline-style-comparison.csv', rows.map(row => row.map(csvCell).join(',')).join('\r\n'), 'text/csv;charset=utf-8');
  };
  const reset = () => { setQuery(''); setTeam('all'); setSameRole(true); setMinMinutes(defaultMinutes); setOnlySaved(false); setWeights({}); setMode('metric'); setExpanded(null); };
  if (!reference) return <><PageHead index="01" title="Recruitment" subtitle="Role-aware profile comparison" /><Empty title="No player profiles published">Publish player aggregates in the workspace to begin.</Empty></>;

  return <>
    <PageHead index="01" title="Player recruitment" subtitle="Historical role profiles · style similarity, not player quality"><button className={`button ${onlySaved ? 'primary' : ''}`} onClick={() => setOnlySaved(v => !v)} aria-pressed={onlySaved}><Bookmark size={15} />Watchlist <span className="button-count">{data.players.filter(p => watchlist.includes(p.id)).length}</span></button><button className="button" disabled={!rankings.length} onClick={exportCSV}><ArrowDownToLine size={15} />Export CSV</button></PageHead>
    {storageError && <div className="notice warning" role="status"><CircleAlert size={15} />Watchlist is kept for this session only. Browser storage is unavailable.</div>}
    <div className="recruitment-layout">
      <aside className="filter-rail" aria-label="Recruitment filters"><SectionHead label={<><SlidersHorizontal size={15} />Search parameters</>} aside={<IconButton icon={RotateCcw} label="Reset recruitment filters and weights" onClick={reset} />} />
        <Field label="Reference player"><select value={reference.id} onChange={e => { setReferenceId(Number(e.target.value)); setSelectedId(null); setExpanded(null); }}>{data.players.map(p => <option key={p.id} value={p.id}>{p.name} · {p.team}</option>)}</select></Field>
        <div className="reference-summary"><span className="eyebrow">REFERENCE / {reference.role}</span><strong>{reference.name}</strong><span>{reference.team} · {reference.position}</span><div><span>{count(reference.minutes)} <small>min*</small></span><span>{count(reference.appearances)} <small>apps</small></span></div></div>
        <Field label="Comparison model"><select value={mode} onChange={e => setMode(e.target.value as SimilarityMode)}><option value="metric">Metric-profile</option><option value="spatial">Spatial-style · 60 bins</option></select></Field>
        <label className="check-label"><input type="checkbox" checked={sameRole} onChange={e => setSameRole(e.target.checked)} />Same role as reference<span className="tiny-tag">{reference.role}</span></label>
        {!sameRole && <p className="micro warning-text">Cross-role z-scores use different role baselines. Interpret with care.</p>}
        <Field label="Team"><select value={team} onChange={e => setTeam(e.target.value)}><option value="all">All teams</option>{teams.map(t => <option key={t}>{t}</option>)}</select></Field>
        <Field label="Minimum minutes"><div className="range-heading"><span>Exposure threshold</span><input aria-label="Minimum minutes, numeric" type="number" min={0} max={maxMinutes} step={1} value={minMinutes} onChange={e => setMinMinutes(clamp(Number(e.target.value) || 0, 0, maxMinutes))} /></div><input aria-label="Minimum minutes, slider" type="range" min={0} max={Math.ceil(maxMinutes)} step={1} value={minMinutes} onChange={e => setMinMinutes(Number(e.target.value))} /></Field>
        <div className="rail-divider" /><SectionHead label="Feature groups" aside={<span className="micro">{activeGroups}/{groups.length}</span>} />
        <p className="micro">{mode === 'metric' ? 'Weights are shared equally across features in each group.' : 'Spatial-style uses 60 bins. Metric group weights are inactive.'}</p>
        <fieldset className="weights" disabled={mode === 'spatial'}><legend className="sr-only">Metric-profile group weights</legend>{groups.map(group => <Field label={group.replaceAll('_', ' ')} key={group}><div className="weight-control"><input aria-label={`${group} weight`} type="range" min={0} max={3} step={0.1} value={weights[group] ?? 1} onChange={e => setWeights(w => ({ ...w, [group]: Number(e.target.value) }))} /><output>{fmt(weights[group] ?? 1, 1)}<small>x</small></output></div></Field>)}</fieldset>
        <div className="rail-note"><CircleAlert size={15} /><p>*Stoppage-inclusive minutes from socceraction. 90% match-bootstrap intervals are sample-limited. Displayed rates are unshrunk; z-scores use train-role shrinkage.</p></div>
      </aside>
      <div className="recruitment-main"><div className="result-toolbar"><div><span className="eyebrow">COMPARISON POOL</span><h2>{count(rankings.length)} profiles <span>/ {sameRole ? reference.role : 'all roles'}</span></h2></div><label className="search-box"><Search size={15} /><input aria-label="Search players, teams or roles" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search player or team" />{query && <IconButton icon={X} label="Clear player search" onClick={() => setQuery('')} />}</label></div>
        <div className="model-strip"><span className="model-badge"><Focus size={13} />{mode === 'metric' ? 'Metric-profile' : 'Spatial-style'}</span><span>Style similarity, <strong>not quality</strong> · cosine × 100{mode === 'metric' ? ' · group-normalized weights' : ' · 60 spatial bins'}</span><button onClick={evidence}>Method & evidence<ArrowRight size={12} /></button></div>
        {!rankings.length ? <Empty title="No profiles meet these filters">Adjust the exposure threshold, team, search or watchlist filter.</Empty> : <div className="table-scroll player-results" tabIndex={0} aria-label="Player similarity results, horizontally scrollable"><table className="player-table"><thead><tr><th scope="col">#</th><th scope="col">Player / team</th><th scope="col" className="numeric">Style similarity ↓</th><th scope="col" className="numeric">Min* / apps</th><th scope="col" className="numeric">xT / 90</th><th scope="col">90% interval</th><th scope="col"><span className="sr-only">Watchlist and compare</span></th></tr></thead><tbody>{rankings.map(({ player: p, similarity: s }, i) => <Fragment key={p.id}><tr className={selected?.player.id === p.id ? 'selected-row' : ''}>
          <td className="rank mono">{String(i + 1).padStart(2, '0')}</td><td><button className="player-name" onClick={() => setSelectedId(p.id)} aria-pressed={selected?.player.id === p.id}>{p.name}</button><span className="player-meta">{p.team}<span>·</span>{p.role}</span></td>
          <td className="numeric"><div className="score"><strong>{s ? `${fmt(s.cosine * 100, 1)}%` : 'N/A'}</strong><div className="score-track">{s && <span style={{ width: `${Math.max(0, s.cosine) * 100}%` }} />}</div><small>{s ? `d ${fmt(s.distance, 3)}` : 'Missing / zero vector'}</small></div></td>
          <td className="numeric mono">{count(p.minutes)}<small className="cell-sub">{count(p.appearances)} apps</small></td><td className="numeric mono">{fmt(xt ? p.metrics[xt.key] : undefined)}</td><td className="interval-cell mono">{interval(p)}<small className="cell-sub">match-bootstrap · limited</small></td>
          <td><div className="row-actions"><IconButton icon={Bookmark} label={watchlist.includes(p.id) ? `Remove ${p.name} from watchlist` : `Save ${p.name} to watchlist`} aria-pressed={watchlist.includes(p.id)} className={watchlist.includes(p.id) ? 'saved' : ''} onClick={() => toggleWatch(p.id)} /><IconButton icon={expanded === p.id ? ChevronUp : ChevronDown} label={`Compare ${p.name} with reference`} aria-expanded={expanded === p.id} onClick={() => { setSelectedId(p.id); setExpanded(expanded === p.id ? null : p.id); }} /></div></td>
        </tr>{expanded === p.id && <tr className="expanded-row"><td colSpan={7}><div className="inline-comparison"><h3>{p.name} <span>vs {reference.name}</span></h3><ProfileBars reference={reference} player={p} features={data.features} /></div></td></tr>}</Fragment>)}</tbody></table></div>}
        <div className="table-note"><span>Ordered by cosine distance · reference excluded</span><span>Similarity can be negative · zero vectors are unranked</span></div>
        {selected && <div className="comparison-workspace"><section className="comparison-profile"><SectionHead label="Profile comparison" aside={<span className="tiny-tag">{selected.player.role}</span>} /><div className="comparison-title"><h3>{selected.player.name}</h3><span>against {reference.name}</span></div><ProfileBars player={selected.player} reference={reference} features={data.features} /><p className="micro">Train-role-shrunken z-scores, clipped to ±3 for display only. Rankings use full values.</p><details className="rate-details"><summary><Activity size={13} />Unshrunk measured rates<ChevronDown size={13} /></summary><div className="table-scroll" tabIndex={0} aria-label="Unshrunk measured rate comparison"><table><thead><tr><th>Metric</th><th className="numeric">Candidate</th><th className="numeric">Reference</th></tr></thead><tbody>{data.features.map(f => <tr key={f.key}><td title={f.description}>{f.label}<small className="cell-sub">{f.unit}</small></td><td className="numeric mono">{fmt(selected.player.metrics[f.key])}</td><td className="numeric mono">{fmt(reference.metrics[f.key])}</td></tr>)}</tbody></table></div></details></section><section className="scout-memo"><SectionHead label="Scout research note" aside={<div className="row-actions"><IconButton icon={ArrowDownToLine} label="Download evidence-linked scout note" onClick={() => download('touchline-scout-note.txt', memo, 'text/plain;charset=utf-8')} /><IconButton icon={copied ? Check : Clipboard} label={copied ? 'Scout note copied' : 'Copy evidence-linked scout note'} onClick={async () => { try { await navigator.clipboard.writeText(memo); setCopied(true); setCopyError(false); } catch { setCopyError(true); } }} /></div>} /><div className="memo-status"><span className="status-dot" />DRAFT / CONTEXT REQUIRED</div><label className="sr-only" htmlFor="scout-memo">Evidence-linked scout memo</label><textarea id="scout-memo" value={memo} readOnly spellCheck={false} /><div className="memo-bottom"><button onClick={evidence}>Inspect evidence<ArrowRight size={13} /></button><span role="status">{copyError ? 'Clipboard unavailable. Download the note.' : copied ? 'Copied to clipboard' : 'Evidence-linked · no recommendation'}</span></div></section></div>}
      </div>
    </div>
  </>;
}

type AggregateLane = Action & { count?: number };
function publishedLanes(match?: Match): AggregateLane[] {
  return (match?.actions ?? []).filter((a: AggregateLane) => a.playerId === 0 && a.player === 'Team aggregate' && Number.isInteger(a.count) && (a.count ?? 0) >= 5 && finite(a.xt) && finite(a.minute) && a.minute % 15 === 0 && ['pass', 'carry'].includes(a.type.toLowerCase()) && a.start?.length === 2 && a.end?.length === 2 && [...a.start, ...a.end].every(finite) && a.start[0] >= 0 && a.start[0] <= 105 && a.end[0] >= 0 && a.end[0] <= 105 && a.start[1] >= 0 && a.start[1] <= 68 && a.end[1] >= 0 && a.end[1] <= 68);
}

function MatchLab({ data }: { data: Dataset }) {
  const [matchId, setMatchId] = useState(data.matches[0]?.id ?? 0);
  const match = data.matches.find(m => m.id === matchId) ?? data.matches[0];
  const [teamChoice, setTeamChoice] = useState('');
  const team = match && [match.home, match.away].includes(teamChoice) ? teamChoice : match?.home ?? '';
  const [type, setType] = useState('all');
  const [bin, setBin] = useState('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(true);
  const arrowId = useId().replaceAll(':', '');
  const available = useMemo(() => publishedLanes(match), [match]);
  const bins = useMemo(() => [...new Set(available.filter(a => a.team === team).map(a => a.minute))].sort((a, b) => a - b), [available, team]);
  const lanes = useMemo(() => available.filter(a => a.team === team && (type === 'all' || a.type.toLowerCase() === type) && (bin === 'all' || a.minute === Number(bin))).sort((a, b) => b.xt - a.xt || a.id.localeCompare(b.id)), [available, team, type, bin]);
  const selected = lanes.find(a => a.id === selectedId) ?? lanes[0];
  const selectedIndex = selected ? lanes.indexOf(selected) : -1;
  const stats = match?.teamStats.find(s => s.team === team);
  const totalSupport = lanes.reduce((sum, a) => sum + (a.count ?? 0), 0);
  const move = (delta: number) => { const lane = lanes[clamp(selectedIndex + delta, 0, lanes.length - 1)]; if (lane) setSelectedId(lane.id); };
  const changeContext = () => { setSelectedId(null); setBin('all'); };
  if (!match) return <><PageHead index="02" title="Match lab" subtitle="Historical team-level event aggregates" /><Empty title="No match aggregates published">Individual event data are not redistributed.</Empty></>;
  const maxLaneXt = stats ? Math.max(Math.abs(stats.left), Math.abs(stats.center), Math.abs(stats.right), 1e-10) : 1;
  return <>
    <PageHead index="02" title="Team attacking structure" subtitle="Historical team patterns · supported aggregate lanes"><span className="scope-label"><Layers size={14} />TEAM AGGREGATES</span></PageHead>
    <div className="analysis-toolbar"><Field label="Historical match"><select value={match.id} onChange={e => { setMatchId(Number(e.target.value)); setTeamChoice(''); changeContext(); }}>{data.matches.map(m => <option key={m.id} value={m.id}>{m.home} {m.score} {m.away} · {m.date}</option>)}</select></Field><Field label="Team"><select value={team} onChange={e => { setTeamChoice(e.target.value); changeContext(); }}><option>{match.home}</option><option>{match.away}</option></select></Field><Field label="Lane type"><select value={type} onChange={e => { setType(e.target.value); setSelectedId(null); }}><option value="all">Pass + carry</option><option value="pass">Pass</option><option value="carry">Carry</option></select></Field><Field label="15-minute bin"><select value={bin} onChange={e => { setBin(e.target.value); setSelectedId(null); }}><option value="all">All published bins</option>{bins.map(b => <option value={b} key={b}>{b}'–{b + 15}'</option>)}</select></Field></div>
    <div className="notice"><ShieldCheck size={16} /><span><strong>Aggregated lanes · at least 5 actions per lane.</strong> Cell-center coordinates; 15-minute bin starts. No individual pass replay. xT is summed across each group.</span></div>
    <div className="analysis-layout"><section className="pitch-section"><SectionHead label={<>{team}<span className="subtle"> / attacking lanes</span></>} aside={<span className="micro">{match.stage} · {match.date}</span>} /><div className="pitch-topline"><span><i className="dot gold" />Selected lane <i className="dot pale" />Other published lanes</span><span>Attack direction<ArrowRight size={14} /></span></div>
      <div className="pitch-surface"><Pitch title={`${team} aggregated pass and carry lanes, attacking left to right, 105 by 68 metres`}><defs><marker id={arrowId} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#edbd60" /></marker></defs><g>{(showAll ? lanes.filter(a => a.id !== selected?.id) : []).map(a => <line key={a.id} x1={a.start[0]} y1={a.start[1]} x2={a.end[0]} y2={a.end[1]} stroke="#c1d7cd" opacity={0.23} strokeWidth={Math.min(1.4, 0.3 + (a.count ?? 0) / 150)} />)}{selected && <g className="selected-lane"><line x1={selected.start[0]} y1={selected.start[1]} x2={selected.end[0]} y2={selected.end[1]} stroke="#edbd60" strokeWidth={0.75} strokeDasharray={selected.type.toLowerCase() === 'carry' ? '1.5 1' : undefined} markerEnd={`url(#${arrowId})`} /><circle cx={selected.start[0]} cy={selected.start[1]} r={1.1} fill="#edbd60" stroke="#183d32" strokeWidth={0.35} /><circle cx={selected.end[0]} cy={selected.end[1]} r={0.65} fill="#edbd60" /></g>}</g></Pitch>{!lanes.length && <div className="pitch-empty">No supported lanes in this selection</div>}</div>
      <div className="pitch-bottomline"><span>105 × 68 m · already normalized left to right</span><label className="check-label"><input type="checkbox" checked={showAll} onChange={e => setShowAll(e.target.checked)} />All filtered lanes</label></div>
      <div className="lane-transport"><div className="row-actions"><IconButton icon={ChevronLeft} label="Previous higher-xT aggregate lane" disabled={selectedIndex <= 0} onClick={() => move(-1)} /><IconButton icon={ChevronRight} label="Next lower-xT aggregate lane" disabled={selectedIndex < 0 || selectedIndex >= lanes.length - 1} onClick={() => move(1)} /></div><span>{selected ? `Lane ${selectedIndex + 1} / ${lanes.length}` : 'No lane selected'}<small>ordered by summed xT, not chronology</small></span>{selected && <div className="lane-readout"><strong>{selected.type} · {selected.minute}'–{selected.minute + 15}'</strong><span>{count(selected.count)} grouped actions · Σ xT {fmt(selected.xt, 3)}</span></div>}</div>
    </section><aside className="analysis-aside"><SectionHead label="Team output" aside={<span className="tiny-tag">FULL MATCH</span>} /><div className="stat-grid"><Stat label="Expected goals" value={fmt(stats?.xg)} note="provider shot xG" /><Stat label="Shots" value={count(stats?.shots)} /><Stat label="Move xT" value={fmt(stats?.xt, 3)} note="successful-move value" /><Stat label="Completion" value={stats && stats.passes > 0 ? `${fmt(stats.completions / stats.passes * 100, 1)}%` : '\u2014'} note={stats ? `${count(stats.completions)} / ${count(stats.passes)} passes` : 'Unavailable'} /></div><SectionHead label="Move xT by lane" /><p className="micro">Full-match net successful-move xT. Not just the selected bin.</p><div className="lane-distribution">{stats && [{ label: 'Left', value: stats.left }, { label: 'Center', value: stats.center }, { label: 'Right', value: stats.right }].map(l => <div key={l.label}><span>{l.label}</span><div><i style={{ width: `${Math.abs(l.value) / maxLaneXt * 100}%`, background: l.value < 0 ? 'var(--coral)' : undefined }} /></div><strong className="mono">{fmt(l.value, 3)}</strong></div>)}</div><div className="aside-summary"><span className="eyebrow">CURRENT FILTER</span><strong>{count(lanes.length)} supported lanes</strong><span>{count(totalSupport)} grouped actions</span><p>Suppressed low-support groups are absent. Lane coverage is not a full event count.</p></div></aside></div>
    <section className="lane-ledger"><SectionHead label="Aggregate lane ledger" aside={<span className="micro">Team aggregate · no player-level identity</span>} />{!lanes.length ? <Empty title="No aggregate lanes meet these filters">Try another team, type or 15-minute bin. Unsupported groups are never shown.</Empty> : <div className="table-scroll" tabIndex={0} aria-label="Aggregate lane ledger, horizontally scrollable"><table><thead><tr><th>Lane</th><th>Type</th><th>Bin start</th><th>Cell center → cell center (m)</th><th className="numeric">Support</th><th className="numeric">Σ xT ↓</th><th>Identity</th></tr></thead><tbody>{lanes.map((a, i) => <tr key={a.id} className={selected?.id === a.id ? 'selected-row' : ''}><td><button className="text-button" aria-pressed={selected?.id === a.id} onClick={() => setSelectedId(a.id)}>Lane {String(i + 1).padStart(2, '0')}<Focus size={13} /></button></td><td className="capitalize">{a.type}</td><td className="mono">{a.minute}'</td><td className="mono">{fmt(a.start[0], 1)}, {fmt(a.start[1], 1)} → {fmt(a.end[0], 1)}, {fmt(a.end[1], 1)}</td><td className="numeric mono">{count(a.count)}</td><td className="numeric mono">{fmt(a.xt, 3)}</td><td>Team aggregate</td></tr>)}</tbody></table></div>}</section>
  </>;
}

function TrackingLab({ data, active }: { data: Dataset; active: boolean }) {
  const [datasetIndex, setDatasetIndex] = useState(0);
  const tracking = data.tracking[datasetIndex];
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [control, setControl] = useState(true);
  const [velocity, setVelocity] = useState(false);
  const [numbers, setNumbers] = useState(true);
  const frame = tracking?.frames[clamp(frameIndex, 0, Math.max(0, tracking.frames.length - 1))];
  useEffect(() => { if (!active) setPlaying(false); }, [active]);
  useEffect(() => {
    if (!playing || !active || !tracking || tracking.frames.length < 2) return;
    const start = performance.now();
    const startIndex = frameIndex;
    const startTime = tracking.frames[startIndex].t;
    let raf = 0;
    const tick = (now: number) => {
      const elapsed = startTime + (now - start) / 1000;
      let low = startIndex, high = tracking.frames.length - 1;
      while (low < high) { const mid = Math.ceil((low + high) / 2); if (tracking.frames[mid].t <= elapsed) low = mid; else high = mid - 1; }
      setFrameIndex(low);
      if (elapsed >= tracking.frames[tracking.frames.length - 1].t) setPlaying(false); else raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
    // Playback is anchored once; changing frameIndex inside the animation must not restart its clock.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, active, tracking]);
  const [length, width] = tracking?.pitch ?? [104, 68];
  const position = (x: number, y: number): [number, number] => [x + length / 2, width / 2 - y];
  const inBounds = (x: number, y: number) => finite(x) && finite(y) && Math.abs(x) <= length / 2 && Math.abs(y) <= width / 2;
  const players = frame?.players.filter(p => inBounds(p.x, p.y)) ?? [];
  const homeControl = frame?.control.flat().filter(finite);
  const meanHome = homeControl?.length ? homeControl.reduce((sum, n) => sum + n, 0) / homeControl.length : null;
  const timestamp = (t: number) => `${Math.floor(t / 60).toString().padStart(2, '0')}:${(t % 60).toFixed(2).padStart(5, '0')}`;
  const step = (delta: number) => { setPlaying(false); setFrameIndex(i => clamp(i + delta, 0, Math.max(0, (tracking?.frames.length ?? 0) - 1))); };
  if (!tracking) return <><PageHead index="03" title="Tracking" subtitle="Separate public SkillCorner tracking sample" /><Empty title="No public tracking frames published">Metrica validation remains local; no Metrica raw positions are redistributed.</Empty></>;
  return <>
    <PageHead index="03" title="Tracking & space control" subtitle="SkillCorner positions · precomputed home-control surface"><span className="scope-label"><Activity size={14} />SEPARATE MATCH</span></PageHead>
    <div className="analysis-toolbar tracking-toolbar"><Field label="Provider / dataset"><select value={datasetIndex} onChange={e => { setDatasetIndex(Number(e.target.value)); setFrameIndex(0); setPlaying(false); }}>{data.tracking.map((t, i) => <option value={i} key={`${t.source}-${t.dataset}`}>{t.source} · {t.label}</option>)}</select></Field><div className="toggle-group">{[{ label: 'Home control', checked: control, set: setControl, icon: Layers }, { label: 'Velocity', checked: velocity, set: setVelocity, icon: ArrowRight }, { label: 'Numbers', checked: numbers, set: setNumbers, icon: Users }].map(({ label, checked, set, icon: Icon }) => <label className="toggle-label" key={label}><input type="checkbox" checked={checked} onChange={e => set(e.target.checked)} /><Icon size={14} /><span>{label}</span></label>)}</div></div>
    <div className="notice"><CircleAlert size={16} /><span><strong>{tracking.home} / {tracking.away} · {tracking.label}.</strong> Separate SkillCorner match, not the StatsBomb competition. No cross-provider match or player join.</span></div>
    <div className="analysis-layout"><section className="pitch-section"><SectionHead label="Pitch-control laboratory" aside={<span className="tiny-tag">{tracking.source}</span>} /><div className="pitch-topline"><span><i className="dot coral" />{tracking.home}<i className="dot light-gold" />{tracking.away}<i className="dot white" />Ball</span><span className="mono">{frame ? timestamp(frame.t) : '\u2014'}</span></div>
      <div className="pitch-surface tracking-surface"><Pitch title={`${tracking.home} and ${tracking.away}, actual centered-metre tracking positions on a ${length} by ${width} metre pitch`} length={length} width={width}>
        {control && frame && frame.control.length > 0 && <g className="control-grid">{frame.control.flatMap((row, y) => row.map((v, x) => {
          if (!finite(v)) return null;
          const probability = clamp(v, 0, 1), cellW = length / Math.max(row.length, 1), cellH = width / frame.control.length;
          return <rect key={`${x}-${y}`} x={x * cellW} y={width - (y + 1) * cellH} width={cellW + 0.02} height={cellH + 0.02} fill={probability >= 0.5 ? '#d67c70' : '#e9c76d'} opacity={0.08 + Math.abs(probability - 0.5) * 0.68}><title>{`Home control ${fmt(v * 100, 1)}%`}</title></rect>;
        }))}</g>}
        <g>{players.map(p => { const [x, y] = position(p.x, p.y); const isHome = p.team === tracking.home || p.team.toLowerCase() === 'home'; return <g key={p.id}><title>{`${p.team} #${p.number}; x ${fmt(p.x, 2)}, y ${fmt(p.y, 2)} m; velocity ${fmt(p.vx)}, ${fmt(p.vy)} m/s`}</title>{velocity && finite(p.vx) && finite(p.vy) && <line x1={x} y1={y} x2={clamp(x + p.vx, 0, length)} y2={clamp(y - p.vy, 0, width)} stroke={isHome ? '#f4a196' : '#f7dc97'} strokeWidth={0.5} />}<circle cx={x} cy={y} r={1.18} fill={isHome ? '#df8475' : '#ecd084'} stroke="#102f28" strokeWidth={0.3} />{numbers && <text x={x} y={y + 0.42} textAnchor="middle" fill="#162d25" fontSize={1.25} fontWeight={700}>{p.number}</text>}</g>; })}</g>
        {frame?.ball && inBounds(frame.ball[0], frame.ball[1]) && <circle cx={position(...frame.ball)[0]} cy={position(...frame.ball)[1]} r={0.7} fill="#fff" stroke="#172f26" strokeWidth={0.28}><title>Current ball position</title></circle>}
      </Pitch>{!frame && <div className="pitch-empty">No frames available for this dataset</div>}</div>
      <div className="pitch-bottomline"><span>{length} × {width} m · centered coordinates · +y up</span><span>Velocity vectors = 1 second displacement</span></div>
      <div className="tracking-transport"><div className="row-actions"><IconButton icon={RotateCcw} label="Restart tracking clip" disabled={!frame} onClick={() => { setPlaying(false); setFrameIndex(0); }} /><IconButton icon={ChevronLeft} label="Previous tracking frame" disabled={!frame || frameIndex <= 0} onClick={() => step(-1)} /><IconButton icon={playing ? Pause : Play} label={playing ? 'Pause tracking playback' : 'Play tracking playback'} className="play-button" aria-pressed={playing} disabled={tracking.frames.length < 2} onClick={() => { if (!playing && frameIndex >= tracking.frames.length - 1) setFrameIndex(0); setPlaying(v => !v); }} /><IconButton icon={ChevronRight} label="Next tracking frame" disabled={!frame || frameIndex >= tracking.frames.length - 1} onClick={() => step(1)} /></div><label className="timeline"><span className="sr-only">Tracking timeline</span><input type="range" min={0} max={Math.max(0, tracking.frames.length - 1)} step={1} value={frameIndex} disabled={!frame} onChange={e => { setPlaying(false); setFrameIndex(Number(e.target.value)); }} /><span className="mono">{frame ? timestamp(frame.t) : '\u2014'} <small>/ {tracking.frames.length ? timestamp(tracking.frames[tracking.frames.length - 1].t) : '\u2014'}</small></span></label><span className="frame-count mono">{frame ? frameIndex + 1 : 0} / {count(tracking.frames.length)}</span></div>
    </section><aside className="analysis-aside"><SectionHead label="Frame diagnostics" aside={<span className="tiny-tag">MEASURED</span>} /><div className="stat-grid"><Stat label="Visible players" value={count(players.length)} note="in pitch bounds" /><Stat label="Home control" value={meanHome === null ? '\u2014' : `${fmt(meanHome * 100, 1)}%`} note="unweighted grid mean" /><Stat label="Sample rate" value={`${fmt(tracking.fps, 1)} Hz`} note="published frame rate" /><Stat label="Mass error" value={finite(frame?.massError) ? fmt(frame.massError, 6) : '\u2014'} note="precomputed diagnostic" /></div><div className="control-legend"><span>{tracking.away}</span><i /><span>{tracking.home}</span><small>Home control probability · 0 to 1</small></div><SectionHead label="Model assumptions" /><p className="model-name">{tracking.model}</p><ul className="plain-list">{tracking.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>{!frame?.ball && <p className="micro warning-text">Ball unavailable for this frame. No ball position is inferred.</p>}<p className="micro">Control cells are precomputed; no browser-side model or calibrated possession forecast.</p></aside></div>
    <section className="quality-ledger"><SectionHead label="Provider quality ledger" /><div className="quality-grid">{Object.entries(tracking.quality).map(([key, value]) => <div key={key}><span>{key.replaceAll('_', ' ')}</span><strong className={typeof value === 'number' ? 'mono' : ''}>{typeof value === 'number' ? fmt(value, Number.isInteger(value) ? 0 : 4) : value}</strong></div>)}</div>{!Object.keys(tracking.quality).length && <p className="micro">No dataset quality summary published.</p>}</section>
  </>;
}

function EvidenceView({ data }: { data: Dataset }) {
  const e = data.evidence;
  const [grid, setGrid] = useState<'value' | 'support'>('value');
  const overlap = e.trainMatches.filter(id => e.testMatches.includes(id));
  const passed = e.checks.filter(c => c.passed).length;
  const aggregateLanes = data.matches.reduce((sum, m) => sum + publishedLanes(m).length, 0);
  return <div id="evidence"><PageHead index="04" title="Evidence & validation" subtitle="Measured build evidence, model boundaries and public-data rights"><span className="scope-label"><Database size={14} />BUILD {data.version}</span></PageHead>
    <div className="evidence-stats"><Stat label="Source events processed" value={count(e.events)} note="raw events not redistributed" /><Stat label="Historical matches" value={count(e.matches)} note={e.competition} /><Stat label="Player profiles" value={count(e.players)} note={`${count(data.players.length)} in public workspace`} /><Stat label="Published lanes" value={count(aggregateLanes)} note="support ≥5 only" /><Stat label="Build checks passed" value={`${passed} / ${e.checks.length}`} note={`Built ${e.buildDate}`} /></div>
    <div className="evidence-columns"><section className="checks-section"><SectionHead label="Validation ledger" aside={<span className={`check-summary ${passed === e.checks.length && e.checks.length ? 'good' : 'warning-text'}`}>{e.checks.length ? `${passed} passed` : 'Not published'}</span>} />{e.checks.length ? <ul className="checks-list">{e.checks.map((c, i) => <li key={i}><span className={c.passed ? 'check-icon good' : 'check-icon bad'}>{c.passed ? <Check size={15} /> : <X size={15} />}</span><div><strong>{c.name}</strong><p>{c.detail}</p></div><span className={c.passed ? 'check-state good' : 'check-state bad'}>{c.passed ? 'PASS' : 'FAIL'}</span></li>)}</ul> : <Empty title="No validation checks published" />}</section><section className="grid-section"><SectionHead label="Expected-threat surface" aside={<div className="segmented" aria-label="Expected-threat grid view"><button aria-pressed={grid === 'value'} className={grid === 'value' ? 'active' : ''} onClick={() => setGrid('value')}>xT value</button><button aria-pressed={grid === 'support'} className={grid === 'support' ? 'active' : ''} onClick={() => setGrid('support')}>Support</button></div>} /><GridHeatmap values={grid === 'value' ? e.xtGrid : e.xtSupport} support={grid === 'value' ? e.xtSupport : undefined} title={grid === 'value' ? 'Fitted expected-threat grid, left to right' : 'Training support counts by grid cell'} /><div className="grid-caption"><span>{grid === 'value' ? 'Fitted xT / grid cell' : 'Training support / grid cell'}</span><span>Lower<i className="heat-scale" />Higher</span></div><p className="micro">Hover a cell for its measured value{grid === 'value' ? ' and support count' : ''}. Model assumptions and evaluation are listed below.</p></section></div>
    <section className="split-section"><SectionHead label="Match-level split isolation" aside={<span className={overlap.length ? 'bad' : 'good'}>{overlap.length ? `${overlap.length} overlapping IDs` : 'No overlapping IDs'}</span>} /><div className="split-grid"><div><h3>Training <span>{e.trainMatches.length} matches</span></h3><p className="id-list mono">{e.trainMatches.join(' · ') || 'No training IDs published'}</p></div><div><h3>Held-out test <span>{e.testMatches.length} matches</span></h3><p className="id-list mono">{e.testMatches.join(' · ') || 'No test IDs published'}</p></div></div>{(!e.trainMatches.length || !e.testMatches.length) && <p className="micro warning-text">An empty split does not establish out-of-sample validity.</p>}</section>
    <section className="evaluation-section"><SectionHead label="Model evaluation" aside={<span className="micro">Published results, not performance guarantees</span>} />{e.evaluation.length ? <div className="table-scroll" tabIndex={0} aria-label="Model evaluation, horizontally scrollable"><table><thead><tr><th>Measure</th><th>Value</th><th>Interpretation / protocol</th></tr></thead><tbody>{e.evaluation.map((v, i) => <tr key={i}><td><strong>{v.name}</strong></td><td className="mono">{typeof v.value === 'number' ? fmt(v.value, 4) : v.value}</td><td className="detail-cell">{v.detail}</td></tr>)}</tbody></table></div> : <Empty title="No evaluation results published" />}</section>
    <section className="providers-section"><SectionHead label="Sources & permissions" aside={<span className="micro">Provider datasets are never implied to share a match</span>} /><div className="provider-list">{e.providers.map((p, i) => <div className="provider-row" key={i}><div><SourceLink href={p.url}><strong>{p.name}</strong></SourceLink><span className="provider-status">{p.status}</span></div><p>{p.scope}</p><span>{p.license}</span></div>)}</div><div className="notice"><ShieldCheck size={16} /><span>StatsBomb match views expose supported aggregate lanes only, never raw events. Only the public SkillCorner tracking sample is displayed. Metrica validation summaries do not expose raw tracking positions.</span></div></section>
    <div className="evidence-columns methodology-columns"><section><SectionHead label="Methodology" /><ol className="method-list">{e.methodology.map((m, i) => <li key={i}><span className="mono">{String(i + 1).padStart(2, '0')}</span><p>{m}</p></li>)}</ol></section><section className="limitations"><SectionHead label="Boundaries of interpretation" aside={<CircleAlert size={16} />} /><ul className="plain-list">{e.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul><p>Style similarity is not player quality, transfer valuation or a calibrated forecast. 90% match-bootstrap intervals are sample-limited. Competition data are historical. Independent portfolio research; no current LA Galaxy affiliation.</p></section></div>
  </div>;
}
