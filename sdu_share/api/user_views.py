# myapp/api/user_views.py
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.exceptions import ObjectDoesNotExist
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

# 缓存配置
CACHE_TIMEOUT = 300  # 5分钟
FULL_PROFILE_CACHE_KEY = "user_profile_full_{id}"
BASIC_PROFILE_CACHE_KEY = "user_profile_basic_{id}"

class UserProfileView(APIView):
    """带缓存优化的用户主页接口"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # 获取目标用户ID
            user_id, target_user, is_owner = self._get_target_user(request)
            if isinstance(user_id, Response):
                return user_id  # 直接返回错误响应
            
            # 根据访问权限获取缓存数据
            cache_key = FULL_PROFILE_CACHE_KEY if is_owner else BASIC_PROFILE_CACHE_KEY
            cache_key = cache_key.format(id=user_id)
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.debug(f"缓存命中: {cache_key}")
                return self._build_cached_response(cached_data, is_owner)
                
            # 缓存未命中时查询数据库
            data = self._build_profile_data(target_user, is_owner)
            cache.set(cache_key, data, CACHE_TIMEOUT)
            
            return self._build_response(data, is_owner)

        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_target_user(self, request):
        """解析目标用户信息"""
        user_id = request.query_params.get('user_id')
        
        # 场景1：未传user_id，默认当前用户
        if not user_id:
            return request.user.id, request.user, True
            
        # 场景2：验证user_id类型
        try:
            user_id = int(user_id)
        except ValueError:
            return Response({
                'status': 400,
                'message': 'user_id必须为整数'
            }, status=status.HTTP_400_BAD_REQUEST), None, None
            
        # 场景3：获取目标用户
        try:
            target_user = User.objects.get(id=user_id)
            is_owner = (request.user.id == user_id)
            return user_id, target_user, is_owner
        except ObjectDoesNotExist:
            return Response({
                'status': 404,
                'message': '用户不存在'
            }, status=status.HTTP_404_NOT_FOUND), None, None

    def _build_profile_data(self, user, is_owner):
        """构建数据并缓存"""
        return self._build_full_profile(user) if is_owner else self._build_basic_profile(user)

    def _build_cached_response(self, data, is_owner):
        """构建缓存响应"""
        return Response({
            'status': 200,
            'message': '完整用户信息（来自缓存）' if is_owner else '基础用户信息（来自缓存）',
            'data': data
        }, status=status.HTTP_200_OK)

    def _build_response(self, data, is_owner):
        """构建新响应"""
        return Response({
            'status': 200,
            'message': '完整用户信息' if is_owner else '基础用户信息',
            'data': data
        }, status=status.HTTP_200_OK)


    def _build_full_profile(self, user):
        """完整信息（本人可见）"""
        return {
            'user_id': user.id,
            'user_name': user.username,
            'email': user.email,
            'reputation': user.reputation,
            'reputation_level': self._calc_reputation_level(user.reputation),
            'master': user.master,
            'super_master': user.super_master,
            'profile_url': user.profile_url,
            'campus': user.campus,
            'college': user.college,
            'major': user.major,
            'all_articles': user.all_articles,
            'all_posts': user.all_posts,
            'all_replys': user.all_replys,
            'block_status': user.block,
            'block_end_time': user.block_end_time.isoformat() if user.block_end_time else '',
            'created_at': user.date_joined.isoformat()
        }

    def _build_basic_profile(self, user):
        """基础信息（他人可见）"""
        return {
            'user_id': user.id,
            'user_name': user.username,
            'profile_url': user.profile_url,
            'campus': user.campus,
            'college': user.college,
            'major': user.major,
            'master': user.master,
            'super_master': user.super_master,
            'block_status': user.block,
            'reputation_level': self._calc_reputation_level(user.reputation),
            'article_count': user.all_articles,
            'post_count': user.all_posts,
            'registration_year': user.date_joined.year
        }

    def _calc_reputation_level(self, reputation):
        """计算信誉等级"""
        if reputation >= 200:
            return "高级用户"
        elif reputation >= 150:
            return "优秀用户"
        elif reputation >= 100:
            return "普通用户"
        else:
            return "新用户"