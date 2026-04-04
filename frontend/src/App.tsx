import { useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import Dashboard from "@/pages/Dashboard";
import Market from "@/pages/Market";
import Screener from "@/pages/Screener";
import StockDetail from "@/pages/StockDetail";
import Compare from "@/pages/Compare";
import Portfolio from "@/pages/Portfolio";
import Trades from "@/pages/Trades";
import Dividends from "@/pages/Dividends";
import Tax from "@/pages/Tax";
import Sentiment from "@/pages/Sentiment";
import AIReport from "@/pages/AIReport";
import Login from "@/pages/Login";
import useAuthStore from "@/stores/authStore";

const App = () => {
  const restore = useAuthStore((s) => s.restore);

  useEffect(() => {
    restore();
  }, [restore]);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/market" element={<Market />} />
        <Route path="/screener" element={<Screener />} />
        <Route path="/stock/:ticker" element={<StockDetail />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/portfolio/trades" element={<Trades />} />
        <Route path="/portfolio/dividends" element={<Dividends />} />
        <Route path="/portfolio/tax" element={<Tax />} />
        <Route path="/sentiment" element={<Sentiment />} />
        <Route path="/sentiment/report" element={<AIReport />} />
      </Route>
    </Routes>
  );
};

export default App;
