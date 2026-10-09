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
    def test_basketball_final_requires_completed_clock_and_no_tie(self):
        h={'Live':False,'Quarter':'','GameTime':'40:00','RemainingPartialTime':'00:00','ScoreA':'77','ScoreB':'83'}
        self.assertTrue(matches.basketball_finished(h))
        for changes in ({'Live':True},{'GameTime':'39:59'},{'ScoreA':'83'},{'Quarter':'4'},{'RemainingPartialTime':'01:00'}):
            self.assertFalse(matches.basketball_finished(h|changes))
    def test_missing_lineup_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory, patch('matches.STATE',Path(directory)/'state.json'), patch('matches.starters',return_value=[]),patch('matches.bot.publish') as publish:
            matches.run([self.match],self.now)
            publish.assert_not_called()
    def test_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'state.json';state.write_text('{"test:pre":{}}')
            with patch('matches.STATE',state),patch('matches.starters') as starters:
                matches.run([self.match],self.now);starters.assert_not_called()

if __name__=='__main__':unittest.main()
