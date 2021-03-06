import json
import logging
from datetime import datetime
from urllib.parse import urlencode

import qiniu

# 类装饰器
from django.utils.decorators import method_decorator
# 取消当前csrf验证
from django.views.decorators.csrf import csrf_exempt

# 类权限
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin,PermissionRequiredMixin
from django.contrib.auth.models import Group,Permission
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Count
from django.http import JsonResponse, Http404
from django.shortcuts import render,redirect
from django.views import View

from users.models import User
from dj_web import settings
from news import models
from doc.models import Doc
from course.models import Course,Teacher,CourseCategory

from utils import paginator_script
from utils.fastdfs.fdfs import FDFS_Client
from utils.json_fun import to_json_data
from utils.res_code import Code, error_map
from utils.secrets import qiniu_secret_info
from .constants import SHOW_HOTNEWS_COUNT, PER_PAGE_NEWS_COUNT,SHOW_BANNER_COUNT
from admin.forms import NewsPubForm, DocsPubForm, CoursesPubForm

logger=logging.getLogger('django')

class IndexView(LoginRequiredMixin,View):
    """ create admin index view"""
    # 如果没登录跳转页面
    # login_url = 'user:login'
    # 登录了后跳转页面
    redirect_field_name = 'next'

    def get(self,request):
        if request.user in User.objects.filter(is_staff=True):
            return render(request,'admin/index/index.html')
        return render(request,'403.html')


class TagManageView(PermissionRequiredMixin,View):
    """
    route: /admin/tags/
    """
    # 添加权限
    permission_required = ('news.add_tag', 'news.view_tag')
    # 没有权限就默认报错
    raise_exception = True
    # 如果没有权限判断是什么请求抛出的异常
    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (TagManageView, self).handle_no_permission ()

    def get(self,request):
        # annotate分组查询,values指定输出字典格式,Count统计数量
        tags = models.Tag.objects.values('id','name').annotate(num_news = Count('news__tag_id')).filter(is_delete=False).\
            order_by('-num_news','update_time')
        return render(request,'admin/news/tag_manage.html',locals())

    def post(self,request):
        """"""
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 将json转化为dict
        dict_data = json.loads(json_data.decode('utf8'))
        tag_name = dict_data.get('name')
        if tag_name:
            tag_name = tag_name.strip()
            tag_tuple = models.Tag.objects.get_or_create(name=tag_name,is_delete=False)
            tag_instance, tag_boolean = tag_tuple
            if tag_boolean:
                news_tag_dict = {
                    'id':tag_instance.id,
                    'name':tag_instance.name
                }
                return to_json_data(errmsg='标签创建成功',data=news_tag_dict)
            else:
                return to_json_data (errno=Code.DATAEXIST, errmsg='标签名已存在!')
        else:
            return to_json_data(errno=Code.PARAMERR,errmsg='标签名为空!')


class TagEditView(PermissionRequiredMixin,View):
    """
    /admin/tags/<int:tag_id>/
    """
    permission_required = ('news.delete_tag', 'news.change_tag')
    raise_exception = True

    def handle_no_permission(self):
        return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')

    def delete(self,request,tag_id):
        tag = models.Tag.objects.only('id').filter(id=tag_id).first()
        if tag:
            tag.is_delete = True
            tag.save(update_fields=['is_delete'])
            return to_json_data(errmsg='标签删除成功!')
        else:
            return to_json_data(errno=Code.PARAMERR,errmsg="需要删除的标签不存在")

    def put(self,request,tag_id):
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 将json转化为dict
        dict_data = json.loads(json_data.decode('utf8'))

        tag_name = dict_data.get('name')
        tag = models.Tag.objects.only('name').filter(id=tag_id).first()
        if tag:
            if tag_name:
                tag_name = tag_name.strip()
                if not models.Tag.objects.only('id').filter(name=tag_name).exists():
                    tag.name = tag_name
                    tag.save(update_fields=['name','update_time'])
                    return to_json_data(errmsg='标签更新成功!')
                else:
                    return to_json_data(errno=Code.PARAMERR, errmsg='标签名未修改!')
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg='需要更新的标签不存在!')


class HotNewsManageView(PermissionRequiredMixin,View):

    permission_required = ('news.view_hotnews')
    raise_exception = True

    def get(self,request):
        #
        hot_news = models.HotNews.objects.select_related('news__tag').\
            only('news__title','news__tag__name','priority','news_id').filter(is_delete=False).\
            order_by('priority','-news__clicks')[:SHOW_HOTNEWS_COUNT]
        return render(request,'admin/news/news_hot.html',locals())


