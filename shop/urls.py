from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('product/<slug:slug>/', views.product_detail_view, name='product_detail'),

    # Cart URLs
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:product_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),

    # Checkout
    path('checkout/', views.checkout_view, name='checkout'),

    # AI Chat API
    path('api/chat/', views.chat_api, name='chat_api'),
]
