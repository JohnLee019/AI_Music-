"""공개(저작권 만료) 시 수집 → data/poems.json 보강 (prep, 1회성).

목적 (사용자 요청):
- 고전 시조는 고어·한자어가 많아 이해가 어려움 → 저작권 만료된 **근대시**를 더해
  '이해 쉬움 + 분위기/특색 + 분량'을 보강한다.
- 공모전 인용을 위해 출처를 **국가기관**으로 통일: 한국저작권위원회 **공유마당**의
  어문 만료저작물(menuNo=200019, '자유이용 만료' 배지)을 source_url 로 인용한다.

설계 메모:
- 공유마당은 시 본문을 다운로드 파일(TXT/HWP/PDF)로만 제공하고 인라인 텍스트로는
  주지 않아 라이브 스크래핑이 불가하다. 따라서 본문은 위키문헌 등과 대조해 검증한
  '검증된 매니페스트'로 보관하고, 스크립트는 source_url 이 살아있는지만 점검한다(API 키 불필요).
- 비파괴 증분: 기존 data/poems.json 을 읽어 DROP_IDS 만 제거하고 NEW_POEMS 를
  추가(중복 id 스킵)한다. 약한 고전을 한꺼번에 지우지 않고 단계적으로 교체하기 위함.
- 모든 작품 저작권 만료(작가 사후 70년 경과): 김소월(1934)·이육사(1944)·정지용(1950) 등.

사용:
  cd backend && python prep/collect_poems.py            # poems.json 갱신
  cd backend && python prep/collect_poems.py --check-urls  # 공유마당 source_url 생존 점검
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows에서 stdout 리다이렉트 시 기본 cp949 → 한글 인코딩 에러 방지.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_DATA = Path(__file__).resolve().parents[2] / "data"
_POEMS_JSON = _DATA / "poems.json"

# 공유마당 어문(만료저작물) 상세 페이지 — 시별 인용 출처(국가기관).
GONGU_VIEW = "https://gongu.copyright.or.kr/gongu/wrt/wrt/view.do?wrtSn={}&menuNo=200019"

_NOTE = (
    "공개(저작권 만료) 시 수록. 고전 시가(현대 철자 표기 원문) + 저작권 만료 근대시. "
    "근대시 출처는 한국저작권위원회 공유마당 어문 만료저작물(source_url, menuNo=200019). "
    "region_keys 는 regions.py 권역 key(sudo_chung·gangwon·yeongnam·honam·jeju), 빈 배열은 전국 공용. "
    "imagery_en 은 BGM 생성 프롬프트에 더해지는 영어 심상."
)

# 단계적으로 교체하는 '약한/난해/중복' 고전 id (사용자 승인분).
DROP_IDS: set[str] = {
    "jeongcheol-samiingok",     # 사미인곡(가사) — 고어 난해
    "jeongmongju-mother-crow",  # 까마귀 싸우는 골에 — 충절·지조 주제 중복
    "hwangjini-eojyeo",         # 어져 내 일이야 — 황진이 4편 중 이별 주제 중복
    "yihwang-dosan-goin",       # 도산십이곡 고인 — 이황 도산 중복 + 학문/고어 난해
    "yisaek-baekseol",          # 백설이 잦아진 골에 — 고어 난해(머흘레라)·우국 니치
    "bakillo-johongsi",         # 조홍시가 — 고어 난해(반중 조홍감)·효 니치
    "seongsammun-loyal-pine",   # 이 몸이 죽어 가서 — 충절 군집 중복(단심가와)
}

# ── 추가할 근대시 (저작권 만료, 공유마당 어문 출처) ──────────────────────
# 본문은 정전(canonical) 표기. 출전 정보는 공유마당 어문 페이지 기준.
NEW_POEMS: list[dict] = [
    {
        "id": "kimsowol-jindallae",
        "title": "진달래꽃",
        "author": "김소월",
        "era": "근대 1922",
        "form": "근대시",
        "text": "나 보기가 역겨워 / 가실 때에는 / 말없이 고이 보내 드리오리다 / "
                "영변(寧邊)에 약산(藥山) / 진달래꽃 / 아름 따다 가실 길에 뿌리오리다 / "
                "가시는 걸음걸음 / 놓인 그 꽃을 / 사뿐히 즈려밟고 가시옵소서 / "
                "나 보기가 역겨워 / 가실 때에는 / 죽어도 아니 눈물 흘리오리다",
        "theme_ko": "이별·체념·인고의 사랑",
        "region_keys": [],
        "place_types": [],
        "imagery_en": "a quiet self-sacrificing farewell, azaleas of Yaksan in Yeongbyeon strewn on the departing path, sorrow held back without tears, restrained tender devotion",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(9000320),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "kimsowol-sanyuhwa",
        "title": "산유화",
        "author": "김소월",
        "era": "근대 1925",
        "form": "근대시",
        "text": "산에는 꽃 피네 / 꽃이 피네 / 갈 봄 여름 없이 / 꽃이 피네 / "
                "산에 / 산에 / 피는 꽃은 / 저만치 혼자서 피어 있네 / "
                "산에서 우는 작은 새여 / 꽃이 좋아 / 산에서 / 사노라네 / "
                "산에는 꽃 지네 / 꽃이 지네 / 갈 봄 여름 없이 / 꽃이 지네",
        "theme_ko": "자연의 순환·홀로 피고 지는 꽃·고요한 외로움",
        "region_keys": [],
        "place_types": [],
        "imagery_en": "mountain flowers blooming and falling through every season, a small bird singing alone on the slope, serene solitude, the quiet cycle of nature, gentle melancholy",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(12198105),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "kimsowol-meonhuil",
        "title": "먼 후일",
        "author": "김소월",
        "era": "근대 1925",
        "form": "근대시",
        "text": "먼 훗날 당신이 찾으시면 / 그때에 내 말이 '잊었노라' / "
                "당신이 속으로 나무라면 / '무척 그리다가 잊었노라' / "
                "그래도 당신이 나무라면 / '믿기지 않아서 잊었노라' / "
                "오늘도 어제도 아니 잊고 / 먼 훗날 그때에 '잊었노라'",
        "theme_ko": "이별·그리움·반어적 체념",
        "region_keys": [],
        "place_types": [],
        "imagery_en": "a vow of having 'forgotten,' a deep longing disguised as forgetting, quiet ache deferred to some far-off day",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(12198105),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "kimsowol-eommaya",
        "title": "엄마야 누나야",
        "author": "김소월",
        "era": "근대 1925",
        "form": "근대시",
        "text": "엄마야 누나야 강변 살자 / 뜰에는 반짝이는 금모래빛 / "
                "뒷문 밖에는 갈잎의 노래 / 엄마야 누나야 강변 살자",
        "theme_ko": "평화·강변·동심의 소망",
        "region_keys": [],
        "place_types": [],
        "imagery_en": "a child's wish to live by the river, glittering golden sand in the yard, the song of reed leaves by the back door, gentle idyllic peace",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(12198105),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "yiyuksa-cheongpodo",
        "title": "청포도",
        "author": "이육사",
        "era": "근대 1939",
        "form": "근대시",
        "text": "내 고장 칠월은 / 청포도가 익어 가는 시절 / "
                "이 마을 전설이 주저리주저리 열리고 / 먼 데 하늘이 꿈꾸며 알알이 들어와 박혀 / "
                "하늘 밑 푸른 바다가 가슴을 열고 / 흰 돛 단 배가 곱게 밀려서 오면 / "
                "내가 바라는 손님은 고달픈 몸으로 / 청포(靑袍)를 입고 찾아온다고 했으니 / "
                "내 그를 맞아 이 포도를 따 먹으면 / 두 손은 함뿍 적셔도 좋으련 / "
                "아이야 우리 식탁엔 은쟁반에 / 하이얀 모시 수건을 마련해 두렴",
        "theme_ko": "고향 칠월·청포도·기다림·풍요와 희망",
        "region_keys": ["yeongnam"],
        "place_types": [],
        "imagery_en": "a hometown July when green grapes ripen, village legends clustering on the vine, a blue sea opening its breast, a white-sailed boat drawing near, awaiting a weary guest in blue robes, abundance and quiet hope",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(9001047),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "yundongju-seosi",
        "title": "서시",
        "author": "윤동주",
        "era": "근대 1941",
        "form": "근대시",
        "text": "죽는 날까지 하늘을 우러러 / 한 점 부끄럼이 없기를, / "
                "잎새에 이는 바람에도 / 나는 괴로워했다. / "
                "별을 노래하는 마음으로 / 모든 죽어 가는 것을 사랑해야지 / "
                "그리고 나한테 주어진 길을 / 걸어가야겠다. / "
                "오늘 밤에도 별이 바람에 스치운다.",
        "theme_ko": "자기 성찰·부끄럼 없는 삶·별",
        "region_keys": [],
        "place_types": [],
        "imagery_en": "looking up to the sky until the day of death, wishing for not a speck of shame, anguish even at wind stirring the leaves, loving all dying things, walking one's given path, a star brushed by the wind at night, pure conscience",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(9000779),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "kimyeongnang-doldam",
        "title": "돌담에 속삭이는 햇발",
        "author": "김영랑",
        "era": "근대 1930",
        "form": "근대시",
        "text": "돌담에 속삭이는 햇발같이 / 풀 아래 웃음 짓는 샘물같이 / "
                "내 마음 고요히 고운 봄 길 위에 / 오늘 하루 하늘을 우러르고 싶다 / "
                "새악시 볼에 떠 오는 부끄럼같이 / 시의 가슴에 살포시 젖는 물결같이 / "
                "보드레한 에메랄드 얇게 흐르는 / 실비단 하늘을 바라보고 싶다",
        "theme_ko": "봄·맑은 서정·하늘을 우러름",
        "region_keys": ["honam"],
        "place_types": [],
        "imagery_en": "sunbeams whispering on a stone wall, a spring smiling under the grass, a quiet lovely spring path, a maiden's rising blush, ripples gently soaking a poet's heart, a soft thin emerald silk sky, serene lyrical yearning",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(9000347),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "hanyongun-nimui-chimmuk",
        "title": "님의 침묵",
        "author": "한용운",
        "era": "근대 1926",
        "form": "근대시",
        "text": "님은 갔습니다. 아아, 사랑하는 나의 님은 갔습니다. / "
                "푸른 산빛을 깨치고 단풍나무 숲을 향하여 난 작은 길을 걸어서, 차마 떨치고 갔습니다. / "
                "황금의 꽃같이 굳고 빛나던 옛 맹세는 차디찬 티끌이 되어서 한숨의 미풍에 날아갔습니다. / "
                "날카로운 첫 키스의 추억은 나의 운명의 지침을 돌려 놓고, 뒷걸음쳐서 사라졌습니다. / "
                "나는 향기로운 님의 말소리에 귀먹고, 꽃다운 님의 얼굴에 눈멀었습니다. / "
                "사랑도 사람의 일이라, 만날 때에 미리 떠날 것을 염려하고 경계하지 아니한 것은 아니지만, 이별은 뜻밖의 일이 되고, 놀란 가슴은 새로운 슬픔에 터집니다. / "
                "그러나 이별을 쓸데없는 눈물의 원천을 만들고 마는 것은 스스로 사랑을 깨치는 것인 줄 아는 까닭에, 걷잡을 수 없는 슬픔의 힘을 옮겨서 새 희망의 정수박이에 들어부었습니다. / "
                "우리는 만날 때에 떠날 것을 염려하는 것과 같이, 떠날 때에 다시 만날 것을 믿습니다. / "
                "아아, 님은 갔지마는 나는 님을 보내지 아니하였습니다. / "
                "제 곡조를 못 이기는 사랑의 노래는 님의 침묵을 휩싸고 돕니다.",
        "theme_ko": "이별·역설적 희망·다시 만남의 믿음",
        "region_keys": ["sudo_chung"],
        "place_types": [],
        "imagery_en": "the beloved has gone, a bright old vow turned to cold dust on a sighing breeze, the memory of a first kiss receding, deaf to the beloved's voice and blind to their face, grief transmuted into new hope, faith in reunion, a love-song circling the beloved's silence",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(9001830),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "jeongjiyong-hosu",
        "title": "호수",
        "author": "정지용",
        "era": "근대 1930",
        "form": "근대시",
        "text": "얼굴 하나야 / 손바닥 둘로 / 폭 가리지만, / "
                "보고 싶은 마음 / 호수만 하니 / 눈 감을밖에",
        "theme_ko": "그리움·호수만 한 마음",
        "region_keys": ["sudo_chung"],
        "place_types": [],
        "imagery_en": "a single face easily hidden behind two cupped palms, yet a longing as wide as a lake, leaving nothing but to close one's eyes, quiet overwhelming yearning",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(9029792),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "kimsowol-ganeungil",
        "title": "가는 길",
        "author": "김소월",
        "era": "근대 1923",
        "form": "근대시",
        "text": "그립다 / 말을 할까 / 하니 그리워 / 그냥 갈까 / 그래도 / 다시 더 한 번…… / "
                "저 산에도 까마귀, 들에 까마귀 / 서산에는 해 진다고 / 지저귑니다. / "
                "앞 강물 뒷 강물 / 흐르는 물은 / 어서 따라오라고 따라가자고 / 흘러도 연달아 흐릅디다려.",
        "theme_ko": "그리움·망설임·흐르는 강물",
        "region_keys": [],
        "place_types": [],
        "imagery_en": "hesitating whether to speak one's longing, crows in mountain and field calling that the sun sets in the west, river waters flowing on and on urging one to follow, lingering reluctant love",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(12198105),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "kimyeongnang-moran",
        "title": "모란이 피기까지는",
        "author": "김영랑",
        "era": "근대 1934",
        "form": "근대시",
        "text": "모란이 피기까지는 / 나는 아직 나의 봄을 기다리고 있을 테요 / "
                "모란이 뚝뚝 떨어져 버린 날 / 나는 비로소 봄을 여읜 설움에 잠길 테요 / "
                "오월 어느 날 그 하루 무덥던 날 / 떨어져 누운 꽃잎마저 시들어 버리고는 / "
                "천지에 모란은 자취도 없어지고 / 뻗쳐오르던 내 보람 서운케 무너졌느니 / "
                "모란이 지고 말면 그뿐 내 한 해는 다 가고 말아 / 삼백예순 날 하냥 섭섭해 우옵네다 / "
                "모란이 피기까지는 / 나는 아직 기다리고 있을 테요 찬란한 슬픔의 봄을",
        "theme_ko": "기다림·모란·찬란한 슬픔의 봄",
        "region_keys": ["honam"],
        "place_types": [],
        "imagery_en": "waiting for the peony to bloom as one's own spring, the grief of a spring lost when petals fall, a sweltering day in May, the flower vanishing without a trace, soaring hope quietly crumbling, yet still awaiting the radiant sorrow of spring",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(9000350),
        "license": "Public Domain (저작권 만료)",
    },
    {
        "id": "yisanghwa-ppaeatgin",
        "title": "빼앗긴 들에도 봄은 오는가",
        "author": "이상화",
        "era": "근대 1926",
        "form": "근대시",
        # ⚠️ 장시(11연) — 출품 전 공유마당 만료저작물 파일과 1:1 검수 필요.
        "text": "지금은 남의 땅 ― 빼앗긴 들에도 봄은 오는가? / "
                "나는 온몸에 햇살을 받고 / 푸른 하늘 푸른 들이 맞붙은 곳으로 / "
                "가르마 같은 논길을 따라 꿈속을 가듯 걸어만 간다. / "
                "입술을 다문 하늘아 들아 / 내 맘에는 내 혼자 온 것 같지를 않구나 / "
                "네가 끌었느냐 누가 부르더냐 답답워라 말을 해 다오. / "
                "바람은 내 귀에 속삭이며 / 한 자국도 섰지 마라 옷자락을 흔들고 / "
                "종다리는 울타리 너머 아씨같이 구름 뒤에서 반갑다 웃네. / "
                "고맙게 잘 자란 보리밭아 / 간밤 자정이 넘어 내리던 고운 비로 / "
                "너는 삼단 같은 머리를 감았구나 내 머리조차 가뿐하다. / "
                "혼자라도 가쁘게나 가자 / 마른 논을 안고 도는 착한 도랑이 / "
                "젖먹이 달래는 노래를 하고 제 혼자 어깨춤만 추고 가네. / "
                "나비 제비야 깝치지 마라 / 맨드라미 들마꽃에도 인사를 해야지 / "
                "아주까리 기름을 바른 이가 지심 매던 그 들이라 다 보고 싶다. / "
                "내 손에 호미를 쥐어 다오 / 살진 젖가슴과 같은 부드러운 이 흙을 / "
                "발목이 시리도록 밟아도 보고 좋은 땀조차 흘리고 싶다. / "
                "강가에 나온 아이와 같이 / 짬도 모르고 끝도 없이 닫는 내 혼아 / "
                "무엇을 찾느냐 어디로 가느냐 우스웁다 답을 하려무나. / "
                "나는 온몸에 풋내를 띠고 / 푸른 웃음 푸른 설움이 어우러진 사이로 / "
                "다리를 절며 하루를 걷는다 아마도 봄 신령이 지폈나 보다. / "
                "그러나 지금은 ― 들을 빼앗겨 봄조차 빼앗기겠네.",
        "theme_ko": "국토 상실의 비애·봄·저항",
        "region_keys": ["yeongnam"],
        "place_types": [],
        "imagery_en": "walking as if in a dream along a parted-hair path where blue sky meets green field, a stolen land where spring still comes, larks laughing behind clouds, barley washed by night rain, longing to grip a hoe and tread the soft earth, green laughter and green sorrow, the dread that even spring will be taken away",
        "source": "공유마당 (한국저작권위원회) — 어문 만료저작물",
        "source_url": GONGU_VIEW.format(9001014),
        "license": "Public Domain (저작권 만료)",
    },
]


def _check_urls(poems: list[dict]) -> None:
    """공유마당 source_url 이 살아있는지 가볍게 점검(키 불필요)."""
    import urllib.request

    seen: set[str] = set()
    for p in poems:
        url = p.get("source_url", "")
        if not url or "gongu.copyright.or.kr" not in url or url in seen:
            continue
        seen.add(url)
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"  [{resp.status}] {p['title']} → {url}")
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR] {p['title']} → {url} ({e})")


def main() -> None:
    check = "--check-urls" in sys.argv

    data = json.loads(_POEMS_JSON.read_text(encoding="utf-8"))
    poems: list[dict] = data.get("poems", [])

    kept = [p for p in poems if p.get("id") not in DROP_IDS]
    existing_ids = {p.get("id") for p in kept}
    added = [p for p in NEW_POEMS if p.get("id") not in existing_ids]
    result = kept + added

    out = {"_note": _NOTE, "poems": result}
    _POEMS_JSON.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"poems.json 갱신: 기존 {len(poems)} - 삭제 {len(poems) - len(kept)} "
        f"+ 추가 {len(added)} = {len(result)}편"
    )
    if check:
        print("공유마당 source_url 점검:")
        _check_urls(added)


if __name__ == "__main__":
    main()
