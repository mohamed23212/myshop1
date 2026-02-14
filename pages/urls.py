from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('shop/', views.shop_page, name='shop'),
    path('about/', views.about_page, name='about'),
    
    #path('signup/', SignUpView.as_view(), name='signup'),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_page, name='cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('place-order/', views.place_order, name='place_order'),

    path('account/', views.account_page, name='account'),
    #path('profile/edit/', views.profile_edit_page, name='profile_edit'),
    
    path('myorder/', views.myorder_page, name='myorder'),
    path('cancel-order/<int:group_id>/', views.cancel_order, name='cancel_order'),
    path('edit-order-delivery/<int:order_id>/', views.edit_order_delivery, name='edit_order_delivery'),

    path("admin-statistics/", views.statistics_view, name="admin_statistics"),
    path("admin_orders/", views.admin_orders_view, name="admin_orders"),
    path('admin/orders/details/<int:order_id>/', views.order_detail_view, name='admin_order_detail'), 
    path('admin/order/<int:group_id>/status/<str:new_status>/', views.admin_change_order_status, name='admin_change_order_status'),
    path('terms-and-conditions/', views.terms_view, name='terms'),
]