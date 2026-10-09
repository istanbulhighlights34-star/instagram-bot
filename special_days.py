"""Calendar-based first posts. No claw asset is used in this renderer."""
import argparse
import base64
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
import io
import json
import logging
from pathlib import Path
import tempfile
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ISTANBUL = ZoneInfo('Europe/Istanbul')
STATE = Path('paylasilan_ozel_gunler.json')
CALENDAR = Path(__file__).parent / 'media' / 'special-calendar.json'
LOG = logging.getLogger(__name__)

# Texts describe the observance; there are no invented quotations or sports calls to action.
EVENTS = {
    'republic': ('29 EKİM', 'Cumhuriyet Bayramı', 'Cumhuriyet, ortak geleceğimizi özgürlük ve eşitlik temelinde kurma irademizdir. Cumhuriyetimizin kuruluşunu gururla kutluyor; Gazi Mustafa Kemal Atatürk’ü ve bağımsızlığımızın bütün kahramanlarını saygı ve minnetle anıyoruz.', 'Turkish flag', '#29Ekim #CumhuriyetBayramı', 'national'),
    'children': ('23 NİSAN', 'Ulusal Egemenlik ve Çocuk Bayramı', 'Türkiye Büyük Millet Meclisinin açıldığı bu gün, millet egemenliğinin ve çocuklara duyulan güvenin simgesidir. Her çocuğun güvenle büyüdüğü, hayallerini özgürce kurduğu bir gelecek dileğiyle 23 Nisan kutlu olsun.', 'Turkish flag', '#23Nisan #UlusalEgemenlikVeÇocukBayramı', 'national'),
    'youth': ('19 MAYIS', 'Atatürk’ü Anma, Gençlik ve Spor Bayramı', '19 Mayıs 1919’da Samsun’da başlayan bağımsızlık yolculuğunu ve bu yolculuğun gençlere emanet edilen umudunu anıyoruz. Gazi Mustafa Kemal Atatürk’ü saygı ve minnetle anıyor; gençliğin ve sporun bayramını kutluyoruz.', 'Mustafa Kemal Atatürk', '#19Mayıs #GençlikVeSporBayramı', 'national'),
    'victory': ('30 AĞUSTOS', 'Zafer Bayramı', '30 Ağustos, bağımsızlık uğruna verilen mücadelenin ve ortak iradenin zaferidir. Başkomutan Gazi Mustafa Kemal Atatürk’ü ve bütün kahramanlarımızı saygı, rahmet ve minnetle anıyoruz. Zafer Bayramımız kutlu olsun.', 'Turkish flag', '#30Ağustos #ZaferBayramı', 'national'),
    'democracy': ('15 TEMMUZ', 'Demokrasi ve Millî Birlik Günü', 'Demokrasiyi ve ortak yaşamımızı korumanın değerini hatırlıyoruz. 15 Temmuz’da yaşamını yitirenleri rahmetle, gazilerimizi saygıyla anıyor; barış, birlik ve dayanışma içinde bir gelecek diliyoruz.', 'Turkish flag', '#15Temmuz #DemokrasiVeMillîBirlikGünü', 'memorial'),
    'ataturk': ('10 KASIM', 'Saygı, özlem ve minnetle', '10 Kasım…\n\nCumhuriyetimizin kurucusu Gazi Mustafa Kemal Atatürk’ü aramızdan ayrılışının yıl dönümünde derin bir özlem, saygı ve minnetle anıyoruz.\n\nEmanetine ve açtığı yola sahip çıkma sorumluluğuyla…', 'Mustafa Kemal Atatürk portrait', '#10Kasım #Atatürk #SaygıylaAnıyoruz', 'memorial'),
    'labour': ('1 MAYIS', 'Emek ve Dayanışma Günü', 'Hayatı alın teriyle kuran herkesin emeğine saygıyla… Daha adil, güvenli ve dayanışma içinde bir çalışma yaşamı dileğiyle 1 Mayıs Emek ve Dayanışma Günü kutlu olsun.', 'Istanbul sunrise', '#1Mayıs #EmekVeDayanışma', 'national'),
    'newyear': ('YENİ YIL', 'Sağlık, huzur ve umutla', 'Yeni yılın herkese sağlık, huzur ve güzel başlangıçlar getirmesini diliyoruz. Birlikte daha çok iyiliği, dayanışmayı ve güzel anıları paylaşacağımız bir yıl olsun.', 'Istanbul sunrise', '#YeniYıl #MutluYıllar', 'national'),
    'ramazan': ('RAMAZAN BAYRAMI', 'Birlikte, sevgiyle', 'Ramazan Bayramı; paylaşmayı, yakınlarımızı hatırlamayı ve kırgınlıkları geride bırakmayı yeniden hatırlatıyor. Bayramın bütün evlere huzur, sofralara bereket ve kalplere iyilik getirmesini diliyoruz. İyi bayramlar.', 'Istanbul mosque', '#RamazanBayramı #İyiBayramlar', 'islamic'),
    'kurban': ('KURBAN BAYRAMI', 'Paylaşmanın ve dayanışmanın bayramı', 'Kurban Bayramı’nın paylaşma, yardımlaşma ve yakınlaşma duygularını güçlendirmesini diliyoruz. Sevdiklerinizle sağlık ve huzur içinde geçireceğiniz bir bayram olsun. İyi bayramlar.', 'Istanbul mosque', '#KurbanBayramı #İyiBayramlar', 'islamic'),
    'regaib': ('REGAİP KANDİLİ', 'İyilik, umut ve dua', 'Regaip Kandili’nin kalplere huzur, evlere bereket ve hayatımıza iyilik getirmesini diliyoruz. Bu anlamlı gecede dualarınızın kabul olması ve dayanışmanın güçlenmesi dileğiyle kandiliniz mübarek olsun.', 'Istanbul mosque night', '#RegaipKandili #HayırlıKandiller', 'islamic'),
    'mirac': ('MİRAÇ KANDİLİ', 'Huzur ve manevi yakınlık', 'İslam geleneğinde Hz. Muhammed’in miraç yolculuğunun anıldığı bu gecenin, manevi yakınlığa ve iyiliğe vesile olmasını diliyoruz. Miraç Kandiliniz mübarek olsun.', 'Istanbul mosque night', '#MiraçKandili #HayırlıKandiller', 'islamic'),
    'berat': ('BERAT KANDİLİ', 'Bağışlanma ve yenilenme', 'Berat Kandili, bağışlanma dileğini ve daha iyi bir insan olma niyetini hatırlatan bir gecedir. Kalplerimizin hafiflediği, iyiliklerin çoğaldığı bir gece dileğiyle kandiliniz mübarek olsun.', 'Istanbul mosque night', '#BeratKandili #HayırlıKandiller', 'islamic'),
    'kadir': ('KADİR GECESİ', 'Dua, merhamet ve huzur', 'Kur’an’ın indirilmeye başlandığı gece olarak anılan Kadir Gecesi’nin; merhameti, paylaşmayı ve barış umudunu güçlendirmesini diliyoruz. Dualarınızın kabul olması dileğiyle Kadir Geceniz mübarek olsun.', 'Istanbul mosque night', '#KadirGecesi #HayırlıKandiller', 'islamic'),
    'mevlid': ('MEVLİD KANDİLİ', 'Merhamet ve güzel ahlak', 'Hz. Muhammed’in doğumunun anıldığı Mevlid Kandili’nin, merhamet ve güzel ahlak üzerine düşünmeye vesile olmasını diliyoruz. Kalplere huzur ve hayatımıza iyilik getirmesi dileğiyle kandiliniz mübarek olsun.', 'Istanbul mosque night', '#MevlidKandili #HayırlıKandiller', 'islamic'),
    'ramadan-start': ('HOŞ GELDİN RAMAZAN', 'Paylaşma ve dayanışma zamanı', 'Ramazan ayının başlangıcında; paylaşmanın, sabrın ve yardımlaşmanın bütün hayatımıza yayılmasını diliyoruz. Bu ayın herkese sağlık, huzur ve bereket getirmesi dileğiyle hayırlı Ramazanlar.', 'Istanbul mosque', '#Ramazan #HayırlıRamazanlar', 'islamic'),
    'ashura': ('AŞURE GÜNÜ', 'Paylaşma ve birlik', 'Aşure Günü’nün paylaşmayı, farklılıklarımızla bir arada yaşamayı ve dayanışmayı güçlendirmesini diliyoruz. Muharrem’in anlamını saygıyla hatırlıyor; bütün kalplere huzur ve barış diliyoruz.', 'ashure dessert', '#AşureGünü #Dayanışma', 'islamic'),
    'christmas': ('NOEL', 'Barış, sevgi ve umut', 'Hz. İsa’nın doğumunun kutlandığı Noel’de, bu günü yaşayan bütün Hristiyan dostlarımıza huzur ve esenlik diliyoruz. Sevginin, dayanışmanın ve barış umudunun çoğaldığı bir bayram olsun.', 'Christmas candles', '#Noel #BarışVeSevgi', 'christian'),
    'epiphany': ('EPİFANİ / THEOFANİ', 'Işık ve manevi yenilenme', 'Hristiyan geleneklerinde Epifani ve Theofani olarak anılan bu özel günde, bayramı yaşayan dostlarımıza huzur ve esenlik diliyoruz. Ermeni Apostolik geleneğinde bugün kutlanan Noel’i de sevgi ve saygıyla karşılıyoruz.', 'church candles', '#Epifani #Theofani', 'christian'),
    'easter-west': ('PASKALYA', 'Yeniden doğan umut', 'Hz. İsa’nın dirilişinin anıldığı Paskalya’yı bugün kutlayan Katolik ve Protestan dostlarımıza esenlik diliyoruz. Umudun, sevginin ve barışın bütün hayatımıza yayıldığı bir bayram olsun.', 'Easter eggs', '#Paskalya #BarışVeSevgi', 'christian'),
    'easter-east': ('ORTODOKS PASKALYASI', 'Umut, sevgi ve esenlik', 'Paskalya’yı bugün yaşayan Ortodoks dostlarımızın bayramını kutluyoruz. Dirilişin ve yenilenen umudun anıldığı bu günün bütün evlere huzur, kalplere sevgi getirmesini diliyoruz.', 'Easter eggs', '#Paskalya #OrtodoksPaskalyası', 'christian'),
    'good-friday-west': ('KUTSAL CUMA', 'Saygıyla ve sükûnetle', 'Hz. İsa’nın çarmıha gerilişinin anıldığı Kutsal Cuma’da, bu günü yaşayan Katolik ve Protestan dostlarımızın manevi duygularına saygıyla eşlik ediyoruz. Barış, merhamet ve insan onuru üzerine düşünmek için anlamlı bir gün.', 'church candles', '#KutsalCuma #Barış', 'memorial'),
    'good-friday-east': ('ORTODOKS KUTSAL CUMASI', 'Saygıyla ve sükûnetle', 'Ortodoks Hristiyanların Hz. İsa’nın çarmıha gerilişini andığı bu günde, manevi duygularına saygıyla eşlik ediyoruz. Merhametin ve barış umudunun hayatımızda çoğalmasını diliyoruz.', 'church candles', '#KutsalCuma #Barış', 'memorial'),
    'pentecost-west': ('PENTEKOST', 'Birlik ve manevi dayanışma', 'Kutsal Ruh’un havarilere inişinin anıldığı Pentekost’u bugün kutlayan Katolik ve Protestan dostlarımıza huzur ve esenlik diliyoruz. Sevgi ve dayanışma içinde bir bayram olsun.', 'church candles', '#Pentekost #Dayanışma', 'christian'),
    'pentecost-east': ('ORTODOKS PENTEKOSTU', 'Birlik ve manevi dayanışma', 'Pentekost’u bugün yaşayan Ortodoks dostlarımıza huzur ve esenlik diliyoruz. Bu bayramın birlik, sevgi ve dayanışma duygularını güçlendirmesini diliyoruz.', 'church candles', '#Pentekost #Dayanışma', 'christian'),
    'ascension-west': ('YÜKSELİŞ BAYRAMI', 'Umut ve manevi yakınlık', 'Hz. İsa’nın göğe yükselişinin anıldığı bu bayramı bugün yaşayan Katolik ve Protestan dostlarımıza huzur ve esenlik diliyoruz. Umudun ve iyiliğin çoğaldığı bir gün olsun.', 'church candles', '#YükselişBayramı #Barış', 'christian'),
    'ascension-east': ('ORTODOKS YÜKSELİŞ BAYRAMI', 'Umut ve manevi yakınlık', 'Hz. İsa’nın göğe yükselişini bugün anan Ortodoks dostlarımıza huzur ve esenlik diliyoruz. Manevi duygularına sevgi ve saygıyla eşlik ediyoruz.', 'church candles', '#YükselişBayramı #Barış', 'christian'),
    'annunciation': ('MÜJDE BAYRAMI', 'Umut ve esenlik', 'Hz. Meryem’e Hz. İsa’nın doğumunun müjdelenmesinin anıldığı bu bayramı bugün yaşayan Hristiyan dostlarımıza huzur ve esenlik diliyoruz. Bu anlamlı günün umut ve barış duygularını güçlendirmesi dileğiyle.', 'church candles', '#MüjdeBayramı #Barış', 'christian'),
    'mary': ('15 AĞUSTOS', 'Huzur ve esenlik dileğiyle', 'Katolik ve Ortodoks geleneklerinde Hz. Meryem’e adanan bu önemli günde, bayramı yaşayan Hristiyan dostlarımızın manevi duygularına saygıyla eşlik ediyoruz. Huzur ve esenlik diliyoruz.', 'church candles', '#15Ağustos #BarışVeSevgi', 'christian'),
}
FIXED = {'01-01':'newyear','01-06':'epiphany','04-23':'children','05-01':'labour', '05-19':'youth','07-15':'democracy','08-30':'victory','10-29':'republic','11-10':'ataturk','12-25':'christmas','01-07':'christmas'}
FIXED.update({'03-25':'annunciation','08-15':'mary'})


