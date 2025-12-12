# field_app/views.py
import subprocess
import sys

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test  # ログイン必須にする
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

import config
from .forms import FieldReportForm, UnsyncedUserEditForm, FieldSignUpForm
from .models import UnsyncedCheckin, UnsyncedFieldReport, UnsyncedUserRegistration


@login_required  # ログインしていないとアクセスできないようにする
def home_view(request):
    """
    現場操作のホームメニュー画面を表示するビュー
    """
    # 各モデルの未同期件数を取得
    unsynced_checkin_count = UnsyncedCheckin.objects.filter(is_synced=False).count()
    unsynced_report_count = UnsyncedFieldReport.objects.filter(is_synced=False).count()

    context = {
        'unsynced_checkin_count': unsynced_checkin_count,
        'unsynced_report_count': unsynced_report_count,
        # 'last_sync_time': ... (最終同期時刻をどこかに保存するなら、それを取得)
    }
    return render(request, 'field_app/home.html', context)


@require_POST  # POSTリクエストのみを受け付ける
@login_required
def manual_sync_view(request):
    """
    手動でのデータ同期をトリガーするビュー。
    バックグラウンドで `sync_data` 管理コマンドを実行する。
    """
    try:
        # 実行するコマンドを準備
        # sys.executable は現在実行中のPythonインタプリタのパス (/path/to/.venv/bin/python)
        # manage.py のフルパスを指定
        manage_py_path = settings.BASE_DIR / "manage.py"
        command = [sys.executable, str(manage_py_path), "sync_data"]

        # Popenを使って非同期でコマンドを実行
        # これにより、同期処理の完了を待たずに、すぐにレスポンスを返すことができる
        subprocess.Popen(command)

        messages.success(request, "データ同期処理を開始しました。完了まで数分かかる場合があります。")

    except Exception as e:
        messages.error(request, f"同期処理の開始に失敗しました: {e}")

    # 処理の成否に関わらず、ホーム画面にリダイレクトする
    return redirect('field_app:home')


