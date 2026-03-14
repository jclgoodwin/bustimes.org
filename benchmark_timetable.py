"""
Standalone benchmark comparing old vs new sort_columns / compare_trips
implementations. No Django required — uses mock objects that mirror the
real Row / Trip / Cell data structures.
"""
import datetime
import graphlib
import random
import time
from functools import cmp_to_key, partial


# ---------------------------------------------------------------------------
# Minimal mock objects
# ---------------------------------------------------------------------------

class MockStop:
    def __init__(self, atco_code):
        self.atco_code = atco_code
        self.stop_code = atco_code


class MockRow:
    def __init__(self, stop_code):
        self.stop = MockStop(stop_code)
        self.times = []


class MockCell:
    def __init__(self, t):
        self._t = t  # datetime.timedelta

    def departure_or_arrival(self):
        return self._t


class MockTrip:
    _id_counter = 0

    def __init__(self, start, stop_indices, all_rows):
        MockTrip._id_counter += 1
        self.id = MockTrip._id_counter
        self.start = start
        self.top = all_rows[stop_indices[0]]
        self.bottom = all_rows[stop_indices[-1]]


# ---------------------------------------------------------------------------
# Build a realistic timetable scenario
# ---------------------------------------------------------------------------

def build_scenario(n_trips, n_stops, seed=42):
    """
    Returns (rows, trips) where:
    - rows  : list of MockRow (length n_stops)
    - trips : list of MockTrip, each covering most stops with a cell time
    """
    rng = random.Random(seed)
    MockTrip._id_counter = 0

    rows = [MockRow(f"S{i:04d}") for i in range(n_stops)]

    trips = []
    base = datetime.timedelta(hours=6)
    interval = datetime.timedelta(minutes=10)

    for t_idx in range(n_trips):
        start_time = base + interval * t_idx
        # Each trip covers a contiguous slice of stops (with minor variation)
        first = rng.randint(0, max(0, n_stops // 10 - 1))
        last = rng.randint(n_stops - n_stops // 10, n_stops - 1)
        stop_indices = list(range(first, last + 1))

        trip = MockTrip(start_time, stop_indices, rows)
        trips.append(trip)

        # Pre-fill row.times with empty strings so column count stays consistent
        for row in rows:
            row.times.append("")

        # Fill in cells for the stops this trip serves
        for i, s_idx in enumerate(stop_indices):
            cell_time = start_time + datetime.timedelta(minutes=i * 2)
            rows[s_idx].times[t_idx] = MockCell(cell_time)

    return rows, trips


# ---------------------------------------------------------------------------
# OLD implementation
# ---------------------------------------------------------------------------

def compare_trips_old(rows, trip_ids, a, b):
    a_top = rows.index(a.top)
    a_bottom = rows.index(a.bottom)
    b_top = rows.index(b.top)
    b_bottom = rows.index(b.bottom)

    a_index = trip_ids.index(a.id)
    b_index = trip_ids.index(b.id)

    for row in rows[max(a_top, b_top): min(a_bottom, b_bottom) + 1]:
        if row.times[a_index] and row.times[b_index]:
            a_time = row.times[a_index].departure_or_arrival()
            b_time = row.times[b_index].departure_or_arrival()
            return (a_time - b_time).total_seconds()

    if a_top > b_bottom:
        a_time, b_time = a.start, b.start  # simplified
    elif b_top > a_bottom:
        a_time, b_time = a.start, b.start
    else:
        a_time, b_time = a.start, b.start

    if a_time and b_time:
        return (a_time - b_time).total_seconds()
    return 0


def sort_columns_old(trips, rows):
    sorter = graphlib.TopologicalSorter()
    for a_index, a in enumerate(trips):
        a_top = rows.index(a.top)
        a_bottom = rows.index(a.bottom)

        for b_index, b in enumerate(trips):
            if a_index == b_index:
                continue

            b_top = rows.index(b.top)
            b_bottom = rows.index(b.bottom)

            for row in rows[max(a_top, b_top): min(a_bottom, b_bottom) + 1]:
                if row.times[a_index] and row.times[b_index]:
                    a_time = row.times[a_index].departure_or_arrival()
                    b_time = row.times[b_index].departure_or_arrival()
                    if a_time > b_time:
                        sorter.add(a.id, b.id)
                    elif a_time < b_time:
                        sorter.add(b.id, a.id)
                    elif b.top is a.bottom:
                        sorter.add(b.id, a.id)
                    break

    trip_ids = [trip.id for trip in trips]
    try:
        indices = [trip_ids.index(trip_id) for trip_id in sorter.static_order()]
        assert len(trip_ids) == len(indices)
        trips = [trips[i] for i in indices]
    except (graphlib.CycleError, AssertionError):
        trips.sort(key=cmp_to_key(partial(compare_trips_old, rows, trip_ids)))
        new_trip_ids = [trip.id for trip in trips]
        indices = [trip_ids.index(trip_id) for trip_id in new_trip_ids]

    for row in rows:
        row.times = [row.times[i] for i in indices]

    return trips


# ---------------------------------------------------------------------------
# NEW implementation
# ---------------------------------------------------------------------------

def compare_trips_new(rows, trip_id_to_index, row_positions, a, b):
    a_top = row_positions[a.top]
    a_bottom = row_positions[a.bottom]
    b_top = row_positions[b.top]
    b_bottom = row_positions[b.bottom]

    a_index = trip_id_to_index[a.id]
    b_index = trip_id_to_index[b.id]

    for row in rows[max(a_top, b_top): min(a_bottom, b_bottom) + 1]:
        if row.times[a_index] and row.times[b_index]:
            a_time = row.times[a_index].departure_or_arrival()
            b_time = row.times[b_index].departure_or_arrival()
            return (a_time - b_time).total_seconds()

    a_time, b_time = a.start, b.start
    if a_time and b_time:
        return (a_time - b_time).total_seconds()
    return 0


def sort_columns_new(trips, rows):
    row_position = {row: i for i, row in enumerate(rows)}
    trip_bounds = [
        (row_position[trip.top], row_position[trip.bottom])
        for trip in trips
    ]

    sorter = graphlib.TopologicalSorter()
    for a_index, a in enumerate(trips):
        a_top, a_bottom = trip_bounds[a_index]

        for b_index in range(a_index + 1, len(trips)):
            b = trips[b_index]
            b_top, b_bottom = trip_bounds[b_index]

            overlap_start = max(a_top, b_top)
            overlap_end = min(a_bottom, b_bottom)
            if overlap_start > overlap_end:
                continue

            for row in rows[overlap_start: overlap_end + 1]:
                if row.times[a_index] and row.times[b_index]:
                    a_time = row.times[a_index].departure_or_arrival()
                    b_time = row.times[b_index].departure_or_arrival()
                    if a_time > b_time:
                        sorter.add(a.id, b.id)
                    elif a_time < b_time:
                        sorter.add(b.id, a.id)
                    elif b.top is a.bottom:
                        sorter.add(b.id, a.id)
                    elif a.top is b.bottom:
                        sorter.add(a.id, b.id)
                    break

    trip_ids = [trip.id for trip in trips]
    try:
        indices = [trip_ids.index(trip_id) for trip_id in sorter.static_order()]
        assert len(trip_ids) == len(indices)
        trips = [trips[i] for i in indices]
    except (graphlib.CycleError, AssertionError):
        trip_id_to_index = {trip_id: i for i, trip_id in enumerate(trip_ids)}
        trips.sort(
            key=cmp_to_key(
                partial(compare_trips_new, rows, trip_id_to_index, row_position)
            )
        )
        new_trip_ids = [trip.id for trip in trips]
        indices = [trip_ids.index(trip_id) for trip_id in new_trip_ids]

    for row in rows:
        row.times = [row.times[i] for i in indices]

    return trips


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def bench(label, fn, rows, trips, repeats=3):
    times = []
    for _ in range(repeats):
        # Deep-copy row.times and trips list so each run starts fresh
        saved_times = [list(row.times) for row in rows]
        trips_copy = list(trips)

        t0 = time.perf_counter()
        fn(trips_copy, rows)
        elapsed = time.perf_counter() - t0
        times.append(elapsed)

        # Restore
        for row, saved in zip(rows, saved_times):
            row.times = saved

    best = min(times)
    return best


scenarios = [
    (50,  30,  "small  ( 50 trips,  30 stops)"),
    (150, 60,  "medium (150 trips,  60 stops)"),
    (400, 80,  "large  (400 trips,  80 stops)"),
    (800, 100, "huge   (800 trips, 100 stops)"),
]

print(f"{'Scenario':<38} {'Old (s)':>10} {'New (s)':>10} {'Speedup':>10}")
print("-" * 72)

for n_trips, n_stops, label in scenarios:
    rows, trips = build_scenario(n_trips, n_stops)

    old_t = bench("old", sort_columns_old, rows, trips)
    new_t = bench("new", sort_columns_new, rows, trips)

    speedup = old_t / new_t if new_t > 0 else float("inf")
    print(f"{label:<38} {old_t:>10.3f} {new_t:>10.3f} {speedup:>9.1f}x")
