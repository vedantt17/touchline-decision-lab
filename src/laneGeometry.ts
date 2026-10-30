import type { Action } from './types';

export const LANE_CELL_WIDTH = 105 / 6;
export const LANE_CELL_HEIGHT = 68 / 4;

export function laneCell(point: [number, number]) {
  if (!point.every(Number.isFinite)) throw new Error('Lane coordinates must be finite');
  const column = Math.max(0, Math.min(5, Math.floor(point[0] / LANE_CELL_WIDTH)));
  const row = Math.max(0, Math.min(3, Math.floor(point[1] / LANE_CELL_HEIGHT)));
  return { column, row, x: column * LANE_CELL_WIDTH, y: row * LANE_CELL_HEIGHT };
}

export function isSameZone(lane: Pick<Action, 'start' | 'end'>) {
  const start = laneCell(lane.start), end = laneCell(lane.end);
  return start.column === end.column && start.row === end.row;
}

export function zoneLabel(point: [number, number]) {
  const { column, row } = laneCell(point);
  const third = column < 2 ? 'defensive third' : column < 4 ? 'middle third' : 'attacking third';
  const channel = ['upper channel', 'upper-central channel', 'lower-central channel', 'lower channel'][row];
  return `${third}, ${channel}`;
}

export function laneDescription(lane: Action) {
  const movement = lane.type.toLowerCase() === 'carry' ? 'carries' : 'passes';
  const origin = zoneLabel(lane.start), destination = zoneLabel(lane.end);
  return isSameZone(lane)
    ? `${lane.count} successful ${movement} within the ${origin}`
    : `${lane.count} successful ${movement} from the ${origin} to the ${destination}`;
}
