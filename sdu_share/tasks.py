# yourapp/tasks.py
from celery import shared_task
from django.db.models import F, Count
from django.utils import timezone
from django.core.cache import cache
from .models import (
    Post, EmailVerificationCode,
    Course, Tag, BlacklistedAccessToken,
    Like,User
)
from django.contrib.contenttypes.models import ContentType
from django.db.models.functions import Coalesce
from django.db.models import Subquery, OuterRef, FloatField

@shared_task
def update_hot_scores():
    """批量更新帖子热度分（每10分钟）"""
    Post.objects.update(
        hot_score=0.3 * F('views') + 0.7 * Coalesce(
            Subquery(
                Like.objects.filter(
                    content_type=ContentType.objects.get_for_model(Post),
                    object_id=OuterRef('pk')
                ).values('object_id').annotate(count=Count('*')).values('count'),
                output_field=FloatField()
            ),
            0.0
        )
    )

@shared_task
def clean_expired_data():
    """每日清理过期数据（凌晨2点执行）"""
    # 清理验证码
    EmailVerificationCode.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()
    
    # 清理黑名单token
    BlacklistedAccessToken.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()

@shared_task
def update_tag_hotness():
    """每小时更新热门标签"""
    hot_tags = Tag.objects.annotate(
        usage_count=Count('articles') + Count('posts') * 0.5
    ).filter(
        usage_count__gte=100
    ).values_list('id', flat=True)
    
    Tag.objects.update(is_hot=False)
    Tag.objects.filter(id__in=hot_tags).update(is_hot=True)

@shared_task
def refresh_course_cache(course_id=None):
    """更新课程缓存"""
    if course_id:
        course = Course.objects.get(pk=course_id)
        cache.set(f'course_{course_id}_avg', course.average_score, 3600)
        cache.set(f'course_{course_id}_reviews', course.total_reviews, 3600)
    else:
        for course in Course.objects.all():
            cache.set(f'course_{course.id}_avg', course.average_score, 3600)
            cache.set(f'course_{course.id}_reviews', course.total_reviews, 3600)