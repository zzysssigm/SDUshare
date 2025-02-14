from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal, InvalidOperation
from ..models import Course, Post, Reply, User

class BaseCourseAPIView(APIView):
    """基础响应处理类"""
    @staticmethod
    def success_response(message, course_id=None):
        data = {
            "status": status.HTTP_200_OK,
            "message": message
        }
        if course_id is not None:
            data["course_id"] = course_id
        return Response(data, status=data["status"])

    @staticmethod
    def error_response(status_code, message):
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