import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# ==========================================
# 1. 初期設定・認証情報の読み込み
# ==========================================
USER_ID = os.environ.get("JKK_USER_ID")
USER_PASS = os.environ.get("JKK_USER_PASS")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS")
TO_EMAIL = os.environ.get("GMAIL_USER")

JKK_LOGIN_URL = "https://www.to-kousya.or.jp/chintai/service/mypage_login.html"
TOEI_SEARCH_URL = "https://www.toeijutaku-online.metro.tokyo.lg.jp/bosyu/#/BC005"
CACHE_FILE = "seen_properties.json"

def send_email(subject, body_text):
    """Gmailで通知を送信する関数"""
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

# ==========================================
# 2. スクレイピング処理（JKK）
# ==========================================
def get_jkk_properties(login_page, search_btn_name, category_title):
    print(f"\n--- 【JKK】{category_title} の検索を開始します ---")
    login_page.locator(f'img[name="{search_btn_name}"]').click()
    login_page.wait_for_load_state()

    login_page.locator("#chk_ku_all").check()
    login_page.wait_for_timeout(1000)

    login_page.locator('img[alt="検索する"]').first.click()
    login_page.wait_for_load_state()

    items = []
    all_rows = login_page.locator("table tr").all()
    for row in all_rows:
        tds = row.locator("> td").all()
        if len(tds) >= 8:
            cols = [td.inner_text().strip().replace('\n', ' ') for td in tds]
            if len(cols) > 1:
                # ヘッダー行を除外
                if "住宅名" in cols[1] or "地域" in cols[1]:
                    continue
                items.append(cols)
    return items

# ==========================================
# 3. スクレイピング処理（都営住宅）
# ==========================================
def get_toei_properties(context):
    print("\n--- 【都営住宅】随時募集（先着順） の検索を開始します ---")
    page = context.new_page()
    try:
        page.goto(TOEI_SEARCH_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000) # サイトの初期描画を待機

        # (1) 募集の種類: 随時募集（先着順）の value="254" を選択
        page.locator("select.width-bosyu").select_option(value="254")
        page.wait_for_timeout(1500) # 次のドロップダウンが生成されるのを待機

        # (2) 住宅の種別: 「世帯向」はリストの最初(index=1)に出るためインデックスで選択
        page.locator("select.width-jyutaku").select_option(index=1)
        page.wait_for_timeout(1000)

        # (3) 入居する人数: 「2」
        page.locator("input.width-nyukyo").fill("2")

        # (4) 区市町: 「区部」のチェックボックス
        page.locator('label', has_text="区部").locator('input[type="checkbox"]').check()

        # (5) 検索ボタンをクリック
        page.locator('input[type="submit"][value="検索"]').click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000) # 検索結果テーブルの描画を待機

        items = []
        # テーブルの行を取得（該当0件の場合はテーブルが無いのでスキップされる）
        rows = page.locator("table tbody tr").all()
        for row in rows:
            # 各セルのテキストを取得
            tds = row.locator("td").all_inner_texts()
            if len(tds) >= 6:
                # 改行が含まれるため、スペースに置換して整形
                cols = [td.strip().replace('\n', ' ') for td in tds]
                items.append(cols)
        
        print(f"▶ 都営住宅の物件を {len(items)} 件確認しました。")
        return items

    except Exception as e:
        print(f"▶ 都営住宅の検索中にエラーが発生しました（スキップします）: {e}")
        return []
    finally:
        page.close()

# ==========================================
# 4. メイン処理ルーチン
# ==========================================
# 過去履歴の読み込み
seen_keys = []
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            seen_keys = json.load(f)
    except Exception as e:
        print(f"履歴ファイルの読み込み失敗: {e}")

print("自動巡回プログラムを開始します...")
items_jkk_gen = []
items_jkk_tom = []
items_toei = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    
    # 通信の高速化設定（都営住宅のVue.jsを壊さないようスクリプトは許可）
    context.route("**/*", lambda route: route.abort() 
                  if route.request.resource_type in ["image", "stylesheet", "font"] 
                  else route.continue_())
    
    # -----------------------------------
    # A. JKKのデータ取得
    # -----------------------------------
    jkk_page = context.new_page()
    jkk_page.goto(JKK_LOGIN_URL)
    with jkk_page.expect_popup() as popup_info:
        jkk_page.get_by_role("link", name="こちら").first.click()
    
    login_page = popup_info.value
    login_page.wait_for_load_state()

    login_page.locator("input[type='text']:visible").first.fill(USER_ID)
    login_page.locator("input[type='password']:visible").first.fill(USER_PASS)
    login_page.locator("#Image12").click()
    login_page.wait_for_load_state()

    items_jkk_gen = get_jkk_properties(login_page, "search1", "一般賃貸住宅")
    
    login_page.locator("#Image_home").click()
    login_page.wait_for_load_state()
    
    items_jkk_tom = get_jkk_properties(login_page, "search5", "東京都施行型都民住宅")
    jkk_page.close()
    login_page.close()

    # -----------------------------------
    # B. 都営住宅のデータ取得
    # -----------------------------------
    items_toei = get_toei_properties(context)

    browser.close()

