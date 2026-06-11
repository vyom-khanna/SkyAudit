import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getScoreColor } from '../../utils/scoreColors';

export default function IndiaMap({ onDistrictSelect }) {
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const geoLayerRef = useRef(null);      // holds the GeoJSON layer so we can remove/rebuild
  const geojsonCacheRef = useRef(null);  // cache the fetched GeoJSON so we don't re-fetch
  const navigate = useNavigate();
  const [districtData, setDistrictData] = useState({});
  const [mapReady, setMapReady] = useState(false);

  // Step 1: fetch district scores
  useEffect(() => {
    import('../../utils/api').then(({ districtsApi }) => {
      districtsApi.getRankings({ limit: 823 })
        .then(res => {
          const map = {};
          res.data.forEach(d => { map[d.district_code] = d; });
          setDistrictData(map);
        })
        .catch(() => {});
    });
  }, []);

  // Step 2: initialise Leaflet map (once only, no GeoJSON yet)
  useEffect(() => {
    if (!mapRef.current || leafletRef.current) return;

    if (!document.getElementById('leaflet-css')) {
      const link = document.createElement('link');
      link.id = 'leaflet-css';
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);
    }

    import('leaflet').then((L) => {
      const map = L.default.map(mapRef.current, {
        center: [22.5937, 78.9629],
        zoom: 5,
        zoomControl: true,
        attributionControl: false,
      });

      L.default.tileLayer(
        'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
        { maxZoom: 18 }
      ).addTo(map);

      leafletRef.current = map;
      setMapReady(true);
    });

    return () => {
      if (leafletRef.current) {
        leafletRef.current.remove();
        leafletRef.current = null;
      }
    };
  }, []);

  // Step 3: build (or rebuild) GeoJSON layer whenever map is ready OR districtData changes
  // This ensures tooltips always have the correct score when they're bound
  useEffect(() => {
    if (!mapReady || !leafletRef.current) return;

    const buildLayer = (L, geojson) => {
      // Remove previous layer if exists
      if (geoLayerRef.current) {
        geoLayerRef.current.remove();
        geoLayerRef.current = null;
      }

      const map = leafletRef.current;

      const geoLayer = L.geoJSON(geojson, {
        style: (feature) => {
          const code = feature.properties?.dt_code || feature.properties?.district_code;
          const district = districtData[code];
          const score = district?.accountability_score ?? 55;
          return {
            fillColor: getScoreColor(score),
            fillOpacity: 0.65,
            color: '#fff',
            weight: 0.7,
            opacity: 0.8,
          };
        },
        onEachFeature: (feature, layer) => {
          const code = feature.properties?.dt_code || feature.properties?.district_code;
          const name = feature.properties?.dtname || feature.properties?.district || 'District';
          const district = districtData[code];
          // Score is guaranteed to be set correctly now since districtData is loaded
          const score = district?.accountability_score != null
            ? district.accountability_score.toFixed(1)
            : '—';

          layer.bindTooltip(
            `<div style="font-weight:600;font-size:13px;">${name}</div>` +
            `<div style="font-size:12px;color:#555;">Score: <strong>${score}</strong>/100</div>`,
            {
              permanent: false,
              direction: 'top',
              className: 'leaflet-tooltip-custom',
              sticky: false,
            }
          );

          layer.on('click', () => {
            if (code) {
              navigate(`/district/${code}`);
              onDistrictSelect?.(code);
            }
          });

          layer.on('mouseover', function () {
            this.setStyle({ fillOpacity: 0.85, weight: 1.5 });
            this.openTooltip();
          });
          layer.on('mouseout', function () {
            this.setStyle({ fillOpacity: 0.65, weight: 0.7 });
            this.closeTooltip();
          });
        },
      });

      geoLayer.addTo(map);
      geoLayerRef.current = geoLayer;
    };

    import('leaflet').then((L) => {
      const Lx = L.default;

      if (geojsonCacheRef.current) {
        // GeoJSON already fetched — just rebuild with updated districtData
        buildLayer(Lx, geojsonCacheRef.current);
        return;
      }

      // First time: fetch GeoJSON then build
      fetch('https://raw.githubusercontent.com/geohacker/india/master/district/india_district.geojson')
        .then(r => r.json())
        .then(geojson => {
          geojsonCacheRef.current = geojson;
          buildLayer(Lx, geojson);
        })
        .catch(() => {
          // Fallback tile layer if GeoJSON fetch fails
          Lx.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(leafletRef.current);
        });
    });
  }, [mapReady, districtData]); // re-runs when districtData loads → tooltips get real scores

  return <div ref={mapRef} className="w-full h-full" />;
}
