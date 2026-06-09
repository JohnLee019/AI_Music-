import { useEffect, useState } from "react";
import { Map, MapMarker, Polygon, useKakaoLoader } from "react-kakao-maps-sdk";
import type { Place } from "../api";
import { REGION_COLOR, REGION_META, REGION_POLYGONS } from "../data/regionGeo";

// Kakao JS 키 (클라이언트 노출 설계 — AGENTS.md §10). frontend/.env 의 VITE_KAKAO_MAP_KEY.
const KEY = import.meta.env.VITE_KAKAO_MAP_KEY;
const KOREA_CENTER = { lat: 36.4, lng: 127.9 };
// 이 지도 레벨 "이하"(=더 확대)에서만 개별 장소 마커를 표시한다. Kakao 레벨은
// 숫자가 작을수록 확대. 기본(전국, 레벨 13) 화면은 권역 폴리곤만 보이고,
// 한 번만 확대(레벨 12↓)하면 곧바로 핀이 나타난다. (10으로 두면 3단계나 확대해야
// 핀이 보여 "확대해도 안 나온다"는 혼동이 있었음 → 12로 완화.)
const MARKER_VISIBLE_LEVEL = 12;

interface Props {
  places: Place[];
  selected: Place | null;
  onSelect: (p: Place) => void;
  onRegionSelect: (regionKey: string) => void;
  loading: boolean;
}

function Fallback({ reason }: { reason: string }) {
  // SDK 로드 실패/키 미설정 시 흰 화면 대신 안내 (AGENTS.md §8: 리스트 폴백)
  return (
    <div className="py-10 text-center text-sm text-stone-400 rounded-xl border border-dashed border-stone-200">
      <div className="text-2xl mb-2">🗺️</div>
      <p>지도를 불러올 수 없습니다 ({reason}).</p>
      <p className="mt-1 text-xs">‘목록’ 보기에서 장소를 선택해 주세요.</p>
    </div>
  );
}

export default function RegionSoundMap(props: Props) {
  // 키가 없으면 SDK 훅을 호출하지 않고 폴백 (훅 순서 일관성 위해 래퍼 분리)
  if (!KEY) return <Fallback reason="지도 키 미설정" />;
  return <MapInner {...props} />;
}

function MapInner({ places, selected, onSelect, onRegionSelect, loading }: Props) {
  const [, error] = useKakaoLoader({ appkey: KEY as string });
  const pts = places.filter((p) => typeof p.lat === "number" && typeof p.lng === "number");

  const [center, setCenter] = useState(KOREA_CENTER);
  const [level, setLevel] = useState(13);

  useEffect(() => {
    if (selected && typeof selected.lat === "number" && typeof selected.lng === "number") {
      setCenter({ lat: selected.lat, lng: selected.lng });
      setLevel(5);
    } else {
      setCenter(KOREA_CENTER);
      setLevel(13);
    }
  }, [selected]);

  if (error) return <Fallback reason="지도 SDK 로드 실패" />;

  return (
    <div className="rounded-xl overflow-hidden border border-stone-200">
      <Map
        center={center}
        level={level}
        style={{ width: "100%", height: "540px" }}
        onDragEnd={(map) => {
          const latlng = map.getCenter();
          setCenter({ lat: latlng.getLat(), lng: latlng.getLng() });
        }}
        onZoomChanged={(map) => {
          setLevel(map.getLevel());
        }}
      >
        {/* 음악 권역(토리) 색상 폴리곤 — 클릭하면 그 고장의 소리를 추천 */}
        {REGION_POLYGONS.map((poly, i) => {
          const color = REGION_COLOR[poly.regionKey];
          return (
            <Polygon
              key={`${poly.regionKey}-${poly.province}-${i}`}
              path={poly.path}
              fillColor={color}
              fillOpacity={0.32}
              strokeColor={color}
              strokeWeight={1.5}
              strokeOpacity={0.85}
              onClick={() => { if (!loading) onRegionSelect(poly.regionKey); }}
              onMouseover={(target) => target.setOptions({ fillOpacity: 0.5 })}
              onMouseout={(target) => target.setOptions({ fillOpacity: 0.32 })}
            />
          );
        })}

        {/* 개별 장소 마커 — 확대(MARKER_VISIBLE_LEVEL 이하)했을 때만 직접 렌더.
            (MarkerClusterer 는 react-kakao-maps-sdk 와 Kakao clusterer 1.1.1 간 호환 문제로
            마커 추가 시 내부 예외 → 앱 크래시가 나서 제거함. 대신 레벨 기반으로 표시를 제어한다.) */}
        {level <= MARKER_VISIBLE_LEVEL && pts.map((p) => (
          <MapMarker
            key={p.id}
            position={{ lat: p.lat as number, lng: p.lng as number }}
            title={p.name}
            onClick={() => { if (!loading) onSelect(p); }}
          />
        ))}
      </Map>

      {/* 범례 — 권역색·토리. 칩 클릭도 권역 추천 */}
      <div className="px-3 py-2.5 bg-stone-50 border-t border-stone-200">
        <div className="flex flex-wrap gap-1.5">
          {REGION_META.map((r) => (
            <button
              key={r.key}
              onClick={() => { if (!loading) onRegionSelect(r.key); }}
              disabled={loading}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-stone-200
                         bg-white text-xs text-stone-600 hover:border-stone-400 transition-colors
                         disabled:opacity-50"
              title={`${r.label} · ${r.tori}`}
            >
              <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: r.color }} />
              <span className="font-medium">{r.label}</span>
              <span className="text-stone-400">{r.tori}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-stone-500">
          🎨 권역(토리)을 클릭하면 그 고장의 소리를, 📍 마커를 클릭하면 그 장소의 국악을 매칭합니다 · 총 {pts.length}곳
          {level > MARKER_VISIBLE_LEVEL && <span className="text-stone-400"> · 🔍 확대하면 장소 마커가 나타납니다</span>}
          {selected && <span className="text-jade font-medium"> · 선택: {selected.name}</span>}
        </p>
      </div>
    </div>
  );
}
