from rest_framework_simplejwt.authentication import JWTAuthentication

class JWTAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = JWTAuthentication().authenticate(request)
        if user:
            request.user = user[0]
        return self.get_response(request)

# from rest_framework_simplejwt.authentication import JWTAuthentication

# class JWTLogoutMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         # 检查访问令牌是否在黑名单中
#         if 'HTTP_AUTHORIZATION' in request.META:
#             try:
#                 auth = JWTAuthentication().authenticate(request)
#                 if auth and auth[1].payload.get('jti') in OutstandingToken.objects.filter(blacklistedtoken__isnull=False):
#                     raise AuthenticationFailed('令牌已失效')
#             except AuthenticationFailed:
#                 return JsonResponse({'status': 401, 'message': '令牌已注销'}, status=401)
        
#         return self.get_response(request)