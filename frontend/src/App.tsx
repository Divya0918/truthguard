import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth';
import { RequireAuth } from './components/RequireAuth';
import LoginPage from './pages/Login';
import ChatPage from './pages/customer/Chat';
import AdminLayout from './layouts/AdminLayout';
import AdminDocuments from './pages/admin/Documents';
import AdminHistory from './pages/admin/ChatHistory';
import AdminResolution from './pages/admin/Resolution';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/login" replace />} />

          {/* Customer routes */}
          <Route element={<RequireAuth />}>
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:convId" element={<ChatPage />} />
          </Route>

          {/* Admin routes */}
          <Route element={<RequireAuth adminOnly />}>
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="/admin/documents" replace />} />
              <Route path="documents" element={<AdminDocuments />} />
              <Route path="history" element={<AdminHistory />} />
              <Route path="resolution" element={<AdminResolution />} />
            </Route>
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
