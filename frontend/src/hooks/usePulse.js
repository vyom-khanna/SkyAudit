import { useState, useEffect, useRef, useCallback } from 'react';
import { pulseApi } from '../utils/api';

export function usePulse(filters = {}) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [newEventIds, setNewEventIds] = useState(new Set());
  const esRef = useRef(null);
  const pausedRef = useRef(false);

  // Initial load
  useEffect(() => {
    setLoading(true);
    pulseApi.getEvents({ limit: 50, ...filters })
      .then(res => setEvents(res.data))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [JSON.stringify(filters)]);

  // SSE stream for live updates
  useEffect(() => {
    const url = pulseApi.streamUrl(filters);
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'heartbeat' || data.type === 'connected') return;
        if (pausedRef.current) return;

        setEvents(prev => {
          const exists = prev.find(ev => ev.id === data.id);
          if (exists) return prev;
          setNewEventIds(ids => new Set([...ids, data.id]));
          setTimeout(() => setNewEventIds(ids => { const n = new Set(ids); n.delete(data.id); return n; }), 3000);
          return [data, ...prev].slice(0, 100);
        });
      } catch (_) {}
    };

    es.onerror = () => es.close();

    return () => es.close();
  }, [JSON.stringify(filters)]);

  const pauseScroll = useCallback(() => { pausedRef.current = true; }, []);
  const resumeScroll = useCallback(() => { pausedRef.current = false; }, []);

  return { events, loading, newEventIds, pauseScroll, resumeScroll };
}
