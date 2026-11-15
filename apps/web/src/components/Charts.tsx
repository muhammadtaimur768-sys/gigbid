/** Minimal SVG charts (no chart library). */

export interface Series {
  key: string;
  label: string;
  className: string;
}

export function GroupedBars({
  data,
  labelKey,
  series,
  title,
  format = (n: number) => String(Math.round(n * 100) / 100),
}: {
  data: Record<string, unknown>[];
  labelKey: string;
  series: Series[];
  title: string;
  format?: (n: number) => string;
}) {
  const H = 180;
  const padL = 36;
  const padB = 40;
  const groupW = Math.max(44, series.length * 18 + 14);
  const W = padL + data.length * groupW + 10;
  const max = Math.max(1e-9, ...data.flatMap((d) => series.map((s) => Number(d[s.key] ?? 0))));
  const y = (v: number) => H - padB - (v / max) * (H - padB - 10);
  const ticks = [0, max / 2, max];
  return (
    <figure style={{ margin: 0 }}>
      <div className="legend" aria-hidden="true">
        {series.map((s) => (
          <span key={s.key}>
            <i className={s.className} style={{ background: "currentColor" }} />
            {s.label}
          </span>
        ))}
      </div>
      <div className="table-wrap">
        <svg className="chart" width={Math.max(W, 280)} height={H} role="img" aria-label={title}>
          {ticks.map((t, i) => (
            <g key={i}>
              <line className="axis" x1={padL} x2={W} y1={y(t)} y2={y(t)} strokeDasharray={i ? "3 3" : undefined} />
              <text x={padL - 6} y={y(t) + 4} textAnchor="end">
                {format(t)}
              </text>
            </g>
          ))}
          {data.map((d, gi) => {
            const gx = padL + gi * groupW + 8;
            return (
              <g key={gi}>
                {series.map((s, si) => {
                  const v = Number(d[s.key] ?? 0);
                  return (
                    <rect key={s.key} className={s.className} x={gx + si * 18} y={y(v)} width={14} height={Math.max(0, H - padB - y(v))} rx={2}>
                      <title>{`${String(d[labelKey])} · ${s.label}: ${format(v)}`}</title>
                    </rect>
                  );
                })}
                <text x={gx + (series.length * 18) / 2 - 2} y={H - padB + 14} textAnchor="middle">
                  {String(d[labelKey]).slice(0, 10)}
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
  return (
    <ul className="clean stack" aria-label={title} style={{ gap: 8 }}>
      {data.map((d) => (
        <li key={d.label}>
          <div className="row-between small">
            <span>{d.label}</span>
            <strong>{d.value}</strong>
          </div>
          <svg width="100%" height="8" className="chart" aria-hidden="true" preserveAspectRatio="none" viewBox="0 0 100 8">
            <rect x="0" y="0" width="100" height="8" rx="4" fill="var(--surface-2)" />
            <rect className="bar-a" x="0" y="0" width={(d.value / max) * 100} height="8" rx="4" />
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
  const pad = 40;
  const mx = Math.max(1e-9, ...data.map((d) => d.x));
  const my = Math.max(1e-9, ...data.map((d) => d.y));
  return (
    <div className="table-wrap">
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }} role="img" aria-label={title}>
        <line className="axis" x1={pad} x2={W - 10} y1={H - pad} y2={H - pad} />
        <line className="axis" x1={pad} x2={pad} y1={10} y2={H - pad} />
        <text x={W / 2} y={H - 8} textAnchor="middle">
          latency (ms) · max {Math.round(mx)}
        </text>
        <text x={12} y={H / 2} transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle">
          cost ($) · max {my.toFixed(4)}
        </text>
        {data.map((d, i) => (
          <circle key={i} className="bar-a" cx={pad + (d.x / mx) * (W - pad - 20)} cy={H - pad - (d.y / my) * (H - pad - 20)} r={4} opacity={0.8}>
            <title>{`${d.label}: ${Math.round(d.x)} ms, $${d.y.toFixed(4)}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}
