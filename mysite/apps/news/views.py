import logging
import json

from django.shortcuts import render
from django.views import View
from django.http import Http404
# 分页
from django.core.paginator import Paginator,EmptyPage,PageNotAnInteger

from dj_web import settings
from news import models

from haystack.views import SearchView as _SearchView

from .constants import PER_PAGE_NEWS_COUNT,SHOW_HOTNEWS_COUNT,SHOW_BANNER_COUNT
from utils.json_fun import to_json_data
from utils.res_code import Code,error_map

# django日志器
logger=logging.getLogger('django')

class IndexView(View):
    def get(self,request):
        # 查询数据，优化只查询id和name字段
        tags=models.Tag.objects.only('id','name').filter(is_delete=False)
        # 查询数据拼接两张表
        hot_news=models.HotNews.objects.select_related('news').only(
            'news__title',
            'news__image_url',
            'news_id'
        ).filter(is_delete=False).order_by('priority','-news__clicks')[0:SHOW_HOTNEWS_COUNT] # 排序切片

        # 排除字段
        # tags=models.Tag.objects.defer('create_time','update_time').filter(is_delete=False)
        # context = {
        #     'tags': tags
        # }
        # locals函数会以字典类型返回当前位置的全部局部变量。
        return render(request,'news/index.html',locals())

# 列表详情页 ajax传参
class NewsListView(View):
    def get(self,request):
        # 获取标签id参数
        # 确保id一定为整数和传参
        try:
            tag_id=int(request.GET.get('tag_id',0))
        except Exception as e:
            # 写入错误日志
            logger.error('标签错误：\n{}'.format(e))
            tag_id=0
        # 获取分页page参数
        try:
            page=int(request.GET.get('page',1))
        except Exception as e:
            logger.error('页码错误：\n{}'.format(e))
            page=1
        # 需要查询的数据：title,
        # 数据库查询数据,关联多表查询优化
        new_queryset = models.News.objects.select_related('tag','author').only(
            'title',
            'digest',
            'image_url',
            'update_time',
            # 关联查询字段
            'tag__name',
            'author__username'
        )
        # 数据查询
        news = new_queryset.filter(is_delete=False,tag_id=tag_id) or new_queryset.filter(is_delete=False)
        # 分页:数据,每页多少条数据
        paginator = Paginator(news,PER_PAGE_NEWS_COUNT)
        # 获取某页数据
        try:
            news_info=paginator.page(page)
        except Exception:
            logger.error('访问页数大于总页数')
            # 获取最后一页数据
            news_info = paginator.page(paginator.num_pages)
        # 序列化输出,符合前端规定好的格式
        '''
        {
            "data": {
                "total_pages": 61,
                "news": [
                    {
                        "digest": "在python用import或者from...import或者from...import...as...来导入相应的模块，作用和使用方法与C语言的include头文件类似。其实就是引入...",
                        "title": "import方法引入模块详解",
                        "author": "python",
                        "image_url": "/media/jichujiaochen.jpeg",
                        "tag_name": "Python基础",
                        "update_time": "2018年12月17日 14:48"
                    },
                    {
                        "digest": "如果你原来是一个php程序员，你对于php函数非常了解（PS：站长原来就是一个php程序员），但是现在由于工作或者其他原因要学习python，但是p...",
                        "title": "给曾经是phper的程序员推荐个学习网站",
                        "author": "python",
                        "image_url": "/media/jichujiaochen.jpeg",
                        "tag_name": "Python基础",
                        "update_time": "2018年12月17日 14:48"
                    }
                ]
            },
            "errno": "0",
            "errmsg": ""
        }
       '''
        news_info_list=[]
        for n in news_info:
            news_info_list.append({
                'id':n.id,
                'title': n.title,
                'digest': n.digest,
                'image_url': n.image_url,
                'tag_name': n.tag.name,
                'author': n.author.username,
                # 格式化输出时间
                'update_time': n.update_time.strftime('%Y年%m月%d日 %H:%M'),
            })
        data={
            'news':news_info_list,
            'total_pages':paginator.num_pages,
        }
        return to_json_data(data=data)

