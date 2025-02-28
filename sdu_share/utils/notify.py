# utils/notify.py
from django.contrib.contenttypes.models import ContentType
from ..models import Notification

class NotificationService:
    @classmethod
    def create_notification(cls, user, n_type, message_template, content_object=None, **extra):
        """
        创建结构化通知
        参数：
        - user: 接收用户
        - n_type: 通知类型
        - message_template: 消息模板（支持格式化）
        - content_object: 关联对象（可选）
        - extra: 模板参数及额外数据
        """
        # 动态生成消息内容
        message = message_template.format(**extra)
        
        # 获取内容类型
        content_type = None
        object_id = None
        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = content_object.id

        # 创建通知对象
        return Notification.objects.create(
            user=user,
            n_type=n_type,
            message=message,
            content_type=content_type,
            object_id=object_id,
            extra_data=extra
        )

# 示例调用场景
"""
# 在帖子回复时触发
NotificationService.create_notification(
    user=post.author,
    n_type='reply_post',
    message_template="{actor} 回复了你的帖子《{title}》",
    content_object=post,
    actor=reply_user.username,
    title=post.post_title
)
"""