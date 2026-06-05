# AGENTS.md

> Antigravity 워크스페이스 규칙 파일. 프로젝트 루트에 둔다.
> (대안 위치: `.agents/rules/project-context.md`)
> 이 파일은 항상 활성화되는 영구 컨텍스트다. **빌드/실행 규칙**만 담는다.
> 출품 부문·평가배점·타깃·차별화 등 제품/전략 결정은 `PRD.md`에 둔다.

---

## 1. 프로젝트 개요

**가칭: GugakPlace — "K-콘텐츠 크리에이터 저작권 쉴드"** — 영상의 기획(시놉시스)이나 배경 장소의 문화 정체성에 맞춰, **수익화·편집에 법적으로 안전한 공공 국악 음원·샘플 루프**를 AI로 매칭·추천하는 **웹 서비스**. (음원별 출처·라이선스·사용 가능 범위를 화면에 함께 표시한다. "저작권 문제 전혀 없음/저작권료 0원"처럼 단정하지 않는다 — "이용조건만 지키면 안전"으로 표기.)
적합한 음원이 부족할 경우, 라이선스가 깨끗한 모델로 국악 색 BGM을 **생성**해 데이터 빈틈을 메운다(보조 기능).

- **1차 사용자**: 글로벌 K-콘텐츠 크리에이터·영상 편집자. 입력 = 시놉시스/무드 텍스트 또는 타깃 장소. 출력 = 매칭된 음원/샘플 루프 + 라이선스 + (편집용) 다운로드.
- **보조 사용자**: 공간 운영자(한옥카페·전통시장·지자체 관광지)의 합법 BGM. 같은 매칭 엔진을 재생 용도로 재사용.
- 형태: 웹(반응형). 네이티브 앱은 만들지 않는다.
- 핵심 차별점: 분위기 추천(어플레이즈)도, 가상악기 제작(조선시리즈)도 아니다. **장소·맥락 정체성 ↔ 지역 문화 음원을 AI로 매칭** + **잠자던 공공 아카이브 활성화** + **이용조건이 명확해 그대로 쓸 수 있음**. (포지셔닝 상세는 PRD.md.)
- 문화 공공데이터를 핵심 엔진으로 사용한다.

## 2. 최우선 원칙 (모든 결정의 기준)

1. **시연 안정성 > 완성도.** 발표에서 라이브로 끊김 없이 돌아가는 게 최우선.
2. **히어로 핵심 흐름(예시 입력 → 매칭 → 재생/표시)은 외부 호출에 의존하지 않는다.** 히어로 장소·예시 시놉시스의 데이터·임베딩은 전부 사전 계산해 로컬에 둔다.
   - ⇒ §5의 데이터 소스 API는 전부 **수집용(1회성)**. 런타임 경로에 두지 않는다.
   - ⇒ 런타임 외부 호출은 **딱 두 곳만** 허용: ① 크리에이터 **자유 텍스트 입력**의 런타임 임베딩(§3), ② **생성 보조**(fal.ai). **둘 다 try/except + 캐싱/예시 폴백 필수**. 외부가 죽어도 히어로 데모는 멀쩡해야 한다.
3. 히어로 예시(장소 3~4곳 + 시놉시스 3~4개)에서 확실히 작동하게 만든다. 전국/전체 커버리지보다 우선.

## 3. 기술 스택

