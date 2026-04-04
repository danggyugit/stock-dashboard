import { useMemo } from "react";
import { formatCurrency } from "@/lib/utils";
import type { DividendEvent } from "@/types";

interface DividendCalendarProps {
  events: DividendEvent[];
  month: number; // 1-12
  year: number;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const DividendCalendar = ({ events, month, year }: DividendCalendarProps) => {
  const { days, startDay, daysInMonth } = useMemo(() => {
    const firstDay = new Date(year, month - 1, 1);
    const startDay = firstDay.getDay();
    const daysInMonth = new Date(year, month, 0).getDate();
    const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
    return { days, startDay, daysInMonth };
  }, [month, year]);

  const eventsByDay = useMemo(() => {
    const map = new Map<number, DividendEvent[]>();
    for (const event of events) {
      const d = new Date(event.ex_date);
      if (d.getFullYear() === year && d.getMonth() + 1 === month) {
        const day = d.getDate();
        if (!map.has(day)) map.set(day, []);
        map.get(day)!.push(event);
      }
    }
    return map;
  }, [events, month, year]);

  const totalWeeks = Math.ceil((startDay + daysInMonth) / 7);

  return (
    <div className="w-full">
      {/* Weekday headers */}
      <div className="grid grid-cols-7 gap-px mb-1">
        {WEEKDAYS.map((day) => (
          <div
            key={day}
            className="text-center text-xs font-medium text-muted-foreground py-1"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-px">
        {/* Empty cells before first day */}
        {Array.from({ length: startDay }).map((_, i) => (
          <div key={`empty-${i}`} className="min-h-[60px] p-1 bg-muted/20 rounded-sm" />
        ))}

        {/* Day cells */}
        {days.map((day) => {
          const dayEvents = eventsByDay.get(day);
          const hasEvents = dayEvents && dayEvents.length > 0;
          return (
            <div
              key={day}
              className={`min-h-[60px] p-1 rounded-sm border text-xs ${
                hasEvents
                  ? "bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800"
                  : "bg-background border-border/50"
              }`}
            >
              <span className="text-[10px] text-muted-foreground">{day}</span>
              {dayEvents?.map((ev, idx) => (
                <div
                  key={`${ev.ticker}-${idx}`}
                  className="mt-0.5 px-1 py-0.5 rounded bg-green-100 dark:bg-green-900/50 text-[10px] font-medium text-green-800 dark:text-green-300 truncate"
                  title={`${ev.ticker}: ${formatCurrency(ev.total_amount)}`}
                >
                  {ev.ticker} {formatCurrency(ev.total_amount)}
                </div>
              ))}
            </div>
          );
        })}

        {/* Empty cells after last day to fill row */}
        {Array.from({
          length: totalWeeks * 7 - (startDay + daysInMonth),
        }).map((_, i) => (
          <div key={`end-${i}`} className="min-h-[60px] p-1 bg-muted/20 rounded-sm" />
        ))}
      </div>
    </div>
  );
};

export default DividendCalendar;
