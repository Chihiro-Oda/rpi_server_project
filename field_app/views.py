# field_app/views.py
import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required  # ログイン必須にする
from django.shortcuts import render, redirect
from django.urls import reverse

import config
from .forms import FieldReportForm
from .models import UnsyncedCheckin, UnsyncedFieldReport


@login_required  # ログインしていないとアクセスできないようにする
def home_view(request):
    """
    現場操作のホームメニュー画面を表示するビュー
    """
    return render(request, 'field_app/home.html')


# --- 避難所受付ビュー (ガワだけ) ---
@login_required
def shelter_checkin_view(request):
    """
    避難所受付画面の表示と、チェックイン/アウト記録の受付
    """
    # POSTリクエスト（JavaScriptからフォームが送信された）の場合
    if request.method == 'POST':
        login_id = request.POST.get('login_id')
        checkin_type = request.POST.get('checkin_type')

        # 簡単なバリデーション
        if not login_id or not checkin_type:
            messages.error(request, 'QRコードの読み取り、または種別の選択に失敗しました。')
            return redirect('field_app:shelter_checkin')

        if checkin_type not in ['checkin', 'checkout']:
            messages.error(request, '無効な種別が指定されました。')
            return redirect('field_app:shelter_checkin')

        # ローカルDBに一時保存
        try:
            UnsyncedCheckin.objects.create(
                login_id=login_id,
                shelter_id=config.SHELTER_ID,
                checkin_type=checkin_type,
            )
            type_display = "入所" if checkin_type == 'checkin' else "退所"
            messages.success(request, f'ID: {login_id} さんの「{type_display}」を記録しました。')
        except Exception as e:
            messages.error(request, f'データベースへの記録中にエラーが発生しました: {e}')

        return redirect('field_app:shelter_checkin')

    # GETリクエスト（通常の画面表示）
    # 直近5件の記録を取得して画面に表示する
    recent_checkins = UnsyncedCheckin.objects.all()[:5]
    context = {
        'recent_checkins': recent_checkins,
    }
    return render(request, 'field_app/shelter_checkin.html', context)


def get_distribution_items():
    """（ヘルパー関数）中央サーバーから配布物資のリストを取得する"""
    try:
        # このAPIは別途作成する必要がある
        response = requests.get(config.CENTRAL_SERVER_URL + "/api/distribution-items/", timeout=3)
        if response.status_code == 200:
            return response.json().get('items', [])
    except requests.exceptions.RequestException:
        return []  # 失敗した場合は空のリストを返す
    return []


@login_required
def food_distribution_view(request):
    context = {}

    # 中央サーバーから配布物資リストを取得
    distribution_items = get_distribution_items()
    if not distribution_items:
        messages.warning(request, "中央サーバーから配布物資リストを取得できませんでした。オフラインの可能性があります。")

    context['distribution_items'] = distribution_items

    # フォームが送信された場合
    if request.method == 'POST':
        login_id = request.POST.get('login_id')
        item_id = request.POST.get('item_id')

        # 中央サーバーのAPIに問い合わせ
        try:
            payload = {
                'login_id': login_id,
                'item_id': item_id,
                'device_id': config.DEVICE_ID,
                'action': 'record'  # 判定と記録を同時に行う
            }
            api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'check-distribution/'
            response = requests.post(api_url, json=payload, timeout=5)

            api_result = response.json()
            context['api_result'] = api_result  # 結果をテンプレートに渡す
            context['last_query'] = {'login_id': login_id, 'item_id': item_id}

            if response.status_code == 200:
                messages.success(request, api_result.get('message', '判定が完了しました。'))
            else:
                messages.error(request, api_result.get('message', '判定中にエラーが発生しました。'))

        except requests.exceptions.RequestException:
            messages.error(request, "中央サーバーに接続できませんでした。")

    return render(request, 'field_app/food_distribution.html', context)


@login_required
def field_report_view(request):
    """
    現場状況報告ページの表示と、報告データの受付
    """
    if request.method == 'POST':
        form = FieldReportForm(request.POST)
        if form.is_valid():
            # DBに保存する前に、shelter_idをセット
            report = form.save(commit=False)
            report.shelter_id = config.SHELTER_ID  # configから取得
            report.save()
            messages.success(request, '現場状況を記録しました。(オンライン時に自動で中央サーバーに送信されます)')
            return redirect('field_app:home')  # 成功したらホームに戻る
    else:
        form = FieldReportForm()

    # 直近の報告履歴を表示
    recent_reports = UnsyncedFieldReport.objects.all()[:3]

    context = {
        'form': form,
        'recent_reports': recent_reports
    }
    return render(request, 'field_app/field_report.html', context)


@login_required
def field_chat_view(request):
    """
    現場チャット画面の表示
    """
    # 選択されているグループIDを取得 (GETパラメータから)
    # 例: /chat/?group_id=3
    selected_group_id = request.GET.get('group_id', 'all')

    if request.method == 'POST':
        group_id = request.POST.get('group_id')
        message = request.POST.get('message')

        if group_id == 'all':  # "本部 (全体連絡)" が選択された場合
            #  全体連絡用のAPIを別途実装するか、特定のグループIDを割り当てる
            messages.info(request, "（未実装）本部への全体連絡を送信しました。")
        elif group_id and message:
            try:
                headers = {'X-User-Login-Id': request.user.username}
                payload = {'group_id': group_id, 'message': message}
                api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'post-group-message/'

                response = requests.post(api_url, headers=headers, json=payload, timeout=5)

                if response.status_code == 200:
                    messages.success(request, "メッセージを送信しました。")
                else:
                    messages.error(request, f"送信エラー: {response.json().get('message')}")

            except requests.exceptions.RequestException:
                messages.error(request, "サーバーに接続できず、メッセージを送信できませんでした。")
                #  未送信メッセージとしてローカルDBに保存するロジック
        else:
            messages.warning(request, "宛先グループとメッセージの両方を入力してください。")

        # return redirect('field_app:field_chat')  # POST後は同じページにリダイレクト
        # redirect先を、選択していたグループIDを維持するように変更
        return redirect(f"{reverse('field_app:field_chat')}?group_id={group_id}")

    groups = []
    try:
        # 中央サーバーに参加グループを問い合わせる
        headers = {'X-User-Login-Id': request.user.username}  # usernameにlogin_idが入っている前提
        api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'get-user-groups/'
        response = requests.get(api_url, headers=headers, timeout=5)

        if response.status_code == 200:
            groups = response.json().get('groups', [])
        else:
            messages.error(request, f"グループ情報の取得に失敗しました: {response.json().get('message')}")

    except requests.exceptions.RequestException:
        messages.error(request, "中央サーバーに接続できず、グループ情報を取得できませんでした。")

    context = {
        'groups': groups,
    }

    messages_history = []
    if selected_group_id != 'all':
        try:
            headers = {'X-User-Login-Id': request.user.username}
            api_url = f"{config.CENTRAL_SERVER_URL}{config.API_BASE_PATH}groups/{selected_group_id}/messages/"

            response = requests.get(api_url, headers=headers, timeout=5)

            if response.status_code == 200:
                messages_history = response.json().get('messages', [])
            else:
                messages.error(request, f"メッセージ履歴の取得に失敗: {response.json().get('message')}")

        except requests.exceptions.RequestException:
            messages.error(request, "サーバーに接続できず、メッセージ履歴を取得できませんでした。")

    context = {
        'groups': groups,
        'selected_group_id': selected_group_id,
        'messages_history': messages_history,
    }
    return render(request, 'field_app/field_chat.html', context)
