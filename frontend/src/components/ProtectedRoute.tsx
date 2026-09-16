import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Loading } from "./ui";

interface Props {
  children: React.ReactNode;
  requireStaff?: boolean;
  requireAdmin?: boolean;
}

export function ProtectedRoute({ children, requireStaff, requireAdmin }: Props) {
  const { principal, loading } = useAuth();
  const location = useLocation();

  if (loading) return <Loading label="校验登录状态…" />;
  if (!principal) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (requireStaff && !principal.is_staff)
    return <Navigate to="/tickets" replace />;
  if (requireAdmin && principal.role !== "ADMIN")
    return <Navigate to="/console/queue" replace />;

  return <>{children}</>;
}
