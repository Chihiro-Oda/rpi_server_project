import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from field_app.models import DistributionItem, User  # ラズパイ側のモデル
import config


class Command(BaseCommand):
    help = '中央サーバーからマスタデータ（配布品目など）を取得して更新する'

    def handle(self, *args, **options):
        self.fetch_distribution_items()
        self.fetch_users()

    def fetch_distribution_items(self):
        now = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'distribution-items/'  # APIのURL

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                items = response.json().get('items', [])

                for item_data in items:
                    # IDをキーにして更新または作成
                    # (中央サーバーとIDを一致させるため、ラズパイ側のモデルにcentral_idを持たせるか、
                    # 名前で一致させるなどの工夫が必要ですが、簡易的にはupdate_or_createでOK)
                    DistributionItem.objects.update_or_create(
                        name=item_data['name'],
                        defaults={'description': item_data.get('description', '')},
                    )

                end_time = timezone.now().strftime('%H:%M:%S')
                self.stdout.write(self.style.SUCCESS(f'[{end_time}]品目マスタを更新しました: {len(items)}件'))
            else:
                end_time = timezone.now().strftime('%H:%M:%S')
                self.stderr.write(f'[{end_time}]取得失敗: {response.status_code}')

        except Exception as e:
            end_time = timezone.now().strftime('%H:%M:%S')
            self.stderr.write(f'[{end_time}]通信エラー: {e}')

    def fetch_users(self):
        now = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(self.style.SUCCESS(f'[{now}]--- ユーザー情報の同期 ---'))
        url = config.CENTRAL_SERVER_URL + config.API_BASE_PATH + 'get-all-users/'

        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                users_data = response.json().get('users', [])

                # Userオブジェクト自体を格納するリストにする
                created_user_objects = []
                updated_count = 0

                for u_data in users_data:
                    user, created = User.objects.update_or_create(
                        username=u_data['username'],
                        defaults={
                            'password': u_data['password'],
                            'full_name': u_data['full_name'],
                            'email': u_data['email'],
                            'role': u_data['role'],
                            'is_active': True,
                        }
                    )

                    if created:
                        # 文字列ではなく、Userオブジェクトそのものを追加
                        created_user_objects.append(user)
                    else:
                        updated_count += 1

                # 出力時に好きな属性を取り出して整形する
                if created_user_objects:
                    end_time = timezone.now().strftime('%H:%M:%S')

                    # オブジェクトのリストから、必要な情報だけを抽出して文字列リストを作る

                    # パターンA: IDだけ出したい場合
                    display_list = [u.username for u in created_user_objects]

                    # パターンB: IDと氏名を出したい場合（要件変更にすぐ対応可能）
                    # display_list = [f"{u.username}({u.full_name})" for u in created_user_objects]

                    # パターンC: IDと権限を出したい場合
                    # display_list = [f"{u.username}[{u.role}]" for u in created_user_objects]

                    # カンマ区切りにする
                    user_info_str = ", ".join(display_list)

                    self.stdout.write(self.style.SUCCESS(
                        f'[{end_time}] ユーザー同期完了: 新規 {len(created_user_objects)} 名を追加しました ({user_info_str}) (既存更新: {updated_count} 名)'
                    ))

            else:
                end_time = timezone.now().strftime('%H:%M:%S')
                self.stderr.write(f'[{end_time}]取得失敗: HTTP {response.status_code}')

        except Exception as e:
            end_time = timezone.now().strftime('%H:%M:%S')
            self.stderr.write(f'[{end_time}]通信エラー: {e}')