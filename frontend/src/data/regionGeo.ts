/**
 * 시도 경계 GeoJSON → 음악 권역(토리)별 카카오 폴리곤 변환.
 *
 * 색·라벨·토리는 백엔드 regions.py(REGION_PROFILES)와 일치시킨다(지도 시각 단일 출처).
 * GeoJSON 좌표는 [lng, lat] 순서라 카카오 {lat, lng} 로 뒤집어 준다.
 */
import raw from "./korea-provinces.geo.json";

export interface LatLng {
  lat: number;
  lng: number;
}

export interface RegionMeta {
  key: string;
  label: string;
  tori: string;
  color: string;
}

// 백엔드 regions.py 의 색·라벨과 동일하게 유지.
export const REGION_META: RegionMeta[] = [
  { key: "sudo_chung", label: "수도권·충청", tori: "경토리", color: "#5B8DB8" },
  { key: "gangwon", label: "강원", tori: "메나리토리·애조", color: "#4E7C59" },
  { key: "yeongnam", label: "영남", tori: "메나리토리·씩씩", color: "#C9882E" },
  { key: "honam", label: "호남", tori: "육자배기토리", color: "#B5485B" },
  { key: "jeju", label: "제주", tori: "제주토리", color: "#7E6BA8" },
];

export const REGION_COLOR: Record<string, string> = Object.fromEntries(
  REGION_META.map((r) => [r.key, r.color]),
);

// 시도(한글 명) → 권역 key. (사용자가 붙여넣은 4대 권역 표 기준, 충청은 수도권에 통합.)
const PROVINCE_TO_REGION: Record<string, string> = {
  서울특별시: "sudo_chung",
  인천광역시: "sudo_chung",
  경기도: "sudo_chung",
  대전광역시: "sudo_chung",
  세종특별자치시: "sudo_chung",
  충청남도: "sudo_chung",
  충청북도: "sudo_chung",
  강원도: "gangwon",
  부산광역시: "yeongnam",
  대구광역시: "yeongnam",
  울산광역시: "yeongnam",
  경상남도: "yeongnam",
  경상북도: "yeongnam",
  광주광역시: "honam",
  전라남도: "honam",
  전라북도: "honam",
  제주특별자치도: "jeju",
};

export interface RegionPolygon {
  regionKey: string;
  province: string;
  // 외곽선 + 구멍(섬·내륙 호수). 카카오 Polygon 의 path: LatLng[][] 형식.
  path: LatLng[][];
}

function ringToPath(ring: number[][]): LatLng[] {
  return ring.map(([lng, lat]) => ({ lat, lng }));
}

/** 권역별 폴리곤 리스트. MultiPolygon(여러 섬)은 서브폴리곤마다 한 항목으로 분리. */
export const REGION_POLYGONS: RegionPolygon[] = (() => {
  const out: RegionPolygon[] = [];
  for (const f of raw.features) {
    const province = f.properties.name;
    const regionKey = PROVINCE_TO_REGION[province];
    if (!regionKey) continue;
    const g = f.geometry;
    if (g.type === "Polygon") {
      out.push({ regionKey, province, path: (g.coordinates as number[][][]).map(ringToPath) });
    } else {
      for (const poly of g.coordinates as number[][][][]) {
        out.push({ regionKey, province, path: poly.map(ringToPath) });
      }
    }
  }
  return out;
})();
