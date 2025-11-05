# field_app/models.py
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
    # ユーザーのプライマリーキー(id)ではなく、QRコードから読み取ったlogin_idをそのまま保存
    login_id = models.CharField(
        verbose_name="避難者のログインID",
        max_length=150
    )

    # 2. どの避難所で (Where)
    # このラズパイが設置されている避難所のID (config.pyなどで管理)
    shelter_id = models.IntegerField(
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
        return f"[{sync_status}] {self.timestamp.strftime('%Y-%m-%d %H:%M')} - {self.login_id} ({self.get_checkin_type_display()})"

    class Meta:
        verbose_name = "未同期チェックイン記録"
        verbose_name_plural = "未同期チェックイン記録"
        ordering = ['-timestamp']  # 新しい記録から順に表示