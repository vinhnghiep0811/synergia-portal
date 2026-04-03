import "./App.css";
import { Route, Routes } from "react-router-dom";
import { HomeDashboard } from "./pages/HomeDashboard.jsx";
import { UploadPage } from "./pages/UploadPage.jsx";
import { PaperDashboard } from "./pages/PaperDashboard.jsx";
import { PaperDetailPage } from "./pages/PaperDetailPage.jsx";
import { CanonicalDocumentsPage } from "./pages/CanonicalDocumentsPage.jsx";
import { CanonicalDocumentDetailPage } from "./pages/CanonicalDocumentDetailPage.jsx";
import { ExtractionRunDetailPage } from "./pages/ExtractionRunDetailPage.jsx";
import { LoginPage } from "./pages/LoginPage.jsx";
import { AuthCallbackPage } from "./pages/AuthCallbackPage.jsx";
import { ProtectedRoute } from "./components/ProtectedRoute.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<HomeDashboard />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/papers" element={<PaperDashboard />} />
        <Route path="/papers/:paperId" element={<PaperDetailPage />} />
        <Route path="/canonical" element={<CanonicalDocumentsPage />} />
        <Route path="/canonical/:canonicalId" element={<CanonicalDocumentDetailPage />} />
        <Route path="/extraction-runs/:runId" element={<ExtractionRunDetailPage />} />
      </Route>
    </Routes>
  );
}