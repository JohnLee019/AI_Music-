# AGENTS.md

> Antigravity 워크스페이스 규칙 파일. 프로젝트 루트에 둔다.
> (대안 위치: `.agents/rules/project-context.md` — Antigravity 네이티브 워크스페이스 규칙 경로)
> 이 파일은 항상 활성화되는 영구 컨텍스트다. 12,000자 이내로 유지한다.

---

## 1. 프로젝트 개요

**가칭: GugakPlace** — 장소(문화유산·관광지·전통시장 등)의 문화 정체성에 맞춰, **이용 조건이 명확한 공공 국악·자유이용 음원**을 AI로 매칭·재생하는 **웹 서비스**. (음원별 출처·라이선스·가공 가능 여부를 화면에 함께 표시한다. "저작권료 0원"처럼 단정하지 않는다.)
적합한 음원이 부족할 경우, 라이선스가 깨끗한 모델로 국악 색의 BGM을 **생성**한다(보조 기능).

- 형태: 웹(반응형). 네이티브 앱은 만들지 않는다.
- 핵심 차별점: 단순 분위기 추천(경쟁사 어플레이즈)이 아니라, **장소의 문화 정체성 ↔ 그 지역의 문화 음원 데이터를 매칭**하는 것.
- 문화 공공데이터를 핵심 엔진으로 사용한다.

## 2. 최우선 원칙 (모든 결정의 기준)

1. **시연 안정성 > 완성도.** 발표에서 라이브로 끊김 없이 돌아가는 게 최우선이다. 화려한 기능보다 "확실히 작동하는 핵심 흐름".
2. **핵심 흐름(장소 선택 → 매칭 → 재생)은 외부 API 호출에 절대 의존하지 않는다.** 모든 장소 데이터·음원은 로컬에 캐싱해 두고 거기서 동작한다.
3. **외부 호출(생성 등)은 반드시 try/except + 캐싱된 폴백**을 가진다. 외부가 죽어도 데모 본체는 멀쩡해야 한다.
4. 히어로 예시 장소 3~4곳(예: 경복궁, 안동 하회마을, 전주 한옥마을, 특정 전통시장)에서 확실히 잘 작동하게 만든다. 전국 커버리지보다 우선.

## 3. 기술 스택

- **Frontend**: React + Vite + TypeScript, Tailwind CSS. 지도(선택) Leaflet.
- **Backend**: Python 3.12 + FastAPI + uvicorn.
- **임베딩(의미 매칭)**: 오프라인 스크립트에서 **장소·트랙 양쪽 임베딩을 미리 구워** `*.json`에 저장한다. 데모는 장소가 고정 3~4곳이므로 **백엔드는 ML 모델을 로드하지 않고 `numpy` 코사인 유사도만** 한다(가장 가볍고 안정적).
  - 사전 계산용 모델은 품질 좋은 걸 써도 됨(런타임 무게 무관). 임의 장소·검색어 입력 경로(후속 국민용 레이어)를 붙일 때만 런타임 모델이 필요하다.
  - ⚠️ 런타임 임베딩이 필요해지면 **백엔드에 `torch`+`transformers`를 직접 올리지 말 것** — 무료 티어(512MB~1GB)는 메모리 초과로 터진다. **Hugging Face Inference API나 OpenAI `text-embedding-3-small` 같은 호스팅 임베딩 API**로 서빙 레이어를 가볍게 유지. 이때 사전 계산 코퍼스도 **같은 임베딩 모델로** 구워야 벡터 공간이 일치한다(혼용 금지). 굳이 소형 로컬이면 `jhgan/ko-sroberta-multitask`.
  - 모델 컨벤션은 하나로 통일한다(예: e5 계열은 `query:`/`passage:` 접두사 필요, ko-sroberta는 불필요 → 섞지 말 것).
- **LLM 선곡·근거(선택)**: provider-agnostic, env로 주입. 없으면 임베딩 유사도 + 템플릿 근거로 대체.
- **음악 생성(보조)**: fal.ai 경유 **ElevenLabs Music** 또는 **Stable Audio**, 또는 자체 호스팅 **MusicGen**.
  - **Suno / Udio는 사용 금지** (상업 라이선스 불명확 → "이용 조건이 명확한 음원만 쓴다"는 전제와 충돌).
