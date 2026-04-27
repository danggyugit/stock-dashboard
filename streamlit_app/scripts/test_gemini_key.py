"""Diagnose a Gemini API key.

Usage:
  C:/Python/python.exe scripts/test_gemini_key.py YOUR_NEW_KEY

Tests in order:
  1. List available models       (validates key + API enabled)
  2. Generate with gemini-2.5-flash  (validates model access + quota)
  3. Compare to currently-active key in secrets.toml
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests


def mask(key: str) -> str:
    if not key:
        return "(empty)"
    return f"{key[:8]}...{key[-4:]} (len={len(key)})"


def test_key(key: str, label: str = "key") -> dict:
    print(f"\n=== Testing {label}: {mask(key)} ===")
    out = {"label": label, "masked": mask(key)}

    # 1. List models
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        r = requests.get(url, timeout=15)
        out["list_models_status"] = r.status_code
        if r.status_code == 200:
            models = r.json().get("models", [])
            out["model_count"] = len(models)
            has_25_flash = any("gemini-2.5-flash" in m.get("name", "") for m in models)
            out["has_2_5_flash"] = has_25_flash
            print(f"  [OK] List models: {len(models)} models, 2.5-flash={has_25_flash}")
        else:
            err = r.json().get("error", {})
            out["list_error"] = err.get("message", r.text[:200])
            print(f"  [FAIL {r.status_code}] {out['list_error']}")
            return out
    except Exception as e:
        out["list_error"] = str(e)
        print(f"  [ERROR] {e}")
        return out

    # 2. Generate
    gen_url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-2.5-flash:generateContent?key={key}"
    )
    body = {
        "contents": [{"parts": [{"text": "say 'ok' in one word"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 10},
    }
    try:
        r = requests.post(gen_url, json=body, timeout=20)
        out["generate_status"] = r.status_code
        if r.status_code == 200:
            data = r.json()
            text = (
                data.get("candidates", [{}])[0]
                    .get("content", {}).get("parts", [{}])[0]
                    .get("text", "")
            )
            out["generate_response"] = text.strip()[:50]
            print(f"  [OK] Generate: '{text.strip()}'")
        else:
            err = r.json().get("error", {})
            out["generate_error"] = err.get("message", r.text[:300])
            out["generate_status_code"] = err.get("status", "")
            print(f"  [FAIL {r.status_code}] {out['generate_error']}")
    except Exception as e:
        out["generate_error"] = str(e)
        print(f"  [ERROR] {e}")

    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: test_gemini_key.py <new_key_to_test>")
        print("       (will also compare to current key in secrets.toml)")
        return 1

    new_key = sys.argv[1].strip()

    # Load current key from secrets
    cur_key = None
    try:
        import toml
        sec_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
        if sec_path.exists():
            sec = toml.load(sec_path)
            cur_key = sec.get("GEMINI_API_KEY", "").strip() or None
    except Exception as e:
        print(f"(secrets.toml load: {e})")

    print(f"Current secrets key: {mask(cur_key) if cur_key else '(none)'}")
    print(f"New key under test:  {mask(new_key)}")
    print(f"Same key?            {new_key == cur_key}")

    new_result = test_key(new_key, "NEW key")
    if cur_key and cur_key != new_key:
        cur_result = test_key(cur_key, "CURRENT (working) key")

    print("\n=== Summary ===")
    if new_result.get("generate_status") == 200:
        print("[PASS] New key works fully.")
        return 0
    elif new_result.get("list_models_status") == 200:
        print("[PARTIAL] Key valid, model access blocked.")
        print(f"  Reason: {new_result.get('generate_error', 'unknown')}")
    else:
        print("[FAIL] Key invalid or API not enabled.")
        print(f"  Reason: {new_result.get('list_error', 'unknown')}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
