import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../services/apiClient";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  const checkSession = useCallback(async () => {
    try {
      const res = await apiClient.get("/api/auth/me");
      setUser(res.data);
      return res.data;
    } catch (err) {
      setUser(null);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      // Đảm bảo URL đồng nhất /api/auth/logout
      await apiClient.post("/api/auth/logout");
    } finally {
      setUser(null);
      setIsLoading(false);
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  useEffect(() => {
    let isMounted = true;
    
    apiClient.get("/api/auth/me")
      .then((res) => {
        if (isMounted) setUser(res.data);
      })
      .catch(() => {
        if (isMounted) setUser(null);
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => { isMounted = false; };
  }, []);
  
  const value = useMemo(
    () => ({
      user,
      setUser,
      logout,
      isLoading,
      checkSession
    }),
    [user, logout, isLoading, checkSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
