import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

USER_ID = "9c16a435"
USER_PASS = "k$5BS5pT7RErbTt"
GMAIL_USER = "abarth6522@gmail.com"
GMAIL_APP_PASS = "varjtbrevzeibahr"
TO_EMAIL = "abarth6522@gmail.com"

def send_email(subject, body_text):
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

    result_text = f"=================== {category_title}（{len(items)}件） ===================\n"
    if not items:
        result_text += "現在、条件に合う空室物件はありません。\n"
    else:
        for i, cols in enumerate(items, start=1):
            name = cols[1] if len(cols) > 1 else ""
            area = cols[2] if len(cols) > 2 else ""
            layout = cols[5] if len(cols) > 5 else ""
            rent = cols[7] if len(cols) > 7 else ""
            service_fee = cols[8] if len(cols) > 8 else ""
            count = cols[9] if len(cols) > 9 else ""
            
            result_text += f"【{i}】{name} ({area})\n"
            result_text += f"    間取り: {layout} | 家賃: {rent}円 | 共益費: {service_fee}円 | 募集: {count}戸\n"
            result_text += "-" * 50 + "\n"

    print(result_text)
    return items, result_text


print("JKK自動巡回＆メール通知プログラムを開始します...")
full_email_body = ""

with sync_playwright() as p:
    # クラウド実行用に headless=True に変更
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto("https://www.to-kousya.or.jp/chintai/service/mypage_login.html")
    with page.expect_popup() as popup_info:
        page.get_by_role("link", name="こちら").first.click()
    
    login_page = popup_info.value
    login_page.wait_for_load_state()

    login_page.locator("input[type='text']:visible").first.fill(USER_ID)
    login_page.locator("input[type='password']:visible").first.fill(USER_PASS)
    login_page.locator("#Image12").click()
    login_page.wait_for_load_state()

    # 一般賃貸
    items_1, text_1 = get_properties(login_page, "search1", "一般賃貸住宅")
    full_email_body += text_1 + "\n\n"

    # マイページ戻り
    login_page.locator("#Image_home").click()
    login_page.wait_for_load_state()

    # 都民住宅
    items_2, text_2 = get_properties(login_page, "search5", "東京都施行型都民住宅")
    full_email_body += text_2 + "\n\n"

    browser.close()

# メール送信
total_count = len(items_1) + len(items_2)
subject = f"【JKK空室通知】合計 {total_count} 件の物件が見つかりました"

send_email(subject, full_email_body)
print("\nすべての処理が完了しました！")