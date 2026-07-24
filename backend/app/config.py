from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wechat_rewriter"
    redis_url: str = "redis://localhost:6379/0"

    admin_username: str = "admin"
    admin_password_hash: str = ""
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    encryption_key: str = ""

    default_writer_provider: str = "deepseek"
    default_reviewer_provider: str = "kimi"
    default_lite_provider: str = "deepseek"

    # CORS：逗号分隔的允许来源，或 "*" 表示任意来源（为 "*" 时自动关闭凭证回显）
    cors_origins: str = "*"
    # 抓取器 SSRF 白名单：逗号分隔的允许 host 后缀。
    # 微信域是原始素材源；后面一串新闻域是自动出稿的当下素材源（热榜话题
    # → 搜到当天报道 → 入库供创作检索）。只列公开新闻站，白名单机制本身
    # 是 SSRF 防护，别改成放行全部。
    # 注意：只列单一机构持有的域名。`gov.cn` 这种准公共后缀不能整段放行——
    # 任意 xxx.gov.cn 都会命中，其中一个子域被拿下就等于白名单被绕过。
    allowed_crawl_domains: str = (
        "mp.weixin.qq.com,weixin.qq.com,"
        "news.qq.com,new.qq.com,view.inews.qq.com,inews.qq.com,"
        "sohu.com,www.gov.cn,thepaper.cn,sina.com.cn,163.com,ifeng.com,"
        "chinanews.com,chinanews.com.cn,people.com.cn,xinhuanet.com,"
        "cctv.com,jiemian.com,yicai.com,huxiu.com,36kr.com,"
        "baijiahao.baidu.com,bjnews.com.cn,nbd.com.cn,cls.cn,stcn.com,"
        "chinadaily.com.cn,workercn.cn,ce.cn,cnr.cn,gmw.cn,china.com.cn"
    )
    # LLM 请求超时（秒），防止外部 AI 服务挂起拖死任务
    llm_timeout_seconds: int = 60

    crawler_timeout: int = 30
    crawler_max_retry: int = 3
    celery_worker_concurrency: int = 4
    image_storage_dir: str = "/data/images"
    rewrite_batch_max: int = Field(default=20, ge=1, le=200)
    draft_max_regenerations: int = Field(default=5, ge=1, le=50)

    # 合规不达标时自动重写：把审核查出的违规条目回灌给写手模型重来一轮。
    # 只看 compliance——原创度/AI 味属于风格判断，自动重跑不易收敛且费 token。
    review_auto_fix_enabled: bool = True
    review_auto_fix_compliance_min: int = Field(default=95, ge=0, le=100)
    review_auto_fix_max_passes: int = Field(default=1, ge=0, le=3)
    stats_backfill_days: int = Field(default=30, ge=7, le=90)
    stats_daily_cron_hour: int = Field(default=3, ge=0, le=23)

    # 主题创作（基于文章库的检索式生成）
    # 检索保留的素材篇数（喂给生成的真实文章）
    creation_retrieval_top_k: int = Field(default=5, ge=1, le=20)
    # 关键词检索的候选池上限
    creation_candidate_limit: int = Field(default=30, ge=5, le=100)
    # 候选池中额外混入的最近文章篇数（保证覆盖"近期"内容）
    creation_recent_count: int = Field(default=10, ge=0, le=50)
    # 无人值守自动推送创作时要求的事实核查最低分数
    creation_auto_publish_min_score: int = Field(default=80, ge=0, le=100)

    # AI 图像生成（豆包 Seedream）
    doubao_api_key: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_image_model: str = "doubao-seedream-3-0-t2i-250415"

    # AI 图像合成
    image_posts_font_path: str = "app/image_composer/fonts/SourceHanSansSC-Bold.otf"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_security_settings(settings: Settings) -> None:
    """启动时校验关键安全配置，发现不安全默认值直接拒绝启动。"""
    problems: list[str] = []
    if not settings.jwt_secret or "change-me" in settings.jwt_secret:
        problems.append("JWT_SECRET 未配置或仍为占位默认值（含 'change-me'）")
    if not settings.encryption_key:
        problems.append("ENCRYPTION_KEY 未配置")
    if not settings.admin_password_hash:
        problems.append("ADMIN_PASSWORD_HASH 未配置")
    if problems:
        raise RuntimeError("检测到不安全的配置，拒绝启动: " + "; ".join(problems))
