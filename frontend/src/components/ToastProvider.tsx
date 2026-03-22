import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

interface Toast { id: number; message: string; type: 'success' | 'error' | 'info'; }

interface ToastCtx { toast: (msg: string, type?: Toast['type']) => void; }

const Ctx = createContext<ToastCtx>({ toast: () => {} });

export const useToast = () => useContext(Ctx);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);

  const toast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = ++counter.current;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500);
  }, []);

  const icon = (type: Toast['type']) =>
    type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type}`}>
            <span>{icon(t.type)}</span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
};
