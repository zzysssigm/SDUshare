# sdu_share/middleware/error_handler.py
from django.http import JsonResponse
from django.urls import Resolver404
from rest_framework import status
from django.core.exceptions import PermissionDenied

class CustomErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response  # Django中间件标准初始化

    def __call__(self, request):
        try:
            response = self.get_response(request)
            
            # 处理Django默认的404响应（非DEBUG模式）
            if response.status_code == 404 and not request.path.startswith('/api/'):
                return JsonResponse({
                    'status_code': status.HTTP_404_NOT_FOUND,
                    'message': '请求的资源不存在'
                }, status=404)
                
            return response
        except Exception as exc:
            # 捕获所有未处理异常
            return self.handle_exception(exc, request)

    def handle_exception(self, exc, request):
        """统一异常处理方法"""
        # 只处理API请求
        if not request.path.startswith('/api/'):
            return None  # 返回默认错误处理

        # 错误类型映射表
        error_map = {
            Resolver404: ('请求的接口不存在', status.HTTP_404_NOT_FOUND),
            PermissionDenied: ('无权访问该资源', status.HTTP_403_FORBIDDEN),
        }

        # 匹配已知错误类型
        for exc_type, (message, code) in error_map.items():
            if isinstance(exc, exc_type):
                return JsonResponse({
                    'status_code': code,
                    'message': message
                }, status=code)

        # 未知错误返回500
        return JsonResponse({
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            'message': '服务器内部错误'
        }, status=500)