# ==========================================
# 5. 差分チェックと通知処理
# ==========================================
all_categories = [
    ("【JKK】一般賃貸住宅", items_jkk_gen, "jkk_gen"),
    ("【JKK】東京都施行型都民住宅", items_jkk_tom, "jkk_tom"),
    ("【都営住宅】随時募集", items_toei, "toei")
]

current_keys = []
new_items_body = ""
new_count = 0

for category_title, items, cat_type in all_categories:
    cat_new_items = []
    
    for cols in items:
        # カテゴリごとにデータの抽出方法を変える
        if cat_type == "jkk_gen":
            name = cols[1] if len(cols) > 1 else ""
            area = cols[2] if len(cols) > 2 else ""
            layout = cols[5] if len(cols) > 5 else ""
            rent = f"{cols[7]}円" if len(cols) > 7 else ""
            service_fee = f"{cols[8]}円" if len(cols) > 8 else ""
            count = cols[9] if len(cols) > 9 else ""
            unique_key = f"jkk_gen_{name}_{layout}_{rent}"
            
        elif cat_type == "jkk_tom":
            name = f"都民住宅（{cols[1]}）" if len(cols) > 1 else "都民住宅"
            area = cols[1] if len(cols) > 1 else ""
            layout = cols[2] if len(cols) > 2 else ""
            rent = f"{cols[4]}円" if len(cols) > 4 else ""
            service_fee = f"{cols[5]}円" if len(cols) > 5 else ""
            count = cols[6] if len(cols) > 6 else ""
            unique_key = f"jkk_tom_{name}_{layout}_{rent}"
            
        elif cat_type == "toei":
            # 都営住宅のテーブル構造から抽出
            name_and_loc = cols[1] if len(cols) > 1 else "不明"
            name = name_and_loc.split()[0] if " " in name_and_loc else name_and_loc
            area = cols[0] if len(cols) > 0 else "" # 申込地区番号
            layout = cols[3] if len(cols) > 3 else "不明" # 間取りと面積
            rent = f"{cols[5]}円" if len(cols) > 5 else "不明" # 使用料
            service_fee = "-(都営)"
            count = cols[2] if len(cols) > 2 else "不明"
            # 地区番号と住宅名で完全な一意キーを作成
            unique_key = f"toei_{area}_{name}"

        current_keys.append(unique_key)

        # 新規物件判定
        if unique_key not in seen_keys:
            cat_new_items.append((name, layout, rent, service_fee, count))
            new_count += 1

    # 新着があったカテゴリのみテキスト化
    if cat_new_items:
        new_items_body += f"=================== 新着：{category_title}（{len(cat_new_items)}件） ===================\n"
        for i, (name, layout, rent, service_fee, count) in enumerate(cat_new_items, start=1):
            new_items_body += f"【{i}】{name}\n"
            new_items_body += f"    間取り等: {layout} | 家賃: {rent} | 共益費: {service_fee} | 募集: {count}戸\n"
            new_items_body += "-" * 50 + "\n"
        new_items_body += "\n"

# 履歴を保存
try:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(current_keys, f, ensure_ascii=False, indent=2)
except Exception as e:
    print(f"▶ 履歴保存エラー: {e}")

# 通知送信
if new_count > 0:
    subject = f"【空室検知】新たに {new_count} 件の物件が掲載されました！"
    
    full_email_body = f"新着物件が掲載されました。\n\n"
    full_email_body += new_items_body
    full_email_body += f"▼ JKK ログインページ\n{JKK_LOGIN_URL}\n"
    full_email_body += f"▼ 都営住宅 随時募集ページ\n{TOEI_SEARCH_URL}\n"

    print(f"新着物件が {new_count} 件検出されました。メールを送信します...")
    send_email(subject, full_email_body)
else:
    print("新着物件はありませんでした（通知をスキップします）。")

print("\nすべての処理が完了しました！")
