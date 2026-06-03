# GugakPlace

장소의 문화 정체성 ↔ 공공 국악 음원을 AI로 매칭·재생하는 웹 서비스.

## 빠른 시작

### 1. 백엔드

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

`http://localhost:8000/health` 에서 상태 확인 가능.

### 2. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173` 에서 서비스 접속.

### 3. 데이터 재생성 (선택)

```bash
cd backend
python prep/generate_data.py
```

## 구조

```
data/
  places.json       히어로 장소 4곳 + 임베딩
  tracks.json       국악 트랙 13곡 + 임베딩
  reasoning.json    사전 생성 매칭 근거
  audio/            음원 파일 (직접 준비 필요 — .gitignore)
backend/
  main.py           FastAPI 엔트리포인트
  matching.py       하이브리드 매칭 엔진
  embeddings.py     임베딩 로드 / 코사인 유사도
  generation.py     BGM 생성 + 폴백
  prep/             오프라인 데이터 가공 스크립트
frontend/
  src/App.tsx       메인 UI
  src/api.ts        API 클라이언트
  src/components/   PlaceSelector, TrackCard, ScoreBar, GenerateBGM
```

## 음원 파일 준비

`data/audio/` 에 아래 파일명으로 mp3를 직접 넣어주세요.
국립국악원 디지털음원(CC BY), 국악방송 공개음원 등을 사용하세요.

| 파일명 | 곡 |
|--------|-----|
| sujecheon.mp3 | 수제천 |
| yeomillak.mp3 | 여민락 |
| jongmyo.mp3 | 종묘제례악 |
| hahoe_byeolsingut.mp3 | 하회별신굿 무가 |
| gyeonggi_minyo.mp3 | 경기 민요 모음 |
| yeongnam_minyo.mp3 | 경상도 민요 모음 |
| pansori_chunhyang.mp3 | 춘향가 |
| gayageum_sanjo.mp3 | 가야금 산조 |
| honam_nongak.mp3 | 호남 농악 |
| samulnori.mp3 | 사물놀이 |
| pungmul.mp3 | 풍물굿 |
| gagok.mp3 | 가곡 |
| daegeum_sanjo.mp3 | 대금 산조 |

## 매칭 가중치

| 신호 | 가중치 |
|------|--------|
| 지역 적합도 | 30% |
| 유형 적합도 | 25% |
| 의미 임베딩 유사도 | 30% |
| 태그 적합도 | 15% |
