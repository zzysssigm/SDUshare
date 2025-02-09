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
]