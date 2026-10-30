export interface Feature { key: string; label: string; group: string; unit: string; description: string }
export interface Player {
 id: number; name: string; team: string; role: string; position: string;
 minutes: number; appearances: number; matches: number[];
 metrics: Record<string, number>; z: Record<string, number>;
 style: number[];
 xtInterval: [number, number] | null;
}
export interface Action { id: string; player: string; playerId: number; team: string; minute: number; period: number; type: string; start: [number,number]; end: [number,number]; xt: number; success: boolean; count: number }
export interface Match { id: number; date: string; home: string; away: string; score: string; stage: string; actions: Action[]; teamStats: {team: string; shots: number; xg: number; xt: number; passes: number; completions: number; left: number; center: number; right: number}[] }
export interface TrackingPlayer {id: string; team: string; number: string; x: number; y: number; vx: number; vy: number; detected?: boolean}
export interface TrackingFrame {t: number; players: TrackingPlayer[]; ball: [number,number] | null; control: number[][]; massError?: number}
export interface Tracking {
 source: string; dataset: string; label: string; fps: number; pitch: [number,number];
 frames: TrackingFrame[]; model: string; assumptions: string[]; home: string; away: string;
 quality: Record<string, number|string>;
}
export interface Provider { name: string; scope: string; license: string; url: string; status: string }
export interface Evidence {
 buildDate: string; competition: string; events: number; matches: number; players: number;
 trainMatches: number[]; testMatches: number[]; xtGrid: number[][]; xtSupport: number[][];
 evaluation: {name: string; value: number|string; detail: string}[];
 checks: {name: string; passed: boolean; detail: string}[];
 providers: Provider[]; limitations: string[]; methodology: string[];
}
export interface Dataset {version: string; features: Feature[]; players: Player[]; matches: Match[]; tracking: Tracking[]; evidence: Evidence}
