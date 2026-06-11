import { useState, useEffect, useCallback, useRef } from 'react';
import { anomaliesApi } from '../utils/api';

export function useAnomaly(anomalyId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!anomalyId) return;
    setLoading(true);
    anomaliesApi.getOne(anomalyId)
      .then(res => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [anomalyId]);

  return { data, loading };
}

export function useAnomalies(filters = {}) {
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(false);
  // Keep filters in a ref so refetch always uses the latest value
  // without needing to be re-created on every render
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const fetchAnomalies = useCallback(() => {
    setLoading(true);
    anomaliesApi.getAll(filtersRef.current)
      .then(res => setAnomalies(res.data))
      .catch(() => setAnomalies([]))
      .finally(() => setLoading(false));
  }, []); // stable — never changes

  useEffect(() => {
    fetchAnomalies();
  }, [JSON.stringify(filters)]); // re-fetch when filters actually change

  // Optimistic update: immediately apply the status change in local state
  // so the UI reflects it instantly without waiting for the re-fetch
  const updateLocalAnomaly = useCallback((anomalyId, newStatus) => {
    setAnomalies(prev =>
      prev.map(a => a.id === anomalyId ? { ...a, status: newStatus } : a)
    );
  }, []);

  return { anomalies, loading, refetch: fetchAnomalies, updateLocalAnomaly };
}
