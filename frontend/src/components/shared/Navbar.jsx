// frontend/src/components/shared/Navbar.jsx
import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Search, MapPin, Radio, BarChart2, Shield, Menu, X, LogIn } from 'lucide-react';

export default function Navbar() {
  const [searchVal, setSearchVal] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleSearch = (e) => {
    e.preventDefault();
    const val = searchVal.trim();
    if (!val) return;
    if (/^\d{11}$/.test(val)) {
      navigate(`/school/${val}`);
    } else {
      navigate(`/?search=${encodeURIComponent(val)}`);
    }
    setSearchVal('');
  };

  const isActive = (path) =>
    location.pathname === path ? 'text-blue-400 font-semibold' : 'text-gray-300 hover:text-white';

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-gray-900 border-b border-gray-700 shadow-lg">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Shield size={18} className="text-white" />
          </div>
          <span className="text-white font-bold text-lg tracking-tight hidden sm:block">
            School<span className="text-blue-400">Truth</span>
          </span>
        </Link>

        {/* Search bar */}
        <form onSubmit={handleSearch} className="flex-1 max-w-md hidden md:flex">
          <div className="relative w-full">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={searchVal}
              onChange={e => setSearchVal(e.target.value)}
              placeholder="Search school name or 11-digit UDISE code…"
              className="w-full bg-gray-800 border border-gray-600 rounded-lg pl-9 pr-4 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>
        </form>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-6 text-sm">
          <Link to="/" className={`flex items-center gap-1.5 ${isActive('/')}`}>
            <MapPin size={15} /> Map
          </Link>
          <Link to="/pulse" className={`flex items-center gap-1.5 ${isActive('/pulse')}`}>
            <Radio size={15} /> Pulse
          </Link>
          <Link to="/rankings" className={`flex items-center gap-1.5 ${isActive('/rankings')}`}>
            <BarChart2 size={15} /> Rankings
          </Link>
          <Link
            to="/officer"
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-sm transition-colors"
          >
            <LogIn size={15} /> Officer Login
          </Link>
        </div>

        {/* Mobile menu button */}
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="md:hidden text-gray-300 hover:text-white"
        >
          {menuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden bg-gray-900 border-t border-gray-700 px-4 py-3 space-y-3">
          <form onSubmit={handleSearch} className="flex">
            <div className="relative flex-1">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchVal}
                onChange={e => setSearchVal(e.target.value)}
                placeholder="UDISE code or school name…"
                className="w-full bg-gray-800 border border-gray-600 rounded-lg pl-9 pr-4 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </form>
          {[['/', 'Map'], ['/pulse', 'Pulse'], ['/rankings', 'Rankings'], ['/officer', 'Officer Login']].map(([path, label]) => (
            <Link key={path} to={path} onClick={() => setMenuOpen(false)}
              className={`block py-2 text-sm ${isActive(path)}`}>
              {label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}
