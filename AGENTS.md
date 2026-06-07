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
- **일반/캐주얼 사용자**: 시놉시스 작성 없이 **장소(또는 지도)만 클릭해 그 고장의 국악을 듣는** 보편 진입. 진입 장벽을 낮춰 1인 크리에이터·소상공인·교육·관광까지 활용 폭을 넓힌다. (활용성·포지셔닝 상세는 PRD.md.)
- 형태: 웹(반응형). 네이티브 앱은 만들지 않는다.
- 핵심 차별점: 분위기 추천(어플레이즈)도, 가상악기 제작(조선시리즈)도 아니다. **장소·맥락 정체성 ↔ 지역 문화 음원을 AI로 매칭** + **잠자던 공공 아카이브 활성화** + **이용조건이 명확해 그대로 쓸 수 있음**. (포지셔닝 상세는 PRD.md.)
- 문화 공공데이터를 핵심 엔진으로 사용한다.

## 2. 최우선 원칙 (모든 결정의 기준)

1. **시연 안정성 > 완성도.** 발표에서 라이브로 끊김 없이 돌아가는 게 최우선.
2. **히어로 핵심 흐름(예시 입력 → 매칭 → 재생/표시)은 외부 호출에 의존하지 않는다.** 히어로 장소·예시 시놉시스의 데이터·임베딩은 전부 사전 계산해 로컬에 둔다.
   - ⇒ §5의 데이터 소스 API는 전부 **수집용(1회성)**. 런타임 경로에 두지 않는다.
   - ⇒ 런타임 외부 호출은 **딱 두 곳만** 허용: ① 크리에이터 **자유 텍스트 입력**의 런타임 임베딩(§3), ② **생성 보조**(ElevenLabs Music → fal.ai, §3). **둘 다 try/except + 캐싱/폴백 필수**. 외부가 죽어도 히어로 데모는 멀쩡해야 한다(생성 실패 시 캐싱 매칭곡으로 폴백).
3. 히어로 예시(장소 3~4곳 + 시놉시스 3~4개)에서 확실히 작동하게 만든다. 전국/전체 커버리지보다 우선.

## 3. 기술 스택

