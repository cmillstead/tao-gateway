import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Key,
  BarChart3,
  Settings,
  ExternalLink,
  LogOut,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

interface SidebarProps {
  collapsed: boolean;
  onSignOut: () => void | Promise<void>;
  userEmail: string;
}

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Overview" },
  { to: "/dashboard/api-keys", icon: Key, label: "API Keys" },
  { to: "/dashboard/usage", icon: BarChart3, label: "Usage" },
];

export function Sidebar({ collapsed, onSignOut, userEmail }: SidebarProps) {
  return (
    <nav
      aria-label="Main navigation"
      className={cn(
        "flex h-full flex-col border-r border-border bg-surface",
        collapsed ? "w-16" : "w-60",
      )}
    >
      {/* Logo / Brand */}
      <div className={cn("flex h-14 items-center border-b border-border px-4", collapsed && "justify-center")}>
        {collapsed ? (
          <span className="text-lg font-bold text-primary">T</span>
        ) : (
          <span className="text-lg font-bold text-foreground">TaoGateway</span>
        )}
      </div>

      {/* Main nav links */}
      <div className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="flex flex-col gap-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === "/dashboard"}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    collapsed && "justify-center px-2",
                    isActive
                      ? "bg-primary/5 text-primary"
                      : "text-muted-foreground hover:bg-elevated hover:text-foreground",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span>{label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>

        <Separator className="my-3" />

        {/* Settings */}
        <ul className="flex flex-col gap-1">
          <li>
            <NavLink
              to="/dashboard/settings"
              title={collapsed ? "Settings" : undefined}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  collapsed && "justify-center px-2",
                  isActive
                    ? "bg-primary/5 text-primary"
                    : "text-muted-foreground hover:bg-elevated hover:text-foreground",
                )
              }
            >
              <Settings className="h-4 w-4 shrink-0" />
              {!collapsed && <span>Settings</span>}
            </NavLink>
          </li>
        </ul>

        <Separator className="my-3" />

        {/* Docs - external link */}
        <ul className="flex flex-col gap-1">
          <li>
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              title={collapsed ? "Docs" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-elevated hover:text-foreground",
                collapsed && "justify-center px-2",
              )}
            >
              <ExternalLink className="h-4 w-4 shrink-0" />
              {!collapsed && <span>Docs</span>}
            </a>
          </li>
        </ul>
      </div>

      {/* User section at bottom */}
      <div className="border-t border-border px-2 py-3">
        {!collapsed && (
          <p
            className="truncate px-3 pb-2 text-xs text-muted-foreground"
            title={userEmail}
          >
            {userEmail}
          </p>
        )}
        <button
          onClick={onSignOut}
          title={collapsed ? "Sign out" : undefined}
          className={cn(
            "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-elevated hover:text-foreground",
            collapsed && "justify-center px-2",
          )}
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </nav>
  );
}
