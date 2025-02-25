# exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed

def custom_exception_handler(exc, context):
    # 先调用默认处理器处理已知异常
    response = exception_handler(exc, context)

    # 自定义处理 AuthenticationFailed
    if isinstance(exc, AuthenticationFailed):
        return Response({
            'status_code': status.HTTP_401_UNAUTHORIZED,
            'message': str(exc.detail)
        }, status=status.HTTP_401_UNAUTHORIZED)

    # 处理其他异常
    if response is not None:
        response.data = {
            'status_code': response.status_code,
            'message': response.data.get('detail', str(exc))
        }

    # 处理未捕获的异常（如500错误）
    else:
        return Response({
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            'message': '服务器内部错误'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response