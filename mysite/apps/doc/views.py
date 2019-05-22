import requests
import logging

from django.shortcuts import render
from django.http import FileResponse, Http404
from django.utils.encoding import escape_uri_path
from django.views import View
from django.conf import settings

from .models import Doc

# 导入日志器
logger = logging.getLogger ('django')


def doc_index(request):
    """
    """
    docs = Doc.objects.defer ('author', 'create_time', 'update_time', 'is_delete').filter (is_delete=False)
    return render (request, 'doc/docDownload.html', locals ())


class DocDownload (View):
    def get(self, request, doc_id):
        # 获取文件地址
        doc = Doc.objects.only ('file_url').filter (is_delete=False, id=doc_id).first ()
        if doc:
            # 下载地址拼接
            doc_url = doc.file_url
            doc_url = settings.SITE_DOMAIN_PORT + doc_url
            try:
                # stream在下载大文件的时候可以提升下载速度
                res = FileResponse(requests.get(doc_url, stream=True))
            except Exception as e:
                logger.info ("获取文档内容出现异常：\n{}".format (e))
                raise Http404 ("文档下载异常！")
            # 得到文件后缀
            ex_name = doc_url.split ('.')[-1]
            # https://stackoverflow.com/questions/23714383/what-are-all-the-possible-values-for-http-content-type-header
            # http://www.iana.org/assignments/media-types/media-types.xhtml#image
            if not ex_name:
                raise Http404 ("文档url异常！")
            else:
                ex_name = ex_name.lower ()

            if ex_name == "pdf":
                res["Content-type"] = "application/pdf"
            elif ex_name == "zip":
                res["Content-type"] = "application/zip"
            elif ex_name == "doc":
                res["Content-type"] = "application/msword"
            elif ex_name == "xls":
                res["Content-type"] = "application/vnd.ms-excel"
            elif ex_name == "docx":
                res["Content-type"] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif ex_name == "ppt":
                res["Content-type"] = "application/vnd.ms-powerpoint"
            elif ex_name == "pptx":
                res["Content-type"] = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            else:
                raise Http404 ("文档格式不正确！")
            doc_filename = escape_uri_path (doc_url.split ('/')[-1])
            # http1.1 中的规范
            # 设置为inline，会直接打开
            # attachment 浏览器会开始下载
            res["Content-Disposition"] = "attachment; filename*=UTF-8''{}".format (doc_filename)
            return res
        else:
            raise Http404 ("文档不存在！")