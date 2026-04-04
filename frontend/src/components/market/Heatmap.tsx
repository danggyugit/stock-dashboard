import { useRef, useEffect, useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as d3 from "d3";
import type { HeatmapResponse, HeatmapSector } from "@/types";
import { formatNumber, formatCurrency, formatPercent } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

interface HeatmapProps {
  data: HeatmapResponse;
  isLoading?: boolean;
  focusSector?: string | null;
}

interface TreemapNode {
  name: string;
  children?: TreemapNode[];
  ticker?: string;
  stockName?: string;
  market_cap?: number;
  price?: number;
  change_pct?: number | null;
  volume?: number;
  sector?: string;
}

const getChangeColor = (changePct: number | null): string => {
  if (changePct === null || changePct === undefined) return "#6b7280";

  const clampedPct = Math.max(-10, Math.min(10, changePct));

  if (clampedPct <= -5) return "#dc2626";
  if (clampedPct >= 5) return "#16a34a";

  if (clampedPct < -0.5) {
    // -5 to -0.5 range: dark red to light red
    const t = (clampedPct - -5) / (-0.5 - -5); // 0 at -5, 1 at -0.5
    const scale = d3.scaleLinear<string>()
      .domain([0, 1])
      .range(["#dc2626", "#ef9a9a"]);
    return scale(t);
  }

  if (clampedPct > 0.5) {
    // 0.5 to 5 range: light green to dark green
    const t = (clampedPct - 0.5) / (5 - 0.5); // 0 at 0.5, 1 at 5
    const scale = d3.scaleLinear<string>()
      .domain([0, 1])
      .range(["#a5d6a7", "#16a34a"]);
    return scale(t);
  }

  // -0.5 to 0.5: neutral gray
  return "#6b7280";
};

const getTextColor = (bgColor: string): string => {
  const c = d3.color(bgColor);
  if (!c) return "#ffffff";
  const rgb = c.rgb();
  const luminance = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
  return luminance > 0.5 ? "#1f2937" : "#ffffff";
};

const buildHierarchy = (
  sectors: HeatmapSector[],
  focusSector: string | null,
): TreemapNode => {
  const filteredSectors = focusSector
    ? sectors.filter((s) => s.name === focusSector)
    : sectors;

  return {
    name: "market",
    children: filteredSectors.map((sector) => ({
      name: sector.name,
      children: sector.stocks.map((stock) => ({
        name: stock.ticker,
        ticker: stock.ticker,
        stockName: stock.name,
        market_cap: stock.market_cap,
        price: stock.price,
        change_pct: stock.change_pct,
        volume: stock.volume,
        sector: sector.name,
      })),
    })),
  };
};

const Heatmap = ({ data, isLoading = false, focusSector: externalFocusSector }: HeatmapProps) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const [internalFocusSector, setInternalFocusSector] = useState<string | null>(null);
  const focusSector = externalFocusSector ?? internalFocusSector;

  const renderTreemap = useCallback(() => {
    if (!svgRef.current || !containerRef.current || !data) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    if (width <= 0 || height <= 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const hierarchy = buildHierarchy(data.sectors, focusSector);

    const hierarchyRoot = d3
      .hierarchy<TreemapNode>(hierarchy)
      .sum((d) => (d.market_cap && !d.children ? d.market_cap : 0))
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

    const root = d3.treemap<TreemapNode>()
      .size([width, height])
      .paddingTop(focusSector ? 0 : 22)
      .paddingRight(1)
      .paddingBottom(1)
      .paddingLeft(1)
      .paddingInner(1)
      .round(true)(hierarchyRoot);

    const tooltip = d3.select(tooltipRef.current);

    // Draw sector groups (level 1)
    if (!focusSector) {
      const sectorGroups = root.children ?? [];
      svg
        .selectAll("g.sector-label")
        .data(sectorGroups)
        .join("g")
        .attr("class", "sector-label")
        .each(function (d) {
          const g = d3.select(this);
          const x0 = d.x0 ?? 0;
          const y0 = d.y0 ?? 0;
          const x1 = d.x1 ?? 0;
          const sectorWidth = x1 - x0;

          g.append("rect")
            .attr("x", x0)
            .attr("y", y0)
            .attr("width", sectorWidth)
            .attr("height", 20)
            .attr("fill", "#1e293b")
            .attr("rx", 2)
            .style("cursor", "pointer");

          // Abbreviate long sector names for narrow spaces
          let label = d.data.name;
          if (sectorWidth < 120) {
            const abbrevMap: Record<string, string> = {
              "Information Technology": "IT",
              "Communication Services": "Comm",
              "Consumer Discretionary": "Cons Disc",
              "Consumer Staples": "Cons Stpl",
              "Health Care": "Health",
              "Financials": "Fin",
              "Industrials": "Ind",
              "Real Estate": "RE",
              "Materials": "Mat",
              "Utilities": "Util",
              "Energy": "Energy",
            };
            label = abbrevMap[label] ?? label.slice(0, 8);
          }

          if (sectorWidth > 30) {
            g.append("text")
              .attr("x", x0 + 4)
              .attr("y", y0 + 14)
              .text(label)
              .attr("fill", "#e2e8f0")
              .attr("font-size", "11px")
              .attr("font-weight", "600")
              .style("pointer-events", "none");
          }

          // Double-click to zoom into sector
          g.on("dblclick", (event) => {
            event.preventDefault();
            event.stopPropagation();
            setInternalFocusSector(d.data.name);
          });
        });
    }

    // Draw leaf cells (stocks)
    const leaves = root.leaves();

    const cellGroups = svg
      .selectAll("g.cell")
      .data(leaves)
      .join("g")
      .attr("class", "cell")
      .attr("transform", (d) => `translate(${d.x0},${d.y0})`);

    // Cell rectangle
    cellGroups
      .append("rect")
      .attr("width", (d) => Math.max(0, (d.x1 ?? 0) - (d.x0 ?? 0)))
      .attr("height", (d) => Math.max(0, (d.y1 ?? 0) - (d.y0 ?? 0)))
      .attr("fill", (d) => getChangeColor(d.data.change_pct ?? null))
      .attr("stroke", "#1e293b")
      .attr("stroke-width", 0.5)
      .attr("rx", 2)
      .style("cursor", "pointer")
      .on("mouseover", (event, d) => {
        d3.select(event.currentTarget)
          .attr("stroke", "#ffffff")
          .attr("stroke-width", 2);

        const stock = d.data;
        const changePct = stock.change_pct;
        const changeStr = changePct !== null && changePct !== undefined
          ? formatPercent(changePct)
          : "N/A";
        const priceStr = stock.price !== undefined ? formatCurrency(stock.price) : "N/A";
        const capStr = stock.market_cap ? formatNumber(stock.market_cap) : "N/A";
        const volStr = stock.volume ? Number(stock.volume).toLocaleString() : "N/A";

        tooltip
          .style("display", "block")
          .html(
            `<div class="font-bold text-sm">${stock.ticker ?? ""}</div>
             <div class="text-xs text-gray-300">${stock.stockName ?? ""}</div>
             <div class="text-xs mt-1">${stock.sector ?? ""}</div>
             <div class="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
               <span class="text-gray-400">Price</span><span>${priceStr}</span>
               <span class="text-gray-400">Change</span><span class="${(changePct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}">${changeStr}</span>
               <span class="text-gray-400">Mkt Cap</span><span>$${capStr}</span>
               <span class="text-gray-400">Volume</span><span>${volStr}</span>
             </div>`,
          );
      })
      .on("mousemove", (event) => {
        const containerRect = container.getBoundingClientRect();
        let left = event.clientX - containerRect.left + 12;
        let top = event.clientY - containerRect.top - 10;

        // Prevent tooltip from going out of bounds
        const tooltipEl = tooltipRef.current;
        if (tooltipEl) {
          const tw = tooltipEl.offsetWidth;
          const th = tooltipEl.offsetHeight;
          if (left + tw > width) left = left - tw - 24;
          if (top + th > height) top = top - th;
          if (top < 0) top = 4;
        }

        tooltip
          .style("left", `${left}px`)
          .style("top", `${top}px`);
      })
      .on("mouseout", (event) => {
        d3.select(event.currentTarget)
          .attr("stroke", "#1e293b")
          .attr("stroke-width", 0.5);
        tooltip.style("display", "none");
      })
      .on("click", (_event, d) => {
        if (d.data.ticker) {
          navigate(`/stock/${d.data.ticker}`);
        }
      })
      .on("dblclick", (event, d) => {
        event.preventDefault();
        event.stopPropagation();
        if (d.data.sector) {
          if (focusSector === d.data.sector) {
            setInternalFocusSector(null);
          } else {
            setInternalFocusSector(d.data.sector);
          }
        }
      });

    // Ticker text (shown when cell is large enough)
    cellGroups
      .append("text")
      .attr("x", 4)
      .attr("y", 14)
      .text((d) => d.data.ticker ?? "")
      .attr("fill", (d) => getTextColor(getChangeColor(d.data.change_pct ?? null)))
      .attr("font-size", "11px")
      .attr("font-weight", "700")
      .style("pointer-events", "none")
      .attr("display", (d) => {
        const w = (d.x1 ?? 0) - (d.x0 ?? 0);
        const h = (d.y1 ?? 0) - (d.y0 ?? 0);
        return w >= 40 && h >= 25 ? "block" : "none";
      });

    // Change percent text
    cellGroups
      .append("text")
      .attr("x", 4)
      .attr("y", 27)
      .text((d) => {
        const pct = d.data.change_pct;
        if (pct === null || pct === undefined) return "N/A";
        return formatPercent(pct);
      })
      .attr("fill", (d) => getTextColor(getChangeColor(d.data.change_pct ?? null)))
      .attr("font-size", "10px")
      .attr("font-weight", "400")
      .style("pointer-events", "none")
      .attr("display", (d) => {
        const w = (d.x1 ?? 0) - (d.x0 ?? 0);
        const h = (d.y1 ?? 0) - (d.y0 ?? 0);
        return w >= 40 && h >= 25 ? "block" : "none";
      });

    // Stock name text (shown when cell is large enough)
    cellGroups
      .append("text")
      .attr("x", 4)
      .attr("y", 40)
      .text((d) => {
        const name = d.data.stockName ?? "";
        const w = (d.x1 ?? 0) - (d.x0 ?? 0);
        if (w < 100) return name.length > 12 ? name.slice(0, 11) + "..." : name;
        return name.length > 22 ? name.slice(0, 21) + "..." : name;
      })
      .attr("fill", (d) => {
        const c = getTextColor(getChangeColor(d.data.change_pct ?? null));
        return c === "#ffffff" ? "rgba(255,255,255,0.7)" : "rgba(31,41,55,0.7)";
      })
      .attr("font-size", "9px")
      .attr("font-weight", "400")
      .style("pointer-events", "none")
      .attr("display", (d) => {
        const w = (d.x1 ?? 0) - (d.x0 ?? 0);
        const h = (d.y1 ?? 0) - (d.y0 ?? 0);
        return w > 80 && h > 40 ? "block" : "none";
      });

    // Company logos (shown on large cells)
    cellGroups
      .append("image")
      .attr("href", (d) =>
        `https://assets.parqet.com/logos/symbol/${d.data.ticker}`,
      )
      .attr("x", (d) => {
        const w = (d.x1 ?? 0) - (d.x0 ?? 0);
        const sz = w >= 140 && ((d.y1 ?? 0) - (d.y0 ?? 0)) >= 80 ? 28 : 20;
        return w - sz - 4;
      })
      .attr("y", 4)
      .attr("width", (d) => {
        const w = (d.x1 ?? 0) - (d.x0 ?? 0);
        const h = (d.y1 ?? 0) - (d.y0 ?? 0);
        return w >= 140 && h >= 80 ? 28 : 20;
      })
      .attr("height", (d) => {
        const w = (d.x1 ?? 0) - (d.x0 ?? 0);
        const h = (d.y1 ?? 0) - (d.y0 ?? 0);
        return w >= 140 && h >= 80 ? 28 : 20;
      })
      .attr("preserveAspectRatio", "xMidYMid meet")
      .style("pointer-events", "none")
      .style("border-radius", "4px")
      .attr("display", (d) => {
        const w = (d.x1 ?? 0) - (d.x0 ?? 0);
        const h = (d.y1 ?? 0) - (d.y0 ?? 0);
        return w >= 80 && h >= 50 ? "block" : "none";
      })
      .on("error", function () {
        d3.select(this).remove();
      });
  }, [data, focusSector, navigate]);

  // Render on data change and resize
  useEffect(() => {
    renderTreemap();

    const container = containerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver(() => {
      renderTreemap();
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, [renderTreemap]);

  if (isLoading) {
    return <Skeleton className="w-full h-full rounded-md" />;
  }

  return (
    <div ref={containerRef} className="relative w-full h-full select-none">
      {focusSector && (
        <button
          className="absolute top-1 left-1 z-20 bg-slate-800 text-white text-xs px-2 py-1 rounded hover:bg-slate-700 transition-colors"
          onClick={() => setInternalFocusSector(null)}
        >
          &larr; All Sectors
        </button>
      )}
      <svg ref={svgRef} className="w-full h-full" />
      <div
        ref={tooltipRef}
        className="absolute z-50 hidden bg-slate-900 text-white p-3 rounded-lg shadow-xl border border-slate-700 pointer-events-none min-w-[180px]"
        style={{ display: "none" }}
      />
    </div>
  );
};

export default Heatmap;