def easter(year, orthodox=False):
    if orthodox:
        a, b, c = year % 4, year % 7, year % 19
        d = (19*c + 15) % 30
        e = (2*a + 4*b - d + 34) % 7
        return date(year, (d+e+114)//31, (d+e+114)%31+1) + timedelta(days=year//100-year//400-2)
    a, b, c = year%19, year//100, year%100
    d, e = b//4, b%4
    f = (b+8)//25
    g = (b-f+1)//3
    h = (19*a+b-d-g+15)%30
    i, k = c//4, c%4
    l = (32+2*e+2*i-h-k)%7
    m = (a+11*h+22*l)//451
    n = h+l-7*m+114
    return date(year,n//31,n%31+1)


class CalendarRows(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None; self.links=[]; self.link=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.row=[]
        if tag in ('td','th') and self.row is not None: self.cell=[]
        if tag=='a': self.link=[dict(attrs).get('href',''),[]]
    def handle_data(self,value):
        if self.cell is not None: self.cell.append(value)
        if self.link is not None: self.link[1].append(value)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(' '.join(' '.join(self.cell).split())); self.cell=None
        if tag=='tr' and self.row is not None:
            self.rows.append(self.row); self.row=None
        if tag=='a' and self.link is not None:
            self.links.append((self.link[0],''.join(self.link[1]))); self.link=None


def refresh_calendar(year):
    """Future years must come from Diyanet; never estimate lunar observances."""
    import bot
    url=f'https://vakithesaplama.diyanet.gov.tr/dinigunler.php?yil={year}'
    response=requests.get(url,timeout=(5,20)); response.raise_for_status()
    parser=CalendarRows(); parser.feed(response.content.decode('utf-8'))
    if not any(len(row)==7 and str(year) in row[4] for row in parser.rows):
        from urllib.parse import urljoin
        target=next((href for href,title in parser.links if str(year)+' Yılı Dini Günler' in title),None)
        if target:
            url=urljoin(url,target)
            if urlsplit(url).hostname!='vakithesaplama.diyanet.gov.tr':
                raise RuntimeError('Takvim kaynağı doğrulanamadı.')
            response=requests.get(url,timeout=(5,20));response.raise_for_status()
            parser=CalendarRows();parser.feed(response.content.decode('utf-8'))
    months={'ocak':1,'subat':2,'mart':3,'nisan':4,'mayis':5,'haziran':6,'temmuz':7,'agustos':8,'eylul':9,'ekim':10,'kasim':11,'aralik':12}
    labels={'mirac kandili':'mirac','berat kandili':'berat','ramazan baslangici':'ramadan-start','kadir gecesi':'kadir','ramazan bayrami':'ramazan','kurban bayrami':'kurban','asure gunu':'ashura','mevlid kandili':'mevlid','regaib kandili':'regaib','regaip kandili':'regaib'}
    dates={}
    for row in parser.rows:
        if len(row)!=7: continue
        label=bot.subject_key(row[6])
        key=next((value for text,value in labels.items() if label.startswith(text)),None)
        month_text=bot.subject_key(row[4])
        month=next((value for text,value in months.items() if month_text.startswith(text+' ')),None)
        if key and month and str(year) in month_text:
            day=date(year,month,int(row[3].replace(' ',''))).isoformat()
            dates.setdefault(day,[]).append(key)
    if len(dates)<12 or not all(any(k in values for values in dates.values()) for k in ('ramazan','kurban','kadir','mirac','berat','mevlid','regaib')):
        raise RuntimeError('Yeni yılın Diyanet takvimi doğrulanamadı.')
    data=json.loads(CALENDAR.read_text())
    data['years'][str(year)]=dates;data['sources'][str(year)]=url
    CALENDAR.write_text(json.dumps(data,ensure_ascii=False,indent=2))


def events_on(day):
    keys = []
    if day.strftime('%m-%d') in FIXED:
        keys.append(FIXED[day.strftime('%m-%d')])
    data = json.loads(CALENDAR.read_text())
    if str(day.year) not in data['years']:
        refresh_calendar(day.year)
        data = json.loads(CALENDAR.read_text())
    keys.extend(data['years'][str(day.year)].get(day.isoformat(), []))
    for orthodox, suffix in [(False,'west'),(True,'east')]:
        delta = (day-easter(day.year,orthodox)).days
        if delta in (-2,0,39,49):
            keys.append({-2:'good-friday-',0:'easter-',39:'ascension-',49:'pentecost-'}[delta]+suffix)
    return list(dict.fromkeys(keys))


def local_now(now=None):
    return (now or datetime.now(ISTANBUL)).astimezone(ISTANBUL)


def read_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def first_post_pending(now=None):
    day = local_now(now).date()
    keys = events_on(day)
    state = read_state()
    return any(state.get(day.isoformat()+':'+key,{}).get('status') != 'published' for key in keys)


def save_state(state):
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state,ensure_ascii=False,indent=2))
    temp.replace(STATE)


def photo_candidates(query):
    preferred=[]
    if 'mosque' in query:
        preferred=['SüleymaniyeMosqueIstanbul.jpg','Süleymaniye Mosque viewed from Galata Tower, Istanbul, 2024.jpg']
    elif query=='church candles':
        preferred=['Candles and windows st Johns Lutheran.jpg']
    if preferred:
        response=requests.get('https://commons.wikimedia.org/w/api.php',params={
            'action':'query','format':'json','titles':'|'.join('File:'+name for name in preferred),
            'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':1080},
            headers={'User-Agent':'KartalpencheSpecialDays/1.0'},timeout=(5,20))
        response.raise_for_status()
        yield from response.json().get('query',{}).get('pages',{}).values()
    for search in (query+' incategory:CC-Zero', query):
        response = requests.get('https://commons.wikimedia.org/w/api.php', params={
            'action':'query','format':'json','generator':'search','gsrsearch':search,
            'gsrnamespace':6,'gsrlimit':12,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':1400},
            headers={'User-Agent':'KartalpencheSpecialDays/1.0'},timeout=(5,20))
        response.raise_for_status()
        yield from sorted(response.json().get('query',{}).get('pages',{}).values(),key=lambda p:p.get('index',99))


def download_photo(event, destination):
    """Search real public-domain photographs; no attribution line is added to captions."""
    query = EVENTS[event][3].replace(' night','')
    if query=='Christmas candles': query='church candles'
    for page in photo_candidates(query):
        title=page.get('title','').casefold()
        if any(word in title for word in ('cemetery','grave','tomb','kfc','advert','logo','screenshot','painting','drawing')):
            continue
        for info in page.get('imageinfo',[]):
            meta = info.get('extmetadata',{})
            license_name = meta.get('LicenseShortName',{}).get('value','').casefold()
            if license_name not in ('cc0','public domain','pd'):
                continue
            for candidate in dict.fromkeys([info['url'],info.get('thumburl',info['url'])]):
                parts=urlsplit(candidate)
                if parts.scheme!='https' or parts.netloc not in ('upload.wikimedia.org','thumb.wikimedia.org'):
                    continue
                url=urlunsplit((parts.scheme,parts.netloc,parts.path,'',''))
                try:
                    with requests.get(url,stream=True,timeout=(5,20),headers={'User-Agent':'KartalpencheSpecialDays/1.0'}) as photo:
                        photo.raise_for_status()
                        raw=bytearray()
                        for chunk in photo.iter_content(65536):
                            raw.extend(chunk)
                            if len(raw)>15*1024*1024: raise ValueError('Fotoğraf boyutu sınırı aşıldı.')
                    with Image.open(io.BytesIO(raw)) as image:
                        if min(image.size)<400 or image.width*image.height>60000000: continue
                        ImageOps.exif_transpose(image).convert('RGB').save(destination,'JPEG',quality=95)
                    return {'source':info.get('descriptionurl',''),'photo_url':url,'license':license_name}
                except (requests.RequestException,ValueError,OSError) as exc:
                    LOG.warning('Özel gün fotoğrafı indirilemedi: %s (%s)',page.get('title',''),type(exc).__name__)
    raise RuntimeError('Güne uygun gerçek fotoğraf bulunamadı; spor fotoğrafıyla değiştirilmedi.')


def render_card(source, destination, event):
    title, subtitle, _, _, _, kind = EVENTS[event]
    font_data = base64.b64decode((Path(__file__).parent/'media/match-font.b64').read_text())
    def font(size): return ImageFont.truetype(io.BytesIO(font_data),size)
    muted = kind=='memorial'
    accent = '#b9b9b9' if muted else {'christian':'#c9aa68','islamic':'#b9a46a'}.get(kind,'#cf263e')
    with Image.open(source) as raw:
        photo = ImageOps.pad(ImageOps.exif_transpose(raw).convert('RGB'),(1000,910),color='#101216')
        if muted: photo=ImageOps.grayscale(photo).convert('RGB')
    canvas=Image.new('RGB',(1080,1350),'#101216')
    canvas.paste(photo,(40,140))
    draw=ImageDraw.Draw(canvas)
    draw.rectangle((22,22,1057,1327),outline=accent,width=3)
    draw.text((540,68),'KARTALPENCHE1903',font=font(35),fill='#e7e7e7',anchor='mm')
    draw.line((65,111,1015,111),fill=accent,width=2)
    size=76
    while draw.textlength(title,font=font(size))>940: size-=2
    draw.text((540,1130),title,font=font(size),fill=accent,anchor='mm')
    size=42
    while draw.textlength(subtitle,font=font(size))>950: size-=2
    draw.text((540,1230),subtitle,font=font(size),fill='#eeeeee',anchor='mm')
    canvas.save(destination,'JPEG',quality=95)


def run(now=None,dry_run=False,preview_date=None):
    import bot
    now=local_now(now)
    if preview_date and not dry_run:
        raise ValueError('Başka tarihte gerçek paylaşım yapılamaz.')
    day=preview_date or now.date()
    keys=events_on(day)
    state=read_state()
    # 10 November starts at 08:30 to allow completion before 09:05.
    start=(8,30) if 'ataturk' in keys else (8,0)
    if not dry_run and (now.hour,now.minute)<start:
        return
    for key in keys:
        identity=day.isoformat()+':'+key
        previous=state.get(identity,{})
        if not dry_run and previous.get('status') in ('published','uploading','uncertain'):
            continue
        folder=Path('preview') if dry_run else Path('special_output')
        folder.mkdir(exist_ok=True)
        path=folder/(day.isoformat()+'-'+key+'.jpg')
        with tempfile.TemporaryDirectory(prefix='special-day-') as temp:
            source=Path(temp)/'source.jpg'
            provenance=download_photo(key,source)
            render_card(source,path,key)
        caption=EVENTS[key][2]+'\n\n'+EVENTS[key][4]
        # A separate preview/source artifact, never appended to the Instagram caption.
        path.with_suffix('.txt').write_text(caption)
        path.with_suffix('.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2))
        if dry_run:
            bot.report_outcome('Filigransız özel gün önizlemesi hazır: '+EVENTS[key][0])
            continue
        state[identity]={'status':'uploading','started_at':now.isoformat()}
        save_state(state)
        try:
            media_id=bot.publish(path,caption)
        except Exception:
            state[identity]['status']='uncertain'
            save_state(state)
            bot.report_outcome('Özel gün paylaşım sonucu belirsiz; çift gönderi olmaması için tekrar gönderilmeyecek.')
            raise
        state[identity].update(status='published',media_id=str(media_id))
        save_state(state)
        bot.report_outcome('Günün ilk özel paylaşımı doğrulandı: '+EVENTS[key][0])


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    parser=argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--date',type=date.fromisoformat,help='Only for dry-run previews')
    args=parser.parse_args()
    run(dry_run=args.dry_run,preview_date=args.date)
