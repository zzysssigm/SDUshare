from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
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
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=['email', 'created_at'])
        ]