- **Frontend**: React + Vite + TypeScript, Tailwind CSS. **지도 Kakao Map(JavaScript SDK, 한국 장소 라벨·커버리지 우수) — 전국 8도 소리 지도(§8) 일반 모드 진입 UI로 채택(구현 Phase 6).** React 연동은 `react-kakao-maps-sdk` 권장. 점수 시각화 **레이더 차트 = recharts `RadarChart`**(게이지 대체).
- **Kakao Map (데모 주의)**: JS SDK는 `//dapi.kakao.com/v2/maps/sdk.js?appkey=<JS키>&autoload=false` 로드 후 `kakao.maps.load(cb)` 패턴(또는 `react-kakao-maps-sdk`). **Kakao Developers에 [플랫폼 > Web] 사이트 도메인 등록 필수** — 로컬 `http://localhost:5173` + 배포 도메인. 미등록 시 지도 안 뜸. 좌표는 WGS84 `new kakao.maps.LatLng(lat,lng)`로 §5.4와 일치. SDK 로드는 **Phase 6 한정**이라 히어로 경로(§2)엔 영향 없음 — 로드 실패 시 리스트 뷰 폴백.
  - **`MarkerClusterer` 금지**: `react-kakao-maps-sdk` + Kakao clusterer 1.1.1 비호환(마커 추가 시 내부 예외 → React 앱 전체 크래시). `libraries:["clusterer"]`로 제대로 로드해도 동일. 대신 **마커를 직접 렌더**하되 `MARKER_VISIBLE_LEVEL`(=12) **이하로 확대했을 때만 표시**(레벨 기반 게이팅, `level <= MARKER_VISIBLE_LEVEL && pts.map(...)`). 전국(레벨 13)은 권역 폴리곤만 + "확대하면 마커" 힌트.
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
- **LLM 근거(선택, prep 단계 우선)**: provider-agnostic, env 주입. **히어로 조합 근거는 prep 스크립트(`prep/generate_reasoning.py`)에서 LLM으로 `reasoning.json`에 미리 굽는다(런타임 호출 아님 — §2·§6).** 키 없거나 prep 미실행 시 유사도 + 템플릿 근거로 자동 대체. 런타임 LLM은 쓰더라도 자유 텍스트 경로 한정 + 타임아웃·템플릿 폴백 필수, 히어로 경로 제외.
- **음악 생성(보조)**: 공급자 체인 **ElevenLabs Music API(1순위) → fal.ai stable-audio(2순위) → None(캐싱 매칭곡 폴백)**. `generation.py`가 키 유무·성공 여부로 순차 시도.
  - **ElevenLabs Music**(현재 활성): 유료 Starter 플랜 필요(무료 티어는 402 Payment Required). `POST https://api.elevenlabs.io/v1/music`, body `{prompt, music_length_ms, model_id:"music_v1"}`, **mp3 바이트를 그대로 반환**(호스팅 URL 아님) → `data/audio/`에 저장 후 `/audio/<file>` 반환. 상업 라이선스는 플랜 보유자(앱 소유자)에 귀속 → 생성물은 "개인적 사용" 크레딧으로 표기.
  - **프롬프트 합성(`build_prompt`)**: `[사용자 자유 입력(선택, ≤200자)] + [장소 cultural_keywords→영어] + [매칭곡 악기/장르/무드→영어] + [고정 앵커: traditional Korean(gugak)·instrumental·ambient]`. 한글 통제어휘는 generation.py 내 영어 매핑 dict로 변환(ElevenLabs는 영어 이해도가 높음). **장소 정보가 매칭곡 선택뿐 아니라 프롬프트에도 직접 반영**된다.
  - **프롬프트 해시 캐싱**: 같은 프롬프트(=같은 place/track/사용자텍스트)는 1회만 생성하고 `gen_*.mp3` 재사용 → 크레딧 절약. 사용자 텍스트가 다르면 캐시 미스=새 생성=과금.
  - **무료 경로는 막혀 있음(재시도 금지)**: ElevenLabs 무료=402, fal.ai 잔액0=403, HF Inference는 MusicGen 미지원("Model not supported by provider hf-inference")+구 엔드포인트 폐기.
  - **Suno / Udio 금지**(상업 라이선스 불명확, "라이선스 클린" 포지셔닝과 상충).
- **데이터 저장**: DB 없이 JSON + 로컬 오디오. 필요 시 SQLite.
- **오디오 서빙**: `data/audio/`는 FastAPI `app.mount("/audio", StaticFiles(...))`로 `/audio/<file>.mp3` 서빙. `tracks.json`의 `audio_path`를 URL과 일치.
- **패키지**: frontend = npm, backend = pip + venv.

### 3.1 실행 명령 (로컬)

```bash
cp .env.example .env                              # 키 채우기 (§10). HF_API_KEY 넣으면 768차원, 비우면 키워드 폴백
cd backend && python -m venv venv
venv\Scripts\activate                             # Windows; Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
cd ../frontend && npm install
cd ../backend && python prep/generate_data.py     # 장소4 + 민요24(CSV) + 정악8(공유마당) + 768차원 임베딩 → places/tracks.json
python prep/download_audio.py                     # 음원 다운로드: 민요=wav 30초 트림, 정악=mp3 전체 (ffmpeg 불요) → data/audio/
uvicorn main:app --reload --port 8000
cd ../frontend && npm run dev                     # http://localhost:5173
```

## 4. 디렉터리 구조

