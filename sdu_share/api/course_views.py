from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal, InvalidOperation
from ..models import Course, Post, Reply, User

class BaseCourseAPIView(APIView):
    """统一响应基类（关键修复）"""
    
    def success_response(self, message, status_code=200, **kwargs):
        """成功响应方法"""
        response_data = {
            "status": status_code,
            "message": message
        }
        response_data.update(kwargs)
        return Response(response_data, status=status_code)

    def error_response(self, status_code, message):
        """错误响应方法"""
        return Response({
            "status": status_code,
            "message": message
        }, status=status_code)

class CourseCreateView(BaseCourseAPIView):
    """课程创建接口（严格响应格式版）"""
    
    def post(self, request):
        try:
            with transaction.atomic():
                # 参数预处理
                course_data = {
                    'course_name': (request.data.get('course_name') or '').strip(),
                    'course_type': request.data.get('course_type'),
                    'college': f"{request.data.get('campus', '').strip()}｜{request.data.get('college', '').strip()}",
                    'course_teacher': (request.data.get('course_teacher') or '').strip(),
                    'course_method': request.data.get('course_method'),
                    'assessment_method': (request.data.get('assessment_method') or '').strip()
                }

                # 必填字段验证
                required_map = {
                    'course_name': "课程名称不能为空",
                    'course_type': "课程类型不能为空",
                    'college': "学院信息不能为空",
                    'course_teacher': "授课教师不能为空",
                    'course_method': "教学方式不能为空",
                    'assessment_method': "考核方式不能为空"
                }
                
                missing = [key for key, msg in required_map.items() if not course_data[key]]
                if missing:
                    return self.error_response(
                        status.HTTP_400_BAD_REQUEST,
                        required_map[missing[0]]
                    )

                # 处理学分字段
                try:
                    raw_credits = request.data.get('credits')
                    if isinstance(raw_credits, list):
                        raw_credits = raw_credits[0]
                        
                    credits = Decimal(str(raw_credits).strip(' "\''))
                    if not (Decimal('0.01') <= credits <= Decimal('99.99')):
                        raise ValidationError("学分必须在0.01到99.99之间")
                    course_data['credits'] = credits
                except (TypeError, InvalidOperation, ValidationError) as e:
                    return self.error_response(
                        status.HTTP_400_BAD_REQUEST,
                        f"学分错误：{str(e)}"
                    )

                # 验证枚举类型
                if course_data['course_type'] not in dict(Course.COURSE_TYPE_CHOICES):
                    valid_types = ', '.join(dict(Course.COURSE_TYPE_CHOICES).keys())
                    return self.error_response(
                        status.HTTP_400_BAD_REQUEST,
                        f"无效课程类型，可选：{valid_types}"
                    )

                if course_data['course_method'] not in dict(Course.COURSE_METHOD_CHOICES):
                    valid_methods = ', '.join(dict(Course.COURSE_METHOD_CHOICES).keys())
                    return self.error_response(
                        status.HTTP_400_BAD_REQUEST,
                        f"无效教学方式，可选：{valid_methods}"
                    )

                # 创建课程
                course = Course.objects.create(
                    course_name=course_data['course_name'][:255],
                    course_type=course_data['course_type'],
                    college=course_data['college'][:255],
                    credits=course_data['credits'],
                    course_teacher=course_data['course_teacher'][:255],
                    course_method=course_data['course_method'],
                    assessment_method=course_data['assessment_method']
                )

                return self.success_response(
                    "课程创建成功",
                    course_id=course.id
                )

        except Exception as e:
            return self.error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "服务器内部错误"
            )

