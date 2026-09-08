# Jo · 项目纪要

- 项目目标：微信公众号素材改写与主题创作。
- 约束：保留无关改动；本轮不部署、不修改生产数据。

## 当前状态
- 已完成：通过 ubuntu 登录服务器，只读核实 cron、独立脚本、9 月 6～8 日出稿日志和最近 8 条创作数据库记录，确认两个相互叠加的问题。
- 进行中：核查已完成，业务代码及生产配置尚未修改。
- 待办：准备并测试每日成功出稿补位修复；核实可用的审核模型；生产修改需用户明确授权。
- 待确认：审核模型替换方案及生产修复授权。

## 决策记录（实时维护）
- [09-08-2026 12:01:18] 每日创作失败补位｜背景：当天选中的文章创作失败后，当日没有文章产出。｜结论：失败后继续尝试下一篇，直到成功产出当天文章。具体入口及边界需结合当前实现核查。｜来源：用户
- [09-08-2026 13:01:43] 服务器入口核查｜背景：本地未找到每日出稿脚本，默认 root 登录被拒，用户确认登录用户为 ubuntu。｜结论：使用 `ubuntu@101.42.185.88` 核查调度和脚本；当前服务器操作限只读，不执行部署或生产写入。｜来源：用户

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

## 工作文件集
- doc/项目纪要-Jo.md
- backend/app/tasks/create.py
- backend/app/creator/routes.py
- backend/app/tasks/maintenance.py
- 服务器：/home/ubuntu/gzh-digest/auto_pipeline.py
- 服务器：/home/ubuntu/gzh-digest/run-auto.sh
- 服务器：/home/ubuntu/gzh-digest/archive/auto-2026-09-07.txt
- 服务器：/home/ubuntu/gzh-digest/latest-auto.txt