# 轮播图
class NewsBannerView(View):
    """
    轮播图，ajax传参，前后端分离
    """
    def get(self,request):
        # 数据库查询
        banners=models.Banner.objects.select_related('news').only('image_url','news_id','news__title').\
            filter(is_delete=False).order_by('priority')[0:SHOW_BANNER_COUNT]
        # 序列化输出
        banners_info_list=[]
        for i in banners:
            banners_info_list.append(
                {
                    'image_url':i.image_url,
                    'news_id':i.news_id,
                    'news_title':i.news.title,
                }
            )
        data={
            'banners':banners_info_list
        }
        return to_json_data(data=data)

# 标签页面
class NewsDetailView(View):
    """
    /news/<int:news_id>/
    """
    def get(self,request,news_id):
        # 关联查询字段名
        news=models.News.objects.select_related('tag','author').only('title','content','update_time','tag__name','author__username').\
            filter(is_delete=False,id=news_id).first()
        if news:
            # 评论信息
            comments = models.Comments.objects.select_related('author','parent').only('content','update_time','author__username','parent__content','parent__author__username','parent__update_time').\
                filter(is_delete=False,news_id=news_id)

            # 序列化输出
            comments_list=[]
            for comm in comments:
                # 调用模型类中的序列化方法
                comments_list.append(comm.to_dict_data())
            i=len(comments_list)

            return render(request ,'news/news_detail.html',locals())
        else:
            raise Http404('新闻{}不存在'.format(news_id))

# 评论
class NewsCommentView(View):
    """
    /news/<int:news_id>/comments/
    """
    def post(self,request,news_id):
        # 判读用户是否登录
        if not request.user.is_authenticated:
            return to_json_data(errno=Code.SESSIONERR,errmsg=error_map[Code.SESSIONERR])
        # 判断是否存在id新闻
        if not models.News.objects.only('id').filter(is_delete=False,id=news_id).exists():
            return to_json_data(errno=Code.PARAMERR,errmsg='新闻不存在')
        # 获取前端ajax传参
        json_data=request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR,errmsg=error_map[Code.PARAMERR])
        dict_data=json.loads(json_data.decode('utf8'))

        content = dict_data.get('content')
        if not dict_data.get('content'):
            return to_json_data(errno=Code.PARAMERR,errmsg='评论的内容不能为空')

        # 父评论的验证
        # 1、有没有父评论,可以没有
        # 2、parent_id 必须是数字
        # 3、数据库里面是否存在
        # 4、父评论的新闻 id 和 news_id 是否一致
        parent_id = dict_data.get('parent_id')
        try:
            if parent_id:
                parent_id = int (parent_id)
                if not models.Comments.objects.only('id').filter(is_delete=False,id=parent_id,news_id=news_id).exists():
                    return to_json_data (errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        except Exception as e:
            logger.info ('前端传递的parent_id异常{}'.format (e))
            return to_json_data (errno=Code.PARAMERR, errmsg='未知异常')

        # 保存到数据库
        # 实例化一个对象
        new_comment = models.Comments()
        # 传入数据
        new_comment.content = content
        new_comment.news_id = news_id
        # request.user是当前用户
        new_comment.author = request.user
        new_comment.parent_id = parent_id if parent_id else None
        new_comment.save ()

        return to_json_data (data=new_comment.to_dict_data ())

# 搜索
class SearchView(_SearchView):
    # 模版文件
    template = 'news/search.html'

    # 重写响应方式，如果请求参数q为空，返回模型News的热门新闻数据，否则根据参数q搜索相关数据
    def create_response(self):
        kw = self.request.GET.get('q', '')
        if not kw:
            show_all = True
            hot_news = models.HotNews.objects.select_related('news'). \
                only('news__title', 'news__image_url', 'news__id'). \
                filter(is_delete=False).order_by('priority', '-news__clicks')

            paginator = Paginator(hot_news, settings.HAYSTACK_SEARCH_RESULTS_PER_PAGE)
            try:
                page = paginator.page(int(self.request.GET.get('page', 1)))
            except PageNotAnInteger:
                # 如果参数page的数据类型不是整型，则返回第一页数据
                page = paginator.page(1)
            except EmptyPage:
                # 用户访问的页数大于实际页数，则返回最后一页的数据
                page = paginator.page(paginator.num_pages)
            return render(self.request, self.template, locals())
        else:
            show_all = False
            qs = super(SearchView, self).create_response()
            return qs