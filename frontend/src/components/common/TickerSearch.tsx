import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/useDebounce";
import { searchStocks } from "@/api/market";
import type { SearchResult } from "@/types";

interface TickerSearchProps {
  onSelect?: (ticker: string) => void;
  placeholder?: string;
  className?: string;
}

const TickerSearch = ({ onSelect, placeholder = "Search stocks...", className }: TickerSearchProps) => {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const debouncedQuery = useDebounce(query, 300);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: results = [] } = useQuery<SearchResult[]>({
    queryKey: ["searchStocks", debouncedQuery],
    queryFn: () => searchStocks(debouncedQuery),
    enabled: debouncedQuery.length >= 1,
    staleTime: 30_000,
  });

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (ticker: string) => {
    setQuery("");
    setIsOpen(false);
    if (onSelect) {
      onSelect(ticker);
    } else {
      navigate(`/stock/${ticker}`);
    }
  };

  return (
    <div ref={containerRef} className={`relative ${className ?? ""}`}>
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          className="pl-9 h-9"
        />
      </div>
      {isOpen && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-lg">
          <ul className="max-h-60 overflow-auto py-1">
            {results.map((result) => (
              <li key={result.ticker}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-accent"
                  onClick={() => handleSelect(result.ticker)}
                >
                  <span className="font-medium">{result.ticker}</span>
                  <span className="text-muted-foreground truncate ml-2">
                    {result.name}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default TickerSearch;
