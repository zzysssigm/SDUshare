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
        if reputation >= 1000:
            return "学术大师"
        elif reputation >= 500:
            return "领域专家"
        elif reputation >= 200:
            return "资深创作者"
        elif reputation >= 100:
            return "知识探索者"
        else:
            return "新晋学者"
        
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import User
import logging

logger = logging.getLogger(__name__)

class UserListView(APIView):
    """带缓存优化的用户列表接口"""
    # permission_classes = [IsAuthenticated]  # 根据需求决定是否开启认证

    CACHE_KEY = 'user_ranking_list'
    CACHE_TIMEOUT = 3000  # 50分钟缓存
    REPUTATION_LEVELS = {
        0: '新晋学者',
        100: '知识探索者',
        200: '资深创作者',
        500: '领域专家',
        1000: '学术大师'
    }

    def get_reputation_level(self, reputation):
        """根据声誉分计算等级"""
        thresholds = sorted(self.REPUTATION_LEVELS.keys(), reverse=True)
        for threshold in thresholds:
            if reputation >= threshold:
                return self.REPUTATION_LEVELS[threshold]
        return '新人学者'

    def get(self, request):
        try:
            # 尝试从缓存获取数据
            cached_data = cache.get(self.CACHE_KEY)
            if cached_data is not None:
                logger.debug('从缓存获取用户列表')
                return Response(cached_data)

            # 缓存未命中，查询数据库
            users = User.objects.all().order_by(
                '-super_master',  # 超级管理员置顶
                '-master',        # 管理员次之
                '-reputation'     # 按声誉分降序
            ).values(
                'id', 'username', 'reputation',
                'all_likes', 'all_articles',
                'master', 'super_master'
            )

            # 处理空结果集
            if not users:
                response_data = {
                    "status": status.HTTP_200_OK,
                    "message": "用户列表为空",
                    "user_list": []
                }
                cache.set(self.CACHE_KEY, response_data, self.CACHE_TIMEOUT)
                return Response(response_data)

            # 构建响应数据
            user_list = []
            for user in users:
                user_data = {
                    "user_id": user['id'],
                    "user_name": user['username'],
                    "reputation_level": self.get_reputation_level(user['reputation']),
                    "all_likes": user['all_likes'],
                    "all_articles": user['all_articles'],
                    "master": user['master'],
                    "super_master": user['super_master']
                }
                user_list.append(user_data)

            response_data = {
                "status": status.HTTP_200_OK,
                "message": "获取成功",
                "user_list": user_list
            }

            # 设置缓存（添加异常处理）
            try:
                cache.set(self.CACHE_KEY, response_data, self.CACHE_TIMEOUT)
                logger.debug('用户列表缓存已更新')
            except Exception as e:
                logger.error(f"缓存设置失败: {str(e)}", exc_info=True)

            return Response(response_data)

        except Exception as e:
            logger.error(f"获取用户列表失败: {str(e)}", exc_info=True)
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "服务器内部错误"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)