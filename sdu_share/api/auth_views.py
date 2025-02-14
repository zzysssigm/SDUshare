# sdu_share/api/auth_views.py
from django.contrib.auth import authenticate, login
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from django.contrib.auth import logout
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from ..models import BlacklistedAccessToken
from ..authentication import CustomJWTAuthentication
from datetime import datetime

from ..models import User, EmailVerificationCode
from ..utils.email_utils import (
    generate_code,
    is_valid_sdu_email,
    send_code_email,
    CODE_EXPIRE_TIME,
    SEND_INTERVAL
)

# TODO: 有个地方注意一下，再次登录其他账户的时候需要自动调用logout，如果没登出不能登录其他账户


class RegisterView(APIView):
    def get(self, request):
        """发送验证码接口"""
        email = request.GET.get('email')
        send_code = request.GET.get('send_code')

        # 参数校验
        if send_code != '1' or not email:
            return Response(
                {'status': 400, 'message': '参数错误'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 邮箱格式验证
        if not is_valid_sdu_email(email):
            return Response(
                {'status': 430, 'message': '非山大邮箱格式'},
                status=430  # 自定义状态码
            )

        # 发送频率限制检查
        latest_sent = EmailVerificationCode.objects.filter(
            email=email,
            created_at__gte=timezone.now() - timezone.timedelta(seconds=SEND_INTERVAL)
        ).first()
        
        if latest_sent:
            remaining = (latest_sent.created_at + timezone.timedelta(seconds=SEND_INTERVAL) 
                          - timezone.now()).seconds
            return Response(
                {'status': 429, 'message': f'操作过于频繁，请{remaining}秒后再试'},
                status=429
            )

        # 生成并存储验证码
        code = generate_code()
        expires_at = timezone.now() + timezone.timedelta(seconds=CODE_EXPIRE_TIME)
        
        EmailVerificationCode.objects.create(
            email=email,
            code=code,
            expires_at=expires_at
        )

        # 发送验证码邮件
        if not send_code_email(email, code, "注册"):
            return Response(
                {'status': 500, 'message': '邮件发送失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {'status': 200, 'message': '验证码已发送'},
            status=status.HTTP_200_OK
        )

    def post(self, request):
        """注册接口"""
        data = request.data
        required_fields = ['user_name', 'pass_word', 'email', 'email_code']
        
        # 校验必要参数
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return Response(
                {'status': 400, 'message': f'缺少必要参数: {", ".join(missing_fields)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = data['email']
        code = data['email_code']

        # 邮箱格式二次验证
        if not is_valid_sdu_email(email):
            return Response(
                {'status': 430, 'message': '非山大邮箱格式'},
                status=430
            )

        # 验证码有效性检查
        verification_code = EmailVerificationCode.objects.filter(
            email=email
        ).order_by('-created_at').first()
        
        if not verification_code:
            return Response(
                {'status': 404, 'message': '请先获取验证码'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        if verification_code.code != code:
            return Response(
                {'status': 401, 'message': '验证码错误'},
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        if verification_code.expires_at < timezone.now():
            return Response(
                {'status': 410, 'message': '验证码已过期'},
                status=status.HTTP_410_GONE
            )

        # 唯一性检查
        if User.objects.filter(username=data['user_name']).exists():
            return Response(
                {'status': 409, 'message': '用户名已被注册'},
                status=status.HTTP_409_CONFLICT
            )
            
        if User.objects.filter(email=email).exists():
            return Response(
                {'status': 409, 'message': '邮箱已被注册'},
                status=status.HTTP_409_CONFLICT
            )

        # 创建用户
        try:
            User.objects.create_user(
                username=data['user_name'],
                password=data['pass_word'],
                email=email,
                campus=data.get('campus'),
                college=data.get('college'),
                major=data.get('major')
            )
        except Exception as e:
            return Response(
                {'status': 500, 'message': '用户创建失败: ' + str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 清除已使用的验证码
        verification_code.delete()
        
        return Response(
            {'status': 200, 'message': '注册成功'},
            status=status.HTTP_200_OK
        )


class LoginPasswdView(APIView):
    # 允许未认证访问
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """安全增强版密码登录接口"""
        username = request.data.get('user_name')
        password = request.data.get('pass_word')

        # 参数校验
        if not username or not password:
            return Response(
                {'status': 400, 'message': '缺少用户名或密码'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 登录频率限制
        cache_key = f'login_fails:{username}'
        fail_count = cache.get(cache_key, 0)
        if fail_count >= 5:
            return Response(
                {'status': 429, 'message': '尝试次数过多，请稍后再试'},
                status=429
            )

        # 用户认证
        user = authenticate(username=username, password=password)
        if not user:
            cache.set(cache_key, fail_count + 1, timeout=300)
            return Response(
                {'status': 401, 'message': '用户名或密码错误'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 清除失败计数
        cache.delete(cache_key)

        # 封禁状态检查
        if user.block:
            if user.block_end_time and user.block_end_time > timezone.now():
                return Response(
                    {'status': 423, 'message': '账号封禁中'},
                    status=423
                )
            else:
                # 自动解封
                user.block = False
                user.block_end_time = None
                user.save()

        # 生成JWT令牌
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return Response({
            'status': 200,
            'message': '登录成功',
            'user_id': user.id,
            'user_name': user.username,
            'email': user.email,
            'access': access_token,
            'refresh': str(refresh)
        }, status=status.HTTP_200_OK)


# class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
#     @classmethod
#     def get_token(cls, user):
#         token = super().get_token(user)
#         # 添加自定义声明
#         token['username'] = user.username
#         token['is_admin'] = user.is_superuser
#         return token

#     def validate(self, attrs):
#         data = super().validate(attrs)
#         # 添加自定义响应字段
#         data.update({
#             'user_id': self.user.id,
#             'username': self.user.username,
#             'email': self.user.email
#         })
#         return data

# class CustomTokenObtainPairView(TokenObtainPairView):
#     serializer_class = CustomTokenObtainPairSerializer


class LoginEmailView(APIView):
    authentication_classes = []  # 允许未认证访问
    permission_classes = []       # 无需权限

    def get(self, request):
        """发送登录验证码"""
        email = request.GET.get('email')
        send_code = request.GET.get('send_code')

        # 参数校验
        if send_code != '1' or not email:
            return Response(
                {'status': 400, 'message': '参数错误'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 邮箱格式验证
        if not is_valid_sdu_email(email):
            return Response(
                {'status': 430, 'message': '非山大邮箱格式'},
                status=430
            )

        # 用户存在性检查
        if not User.objects.filter(email=email).exists():
            return Response(
                {'status': 404, 'message': '邮箱未注册'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 发送频率限制
        latest_sent = EmailVerificationCode.objects.filter(
            email=email,
            purpose='login',
            created_at__gte=timezone.now() - timezone.timedelta(seconds=SEND_INTERVAL)
        ).first()

        if latest_sent:
            remaining = (latest_sent.created_at + timezone.timedelta(seconds=SEND_INTERVAL) 
                          - timezone.now()).seconds
            return Response(
                {'status': 429, 'message': f'操作过于频繁，请{remaining}秒后再试'},
                status=429
            )

        # 生成验证码
        code = generate_code()
        expires_at = timezone.now() + timezone.timedelta(seconds=CODE_EXPIRE_TIME)
        
        EmailVerificationCode.objects.create(
            email=email,
            code=code,
            expires_at=expires_at,
            purpose='login'
        )

        # 发送邮件
        if not send_code_email(email, code, "登录"):
            return Response(
                {'status': 500, 'message': '邮件发送失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {'status': 200, 'message': '验证码已发送'},
            status=status.HTTP_200_OK
        )

    def post(self, request):
        """JWT邮箱验证码登录"""
        data = request.data
        email = data.get('email')
        code = data.get('email_code')

        # 参数校验
        if not all([email, code]):
            return Response(
                {'status': 400, 'message': '缺少必要参数'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证码有效性检查
        verification_code = EmailVerificationCode.objects.filter(
            email=email,
            purpose='login'
        ).order_by('-created_at').first()

        if not verification_code:
            return Response(
                {'status': 404, 'message': '请先获取验证码'},
                status=status.HTTP_404_NOT_FOUND
            )

        if verification_code.code != code:
            return Response(
                {'status': 401, 'message': '验证码错误'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if verification_code.expires_at < timezone.now():
            return Response(
                {'status': 410, 'message': '验证码已过期'},
                status=status.HTTP_410_GONE
            )

        # 获取用户
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'status': 401, 'message': '用户不存在'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 封禁状态检查
        if user.block:
            if user.block_end_time and user.block_end_time > timezone.now():
                return Response(
                    {'status': 423, 'message': '账号封禁中'},
                    status=423
                )
            else:
                # 自动解封
                user.block = False
                user.block_end_time = None
                user.save()

        # 生成JWT令牌
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        # # 添加安全声明
        # access_token['uid'] = user.id.hex  # 使用UUID的hex格式
        # access_token['tv'] = user.token_version  # 令牌版本
        # access_token['pt'] = int(timezone.now().timestamp())  # 颁发时间戳

        # 删除已使用的验证码
        verification_code.delete()

        return Response({
            'status': 200,
            'message': '登录成功',
            'user_id': user.id,
            'user_name': user.username,
            'email': user.email,
            'access': str(access_token),
            'refresh': str(refresh)
        }, status=status.HTTP_200_OK)
    

class LogoutView(APIView):
    authentication_classes = [CustomJWTAuthentication]  # 使用自定义认证类
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """JWT登出接口，拉黑refresh和access token"""
        try:
            # 拉黑refresh token
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            # 拉黑当前access token
            auth_header = request.META.get('HTTP_AUTHORIZATION', '').split()
            if len(auth_header) == 2 and auth_header[0].lower() == 'bearer':
                access_token_str = auth_header[1]
                access_token = AccessToken(access_token_str)
                jti = access_token.get('jti')
                exp = datetime.utcfromtimestamp(access_token['exp'])
                
                # 将access token加入黑名单并清理过期项
                BlacklistedAccessToken.objects.get_or_create(
                    jti=jti, 
                    defaults={'expires_at': exp}
                )
                BlacklistedAccessToken.clean_expired()

            return Response({
                'status': 200,
                'message': '登出成功',
                'user_id': request.user.id,
                'user_name': request.user.username
            }, status=status.HTTP_200_OK)

        except TokenError as e:
            return Response({
                'status': 400,
                'message': f'令牌无效: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'status': 500,
                'message': f'服务器错误: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class DeleteAccountView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request):
        """注销账户验证码发送"""
        email = request.GET.get('email')
        send_code = request.GET.get('send_code')

        if send_code != '1' or not email:
            return Response(
                {'status': 400, 'message': '参数错误'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 邮箱格式验证
        if not is_valid_sdu_email(email):
            return Response(
                {'status': 430, 'message': '非山大邮箱格式'},
                status=430
            )

        # 用户存在性检查
        if not User.objects.filter(email=email).exists():
            return Response(
                {'status': 401, 'message': '用户不存在'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 发送频率限制
        latest_sent = EmailVerificationCode.objects.filter(
            email=email,
            purpose='delete',
            created_at__gte=timezone.now() - timezone.timedelta(seconds=SEND_INTERVAL)
        ).first()

        if latest_sent:
            remaining = (latest_sent.created_at + timezone.timedelta(seconds=SEND_INTERVAL) 
                          - timezone.now()).seconds
            return Response(
                {'status': 429, 'message': f'操作过于频繁，请{remaining}秒后再试'},
                status=429
            )

        # 生成验证码
        code = generate_code()
        expires_at = timezone.now() + timezone.timedelta(seconds=CODE_EXPIRE_TIME)
        
        EmailVerificationCode.objects.create(
            email=email,
            code=code,
            expires_at=expires_at,
            purpose='delete'
        )

        # 发送邮件
        if not send_code_email(email, code, "账户注销"):
            return Response(
                {'status': 500, 'message': '邮件发送失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {'status': 200, 'message': '验证码已发送'},
            status=status.HTTP_200_OK
        )

    def post(self, request):
        """账户注销"""
        data = request.data
        required_fields = ['user_name', 'email', 'email_code']
        
        # 参数校验
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return Response(
                {'status': 400, 'message': f'缺少必要参数: {", ".join(missing_fields)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证用户信息
        try:
            user = User.objects.get(username=data['user_name'], email=data['email'])
        except User.DoesNotExist:
            return Response(
                {'status': 401, 'message': '用户不存在'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 验证码校验
        verification_code = EmailVerificationCode.objects.filter(
            email=data['email'],
            purpose='delete'
        ).order_by('-created_at').first()

        if not verification_code:
            return Response(
                {'status': 404, 'message': '请先获取验证码'},
                status=status.HTTP_404_NOT_FOUND
            )

        if verification_code.code != data['email_code']:
            return Response(
                {'status': 404, 'message': '验证码错误'},
                status=status.HTTP_404_NOT_FOUND
            )

        if verification_code.expires_at < timezone.now():
            return Response(
                {'status': 410, 'message': '验证码已过期'},
                status=status.HTTP_410_GONE
            )

        # 删除用户
        user.delete()
        verification_code.delete()

        return Response(
            {'status': 200, 'message': '账户注销成功'},
            status=status.HTTP_200_OK
        )

class ResetPasswordView(APIView):
    
    def get(self, request):
        """重置密码验证码发送"""
        email = request.GET.get('email')
        send_code = request.GET.get('send_code')

        if send_code != '1' or not email:
            return Response(
                {'status': 400, 'message': '参数错误'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 邮箱格式验证
        if not is_valid_sdu_email(email):
            return Response(
                {'status': 430, 'message': '非山大邮箱格式'},
                status=430
            )

        # 用户存在性检查
        if not User.objects.filter(email=email).exists():
            return Response(
                {'status': 404, 'message': '邮箱未注册'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 发送频率限制
        latest_sent = EmailVerificationCode.objects.filter(
            email=email,
            purpose='reset',
            created_at__gte=timezone.now() - timezone.timedelta(seconds=SEND_INTERVAL)
        ).first()

        if latest_sent:
            remaining = (latest_sent.created_at + timezone.timedelta(seconds=SEND_INTERVAL) 
                          - timezone.now()).seconds
            return Response(
                {'status': 429, 'message': f'操作过于频繁，请{remaining}秒后再试'},
                status=429
            )

        # 生成验证码
        code = generate_code()
        expires_at = timezone.now() + timezone.timedelta(seconds=CODE_EXPIRE_TIME)
        
        EmailVerificationCode.objects.create(
            email=email,
            code=code,
            expires_at=expires_at,
            purpose='reset'
        )

        # 发送邮件
        if not send_code_email(email, code, "密码重置"):
            return Response(
                {'status': 500, 'message': '邮件发送失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {'status': 200, 'message': '验证码已发送'},
            status=status.HTTP_200_OK
        )

    def post(self, request):
        """密码重置"""
        data = request.data
        required_fields = ['email', 'new_pass_word', 'email_code']
        
        # 参数校验
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return Response(
                {'status': 400, 'message': f'缺少必要参数: {", ".join(missing_fields)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证码校验
        verification_code = EmailVerificationCode.objects.filter(
            email=data['email'],
            purpose='reset'
        ).order_by('-created_at').first()

        if not verification_code:
            return Response(
                {'status': 404, 'message': '请先获取验证码'},
                status=status.HTTP_404_NOT_FOUND
            )

        if verification_code.code != data['email_code']:
            return Response(
                {'status': 401, 'message': '验证码错误'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if verification_code.expires_at < timezone.now():
            return Response(
                {'status': 410, 'message': '验证码已过期'},
                status=status.HTTP_410_GONE
            )

        # 获取用户
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            return Response(
                {'status': 401, 'message': '邮箱错误'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 重置频率限制
        cache_key = f'pwd_reset_freq:{user.id}'
        reset_count = cache.get(cache_key, 0)
        if reset_count >= 3:
            return Response(
                {'status': 423, 'message': '操作过于频繁，请1小时后再试'},
                status=423
            )

        # 更新密码
        user.set_password(data['new_pass_word'])
        user.save()

        # 更新频率计数器
        cache.set(cache_key, reset_count + 1, timeout=3600)
        verification_code.delete()

        return Response(
            {'status': 200, 'message': '密码重置成功'},
            status=status.HTTP_200_OK
        )