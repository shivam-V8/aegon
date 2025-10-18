# config logging
import structlog, sys
def setup_logging():
    structlog.configure(
        processors=[structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.add_log_level,
                    structlog.processors.JSONRenderer()],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    )
    return structlog.get_logger()
