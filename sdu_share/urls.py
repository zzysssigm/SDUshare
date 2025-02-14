from django.urls import path
from sdu_share.api import auth_views, blacklist_views, article_views, post_reply_views, course_views

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
    # 帖子相关
    path('api/post/article_post', post_reply_views.ArticlePostCreateView.as_view()),
    path('api/post/course_post', post_reply_views.CoursePostCreateView.as_view()),
    path('api/post/detail', post_reply_views.PostDetailView.as_view()),
    path('api/post/reply_list', post_reply_views.PostReplyListView.as_view(), name='post-reply-list'),
    
    # (5) 删除帖子
    path('api/post/delete', post_reply_views.PostDeleteView.as_view(), name='post-delete'),
    
    # (6) 创建回复
    path('api/reply/create', post_reply_views.ReplyCreateView.as_view(), name='reply-create'),
    path('api/reply/delete', post_reply_views.ReplyDeleteView.as_view(), name='reply-delete'),
    
    # (8) 获取回复详情
    path('api/reply/detail', post_reply_views.ReplyDetailView.as_view(), name='reply-detail'),
    # 课程相关
    path('api/course/create', 
         course_views.CourseCreateView.as_view(), 
         name='course-create'),
    path('api/course/edit', 
         course_views.CourseEditView.as_view(), 
         name='course-edit'),
    path('api/course/delete', 
         course_views.CourseDeleteView.as_view(), 
         name='course-delete'),

]