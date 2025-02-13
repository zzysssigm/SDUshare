from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import uuid
from django.utils import timezone
from .models import BlacklistedAccessToken
from datetime import timedelta

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # 生成新的jti并记录旧值
        old_jti = user.current_access_jti
        new_jti = uuid.uuid4().hex
        token.access_token['jti'] = new_jti
        
        # 将旧jti加入黑名单
        if old_jti:
            BlacklistedAccessToken.objects.create(
                jti=old_jti,
                expires_at=timezone.now() + timedelta(hours=1)  # 与ACCESS_TOKEN_LIFETIME一致
            )
        
        # 更新用户当前jti
        user.current_access_jti = new_jti
        user.save()
        
        return token