#!/usr/bin/env python3
"""
High-performance system metrics agent.
Exposes metrics at http://0.0.0.0:8000/metrics
Optional: ?compact=1 for minified JSON
"""

AGENT_VERSION = "1.0.0"

import json
import os
import time
import socket
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from threading import Lock, Thread
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

# Delta tracking for rate calculations
class DeltaTracker:
    __slots__ = ('_data', '_lock')

    def __init__(self):
        self._data = {}
        self._lock = Lock()

    def update(self, key, value):
        """Update value and return delta since last call"""
        with self._lock:
            now = time.monotonic()
            if key in self._data:
                old_val, old_time = self._data[key]
                time_delta = now - old_time
                val_delta = value - old_val
                self._data[key] = (value, now)
                if time_delta > 0:
                    return val_delta / time_delta
            self._data[key] = (value, now)
            return 0.0

tracker = DeltaTracker()

# Per-core CPU tracking
class CoreTracker:
    __slots__ = ('_cores', '_lock')

    def __init__(self):
        self._cores = {}
        self._lock = Lock()

    def update(self, core_id, idle, total):
        """Update core stats and return usage percent"""
        with self._lock:
            if core_id in self._cores:
                old_idle, old_total = self._cores[core_id]
                idle_delta = idle - old_idle
                total_delta = total - old_total
                self._cores[core_id] = (idle, total)
                if total_delta > 0:
                    return round((1.0 - idle_delta / total_delta) * 100, 1)
            self._cores[core_id] = (idle, total)
            return 0.0

core_tracker = CoreTracker()

# Cache static system info
@lru_cache(maxsize=1)
def get_static_info():
    """Cached static system information"""
    info = {
        'hostname': socket.gethostname(),
        'arch': os.uname().machine,
        'cpu_model': 'unknown',
        'cpu_count': os.cpu_count() or 1,
        'page_size': os.sysconf('SC_PAGE_SIZE'),
    }

    # CPU model (first occurrence)
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('model name'):
                    info['cpu_model'] = line.split(':', 1)[1].strip()
                    break
    except:
        pass

    # OS release info
    try:
        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('PRETTY_NAME='):
                    info['os'] = line.split('=', 1)[1].strip().strip('"')
                    break
    except:
        info['os'] = 'Linux'

    return info

def read_proc_file(path):
    """Fast proc file reader"""
    try:
        with open(path, 'r') as f:
            return f.read()
    except:
        return ''

def get_uptime_boot():
    """Get uptime and boot time"""
    try:
        content = read_proc_file('/proc/uptime')
        uptime = float(content.split()[0])
        boot_time = time.time() - uptime
        return {'uptime_seconds': round(uptime, 1), 'boot_time': int(boot_time)}
    except:
        return {'uptime_seconds': 0, 'boot_time': 0}

def get_cpu():
    """Get CPU usage with delta tracking"""
    try:
        content = read_proc_file('/proc/stat')
        lines = content.split('\n')

        # Overall CPU
        fields = [int(x) for x in lines[0].split()[1:8]]
        idle = fields[3] + fields[4]  # idle + iowait
        total = sum(fields)

        idle_rate = tracker.update('cpu_idle', idle)
        total_rate = tracker.update('cpu_total', total)

        if total_rate > 0:
            percent = round((1.0 - idle_rate / total_rate) * 100, 1)
        else:
            percent = 0.0
        percent = max(0, min(100, percent))

        # Per-core CPU
        cores = []
        for line in lines[1:]:
            if line.startswith('cpu') and len(line) > 3 and line[3].isdigit():
                parts = line.split()
                core_id = int(parts[0][3:])
                fields = [int(x) for x in parts[1:8]]
                c_idle = fields[3] + fields[4]
                c_total = sum(fields)
                usage = core_tracker.update(core_id, c_idle, c_total)
                cores.append({'id': core_id, 'percent': max(0, min(100, usage))})

        # Context switches and processes
        ctxt = 0
        procs_running = 0
        procs_blocked = 0
        for line in lines:
            if line.startswith('ctxt '):
                ctxt = int(line.split()[1])
            elif line.startswith('procs_running '):
                procs_running = int(line.split()[1])
            elif line.startswith('procs_blocked '):
                procs_blocked = int(line.split()[1])

        ctxt_rate = tracker.update('ctxt', ctxt)

        return {
            'percent': percent,
            'cores': cores,
            'context_switches_sec': round(ctxt_rate, 1),
            'procs_running': procs_running,
            'procs_blocked': procs_blocked
        }
    except:
        return {'percent': 0, 'cores': [], 'context_switches_sec': 0}

