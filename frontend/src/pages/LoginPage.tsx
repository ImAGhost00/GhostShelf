import React, { useState } from 'react';
import { useToast } from '@/components/ToastProvider';
import { useNavigate } from 'react-router-dom';

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!username.trim() || !password) {
      toast('Please enter your username and password', 'error');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      
      if (!res.ok) {
        const error = await res.text();
        throw new Error(error || 'Login failed');
      }

      const data = await res.json();
      
      // Store access token in localStorage
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      
      toast('Logged in successfully', 'success');
      navigate('/');
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Login failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center', 
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    }}>
      <div style={{
        background: 'white',
        padding: '2rem',
        borderRadius: '8px',
        boxShadow: '0 10px 25px rgba(0, 0, 0, 0.2)',
        maxWidth: '400px',
        width: '100%',
      }}>
        <h1 style={{ textAlign: 'center', marginBottom: '1.5rem', color: '#333' }}>
          🎞️ GhostShelf
        </h1>
        
        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#555' }}>
              Username
            </label>
            <input
              type="text"
              placeholder="Enter the username you already use"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              style={{
                width: '100%',
                padding: '0.75rem',
                border: '2px solid #ddd',
                borderRadius: '4px',
                fontSize: '1rem',
                boxSizing: 'border-box',
              }}
            />
            <small style={{ color: '#999', marginTop: '0.5rem', display: 'block' }}>
              Use the same credentials you created through Wizarr.
            </small>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#555' }}>
              Password
            </label>
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              style={{
                width: '100%',
                padding: '0.75rem',
                border: '2px solid #ddd',
                borderRadius: '4px',
                fontSize: '1rem',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '0.75rem',
              background: loading ? '#ccc' : '#667eea',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              fontSize: '1rem',
              fontWeight: 'bold',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'background 0.3s',
            }}
            onMouseEnter={(e) => {
              if (!loading) (e.target as HTMLButtonElement).style.background = '#764ba2';
            }}
            onMouseLeave={(e) => {
              if (!loading) (e.target as HTMLButtonElement).style.background = '#667eea';
            }}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
