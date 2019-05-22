from django.http import JsonResponse
from utils.res_code import Code

# 固定json返回格式
def to_json_data(errno=Code.OK,errmsg='',data=None,**kwargs):
    json_dict={
        'errno':errno,
        'errmsg':errmsg,
        'data':data,
    }
    # 判断是否存在，是否是字典，是都有值
    if kwargs and isinstance(kwargs,dict) and kwargs.keys():
        json_dict.update(kwargs)
    return JsonResponse(json_dict)