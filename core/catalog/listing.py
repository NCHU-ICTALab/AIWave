"""統一體系品牌目錄陳列(tier-2)。

兩層制(產品負責人 2026-07-31 拍板):
- tier-1 可交易 Provider:有代表表單、可下單/預約,活在 fake upstream 與目錄投影。
- tier-2 目錄陳列(本檔):其餘統一體系品牌以品牌卡呈現,誠實標示「未開放線上交易」,
  不虛構不存在的消費者流程(B2B、支付工具、基金會等)。

名單唯一來源:產品負責人提供的《廠商and表單.md》(集團官方名單
https://www.pecos.com.tw/group.html)。品牌名稱與分類有公開依據;不得自行增刪品牌。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ListedBrand:
    """目錄陳列品牌(不可下單;`note` 說明為何或現況)。"""

    id: str
    name: str
    scene: str            # food/med/home/move/pre/fun/support
    company: str
    url: str = ""
    note: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "scene": self.scene,
            "company": self.company, "url": self.url, "note": self.note,
            "tags": list(self.tags), "transactable": False,
            "source": "廠商and表單.md(統一集團官方名單)",
        }


LISTED_BRANDS: tuple[ListedBrand, ...] = (
    # ── 食 ──
    ListedBrand("listing-7-11", "7-ELEVEN(含 CITY CAFÉ、鮮食)", "food", "統一超商",
                "https://www.7-11.com.tw/", tags=("零售", "咖啡")),
    ListedBrand("listing-starbucks", "星巴克", "food", "悠旅生活事業",
                "https://www.pecos.com.tw/click/group-13.html", tags=("咖啡",)),
    ListedBrand("listing-mister-donut", "Mister Donut", "food", "統一多拿滋",
                "https://www.pecos.com.tw/click/group-16.html", tags=("甜點",)),
    ListedBrand("listing-coldstone", "COLD STONE 酷聖石", "food", "酷聖石冰淇淋",
                "https://www.pecos.com.tw/click/group-19.html", tags=("冰品",)),
    ListedBrand("listing-semeur", "Semeur 聖娜", "food", "統一聖娜多堡",
                "https://www.pecos.com.tw/click/group-9.html", tags=("烘焙",)),
    ListedBrand("listing-afternoon-tea", "統一午茶風光 Afternoon Tea", "food", "統一企業集團",
                tags=("餐飲",)),
    ListedBrand("listing-heshi", "和食上都", "food", "統一企業集團", tags=("餐飲",)),
    ListedBrand("listing-organic", "統一生機", "food", "統一生機開發",
                "https://www.pecos.com.tw/click/group-7.html", tags=("生機食品",)),
    ListedBrand("listing-santa-cruz", "聖德科斯", "food", "統健(聖德科斯)",
                "https://www.pecos.com.tw/click/group-49.html", tags=("生機食品",)),
    ListedBrand("listing-tait", "德記洋行", "food", "德記洋行",
                "https://www.pecos.com.tw/click/group-51.html", "B2B 品牌代理與貿易", ("B2B",)),
    ListedBrand("listing-nanlien", "南聯國際貿易", "food", "南聯國際貿易",
                "https://www.pecos.com.tw/click/group-41.html", "B2B 貿易", ("B2B",)),
    ListedBrand("listing-prosperity-plaza", "萬家福 PROSPERiTY PLAZA", "food", "康達盛通生活事業",
                "", "量販;2026-07-01 啟用新品牌", ("量販",)),
    ListedBrand("listing-uni-prosperity", "樂家康 Uni-Prosperity", "food", "康達盛通生活事業",
                "", "超市;2026-07-01 啟用新品牌", ("超市",)),
    ListedBrand("listing-mia-cbon", "Mia C'bon", "food", "康達盛通生活事業",
                "", "高端超市", ("超市",)),
    ListedBrand("listing-musashino", "統一武藏野", "food", "統一武藏野", "", "鮮食製造(B2B)", ("B2B",)),
    # ── 醫 ──
    ListedBrand("listing-uni-pharma", "統一藥品(我的美麗日記)", "med", "統一藥品",
                "https://www.pecos.com.tw/click/group-29.html", tags=("藥妝",)),
    ListedBrand("listing-millennium", "千禧之愛健康基金會", "med", "統一企業＋統一超商共同捐助",
                "https://www.pecos.com.tw/click/group-45.html", "公益健康宣導與社區健檢", ("公益",)),
    # ── 住 ──
    ListedBrand("listing-muji", "台灣無印良品 MUJI", "home", "台灣無印良品", "", tags=("居家零售",)),
    ListedBrand("listing-goodneighbor", "好鄰居文教基金會", "home", "統一超商", "", "公益", ("公益",)),
    ListedBrand("listing-prince-property", "太子物業", "home", "太子物業管理顧問",
                "https://www.prince.com.tw/", "社區物業整合窗口", ("物業",)),
    # ── 行 ──
    ListedBrand("listing-ibon-taxi", "ibon 叫車(台灣大車隊/大都會衛星/城市衛星)", "move", "統一超商(合作車隊)",
                "https://www.ibon.com.tw/mobile/life/F0411.aspx?pID=37",
                "官方流程為 ibon 機台操作、照表收費;未提供線上叫車,誠實陳列不虛構線上流程", ("叫車",)),
    ListedBrand("listing-uni-elevator", "電梯/停車設備/洗車機 設計安裝維護", "move", "統一精工",
                "https://www.pecos.com.tw/click/group-12.html", "B2B 設備工程", ("B2B",)),
    ListedBrand("listing-retail-logistics", "捷盟行銷(常溫物流)", "move", "捷盟行銷",
                "https://www.pecos.com.tw/click/group-23.html", "企業物流", ("B2B",)),
    ListedBrand("listing-tongcheng", "統昶行銷(低溫物流)", "move", "統昶行銷", "", "企業物流", ("B2B",)),
    ListedBrand("listing-dazhitong", "大智通文化行銷(書報物流)", "move", "大智通", "", "企業物流", ("B2B",)),
    ListedBrand("listing-jiesheng", "捷盛運輸(大宗貨運)", "move", "捷盛運輸",
                "https://www.pecos.com.tw/click/group-25.html", "企業物流", ("B2B",)),
    ListedBrand("listing-uni-tokyo", "統一東京(汽機車長租/設備租賃/二手車)", "move", "統一東京",
                "https://www.pecos.com.tw/click/group-48.html", "企業長租詢價屬 B 端流程", ("B2B",)),
    # ── 預 ──
    ListedBrand("listing-myship", "7-ELEVEN 賣貨便", "pre", "統一數網",
                "https://myship.7-11.com.tw/", "小賣家開店/收款/物流整合", ("C2C",)),
    ListedBrand("listing-ihuasuan", "i划算", "pre", "統一超商", tags=("電商",)),
    ListedBrand("listing-books", "博客來", "pre", "博客來數位科技",
                "https://www.books.com.tw/", tags=("電商",)),
    ListedBrand("listing-icash", "icash pay / icash 2.0", "pre", "愛金卡",
                "https://www.pecos.com.tw/click/group-47.html", "支付工具", ("支付",)),
    ListedBrand("listing-jinfin", "金財通商務科技", "pre", "金財通", "", "電子發票(B2B)", ("B2B",)),
    # ── 樂 ──
    ListedBrand("listing-uni-lions", "統一獅(統一 7-ELEVEn 獅)", "fun", "統一棒球隊",
                "https://ticket.ibon.com.tw/Index/Sport", "賽事購票走 ibon 售票(劃位型待後續)", ("賽事",)),
    ListedBrand("listing-dream-mall", "統一夢時代購物中心", "fun", "統一夢時代",
                "https://www.pecos.com.tw/click/group-21.html", tags=("商場",)),
    ListedBrand("listing-dream-plaza", "統一時代百貨台北店 DREAM PLAZA", "fun", "統一百華",
                "https://www.uni-ustyle.com.tw/", tags=("商場",)),
    ListedBrand("listing-being-spa", "BEING spa", "fun", "統一佳佳",
                "https://www.beingspa.com.tw/", tags=("休閒",)),
    ListedBrand("listing-being-sport", "BEING sport 統一健身俱樂部", "fun", "統一佳佳",
                "https://group.being.com.tw/", tags=("健身",)),
    ListedBrand("listing-being-fit", "7-ELEVEN × BEING fit", "fun", "統一佳佳",
                "https://group.being.com.tw/", tags=("健身",)),
    ListedBrand("listing-lanyang", "統一蘭陽藝文(國立傳統藝術中心)", "fun", "統一蘭陽藝文", "", tags=("藝文",)),
    ListedBrand("listing-dream-park", "統一夢公園", "fun", "統一夢公園生活事業", "", tags=("休閒",)),
    ListedBrand("listing-ibon-insurance", "ibon 保險", "fun", "統超保經",
                "https://www.pecos.com.tw/click/group-52.html", "保險經紀", ("保險",)),
    # ── 支援型與其他關係企業(整組陳列,無消費者流程) ──
    ListedBrand("listing-presco", "統一資訊(本次命題單位)", "support", "統一資訊",
                "https://www.pecos.com.tw/click/group-56.html", "系統整合/雲端/資安/RMN-R", ("B2B",)),
    ListedBrand("listing-shoufu", "首阜企業管理顧問", "support", "首阜企業管理顧問",
                "https://www.pecos.com.tw/click/group-55.html", "盤點/查核/市調", ("B2B",)),
    ListedBrand("listing-uni-futures", "統一期貨", "support", "統一期貨",
                "https://www.pecos.com.tw/click/group-50.html", "金融", ("金融",)),
    ListedBrand("listing-uni-securities", "統一綜合證券", "support", "統一綜合證券",
                "https://www.pecos.com.tw/click/group-53.html", "金融", ("金融",)),
    ListedBrand("listing-tongyi-glass", "統義玻璃", "support", "統義玻璃",
                "https://www.pecos.com.tw/click/group-54.html", "玻璃瓶器製造(B2B)", ("B2B",)),
)


def listings_for(scene: str | None = None) -> list[dict]:
    return [brand.to_dict() for brand in LISTED_BRANDS if scene is None or brand.scene == scene]
