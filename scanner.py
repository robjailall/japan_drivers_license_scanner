from playwright.sync_api import sync_playwright
import time
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os

# ユーザー設定（フォーム入力用）
# ※ここを実際のあなたの情報に書き換えてください
USER_DATA = {
    "name_kanji": "山田 太郎",
    "name_kana": "ヤマダ タロウ",
    "email": "test@example.com",
    "phone": "090-0000-0000",
    # 他に必要な項目があれば追加
}

SLACK_OAUTH_TOKEN = os.environ.get('SLACK_OAUTH_TOKEN')
SEARCH_RESULTS_URL = "https://www.keishicho-gto.metro.tokyo.lg.jp/keishicho-u/reserve/offerList_reSearch"

def run_booking_flow():
    with sync_playwright() as p:
        # 実際の動作を見るために headless=False に設定
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()

        print("--- ステップ1: 予約サイトへ直接アクセス ---")
        page.goto(SEARCH_RESULTS_URL)

        print("--- ステップ2: 対象の項目を選択 ---")
        # This is for OUTSIDE the 29 countries
        target_text = "【免許手続】29の国・地域以外で取得した運転免許証を日本の免許に切り替える方(Applicants for license conversion)"
        # This is for INSIDE the 29 countries
        target_text = "【免許手続】29の国・地域で取得した運転免許証を日本の免許に切り替える方(Applicants for license conversion)"
        page.get_by_text(target_text).click()

        print("--- ステップ3: 空き枠（緑の丸）を検索 ---")
        # ページ遷移待ち
        page.wait_for_load_state("networkidle")

        slot_found = False

        while not slot_found:
            # 「緑の丸」を探す。通常はテキストが「○」または画像altが「○」であることが多いです。
            # サイトの構造に合わせて調整が必要ですが、ここではテキスト「○」を持つ要素を探します。
            # ※もし画像の場合は page.get_by_alt_text("○") などに変えてください
            '''<svg width="20" height="20" xmlns="http://www.w3.org/2000/svg" viewBox="0 1.5 20 20" role="img" aria-label="予約可能" focusable="false">
                <defs><style>.ok-cls-1,.ok-cls-2{fill:none;}.ok-cls-1{stroke:#008A2B;stroke-miterlimit:10;stroke-width:3px;}</style></defs>
                <circle class="ok-cls-1" cx="10" cy="10" r="7"></circle>
                <rect class="ok-cls-2" width="20" height="20"></rect></svg>'''
            schedule = page.locator(".facilitySelect_calender")
            available_slots = schedule.get_by_label("予約可能")

            if schedule.count() > 0 and available_slots.count() > 0:
                print("空き枠が見つかりました！")
                slot_found = True
                send_slack_message(page_url=SEARCH_RESULTS_URL, title=target_text)

                # # --- ステップ4: 同意して枠をクリック ---
                # # 「上記内容に同意する」にチェックを入れる
                # # チェックボックスのラベルをクリックするか、check()メソッドを使います
                # '''
                # <label for="reserveCaution" class="u-mt15 radio-outline" tabindex="0" role="checkbox" aria-checked="true">
                # <input id="reserveCaution" name="reserveCaution" class="checkbox-input" type="checkbox" value="true" checked="checked"><input type="hidden" name="_reserveCaution" value="on">
                # <span class="checkbox-parts">上記内容に同意する</span>
                #  </label>
                # '''
                # page.get_by_label("上記内容に同意する").check()
                #
                # '''<td id="pc-0_60" class="time--table time--th enable bordernone tdSelect" colspan="6" title="13:00～13:30">
                # <input id="reserveTimeCheck_0_60" name="reserveSlotTimeList[0].reserveTimeCheckArray" class="checkbox_hide" onfocus="onFocusTime(this);" onblur="onBlurTime(this);" onchange="onChangeTime(this);" type="checkbox" value="FR00282_1300"><input type="hidden" name="_reserveSlotTimeList[0].reserveTimeCheckArray" value="on">
                # <label class="sr-only" for="reserveTimeCheck_0_60">
                #     29の国･地域の方の13時00分の予約選択
                # </label> </td>'''
                #
                # # 最初の「○」をクリック
                # available_slots.first.click()
                break

            else:
                print("現在のページに空きはありません。次へ進みます。")
                # 「2週後」ボタンを探す
                next_button = page.get_by_role("button", name="2週後")

                # ボタンが存在し、かつ有効（disabledでない）場合
                if next_button.is_visible() and next_button.is_enabled():
                    next_button.click()
                    # 次のページの読み込みを待つ（重要）
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)  # 念のため少し待機
                else:
                    print("これ以上先のページがないか、ボタンが無効です。検索を終了します。")
                    browser.close()
                    return

        # print("--- ステップ5: 時間枠の選択 ---")
        # # 次のページへ遷移後
        # page.wait_for_load_state("networkidle")
        #
        # # スケジュール行の最初の「緑の丸（○）」をクリック
        # # ※ここも実際のHTML構造に依存しますが、最初の○をクリックするロジックです
        # page.get_by_text("○").first.click()
        #
        # # 「予約する」ボタンをクリック
        # page.get_by_role("button", name="予約する").click()
        #
        # print("--- ステップ6: 同意画面 ---")
        # page.wait_for_load_state("networkidle")
        # page.get_by_role("button", name="同意する").click()
        #
        # print("--- ステップ7: フォーム入力（マルチタブ） ---")
        # # ※注意: ここのセレクタ（fillの中身）はサイトのHTMLを見て特定する必要があります
        # # 以下は一般的な例です。エラーが出る場合は name="..." などを調べて修正してください。
        # try:
        #     # 例: 氏名入力
        #     # page.fill('input[name="userName"]', USER_DATA["name_kanji"])
        #     # page.fill('input[name="userKana"]', USER_DATA["name_kana"])
        #     # page.fill('input[name="mail"]', USER_DATA["email"])
        #
        #     print("フォーム入力処理を実行中...（コード内のセレクタ設定が必要です）")
        #     # デバッグ用に一時停止します。手動で入力して確認してください。
        #     # 自動化が完成したらこの input() は削除してください。
        #     input("ここでフォームが入力されます。Enterキーを押すと次へ進みます（デバッグ用）...")
        #
        # except Exception as e:
        #     print(f"フォーム入力でエラーが発生しました: {e}")
        #
        # print("--- ステップ8: 確認画面へ ---")
        # page.get_by_role("button", name="確認へ進む").click()
        #
        # print("--- ステップ9: 申し込み ---")
        # # 最終確認待ち
        # page.wait_for_load_state("networkidle")
        #
        # # 本当に申し込んで良い場合のみコメントアウトを外してください
        # # page.get_by_role("button", name="申込む").click()
        # print("申し込みボタンをクリックする直前で停止しました。")
        #
        # # 確認のためにブラウザを開いたままにする
        # input("Enterキーを押すとブラウザを閉じます...")
        browser.close()


def send_slack_message(page_url="", title=""):
    # Initialize a WebClient instance with your OAuth token
    client = WebClient(token=SLACK_OAUTH_TOKEN)

    # The channel ID or name where you want to send the message
    channel_id = "rob-notes"

    # The bot name
    bot_name = "rob notifier"

    # The message you want to send
    message = "@channel Found a time slot for '{}'! {} ".format(title, page_url)

    try:
        # Use the chat.postMessage method to send a message to the channel
        response = client.chat_postMessage(channel=channel_id, text=message, username=bot_name)
        print("Message sent successfully!")
    except SlackApiError as e:
        # Error handling in case the message fails to send
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    run_booking_flow()
    #send_slack_message(page_url="suck", title="meh")