import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('auto_pipeline', ROOT / 'auto_pipeline.py')
pipeline = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'digest': types.ModuleType('digest'),
                              'find_news': types.ModuleType('find_news')}):
    spec.loader.exec_module(pipeline)

ACCOUNT = {'id': '11111111-1111-1111-1111-111111111111', 'name': '小镇青年职场说',
           'category': '职场', 'is_active': True, 'wechat_appid': 'wx123'}


class FakeApi:
    def __init__(self, attempts):
        self.attempts = list(attempts)
        self.created = []
        self.published = []
        self.creations = {}
        self.drafts = {}

    def login(self):
        pass

    def post(self, path, body=None):
        if path == '/creations':
            attempt = self.attempts.pop(0)
            cid = str(len(self.created) + 1)
            self.created.append(body['theme'])
            self.creations[cid] = {
                'id': cid, 'status': 'done', 'account_id': body['account_id'],
                'generated_title': body['theme'], 'generated_content_html': '<p>真实的职场故事。</p>',
                'fact_check': {'score': 90}, **attempt,
            }
            return {'id': cid}
        cid = path.split('/')[2]
        self.published.append(cid)
        creation = self.creations[cid]
        did = 'draft-' + cid
        self.drafts[did] = {
            'id': did, 'source_creation_id': cid, 'account_id': creation['account_id'],
            'status': creation.get('push_status', 'published_to_wechat'),
            'error_msg': creation.get('push_error'),
            'wechat_pushed_at': pipeline.business_day() + 'T09:00:00+08:00'
                if creation.get('push_status', 'published_to_wechat') == 'published_to_wechat' else None,
        }
        if creation.get('lost_response'):
            raise TimeoutError('推送响应丢失')
        return {'id': did}

    def get(self, path):
        if path == '/accounts':
            return [ACCOUNT]
        if path.startswith('/creations/'):
            return self.creations[path.split('/')[2]]
        if path.startswith('/drafts/'):
            return self.drafts[path.split('/')[2]]
        raise AssertionError(path)

    def read_drafts(self, account_id, day, creation_id=None):
        return [dict(d) for d in self.drafts.values() if d['account_id'] == account_id]


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name, value in [('STATE_DIR', self.temp.name),
                            ('DONE_TOPICS', str(Path(self.temp.name) / 'topics.txt'))]:
            p = patch.object(pipeline, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(pipeline, 'ingest_material', return_value=0)
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(pipeline, 'business_day', return_value='2026-09-08', create=True)
        p.start()
        self.addCleanup(p.stop)
        self.cfg = {'min_score': 80, 'dry_run': False, 'topic_tries': 1,
                    'material_limit': 3, 'pieces': 1, 'day': '2026-09-08'}
        self.logs = []

    def run_piece(self, attempts, topics=None):
        api = FakeApi(attempts)
        queue = list(topics or ['裁员后的选择', '职场成长经历', '退休前的准备'])
        with patch.object(pipeline, 'read_account_drafts', api.read_drafts, create=True):
            result = pipeline.make_one_piece(api, ACCOUNT, queue, self.cfg, self.logs.append)
        return result, api, queue

    def test_generation_failure_then_success_stops_at_one(self):
        result, api, queue = self.run_piece([{'status': 'failed'}, {}])
        self.assertEqual(result, 'pushed')
        self.assertEqual(len(api.created), 2)
        self.assertEqual(api.published, ['2'])
        self.assertEqual(queue, ['退休前的准备'])

    def test_low_score_then_success(self):
        result, api, _ = self.run_piece([{'fact_check': {'score': 20}}, {}])
        self.assertEqual(result, 'pushed')
        self.assertEqual(api.published, ['2'])

    def test_explicit_publish_rejection_then_success(self):
        result, api, _ = self.run_piece([
            {'push_status': 'failed', 'push_error': 'WeChatDraftError: errcode=45003, errmsg=title too long'}, {}])
        self.assertEqual(result, 'pushed')
        self.assertEqual(len(api.created), 2)

    def test_invalid_review_does_not_pass(self):
        for review in ({}, {'score': None}, {'score': 99, 'error': True},
                       {'score': 99, 'parse_error': True, 'score_recovered': False}):
            with self.subTest(review=review):
                result, api, _ = self.run_piece([{'fact_check': review}, {}])
                self.assertEqual(result, 'pushed')
                self.assertEqual(api.published, ['2'])

    def test_empty_article_is_not_a_success(self):
        result, api, _ = self.run_piece([{'generated_content_html': '  '}, {}])
        self.assertEqual(result, 'pushed')
        self.assertEqual(api.published, ['2'])

    def test_exhausted_low_score_queue_is_not_success(self):
        result, api, queue = self.run_piece([{'fact_check': {'score': 20}}], ['裁员后的选择'])
        self.assertIsNone(result)
        self.assertFalse(queue)
        self.assertFalse(api.published)


if __name__ == '__main__':
    unittest.main()
