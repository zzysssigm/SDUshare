from django.urls import path
from sdu_share.api import auth_views, blacklist_views, article_views

from .views import CustomTokenRefreshView

urlpatterns = [
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
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
    # 黑名单相关
    path('api/block', blacklist_views.BlockUserView.as_view(), name='block-user'),
    path('api/unblock', blacklist_views.UnblockUserView.as_view(), name='unblock-user'),
    path('api/blocklist', blacklist_views.BlockListView.as_view(), name='block-list'),
    # 文章相关
    path('api/article/create', article_views.ArticleCreateView.as_view()),
    path('api/article/edit', article_views.ArticleEditView.as_view()),
    path('api/article/delete', article_views.ArticleDeleteView.as_view()),
    path('api/article/detail', article_views.ArticleDetailView.as_view()),
    path('api/article/post_list', article_views.ArticlePostListView.as_view()),
    path('api/article/list', article_views.ArticleListView.as_view()),
]