def get_cpu_freq():
    """Get CPU frequency from sysfs"""
    try:
        freqs = []
        cpu_path = '/sys/devices/system/cpu'
        for entry in os.listdir(cpu_path):
            if entry.startswith('cpu') and entry[3:].isdigit():
                freq_path = f'{cpu_path}/{entry}/cpufreq/scaling_cur_freq'
                try:
                    with open(freq_path, 'r') as f:
                        freqs.append(int(f.read().strip()) / 1000)  # kHz to MHz
                except:
                    pass
        if freqs:
            return {
                'current_mhz': round(sum(freqs) / len(freqs), 0),
                'min_mhz': round(min(freqs), 0),
                'max_mhz': round(max(freqs), 0)
            }
    except:
        pass
    return None

def get_temperatures():
    """Get system temperatures from thermal zones and hwmon"""
    temps = []

    # Thermal zones
    try:
        thermal_path = '/sys/class/thermal'
        for zone in os.listdir(thermal_path):
            if zone.startswith('thermal_zone'):
                try:
                    with open(f'{thermal_path}/{zone}/temp', 'r') as f:
                        temp = int(f.read().strip()) / 1000.0
                    name = 'unknown'
                    try:
                        with open(f'{thermal_path}/{zone}/type', 'r') as f:
                            name = f.read().strip()
                    except:
                        pass
                    temps.append({'name': name, 'celsius': round(temp, 1)})
                except:
                    pass
    except:
        pass

    # hwmon sensors (CPU package temp, etc)
    try:
        hwmon_path = '/sys/class/hwmon'
        for hw in os.listdir(hwmon_path):
            hw_path = f'{hwmon_path}/{hw}'
            try:
                for f in os.listdir(hw_path):
                    if f.startswith('temp') and f.endswith('_input'):
                        prefix = f[:-6]  # tempN
                        with open(f'{hw_path}/{f}', 'r') as tf:
                            temp = int(tf.read().strip()) / 1000.0
                        name = prefix
                        try:
                            with open(f'{hw_path}/{prefix}_label', 'r') as lf:
                                name = lf.read().strip()
                        except:
                            pass
                        temps.append({'name': name, 'celsius': round(temp, 1)})
            except:
                pass
    except:
        pass

    return temps if temps else None

def get_memory():
    """Get memory and swap from single meminfo read"""
    try:
        content = read_proc_file('/proc/meminfo')
        mem = {}
        for line in content.split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                mem[key.strip()] = int(val.split()[0]) * 1024  # KB to bytes

        total = mem.get('MemTotal', 0)
        available = mem.get('MemAvailable', 0)
        buffers = mem.get('Buffers', 0)
        cached = mem.get('Cached', 0)
        slab = mem.get('Slab', 0)
        used = total - available

        swap_total = mem.get('SwapTotal', 0)
        swap_free = mem.get('SwapFree', 0)
        swap_used = swap_total - swap_free

        return {
            'memory': {
                'total': total,
                'used': used,
                'available': available,
                'buffers': buffers,
                'cached': cached,
                'slab': slab,
                'percent': round((used / total) * 100, 1) if total > 0 else 0
            },
            'swap': {
                'total': swap_total,
                'used': swap_used,
                'free': swap_free,
                'percent': round((swap_used / swap_total) * 100, 1) if swap_total > 0 else 0
            }
        }
    except:
        return {
            'memory': {'total': 0, 'used': 0, 'percent': 0},
            'swap': {'total': 0, 'used': 0, 'percent': 0}
        }

