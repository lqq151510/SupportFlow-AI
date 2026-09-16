import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ConsoleLayout } from "@/components/ConsoleLayout";

import Login from "@/pages/Login";
import TicketList from "@/pages/user/TicketList";
import TicketNew from "@/pages/user/TicketNew";
import TicketDetailUser from "@/pages/user/TicketDetail";
import Queue from "@/pages/console/Queue";
import TicketDetailConsole from "@/pages/console/TicketDetail";
import Approvals from "@/pages/console/Approvals";
import RunDetail from "@/pages/console/RunDetail";
import Knowledge from "@/pages/console/Knowledge";
import Evaluations from "@/pages/console/Evaluations";
import SettingsModels from "@/pages/console/SettingsModels";
import SettingsMembers from "@/pages/console/SettingsMembers";

function IndexRedirect() {
  const { principal, loading } = useAuth();
  if (loading) return <div />;
  if (!principal) return <Navigate to="/login" replace />;
  return <Navigate to={principal.is_staff ? "/console/queue" : "/tickets"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<IndexRedirect />} />
      <Route path="/login" element={<Login />} />

      {/* 用户侧（任意登录用户可访问） */}
      <Route
        path="/tickets"
        element={
          <ProtectedRoute>
            <TicketList />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tickets/new"
        element={
          <ProtectedRoute>
            <TicketNew />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tickets/:id"
        element={
          <ProtectedRoute>
            <TicketDetailUser />
          </ProtectedRoute>
        }
      />

      {/* 坐席 / 管理员侧 */}
      <Route
        path="/console"
        element={
          <ProtectedRoute requireStaff>
            <ConsoleLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/console/queue" replace />} />
        <Route path="queue" element={<Queue />} />
        <Route path="tickets/:id" element={<TicketDetailConsole />} />
        <Route path="approvals" element={<Approvals />} />
        <Route path="runs/:id" element={<RunDetail />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="evaluations" element={<Evaluations />} />
        <Route path="settings/models" element={<SettingsModels />} />
        <Route
          path="settings/members"
          element={
            <ProtectedRoute requireAdmin>
              <SettingsMembers />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
