# sdu_share/api/auth_views.py
from django.contrib.auth import authenticate, login
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import User, EmailVerificationCode
from ..utils.email_utils import (
    generate_code,
    is_valid_sdu_email,
    send_code_email,
    CODE_EXPIRE_TIME,
    SEND_INTERVAL
)

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
    def post(self, request):
        username = request.data.get('user_name')
        password = request.data.get('pass_word')

        if not username or not password:
            return Response(
                {'status': 400, 'message': '缺少用户名或密码'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 登录失败次数检查
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
                user.block = False
                user.block_end_time = None
                user.save()

        # 执行登录
        login(request, user)
        return Response({
            'status': 200,
            'message': '登录成功',
            'user_id': user.id,
            'user_name': user.username,
            'email': user.email
        }, status=status.HTTP_200_OK)