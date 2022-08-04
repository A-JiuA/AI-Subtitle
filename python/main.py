#!/usr/bin/python3
# -*- coding: UTF-8 -*-

from os import truncate
import configs

import sys
import json
import time
from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkcore.acs_exception.exceptions import ServerException
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
import uuid
import requests
import hashlib

# Log
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')


# 响应参数
KEY_TASK = "Task"
KEY_TASK_ID = "TaskId"
KEY_STATUS_TEXT = "StatusText"
KEY_RESULT = "Result"
# 状态值
STATUS_SUCCESS = "SUCCESS"
STATUS_RUNNING = "RUNNING"
STATUS_QUEUEING = "QUEUEING"
# JSON字段
KEY_RESULT_LIST = "Sentences"
KEY_LIST_TIME_BEGIN = "BeginTime"
KEY_LIST_TIME_END = "EndTime"
KEY_LIST_TEXT = "Text"
KEY_LIST_SPEECH_RATE = "SpeechRate"

def stt(akId, akSecret, appKey, fileLink) :
    # 地域ID，固定值。
    REGION_ID = "cn-shanghai"
    PRODUCT = "nls-filetrans"
    DOMAIN = "filetrans.cn-shanghai.aliyuncs.com"
    API_VERSION = "2018-08-17"
    POST_REQUEST_ACTION = "SubmitTask"
    GET_REQUEST_ACTION = "GetTaskResult"
    # 请求参数
    KEY_APP_KEY = "appkey"
    KEY_FILE_LINK = "file_link"
    KEY_VERSION = "version"
    KEY_ENABLE_WORDS = "enable_words"
    # 是否开启智能分轨
    KEY_AUTO_SPLIT = "auto_split"
    # 创建AcsClient实例
    client = AcsClient(akId, akSecret, REGION_ID)
    # 提交录音文件识别请求
    postRequest = CommonRequest()
    postRequest.set_domain(DOMAIN)
    postRequest.set_version(API_VERSION)
    postRequest.set_product(PRODUCT)
    postRequest.set_action_name(POST_REQUEST_ACTION)
    postRequest.set_method('POST')
    # 新接入请使用4.0版本，已接入（默认2.0）如需维持现状，请注释掉该参数设置。
    # 设置是否输出词信息，默认为false，开启时需要设置version为4.0。
    task = {KEY_APP_KEY : appKey, KEY_FILE_LINK : fileLink, KEY_VERSION : "4.0", KEY_ENABLE_WORDS : False}
    # 开启智能分轨，如果开启智能分轨，task中设置KEY_AUTO_SPLIT为True。
    # task = {KEY_APP_KEY : appKey, KEY_FILE_LINK : fileLink, KEY_VERSION : "4.0", KEY_ENABLE_WORDS : False, KEY_AUTO_SPLIT : True}
    task = json.dumps(task)
    logging.debug(task)
    postRequest.add_body_params(KEY_TASK, task)
    taskId = ""
    try :
        postResponse = client.do_action_with_exception(postRequest)
        postResponse = json.loads(postResponse)
        logging.debug(postResponse)
        statusText = postResponse[KEY_STATUS_TEXT]
        if statusText == STATUS_SUCCESS :
            logging.info("录音文件识别请求成功响应！")
            taskId = postResponse[KEY_TASK_ID]
        else :
            logging.error("录音文件识别请求失败！")
            return
    except ServerException as e:
        logging.error(e)
    except ClientException as e:
        logging.error(e)
    # 创建CommonRequest，设置任务ID。
    getRequest = CommonRequest()
    getRequest.set_domain(DOMAIN)
    getRequest.set_version(API_VERSION)
    getRequest.set_product(PRODUCT)
    getRequest.set_action_name(GET_REQUEST_ACTION)
    getRequest.set_method('GET')
    getRequest.add_query_param(KEY_TASK_ID, taskId)
    # 提交录音文件识别结果查询请求
    # 以轮询的方式进行识别结果的查询，直到服务端返回的状态描述符为"SUCCESS"、"SUCCESS_WITH_NO_VALID_FRAGMENT"，
    # 或者为错误描述，则结束轮询。
    statusText = ""
    statusText_old = statusText
    while True :
        try :
            getResponse = client.do_action_with_exception(getRequest)
            getResponse = json.loads(getResponse)
            logging.debug(getResponse)
            statusText = getResponse[KEY_STATUS_TEXT]
            if statusText == STATUS_RUNNING or statusText == STATUS_QUEUEING :
                # 检测状态变化
                if statusText_old != statusText:
                    if statusText == STATUS_QUEUEING:
                        logging.info("录音文件识别请求正在排队中")
                    elif statusText == STATUS_RUNNING:
                        logging.info("录音文件识别请求正在识别中")   
                statusText_old = statusText

                # 继续轮询
                time.sleep(0.1)
            else :
                # 退出轮询
                break
        except ServerException as e:
            logging.error(e)
        except ClientException as e:
            logging.error(e)
    if statusText == STATUS_SUCCESS :
        logging.info("录音文件识别成功！")
    else :
        logging.info("录音文件识别失败！")
        logging.error(statusText)
    return getResponse

