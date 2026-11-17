import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function RequireAuth({ adminOnly = false }: { adminOnly?: boolean }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="flex gap-2">
          <div className="typing-dot w-3 h-3 rounded-full bg-teal-500" />
          <div className="typing-dot w-3 h-3 rounded-full bg-teal-500" />
          <div className="typing-dot w-3 h-3 rounded-full bg-teal-500" />
        </div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== 'admin') return <Navigate to="/chat" replace />;

  return <Outlet />;
}
