import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import nullcontext, redirect_stdout
from io import StringIO
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
            'created_at': pipeline.business_day() + 'T09:00:00+08:00',
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
        return [dict(d) for d in self.drafts.values() if d['account_id'] == account_id and (
            d['source_creation_id'] == creation_id or d['created_at'].startswith(day)
            or (d.get('wechat_pushed_at') or '').startswith(day))]


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

    def test_same_day_repeat_does_not_create_an_extra_draft(self):
        api = FakeApi([{}, {}])
        with patch.object(pipeline, 'read_account_drafts', api.read_drafts, create=True):
            pipeline.make_one_piece(api, ACCOUNT, ['职场成长经历'], self.cfg, self.logs.append)
            pipeline.make_one_piece(api, ACCOUNT, ['退休前的准备'], self.cfg, self.logs.append)
        self.assertEqual(len(api.created), 1)

    def test_publish_response_loss_is_reconciled(self):
        result, api, _ = self.run_piece([{'lost_response': True}])
        self.assertEqual(result, 'pushed')
        self.assertEqual(len(api.published), 1)

    def test_pending_publication_is_resumed_before_new_creation(self):
        api = FakeApi([{'push_status': 'reviewed'}, {}])
        with patch.object(pipeline, 'poll', side_effect=lambda api, path, *a, **kw: api.get(path)), \
                patch.object(pipeline, 'read_account_drafts', api.read_drafts, create=True):
            first = pipeline.make_one_piece(api, ACCOUNT, ['职场成长经历'], self.cfg, self.logs.append)
            self.assertIsNone(first)
            second = pipeline.make_one_piece(api, ACCOUNT, ['退休前的准备'], self.cfg, self.logs.append)
            self.assertIsNone(second)
            api.drafts['draft-1']['status'] = 'published_to_wechat'
            api.drafts['draft-1']['wechat_pushed_at'] = '2026-09-08T09:01:00+08:00'
            pipeline.make_one_piece(api, ACCOUNT, ['退休前的准备'], self.cfg, self.logs.append)
        self.assertEqual(len(api.created), 1)
        self.assertEqual(len(api.published), 1)

    def test_failed_transport_stops_without_creating_next(self):
        result, api, queue = self.run_piece([
            {'push_status': 'failed', 'push_error': 'ReadTimeout: 微信响应超时'}])
        self.assertIsNone(result)
        self.assertEqual(len(api.created), 1)
        self.assertEqual(len(queue), 2)

    def test_creation_timeout_resumes_same_creation(self):
        api = FakeApi([{'status': 'generating'}, {}])
        with patch.object(pipeline, 'poll', side_effect=lambda api, path, *a, **kw: api.get(path)), \
                patch.object(pipeline, 'read_account_drafts', api.read_drafts, create=True):
            pipeline.make_one_piece(api, ACCOUNT, ['职场成长经历'], self.cfg, self.logs.append)
            api.creations['1']['status'] = 'done'
            result = pipeline.make_one_piece(api, ACCOUNT, ['退休前的准备'], self.cfg, self.logs.append)
        self.assertEqual(result, 'pushed')
        self.assertEqual(len(api.created), 1)

    def test_cross_day_does_not_start_a_new_creation(self):
        with patch.object(pipeline, 'business_day', return_value='2026-09-09', create=True):
            result, api, _ = self.run_piece([{}])
        self.assertIsNone(result)
        self.assertFalse(api.created)

    def test_dry_run_does_not_consume_live_quota(self):
        api = FakeApi([{}, {}])
        with patch.object(pipeline, 'read_account_drafts', api.read_drafts, create=True):
            self.cfg['dry_run'] = True
            self.assertEqual(pipeline.make_one_piece(api, ACCOUNT, ['职场成长经历'], self.cfg, self.logs.append), 'dry')
            pipeline.make_one_piece(api, ACCOUNT, ['退休前的准备'], self.cfg, self.logs.append)
            self.assertEqual(len(api.created), 1)
            self.cfg['dry_run'] = False
            self.assertEqual(pipeline.make_one_piece(api, ACCOUNT, ['退休前的准备'], self.cfg, self.logs.append), 'pushed')
        self.assertEqual(len(api.created), 2)

    def test_unused_material_candidates_are_available_for_next_piece(self):
        queue = ['职场成长经历', '退休前的准备', '裁员后的选择']
        self.cfg['topic_tries'] = 2
        topic, _ = pipeline.pick_topic(FakeApi([]), ACCOUNT['name'], queue, self.cfg, self.logs.append)
        self.assertEqual(topic, '职场成长经历')
        self.assertEqual(queue, ['退休前的准备', '裁员后的选择'])

    def run_main(self, api, accounts=None, pieces=1):
        original_get = api.get
        api.get = lambda path: (accounts or [ACCOUNT]) if path == '/accounts' else original_get(path)
        output = StringIO()
        with patch.object(pipeline, 'Api', return_value=api), \
                patch.object(pipeline, 'load_env_file'), \
                patch.object(pipeline, 'env', side_effect=lambda key, default='':
                    {'AUTO_DRY_RUN': '0', 'AUTO_PIECES_PER_ACCOUNT': str(pieces)}.get(key, default)), \
                patch.object(pipeline.digest, 'extract_topics', return_value=['职场成长经历', '退休前的准备'], create=True), \
                patch.object(pipeline, 'build_queue', side_effect=lambda a, t, d: list(t)), \
                patch.object(pipeline, 'read_account_drafts', api.read_drafts), \
                patch.object(pipeline, 'single_run', return_value=nullcontext()), redirect_stdout(output):
            result = pipeline.main()
        return result, output.getvalue()

    def test_main_reports_missing_quota_as_failure(self):
        code, output = self.run_main(FakeApi([{'status': 'failed'}, {'status': 'failed'}]))
        self.assertEqual(code, 1)
        self.assertIn('未完成', output)

    def test_main_repeat_reports_existing_success(self):
        api = FakeApi([{}])
        code, _ = self.run_main(api)
        self.assertEqual(code, 0)
        code, output = self.run_main(api)
        self.assertEqual(code, 0)
        self.assertEqual(len(api.created), 1)
        self.assertIn('当天已完成', output)

    def test_configured_multiple_pieces_stop_at_target(self):
        api = FakeApi([{}, {}])
        code, _ = self.run_main(api, pieces=2)
        self.assertEqual(code, 0)
        self.assertEqual(len(api.published), 2)
        code, _ = self.run_main(api, pieces=2)
        self.assertEqual(code, 0)
        self.assertEqual(len(api.published), 2)

    def test_success_date_uses_local_day_not_utc_day(self):
        from recovery import pushed_today
        draft = {'status': 'published_to_wechat', 'wechat_pushed_at': '2026-09-07T16:00:00+00:00'}
        self.assertTrue(pushed_today(draft, '2026-09-08'))
        self.assertFalse(pushed_today(draft, '2026-09-07'))
        draft['wechat_pushed_at'] = '2026-09-08T16:00:00+00:00'
        self.assertFalse(pushed_today(draft, '2026-09-08'))

    def test_one_account_api_failure_does_not_abort_other_account(self):
        second = {**ACCOUNT, 'id': '22222222-2222-2222-2222-222222222222', 'name': '纯洁的小镇阿姨'}
        api = FakeApi([{}])
        original_post = api.post
        def fail_first_account(path, body=None):
            if path == '/creations' and body['account_id'] == ACCOUNT['id']:
                raise TimeoutError('接口暂时不可用')
            return original_post(path, body)
        api.post = fail_first_account
        code, output = self.run_main(api, [ACCOUNT, second])
        self.assertEqual(code, 1)
        self.assertEqual(len(api.published), 1)
        self.assertIn(second['name'], output)

    def test_systemic_review_failure_does_not_exhaust_queue(self):
        review = {'score': 0, 'error': True, 'issues': ['事实核查失败：Error code: 404 模型不可用']}
        result, api, queue = self.run_piece([{'fact_check': review}])
        self.assertIsNone(result)
        self.assertEqual(len(api.created), 1)
        self.assertEqual(len(queue), 2)

    def test_crossing_midnight_during_generation_does_not_publish(self):
        def finish_tomorrow(api, path, *args, **kwargs):
            pipeline.business_day.return_value = '2026-09-09'
            return api.get(path)
        with patch.object(pipeline, 'poll', side_effect=finish_tomorrow):
            result, api, _ = self.run_piece([{}])
        self.assertIsNone(result)
        self.assertFalse(api.published)

    def test_corrupt_progress_fails_without_new_creation(self):
        Path(self.temp.name, 'daily-live-' + ACCOUNT['id'] + '.json').write_text('{', encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            self.run_piece([{}])

    def test_daily_quota_error_does_not_block_the_next_day(self):
        api = FakeApi([{'push_status': 'failed', 'push_error': 'WeChatDraftError: errcode=45009, errmsg=quota'}, {}])
        with patch.object(pipeline, 'read_account_drafts', api.read_drafts):
            result = pipeline.make_one_piece(api, ACCOUNT, ['职场成长经历'], self.cfg, self.logs.append)
            self.assertIsNone(result)
            self.cfg['day'] = '2026-09-09'
            pipeline.business_day.return_value = '2026-09-09'
            result = pipeline.make_one_piece(api, ACCOUNT, ['退休前的准备'], self.cfg, self.logs.append)
        self.assertEqual(result, 'pushed')
        self.assertEqual(len(api.created), 2)

    def test_previous_day_blocked_pending_after_crash_continues_today(self):
        from recovery import Progress
        api = FakeApi([{}])
        api.drafts['old-draft'] = {
            'id': 'old-draft', 'source_creation_id': 'old', 'account_id': ACCOUNT['id'],
            'status': 'failed', 'error_msg': 'WeChatDraftError: errcode=45009, errmsg=quota',
            'created_at': '2026-09-07T09:00:00+08:00', 'wechat_pushed_at': None,
        }
        progress = Progress(self.temp.name, ACCOUNT['id'], '2026-09-07', False)
        progress.pending = {'day': '2026-09-07', 'creation_id': 'old', 'publishing': True, 'n_material': 0}
        progress.save()
        with patch.object(pipeline, 'read_account_drafts', api.read_drafts):
            result = pipeline.make_one_piece(api, ACCOUNT, ['职场成长经历'], self.cfg, self.logs.append)
        self.assertEqual(result, 'pushed')
        self.assertEqual(len(api.created), 1)

    def test_unsubmitted_publish_has_actionable_manual_recovery(self):
        from recovery import Progress
        progress = Progress(self.temp.name, ACCOUNT['id'], self.cfg['day'], False)
        progress.pending = {'day': self.cfg['day'], 'creation_id': '1', 'publishing': True, 'n_material': 0}
        progress.save()
        result, api, _ = self.run_piece([])
        self.assertIsNone(result)
        self.assertFalse(api.created)
        self.assertTrue(any('人工' in line and '1' in line for line in self.logs))

    def test_existing_success_does_not_hide_unresolved_draft(self):
        api = FakeApi([])
        for cid, status in [('1', 'published_to_wechat'), ('2', 'reviewed')]:
            api.drafts['draft-' + cid] = {
                'id': 'draft-' + cid, 'source_creation_id': cid, 'account_id': ACCOUNT['id'],
                'status': status, 'error_msg': None, 'created_at': '2026-09-08T09:00:00+08:00',
                'wechat_pushed_at': '2026-09-08T09:00:00+08:00' if cid == '1' else None,
            }
        code, output = self.run_main(api)
        self.assertEqual(code, 1)
        self.assertIn('待核实', output)
        self.assertFalse(api.created)

    def test_lost_creation_response_never_publishes_orphan_creation(self):
        api = FakeApi([{}, {}])
        original_post = api.post
        def lose_first_response(path, body=None):
            result = original_post(path, body)
            if path == '/creations' and len(api.created) == 1:
                raise TimeoutError('创作响应丢失')
            return result
        api.post = lose_first_response
        first, _ = self.run_main(api)
        second, _ = self.run_main(api)
        self.assertEqual((first, second), (1, 0))
        self.assertEqual(len(api.created), 2)
        self.assertEqual(api.published, ['2'])

    @unittest.skipIf(sys.platform == 'win32', '进程锁在部署使用的 Linux 上验证')
    def test_second_process_cannot_acquire_run_lock(self):
        from recovery import single_run
        with single_run(self.temp.name):
            with self.assertRaises(BlockingIOError):
                with single_run(self.temp.name):
                    self.fail('第二个锁不应获取成功')

    @unittest.skipIf(sys.platform == 'win32', 'Bash 入口在部署使用的 Linux 上验证')
    def test_runner_preserves_failure_exit_and_log(self):
        runner = Path(self.temp.name) / 'run-auto.sh'
        shutil.copyfile(ROOT / 'run-auto.sh', runner)
        Path(self.temp.name, 'auto_pipeline.py').write_text('print("未完成当天目标")\nraise SystemExit(7)\n', encoding='utf-8')
        result = subprocess.run(['bash', str(runner)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 7)
        self.assertIn('未完成当天目标', Path(self.temp.name, 'latest-auto.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
