from django import forms
from users.models import User
# redis数据库连接
from django_redis import get_redis_connection
# 正则校验器
from django.core.validators import RegexValidator

# 创建手机号正则校验器
mobile_validator=RegexValidator(r'1[3-9]\d{9}$','手机号格式不正确')
# form表单验证信息
class CheckImgCodeForm(forms.Form):
    mobile = forms.CharField (max_length=11, min_length=11, validators=[mobile_validator, ],
                              error_messages={
                                  "min_length": "手机号长度有误",
                                  "max_length": "手机号长度有误",
                                  "required": "手机号不能为空"
                              })
    image_code_id = forms.UUIDField (
        error_messages={
            "required": "图片UUID不能为空"
        })
    text = forms.CharField (max_length=4, min_length=4,
                            error_messages={
                                "min_length": "图片验证码长度有误",
                                "max_length": "图片验证码长度有误",
                                "required": "图片验证码不能为空"
                            })
    # 验证字段
    def clean(self):
        clean_data = super().clean()
        mobile_num = clean_data.get('mobile')
        image_text = clean_data.get('text') # 用户输入的图形验证码
        image_uuid = clean_data.get('image_code_id')

        # 判断并发送错误信息
        if User.objects.filter(mobile=mobile_num):
            raise forms.ValidationError('手机号以及注册')
        # 链接数据库
        con_redis = get_redis_connection(alias='verify_codes')
        img_key = 'img_{}'.format(image_uuid)
        real_image_code_origin = con_redis.get(img_key) # redis取出的值是bytes
        # if real_image_code_origin:
        #     real_image_code=real_image_code_origin.decode('utf8')
        # else:
        #     real_image_code=None
        real_image_code= real_image_code_origin.decode('utf8') if real_image_code_origin else None # 数据库取出的图形验证码
        # con_redis.delete(img_key)

        if (not real_image_code) or (image_text != real_image_code):
            raise forms.ValidationError('验证码错误')

        # 60秒内不能重新发送
        # 构建并从redis数据库中拿到
        sms_flag_fmt = 'sms_flag_{}'.format (mobile_num)
        sms_flg=con_redis.get(sms_flag_fmt)
        if sms_flg:
            raise forms.ValidationError('获取手机短信验证码过于频繁')