import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Portfolio } from "@/types";

interface PortfolioMultiSelectProps {
  portfolios: Portfolio[];
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
}

const PortfolioMultiSelect = ({
  portfolios,
  selectedIds,
  onSelectionChange,
}: PortfolioMultiSelectProps) => {
  const [open, setOpen] = useState(false);
  const allSelected = selectedIds.length === portfolios.length;

  const toggleId = (id: number) => {
    onSelectionChange(
      selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id],
    );
  };

  const toggleAll = () => {
    onSelectionChange(allSelected ? [] : portfolios.map((p) => p.id));
  };

  const label = allSelected
    ? "All Portfolios"
    : selectedIds.length === 0
      ? "Select..."
      : selectedIds.length === 1
        ? portfolios.find((p) => p.id === selectedIds[0])?.name ?? "1 selected"
        : `${selectedIds.length} selected`;

  return (
    <div className="relative">
      <Button
        variant="outline"
        size="sm"
        className="h-8 text-xs gap-1 min-w-[140px]"
        onClick={() => setOpen((v) => !v)}
      >
        {label}
        <ChevronsUpDown className="h-3 w-3" />
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-9 left-0 z-50 w-52 rounded-md border bg-popover shadow-md py-1">
            <button
              className="flex items-center gap-2 w-full px-3 py-1.5 text-xs hover:bg-accent"
              onClick={toggleAll}
            >
              <div
                className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center ${allSelected ? "bg-primary border-primary" : "border-input"}`}
              >
                {allSelected && <Check className="h-2.5 w-2.5 text-primary-foreground" />}
              </div>
              <span className="font-medium">Select All</span>
            </button>
            <div className="h-px bg-border my-1" />
            {portfolios.map((p) => {
              const checked = selectedIds.includes(p.id);
              return (
                <button
                  key={p.id}
                  className="flex items-center gap-2 w-full px-3 py-1.5 text-xs hover:bg-accent"
                  onClick={() => toggleId(p.id)}
                >
                  <div
                    className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center ${checked ? "bg-primary border-primary" : "border-input"}`}
                  >
                    {checked && <Check className="h-2.5 w-2.5 text-primary-foreground" />}
                  </div>
                  <span>{p.name}</span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};

export default PortfolioMultiSelect;
