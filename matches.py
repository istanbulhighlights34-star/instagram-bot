"""Free match monitoring. Sources: ESPN football and Mackolik basketball."""
import argparse
import base64
from html.parser import HTMLParser
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont
import bot

UTC = timezone.utc
ISTANBUL = ZoneInfo('Europe/Istanbul')
STATE = Path('paylasilan_maclar.json')
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/soccer'


def get(url):
    response = requests.get(url, timeout=(5, 20))
    response.raise_for_status()
    return response.json()


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Saat dilimi belirtilmeyen maç saati')
    return result.astimezone(UTC)


def phase(match, now):
    age = now - match['start']
    if match['final'] and timedelta(0) <= age <= timedelta(hours=12):
        return 'result'
    if match['scheduled'] and -timedelta(minutes=30) <= age < timedelta(0):
        return 'pre'
    return None


def football(now):
    output = {}
    for league in ('tur.1', 'uefa.champions', 'uefa.europa', 'uefa.europa.conf', 'tur.cup'):
        try:
            # Scoreboards include live/final status; schedule alone may be stale.
            for day in (now.astimezone(ISTANBUL).date(), (now-timedelta(days=1)).astimezone(ISTANBUL).date()):
                data = get(f'{ESPN}/{league}/scoreboard?dates={day:%Y%m%d}&limit=100')
                for event in data.get('events', []):
                    c = event['competitions'][0]
                    teams = sorted(c['competitors'], key=lambda t: t['homeAway'] != 'home')
                    if not any(str(t['team']['id']) == '1895' for t in teams):
                        continue
                    status = c['status']['type']
                    final = status.get('completed') is True and status.get('name') in {
                        'STATUS_FULL_TIME', 'STATUS_FINAL', 'STATUS_END_OF_EXTRA_TIME', 'STATUS_END_OF_PENALTIES'}
                    match = {'id': f'football:{event["id"]}', 'event': event['id'], 'league': league,
                             'sport': 'FUTBOL', 'start': instant(event['date']), 'final': final,
                             'scheduled': status.get('name') == 'STATUS_SCHEDULED',
                             'teams': [{'id': str(t['team']['id']), 'name': t['team']['displayName'],
                                        'logo': t['team'].get('logo'), 'score': str(t.get('score', ''))} for t in teams]}
                    output[match['id']] = match
        except (requests.RequestException, KeyError, ValueError) as exc:
            bot.LOG.warning('Futbol kaynağı %s okunamadı: %s', league, type(exc).__name__)
    return list(output.values())


