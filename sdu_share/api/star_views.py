from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
import logging
from ..models import Star, StarFolder, Course, Article, Post
from ..utils import notify
from rest_framework.response import Response
from collections import defaultdict
from rest_framework.pagination import PageNumberPagination
from django.db import models
from django.core.cache import cache
from django.http import Http404
from django.db import IntegrityError

logger = logging.getLogger(__name__)

class StarService:
    @classmethod
    def create_star(cls, user, content_type, content_id, folder_id=None):
        """增强版收藏服务方法"""
        # 校验内容类型有效性
        if content_type not in (0, 1, 2):
            raise ValueError("无效内容类型，请使用 0/1/2 分别表示课程/文章/帖子")

        # 获取目标对象
        model_map = {
            0: Course,
            1: Article,
            2: Post
        }
        obj = get_object_or_404(model_map[content_type], id=content_id)

        # 获取或创建收藏夹
        folder = None
        if folder_id:
            # 校验用户是否有权限操作该收藏夹
            folder = get_object_or_404(
                StarFolder, 
                id=folder_id, 
                user=user  # 确保收藏夹属于当前用户
            )
        else:
            # 原子操作获取默认收藏夹
            folder, created = StarFolder.objects.get_or_create(
                user=user,
                is_default=True,
                defaults={
                    'name': '默认收藏',
                    'description': '系统自动创建的默认收藏夹'
                }
            )

        # 创建收藏记录
        star, created = Star.objects.get_or_create(
            user=user,
            content_type=content_type,
            content_id=content_id,
            folder=folder,
            defaults={'notes': ''}
        )
        
        if not created:
            raise ValueError("不可重复收藏相同内容")

        return star

