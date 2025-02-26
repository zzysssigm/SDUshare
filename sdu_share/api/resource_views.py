from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from django.core.files.storage import default_storage
from django.conf import settings
from ..models import Article
import os
import uuid
from rest_framework.permissions import IsAuthenticated
from django.http import FileResponse

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

class ResourceUploadView(APIView):
    parser_classes = (MultiPartParser,)
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_obj = request.FILES.get('file')
        article_id = request.data.get('article_id')

        # 参数验证
        if not file_obj:
            return Response({'status': 400, 'message': '请选择文件'}, status=400)
        if not article_id:
            return Response({'status': 400, 'message': '需要article_id参数'}, status=400)
        if file_obj.size > MAX_FILE_SIZE:
            return Response({'status': 400, 'message': '文件大小不能超过50MB'}, status=400)

        try:
            article = Article.objects.get(id=article_id, author=request.user)
        except Article.DoesNotExist:
            return Response({'status': 404, 'message': '文章不存在'}, status=404)

        # 生成唯一文件名
        ext = os.path.splitext(file_obj.name)[1]
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join('resources', filename)

        # 保存文件
        default_storage.save(filepath, file_obj)

        # 更新文章资源链接
        article.resource_link = default_storage.url(filepath)
        article.save(update_fields=['resource_link'])

        return Response({
            'status': 200,
            'message': '上传成功',
            'source_url': article.resource_link
        })

class ResourceDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, path):
        if not default_storage.exists(path):
            return Response({'status': 404, 'message': '文件不存在'}, status=404)

        file = default_storage.open(path)
        response = FileResponse(file)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
        return response