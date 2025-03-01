from django.urls import path
from sdu_share.api import auth_views, blacklist_views, article_views, post_reply_views, course_views ,like_views, user_views, image_views, resource_views, notification_views, message_views, star_views

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
    # 课程评论评分
    path('api/course/rate', course_views.CourseRateView.as_view(), name='course-rate'),
    path('api/course/edit_rating', course_views.CourseEditRatingView.as_view(), name='edit-rating'),
    path('api/course/user_evaluation', course_views.UserEvaluationView.as_view(), name='user-evaluation'),

    path('api/course/detail', course_views.CourseDetailView.as_view(), name='course-detail'),
    path('api/course/list', course_views.CourseListView.as_view(), name='course-list'),

    path('api/course/post_list', course_views.CoursePostListView.as_view(), name='course-post-list'),
    path('api/course/score_list', course_views.CourseScoreListView.as_view(), name='course-score-list'),

    path('api/like', like_views.LikeView.as_view(), name='like'),
    path('api/unlike', like_views.UnlikeView.as_view(), name='unlike'),
    path('api/like/count', like_views.LikeCountView.as_view(), name='like_count'),
    path('api/like/user', like_views.UserLikesView.as_view(), name='user_likes'),

    path('api/user/homepage', user_views.UserProfileView.as_view(), name='user-profile'),
    path('api/user/list', user_views.UserListView.as_view(), name='user-list'),

    path('api/image/profile', image_views.ProfileImageUpload.as_view()),
    path('api/image/user', image_views.UserProfileImage.as_view()),
    path('api/image/article', image_views.ArticleImageUpload.as_view()),
    path('api/image/get/<str:image_name>', image_views.ImageRetrieve.as_view()),

    path('api/resource/upload', resource_views.ResourceUploadView.as_view(), name='resource-upload'),
    path('api/resource/download', resource_views.ResourceDownloadView.as_view(), name='resource-download'),

    path('api/notifications/list', notification_views.NotificationListView.as_view()),
    path('api/notifications/read', notification_views.NotificationReadView.as_view()),

    path('api/messages/send', message_views.SendMessageView.as_view()),
    path('api/messages/list', message_views.MessageListView.as_view()),
    path('api/messages/delete', message_views.RecallMessageView.as_view()),
    path('api/messages/read', message_views.MarkAsReadView.as_view()),

    path('api/star/create', star_views.StarFolderCreateView.as_view()),
    path('api/star', star_views.StarContentView.as_view()),
    path('api/unstar', star_views.UnstarView.as_view()),
#     path('api/star/folder/create', star_views.StarFolderCreateView.as_view()),
    path('api/star/folder/list', star_views.StarFolderListView.as_view()),
    path('api/star/list', star_views.StarListView.as_view()),

    
]