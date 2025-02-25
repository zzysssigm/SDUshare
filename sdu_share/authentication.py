# authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import BlacklistedAccessToken
from rest_framework_simplejwt.exceptions import TokenError

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # 获取 Authorization 头
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        # 关键修改：无Authorization头时静默返回None
        if not auth_header:
            return None  # 不再抛出异常

        # 验证头格式
        auth_parts = auth_header.split()
        if len(auth_parts) != 2 or auth_parts[0].lower() != 'bearer':
            raise AuthenticationFailed(
                detail="Authorization头格式应为 Bearer <token>",
                code='invalid_header'
            )

        access_token = auth_parts[1]

        try:
            # 调用父类验证逻辑
            auth_result = super().authenticate(request)
            if not auth_result:
                return None  # Token验证失败时不强制阻断

            user, token = auth_result

            # 获取验证后的token
            validated_token = self.get_validated_token(access_token)
            jti = validated_token.get('jti')

            # 检查黑名单
            if BlacklistedAccessToken.objects.filter(jti=jti).exists():
                raise AuthenticationFailed(
                    detail="Token已被拉黑",
                    code='token_blacklisted'
                )

            # 验证是否为最新jti
            if user.current_access_jti != jti:
                raise AuthenticationFailed(
                    detail="Token已过期",
                    code='stale_token'
                )

            return (user, token)

        except TokenError as e:
            raise AuthenticationFailed(
                detail=f"Token无效: {str(e)}",
                code='token_invalid'
            )
        except Exception as e:
            raise AuthenticationFailed(
                detail=str(e),
                code='authentication_error'
            )