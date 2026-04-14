import { Link, useLocation } from "wouter";
import { Activity, LayoutDashboard, Settings, History, ShieldAlert } from "lucide-react";
import { useHealthCheck, getHealthCheckQueryKey } from "@workspace/api-client-react";

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const [location] = useLocation();
  const { data: health, isLoading, isError } = useHealthCheck({ query: { refetchInterval: 10000, queryKey: getHealthCheckQueryKey() } });

  const navigation = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Trade History", href: "/trades", icon: History },
    { name: "Configuration", href: "/config", icon: Settings },
  ];

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-50 flex h-14 items-center gap-4 border-b bg-card px-6">
        <div className="flex items-center gap-2 font-bold text-primary tracking-tight">
          <Activity className="h-5 w-5" />
          <span>TRADE_OPS</span>
        </div>
        
        <div className="ml-auto flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs font-medium">
            <span className="text-muted-foreground">SERVER STATUS</span>
            {isLoading ? (
              <span className="flex h-2 w-2 rounded-full bg-muted animate-pulse" />
            ) : isError || health?.status !== "ok" ? (
              <span className="flex items-center gap-1 text-destructive">
                <ShieldAlert className="h-3 w-3" />
                OFFLINE
              </span>
            ) : (
              <span className="flex items-center gap-1 text-primary">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                </span>
                ONLINE
              </span>
            )}
          </div>
        </div>
      </header>

      <div className="flex flex-1">
        <aside className="w-64 flex-col border-r bg-card hidden md:flex">
          <nav className="flex-1 space-y-1 p-4">
            {navigation.map((item) => {
              const isActive = location === item.href;
              return (
                <Link key={item.name} href={item.href}>
                  <div
                    className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors cursor-pointer ${
                      isActive
                        ? "bg-primary/10 text-primary font-medium"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground"
                    }`}
                    data-testid={`nav-${item.name.toLowerCase().replace(' ', '-')}`}
                  >
                    <item.icon className={`h-4 w-4 ${isActive ? "text-primary" : "text-muted-foreground"}`} />
                    {item.name}
                  </div>
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="flex-1 p-6 md:p-8 overflow-y-auto">
          <div className="mx-auto max-w-6xl">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
