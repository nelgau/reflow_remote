import numpy as np
from dataclasses import dataclass

class Profile:
    def __init__(self):
        self.points = []

    def add_point(self, t, temp):
        self.points.append((t, temp))

    def sample(self, interval=1, should_round=False):
        if len(self.points) == 0:
            return []

        times = [x[0] for x in self.points]
        temps = [x[1] for x in self.points]

        t_max = max(times)
        sample_ts = np.arange(0.0, t_max, interval)
        samples = np.interp(sample_ts, times, temps)

        if should_round:
            samples = np.rint(samples)

        ts = list(sample_ts)
        ss = list(samples)

        return (ts, ss)

@dataclass
class Builder:
    ##
    # Temperatures
    #
    T_liquidus:     float = 217

    T_initial:      float = 50
    T_final:        float = 120

    T_soak_min:     float = 150
    T_soak_max:     float = 200
    T_peak:         float = 250

    ##
    # Durations
    #
    t_initial:      float = 0
    t_peak:         float = 30

    ##
    # Slopes
    #
    ts_preheat:     float = 1.5
    ts_soak:        float = 0.3
    ts_ramp_up:     float = 1
    ts_ramp_down:   float = 1

    def build(self):
        t_preheat   = (self.T_soak_min - self.T_initial)  / self.ts_preheat
        t_soak      = (self.T_soak_max - self.T_soak_min) / self.ts_soak
        t_ramp_up   = (self.T_peak     - self.T_soak_max) / self.ts_ramp_up
        t_ramp_down = (self.T_peak     - self.T_final)    / self.ts_ramp_down

        t0 = self.t_initial
        t1 = t0 + t_preheat
        t2 = t1 + t_soak
        t3 = t2 + t_ramp_up
        t4 = t3 + self.t_peak
        t5 = t4 + t_ramp_down

        profile = Profile()
        profile.add_point(t0, self.T_initial)
        profile.add_point(t1, self.T_soak_min)
        profile.add_point(t2, self.T_soak_max)
        profile.add_point(t3, self.T_peak)
        profile.add_point(t4, self.T_peak)
        profile.add_point(t5, self.T_final)

        return profile