class Node:
    def __init__(self, tag='', attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []
    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()
    def cls(self, value):
        return [n for n in self.walk() if value in n.attrs.get('class','').split()]
    def text(self):
        return ' '.join(c.text() if isinstance(c,Node) else c for c in self.children).strip()


class MatchHTML(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.root = Node()
        self.stack = [self.root]
        self.feed(content)
    def handle_starttag(self, tag, attrs):
        node = Node(tag,attrs)
        self.stack[-1].children.append(node)
        if tag not in {'img','input','br','hr','meta','link','source','area','base','wbr','embed','param','col','track'}:
            self.stack.append(node)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break
    def handle_data(self, text):
        self.stack[-1].children.append(text)


BASKET_TEAM = '8z1xon628i3z0fzga522navq'
BASKET_URL = 'https://www.mackolik.com/basketbol/takim/be%C5%9Fikta%C5%9F-fibabanka/ma%C3%A7lar/'+BASKET_TEAM+'?view=all'


def html_page(url):
    response = requests.get(url, timeout=(5,20), headers={'User-Agent':'Mozilla/5.0'})
    response.raise_for_status()
    return MatchHTML(response.text).root


def parse_basketball_fixture(root):
    result = []
    prefix = 'p0c-team-matches__'
    for row in root.cls(prefix+'row'):
        buttons = row.cls(prefix+'button')
        if not buttons or not buttons[0].attrs.get('data-start-timestamp'):
            continue
        button = buttons[0]
        teams=[]
        for side in ('home','away'):
            nodes=row.cls(prefix+'team--'+side)
            if not nodes:
                break
            node=nodes[0]
            links=node.cls(prefix+'team-name')
            names=node.cls(prefix+'team-full-name')
            scores=node.cls(prefix+'score')
            if not links or not names:
                break
            team_id=links[0].attrs['href'].rstrip('/').split('/')[-1]
            teams.append({'id':'BES' if team_id==BASKET_TEAM else team_id,'name':names[0].text(),
                          'score':scores[0].text() if scores else '',
                          'logo':'https://secure.cache.images.core.optasports.com/basketball/teams/150x150/uuid_'+team_id+'.png'})
        if len(teams)!=2 or not any(t['id']=='BES' for t in teams):
            continue
        link=button.attrs['href']
        classes=button.attrs.get('class','').split()
        result.append({'id':'basketball:mackolik:'+link.rstrip('/').split('/')[-1], 'sport':'BASKETBOL',
                       'start':datetime.fromtimestamp(int(button.attrs['data-start-timestamp']),UTC),
                       'final':False,'scheduled':prefix+'button--start-time' in classes,
                       'teams':teams, 'detail':link})
    return result


def confirm_basketball_result(match, root):
    prefix='widget-basketball-match-details-header__'
    if not root.cls(prefix+'match-status--fullTime') or not root.cls(prefix+'match-status--postGame'):
        return False
    for team,side in zip(match['teams'],('home','away')):
        scores=root.cls(prefix+'score--'+side)
        if len(scores)!=1 or not scores[0].text().isdigit() or scores[0].text()!=team['score']:
            return False
    return match['teams'][0]['score'] != match['teams'][1]['score']


def basketball(now):
    result=[]
    try:
        for match in parse_basketball_fixture(html_page(BASKET_URL)):
            if now-timedelta(hours=12)<=match['start']<=now+timedelta(minutes=30):
                if match['start']<=now and all(t['score'].isdigit() for t in match['teams']):
                    match['final']=confirm_basketball_result(match,html_page(match['detail']))
                    match['scheduled']=False
                if match['scheduled']:
                    enrich_european_logos(match,now)
                result.append(match)
    except (requests.RequestException,KeyError,ValueError) as exc:
        bot.LOG.warning('Basketbol fikstürü okunamadı: %s',type(exc).__name__)
    return result


def enrich_european_logos(match, now):
    year=now.year if now.month>=7 else now.year-1
    for competition in ('E','U'):
        try:
            games=get(f'https://api-live.euroleague.net/v2/competitions/{competition}/seasons/{competition}{year}/games').get('data',[])
            for game in games:
                sides=[game['local'],game['road']]
                if instant(game['utcDate']) != match['start'] or not any(t['club']['code']=='BES' for t in sides):
                    continue
                if [t['id']=='BES' for t in match['teams']] != [t['club']['code']=='BES' for t in sides]:
                    continue
                for team,side in zip(match['teams'],sides):
                    team['logo']=side['club']['images'].get('crest') or team['logo']
                return
        except (requests.RequestException,KeyError,ValueError):
            continue


def starters(match):
    data = get(f'{ESPN}/{match["league"]}/summary?event={match["event"]}')
    for roster in data.get('rosters', []):
        if str(roster['team']['id']) == '1895':
            players = [p['athlete']['displayName'] for p in roster.get('roster', []) if p.get('starter') is True]
            if len(players) == 11 and len(set(players)) == 11:
                return players
    return []


def font(size):
    asset = Path(__file__).resolve().parent/'media'/'match-font.b64'
    return ImageFont.truetype(io.BytesIO(base64.b64decode(asset.read_text())),size)


def team_name(team):
    return 'Beşiktaş' if team['id'] in {'1895', 'BES'} else team['name']


def card(match, kind, players, path):
    picture = Image.new('RGB', (1080,1080), '#101319')
    draw = ImageDraw.Draw(picture)
    for y in range(1080):
        draw.line((0,y,1080,y), fill=(16+y//45,19+y//60,25+y//70))
    def centered(text, y, size=38):
        f = font(size)
        while draw.textbbox((0,0),text,font=f)[2] > 1000 and size > 14:
            size -= 2
            f = font(size)
        draw.text((540,y),text,font=f,fill='white',anchor='mt')
    centered('BEŞİKTAŞ • '+match['sport'], 200, 52)
    logo_y = 345 if players else 360
    logo_height = 145 if players else 190
    name_y = 510 if players else 600
    value_y = 565 if players else 745
    for x, team in zip((280,800), match['teams']):
        if not team.get('logo'):
            raise ValueError('Takım logosu eksik')
        response = requests.get(team['logo'], timeout=(5,15))
        response.raise_for_status()
        if len(response.content) > 8*1024*1024:
            raise ValueError('Logo boyutu sınırı aşıldı')
        logo = Image.open(io.BytesIO(response.content)).convert('RGBA')
        logo = logo.crop(logo.getbbox())
        # Exclude a separated sponsor word above the club crest when present.
        alpha = logo.getchannel('A').point(lambda value: 255 if value >= 20 else 0)
        gap_start = None
        for y in range(1,round(logo.height*.3)):
            blank = alpha.crop((0,y,logo.width,y+1)).getbbox() is None
            if blank and gap_start is None:
                gap_start = y
            if not blank and gap_start is not None:
                if y-gap_start >= max(3,round(logo.height*.01)) and gap_start > logo.height*.08:
                    logo = logo.crop((0,y,logo.width,logo.height))
                    logo = logo.crop(logo.getbbox())
                    break
                gap_start = None
        logo = logo.resize((round(logo.width*logo_height/logo.height),logo_height),Image.Resampling.LANCZOS)
        picture.paste(logo,(x-logo.width//2,logo_y),logo)
        name = team_name(team)
        size = 34
        while draw.textbbox((0,0),name,font=font(size))[2] > 440 and size > 18:
            size -= 2
        draw.text((x,name_y),name,font=font(size),fill='white',anchor='mt')
    subtitle = 'MAÇ SONUCU' if kind == 'result' else 'MAÇ GÜNÜ'
    watermark = bot.claw_mark((605,605),.28)
    watermark_top = (1080-watermark.height)//2 + watermark.getchannel('A').getbbox()[1]
    subtitle_height = draw.textbbox((0,0),subtitle,font=font(32),anchor='mt')[3]
    centered(subtitle,watermark_top-subtitle_height,32)
    centered('VS',logo_y+logo_height//2-15,32)
    centered(' : '.join(t['score'] for t in match['teams']) if kind == 'result' else match['start'].astimezone(ISTANBUL).strftime('%d.%m.%Y • %H:%M'),value_y,72 if kind=='result' else 42)
    if players:
        centered('İLK 11',635,30)
        for i, player in enumerate(players):
            draw.text((80 if i<6 else 580,685+(i if i<6 else i-6)*48),player,font=font(25),fill='white')
    picture.save(path,'JPEG',quality=95)
    bot.apply_claw_branding(path,path,framed=False)


MOTTOS = {
    'away': (
        'Bizim İçin Her Yer Beşiktaş!',
        'Mesafeler Değişir, Beşiktaş Sevgisi Değişmez!',
        'Armanın Peşinde, Yolların Ötesinde!',
        'Deplasmanda da Tek Yürek, Tek Beşiktaş!',
        'Yolumuz Uzun, Sevdamız Siyah Beyaz!',
        'Kartalın Kanatları Her Yere Uzanır!',
        'Nerede Oynarsan Oyna, Kalbimiz Seninle!',
        'Gidilecek Çok Deplasman Var!',
    ),
    'home': (
        'Burası Beşiktaş, Burası Bizim Evimiz!',
        'Semt Bizim, Aşk Bizim, Beşiktaş Bizim!',
        'Siyah Beyaz, Tek Yürek!',
        'Bugün Günlerden Beşiktaş!',
        'Armanın Peşinde, Omuz Omuza!',
        'Kalbimizde Beşiktaş, Tribünde Tek Ses!',
        'Evimizde Hep Birlikte, Son Düdüğe Kadar!',
        'Sen Ben Yok, Beşiktaş Var!',
    ),
}


def choose_motto(away, state):
    context = 'away' if away else 'home'
    records = [r for r in state.values() if isinstance(r, dict) and r.get('motto')]
    counts = {phrase: sum(r['motto'] == phrase for r in records) for phrase in MOTTOS[context]}
    last = max(records, key=lambda r:r.get('published_at',''), default={}).get('motto')
    candidates = [phrase for phrase in MOTTOS[context] if phrase != last]
    # Use every phrase before starting another cycle; oldest usage breaks ties.
    def order(phrase):
        latest = max((r.get('published_at','') for r in records if r['motto']==phrase), default='')
        return counts[phrase], latest
    return min(candidates, key=order)


def run(matches, now, dry_run=False):
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    for match in matches:
        kind = phase(match,now)
        key = match['id']+':'+str(kind)
        if not kind or key in state:
            continue
        players = starters(match) if kind=='pre' and match['sport']=='FUTBOL' else []
        if kind=='pre' and match['sport']=='FUTBOL' and not players:
            bot.LOG.warning('İlk 11 açıklanmadı; sonraki kontrolde yeniden bakılacak.')
            continue
        if kind=='result' and not all(t['score'].isdigit() for t in match['teams']):
            continue
        folder = Path('preview') if dry_run else Path('match_output')
        folder.mkdir(exist_ok=True)
        path = folder/(key.replace(':','-')+'.jpg')
        card(match,kind,players,path)
        caption = ('MAÇ SONUCU 🦅' if kind=='result' else 'MAÇ GÜNÜ 🦅')+'\n\n'+' — '.join(team_name(t) for t in match['teams'])
        caption += '\n'+(' : '.join(t['score'] for t in match['teams']) if kind=='result' else match['start'].astimezone(ISTANBUL).strftime('%d.%m.%Y %H:%M'))
        if players:
            caption += '\n\nİlk 11: '+', '.join(players)
        motto = None
        if kind == 'pre':
            away = match['teams'][1]['id'] in {'BES', '1895'}
            motto = choose_motto(away, state)
            caption += '\n\n' + motto + ' 💪🦅'
        caption += '\n\n#Beşiktaş #BJK #KaraKartal '+('#Basketbol #MaçGünü' if match['sport']=='BASKETBOL' else '#Futbol #MaçGünü')
        if dry_run:
            path.with_suffix('.txt').write_text(caption)
        else:
            media_id = bot.publish(path,caption)
            state[key] = {'media_id': str(media_id), 'published_at': now.isoformat(), 'motto': motto}
            temp = STATE.with_suffix('.tmp')
            temp.write_text(json.dumps(state,ensure_ascii=False,indent=2))
            temp.replace(STATE)
        bot.report_outcome(('Önizleme hazır: ' if dry_run else 'Maç paylaşımı doğrulandı: ')+caption.split('\n\n')[1])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true')
    args = parser.parse_args()
    now = datetime.now(UTC)
    run(football(now)+basketball(now),now,args.dry_run)
