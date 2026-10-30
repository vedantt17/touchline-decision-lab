import { useId, type KeyboardEvent } from 'react';
import type { Action } from './types';
import { Pitch } from './components';
import { isSameZone, laneCell, laneDescription, LANE_CELL_HEIGHT, LANE_CELL_WIDTH } from './laneGeometry';

interface Props {
  team: string;
  lanes: Action[];
  selected?: Action;
  showAll: boolean;
  onSelect: (id: string) => void;
}

export default function LanePitch({ team, lanes, selected, showAll, onSelect }: Props) {
  const arrow = useId().replaceAll(':', '');
  const visible = showAll ? lanes.filter(lane => lane.id !== selected?.id) : [];
  const activate = (lane: Action) => ({
    role: 'button', tabIndex: 0, 'aria-label': laneDescription(lane),
    onClick: () => onSelect(lane.id),
    onKeyDown: (event: KeyboardEvent<SVGGElement>) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(lane.id); }
    },
  });

  return <Pitch title={`${team} supported attacking patterns: highlighted areas are same-zone activity; arrows connect different zones. Attacking left to right.`} className="lane-pitch">
    <defs><marker id={arrow} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#f7c96c" /></marker></defs>
    <g className="lane-grid" stroke="#d4e9df" strokeWidth={0.12} opacity={0.17} pointerEvents="none">
      {[1, 2, 3, 4, 5].map(column => <path key={`x${column}`} d={`M${column * LANE_CELL_WIDTH} 0V68`} />)}
      {[1, 2, 3].map(row => <path key={`y${row}`} d={`M0 ${row * LANE_CELL_HEIGHT}H105`} />)}
    </g>
    <g className="background-lanes">{visible.map(lane => {
      const cell = laneCell(lane.start);
      return <g key={lane.id} {...activate(lane)} className="lane-map-target"><title>{laneDescription(lane)}</title>{isSameZone(lane)
        ? <rect className="other-zone-activity" x={cell.x + .3} y={cell.y + .3} width={LANE_CELL_WIDTH - .6} height={LANE_CELL_HEIGHT - .6} rx={.7} fill="#a6d9c5" fillOpacity={.09} stroke="#b2dbca" strokeOpacity={.22} strokeWidth={.25} />
        : <><line x1={lane.start[0]} y1={lane.start[1]} x2={lane.end[0]} y2={lane.end[1]} stroke="transparent" strokeWidth={3.8} /><line className="other-zone-route" x1={lane.start[0]} y1={lane.start[1]} x2={lane.end[0]} y2={lane.end[1]} stroke="#b3dcca" strokeOpacity={.55} strokeWidth={Math.min(1.2, .45 + lane.count / 120)} strokeDasharray={lane.type === 'carry' ? '1.4 1' : undefined} /></>}
      </g>;
    })}</g>
    {selected && <g className="selected-lane" data-pattern-kind={isSameZone(selected) ? 'same-zone' : 'between-zone'}>
      <title>{laneDescription(selected)}</title>
      {isSameZone(selected) ? <g className="within-zone-activity">
        <rect x={laneCell(selected.start).x + .2} y={laneCell(selected.start).y + .2} width={LANE_CELL_WIDTH - .4} height={LANE_CELL_HEIGHT - .4} rx={.7} fill="#f7c96c" fillOpacity={.22} stroke="#f7c96c" strokeWidth={.55} />
        <circle cx={selected.start[0]} cy={selected.start[1]} r={4.1} fill="none" stroke="#f7c96c" strokeOpacity={.5} strokeWidth={.3} />
        <circle cx={selected.start[0]} cy={selected.start[1]} r={3.25} fill="#f7c96c" stroke="#163c31" strokeWidth={.25} />
        <text x={selected.start[0]} y={selected.start[1]} textAnchor="middle" dominantBaseline="central" fontSize={String(selected.count).length > 2 ? 2.1 : 2.8} fontWeight={700} fill="#253a2e">{selected.count}</text>
      </g> : <g className="between-zone-route">
        <line x1={selected.start[0]} y1={selected.start[1]} x2={selected.end[0]} y2={selected.end[1]} stroke="#153d33" strokeWidth={2.1} />
        <line x1={selected.start[0]} y1={selected.start[1]} x2={selected.end[0]} y2={selected.end[1]} stroke="#f7c96c" strokeWidth={1.15} strokeDasharray={selected.type === 'carry' ? '2 1.2' : undefined} markerEnd={`url(#${arrow})`} />
        <circle cx={selected.start[0]} cy={selected.start[1]} r={1.5} fill="#193e35" stroke="#f7c96c" strokeWidth={.65} />
      </g>}
    </g>}
  </Pitch>;
}