def json2srt(json):
    if json[KEY_STATUS_TEXT] != STATUS_SUCCESS:
        return ""
    else:
        result = ""
        # 获得每句组成的列表
        result_list = json[KEY_RESULT][KEY_RESULT_LIST]
        # 解析每句,转换成srt格式
        t = 1
        for i in result_list:
            # 获得必要的值
            begin_time = i[KEY_LIST_TIME_BEGIN] / 1000
            end_time = i[KEY_LIST_TIME_END] / 1000
            speech_rate = i[KEY_LIST_SPEECH_RATE]
            text = i[KEY_LIST_TEXT]
            # 处理时间
            begin_time = str(int(begin_time) // 3600).zfill(2) + ":" + str(int(begin_time) // 60).zfill(2) + ":" + str(int(begin_time) % 60).zfill(2) + "," + str(int((begin_time - int(begin_time))*1000)).zfill(3)
            end_time = str(int(end_time) // 3600).zfill(2) + ":" + str(int(end_time) // 60).zfill(2) + ":" + str(int(end_time) % 60).zfill(2) + "," + str(int((end_time - int(end_time))*1000)).zfill(3)
            # 翻译
            translate_result = translate(text)
            if translate_result["errorCode"] != "0":
                translate_result = translate(text)
            translation = ""
            if translate_result["errorCode"] == "0":
                for i in translate_result["translation"]:
                    translation = translation + i
            # 转换为srt格式
            logging.debug(str(t))
            tmp_result = str(t) + "\n"
            logging.debug(begin_time + " --> " + end_time)
            tmp_result = tmp_result + begin_time + " --> " + end_time + "\n"
            if translation != "":
                logging.debug(translation)
                tmp_result = tmp_result + translation + "\n"
            logging.debug(text)
            tmp_result = tmp_result + text + "\n"
            tmp_result = tmp_result + "\n"
            
            logging.info("成功转为srt格式: " + text)
            result = result + tmp_result

            t+=1
        logging.info("已转为srt格式")
        return result

def translate(text):
    YOUDAO_URL = 'https://openapi.youdao.com/api'
    
    # 时间戳
    curtime = str(int(time.time()))
    # 盐值
    salt = str(uuid.uuid1())
    
    # 签名input
    size = len(text)
    if size <= 20:
        truncate = text
    else:
        truncate = text[0:10] + str(size) + text[size - 10:size]
    # 签名
    # 计算方法:  sha256(应用ID+input+salt+curtime+应用密钥)
    signStr = configs.YOUDAO_APP_KEY + truncate + salt + curtime + configs.YOUDAO_APP_SECRET
    hash_algorithm = hashlib.sha256()
    hash_algorithm.update(signStr.encode('utf-8'))
    sign = hash_algorithm.hexdigest()
    
    # post
    data = {}
    # 时间戳
    data['curtime'] = curtime
    # 源语言
    data['from'] = 'en'
    # 目标语言
    data['to'] = 'zh-CHS'
    # 签名类型
    data['signType'] = 'v3'
    # appKey
    data['appKey'] = configs.YOUDAO_APP_KEY
    # 待翻译文本
    data['q'] = text
    # 盐值
    data['salt'] = salt
    # 签名
    data['sign'] = sign
    # 严格模式
    data['strict'] = "true"
    # 用户上传的词典
    # data['vocabId'] = "您的用户词表ID"

    logging.debug(str(data))

    # requests
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(YOUDAO_URL, data=data, headers=headers)
    response = json.loads(response.content.decode('UTF-8'))
    if response["errorCode"] == "0":
        logging.info("翻译成功: " + text)
        logging.debug(str(response))
        return response
    else:
        logging.error("翻译失败: " + text)
        logging.debug(str(response))
        return response

def test():
    # fileLink = "https://github.com/A-JiuA/AI-Subtitle/raw/main/samples/A%20Glimpse%20into%20the%20Future.aac"
    fileLink = "https://github.com/A-JiuA/AI-Subtitle/raw/main/samples/%E7%9B%B4%E8%A7%82%E8%A7%86%E8%A7%89(%E4%BC%AA)%E8%AF%81%E6%98%8E%E4%B8%89%E4%BE%8B.aac"
    # 执行录音文件识别
    result = json2srt(stt(configs.ALIYUN_ACCESSKEY_ID, configs.ALIYUN_ACCESSKEY_SECRET, configs.ALIYUN_APPKEY, fileLink))
    with open("output.srt", "w", encoding="utf-8") as f:
        f.write(result)

if __name__ == "__main__":
    test()
    exit()
    # 参数判断
    if len(sys.argv) != 2:
        logging.warning("请提供文件路径")
        exit(1)
    else:
        logging.info(sys.argv[1])