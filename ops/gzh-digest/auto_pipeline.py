#!/usr/bin/env python3
"""每日全自动出稿驱动（主题创作版 + 当下素材）。

流程：热榜话题 → Bing 搜当天关于该话题的新闻报道 → 入素材库（后端抓正文）
→ 「主题创作」模块基于素材库 RAG + 事实核查生成文章 → 过闸门 → 复用桥接端点
推进公众号草稿箱。

为什么要先搜素材：素材库原本只有几十篇旧微信文章，热点话题检索不到依据
（fact_check.mode=no_sources），等于纯 LLM 发挥、没有真实素材支撑。先把当天的
真实报道灌进库里，创作时才检索得到当下的事实。

素材是加分项不是前置条件：搜不到或抓不动照样往下生成，只是退回无依据模式，
保证每天有稿。

红线：只推到草稿箱（publish-to-wechat 内部走 draft/add），永不群发。群发始终人工在微信里点。

复用同目录 digest.py（热榜话题 + 分类关键词 + 账号）。在服务器（国内 IP）上由 cron 调用。

环境变量（~/gzh-digest/.env）：
    API_BASE, ADMIN_USERNAME, ADMIN_PASSWORD
可选覆盖：
    AUTO_PIECES_PER_ACCOUNT(默认1) AUTO_DRY_RUN(默认1=只生成不推送)
    AUTO_CREATION_MIN_SCORE(默认80) 事实核查评分闸门
    AUTO_MATERIAL_LIMIT(默认3) 每个话题最多抓几篇当下报道当素材
    AUTO_TOPIC_TRIES(默认10) 每篇最多试几个话题去找有素材的那个
"""
import os
import sys
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import digest  # noqa: E402  复用话题源 + 分类关键词 + 账号
import find_news  # noqa: E402  话题 → 当下新闻报道链接（Bing）

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "state")
DONE_TOPICS = os.path.join(STATE_DIR, "done_topics_creator.txt")

# 创作是异步的：生成要几十秒到一两分钟，推送(草稿)再等一会。给足超时。
CREATE_POLL_TIMEOUT = 300
CREATE_POLL_INTERVAL = 9
PUBLISH_POLL_TIMEOUT = 120
PUBLISH_POLL_INTERVAL = 6
# 抓一篇新闻正文通常几秒，给足重试余量。
MATERIAL_POLL_TIMEOUT = 120
MATERIAL_POLL_INTERVAL = 5
# 打在自动抓来的素材上，方便在素材库里跟人工素材区分、需要时批量清理。
MATERIAL_TAG = "auto-news"

# 话题降噪：论坛/闲聊帖不是可写的选题。
TOPIC_NOISE = (
    "呜呜", "家人们", "求问", "求助", "如何看待", "怎么看", "有没有", "有没", "求推荐",
    "求分享", "帮我看看", "在线等", "急急急", "救救", "belike", "招聘", "五言古诗",
    "流言板", "视频播客", "反调试",
)


def topic_is_noise(t: str) -> bool:
    if any(n in t for n in TOPIC_NOISE):
        return True
    if len(t) > 34 or t.count("？") + t.count("?") >= 2:
        return True
    return False


