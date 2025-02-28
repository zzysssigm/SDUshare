from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from mptt.models import MPTTModel, TreeForeignKey
from django.core.cache import cache
from django.db.models import F
from django.core.validators import FileExtensionValidator
import uuid


class BlacklistedAccessToken(models.Model):
    jti = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()

    @classmethod
    def clean_expired(cls):
        cls.objects.filter(expires_at__lt=timezone.now()).delete()

class User(AbstractUser):
    current_access_jti = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(unique=True)
    email_code = models.IntegerField(null=True, blank=True)
    reputation = models.IntegerField(default=100)
    all_likes = models.IntegerField(default=0)
    all_views = models.IntegerField(default=0)
    all_articles = models.IntegerField(default=0)
    all_posts = models.IntegerField(default=0)
    all_replys = models.IntegerField(default=0)
    influence = models.IntegerField(default=0)
    master = models.BooleanField(default=False)
    super_master = models.BooleanField(default=False)
    block = models.BooleanField(default=False)
    block_end_time = models.DateTimeField(null=True, blank=True)
    profile_url = models.CharField(max_length=255, null=True, blank=True)
    campus = models.CharField(max_length=255, null=True, blank=True)
    college = models.CharField(max_length=255, null=True, blank=True)
    major = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.username

class EmailVerificationCode(models.Model):
    PURPOSE_CHOICES = [
        ('register', '注册'),
        ('login', '登录'),
        ('delete', '注销'),
        ('reset', '重置密码')
    ]
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    class Meta:
        indexes = [
            # 复合索引优化验证码查询
            models.Index(fields=['email', 'purpose'], name='email_purpose_idx'),
            # 过期时间索引
            models.Index(fields=['expires_at'], name='expiry_idx')
        ]

class BlockList(models.Model):
    from_user = models.ForeignKey(User, related_name='blocking', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='blocked', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='likes',
        db_index=True,  # 新增索引优化用户查询
        verbose_name="点赞用户"
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="内容类型"
    )
    object_id = models.PositiveIntegerField(verbose_name="内容ID")
    content_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")  # 新增字段

    class Meta:
        verbose_name = "点赞"
        verbose_name_plural = "点赞"
        unique_together = ('user', 'content_type', 'object_id')  # 唯一约束防重复
        indexes = [
            # 联合索引优化内容查询
            models.Index(fields=['content_type', 'object_id']),
            # 时间索引优化按时间筛选
            models.Index(fields=['-created_at']),
        ]
        ordering = ['-created_at']  # 默认时间倒序

    def __str__(self):
        return f"{self.user} 点赞了 {self.content_object}"


class Article(models.Model):
    ARTICLE_TYPE_CHOICES = [
        ('original', '原创'),
        ('repost', '转载'),
    ]

    id = models.AutoField(primary_key=True)
    article_title = models.CharField(max_length=255, verbose_name="文章标题")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles', verbose_name="作者")
    content = models.TextField(verbose_name="内容")
    tags = models.ManyToManyField('Tag', related_name='articles', verbose_name="标签")
    stars = models.PositiveIntegerField(default=0, verbose_name="收藏数")
    likes = GenericRelation(Like, verbose_name="点赞")
    views = models.PositiveIntegerField(default=0, verbose_name="浏览量")
    block = models.BooleanField(default=False, db_index=True, verbose_name="是否屏蔽")
    publish_time = models.DateTimeField(auto_now_add=True, verbose_name="发布时间")
    origin_link = models.CharField(max_length=255, blank=True, null=True, verbose_name="原文链接")
    resource_link = models.CharField(max_length=255, blank=True, null=True, verbose_name="资源URL")
    article_summary = models.CharField(max_length=255, blank=True, null=True, default="这个人没有写简介...", verbose_name="文章简介")
    cover_link = models.CharField(max_length=255, blank=True, null=True, default="后续改成默认封面？或者检查到空就不加载", verbose_name="封面URL")
    article_type = models.CharField(
        max_length=10,
        choices=ARTICLE_TYPE_CHOICES,
        default='original',
        verbose_name="文章类型"
    )

    def __str__(self):
        return self.article_title

    class Meta:
        verbose_name = "文章"
        verbose_name_plural = "文章"
        indexes = [
            models.Index(fields=['-publish_time']),  # 显式定义索引
        ]
        ordering = ['-publish_time']

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="标签名")  # 添加索引
    
    def __str__(self):
        return self.name
    