class CourseEditView(BaseCourseAPIView):
    """课程编辑接口"""
    
    def post(self, request):
        try:
            course_id = request.data.get('id')
            if not course_id:
                return self.error_response(
                    status.HTTP_400_BAD_REQUEST,
                    "缺少课程ID参数"
                )

            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return self.error_response(
                    status.HTTP_404_NOT_FOUND,
                    "课程不存在"
                )

            # 可更新字段列表
            update_fields = {}
            field_validators = {
                'course_name': lambda v: v.strip()[:255],
                'course_type': lambda v: v if v in dict(Course.COURSE_TYPE_CHOICES) else None,
                'college': lambda v: v.strip()[:255],
                'credits': lambda v: Decimal(v) if Decimal(v) >= 0 else None,
                'course_teacher': lambda v: v.strip()[:255],
                'course_method': lambda v: v if v in dict(Course.COURSE_METHOD_CHOICES) else None,
                'assessment_method': lambda v: v.strip()
            }

            for field in field_validators:
                if field in request.data:
                    try:
                        processed = field_validators[field](request.data[field])
                        if processed is not None:
                            update_fields[field] = processed
                        else:
                            return self.error_response(
                                status.HTTP_400_BAD_REQUEST,
                                f"字段 {field} 值不合法"
                            )
                    except Exception as e:
                        return self.error_response(
                            status.HTTP_400_BAD_REQUEST,
                            f"字段 {field} 格式错误：{str(e)}"
                        )

            if not update_fields:
                return self.error_response(
                    status.HTTP_400_BAD_REQUEST,
                    "没有提供有效修改字段"
                )

            # 执行更新
            for key, value in update_fields.items():
                setattr(course, key, value)
            course.save()

            return self.success_response("课程更新成功")

        except Exception as e:
            return self.error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "服务器内部错误"
            )

class CourseDeleteView(BaseCourseAPIView):
    """课程删除接口"""
    
    def post(self, request):
        try:
            course_id = request.data.get('course_id')
            if not course_id:
                return self.error_response(
                    status.HTTP_400_BAD_REQUEST,
                    "缺少课程ID参数"
                )

            try:
                course = Course.objects.get(id=course_id)
                course.delete()
                return self.success_response("课程删除成功")
            except Course.DoesNotExist:
                return self.error_response(
                    status.HTTP_404_NOT_FOUND,
                    "课程不存在"
                )

        except Exception as e:
            return self.error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "服务器内部错误"
            )
        
# course_views.py
from decimal import Decimal, InvalidOperation
from django.db import transaction
from ..models import Course, CourseReview
from django.core.exceptions import ObjectDoesNotExist

class CourseRateView(BaseCourseAPIView):  # 直接继承BaseCourseAPIView
    """课程评分接口（完整修复版）"""
    
    def post(self, request):
        try:
            with transaction.atomic():
                # 校验必填参数
                course_id = request.data.get('course_id')
                if not course_id:
                    return self.error_response(400, "缺少课程ID参数")

                # 获取课程实例
                try:
                    course = Course.objects.get(id=course_id)
                except Course.DoesNotExist:
                    return self.error_response(404, "课程不存在")

                # 处理评分参数
                try:
                    raw_score = request.data['score']
                    # 转换为Decimal并保留两位小数
                    score = Decimal(str(raw_score)).quantize(Decimal('0.00'))
                    if not (Decimal('1.00') <= score <= Decimal('5.00')):
                        raise ValueError("评分超出范围")
                except (KeyError, ValueError, InvalidOperation) as e:
                    return self.error_response(400, f"评分错误: {str(e)}")

                # 防止重复评价
                if CourseReview.objects.filter(user=request.user, course=course).exists():
                    return self.error_response(400, "您已评价过该课程")

                # 创建评价记录
                review = CourseReview.objects.create(
                    user=request.user,
                    course=course,
                    score=score,
                    comment=str(request.data.get('comment', '')).strip()[:2000]
                )

                # 正确调用响应方法
                return self.success_response(
                    message="评价提交成功",
                    status_code=status.HTTP_201_CREATED,
                    review_id=review.id,
                    score=float(review.score),
                    comment=review.comment
                )

        except Exception as e:
            return self.error_response(500, f"服务器内部错误: {str(e)}")

