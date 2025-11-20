from django import forms
from .models import UnsyncedFieldReport, UnsyncedUserRegistration


class FieldReportForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 共通のCSSクラスを定義
        common_input_classes = "mt-1 p-3 w-full border rounded-md bg-gray-600 text-white focus:outline-none focus:ring focus:ring-green-400"

        # 各フィールドのウィジェットにクラス属性を追加
        self.fields['current_evacuees'].widget.attrs.update({'class': common_input_classes})
        self.fields['medical_needs'].widget.attrs.update({'class': common_input_classes})
        self.fields['food_stock'].widget.attrs.update({'class': common_input_classes})

    class Meta:
        model = UnsyncedFieldReport
        fields = ['current_evacuees', 'medical_needs', 'food_stock']
        labels = {
            'current_evacuees': '現在避難者数',
            'medical_needs': '医療・要介護者数',
            'food_stock': '食料の残量',
        }

class UnsyncedUserEditForm(forms.ModelForm):
    class Meta:
        model = UnsyncedUserRegistration
        fields = ['username', 'full_name']
        labels = {
            'username': 'ログインID (修正)',
            'full_name': '氏名',
        }


class FieldSignUpForm(forms.ModelForm):
    password = forms.CharField(
        label="パスワード",
        widget=forms.PasswordInput(attrs={'class': 'w-full p-2 border rounded text-gray-900 bg-white'}),
        help_text="※忘れないようにしてください"
    )
    # 確認用パスワード欄も一応つけておくのが親切
    password_confirm = forms.CharField(
        label="パスワード (確認)",
        widget=forms.PasswordInput(attrs={'class': 'w-full p-2 border rounded text-gray-900 bg-white'}),
    )

    class Meta:
        model = UnsyncedUserRegistration
        fields = ['full_name', 'username', 'password']  # login_id -> username に変更済みの前提
        labels = {
            'full_name': '氏名',
            'username': '希望ログインID',
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'w-full p-2 border rounded text-gray-900 bg-white'}),
            'username': forms.TextInput(attrs={'class': 'w-full p-2 border rounded text-gray-900 bg-white'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "パスワードが一致しません。")

        return cleaned_data

