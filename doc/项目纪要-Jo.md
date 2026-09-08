# Jo · 项目纪要

- 项目目标：微信公众号素材改写与主题创作。
- 约束：保留无关改动；用户已授权审核角色改用现有 DeepSeek；其他生产写入及部署不在本次授权内。

## 当前状态
- 已完成：通过 ubuntu 登录服务器，只读核实 cron、独立脚本、9 月 6～8 日出稿日志和最近 8 条创作数据库记录，确认两个相互叠加的问题。
- 进行中：审核模型切换已完成，原始每日补位需求尚未完成。
- 待办：准备并测试每日成功出稿补位修复；核查审核输出预算与模式；补位代码部署和其他生产修改需用户明确授权。
- 待确认：补位脚本的生产部署授权（审核角色变更已授权）。

## 决策记录（实时维护）
- [09-08-2026 12:01:18] 每日创作失败补位｜背景：当天选中的文章创作失败后，当日没有文章产出。｜结论：失败后继续尝试下一篇，直到成功产出当天文章。具体入口及边界需结合当前实现核查。｜来源：用户
- [09-08-2026 13:01:43] 服务器入口核查｜背景：本地未找到每日出稿脚本，默认 root 登录被拒，用户确认登录用户为 ubuntu。｜结论：使用 `ubuntu@101.42.185.88` 核查调度和脚本；当前服务器操作限只读，不执行部署或生产写入。｜来源：用户
- [09-08-2026 13:11:13] 审核角色改用 DeepSeek｜背景：原 reviewer 的 moonshot-v1-32k 返回 404，导致文章被记为 0 分并停稿；writer/lite 已使用 deepseek-v4-flash。｜结论：用户授权审核模型也改用现有 DeepSeek，先验证审核调用，再切换 reviewer 并回读；不重跑整日任务或推送文章。｜来源：用户

## 待解决问题
- 核查每日候选来源、成功标准及无可用候选时的停止条件；处理超时后原任务继续完成导致重复出稿的风险。
- 已验证：`backend/app/tasks/create.py:205` 拒绝空正文，`:267` 将异常标为 failed 后结束；`backend/app/creator/routes.py:62` 每次只派发单篇创作。
- 已验证：`backend/app/tasks/maintenance.py:129` 的定时任务只有清理、素材卡住重置和统计同步，没有每日选题创作。
- Git 提交 `4981520` 的说明提到外部出稿脚本和评分闸门，但当前仓库未找到该脚本。本机 Codex 自动化配置及匹配名称的 Windows 计划任务也未找到相关入口。不能据此推断服务器实际调度位置。
- 2026-09-08 连接验证：默认 root 被拒，用户更正为 ubuntu 后使用本机默认密钥登录成功。未执行生产写入。

