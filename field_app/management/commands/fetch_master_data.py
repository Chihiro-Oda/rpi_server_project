import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from field_app.models import DistributionItem, User  # ラズパイ側のモデル
import config
from field_app.utils import get_active_central_url


class Command(BaseCommand):
    help = '中央サーバーからマスタデータ（ユーザー、配布品目）を取得してUUIDを含めて同期する'

    def handle(self, *args, **options):
        self.stdout.write("--- データ同期を開始します ---")

        # 1. 配布物資マスタの同期
        self.fetch_distribution_items()

        # 2. ユーザー情報の同期
        self.fetch_users()

        self.stdout.write("--- データ同期が完了しました ---")

    def fetch_distribution_items(self):
        now = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(f'[{now}] 配布品目を同期中...')

        # APIのURL
        url = get_active_central_url() + config.API_BASE_PATH + 'distribution-items/'

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                items = response.json().get('items', [])
                count = 0

                for item_data in items:
                    # 名前をキーにして更新、なければ作成
                    # ★重要: 中央のUUID (item_data['id']) をローカルに強制適用する
                    obj, created = DistributionItem.objects.update_or_create(
                        name=item_data['name'],
                        defaults={
                            'id': item_data['id'],  # UUIDを同期
                            'description': item_data.get('description', ''),
                        }
                    )
                    count += 1

                self.stdout.write(self.style.SUCCESS(f'品目マスタ更新完了: {count}件'))
            else:
                self.stdout.write(self.style.ERROR(f'品目取得失敗: {response.status_code}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'品目通信エラー: {e}'))

    def fetch_users(self):
        now = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(self.style.SUCCESS(f'[{now}]--- ユーザー情報の同期 ---'))

        url = get_active_central_url() + config.API_BASE_PATH + 'get-all-users/'

        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                users_data = response.json().get('users', [])
                created_count = 0
                updated_count = 0

                for u_data in users_data:
                    # 1. 同じusernameのユーザーが既にいるか確認
                    try:
                        local_user = User.objects.get(username=u_data['username'])

                        # 2. いる場合、ID(UUID)が一致しているか確認
                        if str(local_user.id) != u_data['id']:
                            # IDが違う場合（ローカルで手動作成したユーザー等）
                            # 古いユーザーを削除しないと、Unique制約で新しいIDのユーザーを作れない
                            self.stdout.write(self.style.WARNING(
                                f"  競合検出: {u_data['username']} のID不一致。ローカルを削除して再作成します。"))
                            local_user.delete()

                            # 削除したので新規作成へ
                            self.create_user_from_data(u_data)
                            created_count += 1
                        else:
                            # IDが合っていれば属性を更新
                            self.update_user_from_data(local_user, u_data)
                            updated_count += 1

                    except User.DoesNotExist:
                        # 3. いない場合は新規作成
                        self.create_user_from_data(u_data)
                        created_count += 1

                self.stdout.write(self.style.SUCCESS(
                    f'ユーザー同期完了: 新規 {created_count} / 更新 {updated_count}'
                ))

            else:
                self.stdout.write(self.style.ERROR(f'ユーザー取得失敗: HTTP {response.status_code}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ユーザー通信エラー: {e}'))

    # --- ヘルパーメソッド ---
    def create_user_from_data(self, data):
        """データからユーザーを新規作成（パスワードはハッシュ済みをセット）"""
        u = User(
            id=data['id'],  # UUIDを強制指定
            username=data['username'],
            full_name=data['full_name'],
            email=data['email'],
            role=data['role'],
            is_active=True,
            is_staff=(data['role'] == 'admin'),  # adminロールなら管理画面に入れるように
            is_superuser=(data['role'] == 'admin')
        )
        u.password = data['password']  # ハッシュ済みパスワードを直接セット
        u.save()

    def update_user_from_data(self, user, data):
        """既存ユーザーの情報を更新"""
        user.full_name = data['full_name']
        user.email = data['email']
        user.role = data['role']
        user.password = data['password']  # パスワード変更も反映
        user.is_active = True
        user.is_staff = (data['role'] == 'admin')
        user.is_superuser = (data['role'] == 'admin')
        user.save()