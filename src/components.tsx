import { useId, type ReactNode, type ButtonHTMLAttributes } from 'react';
import { ArrowUpRight, CircleAlert, SearchX, type LucideIcon } from 'lucide-react';
import type { Feature, Player } from './types';

export const finite = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n);
export const fmt = (n: unknown, digits = 2) => finite(n) ? n.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits }) : '\u2014';
export const count = (n: unknown) => finite(n) ? n.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '\u2014';
export const clamp = (n: number, min: number, max: number) => Math.max(min, Math.min(max, n));

export function IconButton({ icon: Icon, label, children, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { icon: LucideIcon; label: string }) {
  return <button type="button" aria-label={label} title={label} className={`icon-button ${className}`} {...props}><Icon size={16} aria-hidden="true" />{children}</button>;
}
export function Field({ label, children, className = '' }: { label: string; children: ReactNode; className?: string }) {
  return <label className={`field ${className}`}><span>{label}</span>{children}</label>;
}
export function Empty({ title, children, error = false }: { title: string; children?: ReactNode; error?: boolean }) {
  const Icon = error ? CircleAlert : SearchX;
  return <div className={`empty-state ${error ? 'error' : ''}`} role={error ? 'alert' : 'status'}><Icon size={25} strokeWidth={1.5} /><h3>{title}</h3>{children && <p>{children}</p>}</div>;
}
export function SectionHead({ label, aside }: { label: ReactNode; aside?: ReactNode }) {
  return <div className="section-head"><h2>{label}</h2>{aside && <div className="section-aside">{aside}</div>}</div>;
}
export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return <div className="stat"><span className="eyebrow">{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>;
}
export function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  let valid = false;
  try { valid = ['http:', 'https:'].includes(new URL(href).protocol); } catch { /* An absent provider URL is not a usable source link. */ }
  return valid ? <a href={href} target="_blank" rel="noreferrer">{children}<ArrowUpRight size={12} aria-hidden="true" /></a> : <span>{children}</span>;
}

export type SimilarityMode = 'metric' | 'spatial';
export interface Similarity { cosine: number; distance: number; dimensions: number }
export function cosineSimilarity(a: number[], b: number[], weights?: number[]): Similarity | null {
  if (a.length !== b.length || !a.length || a.some(n => !finite(n)) || b.some(n => !finite(n))) return null;
  let dot = 0, aa = 0, bb = 0, dimensions = 0;
  a.forEach((n, i) => {
    const w = weights?.[i] ?? 1;
    if (!finite(w) || w <= 0) return;
    dot += w * n * b[i]; aa += w * n * n; bb += w * b[i] * b[i]; dimensions++;
  });
  if (!dimensions || aa <= 1e-16 || bb <= 1e-16) return null;
  const cosine = clamp(dot / Math.sqrt(aa * bb), -1, 1);
  return { cosine, distance: 1 - cosine, dimensions };
}
export function comparePlayers(reference: Player, player: Player, features: Feature[], groupWeights: Record<string, number>, mode: SimilarityMode): Similarity | null {
  if (mode === 'spatial') return reference.style.length === 60 && player.style.length === 60 ? cosineSimilarity(reference.style, player.style) : null;
  const active = features.filter(f => (groupWeights[f.group] ?? 1) > 0);
  if (!active.length || active.some(f => !finite(reference.z[f.key]) || !finite(player.z[f.key]))) return null;
  const sizes = new Map<string, number>();
  active.forEach(f => sizes.set(f.group, (sizes.get(f.group) ?? 0) + 1));
  return cosineSimilarity(active.map(f => reference.z[f.key]), active.map(f => player.z[f.key]), active.map(f => (groupWeights[f.group] ?? 1) / sizes.get(f.group)!));
}
export function xtFeature(features: Feature[]): Feature | undefined {
  return features.find(f => /x_?t|expected.?threat/i.test(f.key + ' ' + f.label) && /90/.test(f.key + ' ' + f.label + ' ' + f.unit));
}
export function interval(player: Player) {
  return player.xtInterval?.length === 2 && player.xtInterval.every(finite) ? `${fmt(player.xtInterval[0], 3)} to ${fmt(player.xtInterval[1], 3)}` : 'Unavailable';
}
export function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function csvCell(value: unknown) {
  const raw = String(value ?? '');
  const safe = typeof value === 'string' && /^[=+@\-\t\r]/.test(raw) ? `'${raw}` : raw;
  return `"${safe.replaceAll('"', '""')}"`;
}

