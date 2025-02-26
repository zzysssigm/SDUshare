# <app_name>/api/image_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from django.utils import timezone
import os
import logging
from ..models import Image
from django.http import FileResponse

logger = logging.getLogger(__name__)

# 通用配置
MAX_PROFILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_ARTICLE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}

class ImageUploadBase(APIView):
    """图片上传基类"""
    def validate_image(self, file, max_size):
        """通用图片验证"""
        if file.size > max_size:
            return False, '文件过大'
        ext = file.name.split('.')[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, '不支持的格式'
        return True, ''

class ProfileImageUpload(ImageUploadBase):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """上传头像接口（带3小时限流）"""
        # 限流检查
        cache_key = f'profile_upload_{request.user.id}'
        last_upload = cache.get(cache_key)
        if last_upload and (timezone.now() - last_upload).seconds < 10800:
            return Response(
                {'status': status.HTTP_429_TOO_MANY_REQUESTS, 'message': '操作过于频繁'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # 文件验证
        if 'image' not in request.FILES:
            return Response(
                {'status': status.HTTP_400_BAD_REQUEST, 'message': '请选择文件'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['image']
        is_valid, msg = self.validate_image(file, MAX_PROFILE_SIZE)
        if not is_valid:
            return Response(
                {'status': status.HTTP_400_BAD_REQUEST, 'message': msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 删除旧头像
        try:
            old_images = Image.objects.filter(user=request.user, is_profile_image=True)
            for img in old_images:
                default_storage.delete(img.image.name)
            old_images.delete()
        except Exception as e:
            logger.error(f"删除旧头像失败: {str(e)}", exc_info=True)
            return Response(
                {'status': status.HTTP_500_INTERNAL_SERVER_ERROR, 'message': '服务器错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 保存新头像
        try:
            new_image = Image.objects.create(
                user=request.user,
                image=file,
                file_size=file.size,
                content_type=file.content_type,
                is_profile_image=True
            )
        except Exception as e:
            logger.error(f"头像保存失败: {str(e)}", exc_info=True)
            return Response(
                {'status': status.HTTP_500_INTERNAL_SERVER_ERROR, 'message': '保存失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        cache.set(cache_key, timezone.now(), timeout=10800)
        return Response({
            'status': status.HTTP_200_OK,
            'message': '上传成功',
            'profile_url': f'/image/user?user_id={request.user.id}'
        }, status=status.HTTP_200_OK)

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

class UserProfileImage(APIView):
    def get(self, request):
        """开放获取用户头像接口"""
        try:
            # 参数必填校验
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response(
                    {'status': status.HTTP_400_BAD_REQUEST, 'message': '缺少user_id参数'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 类型转换校验
            try:
                user_id = int(user_id)
            except ValueError:
                return Response(
                    {'status': status.HTTP_400_BAD_REQUEST, 'message': '用户ID格式错误'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 获取用户模型（不再依赖request.user）
            UserModel = get_user_model()
            
            # 查询用户
            try:
                user = UserModel.objects.get(pk=user_id)
            except UserModel.DoesNotExist:
                return Response(
                    {'status': status.HTTP_404_NOT_FOUND, 'message': '用户不存在'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 查询最新头像
            image = Image.objects.filter(
                user=user,
                is_profile_image=True
            ).order_by('-created_at').first()
            
            if not image:
                return Response(
                    {'status': status.HTTP_404_NOT_FOUND, 'message': '该用户未设置头像'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 返回文件响应
            try:
                return FileResponse(default_storage.open(image.image.name))
            except FileNotFoundError:
                logger.error(f"头像文件丢失 user_id:{user_id}")
                return Response(
                    {'status': status.HTTP_404_NOT_FOUND, 'message': '头像文件丢失'},
                    status=status.HTTP_404_NOT_FOUND
                )

        except Exception as e:
            logger.error(f"头像接口异常: {str(e)}", exc_info=True)
            return Response(
                {'status': status.HTTP_500_INTERNAL_SERVER_ERROR, 'message': '服务器繁忙'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ArticleImageUpload(ImageUploadBase):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """上传文章图片接口"""
        if 'image' not in request.FILES:
            return Response(
                {'status': status.HTTP_400_BAD_REQUEST, 'message': '请选择文件'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['image']
        is_valid, msg = self.validate_image(file, MAX_ARTICLE_SIZE)
        if not is_valid:
            return Response(
                {'status': status.HTTP_400_BAD_REQUEST, 'message': msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_image = Image.objects.create(
                user=request.user,
                image=file,
                file_size=file.size,
                content_type=file.content_type
            )
        except Exception as e:
            logger.error(f"文章图片上传失败: {str(e)}", exc_info=True)
            return Response(
                {'status': status.HTTP_500_INTERNAL_SERVER_ERROR, 'message': '上传失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            'status': status.HTTP_200_OK,
            'message': '上传成功',
            'image_url': f'/image/get/{new_image.image.name.split("/")[-1]}'  # 仅返回文件名部分
        }, status=status.HTTP_200_OK)

class ImageRetrieve(APIView):
    def get(self, request, image_name):
        """通用图片获取接口"""
        try:
            image = Image.objects.get(image__endswith=f'/{image_name}')
        except Image.DoesNotExist:
            return Response(
                {'status': status.HTTP_404_NOT_FOUND, 'message': '图片不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            return FileResponse(default_storage.open(image.image.name))
        except FileNotFoundError:
            logger.error(f"图片文件缺失: {image_name}")
            return Response(
                {'status': status.HTTP_404_NOT_FOUND, 'message': '文件不存在'},
                status=status.HTTP_404_NOT_FOUND
            )