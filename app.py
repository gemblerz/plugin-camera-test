import logging
import argparse
import time
import threading
from datetime import datetime, timezone

from croniter import croniter
from waggle.plugin import Plugin
from waggle.data.vision import Camera, get_timestamp, ImageSample, RGB

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    datefmt='%Y/%m/%d %H:%M:%S')


class MyCamera:
    def __init__(self, stream):
        self.cam = Camera(stream)
        self.my_loop = threading.Thread(target=self._run)
        self.lock = threading.Lock()
        self.need_to_stop = False

    def __enter__(self):
        self.cam.__enter__()
        self.my_loop.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.need_to_stop = True
        self.my_loop.join()
        self.cam.__exit__(exc_type, exc_val, exc_tb)

    def _run(self):
        while not self.need_to_stop:
            self.lock.acquire()
            self.cam.capture.capture.grab()
            self.timestamp = get_timestamp()
            self.lock.release()
            time.sleep(0.01)

    def snapshot(self):
        self.lock.acquire()
        data, ok = self.cam.capture.capture.retrieve()
        timestamp = self.timestamp
        self.lock.release()
        if not ok:
            raise RuntimeError("failed to retrieve the taken snapshot")
        return ImageSample(data=data, timestamp=timestamp, format=RGB)


# stream_in_buffer renders the current approach on receiving a camera stream.
# we expect that this eventually fails on time synchonization as read() is slower
# than the rate that frames are buffered
def stream_in_buffer(stream):
    now = datetime.now(timezone.utc)
    cron = croniter(args.cronjob, now)
    with Plugin() as plugin, Camera(stream) as cap:
        while True:
            n = cron.get_next(datetime).replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            next_in_seconds = (n - now).total_seconds()
            if next_in_seconds > 0:
                logging.info(f'sleeping for {next_in_seconds} seconds')
                time.sleep(next_in_seconds)
            logging.info("capturing...")
            sample = cap.snapshot()
            sample.save("sample.jpg")
            plugin.upload_file("sample.jpg")


def drain_buffer(stream):
    now = datetime.now(timezone.utc)
    cron = croniter(args.cronjob, now)
    with Plugin() as plugin, MyCamera(stream) as cap:
        while True:
            n = cron.get_next(datetime).replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            next_in_seconds = (n - now).total_seconds()
            if next_in_seconds > 0:
                logging.info(f'sleeping for {next_in_seconds} seconds')
                time.sleep(next_in_seconds)
            logging.info("capturing...")
            sample = cap.snapshot()
            sample.save("sample.jpg")
            plugin.upload_file("sample.jpg")


def run(args):
    logging.info(f'"start getting a stream from {args.stream}')

    if args.mode == "buffered":
        return stream_in_buffer(args.stream)
    elif args.mode == "drained":
        return drain_buffer(args.stream)
    else:
        raise Exception(f'unknown mode ({args.mode})')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--stream', dest='stream',
        action='store', default="camera", type=str,
        help='ID or name of a stream, e.g. sample')
    parser.add_argument(
        '--mode', dest='mode',
        action='store', default="buffered", type=str,
        help='Select run mode: buffered, drained')
    parser.add_argument(
        '--cronjob', dest='cronjob',
        action='store', default="* * * * *", type=str,
        help='Time interval expressed in cronjob style')

    args = parser.parse_args()
    exit(run(args))