"""Free match monitoring. Sources: ESPN football and EuroLeague/EuroCup."""
import argparse
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


def basketball_finished(header):
    try:
        minutes, seconds = map(int, header['GameTime'].split(':'))
        a, b = int(header['ScoreA']), int(header['ScoreB'])
        return (header.get('Live') is False and header.get('Quarter') == ''
                and header.get('RemainingPartialTime') == '00:00'
                and minutes >= 40 and minutes % 5 == 0 and seconds == 0
                and a != b and a > 0 and b > 0)
    except (KeyError, ValueError, TypeError):
        return False


def basketball(now):
    output = []
    year = now.year if now.month >= 7 else now.year-1
    for competition in ('E', 'U'):
        season = f'{competition}{year}'
        try:
            data = get(f'https://api-live.euroleague.net/v2/competitions/{competition}/seasons/{season}/games')
            for game in data.get('data', []):
                sides = [game['local'], game['road']]
                if not any(t['club']['code'] == 'BES' for t in sides):
                    continue
                start = instant(game['utcDate'])
                if not now-timedelta(hours=12) <= start <= now+timedelta(minutes=30):
                    continue
                final = False
                if game.get('played'):
                    header = get(f'https://live.euroleague.net/api/Header?gamecode={game["gameCode"]}&seasoncode={season}')
                    # A stopped clock alone is insufficient: require explicit end marker.
                    final = basketball_finished(header) and all(str(side['score']) == str(header.get(field, '')) for side, field in zip(sides, ('ScoreA', 'ScoreB')))
                output.append({'id': f'basketball:{game["identifier"]}', 'sport': 'BASKETBOL',
                               'start': start, 'final': final,
                               'scheduled': not game.get('played') and game.get('confirmedDate') is True and game.get('confirmedHour') is True and game.get('gameStatus') == 'Confirmed',
                               'teams': [{'id': t['club']['code'], 'name': t['club']['name'],
                                          'logo': t['club']['images'].get('crest'), 'score': str(t['score'])} for t in sides]})
        except (requests.RequestException, KeyError, ValueError) as exc:
            bot.LOG.warning('Basketbol kaynağı %s okunamadı: %s', season, type(exc).__name__)
    return output


def starters(match):
    data = get(f'{ESPN}/{match["league"]}/summary?event={match["event"]}')
    for roster in data.get('rosters', []):
        if str(roster['team']['id']) == '1895':
            players = [p['athlete']['displayName'] for p in roster.get('roster', []) if p.get('starter') is True]
            if len(players) == 11 and len(set(players)) == 11:
                return players
    return []


def font(size):
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/Library/Fonts/Arial.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf'):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError('Türkçe yazı tipi bulunamadı')


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
    centered('BEŞİKTAŞ • '+match['sport'], 60, 44)
    for x, team in zip((280,800), match['teams']):
        if not team.get('logo'):
            raise ValueError('Takım logosu eksik')
        response = requests.get(team['logo'], timeout=(5,15))
        response.raise_for_status()
        if len(response.content) > 8*1024*1024:
            raise ValueError('Logo boyutu sınırı aşıldı')
        logo = Image.open(io.BytesIO(response.content)).convert('RGBA')
        logo.thumbnail((190,190))
        picture.paste(logo,(x-logo.width//2,190),logo)
    centered('MAÇ SONUCU' if kind == 'result' else 'MAÇ GÜNÜ',130,30)
    centered(' — '.join(team_name(t) for t in match['teams']), 410, 35)
    centered(' : '.join(t['score'] for t in match['teams']) if kind == 'result' else match['start'].astimezone(ISTANBUL).strftime('%d.%m.%Y • %H:%M'),480,72 if kind=='result' else 42)
    if players:
        centered('İLK 11',565,30)
        for i, player in enumerate(players):
            draw.text((80 if i<6 else 580,625+(i if i<6 else i-6)*52),player,font=font(25),fill='white')
    picture.save(path,'JPEG',quality=95)
    bot.apply_claw_branding(path,path,framed=False)


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
        caption += '\n\n#Beşiktaş #BJK #KaraKartal '+('#Basketbol #MaçGünü' if match['sport']=='BASKETBOL' else '#Futbol #MaçGünü')
        if dry_run:
            path.with_suffix('.txt').write_text(caption)
        else:
            media_id = bot.publish(path,caption)
            state[key] = {'media_id': str(media_id), 'published_at': now.isoformat()}
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
