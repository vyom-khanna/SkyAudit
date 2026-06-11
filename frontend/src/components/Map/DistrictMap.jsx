import { useEffect, useRef } from 'react';
import { pinColor } from '../../utils/mapUtils';

export default function DistrictMap({ schools = [], onSchoolSelect, selectedUdise }) {
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const markersRef = useRef({});

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
      const Lx = L.default;

      // Center on schools
      const lats = schools.filter(s => s.latitude).map(s => s.latitude);
      const lngs = schools.filter(s => s.longitude).map(s => s.longitude);
      const center = lats.length
        ? [lats.reduce((a, b) => a + b) / lats.length, lngs.reduce((a, b) => a + b) / lngs.length]
        : [27.5, 80.5];

      const map = Lx.map(mapRef.current, {
        center,
        zoom: 10,
        zoomControl: true,
        attributionControl: false,
      });

      Lx.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 18,
      }).addTo(map);

      leafletRef.current = map;
      _addMarkers(Lx, map, schools, onSchoolSelect, markersRef);
    });

    return () => {
      if (leafletRef.current) { leafletRef.current.remove(); leafletRef.current = null; }
    };
  }, []);

  // Update markers when schools change
  useEffect(() => {
    if (!leafletRef.current || !schools.length) return;
    import('leaflet').then((L) => {
      Object.values(markersRef.current).forEach(m => m.remove());
      markersRef.current = {};
      _addMarkers(L.default, leafletRef.current, schools, onSchoolSelect, markersRef);
    });
  }, [schools]);

  // Highlight selected marker
  useEffect(() => {
    if (!selectedUdise || !markersRef.current[selectedUdise]) return;
    const marker = markersRef.current[selectedUdise];
    marker.openPopup?.();
  }, [selectedUdise]);

  return <div ref={mapRef} className="w-full h-full rounded-xl overflow-hidden" />;
}

function _addMarkers(L, map, schools, onSchoolSelect, markersRef) {
  schools.forEach(school => {
    if (!school.latitude || !school.longitude) return;

    const color = pinColor(school);
    const icon = L.divIcon({
      className: '',
      html: `<div style="
        width:12px; height:12px; border-radius:50%;
        background:${color}; border:2px solid white;
        box-shadow:0 1px 4px rgba(0,0,0,0.4);
        cursor:pointer;
      "></div>`,
      iconSize: [12, 12],
      iconAnchor: [6, 6],
    });

    const marker = L.marker([school.latitude, school.longitude], { icon });
    marker.bindTooltip(
      `<div class="font-semibold text-sm">${school.name}</div>
       <div class="text-xs text-gray-500">${school.udise_code}</div>`,
      { direction: 'top', offset: [0, -8] }
    );
    marker.on('click', () => onSchoolSelect?.(school));
    marker.addTo(map);
    markersRef.current[school.udise_code] = marker;
  });
}
