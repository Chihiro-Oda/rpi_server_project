from django.core.management.base import BaseCommand
from django.utils import timezone
import requests
import config  # プロジェクトルートのconfig.py
from field_app.models import UnsyncedFieldReport


class Command(BaseCommand):
    help = '未同期の現場状況報告を中央サーバーに送信します。'

    def handle(self, *args, **kwargs):
        # 1. 未同期のレポートを取得
        unsynced_reports = UnsyncedFieldReport.objects.filter(is_synced=False)

        if not unsynced_reports:
            self.stdout.write(self.style.SUCCESS('同期対象のレポートはありませんでした。'))
            return

        self.stdout.write(f'{len(unsynced_reports)}件の未同期レポートを同期します...')

        api_url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'field-report/'  # APIエンドポイント

        # 2. 1件ずつAPIに送信
        for report in unsynced_reports:
            payload = {
                "shelter_id": report.shelter_id,
                "current_evacuees": report.current_evacuees,
                "medical_needs": report.medical_needs,
                "food_stock": report.food_stock,
                "timestamp": report.timestamp.isoformat(),  # ISO 8601形式の文字列に変換
                "device_id": config.DEVICE_ID
            }

            try:
                response = requests.post(api_url, json=payload, timeout=10)

                # 3. APIからの応答に応じて処理
                if response.status_code == 200 or response.status_code == 201:  # 成功 (201 Created も考慮)
                    # 同期成功したら、フラグを立てる
                    report.is_synced = True
                    report.last_sync_error = None
                    report.save()
                    self.stdout.write(self.style.SUCCESS(f' -> レポートID {report.id}: 同期成功'))
                else:
                    # APIがエラーを返した場合
                    error_msg = response.json().get('message', '不明なサーバーエラー')
                    report.last_sync_error = f"HTTP {response.status_code}: {error_msg}"
                    report.sync_attempts += 1
                    report.save()
                    self.stdout.write(self.style.ERROR(f' -> レポートID {report.id}: 同期失敗 - {error_msg}'))

            except requests.exceptions.RequestException as e:
                # ネットワーク接続エラーの場合
                report.last_sync_error = f"ネットワークエラー: {e}"
                report.sync_attempts += 1
                report.save()
                self.stdout.write(self.style.ERROR(f' -> レポートID {report.id}: ネットワーク接続エラー'))
                # ネットワークエラーが起きたら、一旦処理を中断するのが賢明
                self.stderr.write('中央サーバーに接続できませんでした。処理を中断します。')
                break

        self.stdout.write('同期処理が完了しました。')