class Course(models.Model):
    COURSE_TYPE_CHOICES = [
        ('compulsory', '必修课'),
        ('elective', '选修课'),
        ('restricted_elective', '限选课'),
    ]

    COURSE_METHOD_CHOICES = [
        ('online', '线上'),
        ('offline', '线下'),
        ('hybrid', '混合'),
    ]

    id = models.AutoField(primary_key=True)
    course_name = models.CharField(max_length=255, verbose_name="课程名称", db_index=True)
    course_type = models.CharField(
        max_length=50,
        choices=COURSE_TYPE_CHOICES,
        verbose_name="课程类型",
        db_index=True
    )
    college = models.CharField(max_length=255, verbose_name="开设学院")
    credits = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        verbose_name="学分",
        help_text="例如：3.50 学分"
    )
    course_teacher = models.CharField(max_length=255, verbose_name="授课教师")
    course_method = models.CharField(
        max_length=50,
        choices=COURSE_METHOD_CHOICES,
        verbose_name="教学方式",
        db_index=True
    )
    assessment_method = models.TextField(verbose_name="考核方式")  # 改为TextField支持长文本
    likes = GenericRelation('Like', verbose_name="点赞")
    relative_articles = models.ManyToManyField(
        'Article',
        related_name='courses',
        verbose_name="关联文章",
        blank=True
    )
    publish_time = models.DateTimeField(auto_now_add=True, verbose_name="发布时间")

    class Meta:
        verbose_name = "课程"
        verbose_name_plural = "课程"
        ordering = ['-publish_time']
        indexes = [
            models.Index(fields=['course_name', 'college']),  # 复合索引优化常用查询
        ]

    def __str__(self):
        return f"{self.course_name}（{self.college}）"

    @property
    def average_score(self):
        """实时计算平均分（可缓存优化）"""
        from django.db.models import Avg
        return self.reviews.aggregate(avg=Avg('score'))['avg'] or 0.0

    @property
    def total_reviews(self):
        """总评价人数（可缓存优化）"""
        return self.reviews.count()

# 课程评分与评论
class CourseReview(models.Model):
    SCORE_CHOICES = [(i, str(i)) for i in range(1, 6)]  # 1-5分制

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        verbose_name="用户",
        related_name='course_reviews'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name="课程"
    )
    score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        verbose_name="评分",
        choices=SCORE_CHOICES
    )
    comment = models.TextField(verbose_name="评论", blank=True, null=True)
    publish_time = models.DateTimeField(auto_now_add=True, verbose_name="发布时间")

    class Meta:
        verbose_name = "课程评价"
        verbose_name_plural = "课程评价"
        unique_together = ('user', 'course')  # 确保用户对每门课程只评价一次
        ordering = ['-publish_time']
        indexes = [
            models.Index(fields=['course', '-publish_time']),  # 按课程和时间查询优化
        ]

    def __str__(self):
        return f"{self.user.username} 对《{self.course.course_name}》的评分：{self.score}"

    def save(self, *args, **kwargs):
        """保存时自动校验评分范围"""
        if not 1 <= float(self.score) <= 5:
            raise ValueError("评分必须在1~5分之间")
        super().save(*args, **kwargs)    


