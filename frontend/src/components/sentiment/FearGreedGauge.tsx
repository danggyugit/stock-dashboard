import type { FearGreedData } from "@/types";

interface FearGreedGaugeProps {
  data: FearGreedData;
}

const getScoreColor = (score: number | null): string => {
  if (score === null) return "text-muted-foreground";
  if (score <= 25) return "text-red-600";
  if (score <= 45) return "text-orange-500";
  if (score <= 55) return "text-yellow-500";
  if (score <= 75) return "text-green-500";
  return "text-green-600";
};

const getLabelColor = (score: number): string => {
  if (score <= 25) return "#dc2626";
  if (score <= 45) return "#f97316";
  if (score <= 55) return "#eab308";
  if (score <= 75) return "#22c55e";
  return "#16a34a";
};

interface IndicatorCardProps {
  name: string;
  score: number | null;
}

const IndicatorCard = ({ name, score }: IndicatorCardProps) => (
  <div className="flex flex-col items-center rounded-lg border bg-card p-2 text-center">
    <span className="text-xs text-muted-foreground">{name}</span>
    <span className={`text-sm font-bold mt-0.5 ${getScoreColor(score)}`}>
      {score !== null ? score.toFixed(1) : "N/A"}
    </span>
  </div>
);

const FearGreedGauge = ({ data }: FearGreedGaugeProps) => {
  const { score, label } = data;

  // SVG gauge geometry
  const cx = 150;
  const cy = 140;
  const r = 110;
  const strokeWidth = 24;
  const startAngle = Math.PI; // 180 degrees (left)
  const endAngle = 0; // 0 degrees (right)

  // Arc segments: 5 zones (each 20% of the semicircle)
  const zones = [
    { start: 0, end: 0.2, color: "#dc2626" }, // Extreme Fear
    { start: 0.2, end: 0.4, color: "#f97316" }, // Fear
    { start: 0.4, end: 0.6, color: "#eab308" }, // Neutral
    { start: 0.6, end: 0.8, color: "#22c55e" }, // Greed
    { start: 0.8, end: 1.0, color: "#16a34a" }, // Extreme Greed
  ];

  const getArcPath = (startPct: number, endPct: number): string => {
    const a1 = startAngle - startPct * Math.PI;
    const a2 = startAngle - endPct * Math.PI;
    const x1 = cx + r * Math.cos(a1);
    const y1 = cy - r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2);
    const y2 = cy - r * Math.sin(a2);
    const largeArc = endPct - startPct > 0.5 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
  };

  // Needle
  const normalizedScore = Math.max(0, Math.min(100, score)) / 100;
  const needleAngle = startAngle - normalizedScore * (startAngle - endAngle);
  const needleLength = r - strokeWidth / 2 - 8;
  const needleTipX = cx + needleLength * Math.cos(needleAngle);
  const needleTipY = cy - needleLength * Math.sin(needleAngle);

  const indicators = [
    { name: "VIX", score: data.vix_score },
    { name: "Momentum", score: data.momentum_score },
    { name: "Put/Call", score: data.put_call_score },
    { name: "High/Low", score: data.high_low_score },
    { name: "Volume", score: data.volume_score },
  ];

  return (
    <div className="flex flex-col items-center w-full">
      {/* SVG Gauge */}
      <svg viewBox="0 0 300 170" className="w-full max-w-[280px]">
        {/* Background arc segments */}
        {zones.map((zone, i) => (
          <path
            key={i}
            d={getArcPath(zone.start, zone.end)}
            fill="none"
            stroke={zone.color}
            strokeWidth={strokeWidth}
            strokeLinecap="butt"
            opacity={0.25}
          />
        ))}

        {/* Filled arc up to score */}
        {zones.map((zone, i) => {
          const fillEnd = Math.min(zone.end, normalizedScore);
          if (fillEnd <= zone.start) return null;
          return (
            <path
              key={`fill-${i}`}
              d={getArcPath(zone.start, fillEnd)}
              fill="none"
              stroke={zone.color}
              strokeWidth={strokeWidth}
              strokeLinecap="butt"
            />
          );
        })}

        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needleTipX}
          y2={needleTipY}
          stroke={getLabelColor(score)}
          strokeWidth={3}
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r={6} fill={getLabelColor(score)} />
        <circle cx={cx} cy={cy} r={3} fill="white" />

        {/* Score text */}
        <text
          x={cx}
          y={cy + 30}
          textAnchor="middle"
          className="fill-foreground"
          fontSize="36"
          fontWeight="bold"
        >
          {Math.round(score)}
        </text>
        <text
          x={cx}
          y={cy + 50}
          textAnchor="middle"
          fill={getLabelColor(score)}
          fontSize="14"
          fontWeight="600"
        >
          {label}
        </text>

        {/* Scale labels */}
        <text x={cx - r - 4} y={cy + 16} textAnchor="middle" className="fill-muted-foreground" fontSize="10">
          0
        </text>
        <text x={cx + r + 4} y={cy + 16} textAnchor="middle" className="fill-muted-foreground" fontSize="10">
          100
        </text>
      </svg>

      {/* Indicator Cards */}
      <div className="grid grid-cols-5 gap-1.5 w-full mt-3">
        {indicators.map((ind) => (
          <IndicatorCard key={ind.name} name={ind.name} score={ind.score} />
        ))}
      </div>
    </div>
  );
};

export default FearGreedGauge;
