import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { Card, CardContent } from "@/components/ui/card";
import useAuthStore from "@/stores/authStore";
import { LayoutDashboard } from "lucide-react";

const Login = () => {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <Card className="w-full max-w-sm">
        <CardContent className="pt-8 pb-8 flex flex-col items-center gap-6">
          <div className="flex items-center gap-2 text-2xl font-bold">
            <LayoutDashboard className="h-7 w-7" />
            StockDash
          </div>
          <p className="text-sm text-muted-foreground text-center">
            Sign in to manage your portfolios
          </p>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-md w-full text-center">
              {error}
            </p>
          )}

          {loading ? (
            <p className="text-sm text-muted-foreground animate-pulse">Signing in...</p>
          ) : (
            <GoogleLogin
              onSuccess={async (response) => {
                console.log("[AUTH] Google onSuccess, credential:", response.credential ? "present" : "missing");
                if (!response.credential) {
                  setError("No credential received from Google");
                  return;
                }
                setLoading(true);
                setError(null);
                try {
                  await login(response.credential);
                  navigate("/");
                } catch (err: unknown) {
                  const msg = (err as { response?: { data?: { detail?: string } } })
                    ?.response?.data?.detail || (err as Error).message || "Login failed";
                  console.error("[AUTH] Login error:", msg);
                  setError(msg);
                  setLoading(false);
                }
              }}
              onError={() => {
                console.error("[AUTH] Google onError callback");
                setError("Google sign-in failed. Please try again.");
              }}
              size="large"
              width="300"
              text="signin_with"
            />
          )}

          <p className="text-xs text-muted-foreground">
            Market data and sentiment are available without login.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;