```
project-root/
├── AGENTS.md           # 빌드/실행 규칙
├── .env.example
├── .gitignore
├── 재단법인국악방송_전국8도민요MR_20240301.csv  # 국악방송 원본 데이터 (105곡, EUC-KR)
├── data/
│   ├── raw/gongu_sound.json  # 공유마당 음원 5423건 메타 (정악 큐레이션 소스)
│   ├── places.json     # {meta, places:[히어로4 + TourAPI수집 → 총 234곳]} + image_url/copyright + 768차원 임베딩 ✅ (dict 포맷)
│   ├── tracks.json     # {meta, tracks:[32곡]} 정악8(공유마당)+민요24(국악방송) ✅
│   ├── reasoning.json  # 히어로 조합 근거 — prep/generate_reasoning.py로 신 트랙 id 기준 재생성 완료 (템플릿 폴백 보유) ✅
│   └── audio/          # igbf_*.wav 24(30초 트림) + gongu_*.mp3 8(정악) + gen_*.mp3(ElevenLabs 생성 캐시) — gitignore ✅
│   [미생성] synopsis_examples.json  # 히어로 예시 시놉시스 + 사전 임베딩
├── backend/
│   ├── main.py         # FastAPI (CORS, StaticFiles, 임베딩 가드, /api/places·places/suggest·match·generate) ✅
│   ├── matching.py     # 하이브리드 매칭 (4신호 가중합, 차원 무관, weights 오버라이드 지원) ✅
│   ├── embeddings.py   # HF Inference(768)+키워드 폴백(34) + embed_query(런타임) + 코사인 + dict 로더 ✅
│   ├── licensing.py    # 라이선스 → commercial_ok/derivative_ok 파생 + use_case 필터 ✅
│   ├── generation.py   # BGM 생성: ElevenLabs Music(1순위)+fal.ai(2순위) + 프롬프트 합성(장소·매칭곡·사용자입력→영어) + 해시 캐싱 + 폴백 ✅
│   ├── rules.py        # 지역 권역 매핑 + 장소 유형별 장르 가중 (단일 파일) ✅
│   ├── prep/
│   │   ├── generate_data.py   # 장소 + CSV→민요24 + 공유마당→정악8 + 임베딩 → dict JSON ✅
│   │   ├── download_audio.py  # wav=Range 30초 트림 / mp3=전체 다운로드 (순수 파이썬) ✅
│   │   ├── collect_places.py  # TourAPI 키워드 수집(+ detailCommon2.firstimage → image_url/image_copyright) → data/raw ✅
│   │   ├── generate_reasoning.py  # 히어로 조합 LLM 근거 → reasoning.json (prep, 런타임 아님) ✅
│   │   ├── probe_missing_images.py # (진단, 1회성) image_url 빈 장소를 detailImage2로 보완 조회 ✅
│   │   └── patch_recovered_images.py # (1회성) 위 결과를 places.json에 기록 ✅
│   [미생성] tests/     # 매칭/라이선스 스모크 테스트
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.tsx                    # 자유텍스트+장소선택·매칭결과·필터·재생 ✅
│       ├── api.ts                     # fetchPlaces·fetchPlaceSuggestions·fetchMatch·fetchMatchByText·fetchGenerate ✅
│       └── components/
│           ├── SynopsisSearch.tsx     ✅ (자유 시놉시스·무드 입력)
│           ├── PlaceSelector.tsx      ✅ (검색 + 빈 결과 시 의미 기반 연관 장소 추천)
│           ├── TrackCard.tsx          ✅ (재생·라이선스·ScoreBar·다운로드 버튼)
│           ├── AttributionModal.tsx   ✅ (출처표시 복사 + 다운로드 + 면책)
│           ├── ScoreBar.tsx           ✅
│           ├── ScoreRadar.tsx         ✅ (recharts 레이더, 4 component 시각화, §8)
│           ├── RegionSoundMap.tsx     ✅ (Kakao Map 전국 소리 지도 = 일반 모드 진입, 마커 직접 렌더·줌 게이팅, §8)
│           └── GenerateBGM.tsx        ✅ (사용자 프롬프트 입력 + 라이선스 복사 버튼)
└── (PRD.md, README.md 미생성)
```

## 5. 데이터 (문화 공공데이터)

전부 무료 공공데이터. `data/raw/`에 보관하고 `backend/prep/`로 정제. **수집용(1회성), 런타임 경로에 두지 않는다(§2).**

> ⚠️ **출품 자격**: data.go.kr / 문화공공데이터광장(culture.go.kr/data) / 문화 빅데이터 플랫폼(bigdata-culture.kr) 개방 데이터 **1종 이상** 필수. 국립국악원(15097515)·국가유산청(3070426)·TourAPI(15101578)가 data.go.kr 소스라 충족. `source`에 포털·데이터셋 ID 증빙 기록. 공유마당은 세 포털 등록 여부 불확실 → "추가 음원"으로만 취급.

