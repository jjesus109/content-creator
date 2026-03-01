import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record_dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "pipeline_step": getattr(record, "pipeline_step", ""),
            "content_history_id": getattr(record, "content_history_id", ""),
        }
        if record.exc_info:
            record_dict["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(record_dict, ensure_ascii=False)


class PipelineLogger(logging.LoggerAdapter):
    """
    LoggerAdapter that merges pipeline context into every log call.

    Usage:
        plog = PipelineLogger(logger, {"pipeline_step": "script_gen", "content_history_id": ""})
        plog.extra["pipeline_step"] = "heygen_submit"
        plog.extra["content_history_id"] = content_history_id
    """

    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {}).update(self.extra)
        return msg, kwargs


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
