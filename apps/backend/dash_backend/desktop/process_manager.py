"""Process Manager - Process management for DASH AI OS.

Provides:
- List running processes
- Process information (CPU, memory, I/O)
- Kill/terminate processes
- Start processes
- Monitor process creation/termination
- Resource usage per process
- Process tree view
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a running process.
    
    Attributes:
        pid: Process ID
        name: Process name
        executable: Full executable path
        cmdline: Command line arguments
        status: Process status (running, sleeping, etc.)
        cpu_percent: CPU usage percentage
        memory_percent: Memory usage percentage
        memory_mb: Memory usage in MB
        threads: Number of threads
        handles: Number of handles (Windows)
        open_files: Number of open files
        connections: Number of network connections
        user: Process owner
        created_at: Process start time
        children: Child process IDs
        parent_pid: Parent process ID
    """
    pid: int = 0
    name: str = ""
    executable: str = ""
    cmdline: str = ""
    status: str = "running"
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    threads: int = 0
    handles: int = 0
    open_files: int = 0
    connections: int = 0
    user: str = ""
    created_at: float = 0.0
    children: List[int] = field(default_factory=list)
    parent_pid: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "name": self.name,
            "executable": self.executable,
            "status": self.status,
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_percent": round(self.memory_percent, 1),
            "memory_mb": round(self.memory_mb, 1),
            "threads": self.threads,
            "handles": self.handles,
            "user": self.user,
            "children_count": len(self.children),
        }


