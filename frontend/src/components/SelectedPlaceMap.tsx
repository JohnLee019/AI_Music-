import { Map, MapMarker, useKakaoLoader } from "react-kakao-maps-sdk";
import type { Place } from "../api";

const KEY = import.meta.env.VITE_KAKAO_MAP_KEY;

// ... (rest of helper) ...
function Fallback({ reason }: { reason: string }) {
  return (
    <div className="py-8 text-center text-xs text-stone-400 rounded-xl border border-dashed border-stone-200 bg-stone-50/50 mt-4">
      <div className="text-xl mb-1">🗺️</div>
      <p>지도를 불러올 수 없습니다 ({reason}).</p>
    </div>
  );
}

export default function SelectedPlaceMap({ place }: { place: Place }) {
  if (!KEY) {
    return <Fallback reason="지도 키 미설정" />;
  }
  if (typeof place.lat !== "number" || typeof place.lng !== "number") {
    return <Fallback reason="위치 좌표가 유효하지 않음" />;
  }
  return <MapInner place={place} />;
}

function MapInner({ place }: { place: Place }) {
  const [, error] = useKakaoLoader({ appkey: KEY as string });

  if (error) {
    return <Fallback reason="지도 SDK 로드 실패" />;
  }

  const position = { lat: place.lat as number, lng: place.lng as number };

  return (
    <div className="rounded-xl overflow-hidden border border-stone-200/60 mt-4 h-[240px] relative shadow-inner">
      <Map
        center={position}
        level={5}
        style={{ width: "100%", height: "100%" }}
      >
        <MapMarker
          position={position}
          title={place.name}
        />
      </Map>
    </div>
  );
}
