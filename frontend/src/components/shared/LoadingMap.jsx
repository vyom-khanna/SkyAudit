export function LoadingMap() {
  return (
    <div className="w-full h-full flex items-center justify-center bg-gray-800">
      <div className="flex flex-col items-center gap-3">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-400 text-sm">Loading map data…</p>
      </div>
    </div>
  );
}