class ProcessManager:
    """Manages system processes.
    
    Features:
    - Process enumeration with resource usage
    - Process termination (forceful/graceful)
    - Process launching
    - Process tree navigation
    - Process monitoring
    - Event callbacks for create/terminate
    """
    
    def __init__(self, poll_interval: float = 2.0):
        self._poll_interval = poll_interval
        self._processes: Dict[int, ProcessInfo] = {}
        
        # Event callbacks
        self._created_callbacks: List[Callable] = []
        self._terminated_callbacks: List[Callable] = []
        
        # Monitor task
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        self._stats = {
            "processes_killed": 0,
            "processes_started": 0,
            "total_monitored": 0,
        }
    
    # ── Lifecycle ───────────────────────────────────────────
    
    async def start(self) -> None:
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("ProcessManager started")
    
    async def stop(self) -> None:
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("ProcessManager stopped")
    
    # ── Process Enumeration ─────────────────────────────────
    
    async def list_processes(self, sort_by: str = "cpu",
                              limit: int = 100) -> List[ProcessInfo]:
        """List running processes.
        
        Args:
            sort_by: Sort field (cpu, memory, name, pid)
            limit: Max results
            
        Returns:
            List of ProcessInfo
        """
        processes = await self._get_all_processes()
        
        # Sort
        sort_keys = {
            "cpu": lambda p: p.cpu_percent,
            "memory": lambda p: p.memory_percent,
            "name": lambda p: p.name.lower(),
            "pid": lambda p: p.pid,
        }
        key = sort_keys.get(sort_by, sort_keys["cpu"])
        processes.sort(key=key, reverse=True)
        
        # Cache
        self._processes = {p.pid: p for p in processes}
        self._stats["total_monitored"] = len(processes)
        
        return processes[:limit]
    
    async def get_process(self, pid: int) -> Optional[ProcessInfo]:
        """Get process info by PID.
        
        Args:
            pid: Process ID
            
        Returns:
            ProcessInfo or None
        """
        if pid in self._processes:
            return self._processes[pid]
        
        # Refresh
        await self.list_processes()
        return self._processes.get(pid)
    
    async def find_processes(self, name: Optional[str] = None,
                              user: Optional[str] = None) -> List[ProcessInfo]:
        """Find processes by criteria.
        
        Args:
            name: Filter by name (substring)
            user: Filter by owner
            
        Returns:
            List of matching ProcessInfo
        """
        results = []
        for proc in self._processes.values():
            if name and name.lower() not in proc.name.lower():
                continue
            if user and user.lower() != proc.user.lower():
                continue
            results.append(proc)
        return results
    
    async def get_process_tree(self, pid: int) -> Dict[str, Any]:
        """Get process tree starting from a PID.
        
        Args:
            pid: Root process ID
            
        Returns:
            Process tree dict
        """
        root = await self.get_process(pid)
        if not root:
            return {"error": "Process not found"}
        
        async def build_tree(process_pid: int) -> Dict[str, Any]:
            proc = await self.get_process(process_pid)
            if not proc:
                return {"pid": process_pid, "name": "unknown"}
            
            children = []
            for child_pid in proc.children:
                child_tree = await build_tree(child_pid)
                children.append(child_tree)
            
            return {
                "pid": proc.pid,
                "name": proc.name,
                "cpu": proc.cpu_percent,
                "memory_mb": proc.memory_mb,
                "children": children,
            }
        
        return await build_tree(pid)
    
    # ── Process Control ─────────────────────────────────────
    
    async def kill_process(self, pid: int, force: bool = False) -> bool:
        """Kill a process.
        
        Args:
            pid: Process ID
            force: Force kill (SIGKILL)
            
        Returns:
            True if killed
        """
        import signal
        import os
        
        try:
            if force:
                os.kill(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGTERM)
            
            self._processes.pop(pid, None)
            self._stats["processes_killed"] += 1
            return True
        except ProcessLookupError:
            self._processes.pop(pid, None)
            return True
        except Exception as exc:
            logger.warning("Kill process %d failed: %s", pid, exc)
            return False
    
    async def kill_process_tree(self, pid: int, force: bool = False) -> int:
        """Kill a process and all its children.
        
        Args:
            pid: Root process ID
            force: Force kill
            
        Returns:
            Number of processes killed
        """
        killed = 0
        
        async def kill_recursive(process_pid: int):
            nonlocal killed
            proc = await self.get_process(process_pid)
            if proc:
                for child_pid in proc.children:
                    await kill_recursive(child_pid)
            
            if await self.kill_process(process_pid, force):
                killed += 1
        
        await kill_recursive(pid)
        return killed
    
    async def start_process(self, command: str, args: Optional[List[str]] = None,
                             working_dir: Optional[str] = None,
                             wait: bool = False) -> Optional[int]:
        """Start a new process.
        
        Args:
            command: Executable path
            args: Command line arguments
            working_dir: Working directory
            wait: Wait for completion
            
        Returns:
            PID if started, or None
        """
        import subprocess
        
        try:
            cmd = [command]
            if args:
                cmd.extend(args)
            
            if wait:
                subprocess.run(cmd, cwd=working_dir, timeout=300)
                return None
            else:
                process = subprocess.Popen(
                    cmd,
                    cwd=working_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._stats["processes_started"] += 1
                return process.pid
                
        except Exception as exc:
            logger.warning("Start process failed: %s", exc)
            return None
    
    async def suspend_process(self, pid: int) -> bool:
        """Suspend a process.
        
        Args:
            pid: Process ID
            
        Returns:
            True if suspended
        """
        import signal
        import os
        try:
            os.kill(pid, signal.SIGSTOP)
            return True
        except Exception:
            return False
    
    async def resume_process(self, pid: int) -> bool:
        """Resume a suspended process.
        
        Args:
            pid: Process ID
            
        Returns:
            True if resumed
        """
        import signal
        import os
        try:
            os.kill(pid, signal.SIGCONT)
            return True
        except Exception:
            return False
    
    # ── Process Info ────────────────────────────────────────
    
    async def get_top_processes(self, count: int = 10,
                                  by: str = "cpu") -> List[ProcessInfo]:
        """Get top processes by resource usage.
        
        Args:
            count: Number of processes
            by: Sort by (cpu, memory)
            
        Returns:
            List of ProcessInfo
        """
        return await self.list_processes(sort_by=by, limit=count)
    
    async def get_system_summary(self) -> Dict[str, Any]:
        """Get system process summary.
        
        Returns:
            Dict with process counts and resource usage
        """
        processes = await self.list_processes()
        
        total_cpu = sum(p.cpu_percent for p in processes)
        total_memory = sum(p.memory_mb for p in processes)
        
        return {
            "total_processes": len(processes),
            "total_cpu_percent": round(total_cpu, 1),
            "total_memory_mb": round(total_memory, 1),
            "top_cpu": (await self.get_top_processes(5, "cpu"))[0].name if processes else "",
            "top_memory": (await self.get_top_processes(5, "memory"))[0].name if processes else "",
        }
    
    # ── Monitoring ──────────────────────────────────────────
    
    def on_process_created(self, callback: Callable) -> None:
        self._created_callbacks.append(callback)
    
    def on_process_terminated(self, callback: Callable) -> None:
        self._terminated_callbacks.append(callback)
    
    async def _monitor_loop(self) -> None:
        previous_pids: Set[int] = set()
        
        while self._running:
            try:
                current = await self.list_processes()
                current_pids = {p.pid for p in current}
                
                # Detect new processes
                new_pids = current_pids - previous_pids
                for pid in new_pids:
                    proc = self._processes.get(pid)
                    if proc:
                        for cb in self._created_callbacks:
                            try:
                                cb(proc)
                            except Exception:
                                pass
                
                # Detect terminated processes
                terminated = previous_pids - current_pids
                for pid in terminated:
                    for cb in self._terminated_callbacks:
                        try:
                            cb(pid)
                        except Exception:
                            pass
                
                previous_pids = current_pids
                await asyncio.sleep(self._poll_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Process monitor error: %s", exc)
                await asyncio.sleep(5.0)
    
    async def _get_all_processes(self) -> List[ProcessInfo]:
        """Get all processes with resource info."""
        processes = []
        try:
            import psutil
            
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline',
                                              'status', 'cpu_percent', 'memory_percent',
                                              'memory_info', 'num_threads', 'num_handles',
                                              'open_files', 'connections', 'username',
                                              'create_time', 'children', 'ppid']):
                try:
                    pinfo = proc.info
                    processes.append(ProcessInfo(
                        pid=pinfo['pid'],
                        name=pinfo['name'] or '',
                        executable=pinfo['exe'] or '',
                        cmdline=' '.join(pinfo['cmdline']) if pinfo['cmdline'] else '',
                        status=pinfo['status'] or '',
                        cpu_percent=pinfo['cpu_percent'] or 0.0,
                        memory_percent=pinfo['memory_percent'] or 0.0,
                        memory_mb=(pinfo['memory_info'].rss / (1024 * 1024)) if pinfo['memory_info'] else 0,
                        threads=pinfo['num_threads'] or 0,
                        handles=pinfo['num_handles'] or 0,
                        open_files=len(pinfo['open_files']) if pinfo['open_files'] else 0,
                        connections=len(pinfo['connections']) if pinfo['connections'] else 0,
                        user=pinfo['username'] or '',
                        created_at=pinfo['create_time'] or 0,
                        children=[c.info['pid'] for c in (pinfo['children'] or [])],
                        parent_pid=pinfo['ppid'] or 0,
                    ))
                except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                    continue
                    
        except ImportError:
            logger.debug("psutil not available")
        
        return processes
    
    # ── Stats ───────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        return {**self._stats}


# Global singleton
_process_manager: Optional[ProcessManager] = None


def get_process_manager() -> ProcessManager:
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager()
    return _process_manager
