import multiprocessing

bind = "0.0.0.0:8080"

max_requests = 1000
max_requests_jitter = 50

log_file = "-"

workers = multiprocessing.cpu_count() * 2 + 1

worker_tmp_dir = "/dev/shm"
timeout = 30
