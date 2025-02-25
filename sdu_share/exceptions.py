# exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    PermissionDenied,
    ValidationError
)
from rest_framework_simplejwt.exceptions import (
    InvalidToken,
    TokenError,
    AuthenticationFailed as JWTAuthenticationFailed
)
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404

def custom_exception_handler(exc, context):
    # 优先处理JWT特定错误
    if isinstance(exc, (InvalidToken, TokenError, JWTAuthenticationFailed)):
        return Response({
            'status_code': status.HTTP_401_UNAUTHORIZED,
            'message': _extract_jwt_detail(exc)
        }, status=status.HTTP_401_UNAUTHORIZED)

    # 处理DRF内置异常
    if isinstance(exc, APIException):
        return Response({
            'status_code': exc.status_code,
            'message': _extract_detail_message(exc)
        }, status=exc.status_code)

    # 处理Django原生异常
    if isinstance(exc, Http404):
        return Response({
            'status_code': status.HTTP_404_NOT_FOUND,
            'message': '请求的资源不存在'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if isinstance(exc, DjangoPermissionDenied):
        return Response({
            'status_code': status.HTTP_403_FORBIDDEN,
            'message': '无权执行此操作'
        }, status=status.HTTP_403_FORBIDDEN)

    # 处理未捕获的异常（生产环境）
    return Response({
        'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
        'message': '服务器内部错误'
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _extract_detail_message(exc):
    """统一提取错误信息的核心方法"""
    if hasattr(exc, 'detail'):
        # 处理DRF验证错误的多字段结构
        if isinstance(exc.detail, dict):
            return _format_validation_errors(exc.detail)
        # 处理列表型错误（如多个JWT错误）
        if isinstance(exc.detail, list):
            return ', '.join([str(item) for item in exc.detail])
        return str(exc.detail)
    return str(exc)

def _extract_jwt_detail(exc):
    """深度解析JWT错误结构"""
    try:
        # 处理新版JWT错误格式（带messages数组）
        if hasattr(exc, 'detail') and 'messages' in exc.detail:
            first_msg = exc.detail['messages'][0]
            return f"{first_msg['token_class']}无效: {first_msg['message']}"
        # 处理旧版JWT错误格式
        return str(exc.detail) if hasattr(exc, 'detail') else str(exc)
    except Exception as e:
        return '身份验证失败'

def _format_validation_errors(errors):
    """格式化字段验证错误"""
    error_list = []
    for field, messages in errors.items():
        if isinstance(messages, list):
            error_list.append(f"{field}: {'; '.join(map(str, messages))}")
        else:
            error_list.append(f"{field}: {messages}")
    return ', '.join(error_list)