- **Frontend**: React + Vite + TypeScript, Tailwind CSS. 지도(선택) Leaflet. 점수 시각화 차트(레이더/게이지).
- **Backend**: Python 3.12 + FastAPI + uvicorn.
- **CORS (데모 필수)**: Vite dev(5173) → FastAPI(8000)는 CORS에 막힌다. `CORSMiddleware`로 dev origin 허용, 배포 시 실제 도메인으로 좁힘(와일드카드 금지).
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                     allow_methods=["GET","POST"], allow_headers=["*"])
  ```
- **임베딩(의미 매칭)**:
  - **사전 계산(코퍼스)**: 오프라인 스크립트로 장소·트랙·예시 시놉시스 임베딩을 미리 구워 `*.json`에 저장. 모델 기본값 `jhgan/ko-sroberta-multitask`(768차원, 접두사 불필요).
  - **히어로 경로**: 백엔드는 ML 모델 미로드, `numpy` 코사인만. 가장 가볍고 안정적.
  - **자유 텍스트 입력 경로(크리에이터 핵심 기능)**: 임의 시놉시스를 받으므로 런타임 임베딩이 필요하다. **백엔드에 `torch`+`transformers`를 직접 올리지 말 것**(무료 티어 메모리 초과). **Hugging Face Inference API로 동일 모델(`ko-sroberta-multitask`)을 호출**해 벡터 공간을 코퍼스와 일치시킨다(모델 혼용 금지 — OpenAI 임베딩으로 바꾸려면 코퍼스도 같은 모델로 재생성). 이 호출은 **타임아웃 + 폴백**(실패 시 "예시 시놉시스 중 가장 가까운 것" 또는 장소 선택으로 우회)을 가진다.
  - **임베딩 일관성 가드**: `places.json`·`tracks.json`에 `embedding_model`·`embedding_dim` 저장. 부팅 시 두 파일 + 런타임 임베딩 모델이 같은지 `assert`.
- **LLM 근거(선택)**: provider-agnostic, env 주입. 없으면 유사도 + 템플릿 근거로 대체.
- **음악 생성(보조)**: fal.ai 경유 **ElevenLabs Music / Stable Audio**, 또는 자체 호스팅 **MusicGen**. **Suno / Udio 금지**(상업 라이선스 불명확).
- **데이터 저장**: DB 없이 JSON + 로컬 오디오. 필요 시 SQLite.
- **오디오 서빙**: `data/audio/`는 FastAPI `app.mount("/audio", StaticFiles(...))`로 `/audio/<file>.mp3` 서빙. `tracks.json`의 `audio_path`를 URL과 일치.
- **패키지**: frontend = npm, backend = pip + venv.

### 3.1 실행 명령 (로컬)

```bash
cp .env.example .env                      # 키 채우기 (§10)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../frontend && npm install
cd backend && python -m prep.build_all    # places/tracks/synopsis_examples/reasoning/audio 생성
cd backend && uvicorn main:app --reload --port 8000
cd frontend && npm run dev                 # http://localhost:5173
```

## 4. 디렉터리 구조

```
project-root/
├── AGENTS.md           # 빌드/실행 규칙
├── PRD.md              # 출품 부문·타깃·전략
├── .env.example
├── .gitignore
├── data/
│   ├── raw/            # 원본 다운로드
│   ├── places.json     # 장소 데이터 (+ 임베딩, 메타)
│   ├── tracks.json     # 음원 메타 + 임베딩 + 라이선스 필드
│   ├── synopsis_examples.json  # 히어로 예시 시놉시스 (+ 사전 임베딩)
│   ├── reasoning.json  # 히어로 매칭 근거 (키 "ctx_id:track_id")
│   └── audio/          # 음원 파일, mp3 통일 (gitignore)
├── backend/
│   ├── main.py         # FastAPI (CORS, StaticFiles)
│   ├── matching.py     # 하이브리드 매칭 엔진
│   ├── embeddings.py   # 임베딩 로드/유사도 + HF Inference 호출 + 일관성 assert
│   ├── licensing.py    # 라이선스 → 사용가능범위 파생 (§5.5)
│   ├── generation.py   # 생성(보조) + 폴백
│   ├── rules/          # 매핑표·규칙표 JSON
│   ├── prep/           # 오프라인 가공 스크립트 (.env 읽음)
│   ├── tests/          # 매칭/라이선스 스모크 테스트
│   └── requirements.txt
├── frontend/ (src/App.tsx, components/, api.ts ...)
└── README.md
```

## 5. 데이터 (문화 공공데이터)

전부 무료 공공데이터. `data/raw/`에 보관하고 `backend/prep/`로 정제. **수집용(1회성), 런타임 경로에 두지 않는다(§2).**

> ⚠️ **출품 자격**: data.go.kr / 문화공공데이터광장(culture.go.kr/data) / 문화 빅데이터 플랫폼(bigdata-culture.kr) 개방 데이터 **1종 이상** 필수. 국립국악원(15097515)·국가유산청(3070426)·TourAPI(15101578)가 data.go.kr 소스라 충족. `source`에 포털·데이터셋 ID 증빙 기록. 공유마당은 세 포털 등록 여부 불확실 → "추가 음원"으로만 취급.

### 5.1 장소 소스

| 소스 | 위치 | 형식 | 비고 |
| --- | --- | --- | --- |
| 국가유산청_문화재 공간 정보 | data.go.kr/data/3070426 | XML | 좌표·유형·설명. 지정유산 장소 1차 소스. |
| 한국관광공사 TourAPI(국문) | data.go.kr/data/15101578 | XML/**JSON** | `&_type=json`. 관광지·문화시설·축제·전통시장. |
| (지정유산 상세, 선택) | 국가유산포털(khs.go.kr) | XML | 구 문화재청 엔드포인트 폐기 → 현재 명세 재확인. |

### 5.2 음원 소스 — 역할 구분 (중요)

| 소스 | 위치 | 역할 | 형식 |
| --- | --- | --- | --- |
| 공유마당 자유이용 음원 | gongu.copyright.or.kr (Key 즉시 발급) | **재생용 완성곡(주력)** + 라이선스 필드 | XML |
| 국악방송 공공개방음원 | igbf.kr → data.go.kr 경유 | **재생용 완성곡** | 파일 다운로드(공공누리) |
| 국립국악원 국악디지털음원 | data.go.kr/data/15097515 | **크리에이터 편집용 프리셋 사운드 소스 / 샘플 루프 / instruments 태그** | OpenAPI(Swagger) |

> 국립국악원 "디지털음원"은 완성 BGM이 아니라 악기 단음(약 407) + 악구 루프(약 2,226)인 **샘플**이다. 완성곡 재생 대상으로 쓰지 말 것. 대신 **크리에이터가 영상에 얹는 편집용 사운드 소스/루프**로 제공하면 가치가 살아난다(1차 타깃과 정합). 생성 소스·`instruments` 태그로도 사용.

### 5.3 정제 산출물 스키마

- `places.json`: `{ id, name, region, type, lat, lng, description, cultural_keywords, source, source_url, embedding }`
- `synopsis_examples.json`: `{ id, label, text, embedding }` ← 히어로 시연용 사전 임베딩 시놉시스.
- `tracks.json`: `{ id, title, genre, region, instruments, mood, description, audio_path, asset_kind, source, source_url, license_type, license_note, commercial_ok, is_derivative_allowed, attribution_text, embedding }`
  - `asset_kind` ∈ {`full_track`(완성곡, 재생용), `sample_loop`(편집용 루프/단음)}.
  - `commercial_ok`·`is_derivative_allowed`는 prep에서 `license_type`으로부터 **파생**(§5.5).
  - `attribution_text`: 출처표시 복붙용 문자열. prep에서 **각 소스가 요구하는 형식 그대로** 생성한다(예: 국립국악원 = 발행연도·기관명·홈페이지 URL·저작자 성명·라이선스 유형). GugakPlace 자체 브랜딩 문구는 넣지 않는다(법적 출처표시만).
- 모든 임베딩 JSON에 파일 레벨 메타 `{ embedding_model, embedding_dim, embed_text_recipe }`.
- **임베딩 텍스트 레시피(고정)**: 장소 `f"{name}. {description} 키워드: {','.join(cultural_keywords)}"` / 트랙 `f"{title}. {genre}. 악기: {','.join(instruments)}. 분위기: {mood}. {description}"`. 변경 시 양쪽 코퍼스 동시 재생성.

### 5.4 좌표·포맷 정규화 (prep)

- 좌표: 전부 **WGS84(EPSG:4326)** 정규화(소스별 좌표계 상이).
- 오디오: **ffmpeg로 mp3 통일**(국립국악원 wav 등). `audio_path`는 mp3 기준.

### 5.5 라이선스 = 자격 요건 + 사용가능범위 파생 (`backend/licensing.py`)

⚠️ **라이선스는 가점이 아니라 실격 방지 요건.** 출처·이용조건 불명확 음원은 사용 자체 금지. prep에서 `source_url` 원문 확인(추정 금지).

`license_type`에서 두 권리를 파생한다:

| license_type | commercial_ok | derivative_ok(=is_derivative_allowed) |
| --- | --- | --- |
| 공공누리 제1유형 (출처표시) | ✅ | ✅ |
| 공공누리 제2유형 (출처+상업금지) | ❌ | ✅ |
| 공공누리 제3유형 (출처+변경금지) | ✅ | ❌ |
| 공공누리 제4유형 (출처+상업금지+변경금지) | ❌ | ❌ |
| CC0 / CC BY | ✅ | ✅ |
| CC *-NC | ❌ | (조건별) |
| CC *-ND | (조건별) | ❌ |

**사용 목적별 필터(use_case)**:
- `creator`(영상 편집 + 수익화) → **`commercial_ok AND derivative_ok`** = 사실상 **공공누리 제1유형 + CC0/CC BY만**. (제2=상업금지, 제3=편집금지 모두 탈락.)
- `place_bgm`(상업 공간 재생) → `commercial_ok`(재생은 변경 아님). 제1·제3유형 + CC0/BY.
- `listen`(비상업 청취/학습) → 출처표시만 지키면 전체.

생성(2차 가공)은 `is_derivative_allowed=true`에만 적용(§3 generation에서 false 제외).

## 6. 매칭 파이프라인 (backend/matching.py)

입력: `place_id` **또는** `query_text`(자유 시놉시스), `use_case`. 출력: 점수순 후보 + component 점수 + 근거.

1. **지역 적합도**: 행정구역 → 음악 권역 매핑표. `query_text`엔 약하게/생략. `rules/`에 JSON.
2. **유형 적합도**: 장소 유형 → 장르 가중(궁궐→정악, 사찰→영산회상·범패, 시장→사물놀이, 한옥카페→산조 등). `rules/`에 JSON.
3. **의미 임베딩(AI 기둥 ①)**: 컨텍스트 임베딩 ↔ 트랙 임베딩 코사인. `query_text`는 §3 런타임 임베딩.
4. **악기·분위기 태그 적합도**: 키워드 ↔ `instruments`/`mood`.

**점수 정규화(필수)**: 가중합 전 **각 신호를 `[0,1]`로 정규화**(코사인은 `(cos+1)/2` 또는 `max(0,cos)`). 그 다음:
```
final = 0.30*지역 + 0.25*유형 + 0.30*의미 + 0.15*태그     # 각 항 ∈ [0,1]
```
상위 N(기본 5) 내림차순. 동점은 의미유사도 우선. **use_case 필터(§5.5)를 매칭 전/후 적용**해 부적합 라이선스 음원을 결과에서 제외.

**매칭은 항상 라이브 계산 — 하드코딩 금지.** 근거 텍스트만 사전 생성 가능: 히어로(장소+예시 시놉시스)는 `reasoning.json`, 그 외는 템플릿 폴백. 근거는 응답에 **항상 포함**.

## 7. API 엔드포인트 (FastAPI)

- `GET /api/places` → 데모 장소 목록
- `GET /api/examples` → 히어로 예시 시놉시스 목록(사전 임베딩)
- `POST /api/match` `{ place_id? , query_text? , use_case }` → `{ tracks: [...], reasoning }`
  - `query_text`가 오면 §3 런타임 임베딩(HF Inference, 폴백 보유). `place_id`면 사전 임베딩 사용.
  - 각 트랙은 **최종 점수 + 정규화된 4개 component 점수 분리**(레이더 시각화 전제) + 라이선스 파생값:
    ```json
    { "track_id":"t01", "final_score":0.87,
      "scores":{"region":0.30,"type":0.25,"semantic":0.85,"tag":0.60},
      "asset_kind":"sample_loop", "license_type":"공공누리 제1유형",
      "commercial_ok":true, "derivative_ok":true, "source":"국립국악원",
      "audio_url":"/audio/t01.mp3", "reasoning":"..." }
    ```
- `POST /api/generate` `{ place_id? , query_text? }` → `{ audio_url }` (보조, 실패 시 캐싱본 폴백)

## 8. 프론트엔드 동작

- 입력: **(A) 예시 시놉시스/장소 선택(히어로, 안정)** + **(B) 자유 텍스트 입력(크리에이터 핵심, 폴백 보유)**. 무드/use_case 토글.
- 결과 카드: 곡명·장르·`asset_kind`(완성곡/편집 루프)·**라이선스·출처**·매칭 근거. `sample_loop`은 "편집용 다운로드", `full_track`은 재생 중심.
- **매칭 점수 시각화**: `/api/match`의 4 component를 레이더/게이지로 노출("데이터가 라이브 계산 중"). **반드시 API 응답값으로 그린다(프론트 하드코딩 금지).**
- **악기 태그 시각화(B-1)**: 재생 중 곡의 `instruments` 태그에 해당하는 전통 악기(가야금·거문고·해금·태평소 등) 아이콘/트랙 바를 활성화. ⚠️ 이는 **메타데이터(태그) 기반 표시이지 실시간 오디오 분리(stem separation)가 아니다.** "이 곡에 포함된 악기(메타 기준)"로만 표기하고, AI가 음원을 분해하는 것처럼 보이게 하지 않는다.
- **라이선스 카드는 곡별 실제 값으로 렌더링.** `license_type` 그대로 표시하고 "수익화 가능/편집 가능"은 `commercial_ok`·`derivative_ok`에서 파생. "전 곡 상업 가능" 식 하드코딩 금지. **출처표시는 법적 의무**라 항상 노출.
- **다운로드(크리에이터)**: `use_case=creator` 통과 음원만 다운로드 허용. 다운로드/선택 시 **출처표시 카피 가이드(A-1)**를 팝업으로 제공 — `attribution_text`를 그대로 복사해 유튜브 더보기란에 붙일 수 있게 한다(출처표시는 법적 의무이므로 이행을 적극 유도). ※ "안심 보증서/라이선스 인증" 같은 법적 면책을 약속하는 문서는 발급하지 않는다(보증할 수 없는 영역).
- **빈/에러 상태(시연 직결)**: 결과 0개 → 안내 + 기본 추천. 런타임 임베딩/오디오/생성 실패 → 토스트 + 예시·캐싱본 폴백. 흰 화면 금지.
- **자동재생 차단 대응**: 클릭 즉시 동기 `audio.play()` → 즉시 `pause()`로 권한 잠금 해제, 결과 도착 시 `audio.src` 교체 후 `play()`. Web Audio 시각화 시 같은 클릭에서 `audioContext.resume()`.
- **Web Audio + cross-origin**: 백엔드 오리진이 다르면 시각화에 `<audio crossorigin="anonymous">` + 서버 CORS 헤더 필요(단순 재생은 불필요).

## 9. 코딩 컨벤션

- Python: PEP 8, 타입힌트·docstring. 매직 넘버 상수화. 매핑표·규칙표·라이선스표는 분리(JSON/`licensing.py`).
- TypeScript: 함수형 + Hooks. API 호출은 `src/api.ts`.
- 기능 단위 파일 분리. `main.py`에 로직 몰지 않기.
- 외부 호출 함수는 항상 타임아웃 + 예외 + 폴백.

## 10. 안전 / 가드레일

- **API 키는 backend `.env`에만.** 프론트 노출·커밋 금지. `.env.example`만 커밋. `prep/`도 같은 `.env` 사용.
- **data.go.kr 키 함정**: Encoding/Decoding 키 두 개. 서버 요청엔 보통 **Decoding 키**. `.env`에 종류 주석, 소스별 변수명 구분.
- `.gitignore`: `.env`, `data/audio/`, `data/raw/`, `__pycache__/`, `node_modules/`.
- 파괴적 명령(`rm -rf`, force push, 일괄 삭제)은 실행 전 사용자 확인.
- 음악 생성은 라이선스 클린 모델만. Suno/Udio 금지.

## 11. 구현 순서 & Definition of Done

> 스코프 주의: **매칭 엔진(Phase 2)을 먼저 완성**한 뒤 입력 레이어(자유 텍스트)·다운로드를 얹는다. 마감 대비 한 번에 피벗하지 말 것.

- **Phase 1 — 데이터 준비** ✅
  - DoD: places/tracks/synopsis_examples/reasoning/audio 생성. 임베딩 **실제 ko-sroberta**(더미 금지), 차원 일치. 라이선스 원문 검증 + `commercial_ok`/`is_derivative_allowed` 파생 완료. `asset_kind` 분류 완료.
- **Phase 2 — 매칭 엔진**
  - DoD: 정규화된 4신호 가중합 + use_case 필터 + `POST /api/match`(place_id 경로). 히어로 장소 4곳 라이브 계산·점수순·근거 포함, 하드코딩 없음. `tests/`에 매칭·라이선스 파생 스모크 테스트 통과.
- **Phase 3 — 프론트 끝-끝 + 자유 텍스트 입력**
  - DoD: 예시/장소 경로(안정) + 자유 텍스트 경로(런타임 임베딩 + 폴백). 레이더 점수·라이선스 카드(실제값)·다운로드·빈/에러 폴백 동작. CORS·autoplay 무결.
- **Phase 4 — 생성 보조**
  - DoD: `generation.py` + 폴백. fal.ai 실패 시 캐싱본. `is_derivative_allowed=false` 제외.
- **Phase 5 — 다듬기·배포**
  - DoD: 근거·라이선스/출처·다운로드 안내 다듬기. 배포(프론트 Vercel/Netlify, 백엔드 Render/Fly 등). ⚠️ 무료 티어 디스크 ephemeral → 오디오는 빌드/리포 포함. 라이브 시연 리허설 + 로컬 백업.

> Phase 1~3이면 라이브 시연 요건 충족. Phase 4가 기술 임팩트(AI 활용)용.