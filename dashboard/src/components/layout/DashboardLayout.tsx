import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Menu } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";

export function DashboardLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const userEmail = user?.email ?? "";
  const isAdmin = user?.is_admin ?? false;

  async function handleSignOut() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Skip link */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to main content
      </a>

      {/* Full sidebar (>=1280px) */}
      <div className="hidden xl:flex">
        <Sidebar
          collapsed={false}
          onSignOut={handleSignOut}
          userEmail={userEmail}
          isAdmin={isAdmin}
        />
      </div>

      {/* Collapsed sidebar (1024-1279px) */}
      <div className="hidden lg:flex xl:hidden">
        <Sidebar
          collapsed={true}
          onSignOut={handleSignOut}
          userEmail={userEmail}
          isAdmin={isAdmin}
        />
      </div>

      {/* Mobile sidebar drawer (<1024px) */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-60 p-0" onClose={() => setMobileOpen(false)}>
          <Sidebar
            collapsed={false}
            onSignOut={() => {
              setMobileOpen(false);
              handleSignOut();
            }}
            userEmail={userEmail}
            isAdmin={isAdmin}
          />
        </SheetContent>
      </Sheet>

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="flex h-14 items-center border-b border-border px-4 lg:hidden">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
          <span className="ml-3 text-lg font-bold text-foreground">
            TaoGateway
          </span>
        </header>

        <main
          id="main"
          className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8"
        >
          <div className="mx-auto max-w-[1200px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
