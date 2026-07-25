import uvicorn

from common.config import services


def main() -> None:
    config = services["llm-service"]
    uvicorn.run(
        "llm_service.main:app",
        host=config["host"],
        port=config["port"],
    )


if __name__ == "__main__":
    main()