import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run the private local Econ finance calculators.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    print(f"Econ finance app: http://127.0.0.1:{args.port}/ (Ctrl-C to stop)", flush=True)
    uvicorn.run("econ_sdd.web:create_local_app", factory=True, host="127.0.0.1", port=args.port,
                access_log=False, log_level="warning", proxy_headers=False)


if __name__ == "__main__":
    main()
