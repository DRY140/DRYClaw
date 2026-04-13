# DRYClaw

中文说明，英文版见 [README.md](README.md)。

DRYClaw 是一个面向终端工作流的 Python AI Agent CLI，支持文件操作、Shell 执行、网页交互、任务调度与守护进程模式。

<img src="docs/assets/intro-ui.png" alt="DRYClaw CLI 界面预览" width="700" />

## 项目概览

- 轻量级 CLI Agent 循环与工具调用
- 本地会话持久化与记忆追加能力
- 面向 macOS 的自动化辅助（含可访问性流程，目前完善中）
- 支持 schedule 与 daemon 的持续化任务能力

## 📺 演示视频 | Demo Videos

<table style="width: 100%; table-layout: fixed; border-collapse: collapse; border: none;">
  <tr>
    <td style="padding: 10px; border: none; vertical-align: top;">
      <strong>1. 基础操控与文件自动化</strong><br>
      <i>Basic Control & File Automation</i>
      <p style="font-size: 0.85em; background-color: #f6f8fa; padding: 8px; border-radius: 4px; border-left: 4px solid #33b3ae;">
        <strong>Prompt:</strong> 读取杜甫诗选.txt，统计每首诗字数，生成 python 脚本并保存。
      </p>
      <p style="font-size: 0.9em; color: #666;">
        演示 Agent 在权限引擎保护下，精准执行跨文件读取、Python 代码生成及本地文件系统写入。<br>
        <i>Demonstrates code generation and file system operations under the protection of the permission engine.</i>
      </p>
      <video src="https://github.com/user-attachments/assets/ddfc4e3f-2820-4c6a-9b1e-779b035247f1" controls="controls" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"></video>
    </td>
    <td style="padding: 10px; border: none; vertical-align: top;">
      <strong>2. 多轮对话与文档自动化生成</strong><br>
      <i>Multi-turn Interaction & Doc Gen</i>
      <div style="font-size: 0.82em; background-color: #f6f8fa; padding: 8px; border-radius: 4px; border-left: 4px solid #33b3ae;">
        <strong>Multi-turn Prompts:</strong><br>
        1. 总结 loop.py 核心架构与流程<br>
        2. 给出 3 个最重要的改进点<br>
        3. <strong>将改进方向总结并导出为 <code>改进.md</code></strong>
      </div>
      <p style="font-size: 0.9em; color: #666; margin-top: 8px;">
        演示 Agent 对长上下文的理解能力，并根据对话生成的审计结论自动执行本地文档持久化任务。<br>
        <i>Showcases context retention and autonomous document generation based on audit results.</i>
      </p>
      <video src="https://github.com/user-attachments/assets/2d4461c0-4775-4e2b-829c-d9dd0b52a557" controls="controls" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"></video>
    </td>
  </tr>
</table>

<br>

<div style="width: 100%; padding: 10px; border: 1px solid #eee; border-radius: 8px;">
  <strong>3. GUI 视觉交互全流程 (核心演示)</strong><br>
  <i>Full GUI & Vision Interaction Workflow (Core Demo)</i>
  <p style="font-size: 0.85em; background-color: #f6f8fa; padding: 8px; border-radius: 4px; border-left: 4px solid #33b3ae; margin: 10px 0;">
    <strong>Prompt:</strong> 截取当前屏幕，保存图像并描述你在截图中看到了什么。
  </p>
  <p style="font-size: 0.9em; color: #666;">
    完整演示 Agent 如何通过 IPC 桥接 macOS 无障碍服务实现视觉感知，结合 VLM (视觉大模型) 实现对图形界面的智能识别与反馈。<br>
    <i>A full walkthrough of the Agent perceiving the screen via macOS Accessibility services and generating intelligent descriptions.</i>
  </p>
  <video src="https://github.com/user-attachments/assets/c4544462-f9ac-4c2e-8663-eca6c54d0c7b" controls="controls" style="width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"></video>
</div>

## 安装

### 环境要求

- Python 3.11+

### 从源码安装

```bash
git clone https://github.com/<your-username>/DRYClawV0-1-0.git
cd DRYClawV0-1-0
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 快速开始

```bash
dryclaw -p "用一句话介绍 DRYClaw"
```
或者
```bash
cd /Users/Projects/DRYClaw
source .venv/bin/activate
dryclaw
```
可以直接在项目cli里使用，直接对话（支持多轮对话）


## 环境配置

DRYClaw 会从用户目录读取本地运行配置：

- ~/.dryclaw/config.yaml
- ~/.dryclaw/credentials.json

不要提交真实密钥或私有端点。请使用模板文件：

- [examples/config.example.yaml](examples/config.example.yaml)
- [examples/credentials.example.json](examples/credentials.example.json)

## CLI 用法

常用命令：

- dryclaw --help
- dryclaw -p "..."
- dryclaw --provider anthropic --model claude-3-7-sonnet
- dryclaw --check-auth
- dryclaw schedule create --cron "*/5 * * * *" --prompt "..."
- dryclaw schedule list
- dryclaw schedule delete <id>
- dryclaw daemon start
- dryclaw daemon status
- dryclaw daemon stop

完整文档见 [docs/index.md](docs/index.md)。

## 演示视频

视频索引见 [docs/videos.md](docs/videos.md)。

建议托管平台：

- YouTube
- Bilibili
- GitHub Releases

## 致谢与来源说明

DRYClaw 在设计思路与部分依赖策略上借鉴了 ShanClaw。感谢 ShanClaw 团队的开源工作。

重要说明：

- ax_server 相关依赖与集成路径与 ShanClaw 有关联。
- 启用相关功能前，请核对对应许可证与使用条件。
- 重新分发来自外部项目的组件时，请保留必要的署名与许可证声明。
---

## ⚠️ 声明与免责 | Disclaimer

> **本项目仅用于学习与工程演示，并非面向生产环境设计的自治系统。**
> 
> **DRYClaw** 是一个旨在探索 LLM Agent 底层工程机制、工具调度架构及 GUI 自动化链路的实验性项目。其核心目的在于技术验证与学术研究，不建议将其部署于任何关键生产环境或涉及敏感数据的生产业务中。开发者不对因使用本工具而导致的任何直接或间接资产损失或系统风险承担责任。
>
> ---
>
> **This project is for educational and demonstration purposes only and is NOT an autonomous system designed for production environments.**
> 
> **DRYClaw** is an experimental project focused on exploring the underlying engineering mechanisms of Agent Loops, tool orchestration architectures, and GUI automation workflows. It is intended for technical verification and academic research. We strongly advise against deploying this system in critical production environments or handling sensitive business data. The developer assumes no liability for any direct or indirect asset loss or system risks resulting from the use of this tool.