class StarContentView(APIView):
    """修复版收藏接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            required_fields = ['content_type', 'content_id']
            
            # 参数存在性校验
            if missing := [f for f in required_fields if f not in data]:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': f'缺少必要参数: {", ".join(missing)}'
                }, status.HTTP_400_BAD_REQUEST)

            # 参数类型校验
            try:
                content_type = int(data['content_type'])
                content_id = int(data['content_id'])
                if content_type not in (0, 1, 2):
                    raise ValueError
            except (ValueError, TypeError):
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '参数类型错误：content_type必须为0/1/2，content_id必须为整数'
                }, status.HTTP_400_BAD_REQUEST)

            # 处理收藏请求
            try:
                star = StarService.create_star(
                    user=request.user,
                    content_type=content_type,
                    content_id=content_id,
                    folder_id=data.get('folder_id')
                )
            except Http404 as e:
                return Response({
                    'status': status.HTTP_404_NOT_FOUND,
                    'message': str(e)
                }, status.HTTP_404_NOT_FOUND)

            return Response({
                'status': status.HTTP_201_CREATED,
                'message': '收藏成功',
                'star_id': star.id
            }, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': str(e)
            }, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"收藏失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status.HTTP_500_INTERNAL_SERVER_ERROR)

class StarFolderCreateView(APIView):
    """支持名称重复校验的收藏夹创建接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            required_fields = ['folder_name']
            
            # 参数存在性校验
            if missing := [f for f in required_fields if f not in data]:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': f'缺少必要参数: {", ".join(missing)}'
                }, status.HTTP_400_BAD_REQUEST)

            folder_name = data['folder_name'].strip()
            
            # 名称有效性校验
            if len(folder_name) < 2:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '收藏夹名称至少需要2个有效字符'
                }, status.HTTP_400_BAD_REQUEST)

            # 名称重复性校验
            if StarFolder.objects.filter(
                user=request.user,
                name__iexact=folder_name  # 不区分大小写校验
            ).exists():
                return Response({
                    'status': status.HTTP_409_CONFLICT,
                    'message': '收藏夹名称已存在，请使用其他名称'
                }, status.HTTP_409_CONFLICT)

            # 创建收藏夹
            folder = StarFolder.objects.create(
                user=request.user,
                name=folder_name,
                description=data.get('description', '')[:500],  # 限制长度
                parent_id=data.get('parent_id')
            )

            return Response({
                'status': status.HTTP_201_CREATED,
                'message': '创建成功',
                'folder_id': folder.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"创建收藏夹失败: {str(e)}", exc_info=True)
            error_msg = '服务器内部错误'
            if isinstance(e, IntegrityError):
                error_msg = '收藏夹名称已存在（并发冲突）'
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': error_msg
            }, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class StarListView(APIView):
    """支持分页和整数类型 content_type 的收藏列表接口"""
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
    pagination_class.page_size = 20

    # 内容类型与模型的映射
    CONTENT_TYPE_MAP = {
        0: {
            'model': Course,
            'name_field': 'course_name'
        },
        1: {
            'model': Article,
            'name_field': 'article_title'
        },
        2: {
            'model': Post,
            'name_field': 'post_title'
        }
    }

    def get(self, request):
        try:
            # 获取查询参数
            folder_id = request.query_params.get('folder_id')
            user = request.user

            # 构建基础查询集
            queryset = Star.objects.filter(user=user).select_related('folder')
            
            # 收藏夹过滤
            if folder_id:
                try:
                    folder = StarFolder.objects.get(id=folder_id, user=user)
                    queryset = queryset.filter(folder=folder)
                except StarFolder.DoesNotExist:
                    return Response({
                        'status': status.HTTP_404_NOT_FOUND,
                        'message': '收藏夹不存在'
                    }, status.HTTP_404_NOT_FOUND)

            # 分页处理
            paginator = self.pagination_class()
            page_stars = paginator.paginate_queryset(queryset, request)
            
            # 批量预加载内容对象
            content_objects = self._prefetch_contents(page_stars)

            # 构建响应数据
            star_list = []
            for star in page_stars:
                content_info = content_objects.get((star.content_type, star.content_id), {})
                
                star_data = {
                    "star_id": star.id,
                    "content_type": star.content_type,
                    "content_id": star.content_id,
                    "content_name": content_info.get('name', '已删除内容'),
                    "created_at": star.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "folder_info": {
                        "folder_id": star.folder.id,
                        "folder_name": star.folder.name
                    }
                }
                
                # 添加内容详情链接
                if detail_url := content_info.get('url'):
                    star_data['content_url'] = detail_url
                
                star_list.append(star_data)

            return paginator.get_paginated_response({
                'status': status.HTTP_200_OK,
                'message': '获取成功',
                'data': star_list
            })

        except Exception as e:
            logger.error(f"获取收藏列表失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _prefetch_contents(self, stars):
        """批量预加载所有内容对象"""
        content_map = defaultdict(dict)
        type_groups = defaultdict(list)

        # 按内容类型分组
        for star in stars:
            type_groups[star.content_type].append(star.content_id)

        # 批量查询各类型内容
        for ctype, ids in type_groups.items():
            if ctype not in self.CONTENT_TYPE_MAP:
                continue
                
            model_cls = self.CONTENT_TYPE_MAP[ctype]['model']
            name_field = self.CONTENT_TYPE_MAP[ctype]['name_field']
            
            try:
                for obj in model_cls.objects.filter(id__in=ids):
                    content_map[(ctype, obj.id)] = {
                        'name': getattr(obj, name_field, ''),
                        'url': self._get_detail_url(ctype, obj.id)
                    }
            except Exception as e:
                logger.error(f"内容预加载失败: {str(e)}")

        return content_map

    def _get_detail_url(self, content_type, content_id):
        """生成内容详情页链接"""
        url_patterns = {
            0: '/courses/{id}',
            1: '/articles/{id}',
            2: '/posts/{id}'
        }
        return url_patterns.get(content_type, '').format(id=content_id)
    
class UnstarView(APIView):
    """支持整数类型 content_type 的取消收藏接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            required_fields = ['content_type', 'content_id']
            
            # 参数存在性校验
            if missing := [f for f in required_fields if f not in data]:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': f'缺少必要参数: {", ".join(missing)}'
                }, status.HTTP_400_BAD_REQUEST)

            # 参数类型校验
            try:
                content_type = int(data['content_type'])
                if content_type not in (0, 1, 2):
                    raise ValueError
                content_id = int(data['content_id'])
            except (ValueError, TypeError):
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '参数类型错误：content_type必须为0/1/2，content_id必须为整数'
                }, status.HTTP_400_BAD_REQUEST)

            # 获取收藏记录
            star = get_object_or_404(
                Star,
                user=request.user,
                content_type=content_type,
                content_id=content_id
            )
            
            # 删除前记录信息用于缓存更新
            content_type_val = star.content_type
            content_id_val = star.content_id
            
            # 执行删除
            star.delete()
            
            # 更新缓存计数器
            self._update_star_count_cache(content_type_val, content_id_val)

            return Response({
                'status': status.HTTP_200_OK,
                'message': '取消收藏成功'
            })

        except Exception as e:
            logger.error(f"取消收藏失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _update_star_count_cache(self, content_type, content_id):
        """原子操作更新缓存计数器"""
        cache_key = f'star_count:{content_type}:{content_id}'
        try:
            # 使用原子操作确保并发安全
            cache.decr(cache_key)
        except ValueError:
            # 计数器不存在时重新初始化
            count = Star.objects.filter(
                content_type=content_type,
                content_id=content_id
            ).count()
            cache.set(cache_key, count, timeout=600)
        except Exception as e:
            logger.warning(f"缓存更新异常: {str(e)}")

class StarFolderListView(APIView):
    """修复版收藏夹列表接口"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            
            # 获取包含必要字段的收藏夹列表
            folders = StarFolder.objects.filter(user=user)\
                .annotate(star_count=models.Count('stars'))\
                .values('id', 'name', 'description', 'star_count', 
                       'created_at', 'parent_id')  # 添加 parent_id
            folders = list(folders)  # 转换为列表方便处理

            # 构造树形结构
            folder_map = {}
            for f in folders:
                f['children'] = []
                folder_map[f['id']] = f

            root_folders = []
            for f in folders:
                parent_id = f.get('parent_id')
                if parent_id and parent_id in folder_map:
                    folder_map[parent_id]['children'].append(f)
                else:
                    root_folders.append(f)

            # 按创建时间排序（可选）
            root_folders.sort(key=lambda x: x['created_at'], reverse=True)
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "获取成功",
                "folders": root_folders
            })

        except Exception as e:
            logger.error(f"获取收藏夹失败: {str(e)}", exc_info=True)
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "服务器内部错误"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)