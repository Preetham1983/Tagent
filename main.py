"""Root entrypoint with guidance for the new multi-service architecture."""


def main() -> None:
    print("Tagent now uses microservices + React frontend.")
    print("Run backend/services/orchestrator-service on :8001")
    print("Run backend/services/teams-adapter-service on :3978")
    print("Run frontend with npm run dev")


if __name__ == "__main__":
    main()
