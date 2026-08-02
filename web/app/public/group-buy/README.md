# 團購貨架商品圖：出處與抓取紀錄

這個資料夾放社區團購貨架（`/user/community/group-buys`）用的商品圖，對應
`web/app/src/data/groupBuyCatalog.ts` 的 `imageUrl` / `fallbackImageUrl`。

## 誠實聲明

- `*.jpg` 是**零售通路自己拍的商品照片**（momo 購物網、全聯線上購 PXGo）。我們**一次性下載後放在本專案內由本站提供**，
  執行時不連任何外部 CDN（外站圖片會隨機連線重置，一斷線整個貨架就只剩 emoji）。
- 這些照片**不是統一企業授權或提供的官方素材**，本專案**沒有與統一企業合作**。使用方式是：
  在卡片上保留「查看原商品頁」連結指向該商品的通路頁面，並在這份檔案逐張記錄出處與抓取日期。
- `*.svg` 是我們自己畫的示意插畫，只當商品照載入失敗時的備援。
- 圖片對應的是**商品識別**（品牌 / 口味 / 包裝規格）。團購價格、庫存、到貨日、成團進度全部是
  日光森林社區的 Demo 資料，與通路實際售價無關。

## 逐張紀錄

抓取日期一律為 **2026-08-02**，工具 `curl --ssl-no-revoke`。

| 檔案 | 商品 | 圖片來源 URL | 卡片上的「查看原商品頁」 | 大小 |
| --- | --- | --- | --- | --- |
| `uni-tea-king-green.jpg` | 統一 茶裏王 日式無糖綠茶 600ml | `https://i6.momoshop.com.tw/1751625288/goodsimg/TP000/1342/0000/596/TP00013420000596_R_m.jpg` | <https://www.momoshop.com.tw/TP/TP0001342/goodsDetail/TP00013420000596> | 21,730 B・640×640 |
| `uni-milk-tea.jpg` | 統一 麥香奶茶 300ml（24 入箱） | `https://i6.momoshop.com.tw/1751625288/goodsimg/TP000/2267/0000/041/TP00022670000041_R_m.jpg` | <https://www.momoshop.com.tw/TP/TP0002267/goodsDetail/TP00022670000041> | 45,668 B・640×640 |
| `uni-red-tea.jpg` | 統一 麥香紅茶 300ml（24 入箱） | `https://i6.momoshop.com.tw/1751625288/goodsimg/TP000/2267/0000/039/TP00022670000039_R_m.jpg` | <https://www.momoshop.com.tw/TP/TP0002267/goodsDetail/TP00022670000039> | 45,163 B・640×640 |
| `uni-green-tea.jpg` | 統一 麥香綠茶 300ml（24 入箱） | `https://i6.momoshop.com.tw/1751625288/goodsimg/TP000/6302/0000/615/TP00063020000615_R_m.jpg` | <https://www.momoshop.com.tw/TP/TP0002267/goodsDetail/TP00022670000044> | 38,736 B・640×640 |
| `uni-coffee-square.jpg` | 統一 咖啡廣場 奶香特調 600ml（24 入箱） | `https://i2.momoshop.com.tw/1784025954/goodsimg/0007/219/204/7219204_R.jpg` | <https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code=7219204> | 26,127 B・640×640 |
| `uni-reisui-milk.jpg` | 統一 瑞穗全脂鮮乳 930ml | `https://image.pxgo.com.tw/pic/2025/08/27/fdfb43bce3fc461699e3893060b68d19.jpg` | <https://shop.pxgo.com.tw/hourArrive/goods/253422-21210008-4710088432674> | 30,653 B・550×550 |
| `uni-pudding.jpg` | 統一布丁 100g／3 入 | `https://image.pxgo.com.tw/pic/2025/10/12/07ecc7c00eee45bbbb805fbdb1379ea0.jpg` | <https://shop.pxgo.com.tw/hourArrive/goods/252871-21410008-4710088430922> | 53,662 B・550×550 |
| `uni-noodle.jpg` | 統一麵 肉燥風味特大號 85g | `https://i6.momoshop.com.tw/1751625288/goodsimg/TP000/2019/0000/095/TP00020190000095_R_m.jpg` | <https://www.momoshop.com.tw/TP/TP0002019/goodsDetail/TP00020190000095> | 55,684 B・640×640 |

### 圖片來源與商品頁不同的兩筆（刻意記錄）

- **`uni-green-tea.jpg`**：solo 的麥香綠茶照片來自 momo 商品 `TP00063020000615`，該頁面現在已下架
  （網址仍可開，但只剩通用的 momo 首頁標題），因此卡片連結改指向同規格且仍在架上的
  `TP00022670000044`（麥香 300ml×24 入／箱，綠茶／紅茶／奶茶）。後者的商品照是三種口味合照，
  與已有 solo 照的麥香奶茶／紅茶卡片並排會不一致，所以圖沿用前者。
- **`uni-noodle.jpg`**：momo 的「風味袋 5 入／袋」listing 商品照是四種口味合照
  （`GoodsDetail.jsp?i_code=3831982`），會讓人誤以為團購含四種口味；改用同商品箱裝頁
  `TP00020190000095` 的單包 85g 肉燥風味特大號照片，卡片連結也一併指向該頁。

## 重新抓圖

momo / PXGo 的邊緣節點會隨機連線重置（約 2–3 成），單次失敗屬正常，重試即可：

```sh
for i in 1 2 3 4 5 6; do
  curl --ssl-no-revoke -s -o out.jpg -w "%{http_code}\n" "<URL>" && break
  sleep 2
done
```

換圖後請同步更新這份表格，`web/app/tests/groupBuyCatalog.spec.ts` 會擋住把 `imageUrl` 改回外部
CDN 連結的修改。
