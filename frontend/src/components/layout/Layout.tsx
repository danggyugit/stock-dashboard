import { Outlet } from "react-router-dom";
import Header from "./Header";

const Layout = () => {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="max-w-[1600px] mx-auto px-3 py-3">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
