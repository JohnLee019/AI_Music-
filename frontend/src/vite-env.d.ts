/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_KAKAO_MAP_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// 시도 경계 GeoJSON (Vite가 .json 로더로 번들). 거대한 리터럴 타입 추론을 피하려고
// resolveJsonModule 대신 느슨한 앰비언트 타입을 선언한다.
declare module "*.geo.json" {
  interface GeoFeature {
    type: string;
    properties: Record<string, string>;
    geometry:
      | { type: "Polygon"; coordinates: number[][][] }
      | { type: "MultiPolygon"; coordinates: number[][][][] };
  }
  const value: { type: string; features: GeoFeature[] };
  export default value;
}
