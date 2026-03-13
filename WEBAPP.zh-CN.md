# Web 版部署说明

项目现在包含一个基于现有 CLI 的 Web 壳，适合部署到公网后让其他人直接通过浏览器使用。

## 功能范围

- 提供网页上传入口
- 使用匿名总额度控制每日任务数
- 串行执行任务，复用 `auto_subtitle.py`
- 保存日志和输出文件，处理完成后可下载

## 本地启动

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
Copy-Item .env.web.example .env.web.local
.\run_web.bat
```

默认访问地址：`http://127.0.0.1:8000`

macOS / Linux:

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.web.example .env.web.local
bash run_web.sh
```

## 公网部署

推荐直接使用 Docker Compose：

```bash
cp .env.web.example .env.web.local
docker compose up -d --build
```

运行数据会保存到 `web_data/`，包括：

- `app.db`：任务和额度记录
- `uploads/`：上传原始视频
- `jobs/<job-id>/`：日志和输出文件

如果你想把宿主机端口改成 `7500` 这类非默认值，请在运行 `docker compose` 前额外设置 `WEB_HOST_PORT`，或写入仓库根目录 `.env` 文件。

## 关键环境变量

- `WEB_DAILY_QUOTA`：匿名总额度
- `WEB_HOST_PORT`：Docker Compose 对外暴露的宿主机端口
- `WEB_MAX_UPLOAD_MB`：单文件最大体积
- `WEB_MAX_QUEUE_SIZE`：最大排队任务数
- `WEB_JOB_TIMEOUT_SECONDS`：单任务超时时间
- `WEB_RESULT_TTL_HOURS`：结果保留时长
- `WEB_TIMEZONE`：每日额度重置时区

如果你启用页面上的 `AI Review`，对应的 `AI_REVIEW_PROVIDER`、`OPENAI_API_KEY`、`AI_REVIEW_MODEL` 等变量也需要在服务端配置。
