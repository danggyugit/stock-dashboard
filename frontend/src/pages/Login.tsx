import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { Card, CardContent } from "@/components/ui/card";
import useAuthStore from "@/stores/authStore";
import { LayoutDashboard, Clock } from "lucide-react";

const Login = () => {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const [error, setError] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState(false);
  const [loading, setLoading] = useState(false);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <Card className="w-full max-w-sm">
        <CardContent className="pt-8 pb-8 flex flex-col items-center gap-6">
          <div className="flex items-center gap-2 text-2xl font-bold">
            <LayoutDashboard className="h-7 w-7" />
            StockDash
          </div>

          {pendingApproval ? (
            <>
              <div className="flex flex-col items-center gap-3 text-center">
                <Clock className="h-10 w-10 text-yellow-500" />
                <p className="font-semibold">접근 승인 대기 중</p>
                <p className="text-sm text-muted-foreground">
                  구글 계정이 등록되었지만 아직 관리자 승인이 필요합니다.
                  관리자에게 접근 권한을 요청해 주세요.
                </p>
              </div>
              <button
                className="text-xs text-muted-foreground underline"
                onClick={() => setPendingApproval(false)}
              >
                다른 계정으로 시도
              </button>
            </>
          ) : (
            <>
              <p className="text-sm text-muted-foreground text-center">
                구글 계정으로 로그인하세요
              </p>

              {error && (
                <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-md w-full text-center">
                  {error}
                </p>
              )}

              {loading ? (
                <p className="text-sm text-muted-foreground animate-pulse">로그인 중...</p>
              ) : (
                <GoogleLogin
                  onSuccess={async (response) => {
                    if (!response.credential) {
                      setError("Google에서 인증 정보를 받지 못했습니다.");
                      return;
                    }
                    setLoading(true);
                    setError(null);
                    try {
                      await login(response.credential);
                      navigate("/");
                    } catch (err: unknown) {
                      const status = (err as { status?: number }).status;
                      if (status === 403) {
                        setPendingApproval(true);
                      } else {
                        setError((err as Error).message || "로그인에 실패했습니다.");
                      }
                      setLoading(false);
                    }
                  }}
                  onError={() => {
                    setError("Google 로그인에 실패했습니다. 다시 시도해 주세요.");
                  }}
                  size="large"
                  width="300"
                  text="signin_with"
                />
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;
