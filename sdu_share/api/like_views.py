from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from ..models import Like, Article, Post, Reply
import logging
 


logger = logging.getLogger(__name__)

# 内容类型映射
CONTENT_TYPE_MAP = {
    0: Article,
    1: Post,
    2: Reply
}

class LikeView(APIView):
    """点赞功能核心类"""
    permission_classes = [IsAuthenticated]

    def get_content_model(self, content_type):
        """获取对应的内容模型类"""
        model = CONTENT_TYPE_MAP.get(content_type)
        if not model:
            raise ValueError("无效的内容类型")
        return model

    def post(self, request):
        """创建点赞"""
        try:
            data = request.data
            content_type = int(data.get('content_type'))
            content_id = int(data.get('content_id'))

            # 参数验证
            if content_type not in CONTENT_TYPE_MAP:
                return Response({
                    'status': 400,
                    'message': '无效的内容类型'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 获取内容对象
            model = self.get_content_model(content_type)
            content = model.objects.filter(id=content_id).first()
            if not content:
                return Response({
                    'status': 404,
                    'message': '内容不存在'
                }, status=status.HTTP_404_NOT_FOUND)

            # 创建点赞记录
            Like.objects.create(
                user=request.user,
                content_type=ContentType.objects.get_for_model(model),
                object_id=content_id
            )

            return Response({
                'status': 200,
                'message': '点赞成功'
            }, status=status.HTTP_200_OK)

        except IntegrityError:
            return Response({
                'status': 409,
                'message': '已经点赞过'
            }, status=status.HTTP_409_CONFLICT)
        except (TypeError, ValueError, KeyError):
            return Response({
                'status': 400,
                'message': '参数错误'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"点赞失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UnlikeView(APIView):
    """取消点赞功能"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """取消点赞"""
        try:
            data = request.data
            content_type = int(data.get('content_type'))
            content_id = int(data.get('content_id'))

            # 获取内容类型
            if content_type not in CONTENT_TYPE_MAP:
                return Response({
                    'status': 400,
                    'message': '无效的内容类型'
                }, status=status.HTTP_400_BAD_REQUEST)

            model = CONTENT_TYPE_MAP[content_type]
            content_type_obj = ContentType.objects.get_for_model(model)
            
            # 删除点赞记录
            deleted, _ = Like.objects.filter(
                user=request.user,
                content_type=content_type_obj,
                object_id=content_id
            ).delete()

            if not deleted:
                return Response({
                    'status': 404,
                    'message': '未找到点赞记录'
                }, status=status.HTTP_404_NOT_FOUND)

            return Response({
                'status': 200,
                'message': '取消点赞成功'
            }, status=status.HTTP_200_OK)

        except (TypeError, ValueError, KeyError):
            return Response({
                'status': 400,
                'message': '参数错误'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"取消点赞失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LikeCountView(APIView):
    """获取点赞数"""
    # authentication_classes = []  # 禁用所有认证
    # permission_classes = [AllowAny]  # 允许所有访问
    def get(self, request):
        try:
            content_type = int(request.query_params.get('content_type'))
            content_id = int(request.query_params.get('content_id'))

            if content_type not in CONTENT_TYPE_MAP:
                return Response({
                    'status': 400,
                    'message': '无效的内容类型'
                }, status=status.HTTP_400_BAD_REQUEST)

            model = CONTENT_TYPE_MAP[content_type]
            content_type_obj = ContentType.objects.get_for_model(model)
            count = Like.objects.filter(
                content_type=content_type_obj,
                object_id=content_id
            ).count()

            return Response({
                'status': 200,
                'message': '成功',
                'like_count': count
            }, status=status.HTTP_200_OK)

        except (TypeError, ValueError):
            return Response({
                'status': 400,
                'message': '参数错误'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"获取点赞数失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserLikesView(APIView):
    """用户点赞列表(需验证user_id权限)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # 必须参数校验
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({
                    'status': 400,
                    'message': '缺少user_id参数'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 类型校验
            try:
                user_id = int(user_id)
            except ValueError:
                return Response({
                    'status': 400,
                    'message': 'user_id必须为整数'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 权限校验
            if user_id != request.user.id:
                return Response({
                    'status': 403,
                    'message': '无权查看其他用户点赞列表'
                }, status=status.HTTP_403_FORBIDDEN)

            # 分页参数处理
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))

            # 分页查询
            likes = Like.objects.filter(user=request.user).order_by('-created_at')
            paginated_likes = likes[(page-1)*page_size : page*page_size]

            # 构建响应数据
            content_list = []
            for like in paginated_likes:
                content_type = next(
                    (k for k, v in CONTENT_TYPE_MAP.items() 
                     if v == like.content_type.model_class()),
                    None
                )
                content_list.append({
                    'content_type': content_type,
                    'content_id': like.object_id
                })

            return Response({
                'status': 200,
                'message': '成功',
                'total': likes.count(),
                'page': page,
                'page_size': page_size,
                'data': content_list
            }, status=status.HTTP_200_OK)

        except (TypeError, ValueError) as e:
            logger.warning(f"参数类型错误: {str(e)}")
            return Response({
                'status': 400,
                'message': '参数类型错误'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"获取点赞列表失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)