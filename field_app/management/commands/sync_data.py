# field_app/management/commands/sync_data.py

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q

import config  # ラズパイ側のプロジェクトルートにある config.py
from field_app.models import UnsyncedCheckin, UnsyncedFieldReport, UnsyncedUserRegistration, User


class Command(BaseCommand):
    help = '未同期のデータを中央サーバーに一括で送信します。'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('===== データ同期処理を開始します ====='))

        # ネットワーク接続があるか、まず最初に軽くチェック
        if not self.check_network_connection():
            self.stderr.write(self.style.ERROR('ネットワークに接続できません。同期処理を中断します。'))
            return

        # 1. 未同期の「新規ユーザー仮登録」を同期
        self.sync_user_registrations()

        # 2. 未同期の「避難所チェックイン記録」を同期
        self.sync_checkins()

        # 3. 未同期の「現場状況報告」を同期
        self.sync_field_reports()

        self.stdout.write(self.style.SUCCESS('===== 全ての同期処理が完了しました ====='))

    def check_network_connection(self):
        """中央サーバーのルートにアクセスできるか簡単な疎通確認を行う"""
        try:
            requests.get(config.CENTRAL_SERVER_URL, timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    def sync_checkins(self):
        """未同期のチェックイン記録を同期する"""
        self.stdout.write("\n--- [1/2] 避難所チェックイン記録の同期を開始 ---")
        unsynced_records = UnsyncedCheckin.objects.filter(is_synced=False)

        if not unsynced_records:
            self.stdout.write(self.style.SUCCESS('同期対象のチェックイン記録はありませんでした。'))
            return

        self.stdout.write(f'{len(unsynced_records)}件の未同期チェックインを同期します...')
        api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'shelter-checkin-sync/'

        for record in unsynced_records:
            payload = {
                "username": record.username,
                "shelter_management_id": config.SHELTER_ID,  # configから管理IDを取得
                "checkin_type": record.checkin_type,
                "timestamp": record.timestamp.isoformat(),  # ISO 8601形式の文字列に変換
                "device_id": config.DEVICE_ID
            }
            try:
                response = requests.post(api_url, json=payload, timeout=10)
                if response.status_code in [200, 201]:  # 成功 (201 Created も考慮)
                    record.is_synced = True
                    record.last_sync_error = None
                    record.save()
                    self.stdout.write(self.style.SUCCESS(f'  -> ID {record.id}: 同期成功'))
                else:  # APIがエラーを返した場合
                    error_msg = response.json().get('message', '不明なサーバーエラー')
                    record.last_sync_error = f"HTTP {response.status_code}: {error_msg}"
                    record.sync_attempts += 1
                    record.save()
                    self.stdout.write(self.style.ERROR(f'  -> ID {record.id}: 同期失敗 - {error_msg}'))

            except requests.exceptions.RequestException as e:  # ネットワーク接続エラー
                record.last_sync_error = f"ネットワークエラー: {e}"
                record.sync_attempts += 1
                record.save()
                self.stdout.write(self.style.ERROR(f'  -> ID {record.id}: ネットワーク接続エラー'))
                self.stderr.write('中央サーバーへの接続が失われました。このタスクを中断します。')
                break  # ネットワークが切れたら、このループは中断

    def sync_field_reports(self):
        """未同期の現場状況報告を同期する"""
        self.stdout.write("\n--- [2/2] 現場状況報告の同期を開始 ---")
        unsynced_records = UnsyncedFieldReport.objects.filter(is_synced=False)

        if not unsynced_records:
            self.stdout.write(self.style.SUCCESS('同期対象の現場レポートはありませんでした。'))
            return

        self.stdout.write(f'{len(unsynced_records)}件の未同期レポートを同期します...')
        api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'field-report/'

        for record in unsynced_records:
            payload = {
                "shelter_management_id": config.SHELTER_ID,
                "current_evacuees": record.current_evacuees,
                "medical_needs": record.medical_needs,
                "food_stock": record.food_stock,
                "timestamp": record.timestamp.isoformat(),
                "device_id": config.DEVICE_ID
            }
            try:
                response = requests.post(api_url, json=payload, timeout=10)
                if response.status_code in [200, 201]:
                    record.is_synced = True
                    record.save()
                    self.stdout.write(self.style.SUCCESS(f'  -> ID {record.id}: 同期成功'))
                else:
                    self.stdout.write(self.style.ERROR(f'  -> ID {record.id}: 同期失敗 - {response.text}'))

            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f'  -> ID {record.id}: ネットワーク接続エラー'))
                self.stderr.write('中央サーバーへの接続が失われました。このタスクを中断します。')
                break

    def sync_user_registrations(self):

        self.stdout.write("\n--- [3/3] 新規ユーザー仮登録の同期を開始 ---")
        unsynced_users = UnsyncedUserRegistration.objects.filter(
            Q(sync_error__isnull=True) | Q(sync_error=''),
            is_synced=False
        )

        if not unsynced_users:
            self.stdout.write(self.style.SUCCESS('同期対象の仮登録ユーザーはいませんでした。'))
            return

        api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'register-field-user/'

        for user_reg in unsynced_users:
            payload = {
                "full_name": user_reg.full_name,
                "username": user_reg.username,
                "password": user_reg.password,  # ハッシュ済みのパスワードを送る
            }
            try:
                response = requests.post(api_url, json=payload, timeout=10)

                # ★ 変更点: JSONデコードを try の中ではなく、ステータスコード確認後に行う
                if response.status_code == 201:  # 成功
                    user_reg.is_synced = True
                    user_reg.sync_error = None  # エラーをクリア
                    user_reg.save()

                    if not User.objects.filter(username=user_reg.username).exists():
                        User.objects.create_user(
                            username=user_reg.username,
                            password=user_reg.password,  # 生のパスワードを渡すとハッシュ化して保存される
                            full_name=user_reg.full_name,
                            role='general'  # デフォルトは一般ユーザーとして作成
                        )
                        self.stdout.write(self.style.SUCCESS(f'     (ラズパイ内にもユーザーを作成しました)'))

                    self.stdout.write(self.style.SUCCESS(f'  -> ユーザー {user_reg.username}: 本登録成功'))

                else:  # API側でロジックエラー (400, 409, 500など)
                    # JSONとして解析できるか試す
                    try:
                        error_json = response.json()
                        error_msg = error_json.get('message', '不明なエラー')
                    except ValueError:
                        # JSONじゃなかった場合（500エラーでHTMLが返ってきた時など）
                        error_msg = f"サーバーエラー (Raw): {response.text[:100]}..."  # 最初の100文字だけ表示

                    # データベースにエラーを保存
                    user_reg.sync_error = f"HTTP {response.status_code}: {error_msg}"
                    user_reg.save()

                    # ★ ターミナルに見やすく出力
                    self.stdout.write(
                        self.style.ERROR(f'  -> ユーザー {user_reg.username}: 失敗 (HTTP {response.status_code})'))
                    self.stdout.write(self.style.WARNING(f'     理由: {error_msg}'))

            except requests.exceptions.RequestException as e:
                # 通信自体の失敗（タイムアウト、DNSエラーなど）
                user_reg.sync_error = f"ネットワーク接続エラー: {str(e)}"
                user_reg.save()

                self.stdout.write(self.style.ERROR(f'  -> ユーザー {user_reg.username}: ネットワーク接続エラー'))
                self.stderr.write(f'詳細: {str(e)}')
                self.stderr.write('中央サーバーへの接続が失われました。このタスクを中断します。')
                break

