import requests, re, csv, time
from datetime import datetime

CLIENT_ID     = 'f4qhitulro8pw74cuvlz12sn54j84d'
CLIENT_SECRET = '962eit7ahpu2o0yohz3mi12ruxwl6o'
FOLLOWER_MIN  = 1000
FOLLOWER_MAX  = 10000

USA_KEYWORDS = ['usa','united states','u.s.','american','pst','est','cst','mst',
'pacific time','eastern time','central time','mountain time','california','texas',
'florida','new york','ohio','washington','illinois','georgia','colorado','arizona']

def get_token():
    r = requests.post('https://id.twitch.tv/oauth2/token', data={
        'client_id':CLIENT_ID,'client_secret':CLIENT_SECRET,'grant_type':'client_credentials'})
    return r.json()['access_token']

def hdrs(token):
    return {'Client-ID':CLIENT_ID,'Authorization':f'Bearer {token}'}

def extract_email(text):
    m = re.search(r'[\w.+%\-]+@[\w.\-]+\.[a-zA-Z]{2,}', text or '')
    return m.group(0) if m else ''

def extract_twitter(text):
    for p in [r'(?:twitter\.com|x\.com)/(@?[\w]+)',r'twitter[:\s]+@?([\w]+)',r'🐦[:\s]*@?([\w]+)']:
        m = re.search(p, text or '', re.IGNORECASE)
        if m:
            h = m.group(1).lstrip('@')
            if h.lower() not in ('twitch','youtube','gmail','discord','instagram'):
                return f'https://twitter.com/{h}'
    return ''

def is_usa(text):
    t = (text or '').lower()
    return any(k in t for k in USA_KEYWORDS)

token = get_token()
print('Token OK，开始搜索...')

streams, cursor, page = [], None, 0
while page < 15:
    params = {'first':100,'language':'en','type':'live'}
    if cursor: params['after'] = cursor
    d = requests.get('https://api.twitch.tv/helix/streams', headers=hdrs(token), params=params).json()
    batch = d.get('data',[])
    if not batch: break
    vt = [s for s in batch if s.get('tags') and any('vtuber' in t.lower() for t in s['tags'])]
    streams.extend(vt)
    cursor = d.get('pagination',{}).get('cursor')
    page += 1
    print(f'第{page}页，VTuber累计:{len(streams)}')
    if not cursor: break
    time.sleep(0.3)

seen, unique = set(), []
for s in streams:
    if s['user_id'] not in seen:
        seen.add(s['user_id']); unique.append(s)
print(f'去重后:{len(unique)}个，获取粉丝数...')

fmap = {}
for i,s in enumerate(unique):
    r = requests.get('https://api.twitch.tv/helix/channels/followers',
        headers=hdrs(token), params={'broadcaster_id':s['user_id'],'first':1})
    fmap[s['user_id']] = r.json().get('total',0) if r.status_code==200 else 0
    if (i+1)%10==0: print(f'粉丝数进度:{i+1}/{len(unique)}')
    time.sleep(0.15)

filtered = [s for s in unique if FOLLOWER_MIN <= fmap.get(s['user_id'],0) <= FOLLOWER_MAX]
print(f'符合粉丝量条件:{len(filtered)}个，获取简介...')

dmap = {}
for i in range(0, len(filtered), 100):
    chunk = filtered[i:i+100]
    params = [('login', s['user_login']) for s in chunk]
    r = requests.get('https://api.twitch.tv/helix/users', headers=hdrs(token), params=params)
    for u in r.json().get('data',[]):
        dmap[u['login'].lower()] = u
    time.sleep(0.3)

results = []
for s in filtered:
    detail = dmap.get(s['user_login'].lower(), {})
    bio = detail.get('description','')
    txt = bio + ' ' + s.get('title','')
    results.append({
        '名字': s['user_name'],
        'Twitch': f"https://twitch.tv/{s['user_login']}",
        '粉丝量': fmap.get(s['user_id'],0),
        '最近直播': datetime.now().strftime('%Y-%m-%d'),
        'Twitter': extract_twitter(txt),
        '邮箱': extract_email(txt),
        '含美国标识': '是' if is_usa(txt) else '否',
    })

results.sort(key=lambda x: x['粉丝量'], reverse=True)
fname = f'vtuber_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
with open(fname,'w',newline='',encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=results[0].keys())
    w.writeheader(); w.writerows(results)

print(f'\n完成！共{len(results)}个，已保存到 {fname}')
for r in results[:5]:
    print(f"{r['名字']:<20} {r['粉丝量']:>7,}  {r['邮箱'] or '无邮箱'}")