def get_filesystems():
    """Get all mounted filesystems usage"""
    filesystems = []
    try:
        with open('/proc/mounts', 'r') as f:
            mounts = f.readlines()

        seen = set()
        for line in mounts:
            parts = line.split()
            if len(parts) < 3:
                continue
            device, mount, fstype = parts[0], parts[1], parts[2]

            # Skip virtual filesystems
            if fstype in ('sysfs', 'proc', 'devtmpfs', 'devpts', 'tmpfs',
                          'securityfs', 'cgroup', 'cgroup2', 'pstore',
                          'debugfs', 'tracefs', 'fusectl', 'configfs',
                          'hugetlbfs', 'mqueue', 'binfmt_misc', 'autofs',
                          'overlay', 'nsfs', 'bpf'):
                continue

            # Skip duplicates
            if mount in seen:
                continue
            seen.add(mount)

            try:
                st = os.statvfs(mount)
                total = st.f_blocks * st.f_frsize
                free = st.f_bavail * st.f_frsize
                used = total - free
                if total > 0:
                    filesystems.append({
                        'mount': mount,
                        'device': device.split('/')[-1] if '/' in device else device,
                        'fstype': fstype,
                        'total': total,
                        'used': used,
                        'available': free,
                        'percent': round((used / total) * 100, 1)
                    })
            except:
                pass
    except:
        pass

    return filesystems

def get_disk_io():
    """Get disk I/O rates for all block devices"""
    io_stats = []
    try:
        content = read_proc_file('/proc/diskstats')
        for line in content.split('\n'):
            parts = line.split()
            if len(parts) < 14:
                continue

            name = parts[2]
            # Only major disks, not partitions
            if not re.match(r'^(sd[a-z]|vd[a-z]|nvme\d+n\d+|xvd[a-z])$', name):
                continue

            reads = int(parts[3])
            read_sectors = int(parts[5])
            writes = int(parts[7])
            write_sectors = int(parts[9])
            io_time = int(parts[12])  # ms spent doing I/O

            read_bytes = read_sectors * 512
            write_bytes = write_sectors * 512

            read_rate = tracker.update(f'disk_{name}_read', read_bytes)
            write_rate = tracker.update(f'disk_{name}_write', write_bytes)
            io_rate = tracker.update(f'disk_{name}_io', io_time)

            io_stats.append({
                'device': name,
                'read_bytes_sec': round(max(0, read_rate), 1),
                'write_bytes_sec': round(max(0, write_rate), 1),
                'io_percent': round(min(100, max(0, io_rate / 10)), 1),  # io_time is ms per sec
                'reads': reads,
                'writes': writes
            })
    except:
        pass

    return io_stats

def get_network():
    """Get network stats for all interfaces"""
    interfaces = []
    try:
        content = read_proc_file('/proc/net/dev')
        for line in content.split('\n')[2:]:  # Skip headers
            if ':' not in line:
                continue

            parts = line.split(':')
            iface = parts[0].strip()

            # Skip loopback and virtual interfaces
            if iface in ('lo',) or iface.startswith(('veth', 'br-', 'docker')):
                continue

            stats = parts[1].split()
            if len(stats) < 16:
                continue

            rx_bytes = int(stats[0])
            rx_packets = int(stats[1])
            rx_errors = int(stats[2])
            rx_dropped = int(stats[3])
            tx_bytes = int(stats[8])
            tx_packets = int(stats[9])
            tx_errors = int(stats[10])
            tx_dropped = int(stats[11])

            rx_rate = tracker.update(f'net_{iface}_rx', rx_bytes)
            tx_rate = tracker.update(f'net_{iface}_tx', tx_bytes)

            interfaces.append({
                'interface': iface,
                'rx_bytes': rx_bytes,
                'tx_bytes': tx_bytes,
                'rx_bytes_sec': round(max(0, rx_rate), 1),
                'tx_bytes_sec': round(max(0, tx_rate), 1),
                'rx_packets': rx_packets,
                'tx_packets': tx_packets,
                'rx_errors': rx_errors + rx_dropped,
                'tx_errors': tx_errors + tx_dropped
            })
    except:
        pass

    return interfaces