class Post(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="帖子ID")
    post_title = models.CharField(
        max_length=255,
        verbose_name="帖子标题",
        help_text="标题最多255个字符",
        db_index=True  # 添加标题索引
    )
    poster = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name="发帖人",
        db_index=True  # 外键索引
    )
    content = models.TextField(
        verbose_name="内容",
        help_text="支持Markdown格式"
    )
    views = models.PositiveIntegerField(
        default=0,
        verbose_name="浏览量",
        help_text="通过原子操作更新"
    )
    likes = GenericRelation(
        'Like',
        verbose_name="点赞",
        related_query_name='post'  # 优化反向查询
    )
    block = models.BooleanField(
        default=False,
        verbose_name="是否屏蔽",
        db_index=True  # 高频过滤字段索引
    )
    top = models.BooleanField(
        default=False,
        verbose_name="是否置顶",
        db_index=True  # 高频排序字段索引
    )
    publish_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="发布时间",
        db_index=True  # 时间索引
    )
    article = models.ForeignKey(
        'Article',
        on_delete=models.SET_NULL,  # 文章删除后保留帖子
        related_name='posts',
        null=True,
        blank=True,
        verbose_name="关联文章",
        db_index=True
    )
    course = models.ForeignKey(
        'Course',
        on_delete=models.SET_NULL,  # 课程删除后保留帖子
        related_name='posts',
        null=True,
        blank=True,
        verbose_name="关联课程",
        db_index=True
    )
    hot_score = models.FloatField(
        default=0.0,
        verbose_name="热度分",
        db_index=True,
        help_text="计算公式：浏览量×0.3 + 点赞数×0.7",
        editable=False  # 防止人工修改
    )

    class Meta:
        verbose_name = "帖子"
        verbose_name_plural = "帖子"
        ordering = ['-publish_time']  # 默认时间倒序
        indexes = [
            # 置顶+时间联合索引
            models.Index(fields=['top', '-publish_time']),
            # 作者+时间联合索引
            models.Index(fields=['poster', '-publish_time']),
            models.Index(fields=['article', '-publish_time']),
            models.Index(fields=['course', '-publish_time']),
            # 优化排序查询
            models.Index(fields=['-views']),
            models.Index(fields=['-hot_score']),
            models.Index(fields=['-publish_time', 'block']),
            # 热度分排序索引
            models.Index(fields=['-hot_score', '-publish_time']),
            # 联合查询优化
            models.Index(fields=['block', '-hot_score']),
        ]
        get_latest_by = 'publish_time'

    def __str__(self):
        return f"{self.post_title[:20]}（{self.poster.username}@{self.publish_time:%Y-%m-%d}）"

    def save(self, *args, **kwargs):
        """保存前校验必填字段"""
        if not self.post_title.strip():
            raise ValueError("帖子标题不能为空")
        if len(self.content.strip()) < 10:
            raise ValueError("内容至少需要10个有效字符")
        super().save(*args, **kwargs)

    @property
    def reply_count(self):
        """实时统计回复数（可缓存优化）"""
        return self.replies.count()

    # @property
    # def hot_score(self):
    #     """热度分计算：浏览量*0.3 + 点赞数*0.7"""
    #     return self.views * 0.3 + self.likes.count() * 0.7
    
    def update_hot_scores():
        Post.objects.update(
            hot_score=0.3 * F('views') + 0.7 * F('like_count')
        )

    def increment_views(self):
        """原子操作更新浏览量"""
        Post.objects.filter(id=self.id).update(views=models.F('views') + 1)

class Reply(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="回复ID")
    reply_content = models.TextField(verbose_name="回复内容", help_text="回复内容最多支持5000字符")
    reply_time = models.DateTimeField(auto_now_add=True, verbose_name="回复时间", db_index=True)
    
    post = models.ForeignKey(
        'Post',
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name="关联帖子",
        db_index=True
    )
    
    replier = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name="回复用户",
        db_index=True
    )
    
    parent_reply = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="父级回复",
        db_index=True
    )
    
    likes = GenericRelation(
        'Like',
        verbose_name="点赞",
        help_text="通过GenericForeignKey实现的通用点赞关系"
    )

    class Meta:
        verbose_name = "帖子回复"
        verbose_name_plural = "帖子回复"
        ordering = ['-reply_time']
        indexes = [
            models.Index(fields=['post', 'parent_reply', '-reply_time']),
            models.Index(fields=['replier', '-reply_time']),
        ]

    def __str__(self):
        return f"{self.replier.username} → {self.post.post_title[:20]}（{self.reply_time:%Y-%m-%d}）"

    def save(self, *args, **kwargs):
        if len(self.reply_content.strip()) < 5:
            raise ValueError("回复内容至少需要5个有效字符")
        super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        """保存前自动校验内容长度"""
        if len(self.reply_content.strip()) < 5:
            raise ValueError("回复内容至少需要5个有效字符")
        super().save(*args, **kwargs)