def env(key, default=""):
    return os.environ.get(key, default)


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class Api:
    def __init__(self, base, user, password):
        self.base = base.rstrip("/")
        self.user = user
        self.password = password
        self.token = None

    def login(self):
        data = urllib.parse.urlencode(
            {"username": self.user, "password": self.password}
        ).encode()
        req = urllib.request.Request(
            f"{self.base}/auth/login", data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            self.token = json.load(r)["access_token"]

    def _req(self, method, path, body=None):
        if not self.token:
            self.login()
        url = f"{self.base}{path}"
        headers = {"Authorization": f"Bearer {self.token}"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self.login()
                return self._req(method, path, body)
            raise
        return json.loads(raw) if raw.strip() else {}

    def get(self, path):
        return self._req("GET", path)

    def post(self, path, body=None):
        return self._req("POST", path, body)


def load_state(path):
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {ln.strip() for ln in f if ln.strip()}


def append_state(path, value):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(value + "\n")


def build_queue(acc, topics, done_topics):
    """该号待选话题：命中分类关键词、非噪声、未做过。按热榜顺序（热度）。"""
    kws = digest.keywords_for_category(acc.get("category", ""))
    if not kws:
        return []
    return [
        t for t in topics
        if t not in done_topics
        and not any(n in t for n in digest.NOISE_MARKERS)
        and not topic_is_noise(t)
        and any(k in t for k in kws)
    ]


def poll(api, path, key, done_values, timeout, interval):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        d = api.get(path)
        last = d
        if d.get(key) in done_values:
            return d
        time.sleep(interval)
    return last


def gate_ok(creation, min_score, n_material, log):
    """放宽闸门（用户选定）：无依据(no_sources)也放行——LLM 仍写出完整文章，只是无事实核查。
    仅拦"有依据但评分不达标"（自相矛盾比无依据更糟）。目的是保证每天有文章产出。"""
    fc = creation.get("fact_check") or {}
    title = (creation.get("generated_title") or "")[:30]
    if not title.strip() or not (creation.get("generated_content_html") or "").strip():
        log("  ✗ 缺少标题或正文，换下一篇")
        return False
    if fc.get("error") or (fc.get("parse_error") and not fc.get("score_recovered")):
        log("  ✗ 事实核查失败或结果无效，换下一篇")
        return False
    if fc.get("mode") == "no_sources":
        if n_material:
            # 素材抓到了却没被检索命中：关键词对不上或被更旧的文章挤掉，
            # 说明检索侧要调，日志里必须能看出来。
            log(f"  ~ 抓到 {n_material} 篇当下素材但检索没用上(no_sources)，放行｜{title}")
        else:
            log(f"  ~ 无依据(no_sources)，放宽策略放行｜{title}")
        return True
    score = fc.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100:
        log("  ✗ 缺少有效事实核查分数，换下一篇")
        return False
    # 审查 JSON 被截断时 score 会退化（后端会尽量从截断输出里把真实 score 捞回来）。
    # 无论捞没捞回来，日志里必须看得出是解析出了问题，否则一次解析失败会被当成
    # "这篇写得差" 默默丢掉。
    if fc.get("parse_error"):
        tag = "已从截断输出捞回 score" if fc.get("score_recovered") else "score 未能捞回"
        log(f"  ! 事实核查返回非法 JSON（{tag}）｜{title}")
    if score is not None and score < min_score:
        log(f"  ✗ 有依据但评分 {score} < {min_score}，不推｜{title}")
        return False
    log(f"  ✓ 有依据 score={score}｜{title}")
    return True


def ingest_material(api, topic, cfg, log):
    """搜当下报道并入素材库，返回成功抓到正文的篇数。

    失败一律只记日志不抛：素材是加分项，缺了退回无依据模式也要出稿。
    """
    hits = find_news.search(topic, limit=cfg["material_limit"])
    if hits is None:
        log("  ! 素材搜索失败（Bing 连不上或被拦），本篇无当下素材")
        return 0
    if not hits:
        log("  · 没搜到可抓的报道，本篇无当下素材")
        return 0

    pending = []
    for h in hits:
        try:
            rows = api.post(
                "/library", {"urls": [h["url"]], "tags": [MATERIAL_TAG]}
            )
        except Exception as e:
            log(f"  · 入库失败 {h['url'][:46]}：{str(e)[:50]}")
            continue
        for row in rows or []:
            if row.get("id"):
                pending.append((row["id"], h["title"]))

    ok = 0
    for item_id, fallback_title in pending:
        d = poll(api, f"/library/{item_id}", "status", {"done", "failed"},
                 MATERIAL_POLL_TIMEOUT, MATERIAL_POLL_INTERVAL)
        if d.get("status") == "done":
            ok += 1
            log(f"  + 素材：{(d.get('original_title') or fallback_title)[:36]}")
        else:
            log(f"  - 素材抓取失败：{(d.get('error_msg') or '超时')[:50]}")
    return ok


def pick_topic(api, name, queue, cfg, log):
    """在队列靠前的几个话题里挑第一个能搜到当下素材的，返回 (话题, 素材篇数)。

    热榜里混着大量论坛闲聊帖（「辞职后工作群退不退」这种），它们命中账号
    关键词但根本没有新闻报道。搜素材只花一次 Bing 查询和几次抓取、不烧 LLM，
    所以宁可多试几个话题，也不要拿没素材的话题去生成——那等于退回纯 LLM 发挥。
    都试不出来时退回第一个话题保底出稿。
    """
    fallback = None
    for _ in range(cfg["topic_tries"]):
        if not queue:
            break
        topic = queue.pop(0)
        append_state(DONE_TOPICS, topic)  # 试过就记，避免下次重复试同一话题
        log(f"[{name}] 试选题：{topic}")
        n_material = ingest_material(api, topic, cfg, log)
        if n_material:
            return topic, n_material
        if fallback is None:
            fallback = topic
    return fallback, 0


def make_one_piece(api, acc, queue, cfg, log):
    """从队列消费话题，直到成功产出并（非空跑时）推送一篇，或队列耗尽。返回是否产出。"""
    name = acc["name"]
    while queue:
        topic, n_material = pick_topic(api, name, queue, cfg, log)
        if topic is None:
            break
        log(f"[{name}] 定稿主题：{topic}"
            + (f"（{n_material} 篇当下素材）" if n_material else "（无当下素材）"))

        created = api.post("/creations", {"theme": topic, "account_id": acc["id"]})
        cid = created.get("id")
        if not cid:
            log("  创建失败，跳过")
            continue
        done = poll(api, f"/creations/{cid}", "status",
                    {"done", "failed"}, CREATE_POLL_TIMEOUT, CREATE_POLL_INTERVAL)
        if done.get("status") != "done":
            log(f"  生成失败({done.get('status')})，跳过")
            continue
        title = (done.get("generated_title") or "")[:40]
        if not gate_ok(done, cfg["min_score"], n_material, log):
            continue
        if cfg["dry_run"]:
            fc = done.get("fact_check") or {}
            log(f"  ✓ 过闸门(score={fc.get('score')})｜DRY_RUN 不推｜{title}")
            return "dry"

        # 推送到公众号草稿箱（复用桥接端点）
        pub = api.post(f"/creations/{cid}/publish-to-wechat", {})
        did = pub.get("id")
        if not did:
            log(f"  ! 推送结果未知，需核实原任务｜{title}")
            return None
        pushed = poll(api, f"/drafts/{did}", "status",
                      {"published_to_wechat", "failed"},
                      PUBLISH_POLL_TIMEOUT, PUBLISH_POLL_INTERVAL)
        if pushed.get("status") == "published_to_wechat":
            log(f"  ✓✓ 已进草稿箱｜{title}")
            return "pushed"
        error = pushed.get('error_msg') or ''
        if pushed.get('status') == 'failed' and re.match(
                r'WeChatDraftError: errcode=-?[1-9]\d*,', error):
            log(f"  ✗ 微信明确拒绝，换下一篇：{error[:80]}｜{title}")
            continue
        log(f"  ! 推送结果未知，需核实原任务：{error[:80]}｜{title}")
        return None
    log(f"[{name}] 无更多可用话题")
    return None


def main():
    load_env_file(os.path.join(HERE, ".env"))
    cfg = {
        "pieces": int(env("AUTO_PIECES_PER_ACCOUNT", "1")),
        "dry_run": env("AUTO_DRY_RUN", "1") not in ("0", "false", "False"),
        "min_score": int(env("AUTO_CREATION_MIN_SCORE", "80")),
        "material_limit": int(env("AUTO_MATERIAL_LIMIT", "3")),
        # 实测有可抓正文的话题是少数（科技/公司/政策类有主流媒体报道页，
        # 社会新闻多半只有自媒体覆盖），试多几个才捞得到；搜索不烧 LLM。
        "topic_tries": int(env("AUTO_TOPIC_TRIES", "10")),
    }
    api = Api(env("API_BASE", "https://wechat.azhefuye.online/api"),
              env("ADMIN_USERNAME", "admin"), env("ADMIN_PASSWORD"))

    lines = []
    bj = timezone(timedelta(hours=8))

    def log(msg):
        lines.append(msg)
        print(msg, flush=True)

    log(f"# 自动出稿(创作版+当下素材) {datetime.now(bj):%Y-%m-%d %H:%M}"
        f"（每号{cfg['pieces']}篇，{'DRY_RUN' if cfg['dry_run'] else '实推'}，"
        f"事实核查闸门 score≥{cfg['min_score']}，每话题最多抓 {cfg['material_limit']} 篇素材）")

    api.login()
    # 只有配了真实 appid（wx 开头）且启用的号才出稿。被跳过的号要写进日志：
    # 静默过滤会让"某个号一篇都没收到"看起来像出稿失败，而不是没配置。
    all_accounts = api.get("/accounts")
    accounts, skipped = [], []
    for a in all_accounts:
        appid = str(a.get("wechat_appid", ""))
        if not appid.startswith("wx"):
            skipped.append(f"{a.get('name')}(appid 未配置)")
        elif not a.get("is_active"):
            skipped.append(f"{a.get('name')}(已停用)")
        else:
            accounts.append(a)
    log(f"启用真号 {len(accounts)} 个"
        + (f"；跳过 {len(skipped)} 个：{'、'.join(skipped)}" if skipped else ""))
    topics = digest.extract_topics()
    log(f"扫描热榜话题 {len(topics)} 条\n")

    done_topics = load_state(DONE_TOPICS)
    queues = {a["id"]: build_queue(a, topics, done_topics) for a in accounts}
    made = {a["id"]: 0 for a in accounts}
    outcomes = []
    acc_by_id = {a["id"]: a for a in accounts}

    # 轮转：每一轮给每个号尝试产出一篇，机会均等。
    for _round in range(cfg["pieces"]):
        for aid in queues:
            if made[aid] >= cfg["pieces"]:
                continue
            outcome = make_one_piece(api, acc_by_id[aid], queues[aid], cfg, log)
            if outcome in ("pushed", "dry"):
                made[aid] += 1
                outcomes.append(outcome)

    # 分开统计："产出" 不等于 "进了草稿箱"。两者混讲会让被闸门拦下的稿子看起来
    # 像已推送，真出问题时日报反而掩盖了它。
    total = sum(made.values())
    pushed_n = outcomes.count("pushed")
    gated_n = outcomes.count("gated")
    failed_n = outcomes.count("push_failed")
    parts = [f"本次共产出 {total} 篇"]
    if cfg["dry_run"]:
        parts.append("DRY_RUN 未推送")
    else:
        parts.append(f"已进草稿箱 {pushed_n} 篇")
        if gated_n:
            parts.append(f"闸门拦下 {gated_n} 篇")
        if failed_n:
            parts.append(f"推送失败 {failed_n} 篇")
    log("\n" + "，".join(parts))


if __name__ == "__main__":
    main()
