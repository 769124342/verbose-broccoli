'''
固定文件名称
'''
# 搜索引擎框架
from haystack import indexes
# from haystack import site

from .models import News

# 索引类模型名称加Index名称固定
class NewsIndex(indexes.SearchIndex, indexes.Indexable):
    """
    News索引数据模型类
    """
    text = indexes.CharField(document=True, use_template=True)

    # 获取属性，如果没有就是news.object.id
    id = indexes.IntegerField(model_attr='id')
    title = indexes.CharField(model_attr='title')
    digest = indexes.CharField(model_attr='digest')
    content = indexes.CharField(model_attr='content')
    image_url = indexes.CharField(model_attr='image_url')
    # comments = indexes.IntegerField(model_attr='comments')

    def get_model(self):
        """返回建立索引的模型类
        """
        return News

    def index_queryset(self, using=None):
        """返回要建立索引的数据查询集
        """

        # return self.get_model().objects.filter(is_delete=False)
        # 其中之一：__in   在tag_id标签中，6个中的一个：tag_id__in=[1, 2, 3, 4, 5, 6]
        return self.get_model ().objects.filter (is_delete=False, tag_id__in=[1, 2, 3, 4, 5, 6])