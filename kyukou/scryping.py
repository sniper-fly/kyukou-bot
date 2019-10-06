import requests
from datetime import datetime
from bs4 import BeautifulSoup
from pprint import pprint
import re
import hashlib
import time
isinpackage = not __name__ in ['line_notify_api', '__main__']
if isinpackage:
    from .db import get_collection
    from .util import log, getyear
    from . import twitter_api
    from .search import lectures_class_num
else:
    from util import getyear


def testdata():
    data = [{
        "time": 1570179907.562108,
        "date": datetime(2019, 10, 14).timestamp(),
        "teachers": "皆川",
        "subject": "キャリア教育基礎",
        "periods": [1]
    }, {
        "time": 1570179907.562108,
        "date": datetime(2019, 10, 15).timestamp(),
        "teachers": "MOREAU ROBERT",
        "subject": "Academic Spoken English Ⅰ",
        "periods": [1]
    }, {
        "time": 1570179907.562108,
        "date": datetime(2019, 10, 18).timestamp(),
        "teachers": "小林",
        "subject": "基礎科学実験B",
        "periods": [3, 4]
    }, {
        "time": 1570179907.562108,
        "date": datetime(2019, 10, 14).timestamp(),
        "teachers": "○八百",
        "subject": "健康・体力つくり実習（テニス）",
        "periods": [4]
    }]
    for d in data:
        d["hash"] = hashlib.sha256((str(d['date'])+d['subject']).encode()).hexdigest()
    return data


def kyuukou():
    req = requests.get('http://kyoumu.office.uec.ac.jp/kyuukou/kyuukou.html')
    req.encoding = 'cp932'
    html = req.text

    doc = BeautifulSoup(html, 'html.parser')

    limits = []
    c = re.compile(r'(\d+)月(\d+)日\(.\)')
    for tr in doc.select('tr')[1:]:
        a = tr.select('td')
        m = c.match(a[1].text)
        month, day = int(m.group(1)), int(m.group(2))
        date = datetime(getyear(month, day), month, day)
        limit = {
            "time": time.time(),
            "date": date.timestamp(),
            "teachers": a[4].text,
            "periods": list(map(int, a[2].text.split('・'))),
            "class": a[0].text,
            "subject": a[3].text,
            "remark": a[5].text.replace(u'\xa0', ''),
            "hash": hashlib.sha256((tr.text).encode()).hexdigest()
        }
        limits.append(limit)
    return limits


def format_lecture(data, prefix='【休講情報】'):
    weekday = ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日']
    date = datetime.fromtimestamp(data['date'])
    return f"""{prefix}
日付: {date.month}月{date.day}日({weekday[date.weekday()][0]})
時限: {'・'.join(map(str,data.get('periods',['なし'])))}
対象: {data.get('class','なし')}
科目: {data.get('subject','なし')}
教員: {data.get('teachers','なし')}
備考: {data.get('remark','なし')}"""


def compare(new, old_collection):
    '''
    新旧の休講情報を比較してデータベースに格納する
    '''
    c_insert = 0
    c_delete = 0
    for x in new:
        if not old_collection.find_one({'hash': x['hash']}):
            # 新しい情報
            old_collection.insert_one(x)
            # twitter_api.tweet(format_lecture(x))
            c_insert += 1
    # oldの今日以降の予定を見ていって、newになければ削除された
    for x in old_collection.find({'date': {'$gt': time.time()}}):
        if not next(filter(lambda e: e['hash'] == x['hash'], new), None):
            # 消された
            old_collection.delete_one({'hash': x['hash']})
            # twitter_api.tweet(format_lecture(x, prefix='【削除】\nこの休講情報は削除されました'))
            c_delete += 1
    log(__name__, f'Scraped: {len(new)} , Insert: {c_insert} , Delete: {c_delete}')


def append_class_num(lectures, syllabus):
    '''
    休講情報にシラバス番号を付加する
    シラバス番号から検索を行うため、曖昧で番号を求められなかった休講情報に対しては手動で探して付加する
    '''
    for lecture in lectures:
        class_num = lectures_class_num(lecture, syllabus)
        if class_num and not 'class_num' in lecture:
            lecture['class_num'] = class_num
    return lectures


def run():
    syllabus = list(get_collection('syllabus').find({}))
    compare(append_class_num(kyuukou(), syllabus), get_collection('lectures'))
    get_collection('lectures').insert_many(append_class_num(testdata(), syllabus))


if not isinpackage:
    from pprint import pprint
    pprint(kyuukou()[0])
