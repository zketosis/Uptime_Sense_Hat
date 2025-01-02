import asyncio
import csv
import sys
import logging
from datetime import datetime
from sense_hat import SenseHat

sense = SenseHat()

# Configure logging to stdout
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust level for detailed output

# Clear existing handlers to avoid duplicate logs
if logger.hasHandlers():
    logger.handlers.clear()

# Create and add a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Log everything to console
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Disable propagation to the root logger
logger.propagate = False

logger.info("Program started: Sense HAT Monitor initializing...")

# Define colors
RED = (255, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
OFF = (0, 0, 0)


async def ping(hostname):
    """Pings a hostname and returns True if successful, False otherwise."""
    command = f"ping -c 1 {hostname}"
    logger.debug(f"Executing command: {command}")
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    result = proc.returncode == 0
    logger.info(f"Ping {hostname}: {'Success' if result else 'Failure'}")
    if stderr:
        logger.error(f"Ping error: {stderr.decode().strip()}")
    return result


async def curl(url):
    """Performs a curl request to a URL and returns True if successful, False otherwise."""
    command = f"curl -s -o /dev/null -w '%{{http_code}}' {url}"
    logger.debug(f"Executing command: {command}")
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    status_code = stdout.decode().strip()
    result = status_code == "200"
    logger.info(f"Curl {url}: Status code {status_code}, {'Success' if result else 'Failure'}")
    if stderr:
        logger.error(f"Curl error: {stderr.decode().strip()}")
    return result


async def check_host(x, y, method, hostname, interval, status_dict):
    """Periodically checks a host using ping or curl and updates the Sense HAT display."""
    logger.info(f"Starting check for host: {hostname} at ({x}, {y}) using {method}")
    while True:
        sense.set_pixel(x - 1, y - 1, YELLOW)  # Set to yellow before checking
        await asyncio.sleep(1)  # Brief delay to show yellow

        if method == "ping":
            result = await ping(hostname)
        elif method == "curl":
            result = await curl(hostname)
        else:
            raise ValueError(f"Invalid method: {method}")

        status_dict[(x, y)] = result  # Update the latest status

        if result:
            sense.set_pixel(x - 1, y - 1, GREEN)
        else:
            sense.set_pixel(x - 1, y - 1, RED)

        logger.debug(f"Host {hostname} check result: {'UP' if result else 'DOWN'}")
        await asyncio.sleep(interval - 1)  # Adjust sleep for yellow delay


async def blink_color(x, y, color, on_duration, off_duration):
    """Blinks a color at the specified coordinates."""
    logger.info(f"Starting blink task at ({x}, {y}) with color {color}")
    while True:
        sense.set_pixel(x - 1, y - 1, color)
        await asyncio.sleep(on_duration)
        sense.set_pixel(x - 1, y - 1, OFF)
        await asyncio.sleep(off_duration)


async def display_report(report_interval, status_dict):
    """Periodically displays a report on the Sense HAT display."""
    logger.info(f"Starting report task with interval {report_interval} seconds")
    while True:
        up_count = sum(1 for status in status_dict.values() if status)
        total_count = len(status_dict)
        down_count = total_count - up_count

        message = f"{up_count}/{total_count} UP {down_count}/{total_count} DOWN"
        logger.info(f"Report: {message}")
        if up_count == total_count:
            sense.show_message(message, text_colour=GREEN, scroll_speed=0.05)
        else:
            sense.show_message(message, text_colour=RED, scroll_speed=0.05)

        await asyncio.sleep(report_interval)


async def main():
    """Main function to read the CSV file and start the tasks."""
    logger.info("Reading hosts.csv and initializing tasks...")
    tasks = []
    status_dict = {}  # To store the latest status of each host
    with open("hosts.csv", "r") as f:
        reader = csv.reader(f)
        for row in reader:
            x, y, *args = row
            x = int(x)
            y = int(y)

            if args[0] == "report":
                report_interval = int(args[1])
                report_task = asyncio.create_task(
                    display_report(report_interval, status_dict)
                )
            elif args[0] in ("ping", "curl"):
                method, hostname, interval = args
                interval = int(interval)
                task = asyncio.create_task(
                    check_host(x, y, method, hostname, interval, status_dict)
                )
                tasks.append(task)
            elif args[0] == "color":
                color_name = args[1].lower()
                if color_name == "red":
                    color = RED
                elif color_name == "green":
                    color = GREEN
                elif color_name == "yellow":
                    color = YELLOW
                else:
                    raise ValueError(f"Invalid color: {color_name}")

                if len(args) > 2:
                    on_duration = int(args[2])
                    off_duration = int(args[3])
                    asyncio.create_task(
                        blink_color(x, y, color, on_duration, off_duration)
                    )
                else:
                    sense.set_pixel(x - 1, y - 1, color)
            else:
                raise ValueError(f"Invalid command: {args[0]}")

    logger.info("All tasks initialized. Starting asyncio event loop.")
    try:
        await asyncio.gather(report_task, *tasks)
    except Exception as e:
        logger.exception("Unhandled exception occurred:")


if __name__ == "__main__":
    print("Starting the application...")
    logger.info("Application is about to enter the asyncio event loop.")
    asyncio.run(main())
