<!-- About 简介（推送后填写到仓库 About 栏）：
小白也能用的广告投放方法论：策略/素材/复盘一条龙 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-ads
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, advertising, sem, marketing -->

# lhg-ads：小白也能用的广告投放方法论

> **一句话介绍**：给 AI 助手装上"广告投放组合拳"——投放策略（渠道/人群/出价/预算）→素材清单（标题/创意/落地页）→数据复盘框架（CTR/CVR/ROAS 解读），13 条确定性规则自动体检，小白也能输出结构正确的投放计划。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-ads
> /plugin install lhg-ads@lhg-plugs
> ```

> ⚠️ **方法论声明（置顶）**：投放效果依赖各平台实时数据、算法与市场环境，本插件提供的是**投放方法论、素材清单与复盘框架**，**不承诺任何 ROI / 转化效果**。插件内出现的任何效果数字均为示例口径，不构成收益承诺。

## 它是什么

`lhg-ads` 是一个 Claude Code 插件（plugin 为主、skill 为辅）：

- **5 个命令**（小白入口）：`ads` 投放全流程一条龙，`strategy` 只做投放策略，`creative` 只做素材清单，`review` 数据复盘，`audit` 投放文档体检
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：投放策略、素材创作、数据追踪与口径、数据复盘
- **2 个专家 agent**：投放策略专家、投放审计专家
- **2 个硬门 hooks**：commit 前审计拦截（效果承诺/极限词/密钥泄露）、写投放文档时 UTM/预算表提醒（均可一键豁免）
- **13 条确定性审计规则**：纯 Python、零第三方依赖，秒级出结果

## 5 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-ads:ads` | 投放全流程：输入产品与预算 → 策略 → 素材 → 复盘模板 | `/lhg-ads:ads "轻负担代餐茶" 5万` |
| `/lhg-ads:strategy` | 只做投放策略：渠道/人群/出价/预算分配表/优化目标 | `/lhg-ads:strategy "代餐茶" 5万` |
| `/lhg-ads:creative` | 只做素材：标题清单/创意结构/落地页一致性核对 | `/lhg-ads:creative "0糖配料干净"` |
| `/lhg-ads:review` | 数据复盘：粘贴真实数据，按漏斗解读并输出优化动作 | `/lhg-ads:review` |
| `/lhg-ads:audit` | 投放文档体检：脚本 + 人工复核，输出分级报告 | `/lhg-ads:audit` |

## 自查说明

自查 = 确定性脚本（机器）+ 人工复核清单（人）：

1. 先跑 `scripts/audit/ads_audit.py`（13 条规则），零 LLM 成本；
2. 发现分三级：**blocker**（效果承诺/极限词/密钥泄露，必须修，commit 前 hook 会拦截）、**warning**（预算表/UTM/口径/人群缺失，修或写豁免理由）、**nit**（标题超长/缺日期版本，顺手修）；
3. 再按 `lhg-ads-review` 第 5 节人工复核清单过一遍脚本抓不到的（策略合理性、素材真实性、数据诚实性）。

blocker 清零才算做完；为清零改规则算作弊，不许。

## 目录结构

```
lhg-ads/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 5 个命令：ads / strategy / creative / review / audit
├── skills/                  # 4 个平台中立 skill（策略/素材/追踪口径/复盘）
├── agents/                  # 2 个专家 agent（投放策略专家 / 投放审计专家）
├── hooks/                   # 2 个硬门（commit 前审计拦截 / 投放文档提醒）+ 豁免说明
├── scripts/audit/           # 13 条确定性审计规则（零第三方依赖）
├── fixtures/                # 冒烟测试用例（坏/好对照）
├── smoke_test.py            # 一键冒烟测试
├── ATTRIBUTION.md           # 灵感来源与许可声明
└── LICENSE                  # MIT
```

## 什么时候用 / 什么时候不用（FAQ）

**什么时候用：**

- 你要第一次投广告，不知道渠道怎么选、预算怎么分、人群怎么定 → 用 `/lhg-ads:ads` 一条龙
- 你只会写产品卖点，标题和创意无从下手 → 用 `/lhg-ads:creative`，红线（效果承诺/极限词）自动帮你拦
- 投放跑了一段时间，数据看不懂、复盘写不出 → 用 `/lhg-ads:review`，只解读数据呈现的事实
- 你要检查一份投放计划有没有硬伤（承诺了 ROI、链接没 UTM、预算表对不上）→ 跑 `/lhg-ads:audit`

**什么时候不用：**

- 你想让 AI 替你操作广告账户、自动调价 → 本插件只做方法论与文档，不碰账户操作
- 你要的是"保证 ROI 多少"的承诺 → 本插件红线就是不承诺效果，给承诺的是骗子
- 你已经有成熟的投放团队和 SOP → 本插件的价值是"从 0 到 1 立规矩"，成熟团队用不上
- 你投的是特殊行业（金融/医疗/教育），素材合规要求远超通用规则 → 通用极限词检查不够，需要叠加行业合规审核

## lhg-plugs 插件矩阵

| 插件 | 一句话 | 安装 |
|---|---|---|
| [lhg-fullstack](https://github.com/lhg-plugs/lhg-fullstack) | 小白一句话 → 高质量全栈应用 | `/plugin install lhg-fullstack@lhg-plugs` |
| [lhg-ads](https://github.com/lhg-plugs/lhg-ads) | 小白也能用的广告投放方法论：策略/素材/复盘一条龙 | `/plugin install lhg-ads@lhg-plugs` |

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（JSON 合法、skill/command/agent 完整性、13 条规则、fixtures 命中、hooks 行为）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-ads/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 抖音：搜「刘老师讲AI实战」
- 微信：lhgsmsw
