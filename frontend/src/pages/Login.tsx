import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Lock, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        if (!fullName.trim()) { setError('Full name is required'); setLoading(false); return; }
        await register(email, fullName, password);
      }
      // Navigate based on role stored in localStorage
      const saved = localStorage.getItem('tg_user');
      if (saved) {
        const u = JSON.parse(saved);
        navigate(u.role === 'admin' ? '/admin/documents' : '/chat', { replace: true });
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-teal-700 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white/10 backdrop-blur mb-4">
            <Shield className="w-8 h-8 text-teal-400" />
          </div>
          <h1 className="text-3xl font-bold text-white">TruthGuard</h1>
          <p className="text-teal-200 mt-1 text-sm">Multi-Agent Banking Intelligence System</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          {/* Tab Switch */}
          <div className="flex rounded-lg bg-gray-100 p-1 mb-6">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(''); }}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                  mode === m ? 'bg-white shadow text-navy-900' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {m === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Your full name"
                  className="input-field"
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="input-field"
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input-field pr-10"
                  required
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary justify-center py-2.5 text-base"
            >
              {loading ? (
                <span className="flex gap-1.5">
                  <span className="typing-dot w-2 h-2 rounded-full bg-white" />
                  <span className="typing-dot w-2 h-2 rounded-full bg-white" />
                  <span className="typing-dot w-2 h-2 rounded-full bg-white" />
                </span>
              ) : mode === 'login' ? (
                <><Lock className="w-4 h-4" /> Sign In</>
              ) : (
                'Create Account'
              )}
            </button>
          </form>

          {/* Demo creds hint */}
          <div className="mt-6 pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-500 text-center font-medium mb-2">Click to Quick-Fill Demo Credentials</p>
            <div className="space-y-2 text-xs">
              <button
                type="button"
                onClick={() => { setEmail('admin@demo.com'); setPassword('Admin@123456'); setMode('login'); setError(''); }}
                className="w-full flex justify-between items-center bg-gray-50 hover:bg-teal-50 hover:border-teal-300 border border-gray-200 rounded-lg px-3 py-2 transition-all cursor-pointer text-left group"
                title="Click to auto-fill Admin credentials"
              >
                <span className="font-semibold text-navy-800 group-hover:text-teal-700">Admin:</span>
                <span className="font-mono text-gray-600">admin@demo.com / Admin@123456</span>
              </button>
              <button
                type="button"
                onClick={() => { setEmail('customer@demo.com'); setPassword('Customer@123'); setMode('login'); setError(''); }}
                className="w-full flex justify-between items-center bg-gray-50 hover:bg-teal-50 hover:border-teal-300 border border-gray-200 rounded-lg px-3 py-2 transition-all cursor-pointer text-left group"
                title="Click to auto-fill Customer credentials"
              >
                <span className="font-semibold text-teal-700">Customer:</span>
                <span className="font-mono text-gray-600">customer@demo.com / Customer@123</span>
              </button>
            </div>
          </div>
        </div>

        <p className="text-center text-teal-200/60 text-xs mt-6">
          ⚠ Synthetic demo data only — not a real banking service
        </p>
      </div>
    </div>
  );
}
