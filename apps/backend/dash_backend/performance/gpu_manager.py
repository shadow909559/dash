"""GPU Manager - GPU detection and model optimization."""

from __future__ import annotations

import asyncio
import logging
import platform
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """Information about a GPU."""
    name: str
    vendor: str
    memory_total_mb: int
    memory_free_mb: int
    compute_capability: str
    is_available: bool
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "memory_total_mb": self.memory_total_mb,
            "memory_free_mb": self.memory_free_mb,
            "compute_capability": self.compute_capability,
            "is_available": self.is_available,
        }


class GPUManager:
    """Manages GPU detection and model optimization.
    
    Features:
    - GPU detection (NVIDIA, AMD, Apple Silicon)
    - Memory monitoring
    - Model recommendation based on GPU
    - Background model loading
    - Model reuse
    """
    
    def __init__(self):
        self._gpu_info: Optional[GPUInfo] = None
        self._loaded_models: Dict[str, Any] = {}
        self._loading_tasks: Dict[str, asyncio.Task] = {}
        self._detected = False
        
    async def detect_gpu(self) -> Optional[GPUInfo]:
        """Detect available GPU."""
        if self._detected:
            return self._gpu_info
        
        self._detected = True
        
        # Try NVIDIA
        nvidia_info = await self._detect_nvidia()
        if nvidia_info:
            self._gpu_info = nvidia_info
            logger.info("Detected NVIDIA GPU: %s", nvidia_info.name)
            return nvidia_info
        
        # Try AMD
        amd_info = await self._detect_amd()
        if amd_info:
            self._gpu_info = amd_info
            logger.info("Detected AMD GPU: %s", amd_info.name)
            return amd_info
        
        # Try Apple Silicon
        apple_info = await self._detect_apple_silicon()
        if apple_info:
            self._gpu_info = apple_info
            logger.info("Detected Apple Silicon GPU: %s", apple_info.name)
            return apple_info
        
        logger.info("No GPU detected, will use CPU")
        return None
    
    async def _detect_nvidia(self) -> Optional[GPUInfo]:
        """Detect NVIDIA GPU using nvidia-smi."""
        try:
            import subprocess
            
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,compute_cap", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    parts = lines[0].split(',')
                    return GPUInfo(
                        name=parts[0].strip(),
                        vendor="NVIDIA",
                        memory_total_mb=self._parse_memory(parts[1].strip()),
                        memory_free_mb=self._parse_memory(parts[2].strip()),
                        compute_capability=parts[3].strip() if len(parts) > 3 else "",
                        is_available=True,
                    )
        except Exception as e:
            logger.debug("NVIDIA detection failed: %s", e)
        
        return None
    
    async def _detect_amd(self) -> Optional[GPUInfo]:
        """Detect AMD GPU using rocm-smi."""
        try:
            import subprocess
            
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "--showproductname"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            
            if result.returncode == 0:
                # Parse output (simplified)
                return GPUInfo(
                    name="AMD GPU",
                    vendor="AMD",
                    memory_total_mb=8192,  # Placeholder
                    memory_free_mb=8192,
                    compute_capability="",
                    is_available=True,
                )
        except Exception as e:
            logger.debug("AMD detection failed: %s", e)
        
        return None
    
    async def _detect_apple_silicon(self) -> Optional[GPUInfo]:
        """Detect Apple Silicon GPU."""
        if platform.system() != "Darwin":
            return None
        
        try:
            import subprocess
            
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            
            if result.returncode == 0:
                # Check for Apple Silicon GPU
                if "Apple" in result.stdout or "M1" in result.stdout or "M2" in result.stdout or "M3" in result.stdout:
                    return GPUInfo(
                        name="Apple Silicon GPU",
                        vendor="Apple",
                        memory_total_mb=8192,  # Shared memory
                        memory_free_mb=8192,
                        compute_capability="metal",
                        is_available=True,
                    )
        except Exception as e:
            logger.debug("Apple Silicon detection failed: %s", e)
        
        return None
    
    def _parse_memory(self, memory_str: str) -> int:
        """Parse memory string to MB."""
        memory_str = memory_str.strip().upper()
        
        if "GB" in memory_str:
            return int(float(memory_str.replace("GB", "")) * 1024)
        elif "MB" in memory_str:
            return int(memory_str.replace("MB", ""))
        elif "TB" in memory_str:
            return int(float(memory_str.replace("TB", "")) * 1024 * 1024)
        
        return 0
    
    async def recommend_model(self, task_type: str) -> str:
        """Recommend a model based on GPU and task type."""
        gpu = await self.detect_gpu()

        if not gpu:
            # CPU-only - use smaller models
            return "llama3.2:3b"

        # GPU available - recommend based on memory
        if gpu.memory_free_mb < 4000:
            # Low memory GPU
            return "llama3.2:3b"
        elif gpu.memory_free_mb < 8000:
            # Medium memory GPU
            if task_type == "coding":
                return "qwen2.5-coder:7b"
            elif task_type == "reasoning":
                return "deepseek-r1"
            else:
                return "phi4"
        else:
            # High memory GPU
            if task_type == "coding":
                return "qwen2.5-coder:7b"
            elif task_type == "reasoning":
                return "deepseek-r1"
            else:
                return "phi4"
    
    async def load_model_background(self, model_name: str) -> bool:
        """Load a model in the background."""
        if model_name in self._loaded_models:
            return True
        
        if model_name in self._loading_tasks:
            # Already loading
            return False
        
        async def load_task():
            try:
                # Simulate model loading
                # In production, this would call the actual model loader
                await asyncio.sleep(2)  # Simulate loading time
                self._loaded_models[model_name] = {"loaded": True}
                logger.info("Model loaded: %s", model_name)
                return True
            except Exception as e:
                logger.error("Failed to load model %s: %s", model_name, e)
                return False
        
        self._loading_tasks[model_name] = asyncio.create_task(load_task())
        return False
    
    async def is_model_loaded(self, model_name: str) -> bool:
        """Check if a model is loaded."""
        if model_name in self._loaded_models:
            return True
        
        if model_name in self._loading_tasks:
            task = self._loading_tasks[model_name]
            if task.done():
                result = task.result()
                if result:
                    return True
                else:
                    del self._loading_tasks[model_name]
        
        return False
    
    async def unload_model(self, model_name: str) -> bool:
        """Unload a model to free memory."""
        if model_name in self._loaded_models:
            del self._loaded_models[model_name]
            logger.info("Model unloaded: %s", model_name)
            return True
        
        if model_name in self._loading_tasks:
            self._loading_tasks[model_name].cancel()
            del self._loading_tasks[model_name]
            return True
        
        return False
    
    def get_loaded_models(self) -> List[str]:
        """Get list of loaded models."""
        return list(self._loaded_models.keys())
    
    def get_gpu_info(self) -> Optional[GPUInfo]:
        """Get GPU information."""
        return self._gpu_info


_gpu_manager: Optional[GPUManager] = None


def get_gpu_manager() -> GPUManager:
    global _gpu_manager
    if _gpu_manager is None:
        _gpu_manager = GPUManager()
    return _gpu_manager
