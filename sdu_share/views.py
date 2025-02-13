from django.shortcuts import render

from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from datetime import timedelta
from .models import BlacklistedAccessToken,User
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        new_access = response.data.get('access')
        
        if new_access:
            try:
                access_token = AccessToken(new_access)
                user_id = access_token['user_id']
                user = User.objects.get(id=user_id)
                old_jti = user.current_access_jti
                new_jti = access_token['jti']
                
                if old_jti:
                    # 使用get_or_create避免重复插入
                    BlacklistedAccessToken.objects.get_or_create(
                        jti=old_jti,
                        defaults={'expires_at': timezone.now() + timezone.timedelta(hours=1)}
                    )
                
                user.current_access_jti = new_jti
                user.save()
            except Exception as e:
                # 记录错误但允许刷新流程继续
                logger.error(f"刷新Token时更新jti失败: {str(e)}")
        
        return response