class CourseEditRatingView(BaseCourseAPIView):
    """课程评分编辑接口（完整版）"""
    
    def post(self, request):
        try:
            # 获取必要参数
            course_id = request.data.get('course_id')
            if not course_id:
                return self.error_response(400, "缺少课程ID参数")

            # 获取评价记录
            try:
                review = CourseReview.objects.get(
                    user=request.user,
                    course_id=course_id
                )
            except CourseReview.DoesNotExist:
                return self.error_response(404, "尚未对该课程评分")

            update_data = {}
            
            # 处理评分更新
            if 'score' in request.data:
                try:
                    raw_score = request.data['score']
                    new_score = Decimal(str(raw_score)).quantize(Decimal('0.00'))
                    if not (1 <= new_score <= 5):
                        raise ValueError("评分超出有效范围")
                    update_data['score'] = new_score
                except (ValueError, InvalidOperation) as e:
                    return self.error_response(400, f"评分错误: {str(e)}")

            # 处理评论更新
            if 'comment' in request.data:
                cleaned_comment = str(request.data['comment']).strip()
                update_data['comment'] = cleaned_comment[:2000]

            # 执行更新
            if update_data:
                for key, value in update_data.items():
                    setattr(review, key, value)
                review.save()
                return self.success_response(
                    "评价更新成功",
                    score=float(review.score),
                    comment=review.comment
                )
            else:
                return self.error_response(400, "未提供有效更新字段")

        except Exception as e:
            return self.error_response(500, f"服务器内部错误: {str(e)}")
        

class UserEvaluationView(BaseCourseAPIView):
    """用户评价查询接口（完整版）"""
    
    def post(self, request):
        try:
            # 参数校验
            user_id = request.data.get('user_id')
            course_id = request.data.get('course_id')
            if not all([user_id, course_id]):
                return self.error_response(400, "缺少用户ID或课程ID")

            # 权限验证
            if int(user_id) != request.user.id:
                return self.error_response(401, "无权查看他人评价")

            # 查询评价
            try:
                review = CourseReview.objects.get(
                    user_id=user_id,
                    course_id=course_id
                )
                return self.success_response(
                    "查询成功",
                    score=float(review.score),
                    comment=review.comment
                )
            except CourseReview.DoesNotExist:
                return self.error_response(404, "未找到评价记录")

        except ValueError:
            return self.error_response(400, "用户ID格式错误")
        except Exception as e:
            return self.error_response(500, f"服务器错误: {str(e)}")
        
from django.db.models import Avg, Count
from django.core.paginator import Paginator, EmptyPage

class CourseDetailView(BaseCourseAPIView):
    """课程详情接口（修复字段冲突版）"""
    
    def get(self, request):
        try:
            course_id = request.GET.get('course_id')
            if not course_id:
                return self.error_response(400, "缺少课程ID参数")

            try:
                # 修改annotate字段名称避免冲突
                course = Course.objects.prefetch_related('relative_articles') \
                    .annotate(
                        calculated_avg=Avg('reviews__score'),
                        review_count=Count('reviews')
                    ).get(id=course_id)
            except Course.DoesNotExist:
                return self.error_response(404, "课程不存在")

            # 处理校区信息
            campus, college = (course.college.split('｜') 
                              if '｜' in course.college 
                              else ('', course.college))

            # 构建响应数据
            detail_data = {
                "course_id": course.id,
                "course_name": course.course_name,
                "course_type": course.get_course_type_display(),
                "college": college,
                "campus": campus,
                "credits": float(course.credits),
                "course_teacher": course.course_teacher,
                "course_method": course.get_course_method_display(),
                "assessment_method": course.assessment_method,
                "score": float(course.calculated_avg) if course.calculated_avg else 0.0,
                "all_score": float(course.calculated_avg * course.review_count) if course.calculated_avg else 0.0,
                "all_people": course.review_count,
                "relative_articles": [
                    {"article_id": art.id, "title": art.title[:50]}
                    for art in course.relative_articles.all()
                ],
                "publish_time": course.publish_time.strftime("%Y-%m-%d %H:%M:%S")
            }

            return self.success_response(
                "获取详情成功",
                course_detail=detail_data
            )

        except ValueError:
            return self.error_response(400, "课程ID格式错误")
        except Exception as e:
            return self.error_response(500, f"服务器错误: {str(e)}")
        
