import { useState, useRef } from 'react';

export function SatelliteViewer({ beforeUrl, afterUrl, beforeLabel = 'Before', afterLabel = 'After' }) {
  const [sliderPos, setSliderPos] = useState(50);
  const containerRef = useRef(null);
  const dragging = useRef(false);

  const handleMouseMove = (e) => {
    if (!dragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = (e.clientX ?? e.touches?.[0]?.clientX) - rect.left;
    setSliderPos(Math.max(5, Math.min(95, (x / rect.width) * 100)));
  };

  if (!beforeUrl && !afterUrl) {
    return (
      <div className="w-full h-48 bg-gray-100 rounded-lg flex items-center justify-center text-gray-400 text-sm">
        No satellite imagery available
      </div>
    );
  }

  if (!beforeUrl || !afterUrl) {
    const url = beforeUrl || afterUrl;
    const label = beforeUrl ? beforeLabel : afterLabel;
    return (
      <div className="relative w-full h-48 rounded-lg overflow-hidden">
        <img src={url} alt={label} className="w-full h-full object-cover" />
        <div className="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">{label}</div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative w-full h-48 rounded-lg overflow-hidden select-none cursor-col-resize"
      onMouseMove={handleMouseMove}
      onMouseDown={() => { dragging.current = true; }}
      onMouseUp={() => { dragging.current = false; }}
      onMouseLeave={() => { dragging.current = false; }}
      onTouchMove={handleMouseMove}
      onTouchStart={() => { dragging.current = true; }}
      onTouchEnd={() => { dragging.current = false; }}
    >
      {/* After image (full) */}
      <img src={afterUrl} alt={afterLabel} className="absolute inset-0 w-full h-full object-cover" />

      {/* Before image (clipped) */}
      <div className="absolute inset-0 overflow-hidden" style={{ width: `${sliderPos}%` }}>
        <img src={beforeUrl} alt={beforeLabel} className="w-full h-full object-cover" style={{ width: `${10000 / sliderPos}%` }} />
      </div>

      {/* Slider line */}
      <div className="absolute top-0 bottom-0 w-0.5 bg-white shadow-lg" style={{ left: `${sliderPos}%` }}>
        <div className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-6 bg-white rounded-full shadow-lg flex items-center justify-center">
          <div className="w-3 h-3 border-2 border-gray-400 rounded-full" />
        </div>
      </div>

      {/* Labels */}
      <div className="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">{beforeLabel}</div>
      <div className="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">{afterLabel}</div>
    </div>
  );
}
