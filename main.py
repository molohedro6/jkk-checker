import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

USER_ID = "9c16a435"
USER_PASS = "k$5BS5pT7RErbTt"
GMAIL_USER = "abarth6522@gmail.com"
GMAIL_APP_PASS = "varjtbrevzeibahr"
TO_EMAIL = "abarth6522@gmail.com"

# JKKログインページのURL
LOGIN_URL = "https://www.to-kousya.or.jp/chintai/service/mypage_login.html"
CACHE_FILE = "seen_properties.json"

def send_email(subject, body_text):
    """Gmail送信関数"""
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASS)
            server.send_message(msg)
        print("▶ Gmailへの通知送信に成功しました！")
    except Exception as e:
        print(f"▶ メール送信エラー: {e}")

def get_properties(login_page, search_btn_name, category_title):
    """物件取得処理"""
    print(f"\n--- 【{category_title}】の検索を開始します ---")
    
    login_page.locator(f'img[name="{search_btn_name}"]').click()
    login_page.wait_for_load_state()

    login_page.locator("#chk_ku_all").check()
    login_page.wait_for_timeout(1000)

    login_page.locator('img[alt="検索する"]').first.click()
    login_page.wait_for_load_state()

    all_rows = login_page.locator("table tr").all()
    items = []
    
    for row in all_rows:
        tds = row.locator("> td").all()
        if len(tds) >= 8:
            cols = [td.inner_text().strip().replace('\n', ' ') for td in tds]
            if len(cols) > 1 and "住宅名" not in cols[1]:
                items.append(cols)

    return items


# 1. 過去の検索履歴を読み込み
seen_keys = []
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            seen_keys = json.load(f)
    except Exception as e:
        print(f"履歴ファイルの読み込み失敗: {e}")

print("JKK自動巡回プログラムを開始します...")

# 2. スクレイピング実行
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto(LOGIN_URL)
    with page.expect_popup() as popup_info:
        page.get_by_role("link", name="こちら").first.click()
    
    login_page = popup_info.value
    login_page.wait_for_load_state()

    login_page.locator("input[type='text']:visible").first.fill(USER_ID)
    login_page.locator("input[type='password']:visible").first.fill(USER_PASS)
    login_page.locator("#Image12").click()
    login_page.wait_for_load_state()

    # 一般賃貸
    items_1 = get_properties(login_page, "search1", "一般賃貸住宅")

    # マイページ戻り
    login_page.locator("#Image_home").click()
    login_page.wait_for_load_state()

    # 都民住宅
    items_2 = get_properties(login_page, "search5", "東京都施行型都民住宅")

    browser.close()

# 3. 差分チェック処理
all_categories = [
    ("一般賃貸住宅", items_1),
    ("東京都施行型都民住宅", items_2)
]

current_keys = []
new_items_body = ""
new_count = 0

for category_title, items in all_categories:
    cat_new_items = []
    for cols in items:
        name = cols[1] if len(cols) > 1 else ""
        area = cols[2] if len(cols) > 2 else ""
        layout = cols[5] if len(cols) > 5 else ""
        rent = cols[7] if len(cols) > 7 else ""
        service_fee = cols[8] if len(cols) > 8 else ""
        count = cols[9] if len(cols) > 9 else ""

        # 物件を一意に識別するキー（カテゴリ_物件名_間取り_家賃）
        unique_key = f"{category_title}_{name}_{layout}_{rent}"
        current_keys.append(unique_key)

        # 履歴になければ新着とみなす
        if unique_key not in seen_keys:
            cat_new_items.append((name, area, layout, rent, service_fee, count))
            new_count += 1

    if cat_new_items:
        new_items_body += f"=================== 【新着】{category_title}（{len(cat_new_items)}件） ===================\n"
        for i, (name, area, layout, rent, service_fee, count) in enumerate(cat_new_items, start=1):
            new_items_body += f"【{i}】{name} ({area})\n"
            new_items_body += f"    間取り: {layout} | 家賃: {rent}円 | 共益費: {service_fee}円 | 募集: {count}戸\n"
            new_items_body += "-" * 50 + "\n"
        new_items_body += "\n"

# 4. 今回の検索結果を履歴ファイルに書き込み
try:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(current_keys, f, ensure_ascii=False, indent=2)
    print("▶ 最新の検索履歴を保存しました。")
except Exception as e:
    print(f"▶ 履歴保存エラー: {e}")

# 5. メール送信判断（新着がある場合のみ通知）
if new_count > 0:
    subject = f"【JKK新着通知】新たに {new_count} 件の物件が掲載されました！"
    
    full_email_body = f"JKK netに新しい空室物件が掲載されました。\n\n"
    full_email_body += new_items_body
    full_email_body += f"\n▼ JKK net ログインページ\n{LOGIN_URL}\n"

    print(f"新着物件が {new_count} 件検出されました。メールを送信します...")
    send_email(subject, full_email_body)
else:
    print("新着物件はありませんでした（通知をスキップします）。")

print("\nすべての処理が完了しました！")
