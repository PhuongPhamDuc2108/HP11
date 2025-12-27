from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Order

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer_name', 'phone', 'address', 'payment_method']
        labels = {
            'customer_name': 'Họ và tên',
            'phone': 'Số điện thoại',
            'address': 'Địa chỉ nhận hàng',
            'payment_method': 'Phương thức thanh toán',
        }
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nguyễn Văn A'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09xx xxx xxx'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Số nhà, đường, phường/xã, quận/huyện, tỉnh/thành phố'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
        }
