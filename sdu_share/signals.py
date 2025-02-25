# yourapp/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from .models import (
    User, Article, Post, Reply, 
    Like, Course, CourseReview
)
from django.db import models

# 通用信号处理器
def update_counter(sender, instance, created=False, **kwargs):
    """通用计数更新器"""
    if hasattr(instance, 'update_related_counters'):
        instance.update_related_counters(created=created)

# 用户相关内容计数
@receiver([post_save, post_delete], sender=Article)
@receiver([post_save, post_delete], sender=Post)
@receiver([post_save, post_delete], sender=Reply)
def handle_content_counts(sender, instance, **kwargs):
    """统一处理内容计数更新"""
    action = 'increment' if kwargs.get('created', False) else 'decrement'
    
    # 原子操作更新用户统计
    with transaction.atomic():
        if sender == Article:
            User.objects.filter(pk=instance.author_id).update(
                all_articles=models.F('all_articles') + (1 if action == 'increment' else -1)
            )
        elif sender == Post:
            User.objects.filter(pk=instance.poster_id).update(
                all_posts=models.F('all_posts') + (1 if action == 'increment' else -1)
            )
        elif sender == Reply:
            User.objects.filter(pk=instance.replier_id).update(
                all_replys=models.F('all_replys') + (1 if action == 'increment' else -1)
            )

# 点赞相关信号
@receiver([post_save, post_delete], sender=Like)
def handle_like_cache(sender, instance, **kwargs):
    """点赞变化时更新缓存"""
    ct = ContentType.objects.get_for_model(instance.content_object)
    cache_key = f'like_count:{ct.id}:{instance.object_id}'
    cache.delete(cache_key)
    
    # 更新用户总点赞数
    if kwargs.get('created', False) or kwargs.get('signal') == post_delete:
        delta = 1 if kwargs.get('created') else -1
        User.objects.filter(pk=instance.user_id).update(
            all_likes=models.F('all_likes') + delta
        )

# 课程评分更新信号
@receiver(post_save, sender=CourseReview)
def update_course_score(sender, instance, **kwargs):
    """课程评分更新时清除缓存"""
    cache.delete(f'course_{instance.course_id}_avg')
    cache.delete(f'course_{instance.course_id}_reviews')

# 连接所有信号（防止重复注册）
def connect_signals():
    post_save.connect(handle_content_counts, sender=Article)
    post_delete.connect(handle_content_counts, sender=Article)
    post_save.connect(handle_content_counts, sender=Post)
    post_delete.connect(handle_content_counts, sender=Post)
    post_save.connect(handle_content_counts, sender=Reply)
    post_delete.connect(handle_content_counts, sender=Reply)
    post_save.connect(handle_like_cache, sender=Like)
    post_delete.connect(handle_like_cache, sender=Like)
    post_save.connect(update_course_score, sender=CourseReview)