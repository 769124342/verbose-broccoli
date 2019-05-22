import json

from django.shortcuts import render,redirect,reverse
from django.views import View
from django.contrib.auth import login,logout
# csrf装饰器
from django.views.decorators.csrf import ensure_csrf_cookie
# 类视图的装饰用装饰器
from django.utils.decorators import method_decorator

from users.models import User
from users.forms import RegisterForm,LoginForm
from utils.json_fun import to_json_data
from utils.res_code import Code,error_map
# Create your views here.


class Register(View):
    def get(self,request):
        return render (request, 'users/register.html')

    def post(self,request):
        # 获取ajax传参
        json_data=request.body
        if not json_data:
            return to_json_data(errmsg=Code.PARAMERR,error_map=error_map[Code.PARAMERR])
        dict_data=json.loads(json_data.decode('utf-8'))
        # 校验参数
        form = RegisterForm(data=dict_data)
        # 校验判断
        if form.is_valid():
            username=form.cleaned_data.get('username')
            password=form.cleaned_data.get('password')
            mobile=form.cleaned_data.get('mobile')

            user=User.objects.create_user(username=username,password=password,mobile=mobile)
            login(request,user)
            return to_json_data(errmsg='恭喜注册成功')
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data ().values ():
                err_msg_list.append (item[0].get ('message'))
            # print(item[0].get('message'))   # for test
            err_msg_str = '/'.join (err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data (errno=Code.PARAMERR, errmsg=err_msg_str)

class Login(View):
    # @method_decorator(ensure_csrf_cookie)
    def get(self,request):
        return render(request,'users/login.html')

    def post(self,request):
        # 获取前端参数
        json_data=request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR,errmsg=error_map[Code.PARAMERR])
        dict_data=json.loads(json_data.decode('utf-8')) # 转换成字典格式
        # 校验
        form = LoginForm(data=dict_data,request=request)
        if form.is_valid():
            return to_json_data (errmsg="恭喜您，登录成功！")
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data().values ():
                err_msg_list.append (item[0].get ('message'))
            err_msg_str = '/'.join (err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data (errno=Code.PARAMERR, errmsg=err_msg_str)

class Logout(View):

    def get(self,request):
        logout(request)
        return redirect(reverse('user:login'))