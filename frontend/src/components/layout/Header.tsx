import { Link, useLocation } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  Brain,
  LayoutDashboard,
  Menu,
} from "lucide-react";
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
  { to: "/market", label: "Market", icon: BarChart3 },
  { to: "/screener", label: "Screener", icon: BarChart3 },
  { to: "/portfolio", label: "Portfolio", icon: Briefcase },
  { to: "/sentiment", label: "Sentiment", icon: Brain },
];

const Header = () => {
  const location = useLocation();

  const isActive = (path: string) => location.pathname.startsWith(path);

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
                variant={isActive(item.to) ? "secondary" : "ghost"}
                size="sm"
                className={cn(
                  "gap-1.5",
                  isActive(item.to) && "bg-secondary",
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
              <Link to="/">
                <Button
                  variant={location.pathname === "/" ? "secondary" : "ghost"}
                  className="w-full justify-start gap-2"
                >
                  <LayoutDashboard className="h-4 w-4" />
                  Dashboard
                </Button>
              </Link>
              {navItems.map((item) => (
                <Link key={item.to} to={item.to}>
                  <Button
                    variant={isActive(item.to) ? "secondary" : "ghost"}
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