### 5.1 장소 소스

| 소스 | 위치 | 형식 | 비고 |
| --- | --- | --- | --- |
| 국가유산청_문화재 공간 정보 | data.go.kr/data/3070426 | XML | 좌표·유형·설명. 지정유산 장소 1차 소스. |
| 한국관광공사 TourAPI(국문) | data.go.kr/data/15101578 | XML/**JSON** | EndPoint `apis.data.go.kr/B551011/KorService2`. `&_type=json`. 관광지·문화시설·축제·전통시장. |
| (지정유산 상세, 선택) | 국가유산포털(khs.go.kr) | XML | 구 문화재청 엔드포인트 폐기 → 현재 명세 재확인. |

> **TourAPI 수집 방식(확정, `collect_places.py`로 구현 예정)**: 지역 훑기(잡음 많음) 대신 **키워드 검색**으로 문화 색 뚜렷한 장소만 수집. 키워드: 한옥마을·서원·민속마을·전통시장·향교·고궁·종갓집.
> - `/searchKeyword2` (목록: title·mapx/y·contenttypeid·addr1) → 장소별 `/detailCommon2` (overview=설명) 2단계 호출.
> - **type 매핑**: contenttypeid(숫자, 너무 거침)만으론 궁궐/한옥마을 구분 불가 → 제목 키워드로 `TYPE_GENRE_WEIGHTS` 키 추론. 미스 시 generic(유형 점수 0, 지역+의미로 매칭).
> - **cultural_keywords**: type별 템플릿으로 자동 생성(LLM 불필요). music_region은 addr1 → `rules.REGION_MAP`. 좌표 WGS84.
> - **TOURAPI_KEY**(.env, Decoding 키) 대기 중. 수집 장소는 generate_data가 hero 4곳과 함께 자동 임베딩.

### 5.2 음원 소스 — 역할 구분 (중요)

| 소스 | 위치 | 역할 | 형식 |
| --- | --- | --- | --- |
| 공유마당 자유이용 음원 | gongu.copyright.or.kr (Key 즉시 발급) | **재생용 완성곡(주력)** + 라이선스 필드 | XML |
| 국악방송 공공개방음원 | igbf.kr → data.go.kr 경유 | **재생용 완성곡** | 파일 다운로드(공공누리) |
| 국립국악원 국악디지털음원 | data.go.kr/data/15097515 | **크리에이터 편집용 프리셋 사운드 소스 / 샘플 루프 / instruments 태그** | OpenAPI(Swagger) |

> 국립국악원 "디지털음원"은 완성 BGM이 아니라 악기 단음(약 407) + 악구 루프(약 2,226)인 **샘플**이다. 완성곡 재생 대상으로 쓰지 말 것. 대신 **크리에이터가 영상에 얹는 편집용 사운드 소스/루프**로 제공하면 가치가 살아난다(1차 타깃과 정합). 생성 소스·`instruments` 태그로도 사용.

### 5.3 정제 산출물 스키마

- `places.json`: `{ id, name, region, music_region, type, lat, lng, description, cultural_keywords, source, source_url, image_url, image_copyright, embedding }`
  - `image_url`·`image_copyright`: TourAPI 대표 이미지(공공누리 코드 Type1~4). 빈 값이면 프론트가 유형별 폴백 이미지 사용. 모든 place에 `lat`/`lng` 존재(좌표 없으면 collect_places.py가 제외 → 지도 마커 100% 커버).
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

**매칭은 항상 라이브 계산 — 하드코딩 금지.** 근거 텍스트만 사전 생성 가능: 히어로(장소+예시 시놉시스)는 **`prep/generate_reasoning.py`가 LLM으로 구운 `reasoning.json`**(런타임 호출 아님 — §2 시연 안정성), 그 외는 템플릿 폴백. LLM 키/파일 없으면 템플릿으로 자동 강등. 근거는 응답에 **항상 포함**.

## 7. API 엔드포인트 (FastAPI)

- `GET /api/places` → 데모 장소 목록 (좌표·지역 포함 → 전국 소리 지도 §8의 마커 소스)
- `GET /api/places/suggest?q=&k=3` → 검색어 임베딩 ↔ 보유 장소 코사인 → 의미 가까운 장소 + `similarity`. **구현됨** (없는 장소 검색 시 연관 장소 추천). `embed_query` 사용(런타임 임베딩, 폴백 보유).
- `GET /api/examples` → 히어로 예시 시놉시스 목록(사전 임베딩) — **미구현**(프론트 하드코딩 칩으로 대체)
- `POST /api/match` `{ place_id? , query_text? , use_case }` → `{ place, tracks: [...] }` (각 track에 `reasoning` 포함)
  - **구현 주의**: 실제 응답 필드는 `score`(최종) + `score_detail{region,type,semantic,tag}` (위 예시의 `final_score`/`scores`와 명칭 다름). query_text 경로는 weights=(0,0,0.8,0.2) 재정규화.
  - `query_text`가 오면 §3 런타임 임베딩(HF Inference, 폴백 보유). `place_id`면 사전 임베딩 사용.
  - 각 트랙은 **최종 점수 + 정규화된 4개 component 점수 분리**(레이더 시각화 전제) + 라이선스 파생값:
    ```json
    { "track_id":"t01", "final_score":0.87,
      "scores":{"region":0.30,"type":0.25,"semantic":0.85,"tag":0.60},
      "asset_kind":"sample_loop", "license_type":"공공누리 제1유형",
      "commercial_ok":true, "derivative_ok":true, "source":"국립국악원",
      "audio_url":"/audio/t01.mp3", "reasoning":"..." }
    ```
- `POST /api/generate` `{ place_id, prompt? }` → `{ audio_url, generated, license, prompt_used? | fallback_title? }` (보조)
  - `prompt`: 사용자 자유 입력(선택). 장소·매칭곡 정보와 합쳐져 생성 프롬프트가 됨(§3 `build_prompt`).
  - `generated=true`(AI 생성) 또는 `false`(생성 실패 → `is_derivative_allowed` 음원 중 재생 가능한 최적 매칭으로 폴백).
  - `license`: 복사용 출처/이용 정보. 생성물=「AI 생성(ElevenLabs Music)·개인적 사용」, 폴백=카탈로그곡 실제 CC/공공누리 출처표시.

## 8. 프론트엔드 동작

- 입력 3-모드: **(A) 예시 시놉시스/장소 선택(히어로, 안정)** + **(B) 자유 텍스트 입력(크리에이터 핵심, 폴백 보유)** + **(C) 장소 한 클릭/지도 클릭(일반·캐주얼, 가장 낮은 진입 장벽)**. (C)는 시놉시스 없이 `place_id`만으로 즉시 매칭→재생 — 신규 백엔드 불요(`POST /api/match {place_id}` 재사용). 무드/use_case 토글.
- **전국 8도 소리 지도((C)의 메인 UI)**: Kakao Map에서 권역 폴리곤/장소 마커 클릭 → 그 고장의 국악 매칭·재생. `GET /api/places`(좌표·지역) + `POST /api/match {place_id}` 재사용, `rules.py` 권역 매핑·`전국8도민요` 데이터 활용. **마커/인포윈도우는 API 응답으로 렌더(하드코딩 금지)**, 좌표는 WGS84(§5.4). **Kakao SDK 로드 실패 시 리스트 뷰로 폴백**(흰 화면 금지).
  - **마커 표시 = 줌 게이팅**: `MarkerClusterer`(SDK 비호환, §3) 대신 마커를 직접 렌더하되 `MARKER_VISIBLE_LEVEL`(=12) 이하로 확대했을 때만 표시. 전국 뷰는 폴리곤만 보여 깔끔하게 두고, 한 번 확대하면 마커가 나타난다.
- **맞춤 BGM 생성(보조, `GenerateBGM`)**: 장소 상세에서 "생성하기" → `POST /api/generate`. **사용자 자유 프롬프트 입력칸**(선택, ≤200자) 제공 — 장소·매칭곡 정보와 합쳐져 생성에 반영(§3·§7). 결과에 **라이선스/출처 배지 + 📋 복사 버튼**(생성물=개인적 사용, 폴백=카탈로그곡 실제 출처표시). 생성 실패 시 매칭 음원 폴백 안내.
- 결과 카드: 곡명·장르·`asset_kind`(완성곡/편집 루프)·**라이선스·출처**·매칭 근거. `sample_loop`은 "편집용 다운로드", `full_track`은 재생 중심.
- **매칭 점수 시각화 = 레이더 차트(확정)**: `/api/match`의 4 component(지역·유형·의미·태그)를 **recharts `RadarChart`(`ScoreRadar.tsx`)**로 노출해 "데이터가 라이브 계산 중"임을 시각적으로 증명(AI 가시화). ScoreBar는 보조/모바일 폴백으로 유지. **반드시 API 응답값으로 그린다(프론트 하드코딩 금지).**
- **악기 태그 시각화(B-1)**: 재생 중 곡의 `instruments` 태그에 해당하는 전통 악기(가야금·거문고·해금·태평소 등) 아이콘/트랙 바를 활성화. ⚠️ 이는 **메타데이터(태그) 기반 표시이지 실시간 오디오 분리(stem separation)가 아니다.** "이 곡에 포함된 악기(메타 기준)"로만 표기하고, AI가 음원을 분해하는 것처럼 보이게 하지 않는다.
- **라이선스 안전 UX = 시연의 핵심 차별 포인트(전면 배치).** 곡별 **3-state 배지**로 한눈에: `수익화 OK/불가`(`commercial_ok`) · `편집 OK/불가`(`derivative_ok`) · `출처표시 필수`(항상). 곡별 실제 값으로 렌더(`license_type` 그대로 표시), "전 곡 상업 가능" 식 하드코딩 금지. **출처표시는 법적 의무**라 항상 노출. (일반 음원 라이브러리 대비 차별 근거는 PRD.md.)
- **다운로드(크리에이터)**: `use_case=creator` 통과 음원만 다운로드 허용. 다운로드/선택 시 **출처표시 카피 가이드(A-1)**를 팝업으로 제공 — `attribution_text`를 **원클릭 복사**해 유튜브 더보기란에 그대로 붙일 수 있게 한다(**"붙여넣기만 하면 법적 의무 끝" = 시연 클라이맥스**; 출처표시는 법적 의무이므로 이행을 적극 유도). ※ "안심 보증서/라이선스 인증" 같은 법적 면책을 약속하는 문서는 발급하지 않는다(보증할 수 없는 영역).
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
- **Kakao Map JS 키 = 위 "프론트 노출 금지"의 명시적 예외.** Kakao Developers의 여러 키 중 **JavaScript 키**를 쓰며, 이 키는 *설계상 클라이언트(브라우저)에 노출*된다 — 비밀이 아니라 **도메인 등록(플랫폼>Web)**으로 보호. 하드코딩·커밋은 여전히 금지: Vite 환경변수(`import.meta.env.VITE_KAKAO_MAP_KEY`)로 주입하고 `.env`는 gitignore. (REST/Admin 키는 절대 프론트에 두지 말 것 — 그건 backend 전용.)
- `.gitignore`: `.env`, `data/audio/`, `data/raw/`, `__pycache__/`, `node_modules/`.
- 파괴적 명령(`rm -rf`, force push, 일괄 삭제)은 실행 전 사용자 확인.
- 음악 생성은 라이선스 클린 모델만. Suno/Udio 금지.

## 11. 구현 순서 & Definition of Done

> 스코프 주의: **매칭 엔진(Phase 2)을 먼저 완성**한 뒤 입력 레이어(자유 텍스트)·다운로드를 얹는다. 마감 대비 한 번에 피벗하지 말 것.

- **Phase 1 — 데이터 준비** ✅ 완료 (실제 재생 + 768차원 의미 매칭)
  - ✅ places.json (4곳), tracks.json (**32곡 = 정악8 + 민요24**)
  - ✅ **실제 재생 가능 음원 32개** — 사용자가 수동으로 파일 넣을 필요 없음:
    - 민요 24곡: 국악방송 wav 원본 → `download_audio.py` 순수 파이썬 Range 30초 트림 → `igbf_*.wav` (ffmpeg 불요)
    - 정악 8곡: 공유마당 «국악연주곡_» (여민락·영산회상·가곡 등) mp3 전체 다운로드 → `gongu_*.mp3` (mp3는 압축이라 트림 불가, 전체 받음)
  - ✅ 라이선스 검증: 민요=**공공누리 제1유형**, 정악=**CC BY** → `commercial_ok`/`derivative_ok`/`attribution_text` 파생
  - ✅ `asset_kind`, `embedding_model`·`embedding_dim`·`embed_text_recipe` 파일 레벨 메타 (dict 포맷)
  - ✅ **임베딩 768차원 ko-sroberta 적용** (HF_API_KEY 설정됨). HF 미설정 시 키워드 폴백(34차원)으로 자동 강등. 빌드 시 모드 1회 결정 → places·tracks 차원 일관.
    - ⚠️ HF 주의: ko-sroberta는 task가 `sentence-similarity`라 `router.huggingface.co/hf-inference/.../pipeline/feature-extraction` 호출 + **Inference 권한 있는 토큰(Write)** 필요. 구 `api-inference.huggingface.co`는 폐기됨.
  - ✅ **매칭 검증**: 경복궁(궁궐)→여민락·영산회상(정악), 전주→호남민요, 남대문→경기민요, 하회→민요(유형). 지역+유형+의미 모두 기여.
  - ✅ `synopsis_examples.json`은 프론트엔드 하드코딩 칩으로 간소화하여 대체 완료
  - ✅ `reasoning.json` 은 `prep/generate_reasoning.py`를 통해 신 트랙 ID 체계에 맞게 사전 생성 완료 (LLM 및 템플릿 폴백)

- **Phase 2 — 매칭 엔진** ✅ 완료
  - ✅ `matching.py`: 4신호 가중합 (지역 30% + 유형 25% + 의미 30% + 태그 15%), `[0,1]` 정규화
  - ✅ `rules.py`: 지역 권역 매핑 + 장소 유형별 장르 가중
  - ✅ `licensing.py`: `commercial_ok`/`derivative_ok` 파생 + `use_case` 필터
  - ✅ `POST /api/match` (place_id 경로), 점수순·근거 포함, 하드코딩 없음
  - ❌ `backend/tests/` 없음 — 매칭·라이선스 스모크 테스트 미작성 (시연용 API 동작으로 대체 검증)

- **Phase 3 — 프론트 끝-끝 + 자유 텍스트 입력** ✅ 핵심 경로 완료
  - ✅ 장소 선택 → 매칭 결과 → 재생 (end-to-end 동작)
  - ✅ **자유 텍스트 입력(query_text) 구현** — `SynopsisSearch` 컴포넌트 + `POST /api/match {query_text}` + 런타임 HF 임베딩(`embed_query`). 예시 칩·Ctrl+Enter. 검증: "비 내리는 한옥…" → 영산회상(정악).
  - ✅ 자유 텍스트는 지역·유형 신호 없어 의미·태그 가중(0,0,0.8,0.2) 재정규화 (matching.match weights 파라미터)
  - ✅ HF Inference 런타임 임베딩 연동 (실패 시 키워드 폴백)
  - ✅ 장르 필터 칩 + "수익화 가능만 보기" 체크박스
  - ✅ 라이선스 배지 (`commercial_ok`·`derivative_ok` 실제값 기반)
  - ✅ ScoreBar (4개 component 점수 시각화) — 보조/모바일 폴백으로 유지
  - ✅ autoplay 잠금 해제 패턴, 빈 결과·에러 상태 처리
  - ✅ **다운로드 + 출처표시 팝업** (`AttributionModal`) — 수익화+편집 가능 음원만 다운로드 버튼 활성, 클릭 시 `attribution_text` 복사 가이드 + 파일 다운로드. "보증서 미발급" 면책 문구 포함 (AGENTS.md §8 준수).
  - ✅ **의미 기반 연관 장소 추천** — `GET /api/places/suggest` + PlaceSelector 빈 결과 시 디바운스 호출. 없는 장소 검색 시 가까운 보유 장소 칩 제안(예: "북촌 한옥마을"→전주 한옥마을 84%). 장소가 늘면 품질 향상.
  - ✅ `GET /api/examples` 대신 프론트 하드코딩 예시 칩 활용
  - ✅ 레이더 차트(`ScoreRadar.tsx`, recharts) — `ScoreRadar` 컴포넌트 구현 및 매칭 점수 세부 항목(지역·유형·의미·태그) 가시화 완료. ScoreBar는 모바일/폴백용으로 유지.

- **Phase 3.5 — 장소 확장 (TourAPI 수집)** ✅ 완료
  - ✅ `collect_places.py` 구현 완료 — 키워드 기반 한옥마을, 서원, 향교 등 문화 명소 약 200여 곳 수집 및 raw 데이터 생성.
  - ✅ `generate_data.py` 연동 완료 — 수집 장소에 임베딩 자동 부여 및 `places.json` 병합 완료. 연관 장소 추천 품질 향상.

- **Phase 4 — 생성 보조** ✅ 완료
  - ✅ `generation.py`: 공급자 체인 **ElevenLabs Music(1순위, 유료 Starter 활성) → fal.ai stable-audio(2순위) → 캐싱 매칭곡 폴백**
  - ✅ 프롬프트 합성(`build_prompt`): 사용자 자유 입력 + 장소 키워드 + 매칭곡 메타를 영어로 결합, 프롬프트 해시 캐싱(크레딧 절약)
  - ✅ `POST /api/generate` 구현(`prompt` 입력 + `license` 응답), `is_derivative_allowed=false` 제외
  - ✅ ElevenLabs 실제 생성 검증(브라우저), 키/잔액/네트워크 장애 시 매칭 음원 폴백 처리 적용 완료

- **Phase 4.5 — AI 가시화 (레이더 + prep LLM 근거)** ✅ 완료
  - ✅ `ScoreRadar.tsx`(recharts `RadarChart`) — 4개 component 점수(지역·유형·의미·태그)를 레이더 차트로 라이브 렌더링.
  - ✅ `prep/generate_reasoning.py` — 히어로 조합 근거를 LLM/템플릿으로 사전 계산하여 `reasoning.json` 신 트랙 ID 기준 재생성 완료.

- **Phase 5 — 다듬기·배포** ✅ 완료
  - ✅ **라이선스 안전 UX 전면 배치(§8)** — `AttributionModal` 기반 3-state 배지 + 원클릭 출처 복사 시연용 가이드 팝업을 전면 배치하여 신뢰성 강화.
  - ⚠️ 무료 티어 디스크 ephemeral → 오디오는 빌드/리포 포함 필요. 라이브 시연 리허설 + 로컬 백업.

- **Phase 6 — 일반 모드 + 전국 8도 소리 지도** ✅ 완료
  - ✅ (C) 장소 한 클릭/권역 선택 모드 구현 완료 (시놉시스 입력 없이 `POST /api/match {region/place_id}` 호출)
  - ✅ `RegionSoundMap.tsx`(Kakao Map JS SDK 활용) 구현 완료 — 전국 5대 권역 폴리곤 클릭 시 토리 정서 매칭곡 추천, 장소 마커 클릭 시 장소 국악 매칭·재생. SDK 로드 실패 시 리스트 뷰로 자동 폴백.
  - ✅ **마커 줌 게이팅** — `MarkerClusterer`는 SDK 비호환으로 제거(§3), 마커를 직접 렌더하되 확대(`MARKER_VISIBLE_LEVEL`=12 이하) 시에만 표시. 전국 234곳 모두 좌표 보유.

- **Phase 7 — (보류) 사진 → 분위기 추출 → 음원 멀티모달 입력** ⏸️ (보류 상태 유지)
  - 사용자가 공간 사진 업로드 → 비전 모델이 분위기·정체성 추출 → 국악 매칭. AI 차별화 임팩트는 크나 외부 호출과 데모 안정성을 위해 우선 보류.

> **현재 시연 가능 범위**: 백엔드+프론트 기동 후 장소 선택 → 매칭 결과 표시까지. 음원 파일(`data/audio/`)이 없으면 재생 버튼은 렌더링되지만 소리가 나지 않는다.
> Phase 1~3 완료 시 라이브 시연 요건 충족. Phase 4·4.5가 기술 임팩트(AI 활용·가시화), Phase 6이 활용성(일반 모드·소리 지도) 보강용. Phase 7은 보류(전체 완료 후 선택).