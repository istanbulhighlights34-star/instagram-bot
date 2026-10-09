import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import tempfile
from pathlib import Path
import matches

class MatchTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,9,12,tzinfo=timezone.utc)
        self.match={'id':'test','start':self.now+timedelta(minutes=30),'final':False,'scheduled':True,'sport':'FUTBOL'}
    def test_pre_window(self):
        self.assertEqual(matches.phase(self.match,self.now),'pre')
        self.assertIsNone(matches.phase(self.match,self.now-timedelta(seconds=1)))
        self.assertIsNone(matches.phase(self.match,self.match['start']))
    def test_postponed(self):
        self.match['scheduled']=False
        self.assertIsNone(matches.phase(self.match,self.now))
    def test_final_recent_only(self):
        self.match.update(final=True,scheduled=False,start=self.now-timedelta(hours=2))
        self.assertEqual(matches.phase(self.match,self.now),'result')
        self.match['start']=self.now-timedelta(days=1)
        self.assertIsNone(matches.phase(self.match,self.now))
    def test_timezone(self):
        self.assertEqual(matches.instant('2026-10-09T15:00:00+03:00'),self.now)
        with self.assertRaises(ValueError):matches.instant('2026-10-09T15:00:00')
    def test_lineup_requires_eleven(self):
        self.match.update(league='tur.1',event='1')
        roster={'team':{'id':'1895'},'roster':[{'starter':True,'athlete':{'displayName':str(i)}} for i in range(10)]}
        with patch('matches.get',return_value={'rosters':[roster]}):self.assertEqual(matches.starters(self.match),[])
        roster['roster'].append({'starter':True,'athlete':{'displayName':'10'}})
        with patch('matches.get',return_value={'rosters':[roster]}):self.assertEqual(len(matches.starters(self.match)),11)
    def test_basketball_final_requires_explicit_finished_status(self):
        m={'teams':[{'score':'90'},{'score':'81'}]}
        html='<div class="widget-basketball-match-details-header__match-status--fullTime widget-basketball-match-details-header__match-status--postGame">MS</div><span class="widget-basketball-match-details-header__score--home">90</span><span class="widget-basketball-match-details-header__score--away">81</span>'
        self.assertTrue(matches.confirm_basketball_result(m,matches.MatchHTML(html).root))
        self.assertFalse(matches.confirm_basketball_result(m,matches.MatchHTML(html.replace('--fullTime','--inGame')).root))
        self.assertFalse(matches.confirm_basketball_result(m,matches.MatchHTML(html.replace('>90<','>91<')).root))
    def test_basketball_fixture_utc_and_teams(self):
        html='<tr class="p0c-team-matches__row"><td><a class="p0c-team-matches__button p0c-team-matches__button--start-time" href="https://www.mackolik.com/basketbol/mac/test/id" data-start-timestamp="1791730800">11.10</a>'
        for side,team,name in [('home','other','Türk Telekom'),('away',matches.BASKET_TEAM,'Beşiktaş')]:
            html+=f'<div class="p0c-team-matches__team--{side}"><a class="p0c-team-matches__team-name" href="https://www.mackolik.com/basketbol/takim/{team}"><span class="p0c-team-matches__team-full-name">{name}</span></a></div>'
        html+='</td></tr>'
        m=matches.parse_basketball_fixture(matches.MatchHTML(html).root)[0]
        self.assertEqual(m['start'].astimezone(matches.ISTANBUL).strftime('%Y-%m-%d %H:%M'),'2026-10-11 18:00')
        self.assertEqual([t['id'] for t in m['teams']],['other','BES'])
        self.assertTrue(m['scheduled'])
    def test_missing_lineup_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory, patch('matches.STATE',Path(directory)/'state.json'), patch('matches.starters',return_value=[]),patch('matches.bot.publish') as publish:
            matches.run([self.match],self.now)
            publish.assert_not_called()
    def test_preview_does_not_publish_or_consume_history(self):
        self.match.update(sport='BASKETBOL', teams=[{'id':'BES','name':'Beşiktaş'},{'id':'other','name':'Rakip'}])
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'state.json'
            with patch('matches.STATE',state),patch('matches.card'),patch('matches.bot.publish') as publish,patch('pathlib.Path.write_text'):
                matches.run([self.match],self.now,dry_run=True)
                publish.assert_not_called()
                self.assertFalse(state.exists())
    def test_failed_upload_does_not_consume_history(self):
        self.match.update(sport='BASKETBOL', teams=[{'id':'BES','name':'Beşiktaş'},{'id':'other','name':'Rakip'}])
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'state.json'
            with patch('matches.STATE',state),patch('matches.card'),patch('matches.bot.publish',side_effect=RuntimeError('Upload failed')):
                with self.assertRaises(RuntimeError):matches.run([self.match],self.now)
                self.assertFalse(state.exists())
    def test_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'state.json';state.write_text('{"test:pre":{}}')
            with patch('matches.STATE',state),patch('matches.starters') as starters:
                matches.run([self.match],self.now);starters.assert_not_called()

if __name__=='__main__':unittest.main()
