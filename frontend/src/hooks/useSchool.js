// frontend/src/hooks/useSchool.js
import { useState, useEffect } from 'react';
import { schoolsApi } from '../utils/api';

export function useSchool(udiseCode) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!udiseCode) return;
    setLoading(true);
    setError(null);
    schoolsApi.getProfile(udiseCode)
      .then(res => setData(res.data))
      .catch(err => setError(err.response?.data?.detail || 'Failed to load school'))
      .finally(() => setLoading(false));
  }, [udiseCode]);

  return { data, loading, error };
}

export function useSchoolSatellite(udiseCode) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!udiseCode) return;
    setLoading(true);
    schoolsApi.getSatellite(udiseCode)
      .then(res => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [udiseCode]);

  return { data, loading };
}
