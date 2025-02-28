
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from ..models import Notification, User
import logging
logger = logging.getLogger(__name__)

class NotificationPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 100
    page_size_query_param = 'page_size'
    page_query_param = 'page_index'

class NotificationListView(APIView):
    """获取通知列表（安全增强版）"""
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get(self, request):
        try:
            # 直接从认证用户获取信息
            user = request.user
            
            # 构建查询集（添加预加载优化）
            queryset = Notification.objects.filter(
                user=user
            ).select_related('content_type').prefetch_related('content_object')
            
            # 添加过滤参数（示例）
            if n_type := request.query_params.get('type'):
                queryset = queryset.filter(n_type=n_type)
            
            # 分页处理
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request)
            
            # 序列化逻辑（添加空值保护）
            notification_list = []
            for n in page or []:
                try:
                    related_obj = {
                        'type': n.content_type.model if n.content_type else None,
                        'id': n.object_id or 0,
                        'preview': str(n.content_object)[:50] if n.content_object else None
                    } if n.content_object else None
                    
                    notification_list.append({
                        'notification_id': n.id,
                        'type': n.n_type or 'unknown',
                        'message': (n.message or '')[:200],  # 防止超长文本
                        'is_read': n.is_read,
                        'created_at': n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else None,
                        'related_object': related_obj,
                        'extra': n.extra_data or {}
                    })
                except Exception as e:
                    logger.error(f"通知序列化异常 ID:{n.id} - {str(e)}")

            return Response({
                'status': status.HTTP_200_OK,
                'message': '获取成功',
                'notification_list': notification_list,
                'total': queryset.count(),
                'unread_count': queryset.filter(is_read=False).count()
            })

        except Exception as e:
            logger.error(f"通知列表获取失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            notification_ids = request.data.get('notification_ids', [])
            if not isinstance(notification_ids, list):
                notification_ids = [notification_ids]

            # 批量更新
            updated = Notification.objects.filter(
                id__in=notification_ids,
                user=request.user
            ).update(is_read=True)

            if updated == 0:
                return Response({
                    'status': status.HTTP_404_NOT_FOUND,
                    'message': '未找到相关通知'
                }, status=status.HTTP_404_NOT_FOUND)

            return Response({
                'status': status.HTTP_200_OK,
                'message': f'成功标记{updated}条通知为已读'
            })

        except Exception as e:
            logger.error(f"标记已读失败: {str(e)}")
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)