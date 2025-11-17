# field_app/management/commands/sync_data.py

import requests
from django.core.management.base import BaseCommand
import config  # ラズパイ側のプロジェクトルートにある config.py
from field_app.models import UnsyncedCheckin, UnsyncedFieldReport

class Command(BaseCommand):
    help = '未同期のデータを中央サーバーに一括で送信します。'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('===== データ同期処理を開始します ====='))

        # ネットワーク接続があるか、まず最初に軽くチェック
        if not self.check_network_connection():
            self.stderr.write(self.style.ERROR('ネットワークに接続できません。同期処理を中断します。'))
            return

        # 1. 未同期の「避難所チェックイン記録」を同期
        self.sync_checkins()

        # 2. 未同期の「現場状況報告」を同期
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
                "login_id": record.login_id,
                "shelter_management_id": config.SHELTER_ID, # configから管理IDを取得
                "checkin_type": record.checkin_type,
                "timestamp": record.timestamp.isoformat(), # ISO 8601形式の文字列に変換
                "device_id": config.DEVICE_ID
            }
            try:
                response = requests.post(api_url, json=payload, timeout=10)
                if response.status_code in [200, 201]:  # 成功 (201 Created も考慮)
                    record.is_synced = True
                    record.last_sync_error = None
                    record.save()
                    self.stdout.write(self.style.SUCCESS(f'  -> ID {record.id}: 同期成功'))
                else: # APIがエラーを返した場合
                    error_msg = response.json().get('message', '不明なサーバーエラー')
                    record.last_sync_error = f"HTTP {response.status_code}: {error_msg}"
                    record.sync_attempts += 1
                    record.save()
                    self.stdout.write(self.style.ERROR(f'  -> ID {record.id}: 同期失敗 - {error_msg}'))

            except requests.exceptions.RequestException as e: # ネットワーク接続エラー
                record.last_sync_error = f"ネットワークエラー: {e}"
                record.sync_attempts += 1
                record.save()
                self.stdout.write(self.style.ERROR(f'  -> ID {record.id}: ネットワーク接続エラー'))
                self.stderr.write('中央サーバーへの接続が失われました。このタスクを中断します。')
                break # ネットワークが切れたら、このループは中断

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