from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import BlacklistedAccessToken
from rest_framework_simplejwt.exceptions import TokenError

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # 调用父类方法，获取(user, token)元组
        auth_result = super().authenticate(request)  # 返回 (user, token) 或 None
        if not auth_result:
            return None

        user, token = auth_result  # 解包元组

        # 获取Authorization头
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header:
            raise AuthenticationFailed('缺少Authorization头')

        # 验证头格式
        auth_parts = auth_header.split()
        if len(auth_parts) != 2 or auth_parts[0].lower() != 'bearer':
            raise AuthenticationFailed('Authorization头格式应为 Bearer <token>')

        access_token = auth_parts[1]

        # 验证Token有效性
        try:
            validated_token = self.get_validated_token(access_token)
        except TokenError as e:
            raise AuthenticationFailed(f'Token无效: {str(e)}')

        # 提取jti
        jti = validated_token.get('jti')

        # 检查黑名单
        if BlacklistedAccessToken.objects.filter(jti=jti).exists():
            raise AuthenticationFailed('Token已被拉黑')

        # 检查是否为当前有效jti
        if user.current_access_jti != jti:  # 现在user是真正的User对象
            raise AuthenticationFailed('Token已过期')

        return (user, token)  # 必须返回元组