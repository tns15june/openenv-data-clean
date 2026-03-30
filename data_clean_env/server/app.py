"""FastAPI application for the DataClean Environment."""

from openenv.core.env_server.http_server import create_app

try:
    from .environment import DataCleanEnvironment
    from ..models import DataCleanAction, DataCleanObservation
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from server.environment import DataCleanEnvironment
    from models import DataCleanAction, DataCleanObservation

app = create_app(
    DataCleanEnvironment,
    DataCleanAction,
    DataCleanObservation,
    env_name="data_clean_env",
)


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