- **데이터 저장**: DB 없이 JSON 파일 + 로컬 오디오 파일. 필요 시 SQLite.
- **오디오 서빙**: 루트의 `data/audio/`는 브라우저가 직접 접근 못 한다. FastAPI가 `app.mount("/audio", StaticFiles(directory=...), name="audio")`로 마운트해 `/audio/<file>.mp3` URL로 서빙하고, `tracks.json`의 `audio_path`를 그 URL과 일치시킨다. (대안: `frontend/public/audio/`에 두고 프론트가 직접 접근.)
- **패키지**: frontend = npm, backend = pip + venv.

## 4. 디렉터리 구조

```
project-root/
├── AGENTS.md
├── .env.example
├── .gitignore
├── data/
│   ├── raw/            # 원본 다운로드 (국가유산청, 국립국악원 등)
│   ├── places.json     # 정제된 장소 데이터
│   ├── tracks.json     # 정제된 음원 메타 + 임베딩 벡터
│   └── audio/          # 캐싱된 무료 음원 파일 (gitignore)
├── backend/
│   ├── main.py         # FastAPI 엔트리포인트
│   ├── matching.py     # 하이브리드 매칭 엔진(지역+유형+의미+태그)
│   ├── embeddings.py   # 임베딩 로드/유사도
│   ├── generation.py   # 생성(보조) + 폴백
│   ├── prep/           # 오프라인 데이터 가공 스크립트
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   └── api.ts
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 5. 데이터 (문화 공공데이터)

전부 data.go.kr 등에서 받아 `data/raw/`에 보관하고, `backend/prep/` 스크립트로 정제한다.

- **장소**: 국가유산청 지정유산 지도다운로드 / 문화유산 데이터 지도 (명칭·소재지·지정구분·유형·좌표·설명). 정적 파일.
- **음원**: 국립국악원 국악디지털음원(오픈 API), 국악방송 공공개방음원, 공유마당 자유이용 음원. **무료/라이선스 클린만** 사용.

정제 산출물 스키마:
- `places.json`: `{ id, name, region, type, lat, lng, description, cultural_keywords, embedding }`  ← 데모 고정 장소는 임베딩까지 사전 계산. `cultural_keywords`는 매칭 신호이자 근거 표시용(예: ["왕실","궁중","의례","정제됨"]).
- `tracks.json`: `{ id, title, genre, region, instruments, mood, description, audio_path, source, source_url, license_type, license_note, is_derivative_allowed, embedding }`  ← 라이선스 검증 필드(출처·원문 URL·라이선스 유형·가공 가능 여부) 필수.

**라이선스 규칙**: 음원별 라이선스를 반드시 기록한다. 편곡/생성(2차 가공)은 **변경 허용 라이선스(CC BY 등) 음원에만** 적용한다. CC BY-ND·변경금지 음원은 가공 금지, 원본 재생만.

## 6. 매칭 파이프라인 (backend/matching.py)

입력: place_id → 출력: 점수순 후보 트랙 리스트 + 매칭 근거 텍스트.

1. **지역 필터**: 행정구역 → 음악 권역 매핑표(경북→영남, 전라→호남, 경기/서울→경기 등)로 1차 거름.
2. **유형 규칙표**: 장소 유형 → 장르 가중 (궁궐→정악·궁중음악, 서원→정악·가곡, 사찰→영산회상·범패, 민속마을→민요·농악, 전통시장→사물놀이·민속악, 한옥카페→산조·독주).
3. **의미 임베딩(AI 기둥 ①)**: 장소 설명문·`cultural_keywords` 임베딩 ↔ 트랙 임베딩 코사인 유사도(`numpy`).
4. **악기·분위기 태그 적합도**: 장소 `cultural_keywords` ↔ 트랙 `instruments`/`mood` 태그 일치도.

이 4개 신호를 결합한 **하이브리드 문화 맥락 매칭 엔진**이다(단순 유사도 검색이 아님 — AI활용 평가에서 이 점을 강조). 최종 점수는 가중 합산, 시작 기본값(튜닝 가능):

```
final = 0.30*지역적합도 + 0.25*유형적합도 + 0.30*의미유사도 + 0.15*태그적합도
```

**매칭(선곡)은 항상 라이브로 진짜 계산한다 — 절대 하드코딩하지 않는다.** 여기가 AI의 실체다(AI활용 20점). 근거 텍스트만 사전 생성/캐싱하고 매칭까지 박아버리면 안 된다.

근거 텍스트(설명 레이어)는 사전 생성해도 된다:
- 히어로 장소 3~4곳: LLM이 생성한 고품질 근거 문장을 `data/reasoning.json`(키: `place_id:track_id`)에 미리 박아둔다 → 데모 중 LLM 라이브 호출 0, 딜레이·실패 없음.
- 그 외 장소: 메타데이터(유형·장르) 기반 템플릿 문장으로 대체. (LLM 라이브 호출은 파이프라인만 구축해 두고 데모 기본 경로에서는 끈다.)

근거 텍스트는 응답에 항상 포함한다(프론트에서 노출 → "랜덤이 아니라 AI 판단"임을 보여줌).

## 7. API 엔드포인트 (FastAPI)

- `GET /api/places` → 데모 장소 목록
- `POST /api/match` `{place_id}` → `{ tracks: [...], reasoning }`
- `POST /api/generate` `{place_id}` → `{ audio_url }` (보조, 실패 시 캐싱본 폴백)

## 8. 프론트엔드 동작

- 장소 선택(드롭다운 + 선택적 Leaflet 지도) → 매칭 결과 카드(곡명·장르·라이선스·매칭 근거) → HTML5 `<audio>` 재생.
- "맞춤 BGM 생성" 버튼은 보조. 미리 생성된 예시를 기본 노출, 라이브 생성은 1회 + 폴백.
  - 생성 프롬프트는 메타데이터에서 **고정 템플릿으로 조립**(`generation.py`). 예: `"{genre} music featuring {instruments}, {mood} atmosphere, traditional Korean (gugak), instrumental, ambient background"`. `traditional Korean / gugak / instrumental` 앵커를 반드시 넣어 현대 팝으로 새지 않게 한다.
- **자동재생(autoplay) 차단 대응 (데모 필수)**: `await fetch()`/`axios` 같은 비동기 호출이 끝난 *뒤* `audio.play()`를 부르면 브라우저가 사용자 제스처 콜스택으로 인정하지 않아 재생을 차단한다. 따라서 **클릭 즉시(동기적으로) 재생 권한을 먼저 확보**하는 패턴을 쓴다: 사용자가 장소를 클릭하면 그 자리에서 `audio.play()` → 즉시 `pause()`로 권한을 잠금 해제하고, 이후 `POST /api/match` 결과가 도착하면 `audio.src`만 교체해 `play()`한다. Web Audio 시각화를 쓰면 같은 클릭에서 `audioContext.resume()`도 호출. 발표 기기에서 코덱·재생 사전 점검.

## 9. 코딩 컨벤션

- Python: PEP 8, 함수에 타입힌트와 docstring. 매직 넘버 금지(상수화). 매핑표·규칙표는 별도 모듈/JSON로 분리.
- TypeScript: 함수형 컴포넌트 + Hooks. API 호출은 `src/api.ts`에 모은다.
- 기능 단위로 파일 분리. `main.py`에 로직 몰아넣지 않는다.
- 외부 호출 함수는 항상 타임아웃 + 예외 처리 + 폴백.

## 10. 안전 / 가드레일 (auto-continue 주의)

- **API 키는 backend `.env`에만.** 프론트엔드에 노출 금지, 절대 커밋 금지. `.env.example`만 커밋.
- `.gitignore`: `.env`, `data/audio/`, `data/raw/`(대용량), `__pycache__/`, `node_modules/`.
- 비밀키·개인정보·실데이터 커밋 금지.
- 파괴적 명령(`rm -rf`, force push, DB/파일 일괄 삭제)은 실행 전 사용자 확인을 받는다.
- 음악 생성은 라이선스 클린 모델만(§3). Suno/Udio 금지.

## 11. 구현 순서 (현재 단계)

- **Phase 1 (지금)**: `backend/prep/` 데이터 가공 → `places.json`(장소 임베딩 포함) / `tracks.json`(트랙 임베딩 포함) / `data/audio/` / `data/reasoning.json`(히어로 장소 근거).
- Phase 2: `matching.py`(지역+유형+의미+태그 가중합) + `POST /api/match`.
- Phase 3: 프론트 "장소 선택 → 결과 → 재생" 끝-끝 연결.
- Phase 4: 생성 보조(`generation.py`) + 폴백.
- Phase 5: 히어로 예시·근거 표시 다듬기 + 배포(백업·증빙).

> Phase 1~3만 완성돼도 발표 시연 요건(라이브 시연 가능)은 충족된다. Phase 4가 기술 임팩트(AI 활용)용.
