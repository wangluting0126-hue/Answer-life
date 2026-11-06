FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN uv sync --no-dev --extra feishu --extra dingtalk
ENV ANSWERLIFE_HOME=/data HOST=0.0.0.0 PORT=8020
VOLUME /data
EXPOSE 8020
CMD ["uv", "run", "--no-sync", "answerlife", "serve"]
