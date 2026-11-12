/** Static illustration of the Refinery pipeline. Shown first on every device and kept when 3D is unavailable. */
export function HeroFallback({ className }: { className?: string }) {
  const cells = (rows: number, cols: number, messy: boolean) =>
    Array.from({ length: rows * cols }, (_, i) => {
      const r = Math.floor(i / cols);
      const c = i % cols;
      // Deterministic pseudo-random jitter (no Math.random: must match between server and client).
      const j = ((i * 9301 + 49297) % 233280) / 233280;
      const k = ((i * 4253 + 1237) % 7919) / 7919;
      const bad = messy && (i % 7 === 3 || i % 11 === 5);
      return (
        <rect
          key={i}
          x={c * 22 + (messy ? (j - 0.5) * 7 : 0)}
          y={r * 13 + (messy ? (k - 0.5) * 5 : 0)}
          width={messy ? 12 + j * 9 : 18}
          height={8}
          rx={2}
          transform={messy ? `rotate(${(j - 0.5) * 10} ${c * 22 + 9} ${r * 13 + 4})` : undefined}
          fill={bad ? (i % 2 ? "#F59E0B" : "#F87171") : messy ? "#475569" : c === 0 ? "#22D3EE" : "#3B82F6"}
          opacity={bad ? 0.95 : messy ? 0.55 : 0.75 - (r % 2) * 0.15}
        />
      );
    });

  return (
    <svg viewBox="0 0 640 440" className={className} role="img" aria-labelledby="hero-fallback-title" preserveAspectRatio="xMidYMid meet">
      <title id="hero-fallback-title">
        Messy spreadsheet cells flow through a processing core and come out as a clean table with charts rising from it
      </title>
      <defs>
        <linearGradient id="hf-panel" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1E2A44" stopOpacity="0.9" />
          <stop offset="1" stopColor="#111827" stopOpacity="0.9" />
        </linearGradient>
        <linearGradient id="hf-flow" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#F59E0B" stopOpacity="0.7" />
          <stop offset="0.5" stopColor="#8B5CF6" />
          <stop offset="1" stopColor="#14B8A6" />
        </linearGradient>
        <radialGradient id="hf-core" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#22D3EE" stopOpacity="0.55" />
          <stop offset="1" stopColor="#22D3EE" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* flow lines */}
      {[-34, -12, 12, 34].map((dy, i) => (
        <path
          key={i}
          d={`M 150 ${250 + dy * 1.6} C 240 ${250 + dy * 1.4}, 270 ${230 + dy * 0.3}, 320 230 S 420 ${230 + dy * 0.5}, 470 ${250 + dy * 0.9}`}
          fill="none"
          stroke="url(#hf-flow)"
          strokeWidth="1.25"
          opacity="0.55"
        />
      ))}

      {/* messy stack */}
      <g transform="translate(34 150)">
        <g transform="rotate(-9 70 90)">
          <rect x="6" y="14" width="140" height="170" rx="12" fill="url(#hf-panel)" stroke="#334155" />
        </g>
        <g transform="rotate(6 70 90)">
          <rect x="-4" y="4" width="140" height="170" rx="12" fill="url(#hf-panel)" stroke="#475569" />
        </g>
        <g transform="rotate(-3 70 90)">
          <rect x="0" y="0" width="140" height="170" rx="12" fill="url(#hf-panel)" stroke="#64748B" />
          <g transform="translate(16 20)">{cells(11, 5, true)}</g>
        </g>
      </g>

      {/* core */}
      <g transform="translate(320 230)">
        <circle r="92" fill="url(#hf-core)" />
        <ellipse rx="62" ry="62" fill="none" stroke="#22D3EE" strokeWidth="2" opacity="0.9" />
        <ellipse rx="62" ry="22" fill="none" stroke="#8B5CF6" strokeWidth="1.5" opacity="0.8" transform="rotate(28)" />
        <ellipse rx="62" ry="22" fill="none" stroke="#3B82F6" strokeWidth="1.5" opacity="0.8" transform="rotate(-32)" />
        <polygon points="0,-26 23,-13 23,13 0,26 -23,13 -23,-13" fill="#0B1222" stroke="#22D3EE" strokeWidth="1.5" />
        <circle r="5" fill="#22D3EE" />
        {[0, 60, 120, 180, 240, 300].map((a) => (
          <circle key={a} r="3.5" fill="#F8FAFC" cx={62 * Math.cos((a * Math.PI) / 180)} cy={62 * Math.sin((a * Math.PI) / 180)} />
        ))}
      </g>

      {/* clean panel */}
      <g transform="translate(466 190)">
        <rect x="0" y="0" width="140" height="170" rx="12" fill="url(#hf-panel)" stroke="#14B8A6" strokeOpacity="0.7" />
        <g transform="translate(16 22)">{cells(10, 5, false)}</g>
      </g>

      {/* insights rising from the clean panel */}
      <g transform="translate(478 60)">
        {[34, 58, 46, 82, 70].map((h, i) => (
          <rect key={i} x={i * 24} y={104 - h} width="14" height={h} rx="3" fill={["#3B82F6", "#14B8A6", "#8B5CF6", "#22D3EE", "#3B82F6"][i]} opacity="0.9" />
        ))}
        <path d="M 2 62 L 30 40 L 54 52 L 78 14 L 104 26" fill="none" stroke="#F8FAFC" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        {[
          [2, 62],
          [30, 40],
          [54, 52],
          [78, 14],
          [104, 26],
        ].map(([x, y]) => (
          <circle key={x} cx={x} cy={y} r="3" fill="#22D3EE" />
        ))}
      </g>
    </svg>
  );
}