# --- 避難所受付ビュー ---
@login_required
def shelter_checkin_view(request):
    """
    避難所受付画面の表示と、チェックイン/アウト記録の受付
    """
    # POSTリクエスト（JavaScriptからフォームが送信された）の場合
    if request.method == 'POST':
        username = request.POST.get('username')
        checkin_type = request.POST.get('checkin_type')

        # 簡単なバリデーション
        if not username or not checkin_type:
            messages.error(request, 'QRコードの読み取り、または種別の選択に失敗しました。')
            return redirect('field_app:shelter_checkin')

        if checkin_type not in ['checkin', 'checkout']:
            messages.error(request, '無効な種別が指定されました。')
            return redirect('field_app:shelter_checkin')

        # 連続入退所のチェック
        # このユーザーの「最新の記録」を1件取得する
        last_record = UnsyncedCheckin.objects.filter(username=username).order_by('-timestamp').first()

        if last_record and last_record.checkin_type == checkin_type:
            # 直前の記録と同じ種別だった場合、保存せずに警告を出す
            action_name = "入所" if checkin_type == 'checkin' else "退所"
            messages.warning(request,
                                f'ID: {username} さんは既に「{action_name}」済みです。連続して同じ操作はできません。')

            # エラーではないので、リダイレクトして終了
            return redirect('field_app:shelter_checkin')

        # ローカルDBに一時保存
        try:
            UnsyncedCheckin.objects.create(
                username=username,
                shelter_id=config.SHELTER_ID,
                checkin_type=checkin_type,
            )
            type_display = "入所" if checkin_type == 'checkin' else "退所"
            messages.success(request, f'ID: {username} さんの「{type_display}」を記録しました。')
        except Exception as e:
            messages.error(request, f'データベースへの記録中にエラーが発生しました: {e}')

        return redirect('field_app:shelter_checkin')

    # GETリクエスト（通常の画面表示）
    # 直近5件の記録を取得して画面に表示する
    recent_checkins = UnsyncedCheckin.objects.all()[:5]
    context = {
        'recent_checkins': recent_checkins,
        'debug': settings.DEBUG,
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
        username = request.POST.get('username')
        item_id = request.POST.get('item_id')

        # 中央サーバーのAPIに問い合わせ
        try:
            payload = {
                'username': username,
                'item_id': item_id,
                'device_id': config.DEVICE_ID,
                'action': 'record'  # 判定と記録を同時に行う
            }
            api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'check-distribution/'
            response = requests.post(api_url, json=payload, timeout=5)

            api_result = response.json()
            context['api_result'] = api_result  # 結果をテンプレートに渡す
            context['last_query'] = {'username': username, 'item_id': item_id}

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
    現場チャット画面の表示（画像送信対応版）
    """
    print(f"DEBUG: field_chat_view called. Method: {request.method}, User: {request.user.username}")
    # 選択されているグループIDを取得 (デフォルトは 'all')
    selected_group_id = request.GET.get('group_id', 'all')
    print(f"DEBUG: Selected group ID: {selected_group_id}")

    # ---------------------------------------------------------
    # 1. メッセージ送信処理 (POST)
    # ---------------------------------------------------------
    if request.method == 'POST':
        print("DEBUG: Handling POST request for chat message.")
        group_id = request.POST.get('group_id')

        # 権限チェック: 全体連絡は管理者のみ
        if group_id == 'all':
            if request.user.role not in ['admin', 'rescuer'] and not request.user.is_superuser:
                messages.error(request, "全体連絡への送信権限がありません。")
                print(f"DEBUG: Permission denied for user {request.user.username} to send to group 'all'.")
                return redirect(f"{reverse('field_app:field_chat')}?group_id={group_id}")

        message = request.POST.get('message', '')
        image_file = request.FILES.get('image')  # 画像ファイルを取得
        print(f"DEBUG: Group ID: {group_id}, Message: '{message[:50]}...', Image file present: {bool(image_file)}")

        # ★★★ 修正: メッセージ または 画像 があれば送信許可 ★★★
        if group_id and (message or image_file):
            try:
                headers = {'X-User-Login-Id': request.user.username}

                # ★★★ 修正: requests用のデータ構築 ★★★
                # テキストデータは 'data' 引数に渡す辞書へ
                data_payload = {
                    'group_id': group_id,
                    'message': message
                }

                # ファイルデータは 'files' 引数に渡す辞書へ
                files_payload = {}
                if image_file:
                    # {'フォームのフィールド名': ファイルオブジェクト}
                    files_payload = {'image': image_file}

                api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'post-group-message/'
                print(f"DEBUG: Sending chat message to API: {api_url}")
                print(f"DEBUG: Headers: {headers}")
                print(f"DEBUG: Data payload: {data_payload}")
                print(f"DEBUG: Files payload keys: {files_payload.keys()}")

                # ★★★ 修正: json=... ではなく data=... と files=... を使う ★★★
                # これにより Content-Type が multipart/form-data に自動設定されます
                response = requests.post(
                    api_url,
                    headers=headers,
                    data=data_payload,
                    files=files_payload,
                    timeout=10,  # 画像送信を含むためタイムアウトを少し長めに
                    verify=config.VERIFY_SSL # SSL検証設定を追加
                )
                print(f"DEBUG: Chat API response status code: {response.status_code}")

                if response.status_code == 200:
                    messages.success(request, "送信しました。")
                    print("DEBUG: Chat message sent successfully.")
                else:
                    # エラーレスポンスの解析
                    try:
                        error_msg = response.json().get('message', '不明なエラー')
                    except ValueError:
                        error_msg = f"HTTP {response.status_code}"
                    messages.error(request, f"送信エラー: {error_msg}")
                    print(f"DEBUG: Chat message send error: {error_msg}")

            except requests.exceptions.RequestException as e:
                # エラー詳細をログに出すなどしても良い
                print(f"DEBUG: Connection Error during chat message send: {e}")
                messages.error(request, "サーバーに接続できず、メッセージを送信できませんでした。")
                # 将来的なTodo: 未送信メッセージとしてローカルDBに保存するロジック
        else:
            messages.warning(request, "宛先グループと、メッセージまたは画像を入力してください。")
            print("DEBUG: Missing group ID, message, or image file.")

        # 選択していたグループIDを維持してリダイレクト
        return redirect(f"{reverse('field_app:field_chat')}?group_id={group_id}")

    # ---------------------------------------------------------
    # 2. グループリストの取得
    # ---------------------------------------------------------
    groups = []
    print("DEBUG: Fetching group list.")
    try:
        headers = {'X-User-Login-Id': request.user.username}
        api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'get-user-groups/'
        print(f"DEBUG: Group list API URL: {api_url}, Headers: {headers}")
        response = requests.get(api_url, headers=headers, timeout=5, verify=config.VERIFY_SSL) # SSL検証設定を追加

        print(f"DEBUG: Group list API response status code: {response.status_code}")
        if response.status_code == 200:
            groups = response.json().get('groups', [])
            print(f"DEBUG: Successfully fetched {len(groups)} groups.")
        else:
            messages.error(request, f"グループ情報の取得に失敗しました: {response.status_code}")
            print(f"DEBUG: Failed to fetch groups: {response.status_code}, Response: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Connection Error during group list fetch: {e}")
        messages.error(request, "中央サーバーに接続できず、グループ情報を取得できませんでした。")

    # ---------------------------------------------------------
    # 3. メッセージ履歴の取得
    # ---------------------------------------------------------
    messages_history = []

    if selected_group_id:
        print(f"DEBUG: Fetching message history for group: {selected_group_id}")
        try:
            headers = {'X-User-Login-Id': request.user.username}

            # URL構築: groups/all/messages/ または groups/1/messages/
            api_url = f"{config.CENTRAL_SERVER_URL}{config.API_BASE_PATH}groups/{selected_group_id}/messages/"
            print(f"DEBUG: Message history API URL: {api_url}, Headers: {headers}")

            response = requests.get(api_url, headers=headers, timeout=5, verify=config.VERIFY_SSL) # SSL検証設定を追加
            print(f"DEBUG: Message history API response status code: {response.status_code}")

            if response.status_code == 200:
                messages_history = response.json().get('messages', [])
                print(f"DEBUG: Successfully fetched {len(messages_history)} messages for group {selected_group_id}.")
            else:
                try:
                    error_msg = response.json().get('message', '取得失敗')
                except ValueError:
                    error_msg = f"HTTP {response.status_code}"
                messages.error(request, f"履歴取得エラー: {error_msg}")
                print(f"DEBUG: Failed to fetch message history: {error_msg}, Response: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Connection Error during message history fetch: {e}")
            messages.error(request, "サーバーに接続できず、メッセージ履歴を取得できませんでした。")

    context = {
        'groups': groups,
        'selected_group_id': selected_group_id,
        'messages_history': messages_history,
        'central_server_url': config.CENTRAL_SERVER_URL,
        'current_username': request.user.username,  # 自分の判定用
        'current_fullname': request.user.full_name,  # 自分の判定用
    }
    print("DEBUG: Rendering field_chat.html with context.")
    return render(request, 'field_app/field_chat.html', context)


def field_signup_view(request):
    if request.method == 'POST':
        form = FieldSignUpForm(request.POST)
        if form.is_valid():
            # DBに保存（UnsyncedUserRegistrationモデル）
            # フォームで定義した password フィールドの値は自動でモデルの password フィールドに入る
            form.save()

            messages.success(request, '仮登録を受け付けました。管理者の承認（データ同期）をお待ちください。')
            return redirect('field_app:login')  # ログイン画面に戻る
    else:
        form = FieldSignUpForm()

    return render(request, 'field_app/field_signup.html', {'form': form})


def is_field_staff(user):
    # Userモデルにroleがある前提。ない場合は user.is_staff などで代用
    return user.is_authenticated and getattr(user, 'role', 'general') in ['admin', 'rescuer']


# --- 未同期ユーザー一覧 ---
@login_required
@user_passes_test(is_field_staff)
def unsynced_users_list_view(request):
    # 未同期のユーザーを全て取得
    users = UnsyncedUserRegistration.objects.filter(is_synced=False).order_by('-created_at')

    context = {
        'users': users,
    }
    return render(request, 'field_app/unsynced_users_list.html', context)


# --- 未同期ユーザー修正 ---
@login_required
@user_passes_test(is_field_staff)
def unsynced_user_edit_view(request, pk):
    user_reg = get_object_or_404(UnsyncedUserRegistration, pk=pk)

    if request.method == 'POST':
        form = UnsyncedUserEditForm(request.POST, instance=user_reg)
        if form.is_valid():
            saved_user = form.save(commit=False)
            saved_user.sync_error = None
            saved_user.save()

            messages.success(request, f'{saved_user.username} さんの情報を修正しました。次回の同期で再送信されます。')
            return redirect('field_app:unsynced_users_list')

    else:  # GETリクエストの場合
        form = UnsyncedUserEditForm(instance=user_reg)

    # ★★★★★ ここが重要！ ★★★★★
    # この return 文は、if/else のブロックの「外側」にある必要があります。
    # インデントを def unsynced_user_edit_view と同じレベルより一段下げた位置にしてください。

    context = {
        'form': form,
        'user_reg': user_reg,
    }
    return render(request, 'field_app/unsynced_user_edit.html', context)
