# AI Quant Lab — Instagram Card Production

미국주식 데이터 분석 플랫폼의 인스타그램 카드 콘텐츠 작업장.

## 📂 폴더 구조

```
docs/instagram/
├── README.md              # 이 파일
├── _shared/               # 공유 자산 (디자인 토큰, 가이드)
├── _scripts/
│   └── export_all.py      # HTML → 1080×1350 PNG 일괄 export
│
├── 00_brand/              # 평생 1번 (앱 소개, 프로필 이미지)
├── 01_earnings/           # 종목별 어닝 분석 (반복 시리즈)
├── 02_weekly_calendar/    # 주간 어닝 캘린더
├── 03_quant_basics/       # 퀀트 입문 교육 (PER, PBR, ROE...)
├── 04_market_recap/       # 주간/월간 시장 리캡
├── 05_strategy/           # 매매 전략 교육
│
└── output/                # 생성된 PNG (gitignore 됨)
```

## 🎨 디자인 가이드

| 항목 | 규칙 |
|---|---|
| 카드 크기 | **540×675 (4:5)** → 1080×1350 export |
| 폰트 최소 | **14px** (기본 16px 이상) |
| 폰트 굵기 | **500 이상** (Regular 400 금지) |
| 색상 금지 | `#A0AEC0` (mute), `#64748B` (dark mute) |
| 권장 색상 | `#F1F5F9` (white) / `#CBD5E1` (dim) / `#4ADE80` (green) / `#93C5FD` (blue) / `#FDE68A` (gold) / `#FCA5A5` (red) |
| 배경 | `#0A0E1A` (page) / `#0F172A` (card) |

## 🚀 워크플로우

### 새 카드 만들기

```bash
# 1. 같은 시리즈 템플릿 복사
cp 03_quant_basics/_template.html 03_quant_basics/02_PBR.html

# 2. 내용 교체 (브라우저로 미리보기 가능)

# 3. PNG export
python _scripts/export_all.py 03_quant_basics/02_PBR.html
# → output/03_quant_basics/02_PBR/card_1.png ~ card_N.png
```

### 폴더 전체 / 모든 시리즈 export

```bash
python _scripts/export_all.py 01_earnings  # 한 폴더
python _scripts/export_all.py              # 모든 시리즈
```

## 📝 파일명 규칙

| 시리즈 | 형식 | 예 |
|---|---|---|
| 종목별 어닝 | `YYYY-MM-DD_TICKER.html` | `2026-04-24_INTC.html` |
| 주간 캘린더 | `YYYY-WNN_<범위>.html` | `2026-W18_apr28-may02.html` |
| 퀀트 입문 | `NN_<주제>.html` | `01_PER.html`, `02_PBR.html` |
| 매매 전략 | `NN_<주제>.html` | `01_earnings_trading.html` |

## 🛠️ 카드 HTML 구조

각 카드는 `.card-wrap > .card` 구조 + `.card-label`로 카드 번호:

```html
<div class="card-wrap">
  <div class="card-label">CARD 1 · COVER</div>
  <div class="card ...">
    <div class="card-head">...</div>
    <!-- 콘텐츠 -->
  </div>
</div>
```

`export_all.py`가 `CARD N` 라벨을 파싱해 `card_N.png`로 저장.

## 📤 인스타 업로드

- 한 게시물 = 한 폴더의 모든 PNG (캐러셀)
- 1080×1350 (4:5) → 인스타 그리드에서 잘림 없음
- 첫 사진 비율이 캐러셀 전체 비율 결정 → 항상 4:5 유지

## 🔁 PNG가 사라졌을 때

```bash
python _scripts/export_all.py
```

HTML이 git에 살아있으면 PNG는 언제든 재생성 가능.
