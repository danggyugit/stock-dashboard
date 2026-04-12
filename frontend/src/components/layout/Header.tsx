import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  Brain,
  CalendarDays,
  LayoutDashboard,
  Menu,
  LogIn,
  LogOut,
} from "lucide-react";
import useAuthStore from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetTitle,
} from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import TickerSearch from "@/components/common/TickerSearch";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/market", label: "Market", icon: BarChart3 },
  { to: "/screener", label: "Screener", icon: BarChart3 },
  { to: "/portfolio", label: "Portfolio", icon: Briefcase },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/sentiment", label: "Sentiment", icon: Brain },
];

const Header = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuthStore();

  const isActive = (path: string, exact?: boolean) =>
    exact ? location.pathname === path : location.pathname.startsWith(path);

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 items-center px-4">
        {/* Logo */}
        <Link
          to="/"
          className="flex items-center gap-2 mr-6 font-bold text-lg"
        >
          <LayoutDashboard className="h-5 w-5" />
          <span>StockDash</span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-1">
          {navItems.map((item) => (
            <Link key={item.to} to={item.to}>
              <Button
                variant={isActive(item.to, item.exact) ? "secondary" : "ghost"}
                size="sm"
                className={cn(
                  "gap-1.5",
                  isActive(item.to, item.exact) && "bg-secondary",
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Button>
            </Link>
          ))}
        </nav>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Search - Desktop */}
        <div className="hidden md:block w-64 mr-2">
          <TickerSearch />
        </div>

        {/* Auth */}
        {isAuthenticated && user ? (
          <div className="flex items-center gap-2 ml-2">
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt=""
                className="w-7 h-7 rounded-full"
                referrerPolicy="no-referrer"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">
                {(user.name || user.email || "?").charAt(0).toUpperCase()}
              </div>
            )}
            <span className="hidden lg:inline text-xs font-medium">{user.name}</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2"
              onClick={() => { logout(); navigate("/"); }}
            >
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        ) : (
          <Link to="/login" className="ml-2">
            <Button variant="outline" size="sm" className="h-7 gap-1 text-xs">
              <LogIn className="h-3.5 w-3.5" />
              Sign in
            </Button>
          </Link>
        )}

        {/* Mobile Menu */}
        <Sheet>
          <SheetTrigger
            render={<Button variant="ghost" size="icon" className="md:hidden" />}
          >
            <Menu className="h-5 w-5" />
            <span className="sr-only">Toggle menu</span>
          </SheetTrigger>
          <SheetContent side="left" className="w-72">
            <SheetTitle className="flex items-center gap-2 px-2 mb-4">
              <LayoutDashboard className="h-5 w-5" />
              StockDash
            </SheetTitle>
            <div className="px-2 mb-4">
              <TickerSearch placeholder="Search..." />
            </div>
            <Separator className="mb-4" />
            <nav className="flex flex-col gap-1">
              {navItems.map((item) => (
                <Link key={item.to} to={item.to}>
                  <Button
                    variant={isActive(item.to, item.exact) ? "secondary" : "ghost"}
                    className="w-full justify-start gap-2"
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Button>
                </Link>
              ))}
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
};

export default Header;
