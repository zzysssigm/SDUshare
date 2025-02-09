from django.urls import path
from sdu_share.api import auth_views

urlpatterns = [
    path('register', auth_views.RegisterView.as_view()),  # 注册相关接口
    path('login_passwd', auth_views.LoginPasswdView.as_view()),  # 密码登录接口
]