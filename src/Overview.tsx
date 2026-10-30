import { useId, useMemo, useState } from 'react';
import { ArrowDownToLine, ArrowRight, Bookmark, Database, Flag, Shield, Users } from 'lucide-react';
import type { Dataset } from './types';
import { count, csvCell, download, finite, fmt, GridHeatmap } from './components';

interface OverviewProps {
  data: Dataset;
  onPlayer: (id: number) => void;
  onMatch: (id: number) => void;
  onNavigate: (view: 'recruitment' | 'match' | 'tracking' | 'evidence') => void;
  watchlist: number[];
  toggleWatch: (id: number) => void;
}

const metrics = [
  { key: 'xt90', label: 'xT / 90', digits: 3, note: 'Net successful-move xT, not total player quality.' },
  { key: 'progressive_pass90', label: 'Progressive passes / 90', digits: 2, note: 'Completed passes advancing at least 10 m into the attacking half.' },
  { key: 'npxg90', label: 'Non-penalty xG / 90', digits: 3, note: 'Non-penalty xG measures shot opportunity, not finishing skill.' },
] as const;

const roleDefinitions = [
  { name: 'Goalkeeper', color: '#64748b' },
  { name: 'Centre back', color: '#10b981' },
  { name: 'Full back', color: '#3b82f6' },
  { name: 'Midfielder', color: '#8b5cf6' },
  { name: 'Wide forward', color: '#e87965' },
  { name: 'Striker', color: '#d99b22' },
];

