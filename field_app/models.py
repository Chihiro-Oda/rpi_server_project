# field_app/models.py
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.conf import settings  # (もしUserモデルと連携する場合)


class UnsyncedCheckin(models.Model):
    """
    まだ中央サーバーに同期されていない、避難所の入退所記録を一時的に保存するモデル。
    """

    # チェックインかチェックアウトかを区別する選択肢
    CHECKIN_TYPE_CHOICES = (
        ('checkin', '入所'),
        ('checkout', '退所'),
    )

    # 1. 誰が (Who)
    # ユーザーのプライマリーキー(id)ではなく、QRコードから読み取ったusernameをそのまま保存
    username = models.CharField(
        verbose_name="避難者のログインID",
        max_length=150
    )

    # 2. どの避難所で (Where)
    # このラズパイが設置されている避難所のID (config.pyなどで管理)
    shelter_id = models.CharField(
        verbose_name="避難所ID"
    )

    # 3. 何を (What)
    # 入所か退所か
    checkin_type = models.CharField(
        verbose_name="種別",
        max_length=10,
        choices=CHECKIN_TYPE_CHOICES
    )

    # 4. いつ (When)
    # この記録が作成された日時
    timestamp = models.DateTimeField(
        verbose_name="記録日時",
        auto_now_add=True  # レコード作成時に自動で現在日時が設定される
    )

    # 5. 同期状態 (Status)
    # この記録が中央サーバーに送信済みかどうかを示すフラグ
    is_synced = models.BooleanField(
        verbose_name="同期済み",
        default=False,
        db_index=True  # このフィールドで検索することが多いため、インデックスを貼って高速化
    )

    # (オプション) 同期試行回数
    sync_attempts = models.IntegerField(
        verbose_name="同期試行回数",
        default=0
    )

    # (オプション) 同期失敗時のエラーメッセージ
    last_sync_error = models.TextField(
        verbose_name="最終同期エラー",
        blank=True,
        null=True
    )

    def __str__(self):
        # 管理画面などで見やすいように表示形式を定義
        sync_status = "同期済" if self.is_synced else "未同期"
        return f"[{sync_status}] {self.timestamp.strftime('%Y-%m-%d %H:%M')} - {self.username} ({self.get_checkin_type_display()})"

    class Meta:
        verbose_name = "未同期チェックイン記録"
        verbose_name_plural = "未同期チェックイン記録"
        ordering = ['-timestamp']  # 新しい記録から順に表示


class UnsyncedFieldReport(models.Model):
    """
    まだ中央サーバーに同期されていない、現場状況報告を一時的に保存するモデル。
    """
    FOOD_STOCK_CHOICES = (
        ('safe', '3日以上持つ'),
        ('warning', '1日〜3日持つ'),
        ('critical', '本日分で尽きる'),
    )

    # 1. どの避難所から (Where)
    shelter_id = models.CharField(verbose_name="避難所ID")

    # 2. 報告内容 (What)
    current_evacuees = models.PositiveIntegerField(verbose_name="現在避難者数")
    medical_needs = models.PositiveIntegerField(verbose_name="医療・要介護者数")
    food_stock = models.CharField(verbose_name="食料の残量", max_length=10, choices=FOOD_STOCK_CHOICES)

    # 3. いつ (When)
    timestamp = models.DateTimeField(verbose_name="報告日時", auto_now_add=True)

    # 4. 誰が (Who) - 任意
    # reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    # 5. 同期状態 (Status)
    is_synced = models.BooleanField(verbose_name="同期済み", default=False, db_index=True)

    def __str__(self):
        return f"[{'同期済' if self.is_synced else '未同期'}] {self.timestamp.strftime('%Y-%m-%d %H:%M')} - 避難所ID:{self.shelter_id}"

    class Meta:
        verbose_name = "未同期 現場状況報告"
        verbose_name_plural = "未同期 現場状況報告"
        ordering = ['-timestamp']


class UnsyncedUserRegistration(models.Model):
    """中央サーバーに同期されていない、新規ユーザーの仮登録情報"""
    full_name = models.CharField(verbose_name="氏名", max_length=150)
    username = models.CharField(verbose_name="希望ログインID", max_length=150, unique=True)
    password = models.CharField(verbose_name="パスワード (ハッシュ化済)", max_length=128)

    # 同期状態を管理するフィールド
    is_synced = models.BooleanField(verbose_name="同期済み", default=False)
    sync_error = models.TextField(verbose_name="同期エラー", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.username}) - {'同期済' if self.is_synced else '未同期'}"


# 中央サーバーと同じ定義をコピー
class User(AbstractUser):
    # --- カスタムフィールド ---
    ROLE_CHOICES = (
        ('general', '一般ユーザー'),
        ('admin', 'システム管理者'),
        ('rescuer', '救助チーム')
    )
    STATUS_CHOICES = (
        ('safe', '無事'),
        ('help', '要支援'),
        ('unknown', '未確認'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='general')
    # safety_status など、ラズパイ側で使わないフィールドは省略しても良いですが、
    # コピーして同じにしておく方が混乱がありません。
    safety_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')

    # AbstractUserを継承しているので、username, password, emailなどは自動で入ります
    # 中央サーバーで設定した通り、emailのユニーク制約解除やfull_nameの追加を行います
    email = models.EmailField(verbose_name='メールアドレス', blank=True, unique=False)
    full_name = models.CharField(verbose_name='氏名', max_length=150, blank=True)

    # USERNAME_FIELDなどの設定も合わせる
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    # related_name の衝突回避（ラズパイ側でも必要）
    groups = models.ManyToManyField(
        Group,
        verbose_name=('groups'),
        blank=True,
        related_name="field_user_set",  # 名前を変えておく
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=('user permissions'),
        blank=True,
        related_name="field_user_permissions_set",  # 名前を変えておく
        related_query_name="user",
    )

    def __str__(self):
        return self.full_name or self.username


class DistributionItem(models.Model):
    """配布する物資の種類を管理するモデル（例：朝食、水、毛布）"""
    name = models.CharField(verbose_name="物資名", max_length=100, unique=True)
    description = models.TextField(verbose_name="説明", blank=True, null=True)

    def __str__(self):
        return self.name