## 服务器核查证据（2026-09-08）
- 登录：`ssh -o BatchMode=yes ubuntu@101.42.185.88`。服务器日期偏移为 `+08:00`。
- `ubuntu` 的 crontab：每天 08:00 执行 `/home/ubuntu/gzh-digest/run.sh` 生成选题简报；每天 08:30 执行 `/home/ubuntu/gzh-digest/run-auto.sh`，后者运行同目录 `auto_pipeline.py`。脚本不在当前应用仓库中。
- `/home/ubuntu/gzh-digest/auto_pipeline.py:259` 的 `make_one_piece` 已有消费队列的 while 循环；`:276` 对生成 failed 或轮询未完成执行 continue。因此不能再声称服务器生成失败后完全没有补位。
- 直接退出点：`:280` 评分闸门不通过就返回 `gated`；`:292`、`:300` 推送失败返回 `push_failed`；`:360` 主循环把任何非空返回值计入每日名额。每日名额默认为 1，所以这些失败结果会结束该号当天出稿。
- `/home/ubuntu/gzh-digest/archive/auto-2026-09-07.txt`：白露时节如何养生空正文失败后继续生成白露换季养生要点，但评分 0 被拦；应该削减机关事业单位的退休金空正文失败后继续生成港硕话题并成功推送。共生成 2 篇、进草稿箱 1 篇、闸门拦下 1 篇。
- `/home/ubuntu/gzh-digest/latest-auto.txt`（9 月 8 日）：两个启用号各生成 1 篇，两篇均评分 0 被拦，进草稿箱 0 篇。
- 通过 API 容器中的 asyncpg 显式只读事务查询最近 8 条 `theme_creations`：上述空正文失败与截图主题对应；9 月 6～8 日所有查到的有素材 0 分记录均含 `fact_check.error=true`，issues 明确为 `Error code: 404 ... Not found the model moonshot-v1-32k or Permission denied`。这是模型调用失败，不是已验证的文章质量低分，也不是先前 JSON 截断问题。
- 只读查询 `role_bindings`：reviewer=`moonshot-v1-32k`；writer/lite=`deepseek-v4-flash`。仅确认当前绑定，不代表替代审核模型已经验证可用。
- 应用服务器仓库当前提交 `937a825`；独立脚本 SHA256：`1edb2ea4a04221c38fe99236397130594e10e6f51d62abd85b04cd93fd4b72df`。
- 后续修复需区分：单篇生成失败或实际质量不达标可换下一候选；共同模型故障需修复配置或明确暂停，不能无限消耗候选；推送结果未知时先核实原任务，避免重复草稿。当前脚本无按账号/日期的完成持久化，直接重跑整个脚本可能给已有成功稿的号额外出稿。

## 审核模型变更（2026-09-08）
- 根据用户本轮授权，通过现有 `PUT /api/ai-providers/role-bindings` 将 reviewer 从 Kimi / moonshot-v1-32k 改为 DeepSeek / deepseek-v4-flash；GET 回读与逐角色比较通过，writer/lite/image 未变。
- 角色记录 ID 保持 `82adb03c-cf7c-452a-b70d-6897b41fca2c`；原 provider ID `854bfbc2-cf48-4f42-9b50-ad8bf2acf0dd`，新 provider ID `fa4e7af1-8620-4220-920d-252513840523`。这些信息仅用于必要时恢复原绑定，旧模型目前仍有 404 问题。
- 切换前以今天的养老金创作及其真实检索素材调用现有 grounding 提示词：首次返回未通过有效 JSON 校验；第二次诊断调用返回有效 JSON，score=85，finish_reason=stop，completion_tokens=2929，其中 reasoning_tokens=2760，max_tokens=3000。这证明可用，但输出预算余量不足；不能宣称首次失败根因已被确认或所有审核失败已解决。
- DeepSeek 官方文档 https://api-docs.deepseek.com/quick_start/pricing/ 显示 V4 默认开启 thinking；现有适配器未传模式参数。后续输出预算或模式调整需独立验证，当前未改代码或其他生产配置。
- 历史创作的 fact_check 未写回，未触发生成、草稿推送或整日任务；只是对原文进行不落库的审核验证。
- 13:16 完成 worker 容器验证：按任务相同路径 `load_from_db` 读取 reviewer，确认 DeepSeek / deepseek-v4-flash；用图书馆公告和一致正文调用 `review_grounding`，返回有效 JSON、score=100、无错误或解析错误，输出 `WORKER_REVIEWER_VERIFIED`，进程退出码 0。下次创作任务会热加载新绑定，无需重启服务；正在执行的旧任务不承诺中途切换。

## 工作文件集
- doc/项目纪要-Jo.md
- backend/app/tasks/create.py
- backend/app/creator/routes.py
- backend/app/tasks/maintenance.py
- 服务器：/home/ubuntu/gzh-digest/auto_pipeline.py
- 服务器：/home/ubuntu/gzh-digest/run-auto.sh
- 服务器：/home/ubuntu/gzh-digest/archive/auto-2026-09-07.txt
- 服务器：/home/ubuntu/gzh-digest/latest-auto.txt