export default function Overview({ data, onPlayer, onMatch, onNavigate, watchlist, toggleWatch }: OverviewProps) {
  const id = useId();
  const [metricKey, setMetricKey] = useState<string>('xt90');
  const [minimumMinutes, setMinimumMinutes] = useState(270);
  const [exportStatus, setExportStatus] = useState('');
  const metric = metrics.find(item => item.key === metricKey) ?? metrics[0];
  const saved = useMemo(() => new Set(watchlist), [watchlist]);
  const evidence = data.evidence;
  const competition = evidence.competition || 'Historical public-data research';
  const trainCount = new Set(evidence.trainMatches.filter(finite)).size;
  const testCount = new Set(evidence.testMatches.filter(finite)).size;
  const grid = evidence.xtGrid;
  const gridRows = grid.length;
  const gridCols = grid.reduce((max, row) => Math.max(max, row.length), 0);
  const gridValues = grid.flat().filter(finite);
  const gridRange = gridValues.reduce(
    (range, value) => [Math.min(range[0], value), Math.max(range[1], value)],
    [Infinity, -Infinity],
  );
  const teamCount = useMemo(() => new Set([
    ...data.players.map(player => player.team),
    ...data.matches.flatMap(match => [match.home, match.away]),
  ].filter(team => team.trim())).size, [data.players, data.matches]);
  const roles = useMemo(() => {
    const totals = new Map<string, number>();
    data.players.forEach(player => {
      const role = player.role.trim() || 'Unspecified';
      totals.set(role, (totals.get(role) ?? 0) + 1);
    });
    return [
      ...roleDefinitions.map(role => ({ ...role, count: totals.get(role.name) ?? 0 })),
      ...[...totals].filter(([name]) => !roleDefinitions.some(role => role.name === name))
        .map(([name, total]) => ({ name, color: '#64748b', count: total })),
    ].filter(role => role.count > 0);
  }, [data.players]);
  const roleMaximum = Math.max(1, ...roles.map(role => role.count));
  const axisMaximum = Math.max(10, Math.ceil(roleMaximum / 10) * 10);
  const eligiblePlayers = useMemo(() => data.players.filter(player =>
    finite(player.minutes) && player.minutes > 0 && player.minutes >= minimumMinutes
    && finite(player.metrics[metric.key]),
  ).sort((a, b) => b.metrics[metric.key] - a.metrics[metric.key]
    || b.minutes - a.minutes || a.name.localeCompare(b.name) || a.id - b.id),
  [data.players, minimumMinutes, metric.key]);
  const visiblePlayers = eligiblePlayers.slice(0, 8);
  const sourceEvents = finite(evidence.events) && evidence.events >= 0 ? evidence.events : undefined;
  const kpis = [
    { label: 'Outfield profiles', value: data.players.length, note: 'Player-level comparisons', icon: Users },
    { label: 'Matches analyzed', value: data.matches.length, note: 'All tournament stages', icon: Flag },
    { label: 'National teams', value: teamCount, note: 'World Cup 2022 coverage', icon: Shield },
    { label: 'Source events', value: sourceEvents, note: 'StatsBomb Open Data', icon: Database },
  ];
  const spotlight = data.matches.at(-1);
  const homeStats = spotlight?.teamStats.find(team => team.team === spotlight.home);
  const awayStats = spotlight?.teamStats.find(team => team.team === spotlight.away);
  const xgMaximum = Math.max(1,
    finite(homeStats?.xg) && homeStats.xg >= 0 ? homeStats.xg : 0,
    finite(awayStats?.xg) && awayStats.xg >= 0 ? awayStats.xg : 0,
  );

  function exportOverview() {
    const rows: unknown[][] = [
      ['section', 'scope', 'label', 'player_id', 'team', 'role', 'minutes', 'metric', 'value', 'unit', 'saved'],
      ['build', competition, 'Dataset version', '', '', '', '', '', data.version, '', ''],
      ...kpis.map(kpi => ['coverage', competition, kpi.label, '', '', '', '', '', kpi.value ?? '', 'count', '']),
      ...roles.map(role => ['roles', competition, role.name, '', '', '', '', '', role.count, 'profiles', '']),
      ['model', competition, 'Training matches', '', '', '', '', '', trainCount, 'matches', ''],
      ['model', competition, 'Held-out matches', '', '', '', '', '', testCount, 'matches', ''],
      ['filter', competition, 'Minimum approximate minutes', '', '', '', '', '', minimumMinutes, 'minutes', ''],
      ['definition', competition, metric.note, '', '', '', '', metric.key, '', '', ''],
      ...eligiblePlayers.map(player => ['players', competition, player.name, player.id, player.team,
        player.role, player.minutes, metric.key, player.metrics[metric.key], '/90', saved.has(player.id)]),
      ...grid.flatMap((row, y) => row.flatMap((value, x) => finite(value)
        ? [['xt_surface', `Training matches: ${trainCount}`, `Column ${x + 1}; row ${y + 1}`, '', '', '', '', 'xT', value, 'cell value', '']]
        : [])),
    ];
    try {
      download('touchline-workspace-overview.csv', '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n'), 'text/csv;charset=utf-8');
      setExportStatus(`Exported overview and ${count(eligiblePlayers.length)} eligible profiles.`);
    } catch {
      setExportStatus('Export unavailable. Please try again.');
    }
  }

  return <div className="overview">
    <header className="overview-header">
      <div><h1>Workspace overview</h1><p>FIFA World Cup 2022 <span aria-hidden="true">/</span> Historical dataset</p></div>
      <div className="ov-header-actions">
        <button type="button" className="ov-export" onClick={exportOverview}><ArrowDownToLine size={16} aria-hidden="true" />Export report</button>
        <span className="ov-export-status" role="status">{exportStatus}</span>
      </div>
    </header>

    <dl className="overview-kpis" aria-label="Published dataset coverage">
      {kpis.map(({ label, value, note, icon: Icon }) => <div className="ov-kpi" key={label}>
        <dt><Icon size={16} aria-hidden="true" />{label}</dt><dd>{count(value)}</dd><div className="ov-kpi-note">{note}</div>
      </div>)}
    </dl>

    <div className="overview-analytics">
      <section className="ov-role-section" aria-labelledby={`${id}-roles`}>
        <div className="ov-section-head"><div><h2 id={`${id}-roles`}>Role distribution</h2><p>All {count(data.players.length)} published profiles</p></div><span className="ov-unit">Players</span></div>
        <svg className="ov-role-chart" viewBox={`0 0 480 ${roles.length * 31 + 32}`} role="img" aria-labelledby={`${id}-role-title`}>
          <title id={`${id}-role-title`}>{`Player counts by role: ${roles.map(role => `${role.name}: ${role.count}`).join('; ')}`}</title>
          {roles.map((role, index) => <g key={role.name} transform={`translate(0 ${index * 31 + 8})`}>
            <text className="ov-chart-label" x={0} y={14}>{role.name}</text>
            <rect className="ov-role-bar" x={126} y={2} width={role.count / axisMaximum * 304} height={16} rx={2} fill={role.color} />
            <text className="ov-chart-value" x={466} y={14} textAnchor="end">{count(role.count)}</text>
          </g>)}
          {[0, axisMaximum / 2, axisMaximum].map(tick => <text className="ov-chart-tick" key={tick} x={126 + tick / axisMaximum * 304} y={roles.length * 31 + 23} textAnchor="middle">{count(tick)}</text>)}
        </svg>
        <p className="ov-note">Primary event-derived role · outfield players only.</p>
      </section>

      <section className="ov-xt-section" aria-labelledby={`${id}-xt`}>
        <div className="ov-section-head"><div><h2 id={`${id}-xt`}>Expected threat surface</h2><p>{count(trainCount)} training matches <span aria-hidden="true">/</span> {count(testCount)} held out</p></div>
          <button type="button" className="ov-text-button" onClick={() => onNavigate('evidence')}>View evidence<ArrowRight size={14} aria-hidden="true" /></button>
        </div>
        <div className="ov-heatmap"><GridHeatmap values={grid} support={evidence.xtSupport} title={`Historical xT surface fitted on ${trainCount} training matches, attack left to right`} /></div>
        <div className="ov-heatmap-meta"><span>{gridValues.length ? `${gridCols} x ${gridRows} grid` : 'No fitted cells published'}</span><span>Attack direction<ArrowRight size={13} aria-hidden="true" /></span><span>{gridValues.length ? `${fmt(gridRange[0], 3)} to ${fmt(gridRange[1], 3)} xT` : 'xT unavailable'}</span></div>
        <p className="ov-note">Successful-move value, not total player quality.</p>
      </section>
    </div>

    <div className="overview-bottom">
      <section className="ov-discovery" aria-labelledby={`${id}-discovery`}>
        <div className="ov-section-head ov-discovery-head">
          <div><h2 id={`${id}-discovery`}>Player discovery</h2><p>{count(eligiblePlayers.length)} eligible profiles <span aria-hidden="true">/</span> Highest measured rates</p></div>
          <div className="ov-filters">
            <label className="ov-field"><span>Metric</span><select value={metric.key} onChange={event => setMetricKey(event.target.value)}>{metrics.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
            <label className="ov-field"><span>Minimum minutes</span><select value={minimumMinutes} onChange={event => setMinimumMinutes(Number(event.target.value))}>{[0, 90, 180, 270, 450, 600].map(minutes => <option key={minutes} value={minutes}>{minutes === 0 ? 'Any exposure' : `${minutes}+ min`}</option>)}</select></label>
          </div>
        </div>
        <div className="ov-table-scroll" tabIndex={0} role="region" aria-label="Player discovery table">
          <table className="ov-player-table">
            <thead><tr><th scope="col">Player</th><th scope="col">Team</th><th scope="col">Role</th><th scope="col" className="ov-numeric">Min*</th><th scope="col" className="ov-numeric" aria-sort="descending">{metric.label}<span aria-hidden="true"> ↓</span></th><th scope="col"><span className="ov-save-heading">Save</span></th></tr></thead>
            <tbody>{visiblePlayers.length ? visiblePlayers.map(player => <tr key={player.id}>
              <td><button type="button" className="ov-player-name" onClick={() => onPlayer(player.id)}><span>{player.name}</span><small className="ov-player-team">{player.team}</small></button></td><td>{player.team}</td><td>{player.role}</td>
              <td className="ov-numeric">{count(player.minutes)}</td><td className="ov-numeric ov-metric-value">{fmt(player.metrics[metric.key], metric.digits)}</td>
              <td><button type="button" className={`ov-save${saved.has(player.id) ? ' ov-saved' : ''}`} aria-pressed={saved.has(player.id)} aria-label={`${saved.has(player.id) ? 'Remove' : 'Save'} ${player.name}${saved.has(player.id) ? ' from' : ' to'} watchlist`} title={saved.has(player.id) ? 'Remove from watchlist' : 'Save to watchlist'} onClick={() => toggleWatch(player.id)}><Bookmark size={16} fill={saved.has(player.id) ? 'currentColor' : 'none'} aria-hidden="true" /></button></td>
            </tr>) : <tr><td colSpan={6} className="ov-empty" role="status">No profiles with a measured {metric.label} meet this exposure threshold.</td></tr>}</tbody>
          </table>
        </div>
        <div className="ov-table-footer"><p className="ov-note">*Approximate, stoppage-inclusive minutes. {metric.note}</p><button type="button" className="ov-text-button" onClick={() => onNavigate('recruitment')}>Open recruitment<ArrowRight size={14} aria-hidden="true" /></button></div>
      </section>

      <aside className="ov-match" aria-labelledby={`${id}-match`}>
        <div className="ov-section-head"><h2 id={`${id}-match`}>Match spotlight</h2></div>
        {spotlight ? <>
          <p className="ov-match-context"><time dateTime={spotlight.date}>{spotlight.date}</time> <span aria-hidden="true">/</span> {spotlight.stage}</p>
          <div className="ov-scoreline"><span>{spotlight.home}</span><strong aria-label={`Final score ${spotlight.score}`}>{spotlight.score || 'Score unavailable'}</strong><span>{spotlight.away}</span></div>
          <div className="ov-match-label">Final score</div>
          <h3 className="ov-xg-title">Expected goals</h3>
          <svg className="ov-xg-chart" viewBox="0 0 280 90" role="img" aria-labelledby={`${id}-xg-title`}>
            <title id={`${id}-xg-title`}>{`Provider shot xG: ${spotlight.home} ${fmt(homeStats?.xg, 2)}; ${spotlight.away} ${fmt(awayStats?.xg, 2)}`}</title>
            {[{ team: spotlight.home, value: homeStats?.xg, color: '#10b981' }, { team: spotlight.away, value: awayStats?.xg, color: '#3b82f6' }].map((team, index) => <g key={`${team.team}-${index}`} transform={`translate(0 ${index * 44})`}>
              <text className="ov-chart-label" x={0} y={13}>{team.team}</text><text className="ov-chart-value" x={278} y={13} textAnchor="end">{finite(team.value) && team.value >= 0 ? fmt(team.value, 2) : 'N/A'}</text>
              {finite(team.value) && team.value >= 0 && <rect x={0} y={23} width={team.value / xgMaximum * 278} height={9} rx={2} fill={team.color} />}
            </g>)}
          </svg>
          <p className="ov-note">Provider shot xG, not a match forecast.</p>
          <button type="button" className="ov-inspect-match" onClick={() => onMatch(spotlight.id)}>Inspect match<ArrowRight size={14} aria-hidden="true" /></button>
        </> : <p className="ov-empty" role="status">No historical match aggregates published.</p>}
      </aside>
    </div>
  </div>;
}
