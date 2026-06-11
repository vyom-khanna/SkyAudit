import { useRef } from 'react';
import { AnomalyCard } from './AnomalyCard';
import { usePulse } from '../../hooks/usePulse';

export function PulseFeed({ filters = {} }) {
  const { events, loading, newEventIds, pauseScroll, resumeScroll } = usePulse(filters);

  return (
    <div
      className="space-y-3 overflow-y-auto pr-1"
      onMouseEnter={pauseScroll}
      onMouseLeave={resumeScroll}
      style={{ maxHeight: 'calc(100vh - 200px)' }}
    >
      {loading && events.length === 0 ? (
        Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-36 bg-gray-100 rounded-xl animate-pulse" />
        ))
      ) : events.length === 0 ? (
        <div className="text-center text-gray-400 py-16 text-sm">No pulse events found</div>
      ) : (
        events.map(ev => (
          <AnomalyCard
            key={ev.id}
            event={ev}
            isNew={newEventIds.has(ev.id)}
          />
        ))
      )}
    </div>
  );
}