def get_tcp_connections():
    """Get TCP connection stats from /proc/net/tcp and tcp6"""
    states = {
        '01': 'established', '02': 'syn_sent', '03': 'syn_recv',
        '04': 'fin_wait1', '05': 'fin_wait2', '06': 'time_wait',
        '07': 'close', '08': 'close_wait', '09': 'last_ack',
        '0A': 'listen', '0B': 'closing'
    }

    counts = {s: 0 for s in states.values()}
    counts['total'] = 0

    for tcp_file in ('/proc/net/tcp', '/proc/net/tcp6'):
        try:
            content = read_proc_file(tcp_file)
            for line in content.split('\n')[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    state = parts[3].upper()
                    counts['total'] += 1
                    state_name = states.get(state, 'other')
                    if state_name in counts:
                        counts[state_name] += 1
        except:
            pass

    return counts

def get_load():
    """Get load averages and process counts"""
    try:
        content = read_proc_file('/proc/loadavg')
        parts = content.split()
        running, total = parts[3].split('/')
        return {
            'load1': float(parts[0]),
            'load5': float(parts[1]),
            'load15': float(parts[2]),
            'processes_running': int(running),
            'processes_total': int(total)
        }
    except:
        return {'load1': 0, 'load5': 0, 'load15': 0}

def get_file_descriptors():
    """Get file descriptor usage"""
    try:
        content = read_proc_file('/proc/sys/fs/file-nr')
        parts = content.split()
        allocated = int(parts[0])
        max_fds = int(parts[2])
        return {
            'allocated': allocated,
            'max': max_fds,
            'percent': round((allocated / max_fds) * 100, 2) if max_fds > 0 else 0
        }
    except:
        return None

def get_entropy():
    """Get available entropy"""
    try:
        content = read_proc_file('/proc/sys/kernel/random/entropy_avail')
        return int(content.strip())
    except:
        return None

def get_top_processes(n=10):
    """Get top processes by reading /proc directly (no subprocess)"""
    processes = []
    page_size = os.sysconf('SC_PAGE_SIZE')
    clock_ticks = os.sysconf('SC_CLK_TCK')

    # Get total system uptime for CPU calculation
    try:
        with open('/proc/uptime', 'r') as f:
            uptime = float(f.read().split()[0])
    except:
        return []

    try:
        pids = [p for p in os.listdir('/proc') if p.isdigit()]
        proc_data = []

        for pid in pids:
            try:
                # Read stat for CPU info
                with open(f'/proc/{pid}/stat', 'r') as f:
                    stat = f.read()

                # Parse stat (handle command names with spaces/parens)
                comm_start = stat.index('(')
                comm_end = stat.rindex(')')
                comm = stat[comm_start+1:comm_end]
                fields = stat[comm_end+2:].split()

                utime = int(fields[11])
                stime = int(fields[12])
                starttime = int(fields[19])
                vsize = int(fields[20])  # Virtual memory
                rss = int(fields[21]) * page_size  # Resident memory

                # Calculate CPU percent
                total_time = utime + stime
                proc_uptime = uptime - (starttime / clock_ticks)
                if proc_uptime > 0:
                    cpu_percent = (total_time / clock_ticks / proc_uptime) * 100
                else:
                    cpu_percent = 0

                proc_data.append({
                    'pid': int(pid),
                    'name': comm[:15],  # Limit name length
                    'cpu': round(cpu_percent, 1),
                    'mem_rss': rss,
                    'mem_virt': vsize
                })
            except:
                continue

        # Sort by CPU and take top n
        proc_data.sort(key=lambda x: x['cpu'], reverse=True)
        processes = proc_data[:n]
    except:
        pass

    return processes

def get_containers():
    """Get running Docker containers via Unix socket"""
    containers = []
    try:
        # Connect to Docker daemon via Unix socket with timeout
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect('/var/run/docker.sock')

        # Send HTTP request to Docker API (only get running containers)
        request = b'GET /containers/json?all=false HTTP/1.1\r\nHost: localhost\r\n\r\n'
        sock.sendall(request)

        # Read response with multiple smaller reads
        response = b''
        sock.settimeout(1)
        for _ in range(100):  # Max 100 chunks
            try:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                response += chunk
                # If we have a complete response, break
                if b'\r\n0\r\n\r\n' in response or len(response) > 50000:
                    break
            except socket.timeout:
                break

        sock.close()

        # Parse HTTP response (skip headers)
        if b'\r\n\r\n' in response:
            headers, body = response.split(b'\r\n\r\n', 1)

            # Handle chunked encoding - look for JSON data
            # The response will have chunk size prefixes like "123\r\n{...}\r\n0\r\n\r\n"
            # We need to extract just the JSON part

            # Find JSON array start
            json_start = body.find(b'[')
            if json_start >= 0:
                # Find matching end bracket with depth tracking
                depth = 0
                json_end = json_start
                for i in range(json_start, min(len(body), json_start + 50000)):  # Limit search
                    if body[i:i+1] == b'[':
                        depth += 1
                    elif body[i:i+1] == b']':
                        depth -= 1
                        if depth == 0:
                            json_end = i + 1
                            break

                json_str = body[json_start:json_end].decode('utf-8')
                data = json.loads(json_str)

                # Parse container data
                for container in data:
                    # Get first name
                    names = container.get('Names', [])
                    if not names:
                        continue
                    name = names[0].lstrip('/')

                    # Get image (shorten if needed)
                    image = container.get('Image', '')
                    if '/' in image:
                        image = image.split('/')[-1]

                    # Get state
                    state = container.get('State', 'unknown')

                    containers.append({
                        'name': name,
                        'status': state,
                        'image': image
                    })
    except Exception as e:
        # On any error, return empty list
        pass

    return containers

def get_recent_logs(max_entries=10):
    """Get recent safe log entries from various sources"""
    import subprocess
    logs = []

    # Docker events (recent container actions - safe, no sensitive info)
    try:
        result = subprocess.run(
            ['docker', 'events', '--since', '5m', '--until', '0s',
             '--format', '{{.Action}} {{.Actor.Attributes.name}}'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            now = datetime.now()
            for line in result.stdout.strip().split('\n')[-5:]:
                if line and ' ' in line:
                    parts = line.split(' ', 1)
                    action = parts[0]
                    name = parts[1] if len(parts) > 1 else ''
                    # Skip exec events (too noisy)
                    if action.startswith('exec_'):
                        continue
                    logs.append({
                        'time': now.strftime('%H:%M:%S'),
                        'level': 'info',
                        'source': 'docker',
                        'message': f"{name} {action}"
                    })
    except:
        pass

    # Caddy access logs - just endpoints, no IPs (from journalctl)
    try:
        result = subprocess.run(
            ['journalctl', '-u', 'caddy', '-n', '20', '--no-pager', '-o', 'cat'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n')[-5:]:
                if '"GET ' in line or '"POST ' in line:
                    # Extract just method, path, and status
                    import re
                    match = re.search(r'"(GET|POST|PUT|DELETE)\s+([^\s"]+)[^"]*"\s+(\d+)', line)
                    if match:
                        method, path, status = match.groups()
                        level = 'success' if status.startswith('2') else 'warn' if status.startswith('4') else 'info'
                        logs.append({
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'level': level,
                            'source': 'caddy',
                            'message': f"{method} {path[:30]} [{status}]"
                        })
    except:
        pass

    # System service events (safe - just service names)
    try:
        result = subprocess.run(
            ['journalctl', '-p', '4', '-n', '10', '--no-pager',
             '-o', 'json', '--output-fields=MESSAGE,_SYSTEMD_UNIT,__REALTIME_TIMESTAMP'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n')[-3:]:
                if line:
                    try:
                        entry = json.loads(line)
                        msg = entry.get('MESSAGE', '')[:50]
                        unit = entry.get('_SYSTEMD_UNIT', 'system')
                        ts = int(entry.get('__REALTIME_TIMESTAMP', 0)) // 1000000
                        time_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts else '--:--:--'
                        # Skip noisy/sensitive entries
                        if any(skip in msg.lower() for skip in ['password', 'key', 'secret', 'token', 'auth']):
                            continue
                        logs.append({
                            'time': time_str,
                            'level': 'warn',
                            'source': unit.replace('.service', '')[:10],
                            'message': msg
                        })
                    except:
                        pass
    except:
        pass

    # SSH logins (successful only - safe)
    try:
        result = subprocess.run(
            ['journalctl', '-u', 'sshd', '-n', '20', '--no-pager', '-o', 'cat'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if 'Accepted' in line:
                    # Extract just user and method, not IP
                    import re
                    match = re.search(r'Accepted (\w+) for (\w+)', line)
                    if match:
                        method, user = match.groups()
                        logs.append({
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'level': 'success',
                            'source': 'ssh',
                            'message': f"Login: {user} via {method}"
                        })
    except:
        pass

    # Sort by time and limit
    return logs[-max_entries:]

def collect_metrics():
    """Collect all metrics efficiently using thread pool"""
    static = get_static_info()

    # Parallel collection for independent metrics
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            'uptime': executor.submit(get_uptime_boot),
            'cpu': executor.submit(get_cpu),
            'cpu_freq': executor.submit(get_cpu_freq),
            'temps': executor.submit(get_temperatures),
            'memory': executor.submit(get_memory),
            'filesystems': executor.submit(get_filesystems),
            'disk_io': executor.submit(get_disk_io),
            'network': executor.submit(get_network),
            'tcp': executor.submit(get_tcp_connections),
            'load': executor.submit(get_load),
            'fds': executor.submit(get_file_descriptors),
            'entropy': executor.submit(get_entropy),
            'processes': executor.submit(get_top_processes),
            'containers': executor.submit(get_containers),
            'logs': executor.submit(get_recent_logs),
        }

        results = {k: v.result() for k, v in futures.items()}

    mem_data = results['memory']

    metrics = {
        'agent_version': AGENT_VERSION,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'hostname': static['hostname'],
        'system': {
            'os': static['os'],
            'arch': static['arch'],
            'cpu_model': static['cpu_model'],
            'cpu_count': static['cpu_count'],
        },
        'uptime': results['uptime'],
        'cpu': results['cpu'],
        'memory': mem_data['memory'],
        'swap': mem_data['swap'],
        'load': results['load'],
        'filesystems': results['filesystems'],
        'disk_io': results['disk_io'],
        'network': results['network'],
        'tcp': results['tcp'],
        'processes': results['processes'],
        'containers': results['containers'],
        'logs': results['logs'],
    }

    # Add optional metrics only if available
    if results['cpu_freq']:
        metrics['cpu_freq'] = results['cpu_freq']
    if results['temps']:
        metrics['temperatures'] = results['temps']
    if results['fds']:
        metrics['file_descriptors'] = results['fds']
    if results['entropy'] is not None:
        metrics['entropy'] = results['entropy']

    return metrics

class MetricsHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        path = self.path.split('?')[0]
        query = self.path.split('?')[1] if '?' in self.path else ''
        compact = 'compact=1' in query or 'compact=true' in query

        if path == '/metrics':
            metrics = collect_metrics()
            if compact:
                body = json.dumps(metrics, separators=(',', ':')).encode()
            else:
                body = json.dumps(metrics, indent=2).encode()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(body))
            self.send_header('Cache-Control', 'no-cache, no-store')
            self.end_headers()
            self.wfile.write(body)

        elif path == '/health':
            body = b'OK'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress access logs

class ThreadedHTTPServer(HTTPServer):
    """Handle each request in a separate thread"""
    def process_request(self, request, client_address):
        thread = Thread(target=self.process_request_thread, args=(request, client_address))
        thread.daemon = True
        thread.start()

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    server = ThreadedHTTPServer(('0.0.0.0', port), MetricsHandler)
    print(f'Metrics agent running on http://0.0.0.0:{port}/metrics')
    print(f'Health check: http://0.0.0.0:{port}/health')
    print(f'Compact mode: http://0.0.0.0:{port}/metrics?compact=1')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.shutdown()