class StarFolder(MPTTModel):
    """支持多级嵌套的收藏夹"""
    name = models.CharField(max_length=100, verbose_name="收藏夹名称")
    user = models.ForeignKey(
        'User', 
        on_delete=models.CASCADE,
        related_name='star_folders',
        verbose_name="所属用户"
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="父级收藏夹"
    )
    is_default = models.BooleanField(default=False, verbose_name="默认收藏夹")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    cover = models.URLField(null=True, blank=True, verbose_name="封面图URL")
    description = models.TextField(null=True, blank=True, verbose_name="描述")

    class MPTTMeta:
        order_insertion_by = ['name']
    
    class Meta:
        verbose_name = "收藏夹"
        verbose_name_plural = "收藏夹"
        unique_together = ('user', 'name')  # 同一用户下收藏夹名称唯一
        indexes = [
            models.Index(fields=['user', 'is_default']),
        ]

    def __str__(self):
        return f"{self.user.username}的收藏夹：{self.name}"

class Star(models.Model):
    """支持多级收藏夹的泛型收藏模型"""
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='stars',
        verbose_name="用户",
        db_index=True
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="内容类型"
    )
    object_id = models.PositiveIntegerField(verbose_name="对象ID")
    content_object = GenericForeignKey('content_type', 'object_id')
    
    folder = models.ForeignKey(
        StarFolder,
        on_delete=models.CASCADE,
        related_name='stars',
        verbose_name="所属收藏夹"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="收藏时间")
    notes = models.TextField(null=True, blank=True, verbose_name="收藏备注")

    class Meta:
        verbose_name = "收藏记录"
        verbose_name_plural = "收藏记录"
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['-created_at']),
        ]
        constraints = [
            # 同一用户不能在同一个收藏夹重复收藏相同内容
            models.UniqueConstraint(
                fields=['user', 'content_type', 'object_id', 'folder'],
                name='unique_star_per_folder'
            ),
        ]

    def __str__(self):
        return f"{self.user.username}收藏的{self.content_object}"

    def save(self, *args, **kwargs):
        # 自动关联默认收藏夹
        if not self.folder_id:
            default_folder = StarFolder.objects.get_or_create(
                user=self.user,
                is_default=True,
                defaults={'name': '默认收藏'}
            )[0]
            self.folder = default_folder
        super().save(*args, **kwargs)

    @classmethod
    def get_star_count(cls, obj):
        """获取对象的收藏计数（带缓存）"""
        ct = ContentType.objects.get_for_model(obj)
        cache_key = f'star_count:{ct.id}:{obj.id}'
        count = cache.get(cache_key)
        if count is None:
            count = cls.objects.filter(content_type=ct, object_id=obj.id).count()
            cache.set(cache_key, count, timeout=300)
        return count
    
def image_upload_path(instance, filename):
    return f"images/{uuid.uuid4().hex[:8]}/{filename}"

class Image(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        upload_to=image_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
        verbose_name='图片文件'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    file_size = models.PositiveIntegerField(editable=False)
    content_type = models.CharField(max_length=50, editable=False)
    is_profile_image = models.BooleanField(default=False)  # 新增字段标识头像图片

    @property
    def image_name(self):
        return self.image.name.split('/')[-1]
    
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('reply_post', '回复帖子'),
        ('reply_article', '回复文章'),
        ('reply_reply', '回复评论'),
        ('like', '点赞'),
        ('system', '系统通知'),
        ('message', '私信'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True  # 添加索引
    )
    n_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        verbose_name="通知类型",
        db_index=True
    )
    message = models.TextField(verbose_name="通知内容")
    is_read = models.BooleanField(default=False, verbose_name="已读状态", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_index=True)
    
    # 通用外键关联目标内容
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # 额外信息存储
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # 复合索引优化常见查询
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'n_type']),
        ]
        verbose_name = "通知"
        verbose_name_plural = "通知"

    def __str__(self):
        return f"[{self.get_n_type_display()}] {self.message[:30]}"
    

class Message(models.Model):
    sender = models.ForeignKey(
        User, 
        related_name='sent_messages', 
        on_delete=models.CASCADE,
        db_index=True  # 添加索引
    )
    receiver = models.ForeignKey(
        User, 
        related_name='received_messages', 
        on_delete=models.CASCADE,
        db_index=True  # 添加索引
    )
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)  # 时间索引
    read = models.BooleanField(default=False)
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_receiver = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['-sent_at'], name='msg_chronological_idx')  # 复合索引
        ]
        ordering = ['-sent_at']

    def __str__(self):
        return f"From {self.sender} to {self.receiver}: {self.content[:20]}"