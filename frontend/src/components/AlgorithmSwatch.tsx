export default function AlgorithmSwatch({ visual }: { visual?: Record<string, any> }) {
  if (!visual) return null;
  const dash = ({ solid: "", dash: "6 3", dot: "1 3", dashdot: "6 3 1 3" } as Record<string, string>)[visual.dash];
  return <svg width="48" height="20" viewBox="0 0 48 20" aria-label={`${visual.dash} ${visual.symbol}`} style={{ color: visual.color, verticalAlign: "middle" }}>
    <line x1="1" y1="10" x2="47" y2="10" stroke="currentColor" strokeWidth="2" strokeDasharray={dash} />
    <g fill="currentColor" stroke="white" strokeWidth="1">
      {visual.symbol === "square" ? <rect x="20" y="6" width="8" height="8" /> :
        visual.symbol === "diamond" ? <path d="M24 4L30 10L24 16L18 10Z" /> :
        visual.symbol === "triangle-up" ? <path d="M24 4L30 15L18 15Z" /> :
        visual.symbol === "cross" || visual.symbol === "x" ? <text x="24" y="15" textAnchor="middle" stroke="none" fontSize="18">{visual.symbol === "x" ? "×" : "+"}</text> :
        <circle cx="24" cy="10" r="5" />}
    </g>
  </svg>;
}
