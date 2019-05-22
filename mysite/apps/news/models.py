import pytz
from utils.models import ModelBase
from django.db import models
# 最小长度校验器
from django.core.validators import MinLengthValidator

# 继承模型表基类
# 标签表
class Tag(ModelBase):
    name=models.CharField(max_length=64, verbose_name="标签名", help_text="标签名")

    class Meta:
        ordering = ['-update_time', '-id'] # 排序从大到小
        db_table = "tb_tag"  # 指明数据库表名
        verbose_name = "新闻标签"  # 在admin站点中显示的名称
        verbose_name_plural = verbose_name  # 显示的复数名称

    def __str__(self):
        return self.name

# 文章表
class News(ModelBase):
    # 限制最小长度 validators=[MinLengthValidator(1)]
    title = models.CharField (max_length=150,validators=[MinLengthValidator(1)] ,verbose_name="标题", help_text="标题")
    digest = models.CharField (max_length=200,validators=[MinLengthValidator(1)], verbose_name="摘要", help_text="摘要")
    content = models.TextField (verbose_name="内容", help_text="内容")
    clicks = models.IntegerField (default=0, verbose_name="点击量", help_text="点击量")
    image_url = models.URLField (default="", verbose_name="图片url", help_text="图片url")
    # 标签，外键关联tag表，一对多建表在多的地方，on_delete=models.SET_NULL 设置为空
    tag = models.ForeignKey ('Tag', on_delete=models.SET_NULL, null=True)
    # 作者，外键关联users app里面的User表，一对多
    author = models.ForeignKey ('users.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-update_time', '-id']
        db_table = "tb_news"  # 指明数据库表名
        verbose_name = "新闻"  # 在admin站点中显示的名称
        verbose_name_plural = verbose_name  # 显示的复数名称

    def __str__(self):
        return self.title

# 评论信息表
class Comments(ModelBase):
    content = models.TextField (verbose_name="内容", help_text="内容")
    # 外键关联用户表
    author = models.ForeignKey ('users.User', on_delete=models.SET_NULL, null=True)
    # 外键关联新闻表 级联删除
    news = models.ForeignKey ('News', on_delete=models.CASCADE)
    # 关联自己，做子评论
    parent = models.ForeignKey('self',on_delete=models.CASCADE,null=True,blank=True)
    # 模型中序列化
    def to_dict_data(self):
        shanghai_tz = pytz.timezone('Asia/Shanghai')
        update_time_locale = shanghai_tz.normalize(self.update_time)
        comment_dict = {
            'news_id':self.news_id,
            'comment_id':self.id,
            'content':self.content,
            'author':self.author.username,
            # 'update_time':self.update_time.strftime('%Y年%m月%d日 %H:%M'),
            'update_time':update_time_locale.strftime('%Y年%m月%d日 %H:%M'),
            'parent':self.parent.to_dict_data() if self.parent else None,
        }
        return comment_dict

    class Meta:
        ordering = ['-update_time', '-id']
        db_table = "tb_comments"  # 指明数据库表名
        verbose_name = "评论"  # 在admin站点中显示的名称
        verbose_name_plural = verbose_name  # 显示的复数名称

    def __str__(self):
        return '<评论{}>'.format (self.id)

# 热门文章
class HotNews(ModelBase):
    # 一对一关联新闻表
    news = models.OneToOneField('News', on_delete=models.CASCADE)
    # 用于页面上的选择框标签
    PRI_CHOICES=[
        (1,'第一级'),
        (2,'第二级'),
        (3,'第三级'),
    ]
    # 优先级字段 限制值的范围
    priority = models.IntegerField(choices=PRI_CHOICES, default=3, verbose_name="优先级", help_text="优先级")

    class Meta:
        ordering = ['-update_time', '-id']
        db_table = "tb_hotnews"  # 指明数据库表名
        verbose_name = "热门新闻"  # 在admin站点中显示的名称
        verbose_name_plural = verbose_name  # 显示的复数名称

    def __str__(self):
        return '<热门新闻{}>'.format(self.id)

# 轮播图
class Banner(ModelBase):
    # 轮播图图片地址
    image_url = models.URLField(verbose_name="轮播图url", help_text="轮播图url")
    #
    PRI_CHOICES=[
        (1,'第一级'),
        (2,'第二级'),
        (3,'第三级'),
        (4,'第四级'),
        (5,'第五级'),
        (6,'第六级'),
    ]
    # 轮播图优先级 限制值的范围
    priority = models.IntegerField(choices=PRI_CHOICES,default=6, verbose_name="优先级", help_text="优先级")
    # 一对一
    news = models.OneToOneField('News', on_delete=models.CASCADE)

    class Meta:
        ordering = ['priority', '-update_time', '-id']
        db_table = "tb_banner"  # 指明数据库表名
        verbose_name = "轮播图"  # 在admin站点中显示的名称
        verbose_name_plural = verbose_name  # 显示的复数名称

    def __str__(self):
        return '<轮播图{}>'.format(self.id)