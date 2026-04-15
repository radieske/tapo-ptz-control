import sys

from shared.tapo import TapoConfig, TapoService


def print_menu() -> None:
    print("\n" + "=" * 44)
    print("  PTZ Control - Tapo C500")
    print("=" * 44)
    print("  w/s/a/d   -> Short step (tap)")
    print("  W/S/A/D   -> Continuous move")
    print("  b / B     -> Stop motor")
    print("  q         -> Quit")
    print("=" * 44)


def create_service() -> TapoService:
    config = TapoConfig.from_env()
    print(f"Connecting to {config.ip}:{config.port}...")
    try:
        service = TapoService(config)
        service.connect()
        print("Connected successfully!\n")
        return service
    except Exception as exc:
        message = str(exc).lower()
        if "environment variable is not set" in message:
            print("Error: TAPO_PASS environment variable is not set.")
            print("  Copy .env.example to .env and fill in your credentials.")
        elif "authority" in message:
            print("Authentication error: check your credentials and make sure your system clock is synced.")
        elif "connection" in message or "timeout" in message:
            print(f"Network error: could not reach {config.ip}:{config.port}. Check IP and port.")
        else:
            print(f"Connection error: {exc}")
        sys.exit(1)


def main() -> None:
    service = create_service()
    print_menu()

    commands = {
        "w": lambda: service.move_step("up"),
        "s": lambda: service.move_step("down"),
        "a": lambda: service.move_step("left"),
        "d": lambda: service.move_step("right"),
        "W": lambda: service.move_continuous("down"),
        "S": lambda: service.move_continuous("up"),
        "A": lambda: service.move_continuous("left"),
        "D": lambda: service.move_continuous("right"),
        "b": service.stop,
        "B": service.stop,
    }

    while True:
        try:
            cmd = input("Command: ")
        except (KeyboardInterrupt, EOFError):
            print("\nQuitting...")
            break

        if cmd == "q":
            print("Quitting...")
            break

        handler = commands.get(cmd)
        if handler is None:
            print(f"Unknown command: '{cmd}'. Use w/a/s/d, W/A/S/D, b or q.")
            continue

        try:
            handler()
        except Exception as exc:
            print(f"Error executing command '{cmd}': {exc}")
