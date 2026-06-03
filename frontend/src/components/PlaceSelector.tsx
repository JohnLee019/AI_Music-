import type { Place } from "../api";

interface Props {
  places: Place[];
  selected: Place | null;
  onSelect: (place: Place) => void;
  loading: boolean;
}

const TYPE_ICON: Record<string, string> = {
  궁궐: "🏯",
  민속마을: "🏘️",
  한옥마을: "🏠",
  전통시장: "🏪",
};

export default function PlaceSelector({ places, selected, onSelect, loading }: Props) {
  return (
    <section>
      <h2 className="text-sm font-medium text-stone-500 mb-3 tracking-widest uppercase">
        장소 선택
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {places.map((place) => {
          const isSelected = selected?.id === place.id;
          return (
            <button
              key={place.id}
              disabled={loading}
              onClick={() => onSelect(place)}
              className={`card text-left transition-all hover:-translate-y-0.5 active:scale-95
                ${isSelected
                  ? "ring-2 ring-jade bg-jade/5 border-jade"
                  : "hover:border-stone-300"
                }
                ${loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <div className="text-2xl mb-1">{TYPE_ICON[place.type] ?? "📍"}</div>
              <div className="font-semibold text-base leading-tight">{place.name}</div>
              <div className="text-xs text-stone-500 mt-0.5">{place.type}</div>
              <div className="text-xs text-stone-400 mt-0.5 truncate">{place.region}</div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
