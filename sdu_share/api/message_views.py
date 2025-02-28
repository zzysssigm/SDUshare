from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Q
from ..models import Message, User, BlockList
import logging
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from datetime import timedelta
from rest_framework.pagination import PageNumberPagination

logger = logging.getLogger(__name__)

class SendMessageView(APIView):
    """发送私信接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        receiver_id = request.data.get('receiver_id')
        content = (request.data.get('content') or '').strip()

        # 参数校验
        if not receiver_id or not content:
            return Response({
                'status': 400,
                'message': '缺少必要参数'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            receiver = User.objects.get(id=receiver_id)
            sender = request.user

            # 检查双方拉黑关系
            if BlockList.objects.filter(
                Q(from_user=sender, to_user=receiver) | 
                Q(from_user=receiver, to_user=sender)
            ).exists():
                return Response({
                    'status': 403,
                    'message': '存在拉黑关系无法发送'
                }, status=status.HTTP_403_FORBIDDEN)

            # 创建消息记录
            Message.objects.create(
                sender=sender,
                receiver=receiver,
                content=content
            )
            return Response({
                'status': 200,
                'message': '私信发送成功'
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'status': 404,
                'message': '接收用户不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"发送私信失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MessagePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class MessageListView(APIView):
    """获取私信列表接口"""
    permission_classes = [IsAuthenticated]
    pagination_class = MessagePagination

    def get(self, request):
        user = request.user
        page_size = int(request.query_params.get('page_size', 10))
        page_index = int(request.query_params.get('page_index', 1))

        # 构建查询条件
        messages = Message.objects.filter(
            Q(sender=user, is_deleted_by_sender=False) |
            Q(receiver=user, is_deleted_by_receiver=False)
        ).order_by('-sent_at')

        # 分页处理
        paginator = self.pagination_class()
        paginator.page_size = page_size
        result_page = paginator.paginate_queryset(messages, request)

        # 序列化数据
        message_list = [{
            "message_id": msg.id,
            "sender_id": msg.sender.id,
            "receiver_id": msg.receiver.id,
            "content": msg.content,
            "sent_at": msg.sent_at.strftime("%Y-%m-%d %H:%M:%S"),
            "read": msg.read
        } for msg in result_page]

        return paginator.get_paginated_response({
            'status': 200,
            'message': '获取成功',
            'message_list': message_list
        })

class MarkAsReadView(APIView):
    """标记消息为已读接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message_id = request.data.get('message_id')
        if not message_id:
            return Response({
                'status': 400,
                'message': '缺少消息ID'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            message = Message.objects.get(id=message_id, receiver=request.user)
            if not message.read:
                message.read = True
                message.save(update_fields=['read'])
            return Response({
                'status': 200,
                'message': '标记成功'
            }, status=status.HTTP_200_OK)

        except Message.DoesNotExist:
            return Response({
                'status': 404,
                'message': '消息不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"标记已读失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecallMessageView(APIView):
    """撤回私信接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message_id = request.data.get('message_id')
        if not message_id:
            return Response({
                'status': 400,
                'message': '缺少消息ID'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            message = Message.objects.get(id=message_id, sender=request.user)

            # 检查是否超过撤回时限（5分钟）
            if timezone.now() - message.sent_at > timedelta(minutes=5):
                return Response({
                    'status': 400,
                    'message': '超过可撤回时限'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 逻辑删除
            message.is_deleted_by_sender = True
            message.save(update_fields=['is_deleted_by_sender'])

            return Response({
                'status': 200,
                'message': '撤回成功'
            }, status=status.HTTP_200_OK)

        except Message.DoesNotExist:
            return Response({
                'status': 403,
                'message': '无权操作该消息'
            }, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"撤回消息失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)