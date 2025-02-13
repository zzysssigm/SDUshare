# sdu_share_backend/sdu_share/api/blacklist_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from ..models import BlockList, User
import logging

logger = logging.getLogger(__name__)

class BlockUserView(APIView):
    """拉黑用户接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        to_user_id = request.data.get('to_user_id')
        from_user = request.user

        # 参数校验
        if not to_user_id:
            return Response({
                'status': 400,
                'message': '缺少to_user_id参数'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 验证被拉黑用户是否存在
            to_user = User.objects.get(id=to_user_id)
            # 是否已经注销
            if not to_user.is_active:  
                return Response({
                    'status': 404,
                    'message': '用户已注销'
                }, status=status.HTTP_404_NOT_FOUND)
            # 不能拉黑自己
            if from_user.id == int(to_user_id):
                return Response({
                    'status': 400,
                    'message': '不能拉黑自己'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 创建拉黑关系
            BlockList.objects.create(
                from_user=from_user,
                to_user=to_user
            )
            return Response({
                'status': 200,
                'message': '拉黑成功'
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'status': 404,
                'message': '用户不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError:
            return Response({
                'status': 409,
                'message': '已拉黑该用户'
            }, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            logger.error(f"拉黑用户失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UnblockUserView(APIView):
    """解除拉黑接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        to_user_id = request.data.get('to_user_id')
        from_user = request.user

        if not to_user_id:
            return Response({
                'status': 400,
                'message': '缺少to_user_id参数'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 获取被拉黑用户
            to_user = User.objects.get(id=to_user_id)
            if not to_user.is_active:
                return Response({
                    'status': 404,
                    'message': '用户已注销'
                }, status=status.HTTP_404_NOT_FOUND)

            # 删除拉黑关系
            block_entry = BlockList.objects.get(
                from_user=from_user,
                to_user=to_user
            )
            block_entry.delete()
            return Response({
                'status': 200,
                'message': '解除拉黑成功'
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'status': 404,
                'message': '用户不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except BlockList.DoesNotExist:
            return Response({
                'status': 401,
                'message': '尚未拉黑该用户'
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"解除拉黑失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BlockListView(APIView):
    """获取黑名单列表接口"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get('user_id')
        current_user = request.user

        # 验证权限
        if current_user.id != int(user_id):
            return Response({
                'status': 401,
                'message': '无权查看他人黑名单'
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            # 获取黑名单列表
            block_entries = BlockList.objects.filter(from_user=current_user)
            block_list = []
            for entry in block_entries:
                user = entry.to_user
                block_list.append({
                    'to_user_id': user.id,
                    'to_user_name': user.username,
                    'email': user.email,
                    'profile_url': user.profile.avatar_url if hasattr(user, 'profile') else None
                })
            return Response({
                'status': 200,
                'message': '获取成功',
                'block_list': block_list
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"获取黑名单失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)