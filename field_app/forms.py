from django import forms
from .models import UnsyncedFieldReport


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