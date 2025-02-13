# sdu_share_backend/sdu_share/api/article_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from ..models import Article, User, Tag, Post, Reply, Course, Star, Like
import logging
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Count, Prefetch
from django.db import models
from django.core.cache import cache

logger = logging.getLogger(__name__)

class ArticleCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 必填字段检查（移除了author_id）
        required_fields = ['article_title', 'content']
        if not all(field in request.data for field in required_fields):
            return Response({
                'status': 400,
                'message': '缺少必要参数：article_title, content'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = request.data
            author = request.user  # 直接从Token获取当前用户
            
            with transaction.atomic():
                # 创建文章
                article = Article.objects.create(
                    article_title=data['article_title'],
                    content=data['content'],
                    author=author,  # 自动关联当前用户
                    article_type=data.get('article_type', 'original'),
                    origin_link=data.get('origin_link'),
                    resource_link=data.get('resource_link'),
                    cover_link=data.get('cover_link'),
                    article_summary=data.get('article_summary', '')
                )

                # 处理标签（逻辑保持不变）
                tags_str = data.get('tags', '')
                if tags_str:
                    tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
                    for tag_name in tags:
                        tag, _ = Tag.objects.get_or_create(name=tag_name)
                        article.tags.add(tag)

                return Response({
                    'status': 200,
                    'message': '创建成功',
                    'article_id': article.id
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"创建文章失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ArticleEditView(APIView):
    """编辑文章接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if 'article_id' not in request.data:
            return Response({
                'status': 400,
                'message': '缺少article_id参数'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = request.data
            article = get_object_or_404(Article, id=data['article_id'])
            
            # 验证操作者是否为作者
            if request.user != article.author:
                return Response({
                    'status': 403,
                    'message': '无权编辑他人文章'
                }, status=status.HTTP_403_FORBIDDEN)

            with transaction.atomic():
                # 更新基础字段
                fields = ['article_title', 'content', 'article_type', 'origin_link']
                for field in fields:
                    if field in data:
                        setattr(article, field, data[field])
                
                # 处理标签
                if 'tags' in data:
                    article.tags.clear()
                    tags = [tag.strip() for tag in data['tags'].split('#') if tag.strip()]
                    for tag_name in tags:
                        tag, _ = Tag.objects.get_or_create(name=tag_name)
                        article.tags.add(tag)
                
                article.save()
                return Response({
                    'status': 200,
                    'message': '更新成功'
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"编辑文章失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ArticleDeleteView(APIView):
    """删除文章接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if 'article_id' not in request.data:
            return Response({
                'status': 400,
                'message': '缺少article_id参数'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            article = get_object_or_404(Article, id=request.data['article_id'])
            
            # 验证操作者是否为作者
            if request.user != article.author:
                return Response({
                    'status': 403,
                    'message': '无权删除他人文章'
                }, status=status.HTTP_403_FORBIDDEN)

            article.delete()
            return Response({
                'status': 200,
                'message': '删除成功'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"删除文章失败: {str(e)}", exc_info=True)
            return Response({
                'status': 500,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

from django.contrib.contenttypes.models import ContentType

class ArticleDetailView(APIView):
    """获取文章详情接口"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        article_id = request.query_params.get('article_id')
        if not article_id:
            return Response({
                'status': 400,
                'message': '缺少article_id参数'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            article = Article.objects.select_related('author').prefetch_related('tags').get(id=article_id)
            current_user = request.user if request.user.is_authenticated else None
            
            data = {
                'article_id': article.id,
                'article_title': article.article_title,
                'article_content': article.content,
                'article_type': article.get_article_type_display(),
                'origin_link': article.origin_link,
                'article_tags': [tag.name for tag in article.tags.all()],
                'author_name': article.author.username,
                'author_profile_url': article.author.profile_url,
                'like_count': article.likes.count(),
                'star_count': self.get_star_count(article),
                'view_count': article.views,
                'reply_count': article.posts.aggregate(total=Count('replies'))['total'],
                'source_url': article.resource_link,
                'publish_time': article.publish_time,
                'if_like': article.likes.filter(user=current_user).exists() if current_user else False,
                # 修改这里，使用检查方法代替直接属性访问
                'if_star': self.check_if_starred(current_user, article.id)
            }

            Article.objects.filter(id=article_id).update(views=models.F('views') + 1)
            return Response({'status': 200, 'article_detail': data}, status=200)

        except Article.DoesNotExist:
            return Response({'status': 404, 'message': '文章不存在'}, status=404)
        except Exception as e:
            logger.error(f"获取文章详情失败: {str(e)}", exc_info=True)
            return Response({'status': 500, 'message': '服务器错误'}, status=500)

    def check_if_starred(self, user, article_id):
        """检查是否收藏（带缓存优化）"""
        if not user:
            return False

        cache_key = f'user_star_status:{user.id}:article:{article_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        article_ct = ContentType.objects.get_for_model(Article)
        is_starred = Star.objects.filter(
            user=user,
            content_type=article_ct,
            object_id=article_id
        ).exists()

        cache.set(cache_key, is_starred, timeout=300)
        return is_starred

    def get_star_count(self, article):
        """获取文章收藏数（带缓存）"""
        ct = ContentType.objects.get_for_model(Article)
        cache_key = f'article_stars:{article.id}'
        count = cache.get(cache_key)
        if count is None:
            count = Star.objects.filter(content_type=ct, object_id=article.id).count()
            cache.set(cache_key, count, timeout=300)
        return count


class ArticlePostListView(APIView):
    """获取文章关联帖子分页列表接口（带优化）"""
    permission_classes = []  # 根据实际需求设置权限

    def get(self, request):
        try:
            # 参数解析与校验
            article_id = request.query_params.get('article_id')
            page_index = int(request.query_params.get('page_index', 1))
            page_size = int(request.query_params.get('page_size', 20))

            # 参数有效性检查
            if not article_id:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '缺少article_id参数'
                }, status=status.HTTP_400_BAD_REQUEST)

            if page_index < 1 or page_size < 1:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '分页参数必须大于0'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 验证文章存在性
            try:
                Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                return Response({
                    'status': status.HTTP_404_NOT_FOUND,
                    'message': '文章不存在'
                }, status=status.HTTP_404_NOT_FOUND)

            # 构建基础查询
            base_query = Post.objects.filter(
                article_id=article_id
            ).select_related('poster').prefetch_related(
                Prefetch('tags', queryset=Tag.objects.only('name'))
            ).annotate(
                like_count=Count('likes'),
                reply_count=Count('replies')
            ).order_by('-publish_time')

            # 分页处理
            paginator = Paginator(base_query, page_size)
            try:
                page_obj = paginator.page(page_index)
            except EmptyPage:
                return Response({
                    'status': status.HTTP_200_OK,
                    'message': '无更多数据',
                    'post_list': [],
                    'total_pages': paginator.num_pages,
                    'current_page': page_index
                }, status=status.HTTP_200_OK)

            # 预取点赞状态（优化批量查询）
            current_user = request.user if request.user.is_authenticated else None
            liked_post_ids = set()
            if current_user:
                liked_posts = Like.objects.filter(
                    user=current_user,
                    content_type=ContentType.objects.get_for_model(Post),
                    object_id__in=[post.id for post in page_obj]
                ).values_list('object_id', flat=True)
                liked_post_ids = set(liked_posts)

            # 构建响应数据
            post_list = []
            for post in page_obj:
                post_list.append({
                    'post_id': post.id,
                    'post_title': post.post_title,
                    'post_content': post.content,
                    'poster_name': post.poster.username,
                    'poster_profile_url': post.poster.profile_url,
                    'view_count': post.views,
                    'like_count': post.like_count,  # 使用annotate结果
                    'reply_count': post.reply_count,  # 使用annotate结果
                    'tags': [tag.name for tag in post.tags.all()],
                    'publish_time': post.publish_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'if_like': post.id in liked_post_ids
                })

            return Response({
                'status': status.HTTP_200_OK,
                'message': '获取成功',
                'post_list': post_list,
                'total_pages': paginator.num_pages,
                'current_page': page_index
            }, status=status.HTTP_200_OK)

        except ValueError:
            logger.warning("参数类型错误")
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': '参数类型错误'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"获取帖子列表失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

from django.db.models import Case, When, IntegerField
from django.core.cache import cache

class ArticleListView(APIView):
    """分页获取文章列表接口（支持标签名称筛选和多维度排序）"""
    permission_classes = []  # 根据实际需求设置权限

    SORT_MAPPING = {
        'time': '-publish_time',
        'star': '-stars',
        'view': '-views'
    }

    def get(self, request):
        try:
            # 参数解析与校验
            page_index = int(request.query_params.get('page_index', 1))
            page_size = int(request.query_params.get('page_size', 20))
            tags_param = request.query_params.get('tags', '')
            sort_type = request.query_params.get('sort', 'time')

            # 参数有效性检查
            if page_index < 1 or page_size < 1:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '分页参数必须大于0'
                }, status=status.HTTP_400_BAD_REQUEST)

            if sort_type not in self.SORT_MAPPING:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': f'无效排序参数，可选值：{",".join(self.SORT_MAPPING.keys())}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 处理标签筛选
            tag_names = [name.strip().lower() for name in tags_param.split(',') if name.strip()]
            invalid_tags = []
            queryset = Article.objects.select_related('author').prefetch_related('tags')

            if tag_names:
                # 验证标签是否存在并构建筛选条件
                exist_tags = Tag.objects.filter(name__in=tag_names)
                existing_tag_names = set(tag.name.lower() for tag in exist_tags)
                invalid_tags = [name for name in tag_names if name not in existing_tag_names]

                if invalid_tags:
                    return Response({
                        'status': status.HTTP_400_BAD_REQUEST,
                        'message': f'无效标签: {", ".join(invalid_tags)}'
                    }, status=status.HTTP_400_BAD_REQUEST)

                # 构建AND条件的标签筛选
                for tag_name in tag_names:
                    queryset = queryset.filter(tags__name__iexact=tag_name)
                queryset = queryset.distinct()

            # 应用排序规则
            order_field = self.SORT_MAPPING[sort_type]
            queryset = queryset.order_by(order_field, '-id')  # 二级排序保证分页稳定

            # 分页处理
            paginator = Paginator(queryset, page_size)
            try:
                page_obj = paginator.page(page_index)
            except EmptyPage:
                return Response({
                    'status': status.HTTP_200_OK,
                    'message': '无更多数据',
                    'article_list': [],
                    'total_pages': paginator.num_pages,
                    'current_page': page_index
                }, status=status.HTTP_200_OK)

            # 构建响应数据
            article_list = []
            for article in page_obj:
                article_data = {
                    'article_id': article.id,
                    'article_title': article.article_title,
                    'author_name': article.author.username,
                    'author_profile_url': article.author.profile_url,
                    'star_count': article.stars,
                    'view_count': article.views,
                    'like_count': article.likes.count(),
                    'tags': [tag.name for tag in article.tags.all()],
                    'publish_time': article.publish_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'article_summary': article.article_summary,
                    'cover_link': article.cover_link,
                    'article_type': article.get_article_type_display()
                }
                article_list.append(article_data)

            return Response({
                'status': status.HTTP_200_OK,
                'message': '获取成功',
                'article_list': article_list,
                'total_pages': paginator.num_pages,
                'current_page': page_index
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.warning(f"参数格式错误: {str(e)}")
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': '参数格式错误'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"获取文章列表失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)