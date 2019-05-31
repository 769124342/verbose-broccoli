# 日志模块
import logging
import json
import random
import string

from django.shortcuts import render
from django.http import HttpResponse,JsonResponse
from django.views import View
from django_redis import get_redis_connection

from users.models import User

from utils.captcha.captcha import captcha
from .constants import IMAGE_CODE_REDIS_EXPIRES,SMS_CODE_NUMS,SMS_CODE_REDIS_EXPIRES,SMS_CODE_TEMP_ID,SEND_SMS_CODE_INTERVAL
from utils.json_fun import to_json_data
from utils.res_code import Code,error_map
from .forms import CheckImgCodeForm
from utils.yuntongxun.sms import CCP
from celery_tasks.sms import tasks as sms_tasks


# 导入日志器
logger=logging.getLogger('django')

# 图形验证码
class ImageCode(View):

    def get(self,request,image_code_id):
        # 生成图片验证码的方法，返回元组，里面包含文字和图片
        text,image=captcha.generate_captcha()
        # 连接redis数据库并且指定存储到什么位置
        con_redis=get_redis_connection(alias='verify_codes')
        # 字符串拼接加上uuid信息
        img_key='img_{}'.format(image_code_id)
        # redis存储命令：命名，时间和存储信息
        con_redis.setex(img_key,IMAGE_CODE_REDIS_EXPIRES,text)
        # 日志打印出文本信息
        logger.info('image.code:{}'.format(text))
        # 返回前端数据流指定格式
        return HttpResponse(content=image,content_type='image/jpg')

# 用户名判断
class CheckUsernameView(View):
    """
    /username/(?P<username>\w{4,20})/
    """
    def get(self,request,username):
        # 统计同一名字是否有多个用户
        count=User.objects.filter(username=username).count()
        data={
            'count':count,
            'username':username,
        }
        # 回传参数
        return to_json_data(data=data)

# 手机号判断
class CheckMobileView(View):
    """
    /mobile/(?P<mobile>1[3-9]\d{9})/
    """
    def get(self,request,mobile):
        # 统计手机号
        count=User.objects.filter(mobile=mobile).count()
        data = {
            'count': count,
            'mobile': mobile,
        }
        # 回传参数
        # return JsonResponse({'data':data})
        return to_json_data(data=data)

# 发送短信验证码
class SmsCodesView(View):
    """
    /sms_codes/
    """
    def post(self,request):

        # 1.获取前端参数
        json_data = request.body # byte  str
        if not json_data:
            return to_json_data(errno=Code.PARAMERR,errmsg=error_map[Code.PARAMERR])
        dict_data=json.loads(json_data.decode('utf8')) # 转换成字典格式

        # 2.验证参数
        form = CheckImgCodeForm(data=dict_data)
        if form.is_valid():
            # 3.保存短信验证码
            mobile = form.cleaned_data.get('mobile') # 获取手机号
            # sms_num = ''
            # for i in range(6):
            #     sms_num += random.choice(string.digits)
            # sms_num=''.join([random.choice(string.digits) for _ in range(SMS_CODE_NUMS)]) # 生成随机验证码

            sms_num='%06d'% random.randint(0,999999) # 生成随机验证码

            con_redis=get_redis_connection(alias='verify_codes') # 连接存储redis数据库

            pl=con_redis.pipeline() # redis管道

            sms_text_fmt = 'sms_{}'.format(mobile) # 验证码的键
            sms_flag_fmt = 'sms_flag_{}'.format(mobile) #发送标记

            try:
                pl.setex(sms_flag_fmt,SEND_SMS_CODE_INTERVAL,1) # 短信验证码发送间隔
                pl.setex(sms_text_fmt,SMS_CODE_REDIS_EXPIRES,sms_num) # 验证码有效期
                # 让管道通知redis执行命令
                pl.execute ()
            except Exception as e:
                logger.debug('redis执行异常{}'.format(e))
                return to_json_data(errno=Code.UNKOWNERR,errmsg=error_map[Code.UNKOWNERR])
            logger.info ("Sms code: {}".format (sms_num))

            # 4.发送短信验证码
            # logger.info('发送短信验证码[正常][mobile:%s sms_code:%s]'%(mobile,sms_num))
            # return to_json_data(errmsg=Code.OK,error_map='短信验证码发送成功')

            expires = SMS_CODE_REDIS_EXPIRES
            sms_tasks.send_sms_code.delay (mobile, sms_num, expires, SMS_CODE_TEMP_ID)
            return to_json_data (errno=Code.OK, errmsg="短信验证码发送成功")

            # try:
            #     # 云通讯发送短信验证码（手机号，短信验证码，验证码有效期，短信模板）
            #     result = CCP ().send_template_sms (mobile,[sms_num,SMS_CODE_REDIS_EXPIRES],SMS_CODE_TEMP_ID)
            # except Exception as e:
            #     logger.error ("发送验证码短信[异常][ mobile: %s, message: %s ]" % (mobile, e))
            #     return to_json_data (errno=Code.SMSERROR, errmsg=error_map[Code.SMSERROR])
            # else:
            #     if result == 0:
            #         logger.info ("发送验证码短信[正常][ mobile: %s sms_code: %s]" % (mobile, sms_num))
            #         return to_json_data (errno=Code.OK, errmsg="短信验证码发送成功")
            #     else:
            #         logger.warning ("发送验证码短信[失败][ mobile: %s ]" % mobile)
            #         return to_json_data (errno=Code.SMSFAIL, errmsg=error_map[Code.SMSFAIL])
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data ().values ():
                err_msg_list.append (item[0].get ('message'))
            # print(item[0].get('message'))   # for test
            err_msg_str = '/'.join (err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data (errno=Code.PARAMERR, errmsg=err_msg_str)
        # 5.返回前端