/** Small SVG charts drawn in the theme tokens (no chart library). */

export interface Series {
  key: string;
  label: string;
  className: string;
}

function Legend({ series }: { series: Series[] }) {
  return (
    <div className="legend" aria-hidden="true" style={{ marginBottom: 12 }}>
      {series.map((s) => (
        <span key={s.key}>
          <i className={`swatch ${s.className}`} />
          {s.label}
        </span>
      ))}
    </div>
  );
}

export function GroupedBars({
  data,
  labelKey,
  series,
  title,
  format = (n: number) => String(Math.round(n * 100) / 100),
  height = 220,
}: {
  data: Record<string, unknown>[];
  labelKey: string;
  series: Series[];
  title: string;
  format?: (n: number) => string;
  height?: number;
}) {
  const H = height;
  const padL = 44;
  const padT = 16;
  const padB = 32;
  const bar = 16;
  const gap = 4;
  const groupW = Math.max(72, series.length * (bar + gap) + 32);
  const W = padL + data.length * groupW + 8;
  const max = Math.max(1e-9, ...data.flatMap((d) => series.map((s) => Number(d[s.key] ?? 0))));
  const plotH = H - padB - padT;
  const y = (v: number) => H - padB - (v / max) * plotH;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const showValues = data.length * series.length <= 18;
  return (
    <figure style={{ margin: 0 }}>
      <Legend series={series} />
      <div className="table-wrap">
        <svg
          className="chart"
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          style={{ minWidth: Math.min(W, 320), maxHeight: H + 40 }}
          role="img"
          aria-label={title}
        >
          {ticks.map((t, i) => (
            <g key={i}>
              <line className={i === 0 ? "axis-base" : "axis"} x1={padL} x2={W} y1={y(t)} y2={y(t)} />
              <text x={padL - 8} y={y(t) + 4} textAnchor="end">
                {format(t)}
              </text>
            </g>
          ))}
          {data.map((d, gi) => {
            const inner = series.length * bar + (series.length - 1) * gap;
            const gx = padL + gi * groupW + (groupW - inner) / 2;
            return (
              <g key={gi}>
                {series.map((s, si) => {
                  const v = Number(d[s.key] ?? 0);
                  const x = gx + si * (bar + gap);
                  const h = Math.max(H - padB - y(v), v > 0 ? 2 : 0);
                  return (
                    <g key={s.key}>
                      <rect className={s.className} x={x} y={H - padB - h} width={bar} height={h} rx={3}>
                        <title>{`${String(d[labelKey])} · ${s.label}: ${format(v)}`}</title>
                      </rect>
                      {showValues && (
                        <text className="val" x={x + bar / 2} y={H - padB - h - 4} textAnchor="middle">
                          {format(v)}
                        </text>
                      )}
                    </g>
                  );
                })}
                <text x={gx + inner / 2} y={H - padB + 18} textAnchor="middle">
                  {String(d[labelKey]).slice(0, 12)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <figcaption className="sr-only">{title}</figcaption>
    </figure>
  );
}

export function HBars({ data, title }: { data: { label: string; value: number }[]; title: string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (!data.length) return <p className="small muted">No data yet</p>;
  return (
    <ul className="clean stack" aria-label={title} style={{ gap: 12 }}>
      {data.map((d) => (
        <li key={d.label}>
          <div className="row-between small" style={{ marginBottom: 4 }}>
            <span>{d.label}</span>
            <span className="mono">{d.value}</span>
          </div>
          <svg width="100%" height="6" className="chart" aria-hidden="true" preserveAspectRatio="none" viewBox="0 0 100 6">
            <rect className="hbar-track" x="0" y="0" width="100" height="6" rx="3" />
            <rect className="bar-a" x="0" y="0" width={(d.value / max) * 100} height="6" rx="3" />
          </svg>
        </li>
      ))}
    </ul>
  );
}

export function Scatter({
  data,
  title,
}: {
  data: { x: number; y: number; label: string }[];
  title: string;
}) {
  const W = 420;
  const H = 200;
  const pad = 44;
  const mx = Math.max(1e-9, ...data.map((d) => d.x));
  const my = Math.max(1e-9, ...data.map((d) => d.y));
  return (
    <div className="table-wrap">
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }} role="img" aria-label={title}>
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} className="axis" x1={pad} x2={W - 10} y1={H - pad - f * (H - pad - 20)} y2={H - pad - f * (H - pad - 20)} />
        ))}
        <line className="axis-base" x1={pad} x2={W - 10} y1={H - pad} y2={H - pad} />
        <line className="axis-base" x1={pad} x2={pad} y1={10} y2={H - pad} />
        <text x={W / 2} y={H - 10} textAnchor="middle">
          latency (ms) · max {Math.round(mx)}
        </text>
        <text x={14} y={H / 2} transform={`rotate(-90 14 ${H / 2})`} textAnchor="middle">
          cost ($) · max {my.toFixed(4)}
        </text>
        {data.map((d, i) => (
          <circle key={i} className="bar-b" cx={pad + (d.x / mx) * (W - pad - 20)} cy={H - pad - (d.y / my) * (H - pad - 20)} r={4} opacity={0.85}>
            <title>{`${d.label}: ${Math.round(d.x)} ms, $${d.y.toFixed(4)}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}