class CourseListView(BaseCourseAPIView):
    """课程分页列表接口（修复字段冲突版）"""
    
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    def get(self, request):
        try:
            # 解析分页参数
            page_index = int(request.GET.get('page_index', 1))
            page_size = int(request.GET.get('page_size', self.DEFAULT_PAGE_SIZE))

            # 参数有效性验证
            if page_index < 1 or page_size < 1:
                raise ValueError()
            page_size = min(page_size, self.MAX_PAGE_SIZE)

            # 修改annotate字段名称
            queryset = Course.objects.annotate(
                calculated_avg=Avg('reviews__score'),
                review_count=Count('reviews')
            ).order_by('-publish_time')

            paginator = Paginator(queryset, page_size)
            
            try:
                page = paginator.page(page_index)
            except EmptyPage:
                return self.error_response(400, "页码超出范围")

            # 构建响应数据
            course_list = []
            for course in page.object_list:
                campus, college = (course.college.split('｜') 
                                  if '｜' in course.college 
                                  else ('', course.college))
                
                course_list.append({
                    "course_id": course.id,
                    "course_name": course.course_name[:50],
                    "course_type": course.get_course_type_display(),
                    "college": college,
                    "credits": float(course.credits),
                    "course_teacher": course.course_teacher[:20],
                    "course_method": course.get_course_method_display(),
                    "assessment_method": course.assessment_method[:100],
                    "score": float(course.calculated_avg) if course.calculated_avg else 0.0,
                    "all_score": float(course.calculated_avg * course.review_count) if course.calculated_avg else 0.0,
                    "all_people": course.review_count,
                    "publish_time": course.publish_time.strftime("%Y-%m-%d")
                })

            return self.success_response(
                "获取列表成功",
                course_list=course_list,
                total_pages=paginator.num_pages,
                current_page=page.number,
                total_items=paginator.count
            )

        except ValueError:
            return self.error_response(400, "分页参数格式错误")
        except Exception as e:
            return self.error_response(500, f"服务器错误: {str(e)}")
        
class CourseListView(BaseCourseAPIView):
    """课程分页列表接口（修复annotate字段冲突）"""
    
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    def get(self, request):
        try:
            # 解析分页参数
            page_index = int(request.GET.get('page_index', 1))
            page_size = int(request.GET.get('page_size', self.DEFAULT_PAGE_SIZE))

            # 验证参数有效性
            if page_index < 1 or page_size < 1:
                raise ValueError()
            page_size = min(page_size, self.MAX_PAGE_SIZE)

            # 修改annotate字段名称避免与模型属性冲突
            queryset = Course.objects.annotate(
                calculated_avg=Avg('reviews__score'),
                review_count=Count('reviews')
            ).order_by('-publish_time')

            paginator = Paginator(queryset, page_size)
            
            try:
                page = paginator.page(page_index)
            except EmptyPage:
                return self.error_response(400, "页码超出范围")

            # 构建列表数据
            course_list = []
            for course in page.object_list:
                # 使用模型自身的属性方法
                campus, college = course.college.split('｜') if '｜' in course.college else ('', course.college)
                
                course_list.append({
                    "course_id": course.id,
                    "course_name": course.course_name[:50],
                    "course_type": course.get_course_type_display(),
                    "college": college,
                    "credits": float(course.credits),
                    "course_teacher": course.course_teacher[:20],
                    "course_method": course.get_course_method_display(),
                    "assessment_method": course.assessment_method[:100],
                    # 使用模型属性替代annotate字段
                    "score": float(course.average_score),
                    "all_score": float(course.average_score * course.total_reviews),
                    "all_people": course.total_reviews,
                    "publish_time": course.publish_time.strftime("%Y-%m-%d")
                })

            return self.success_response(
                "获取列表成功",
                course_list=course_list,
                total_pages=paginator.num_pages,
                current_page=page.number,
                total_items=paginator.count
            )

        except ValueError:
            return self.error_response(400, "分页参数格式错误")
        except Exception as e:
            return self.error_response(500, f"服务器错误: {str(e)}")