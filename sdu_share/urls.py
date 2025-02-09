from django.urls import path
from sdu_share.api import auth_views

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/register', auth_views.RegisterView.as_view()),  # 注册相关接口
    path('api/login_passwd', auth_views.LoginPasswdView.as_view()),  # 密码登录接口
    # 邮箱验证码登录
    path('api/login_email', auth_views.LoginEmailView.as_view(), name='login_email'),
    # 登出
    path('api/logout', auth_views.LogoutView.as_view(), name='logout'),
    # 账户注销
    path('api/delete_account', auth_views.DeleteAccountView.as_view(), name='delete_account'),
    # 密码重置
    path('api/reset_password', auth_views.ResetPasswordView.as_view(), name='reset_password'),
]