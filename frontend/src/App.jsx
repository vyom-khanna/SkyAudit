// frontend/src/App.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/shared/Navbar';
import Home from './pages/Home';
import District from './pages/District';
import School from './pages/School';
import Pulse from './pages/Pulse';
import Rankings from './pages/Rankings';
import OfficerDashboard from './pages/OfficerDashboard';

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/district/:districtCode" element={<District />} />
        <Route path="/school/:udiseCode" element={<School />} />
        <Route path="/pulse" element={<Pulse />} />
        <Route path="/rankings" element={<Rankings />} />
        <Route path="/officer" element={<OfficerDashboard />} />
        <Route path="/login" element={<OfficerDashboard />} />
      </Routes>
    </BrowserRouter>
  );
}
