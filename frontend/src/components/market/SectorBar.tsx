import type { HeatmapSector } from "@/types";
import { cn } from "@/lib/utils";

interface SectorBarProps {
  sectors: HeatmapSector[];
  focusSector: string | null;
  onSectorClick: (sectorName: string | null) => void;
}

const getSectorBadgeColor = (avgChangePct: number | undefined | null): string => {
  const pct = avgChangePct ?? 0;

  if (pct <= -3) return "bg-red-700 text-white";
  if (pct <= -1) return "bg-red-500/80 text-white";
  if (pct <= -0.5) return "bg-red-400/60 text-white";
  if (pct < 0.5) return "bg-gray-500/60 text-white";
  if (pct < 1) return "bg-green-400/60 text-white";
  if (pct < 3) return "bg-green-500/80 text-white";
  return "bg-green-700 text-white";
};

const getAvgChangePct = (sector: HeatmapSector): number => {
  if (sector.avg_change_pct !== undefined && sector.avg_change_pct !== null) {
    return sector.avg_change_pct;
  }
  // Calculate from stocks if not provided
  if (sector.stocks.length === 0) return 0;
  const sum = sector.stocks.reduce((acc, s) => acc + (s.change_pct ?? 0), 0);
  return sum / sector.stocks.length;
};

const abbreviateSector = (name: string): string => {
  const map: Record<string, string> = {
    "Information Technology": "IT",
    "Communication Services": "Comm Svc",
    "Consumer Discretionary": "Cons Disc",
    "Consumer Staples": "Cons Stpl",
    "Health Care": "Healthcare",
    "Real Estate": "Real Est",
  };
  return map[name] ?? name;
};

const SectorBar = ({ sectors, focusSector, onSectorClick }: SectorBarProps) => {
  const sorted = [...sectors].sort(
    (a, b) => getAvgChangePct(b) - getAvgChangePct(a),
  );

  return (
    <div className="flex flex-wrap gap-1.5">
      {sorted.map((sector) => {
        const avg = getAvgChangePct(sector);
        const isActive = focusSector === sector.name;
        const sign = avg >= 0 ? "+" : "";

        return (
          <button
            key={sector.name}
            onClick={() => onSectorClick(isActive ? null : sector.name)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
              getSectorBadgeColor(avg),
              isActive
                ? "ring-2 ring-white ring-offset-1 ring-offset-background scale-105"
                : "hover:opacity-80",
            )}
            title={`${sector.name}: ${sign}${avg.toFixed(2)}%`}
          >
            <span className="truncate max-w-[100px]">
              {abbreviateSector(sector.name)}
            </span>
            <span className="font-bold tabular-nums">
              {sign}{avg.toFixed(2)}%
            </span>
          </button>
        );
      })}
    </div>
  );
};

export default SectorBar;
