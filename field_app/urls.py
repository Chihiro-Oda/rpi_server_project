# field_app/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'field_app'

urlpatterns = [
    # --- ホーム画面 ---
    path('', views.home_view, name='home'),

    # --- 認証関連 ---
    path('login/', auth_views.LoginView.as_view(
        template_name='field_app/login.html'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # --- 機能ページ ---
    path('checkin/', views.shelter_checkin_view, name='shelter_checkin'),

    path('food/', views.food_distribution_view, name='food_distribution'),

    path('report/', views.field_report_view, name='field_report'),

    path('chat/', views.field_chat_view, name='field_chat'),

    path('manual-sync/', views.manual_sync_view, name='manual_sync'),

    path('unsynced-users/', views.unsynced_users_list_view, name='unsynced_users_list'),
    path('unsynced-users/<int:pk>/edit/', views.unsynced_user_edit_view, name='unsynced_user_edit'),

    path('signup/', views.field_signup_view, name='signup'),

]