export function Pitch({ children, title, length = 105, width = 68, className = '' }: { children?: ReactNode; title: string; length?: number; width?: number; className?: string }) {
  const id = useId();
  return <svg className={`pitch ${className}`} viewBox={`-4 -5 ${length + 8} ${width + 10}`} role="img" aria-labelledby={id}>
    <title id={id}>{title}</title>
    <rect x={-4} y={-5} width={length + 8} height={width + 10} fill="var(--pitch)" />
    {Array.from({ length: 6 }, (_, i) => <rect key={i} x={i * length / 6} y={0} width={length / 6} height={width} fill={i % 2 ? '#ffffff04' : '#00000004'} />)}
    {children}
    <g className="pitch-markings" fill="none" strokeWidth={0.22}>
      <rect x={0} y={0} width={length} height={width} /><path d={`M${length / 2},0V${width}`} />
      <circle cx={length / 2} cy={width / 2} r={9.15} />
      {[0, 1].map(side => <g key={side} transform={side ? `translate(${length},0) scale(-1,1)` : undefined}>
        <rect x={0} y={(width - 40.32) / 2} width={16.5} height={40.32} /><rect x={0} y={(width - 18.32) / 2} width={5.5} height={18.32} />
        <path d={`M0,${width / 2 - 3.66}H-1.4V${width / 2 + 3.66}H0`} /><circle cx={11} cy={width / 2} r={0.35} fill="currentColor" />
        <path d={`M16.5,${width / 2 - 7.31} A9.15,9.15 0 0 1 16.5,${width / 2 + 7.31}`} />
      </g>)}
      <circle cx={length / 2} cy={width / 2} r={0.35} fill="currentColor" />
    </g>
  </svg>;
}

export function ProfileBars({ reference, player, features }: { reference: Player; player: Player; features: Feature[] }) {
  return <div className="profile-bars"><div className="legend"><span><i className="dot green" />{player.name}</span><span><i className="dot gold" />{reference.name}</span><span>role-normalized z</span></div>
    {features.map(f => <div className="profile-row" key={f.key} title={f.description}>
      <span>{f.label}</span><div className="bar-pair"><i className="zero-line" />{[player, reference].map((p, i) => {
        const value = p.z[f.key];
        return <div className="bar-track" key={p.id + '-' + i}>{finite(value) && <b className={i ? 'reference-bar' : 'candidate-bar'} style={{ left: `${50 + Math.min(0, clamp(value, -3, 3)) / 6 * 100}%`, width: `${Math.abs(clamp(value, -3, 3)) / 6 * 100}%` }} />}</div>;
      })}</div><span className="mono">{fmt(player.z[f.key], 1)} <small>/ {fmt(reference.z[f.key], 1)}</small></span>
    </div>)}<div className="bar-axis"><span>-3</span><span>0</span><span>+3</span></div>
  </div>;
}

export function GridHeatmap({ values, support, title }: { values: number[][]; support?: number[][]; title: string }) {
  const flat = values.flat().filter(finite), max = Math.max(...flat.map(Math.abs), 1e-10);
  if (!flat.length) return <Empty title="No grid published" />;
  const rows = values.length, cols = Math.max(...values.map(r => r.length));
  return <Pitch title={title}><g>{values.flatMap((row, y) => row.map((v, x) => finite(v) ? <rect key={`${x}-${y}`} x={105 * x / cols} y={68 * y / rows} width={105 / cols} height={68 / rows} fill={v < 0 ? '#c86b58' : '#e9bc59'} opacity={0.12 + Math.abs(v) / max * 0.76} stroke="#ffffff18" strokeWidth={0.2}><title>{`Cell ${x + 1}, ${y + 1}: ${fmt(v, 4)}${support ? `; support ${count(support[y]?.[x])}` : ''}`}</title></rect> : null))}</g></Pitch>;
}
