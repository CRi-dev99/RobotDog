import threading
import time
from dataclasses import dataclass


SPEED_OF_SOUND_CM_S = 34300.0

# Physical BOARD pins from pi_server/routesv2.py showDistance().
BOARD_TRIGGER_PIN = 29
BOARD_ECHO_PIN = 37
BOARD_5V_PIN = 4

# Only the pins used by this project are mapped here.
BOARD_TO_BCM = {
    BOARD_TRIGGER_PIN: 5,
    BOARD_ECHO_PIN: 26,
}


@dataclass(frozen=True)
class UltrasonicReading:
    distance_cm: float
    pulse_seconds: float
    timestamp: float


class Ultrasonic:
    def __init__(
        self,
        trigger_pin=BOARD_TRIGGER_PIN,
        echo_pin=BOARD_ECHO_PIN,
        pin_mode="BOARD",
        gpiochip=None,
        timeout=0.06,
        echo_clear_timeout=0.25,
        min_interval_s=0.06,
    ):
        try:
            import lgpio
        except ImportError as exc:
            raise RuntimeError(
                "python3-lgpio is required for the Pi 5 ultrasonic sensor. "
                "Install it with: sudo apt install python3-lgpio gpiod"
            ) from exc

        self._lgpio = lgpio
        self.trigger_gpio = self._pin_to_bcm(trigger_pin, pin_mode)
        self.echo_gpio = self._pin_to_bcm(echo_pin, pin_mode)
        self.timeout = timeout
        self.echo_clear_timeout = echo_clear_timeout
        self.min_interval_s = min_interval_s

        self._handle = None
        self._chip = None
        self._callback = None
        self._closed = True

        self._measure_lock = threading.Lock()
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

        self._state = "idle"
        self._seq = 0
        self._done_seq = None
        self._rise_tick = None
        self._pulse_s = None
        self._last_trigger_time = 0.0

        self._open_gpiochip(gpiochip)

    def _pin_to_bcm(self, pin, pin_mode):
        mode = pin_mode.upper()
        if mode == "BCM":
            return pin
        if mode != "BOARD":
            raise ValueError("pin_mode must be 'BOARD' or 'BCM'")
        try:
            return BOARD_TO_BCM[pin]
        except KeyError as exc:
            raise ValueError(
                f"BOARD pin {pin} is not mapped. Add it to BOARD_TO_BCM or use pin_mode='BCM'."
            ) from exc

    def _open_gpiochip(self, requested_chip):
        chips = [requested_chip] if requested_chip is not None else [4, 0]
        errors = []

        for chip in chips:
            handle = None
            try:
                handle = self._lgpio.gpiochip_open(chip)
                self._lgpio.gpio_claim_output(handle, self.trigger_gpio, 0)
                self._lgpio.gpio_claim_alert(
                    handle,
                    self.echo_gpio,
                    self._lgpio.BOTH_EDGES,
                )
                callback = self._lgpio.callback(
                    handle,
                    self.echo_gpio,
                    self._lgpio.BOTH_EDGES,
                    self._echo_interrupt,
                )

                self._handle = handle
                self._chip = chip
                self._callback = callback
                self._closed = False
                time.sleep(0.05)
                return

            except Exception as exc:
                errors.append(f"gpiochip{chip}: {exc}")
                if handle is not None:
                    try:
                        self._lgpio.gpiochip_close(handle)
                    except Exception:
                        pass

        raise RuntimeError(
            "Could not initialize ultrasonic sensor on "
            f"trigger GPIO{self.trigger_gpio}, echo GPIO{self.echo_gpio}. "
            + "; ".join(errors)
        )

    def _ensure_open(self):
        if self._closed or self._handle is None:
            raise RuntimeError("Ultrasonic sensor is closed")

    def _echo_interrupt(self, chip, gpio, level, tick):
        if level not in (0, 1):
            return

        with self._condition:
            if self._state == "closed":
                return

            if self._state == "waiting_rise" and level == 1:
                self._rise_tick = tick
                self._state = "waiting_fall"

            elif self._state == "waiting_fall" and level == 0:
                if self._rise_tick is None:
                    return

                pulse_ns = tick - self._rise_tick
                if pulse_ns <= 0:
                    return

                self._pulse_s = pulse_ns / 1_000_000_000.0
                self._done_seq = self._seq
                self._state = "done"
                self._condition.notify_all()

    def _wait_for_echo_low(self, timeout):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._lgpio.gpio_read(self._handle, self.echo_gpio) == 0:
                return True
            time.sleep(0.0005)

        return False

    def _enforce_min_interval(self):
        if self.min_interval_s <= 0:
            return

        remaining = self.min_interval_s - (time.monotonic() - self._last_trigger_time)
        if remaining > 0:
            time.sleep(remaining)

    def read(self, timeout=None, echo_clear_timeout=None):
        timeout = self.timeout if timeout is None else timeout
        echo_clear_timeout = (
            self.echo_clear_timeout if echo_clear_timeout is None else echo_clear_timeout
        )

        with self._measure_lock:
            self._ensure_open()
            self._enforce_min_interval()

            if not self._wait_for_echo_low(echo_clear_timeout):
                raise TimeoutError("ECHO stuck high before trigger")

            with self._condition:
                self._seq += 1
                seq = self._seq
                self._state = "waiting_rise"
                self._done_seq = None
                self._rise_tick = None
                self._pulse_s = None

            self._lgpio.gpio_write(self._handle, self.trigger_gpio, 1)
            time.sleep(0.000015)
            self._lgpio.gpio_write(self._handle, self.trigger_gpio, 0)
            self._last_trigger_time = time.monotonic()

            deadline = time.monotonic() + timeout
            timeout_state = None

            with self._condition:
                while self._done_seq != seq:
                    remaining = deadline - time.monotonic()

                    if remaining <= 0:
                        timeout_state = self._state
                        self._state = "idle"
                        self._rise_tick = None
                        self._pulse_s = None
                        break

                    self._condition.wait(remaining)

                if self._done_seq == seq:
                    pulse_s = self._pulse_s
                    self._state = "idle"
                else:
                    pulse_s = None

            if pulse_s is None:
                echo_cleared = self._wait_for_echo_low(echo_clear_timeout)

                if timeout_state == "waiting_rise":
                    raise TimeoutError("ECHO timeout: never rose")

                if echo_cleared:
                    raise TimeoutError("ECHO timeout: rose but did not fall")

                raise TimeoutError("ECHO timeout: remained high")

            return UltrasonicReading(
                distance_cm=pulse_s * SPEED_OF_SOUND_CM_S / 2.0,
                pulse_seconds=pulse_s,
                timestamp=time.monotonic(),
            )

    def get_distance(self):
        return int(round(self.read().distance_cm))

    def close(self):
        with self._measure_lock:
            if self._closed:
                return

            self._closed = True

            with self._condition:
                self._state = "closed"
                self._condition.notify_all()

            if self._callback is not None:
                try:
                    self._callback.cancel()
                except Exception:
                    pass
                self._callback = None

            if self._handle is not None:
                try:
                    self._lgpio.gpio_write(self._handle, self.trigger_gpio, 0)
                except Exception:
                    pass

                try:
                    self._lgpio.gpiochip_close(self._handle)
                except Exception:
                    pass

                self._handle = None

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


if __name__ == "__main__":
    with Ultrasonic() as sensor:
        while True:
            try:
                print(f"Distance: {sensor.get_distance()} cm")
            except Exception as exc:
                print(f"Distance error: {exc}")
            time.sleep(0.2)
