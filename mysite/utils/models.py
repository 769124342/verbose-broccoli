from django.db import models

# 模型表基类
class ModelBase(models.Model):
    # 创建时间 自动添加
    create_time=models.DateTimeField(auto_now_add=True,verbose_name='创建时间')
    # 更新时间
    update_time=models.DateTimeField(auto_now=True,verbose_name='更新时间')
    # 逻辑删除
    is_delete=models.BooleanField(default=False,verbose_name='逻辑删除')

    # 防止数据库迁移的时候创建表，数据只用来做继承
    class Meta:
        # 为抽象模型类, 用于其他模型来继承，数据库迁移时不会创建ModelBase表
        abstract=True