class HotNewsEditView(PermissionRequiredMixin,View):
    """"""
    permission_required = ('news.delete_hotnews', 'news.change_hotnews')
    raise_exception = True

    def handle_no_permission(self):
        return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')

    def delete(self,request,hotnews_id):
        hotnews= models.HotNews.objects.only('id').filter(id=hotnews_id).first()
        if hotnews:
            hotnews.is_delete = True
            hotnews.save(update_fields = ['is_delete'])
            return to_json_data(errmsg='热门文章删除成功!')
        else:
            return to_json_data(errno=Code.PARAMERR,errmsg='需要删除的热门文章不存在!')
    # 编辑
    def put(self,request,hotnews_id):
        json_data=request.body
        if not json_data:
            return to_json_data (errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads (json_data.decode ('utf8'))
        try:
            # 指定前端传参
            priority = int (dict_data.get ('priority'))
            # 列表生成式取值
            priority_list = [i for i, _ in models.HotNews.PRI_CHOICES]
            if priority not in priority_list:
                return to_json_data (errno=Code.PARAMERR, errmsg='热门文章优先级设置错误!')
        except Exception as e:
            logger.info ('热门文章优先级异常:\n{}'.format (e))
            return to_json_data (errno=Code.PARAMERR, errmsg='热门文章优先级设置错误!')

        hotnews = models.HotNews.objects.only ('id').filter (id=hotnews_id).first ()
        if not hotnews:
            return to_json_data (errno=Code.PARAMERR, errmsg='热门新闻不存在!')
        if hotnews.priority == priority:
            return to_json_data (errno=Code.PARAMERR, errmsg='热门文章的优先级未改变!!')
        hotnews.priority = priority
        hotnews.save (update_fields=['priority'])
        return to_json_data (errmsg='热门文章更新成功!')


class HotNewsAddView(PermissionRequiredMixin,View):

    permission_required = ('news.view_hotnews','news.add_hotnews')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (HotNewsAddView, self).handle_no_permission ()

    def get(self,request):
        tags = models.Tag.objects.values ('id', 'name').annotate (num_news=Count ('news')).filter (is_delete=False). \
            order_by ('-num_news', 'update_time')
        priority_dict = dict(models.HotNews.PRI_CHOICES)
        return render(request,'admin/news/news_hot_add.html',locals())

    def post(self,request):
        json_data = request.body
        if not json_data:
            return to_json_data (errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 将json转化为dict
        dict_data = json.loads (json_data.decode ('utf8'))
        try:
            news_id = int (dict_data.get ('news_id'))
        except Exception as e:
            logger.info ('热门文章:\n{}'.format (e))
            return to_json_data (errno=Code.PARAMERR, errmsg='参数错误')
        if not models.News.objects.filter(id=news_id):
            return to_json_data (errno=Code.PARAMERR, errmsg='文章不存在')
        try:
            priority = int (dict_data.get ('priority'))
            # 列表生成式
            priority_list = [i for i, _ in models.HotNews.PRI_CHOICES]
            if priority not in priority_list:
                return to_json_data (errno=Code.PARAMERR, errmsg='热门文章的优先级设置错误')
        except Exception as e:
            logger.info ('热门文章优先级异常：\n{}'.format (e))
            return to_json_data (errno=Code.PARAMERR, errmsg='热门文章的优先级设置错误')

        # 创建热门新闻
        hotnews_tuple = models.HotNews.objects.get_or_create (news_id=news_id)
        hotnews, is_created = hotnews_tuple
        hotnews.priority = priority  # 修改优先级
        hotnews.save (update_fields=['priority'])
        return to_json_data (errmsg="热门文章创建成功")


# 根据对应id显示数据
class NewsByTagIdView(PermissionRequiredMixin,View):

    permission_required = ('news.view_news')
    raise_exception = True

    def handle_no_permission(self):
        return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')

    def get(self,request,tag_id):
        news = models.News.objects.values ('id', 'title').filter (is_delete=False, tag_id=tag_id)
        news_list = [i for i in news]
        return to_json_data(data={
            'news':news_list
        })


class NewsManageView(PermissionRequiredMixin,View):
    """
    请求方式：get
    携带的参数：?start_time&end_time&title&author_name&tag_id
    返回的参数：title author_username tag_name update_time id
    """
    permission_required = ('news.view_news')
    raise_exception = True

    def get(self,request):
        # 没有传参时返回的信息
        tag=models.Tag.objects.only('id','name').filter(is_delete=False)
        news=models.News.objects.select_related('author','tag').\
            only('title','author__username','tag__name','update_time').filter(is_delete=False)

        # 通过时间进行过滤
        try:
            # 查询到的起始时间 url获取参数
            start_time = request.GET.get('start_time', '')
            # 对时间格式化 字符串转换成时间
            start_time = datetime.strptime (start_time, '%Y/%m/%d') if start_time else ''
            # 查询截止的时间
            end_time = request.GET.get ('end_time', '')
            # 时间格式化
            end_time = datetime.strptime (end_time, '%Y/%m/%d') if end_time else ''
        except Exception as e:
            logger.info ("用户输入的时间有误：\n{}".format (e))
            start_time = end_time = ''

        # 只有起始时间
        if start_time and not end_time:
            # 大于等于
            news = news.filter (update_time__gte=start_time)

        # 只有结束时间
        if end_time and not start_time:
            # 小于等于
            news = news.filter (update_time__lte=end_time)

        # 起始时间和结束时间
        if start_time and end_time:
            # 范围查询
            news = news.filter (update_time__range=(start_time, end_time))

        # 通过title进行过滤
        title = request.GET.get ('title', '')
        if title:
            # icontains大小写不敏感模糊查询
            news = news.filter (title__icontains=title)

        # 通过作者名进行过滤
        author_name = request.GET.get ('author_name', '')
        if author_name:
            news = news.filter (author__username__icontains=author_name)

        # 通过标签id进行过滤
        try:
            tag_id=int(request.GET.get('tag_id',0))
        except Exception as e:
            logger.info('标签错误：\n{}'.format(e))
            tag_id=0
        if tag_id:
            news=news.filter(tag_id=tag_id)

        # 分页算法
        try:
            # 获取前端的页码,默认是第一页
            page = int (request.GET.get ('page', 1))
        except Exception as e:
            logger.info ("当前页数错误：\n{}".format (e))
            page = 1
        # 分页
        paginator = Paginator(news, PER_PAGE_NEWS_COUNT)
        try:
            # 具体页面文章内容
            news_info = paginator.page (page)
        except EmptyPage:
            # 若用户访问的页数大于实际页数，则返回最后一页数据
            logging.info ("用户访问的页数大于总页数。")
            news_info = paginator.page (paginator.num_pages)

        paginator_data = paginator_script.get_paginator_data (paginator, news_info)
        # strftime时间转换成字符串
        start_time = start_time.strftime ('%Y/%m/%d') if start_time else ''
        end_time = end_time.strftime ('%Y/%m/%d') if end_time else ''
        context = {
            'news_info': news_info,
            'tags': tag,
            'start_time': start_time,
            "end_time": end_time,
            "title": title,
            "author_name": author_name,
            "tag_id": tag_id,
            "other_param": urlencode ({
                "start_time": start_time,
                "end_time": end_time,
                "title": title,
                "author_name": author_name,
                "tag_id": tag_id,
            })
        }
        context.update (paginator_data)
        return render (request, 'admin/news/news_manage.html', context=context)


class NewsPubView(PermissionRequiredMixin,View):
    '''
    /admin/news/pub/
    '''

    permission_required = ('news.view_news','news.add_news')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (NewsPubView, self).handle_no_permission ()

    def get(self,request):
        tags = models.Tag.objects.only('id','name').filter(is_delete=False)
        return render(request,'admin/news/news_pub.html',locals())

    def post(self,request):
        # 1.从前端获取参数
        json_data = request.body
        if not json_data:
            return to_json_data (errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 2.将json转化为dict
        dict_data = json.loads (json_data.decode ('utf8'))
        form = NewsPubForm (data=dict_data)
        if form.is_valid ():
            # 3.保存到数据库
            # 只有form继承了forms.ModelForm 才能使用这种方法
            # 数据缓存
            news_instance = form.save (commit=False)
            news_instance.author = request.user
            # news_instance.author_id = 1     # for test
            news_instance.save ()
            # 4. 返回给前端
            return to_json_data (errmsg='文章创建成功')
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data ().values ():
                err_msg_list.append (item[0].get ('message'))
            err_msg_str = '/'.join (err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data (errno=Code.PARAMERR, errmsg=err_msg_str)


class NewsUploadImage(View):

    def post(self,request):
        # 传递文件
        image_file=request.FILES.get('image_file')
        if not image_file:
            return to_json_data(errno=Code.PARAMERR,errmsg='前端获取图片失败')
        # 判断文件类型
        if image_file.content_type not in ('image/jpeg', 'image/png', 'image/gif'):
            return to_json_data (errno=Code.DATAERR, errmsg='不能上传非图片文件')
        # 文件后缀获取
        try:
            image_ext_name = image_file.name.split ('.')[-1]
        except Exception as e:
            logger.info ('图片拓展名异常：{}'.format (e))
            image_ext_name = 'jpg'
        # 文件上传
        try:
            upload_res = FDFS_Client.upload_by_buffer (image_file.read (), file_ext_name=image_ext_name)
        except Exception as e:
            logger.error ('图片上传出现异常：{}'.format (e))
            return to_json_data (errno=Code.UNKOWNERR, errmsg='图片上传异常')
        else:
            if upload_res.get ('Status') != 'Upload successed.':
                logger.info ('图片上传到FastDFS服务器失败')
                return to_json_data (Code.UNKOWNERR, errmsg='图片上传到服务器失败')
            else:
                image_name = upload_res.get ('Remote file_id')
                image_url = settings.FASTDFS_SERVER_DOMAIN + '/' + image_name
                return to_json_data (data={'image_url': image_url}, errmsg='图片上传成功')


class UploadToken(View):
    """
    七牛云上传
    """
    def get(self, request):
        access_key = qiniu_secret_info.QI_NIU_ACCESS_KEY
        secret_key = qiniu_secret_info.QI_NIU_SECRET_KEY
        bucket_name = qiniu_secret_info.QI_NIU_BUCKET_NAME
        # 构建鉴权对象
        q = qiniu.Auth(access_key, secret_key)
        token = q.upload_token(bucket_name)

        return JsonResponse({"uptoken": token})


# 装饰类，并且用到csrf装饰器，装饰所有
@method_decorator(csrf_exempt,name='dispatch')
class MarkDownUploadImage(View):
    """"""
    def post(self, request):
        image_file = request.FILES.get('editormd-image-file')
        if not image_file:
            logger.info('从前端获取图片失败')
            return JsonResponse({'success': 0, 'message': '从前端获取图片失败'})

        if image_file.content_type not in ('image/jpeg', 'image/png', 'image/gif'):
            return JsonResponse({'success': 0, 'message': '不能上传非图片文件'})

        try:
            image_ext_name = image_file.name.split('.')[-1]
        except Exception as e:
            logger.info('图片拓展名异常：{}'.format(e))
            image_ext_name = 'jpg'

        try:
            upload_res = FDFS_Client.upload_by_buffer(image_file.read(), file_ext_name=image_ext_name)
        except Exception as e:
            logger.error('图片上传出现异常：{}'.format(e))
            return JsonResponse({'success': 0, 'message': '图片上传异常'})
        else:
            if upload_res.get('Status') != 'Upload successed.':
                logger.info('图片上传到FastDFS服务器失败')
                return JsonResponse({'success': 0, 'message': '图片上传到服务器失败'})
            else:
                image_name = upload_res.get('Remote file_id')
                image_url = settings.FASTDFS_SERVER_DOMAIN + image_name
                return JsonResponse({'success': 1, 'message': '图片上传成功', 'url': image_url})


# 文章编辑删除
class NewsEditView(PermissionRequiredMixin,View):
    '''
    admin/news/<int:news_id>
    '''

    permission_required = ('news.view_news', 'news.change_news','news.delete_news')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (NewsEditView, self).handle_no_permission ()

    def delete(self, request,news_id):
        news=models.News.objects.only('id').filter(id=news_id).first()
        if not news:
            return to_json_data (errno=Code.PARAMERR, errmsg="需要删除的文章不存在")
        else:
            news.is_delete = True
            news.save (update_fields=['is_delete','update_time'])
            return to_json_data (errmsg='文章删除成功!')

    def get(self,request,news_id):
        news=models.News.objects.filter(is_delete=False,id=news_id).first()
        if not news:
            return to_json_data (errno=Code.PARAMERR, errmsg="文章不存在")
        else:
            tags = models.Tag.objects.only ('id', 'name').filter (is_delete=False)
            return render(request, 'admin/news/news_pub.html', locals ())

    def put(self,request,news_id):
        news = models.News.objects.only ('id').filter (id=news_id).first ()
        if not news:
            return to_json_data (errno=Code.PARAMERR, errmsg="文章不存在")
        json_data = request.body
        if not json_data:
            return to_json_data (errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 将json转化为dict
        dict_data = json.loads (json_data.decode ('utf8'))
        form = NewsPubForm(data=dict_data)
        if form.is_valid():
            # 数据清洗获取
            news.title = form.cleaned_data.get ('title')
            news.digest = form.cleaned_data.get ('digest')
            news.content = form.cleaned_data.get ('content')
            news.image_url = form.cleaned_data.get ('image_url')
            news.tag = form.cleaned_data.get ('tag')
            news.save()
            return to_json_data (errmsg='文章更新成功')
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data ().values ():
                err_msg_list.append (item[0].get ('message'))
            err_msg_str = '/'.join (err_msg_list)  # 拼接错误信息为一个字符串
            return to_json_data (errno=Code.PARAMERR, errmsg=err_msg_str)


class DocsManageView(PermissionRequiredMixin,View):
    '''
    admin/docs/
    '''

    permission_required = ('doc.view_doc')
    raise_exception = True

    def get(self,request):
        docs = Doc.objects.only('title','update_time').filter(is_delete=False)
        return render(request,'admin/doc/docs_manage.html',locals())


class DocsEditView(PermissionRequiredMixin,View):
    """
        /admin/docs/<int:doc_id>/
        """

    permission_required = ('doc.view_doc', 'doc.delete_doc', 'doc.change_doc')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (DocsEditView, self).handle_no_permission ()

    def get(self, request, doc_id):
        doc = Doc.objects.filter (is_delete=False, id=doc_id).first ()
        if doc:
            return render (request, 'admin/doc/docs_pub.html', locals ())
        else:
            return to_json_data (errno=Code.NODATA, errmsg='需要更新的文档不存在')

    def delete(self, request, doc_id):
        doc = Doc.objects.filter(is_delete=False,id = doc_id).first()
        if  doc:
            doc.is_delete = True
            doc.save(update_fields=['is_delete','update_time'])
            return to_json_data(errmsg="文档删除成功")
        else:
            return to_json_data(errno=Code.NODATA, errmsg='需要删除的文档不存在')

    def put(self, request, doc_id):
        doc = Doc.objects.filter (is_delete=False, id=doc_id).first ()
        if not doc:
            return to_json_data (errno=Code.NODATA, errmsg='需要更新的文档不存在')

        json_data = request.body
        if not json_data:
            return to_json_data (errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 将json转化为dict
        dict_data = json.loads (json_data.decode ('utf8'))
        form = DocsPubForm (data=dict_data)
        if form.is_valid ():
            for attr, value in form.cleaned_data.items ():
                setattr (doc, attr, value)
            doc.save ()
            return to_json_data (errmsg='文档更新成功')
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data ().values ():
                err_msg_list.append (item[0].get ('message'))
            err_msg_str = '/'.join (err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data (errno=Code.PARAMERR, errmsg=err_msg_str)


class DocsUploadFile(PermissionRequiredMixin,View):
    """
        /admin/docs/files/
    """
    permission_required = ('doc.add_doc', 'doc.change_doc')
    raise_exception = True

    def handle_no_permission(self):
        return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')


    def post(self, request):
        text_file = request.FILES.get ('text_file')
        if not text_file:
            logger.info ('从前端获取文件失败!')
            return to_json_data (errno=Code.NODATA, errmsg='从前端获取文件失败')
        if text_file.content_type not in ('application/octet-stream', 'application/pdf',
                                          'application/zip', 'text/plain', 'application/x-rar','application/msword'):
            return to_json_data (errno=Code.DATAERR, errmsg='不能上传的文件类型')

        try:
            text_ext_name = text_file.name.split ('.')[-1]
        except Exception as e:
            logger.info ('文件拓展名异常：{}'.format (e))
            text_ext_name = 'pdf'

        try:
            upload_res = FDFS_Client.upload_by_buffer (text_file.read (), file_ext_name=text_ext_name)
        except Exception as e:
            logger.error ('文件上传出现异常：{}'.format (e))
            return to_json_data (errno=Code.UNKOWNERR, errmsg='文件上传异常')
        else:
            if upload_res.get ('Status') != 'Upload successed.':
                logger.info ('文件上传到FastDFS服务器失败')
                return to_json_data (Code.UNKOWNERR, errmsg='文件上传到服务器失败')
            else:
                text_name = upload_res.get ('Remote file_id')
                text_url = settings.FASTDFS_SERVER_DOMAIN + '/' + text_name
                return to_json_data (data={'text_file': text_url}, errmsg='文件上传成功')


class DocsPubView(PermissionRequiredMixin,View):
    """
    /admin/docs/pub/
    """
    permission_required = ('doc.view_doc', 'doc.add_doc')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (DocsPubView, self).handle_no_permission ()

    def get(self,request):
        return render(request,'admin/doc/docs_pub.html')

    def post(self,request):
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))

        form = DocsPubForm(data=dict_data)
        if form.is_valid():
            doc_instance = form.save(commit=False)
            doc_instance.author = request.user
            doc_instance.save()
            return to_json_data(errmsg='文档创建成功')
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data().values():
                err_msg_list.append(item[0].get('message'))
            err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)


class CoursesManageView(PermissionRequiredMixin,View):
    """
    /admin/courses/
    """
    permission_required = ('course.view_course')
    raise_exception = True

    def get(self,request):
        courses = Course.objects.select_related('category','teacher').\
            only('title','category__name','teacher__name').filter(is_delete=False)
        return render(request,'admin/course/courses_manage.html',locals())


class CoursesEditView(PermissionRequiredMixin,View):
    """
    /admin/courses/<int:course_id>/
    """
    permission_required = ('course.view_course', 'course.delete_course', 'course.change_course')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (CoursesEditView, self).handle_no_permission ()

    def get(self, request, course_id):
        course = Course.objects.filter(is_delete=False, id=course_id).first()
        if course:
            teachers = Teacher.objects.only('name').filter(is_delete=False)
            categories = CourseCategory.objects.only('name').filter(is_delete=False)
            return render(request, 'admin/course/courses_pub.html', locals())
        else:
            return to_json_data(errno=Code.NODATA, errmsg='需要更新的课程不存在')

    def delete(self, request, course_id):
        course = Course.objects.filter(is_delete=False, id=course_id).first()
        if course:
            course.is_delete = True
            course.save(update_fields=['is_delete','update_time'])
            return to_json_data(errmsg="课程删除成功")
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="需要删除的课程不存在")

    def put(self, request, course_id):
        course = Course.objects.filter (is_delete=False, id=course_id).first ()
        if not course:
            return to_json_data (errno=Code.NODATA, errmsg='需要更新的课程不存在')

        json_data = request.body
        if not json_data:
            return to_json_data (errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 将json转化为dict
        dict_data = json.loads (json_data.decode ('utf8'))

        form = CoursesPubForm (data=dict_data)
        if form.is_valid ():
            for attr, value in form.cleaned_data.items ():
                setattr (course, attr, value)

            course.save ()
            return to_json_data (errmsg='课程更新成功')
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data ().values ():
                err_msg_list.append (item[0].get ('message'))
            err_msg_str = '/'.join (err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data (errno=Code.PARAMERR, errmsg=err_msg_str)


class CoursesPubView(PermissionRequiredMixin,View):
    """
    /admin/courses/pub/
    """
    permission_required = ('course.view_course', 'course.add_course')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (CoursesPubView, self).handle_no_permission ()

    def get(self,request):
        teachers = Teacher.objects.only('name').filter(is_delete=False)
        categories = CourseCategory.objects.only('name').filter(is_delete=False)
        return render(request,'admin/course/courses_pub.html',locals())

    def post(self,request):
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))

        form = CoursesPubForm(data=dict_data)
        if form.is_valid():
            courses_instance = form.save()
            return to_json_data(errmsg='课程发布成功')
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data().values():
                err_msg_list.append(item[0].get('message'))
            err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)


class BannerManageView(PermissionRequiredMixin,View):

    permission_required = ('news.view_banner')
    raise_exception = True

    def get(self,request):
            banners = models.Banner.objects.only('image_url','priority').filter(is_delete=False).\
                order_by('priority','id')[0:SHOW_BANNER_COUNT]
            priority_dict = dict(models.Banner.PRI_CHOICES)
            return render(request,'admin/news/news_banner.html',locals())


class BannerEditView(PermissionRequiredMixin,View):
    permission_required = ('news.delete_banner', 'news.change_banner')
    raise_exception = True

    def handle_no_permission(self):
        return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')

    def delete(self,request,banner_id):
        banner=models.Banner.objects.filter(is_delete=False,id=banner_id).first()
        if banner:
            banner.is_delete=True
            banner.save(update_fields=['is_delete','update_time'])
            return to_json_data(errmsg='轮播图删除成功')
        return to_json_data(errno=Code.PARAMERR, errmsg="需要删除的轮播图不存在")

    def put(self,request,banner_id):
        rotation_char = models.Banner.objects.filter(id=banner_id).first()
        if rotation_char:
            json_data = request.body
            if not json_data:
                return to_json_data (errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
            # 将json转化为dict
            dict_data = json.loads (json_data.decode ('utf8'))
            try:
                # 从前端获取到优先级并且转换成int类型
                priority = int (dict_data.get ('priority'))
                # 列表生成式，判断前端传递优先级在不在规定优先级中
                priority_list = [i for i, _ in models.Banner.PRI_CHOICES]
                if priority not in priority_list:
                    return to_json_data (errno=Code.PARAMERR, errmsg='轮播图的优先级设置错误')
            except Exception as e:
                logger.info ('轮播图优先级异常：{}'.format (e))
                return to_json_data (errno=Code.PARAMERR, errmsg='轮播图的优先级设置错误')
            image_url = dict_data.get ('image_url')
            if image_url:
                if rotation_char.priority != priority and rotation_char.image_url == image_url:
                    # 保存更改
                    rotation_char.priority = priority
                    rotation_char.image_url = image_url
                    rotation_char.save (update_fields=['priority', 'image_url'])
                    return to_json_data (errmsg="更新成功")

                else:
                    return to_json_data (errno=Code.PARAMERR, errmsg="参数未改变")
            else:
                return to_json_data (errno=Code.PARAMERR, errmsg='url为空')
        else:
            return to_json_data (errno=Code.PARAMERR, errmsg="需要更新的轮播图不存在")


class BannerAddView(PermissionRequiredMixin,View):
    permission_required = ('news.view_banner', 'news.add_banner')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (BannerAddView, self).handle_no_permission ()

    def get(self,request):
        tags=models.Tag.objects.only('id','name').filter(is_delete=False)
        priority_dict=dict(models.Banner.PRI_CHOICES)
        return render(request,'admin/news/news_banner_add.html',locals())

    def post(self,request):
        json_data = request.body
        if not json_data:
            return to_json_data (errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 将json转化为dict
        dict_data = json.loads (json_data.decode ('utf8'))
        try:
            news_id = int (dict_data.get ('news_id'))
        except Exception as e:
            logger.info ('参数错误：{}'.format (e))
            return to_json_data (errno=Code.PARAMERR, errmsg='参数错误')
        if models.News.objects.filter (id=news_id).exists ():
            try:
                priority = int (dict_data.get ('priority'))
                # 图片优先级，的数字
                priority_list = [i for i, _ in models.Banner.PRI_CHOICES]
                if priority not in priority_list:
                    return to_json_data (errno=Code.PARAMERR, errmsg='轮播图的优先级设置错误')
            except Exception as e:
                logger.info ('轮播图优先级异常：\n{}'.format (e))
                return to_json_data (errno=Code.PARAMERR, errmsg='轮播图的优先级设置错误')
            # 获取轮播图url
            image_url = dict_data.get ('image_url')
            if image_url:
                # 创建轮播图
                # 没有则创建 ，有则取出
                rotation_char_tuple = models.Banner.objects.get_or_create(news_id=news_id)
                #  is_created 第二个元素如果是 False,说明  存在，并取出
                # 如果是 True 创建
                #  rotation_char 查询集
                rotation_char,is_created = rotation_char_tuple
                rotation_char.priority = priority
                rotation_char.image_url = image_url
                # 针对性保存
                rotation_char.save (update_fields=['priority', 'image_url'])
                return to_json_data (errmsg="轮播图创建成功")
            else:
                return to_json_data (errno=Code.PARAMERR, errmsg='轮播图url为空')
        else:
            return to_json_data (errno=Code.PARAMERR, errmsg='文章不存在')


class GroupsManageView(PermissionRequiredMixin,View):
    """
    /admin/groups/
    """
    permission_required = ('news.view_course')
    raise_exception = True

    def get(self,request):
        # 组信息查询，annotate（分组查询）
        groups = Group.objects.values('id','name').annotate(num_users=Count('user')).\
            order_by('-num_users','id')
        return render(request,'admin/user/groups_manage.html',locals())


class GroupsEditView(PermissionRequiredMixin,View):
    """
    /admin/groups/<int:group_id>/
    """
    permission_required = ('auth.view_group', 'auth.delete_group', 'auth.change_group')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (GroupsEditView, self).handle_no_permission ()

    def get(self,request,group_id):
        group = Group.objects.filter(id=group_id).first()
        if group:
            permissions = Permission.objects.only('id').all()
            return render(request,'admin/user/groups_add.html',locals())
        raise Http404('需要更新的组不存在!')

    def delete(self, request, group_id):
        group = Group.objects.filter(id=group_id).first()
        if group:
            group.permissions.clear()   # 清空权限
            group.delete()
            return to_json_data(errmsg="用户组删除成功")
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="需要删除的用户组不存在")

    def put(self,request,group_id):
        group = Group.objects.filter(id=group_id).first()
        if not group:
            return to_json_data(errno=Code.NODATA, errmsg='需要更新的用户组不存在')

        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 将json转化为dict
        dict_data = json.loads(json_data.decode('utf8'))

        # 取出组名，进行判断
        group_name = dict_data.get('name', '').strip()
        if not group_name:
            return to_json_data(errno=Code.PARAMERR, errmsg='组名为空')

        if group_name != group.name and Group.objects.filter(name=group_name).exists():
                return to_json_data(errno=Code.DATAEXIST, errmsg='组名已存在')

        # 取出权限
        group_permissions = dict_data.get('group_permissions')
        if not group_permissions:
            return to_json_data(errno=Code.PARAMERR, errmsg='权限参数为空')

        try:
            permissions_set = set(int(i) for i in group_permissions)
        except Exception as e:
            logger.info('传的权限参数异常：\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='权限参数异常')

        all_permissions_set = set(i.id for i in Permission.objects.only('id'))
        if not permissions_set.issubset(all_permissions_set):
            return to_json_data(errno=Code.PARAMERR, errmsg='有不存在的权限参数')

        existed_permissions_set = set(i.id for i in group.permissions.all())
        if group_name == group.name and permissions_set == existed_permissions_set:
            return to_json_data(errno=Code.DATAEXIST, errmsg='用户组信息未修改')
        # 设置权限
        for perm_id in permissions_set:
            p = Permission.objects.get(id=perm_id)
            group.permissions.add(p)
        group.name = group_name
        group.save()
        return to_json_data(errmsg='组更新成功！')


class GroupsAddView(PermissionRequiredMixin,View):
    """
    /admin/groups/add/
    """
    permission_required = ('auth.view_group', 'auth.add_group')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (GroupsAddView, self).handle_no_permission ()

    def get(self,request):
        permissions = Permission.objects.only('id').all()
        return render(request,'admin/user/groups_add.html',locals())

    def post(self,request):
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))

        # 取出组名，进行判断
        group_name = dict_data.get('name', '').strip()
        if not group_name:
            return to_json_data(errno=Code.PARAMERR, errmsg='组名为空')

        one_group, is_created = Group.objects.get_or_create(name=group_name)
        if not is_created:
            return to_json_data(errno=Code.DATAEXIST, errmsg='组名已存在')

        # 取出权限
        group_permissions = dict_data.get('group_permissions')
        if not group_permissions:
            return to_json_data(errno=Code.PARAMERR, errmsg='权限参数为空')

        try:
            permissions_set = set(int(i) for i in group_permissions)
        except Exception as e:
            logger.info('传的权限参数异常：\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='权限参数异常')

        all_permissions_set = set(i.id for i in Permission.objects.only('id'))
        if not permissions_set.issubset(all_permissions_set):
            return to_json_data(errno=Code.PARAMERR, errmsg='有不存在的权限参数')

        # 设置权限
        for perm_id in permissions_set:
            p = Permission.objects.get(id=perm_id)
            one_group.permissions.add(p)

        one_group.save()
        return to_json_data(errmsg='组创建成功！')


class UsersManageView(PermissionRequiredMixin,View):
    """
    /admin/users/
    """
    permission_required = ('users.view_users')
    raise_exception = True

    def get(self,request):
        users = User.objects.only('username', 'is_staff', 'is_superuser').filter(is_active=True)
        return render(request, 'admin/user/users_manage.html', locals())


class UsersEditView(PermissionRequiredMixin,View):
    """
    /admin/users/<int:user_id>/
    """
    permission_required = ('user.view_users', 'user.change_users', 'user.delete_users')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower () != 'get':
            return to_json_data (errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super (UsersEditView, self).handle_no_permission ()

    def get(self,request,user_id):
        user_instance = User.objects.filter(id=user_id).first()
        if user_instance:
            groups = Group.objects.only('name').all()
            return render(request, 'admin/user/users_edit.html', locals())
        else:
            raise Http404('需要更新的用户不存在！')

    def put(self,request,user_id):
        user_instance = User.objects.filter(id=user_id).first()
        if not user_instance:
            return to_json_data(errno=Code.NODATA, errmsg='需要更新的用户不存在')

        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 将json转化为dict
        dict_data = json.loads(json_data.decode('utf8'))

        # 取出参数，进行判断
        try:
            groups = dict_data.get('groups')    # 取出用户组列表

            is_staff = int(dict_data.get('is_staff'))
            is_superuser = int(dict_data.get('is_superuser'))
            is_active = int(dict_data.get('is_active'))
            params = (is_staff, is_superuser, is_active)
            if not all([p in (0, 1) for p in params]):
                return to_json_data(errno=Code.PARAMERR, errmsg='参数错误')
        except Exception as e:
            logger.info('从前端获取参数出现异常：\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='参数错误')

        try:
            groups_set = set(int(i) for i in groups) if groups else set()
        except Exception as e:
            logger.info('传的用户组参数异常：\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='用户组参数异常')

        all_groups_set = set(i.id for i in Group.objects.only('id'))
        if not groups_set.issubset(all_groups_set):
            return to_json_data(errno=Code.PARAMERR, errmsg='有不存在的用户组参数')

        gs = Group.objects.filter(id__in=groups_set)
        # 先清除组
        user_instance.groups.clear()
        user_instance.groups.set(gs)

        user_instance.is_staff = bool(is_staff)
        user_instance.is_superuser = bool(is_superuser)
        user_instance.is_active = bool(is_active)
        user_instance.save()
        return to_json_data(errmsg='用户信息更新成功！')

    def delete(self, request, user_id):
        user_instance = User.objects.filter(id=user_id).first()
        if user_instance:
            user_instance.groups.clear()    # 清除用户组
            user_instance.user_permissions.clear()  # 清除用户权限
            user_instance.is_active = False  # 设置为不激活状态
            user_instance.save()
            return to_json_data(errmsg="用户删除成功")
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="需要删除的用户不存在")