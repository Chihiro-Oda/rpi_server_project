from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UnsyncedCheckin, UnsyncedFieldReport, UnsyncedUserRegistration


# ユーザー管理画面のカスタマイズ
class FieldUserAdmin(UserAdmin):
    # 一覧画面に表示する項目
    list_display = ('username', 'full_name', 'role', 'is_active', 'is_staff')

    # 編集画面のフィールド構成（標準のUserAdminの設定に、カスタムフィールドを追加）
    fieldsets = UserAdmin.fieldsets + (
        ('現場用カスタム情報', {'fields': ('role', 'safety_status')}),
    )

    # ユーザー作成画面のフィールド構成
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('full_name', 'role', 'email')}),
    )

    search_fields = ('username', 'full_name')
    list_filter = ('role', 'is_staff', 'is_active')


# Userモデルを登録
admin.site.register(User, FieldUserAdmin)

# ついでに、デバッグ用に他の未同期データモデルも登録しておくと便利です
admin.site.register(UnsyncedCheckin)
admin.site.register(UnsyncedFieldReport)
admin.site.register(UnsyncedUserRegistration)