import "./App.css";
import { Route, Routes } from "react-router-dom";
import { HomeDashboard } from "./pages/HomeDashboard.jsx";
import { UploadPage } from "./pages/UploadPage.jsx";
import { PaperDashboard } from "./pages/PaperDashboard.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeDashboard />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/papers" element={<PaperDashboard />} />
      <Route path="/papers/:paperId" element={<PaperDashboard />} />
    </Routes>
  );
}