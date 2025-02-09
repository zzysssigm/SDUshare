import re
import random
from django.conf import settings
from django.core.mail import send_mail

# 验证码有效期（秒）
CODE_EXPIRE_TIME = 600
# 发送间隔（秒）
SEND_INTERVAL = 60

def generate_code():
    """生成6位数字验证码"""
    return str(random.randint(100000, 999999))

def is_valid_sdu_email(email):
    """验证山大邮箱格式"""
    pattern = r'^[\w\.-]+@mail\.sdu\.edu\.cn$'  # 根据实际邮箱格式调整
    return re.match(pattern, email) is not None

def send_code_email(email, code, purpose="注册"):
    """发送验证码邮件"""
    subject = f'【SDU SHARE】{purpose}验证码'
    message = f'您的验证码为：{code}，有效期10分钟。请勿泄露给他人。'
    print(message)
    from_email = settings.EMAIL_HOST_USER
    
    try:
        send_mail(subject, message, from_email, [email])
        return True
    except Exception as e:
        print(f"邮件发送失败：{e}")
        return False