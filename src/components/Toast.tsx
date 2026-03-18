"use client";

import { useState, useCallback, useEffect, createContext, useContext } from "react";

interface ToastMessage {
  id: number;
  text: string;
  type: "success" | "error" | "info";
}

interface ToastContextType {
  toast: (text: string, type?: "success" | "error" | "info") => void;
}

const ToastContext = createContext<ToastContextType>({ toast: () => {} });

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([]);

  const toast = useCallback((text: string, type: "success" | "error" | "info" = "info") => {
    const id = ++nextId;
    setMessages((prev) => [...prev, { id, text, type }]);
    setTimeout(() => {
      setMessages((prev) => prev.filter((m) => m.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[9999] space-y-2">
        {messages.map((msg) => (
          <ToastItem key={msg.id} message={msg} onClose={() => setMessages((prev) => prev.filter((m) => m.id !== msg.id))} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ message, onClose }: { message: ToastMessage; onClose: () => void }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => { setVisible(true); }, []);

  const colors = {
    success: "bg-green-50 border-green-200 text-green-800",
    error: "bg-red-50 border-red-200 text-red-800",
    info: "bg-blue-50 border-blue-200 text-blue-800",
  };

  return (
    <div
      className={`px-4 py-3 rounded-lg border shadow-lg text-sm font-medium transition-all duration-300 ${
        colors[message.type]
      } ${visible ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"}`}
    >
      <div className="flex items-center gap-2">
        <span>{message.text}</span>
        <button onClick={onClose} className="ml-2 text-current opacity-50 hover:opacity-100">&times;</button>
      </div>
    </div>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
