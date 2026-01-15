# management/commands/sync_report.py
import requests
from django.core.management.base import BaseCommand

import config
from field_app.models import UnsyncedFieldReport, UnsyncedCheckin  # UnsyncedCheckin をインポート
from field_app.utils import get_active_central_url


class Command(BaseCommand):
    help = '未同期のデータを中央サーバーに送信します。'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('===== データ同期処理を開始します ====='))

        # --- 1. 現場状況報告の同期 ---
        self.sync_field_reports()

        # --- 2. 避難所チェックイン記録の同期 ---
        self.sync_checkins()

        self.stdout.write(self.style.SUCCESS('===== 全ての同期処理が完了しました ====='))

    def sync_field_reports(self):
        """未同期の現場状況報告を同期する"""
        self.stdout.write("\n--- 現場状況報告の同期を開始 ---")
        unsynced_reports = UnsyncedFieldReport.objects.filter(is_synced=False)

        if not unsynced_reports:
            self.stdout.write(self.style.SUCCESS('同期対象のレポートはありませんでした。'))
            return

        self.stdout.write(f'{len(unsynced_reports)}件の未同期レポートを同期します...')
        api_url = get_active_central_url() + config.API_BASE_PATH + 'field-report/'

        for report in unsynced_reports:
            payload = {
                "shelter_id": report.shelter_id,
                "current_evacuees": report.current_evacuees,
                "medical_needs": report.medical_needs,
                "food_stock": report.food_stock,
                "timestamp": report.timestamp.isoformat(),
                "device_id": config.DEVICE_ID
            }
            try:
                response = requests.post(api_url, json=payload, timeout=10, verify=config.VERIFY_SSL)
                if response.status_code in [200, 201]:
                    report.is_synced = True
                    # report.last_sync_error = None # モデルにフィールドを追加した場合
                    report.save()
                    self.stdout.write(self.style.SUCCESS(f' -> レポートID {report.id}: 同期成功'))
                else:
                    error_msg = response.json().get('message', '不明なサーバーエラー')
                    # report.last_sync_error = f"HTTP {response.status_code}: {error_msg}" # モデルにフィールドを追加した場合
                    # report.sync_attempts += 1 # モデルにフィールドを追加した場合
                    report.save()
                    self.stdout.write(self.style.ERROR(f' -> レポートID {report.id}: 同期失敗 - {error_msg}'))
            except requests.exceptions.RequestException as e:
                # report.last_sync_error = f"ネットワークエラー: {e}" # モデルにフィールドを追加した場合
                # report.sync_attempts += 1 # モデルにフィールドを追加した場合
                report.save()
                self.stdout.write(self.style.ERROR(f' -> レポートID {report.id}: ネットワーク接続エラー'))
                self.stderr.write('中央サーバーに接続できませんでした。この処理を中断します。')
                break  # 現場報告の同期を中断

    def sync_checkins(self):
        """未同期のチェックイン記録を同期する"""
        self.stdout.write("\n--- 避難所チェックイン記録の同期を開始 ---")
        unsynced_checkins = UnsyncedCheckin.objects.filter(is_synced=False)

        if not unsynced_checkins:
            self.stdout.write(self.style.SUCCESS('同期対象のチェックイン記録はありませんでした。'))
            return

        self.stdout.write(f'{len(unsynced_checkins)}件の未同期チェックインを同期します...')
        # ★★★ 中央サーバー側のAPIエンドポイントに合わせて修正してください ★★★
        api_url = get_active_central_url() + config.API_BASE_PATH + 'shelter-checkin-sync/'

        for checkin in unsynced_checkins:
            payload = {
                "username": checkin.username,
                "shelter_management_id": checkin.shelter_id,
                "checkin_type": checkin.checkin_type,
                "timestamp": checkin.timestamp.isoformat(),
                "device_id": config.DEVICE_ID
            }
            try:
                response = requests.post(api_url, json=payload, timeout=10, verify=config.VERIFY_SSL)
                if response.status_code in [200, 201]:
                    checkin.is_synced = True
                    checkin.last_sync_error = None
                    checkin.save()
                    self.stdout.write(self.style.SUCCESS(f' -> チェックインID {checkin.id}: 同期成功'))
                else:
                    error_msg = response.json().get('message', '不明なサーバーエラー')
                    checkin.last_sync_error = f"HTTP {response.status_code}: {error_msg}"
                    checkin.sync_attempts += 1
                    checkin.save()
                    self.stdout.write(self.style.ERROR(f' -> チェックインID {checkin.id}: 同期失敗 - {error_msg}'))
            except requests.exceptions.RequestException as e:
                checkin.last_sync_error = f"ネットワークエラー: {e}"
                checkin.sync_attempts += 1
                checkin.save()
                self.stdout.write(self.style.ERROR(f' -> チェックインID {checkin.id}: ネットワーク接続エラー'))
                self.stderr.write('中央サーバーに接続できませんでした。この処理を中断します。')
                break  # チェックインの同期を中断
