import { useState, useEffect } from 'react';
import { districtsApi } from '../utils/api';

export function useDistrict(districtCode) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!districtCode) return;
    setLoading(true);
    setError(null);
    districtsApi.getProfile(districtCode)
      .then(res => setData(res.data))
      .catch(err => setError(err.response?.data?.detail || 'Failed to load district'))
      .finally(() => setLoading(false));
  }, [districtCode]);

  return { data, loading, error };
}

export function useDistrictSchools(districtCode, filters = {}) {
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!districtCode) return;
    setLoading(true);
    districtsApi.getSchools(districtCode, filters)
      .then(res => setSchools(res.data))
      .catch(() => setSchools([]))
      .finally(() => setLoading(false));
  }, [districtCode, JSON.stringify(filters)]);

  return { schools, loading };
}

export function useDistrictRankings(params = {}) {
  const [rankings, setRankings] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    districtsApi.getRankings(params)
      .then(res => setRankings(res.data))
      .catch(() => setRankings([]))
      .finally(() => setLoading(false));
  }, [JSON.stringify(params)]);

  return { rankings, loading };
}
