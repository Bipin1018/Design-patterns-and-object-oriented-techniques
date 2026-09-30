"""The simulation sampler.

Records a reading for every simulation sensor whose interval has elapsed.

run_once takes `now` as an argument rather than calling the clock itself. That
one decision is what makes this testable: a test can hand it a time ten minutes
in the future and check that a row appeared, without sleeping for ten minutes.
The lifespan task passes the real clock.

It does not sample MQTT devices. Generating a value for a device that reports
for itself would be inventing data it never sent. The repository query already
excludes them, and the count this method returns is the proof.
"""

import logging
from datetime import datetime

from src.application.readings.service import ReadingIngest
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.reading_repository import ReadingRepository

logger = logging.getLogger(__name__)


class SimulationSampler:
    def __init__(
        self,
        devices: DeviceRepository,
        readings: ReadingRepository,
        ingest: ReadingIngest,
    ) -> None:
        self._devices = devices
        self._readings = readings
        self._ingest = ingest

    def run_once(self, now: datetime) -> int:
        """Record every due device. Returns how many rows were written.

        Due means one of two things: the device has no reading at all, or its
        last reading is at least sampling_interval_seconds old. A device read
        manually a second ago is therefore not due, which is what stops the
        sampler from doubling up on a user who just pressed the button.
        """
        candidates = self._devices.list_sampling_candidates()
        if not candidates:
            return 0

        device_ids = [device.id for device in candidates if device.id is not None]
        last_seen = self._readings.latest_recorded_at(device_ids)

        written = 0
        for device in candidates:
            if device.id is None:
                continue

            last = last_seen.get(device.id)
            if last is not None:
                elapsed = (now - last).total_seconds()
                if elapsed < device.sampling_interval_seconds:
                    continue

            try:
                self._ingest.take_reading(device.id)
                written += 1
            except Exception:
                # One broken device must not stop the tick. The others are
                # still due, and the sampler runs again in a few seconds.
                logger.exception("Sampler could not read device %s", device.id)

        return written