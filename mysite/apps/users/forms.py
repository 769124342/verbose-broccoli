import re

from django import forms
from django_redis import get_redis_connection
from django.db.models import Q
from django.contrib.auth import login

from verifications.constants import SMS_CODE_NUMS
from .constants import USER_SESSION_EXPIRES
from .models import User


# 注册的form验证
class RegisterForm(forms.Form):
    """
    """
    username = forms.CharField(label='用户名', max_length=20, min_length=4,
                               error_messages={"min_length": "用户名长度要大于4", "max_length": "用户名长度要小于20",
                                               "required": "用户名不能为空"}
                               )
    password = forms.CharField(label='密码', max_length=20, min_length=6,
                               error_messages={"min_length": "密码长度要大于6", "max_length": "密码长度要小于20",
                                               "required": "密码不能为空"}
                               )
    password_repeat = forms.CharField(label='确认密码', max_length=20, min_length=6,
                                      error_messages={"min_length": "密码长度要大于6", "max_length": "密码长度要小于20",
                                                      "required": "密码不能为空"}
                                      )
    mobile = forms.CharField(label='手机号', max_length=11, min_length=11,
                             error_messages={"min_length": "手机号长度有误", "max_length": "手机号长度有误",
                                             "required": "手机号不能为空"})

    sms_code = forms.CharField(label='短信验证码', max_length=SMS_CODE_NUMS, min_length=SMS_CODE_NUMS,
                               error_messages={"min_length": "短信验证码长度有误", "max_length": "短信验证码长度有误",
                                               "required": "短信验证码不能为空"})

    def clean_mobile(self):
        """
        单项验证
        """
        # 获取参数
        tel = self.cleaned_data.get('mobile')
        if not re.match(r"^1[3-9]\d{9}$", tel):
            raise forms.ValidationError("手机号码格式不正确")

        if User.objects.filter(mobile=tel).exists():
            raise forms.ValidationError("手机号已注册，请重新输入！")

        return tel

    def clean(self):
        """
        多项验证
        """
        # 继承父类
        cleaned_data = super().clean()
        username=cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('用户名已注册，请重新输入')

        passwd = cleaned_data.get('password')
        passwd_repeat = cleaned_data.get('password_repeat')

        if passwd != passwd_repeat:
            # 两次
            raise forms.ValidationError("两次密码不一致")

        # 用户输入的电话和短信验证码
        tel = cleaned_data.get('mobile')
        sms_text = cleaned_data.get('sms_code')

        # 建立redis连接
        redis_conn = get_redis_connection(alias='verify_codes')
        # 构建短信验证码的键
        sms_fmt = "sms_{}".format(tel)
        # 获取redis数据库中的短信验证码（数据库中的是bytes类型）
        real_sms = redis_conn.get(sms_fmt)

        # 判断是否有短信验证码，判断短信验证码是否一致
        if (not real_sms) or (sms_text != real_sms.decode('utf-8')):
            raise forms.ValidationError("短信验证码错误")

# 登录的form验证
class LoginForm(forms.Form):
    user_account = forms.CharField()
    password = forms.CharField (label='密码', max_length=20, min_length=6,error_messages={
        "min_length": "密码长度要大于6",
        "max_length": "密码长度要小于20",
        "required": "密码不能为空",
    })
    remember_me = forms.BooleanField (required=False)

    # 增加属性(继承重写)
    def __init__(self,*args,**kwargs):
        self.request = kwargs.pop('request',None)
        super(LoginForm,self).__init__(*args,**kwargs)

    def clean_user_account(self):
        user_info=self.cleaned_data.get('user_account')
        if not user_info:
            raise forms.ValidationError('用户账号不能为空')
        if (not re.match (r"^1[3-9]\d{9}$", user_info)) and (len(user_info)<4 or len(user_info)>20):
            raise  forms.ValidationError('输入账号格式不正确')
        return user_info

    def clean(self):
        cleaned_data=super().clean()
        # 获取前端信息
        user_info=cleaned_data.get('user_account')
        passwd=cleaned_data.get('password')
        hold_login=cleaned_data.get('remember_me')
        # 数据库查询（用户名或手机号查询）
        user_queryset = User.objects.filter(Q(username=user_info)|Q(mobile=user_info))
        if user_queryset:
            user=user_queryset.first()
            if user.check_password(passwd):
                # 设置session过期时间
                # 用户没有点记住，关闭浏览器过期
                if not hold_login:
                    self.request.session.set_expiry(1)
                else:
                    # 用户点击了记住，设置session过期时间
                    self.request.session.set_expiry(USER_SESSION_EXPIRES)
                    # 登录操作
                    # request.session['username']=username
                login (self.request, user)
            else:
                raise forms.ValidationError ("密码不正确，请重新输入")

        else:
            raise forms.ValidationError ("用户账号不存在，请重新输入")