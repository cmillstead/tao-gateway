import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/hooks/useAuth";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { AdminRoute } from "@/components/auth/AdminRoute";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Login } from "@/pages/Login";
import { Signup } from "@/pages/Signup";
import { Dashboard } from "@/pages/Dashboard";
import { ApiKeys } from "@/pages/ApiKeys";
import { Usage } from "@/pages/Usage";
import { SettingsPage } from "@/pages/SettingsPage";
import { Admin } from "@/pages/Admin";
import { AdminMetagraph } from "@/pages/AdminMetagraph";
import { AdminDevelopers } from "@/pages/AdminDevelopers";
import { AdminMiners } from "@/pages/AdminMiners";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />

            {/* Redirect root to dashboard */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />

            {/* Protected dashboard routes */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="api-keys" element={<ApiKeys />} />
              <Route path="usage" element={<Usage />} />
              <Route path="settings" element={<SettingsPage />} />

              {/* Admin routes */}
              <Route path="admin" element={<AdminRoute><Admin /></AdminRoute>} />
              <Route path="admin/metagraph" element={<AdminRoute><AdminMetagraph /></AdminRoute>} />
              <Route path="admin/developers" element={<AdminRoute><AdminDevelopers /></AdminRoute>} />
              <Route path="admin/miners" element={<AdminRoute><AdminMiners /></AdminRoute>} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
