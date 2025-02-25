# 修改报错格式
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import BlacklistedAccessToken
from rest_framework_simplejwt.exceptions import TokenError

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # 获取 Authorization 头
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        # 检查是否存在 Authorization 头
        if not auth_header:
            raise AuthenticationFailed(
                detail="缺少Authorization头",  # 关键修改：添加detail参数
                code='missing_auth_header'
            )

        # 验证头格式
        auth_parts = auth_header.split()
        if len(auth_parts) != 2 or auth_parts[0].lower() != 'bearer':
            raise AuthenticationFailed(
                detail="Authorization头格式应为 Bearer <token>",  # 关键修改
                code='invalid_header'
            )

        access_token = auth_parts[1]

        try:
            # 调用父类验证逻辑
            auth_result = super().authenticate(request)  # 返回 (user, token) 或 None
            if not auth_result:
                raise AuthenticationFailed(
                    detail="无效用户凭证",  # 关键修改
                    code='authentication_failed'
                )

            user, token = auth_result

            # 获取验证后的token
            validated_token = self.get_validated_token(access_token)
            jti = validated_token.get('jti')

            # 检查黑名单
            if BlacklistedAccessToken.objects.filter(jti=jti).exists():
                raise AuthenticationFailed(
                    detail="Token已被拉黑",  # 关键修改
                    code='token_blacklisted'
                )

            # 验证是否为最新jti
            if user.current_access_jti != jti:
                raise AuthenticationFailed(
                    detail="Token已过期",  # 关键修改
                    code='stale_token'
                )

            return (user, token)

        except TokenError as e:
            # 处理JWT验证错误
            raise AuthenticationFailed(
                detail=f"Token无效: {str(e)}",  # 关键修改
                code='token_invalid'
            )
        except Exception as e:
            # 处理其他意外错误
            raise AuthenticationFailed(
                detail=str(e),  # 关键修改
                code='authentication_error'
            )