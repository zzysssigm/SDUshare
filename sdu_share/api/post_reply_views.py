# post_reply_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import models
from django.db.models import Count
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, F
from ..models import Article, Course, Post, Like, Tag, User, Reply
from django.core.paginator import Paginator, EmptyPage
import logging

logger = logging.getLogger(__name__)

from django.db import transaction

class ArticlePostCreateView(APIView):
    """创建文章关联帖子接口（增强校验版）"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            data = request.data
            required_fields = {'article_id', 'post_content'}
            
            # 参数存在性校验
            missing_fields = required_fields - data.keys()
            if missing_fields:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': f'缺少必要参数: {", ".join(missing_fields)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 参数类型校验
            try:
                article_id = int(data['article_id'])
            except (TypeError, ValueError):
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': 'article_id必须为整数'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 内容长度校验
            if len(data['post_content'].strip()) < 10:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '内容至少需要10个有效字符'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 验证文章存在性
            try:
                article = Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                return Response({
                    'status': status.HTTP_404_NOT_FOUND,
                    'message': '指定文章不存在'
                }, status=status.HTTP_404_NOT_FOUND)

            # 创建帖子
            post = Post.objects.create(
                post_title=data.get('post_title', '未命名帖子')[:255],  # 防止超长
                content=data['post_content'],
                poster=request.user,
                article=article
            )

            # 处理标签（带有效性校验）
            if tag_ids := data.get('tags'):
                try:
                    tag_ids = [int(tid) for tid in tag_ids]
                    valid_tags = Tag.objects.filter(id__in=tag_ids)
                    if len(valid_tags) != len(tag_ids):
                        invalid_ids = set(tag_ids) - set(valid_tags.values_list('id', flat=True))
                        logger.warning(f"无效标签ID: {invalid_ids}")
                    post.tags.set(valid_tags)
                except Exception as e:
                    logger.error(f"标签处理异常: {str(e)}")

            return Response({
                'status': status.HTTP_201_CREATED,
                'message': '创建成功',
                'post_id': post.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"创建失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CoursePostCreateView(APIView):
    """创建课程关联帖子接口（增强校验版）"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            data = request.data
            required_fields = {'course_id', 'post_content'}
            
            # 参数存在性校验
            missing_fields = required_fields - data.keys()
            if missing_fields:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': f'缺少必要参数: {", ".join(missing_fields)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 参数类型校验
            try:
                course_id = int(data['course_id'])
            except (TypeError, ValueError):
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': 'course_id必须为整数'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 内容长度校验
            if len(data['post_content'].strip()) < 10:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '内容至少需要10个有效字符'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 验证课程存在性
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return Response({
                    'status': status.HTTP_404_NOT_FOUND,
                    'message': '指定课程不存在'
                }, status=status.HTTP_404_NOT_FOUND)

            # 创建帖子
            post = Post.objects.create(
                post_title=data.get('post_title', '未命名提问')[:255],  # 防止超长
                content=data['post_content'],
                poster=request.user,
                course=course
            )

            return Response({
                'status': status.HTTP_201_CREATED,
                'message': '创建成功',
                'post_id': post.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"创建失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PostDetailView(APIView):
    """帖子详情接口（修复浏览量更新问题）"""
    def get(self, request):
        try:
            post_id = request.query_params.get('post_id')
            if not post_id:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '缺少post_id参数'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 缓存检查
            cache_key = f'post_detail:{post_id}'
            cached_data = cache.get(cache_key)
            if cached_data:
                # 即使命中缓存也更新浏览量
                Post.objects.filter(id=post_id).update(views=F('views') + 1)
                return Response(cached_data)

            # 先原子更新浏览量（确保后续查询包含新值）
            Post.objects.filter(id=post_id).update(views=F('views') + 1)

            # 获取最新数据（包含更新后的views）
            post = Post.objects.select_related('poster')\
                              .annotate(
                                  like_count=Count('likes'),
                                  annotated_reply_count=Count('replies')
                              ).get(id=post_id)

            # 点赞状态检查
            current_user = request.user if request.user.is_authenticated else None
            if_like = False
            if current_user:
                ct = ContentType.objects.get_for_model(Post)
                if_like = Like.objects.filter(
                    user=current_user,
                    content_type=ct,
                    object_id=post.id
                ).exists()

            # 构建最新响应数据
            response_data = {
                'status': status.HTTP_200_OK,
                'message': '获取成功',
                'post_detail': {
                    'post_id': post.id,
                    'post_title': post.post_title,
                    'post_content': post.content,
                    'poster_name': post.poster.username,
                    'poster_profile_url': post.poster.profile_url,
                    'view_count': post.views,  # 现在包含+1后的值
                    'like_count': post.like_count,
                    'reply_count': post.annotated_reply_count,
                    'publish_time': post.publish_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'if_like': if_like
                }
            }

            # 更新缓存（包含最新浏览量）
            cache.set(cache_key, response_data, 300)

            return Response(response_data, status=status.HTTP_200_OK)

        except Post.DoesNotExist:
            return Response({
                'status': status.HTTP_404_NOT_FOUND,
                'message': '帖子不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"获取帖子详情失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# （4）获取Post回复列表
class PostReplyListView(APIView):
    """分页获取Post回复列表接口"""
    
    def get(self, request):
        try:
            # 参数解析与校验
            post_id = request.query_params.get('post_id')
            page_index = int(request.query_params.get('page_index', 1))
            page_size = int(request.query_params.get('page_size', 20))

            # 参数检查
            if not post_id:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '缺少post_id参数'
                }, status=status.HTTP_400_BAD_REQUEST)

            if page_index < 1 or page_size < 1:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '分页参数必须大于0'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 验证帖子存在性
            try:
                Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                return Response({
                    'status': status.HTTP_404_NOT_FOUND,
                    'message': '帖子不存在'
                }, status=status.HTTP_404_NOT_FOUND)

            # 构建查询（包含点赞数统计）
            base_query = Reply.objects.filter(
                post_id=post_id
            ).select_related('replier').annotate(
                like_count=Count('likes')
            ).order_by('reply_time')

            # 分页处理
            paginator = Paginator(base_query, page_size)
            try:
                page_obj = paginator.page(page_index)
            except EmptyPage:
                return Response({
                    'status': status.HTTP_200_OK,
                    'message': '无更多数据',
                    'reply_list': [],
                    'total_pages': paginator.num_pages,
                    'current_page': page_index
                }, status=status.HTTP_200_OK)

            # 构建响应数据
            reply_list = [{
                'reply_id': reply.id,
                'reply_content': reply.reply_content,
                'replier_name': reply.replier.username,
                'replier_profile_url': reply.replier.profile_url,
                'like_count': reply.like_count,
                'publish_time': reply.reply_time.strftime('%Y-%m-%d %H:%M:%S')
            } for reply in page_obj]

            return Response({
                'status': status.HTTP_200_OK,
                'message': '获取成功',
                'reply_list': reply_list,
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
            logger.error(f"获取回复列表失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# （5）删除帖子
class PostDeleteView(APIView):
    """删除帖子接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            post_id = request.data.get('post_id')
            if not post_id:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '缺少post_id参数'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                post = Post.objects.get(id=post_id)
                
                # 权限验证：只有发帖人或管理员可以删除
                if request.user != post.poster and not request.user.master:
                    return Response({
                        'status': status.HTTP_403_FORBIDDEN,
                        'message': '无操作权限'
                    }, status=status.HTTP_403_FORBIDDEN)

                # 级联删除关联数据
                with transaction.atomic():
                    # 删除关联回复
                    Reply.objects.filter(post=post).delete()
                    # 删除帖子
                    post.delete()

                return Response({
                    'status': status.HTTP_200_OK,
                    'message': '删除成功'
                }, status=status.HTTP_200_OK)

            except Post.DoesNotExist:
                return Response({
                    'status': status.HTTP_404_NOT_FOUND,
                    'message': '帖子不存在'
                }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"删除帖子失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# （6）创建回复
class ReplyCreateView(APIView):
    """创建回复接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            post_id = request.data.get('post_id')
            content = request.data.get('reply_content')
            
            # 参数校验
            if not all([post_id, content]):
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '参数不完整'
                }, status=status.HTTP_400_BAD_REQUEST)

            if len(content.strip()) < 5:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '回复内容至少5个字符'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 验证帖子存在性
            try:
                post = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                return Response({
                    'status': status.HTTP_404_NOT_FOUND,
                    'message': '帖子不存在'
                }, status=status.HTTP_404_NOT_FOUND)

            # 创建回复
            new_reply = Reply.objects.create(
                post=post,
                reply_content=content,
                replier=request.user
            )

            return Response({
                'status': status.HTTP_201_CREATED,
                'message': '回复成功',
                'reply_id': new_reply.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"创建回复失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# （7）删除回复
class ReplyDeleteView(APIView):
    """删除回复接口"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            reply_id = request.data.get('reply_id')
            if not reply_id:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '缺少reply_id参数'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                reply = Reply.objects.select_related('replier').get(id=reply_id)
                
                # 权限验证：只有回复者或管理员可删除
                if request.user != reply.replier and not request.user.master:
                    return Response({
                        'status': status.HTTP_403_FORBIDDEN,
                        'message': '无操作权限'
                    }, status=status.HTTP_403_FORBIDDEN)

                # 原子操作删除关联点赞
                with transaction.atomic():
                    # 通过GenericRelation自动删除关联点赞
                    reply.likes.all().delete()
                    reply.delete()

                return Response({
                    'status': status.HTTP_200_OK,
                    'message': '删除成功'
                }, status=status.HTTP_200_OK)

            except Reply.DoesNotExist:
                return Response({
                    'status': status.HTTP_404_NOT_FOUND,
                    'message': '回复不存在'
                }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"删除回复失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# （8）获取回复详情
class ReplyDetailView(APIView):
    """获取回复详情接口"""
    
    def get(self, request):
        try:
            reply_id = request.query_params.get('reply_id')
            if not reply_id:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': '缺少reply_id参数'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 使用注解优化点赞数查询
            reply = Reply.objects.select_related('replier')\
                                .annotate(like_count=Count('likes'))\
                                .get(id=reply_id)

            response_data = {
                'reply_id': reply.id,
                'reply_content': reply.reply_content,
                'replier_name': reply.replier.username,
                'replier_profile_url': reply.replier.profile_url,
                'like_count': reply.like_count,
                'publish_time': reply.reply_time.strftime('%Y-%m-%d %H:%M:%S')
            }

            return Response({
                'status': status.HTTP_200_OK,
                'message': '获取成功',
                'reply_detail': response_data
            }, status=status.HTTP_200_OK)

        except Reply.DoesNotExist:
            return Response({
                'status': status.HTTP_404_NOT_FOUND,
                'message': '回复不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': '参数类型错误'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"获取回复详情失败: {str(e)}", exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)