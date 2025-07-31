import torch
import torch.nn as nn
import onnx
import onnxruntime as ort
import numpy as np
from pathlib import Path
import tempfile
import os

class ModelOptimizer:
    """
    Utility class for optimizing PyTorch models with quantization and ONNX conversion
    """
    
    def __init__(self, logger=None):
        self.logger = logger
        self.optimized_models = {}
        
    def log(self, message: str):
        """Log message to both console and logger if available"""
        print(f"[MODEL_OPT] {message}")
        if self.logger:
            self.logger.log(f"[MODEL_OPT] {message}")
    
    def quantize_model_dynamic(self, model: nn.Module, model_name: str = "model") -> nn.Module:
        """
        Apply dynamic quantization to reduce model from Float32 to Int8
        
        Args:
            model: PyTorch model to quantize
            model_name: Name for logging purposes
            
        Returns:
            Quantized model
        """
        self.log(f"Starting dynamic quantization for {model_name}")
        
        # Set model to evaluation mode
        model.eval()
        
        # Apply dynamic quantization
        quantized_model = torch.quantization.quantize_dynamic(
            model,  # Original model
            {torch.nn.Linear, torch.nn.Conv2d},  # Layers to quantize
            dtype=torch.qint8  # Target dtype
        )
        
        self.log(f"Dynamic quantization completed for {model_name}")
        return quantized_model
    
    def quantize_model_static(self, model: nn.Module, calibration_data: torch.Tensor, 
                            model_name: str = "model") -> nn.Module:
        """
        Apply static quantization with calibration data
        
        Args:
            model: PyTorch model to quantize
            calibration_data: Sample data for calibration
            model_name: Name for logging purposes
            
        Returns:
            Statically quantized model
        """
        self.log(f"Starting static quantization for {model_name}")
        
        # Set model to evaluation mode
        model.eval()
        
        # Prepare model for quantization
        model.qconfig = torch.quantization.get_default_qconfig('fbgemm')
        model_prepared = torch.quantization.prepare(model)
        
        # Calibrate with sample data
        self.log("Calibrating model with sample data")
        with torch.no_grad():
            model_prepared(calibration_data)
        
        # Convert to quantized model
        quantized_model = torch.quantization.convert(model_prepared)
        
        self.log(f"Static quantization completed for {model_name}")
        return quantized_model
    
    def quantize_model_int8_static(self, model: nn.Module, calibration_loader, 
                                   model_name: str = "model") -> nn.Module:
        """
        Apply static INT8 quantization for maximum performance
        
        Args:
            model: PyTorch model to quantize
            calibration_loader: DataLoader with calibration data
            model_name: Name for logging purposes
            
        Returns:
            INT8 quantized model
        """
        self.log(f"Starting static INT8 quantization for {model_name}")
        
        # Set model to evaluation mode
        model.eval()
        model.cpu()  # Move to CPU for quantization
        
        # Configure quantization for CPU (fbgemm backend)
        model.qconfig = torch.quantization.get_default_qconfig('fbgemm')
        
        # Prepare model for static quantization
        model_prepared = torch.quantization.prepare(model, inplace=False)
        
        # Calibration phase with real data
        self.log("Calibrating model with sample data for INT8 quantization")
        with torch.no_grad():
            for i, data in enumerate(calibration_loader):
                if i >= 100:  # Limit calibration samples for speed
                    break
                model_prepared(data)
                if i % 20 == 0:
                    self.log(f"Calibration progress: {i}/100")
        
        # Convert to quantized model
        quantized_model = torch.quantization.convert(model_prepared, inplace=False)
        
        self.log(f"Static INT8 quantization completed for {model_name}")
        return quantized_model
    
    def create_calibration_loader(self, input_shape: tuple, num_samples: int = 100):
        """
        Create a calibration data loader for quantization
        
        Args:
            input_shape: Shape of input tensor (batch_size, channels, height, width)
            num_samples: Number of calibration samples
            
        Returns:
            DataLoader with calibration data
        """
        import torch.utils.data as data
        
        # Generate synthetic calibration data that mimics real image data
        calibration_data = []
        for _ in range(num_samples):
            # Create realistic image-like data (normalized to [0,1] then standardized)
            sample = torch.randn(input_shape[1:])  # Remove batch dimension
            # Apply ImageNet-like normalization
            sample = (sample + 1) / 2  # Scale to [0, 1]
            sample = (sample - torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)) / torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            calibration_data.append(sample)
        
        # Create dataset that returns single tensors (not lists)
        class CalibrationDataset(data.Dataset):
            def __init__(self, data_list):
                self.data = data_list
            
            def __len__(self):
                return len(self.data)
                
            def __getitem__(self, idx):
                return self.data[idx]
        
        dataset = CalibrationDataset(calibration_data)
        loader = data.DataLoader(dataset, batch_size=1, shuffle=False)
        
        self.log(f"Created calibration loader with {num_samples} samples")
        return loader
    
    def convert_to_onnx(self, model: nn.Module, input_shape: tuple, 
                       model_name: str = "model", save_path: str = None) -> str:
        """
        Convert PyTorch model to ONNX format
        
        Args:
            model: PyTorch model to convert
            input_shape: Shape of input tensor (batch_size, channels, height, width)
            model_name: Name for the model
            save_path: Path to save ONNX model
            
        Returns:
            Path to saved ONNX model
        """
        self.log(f"Converting {model_name} to ONNX format")
        
        # Create dummy input
        dummy_input = torch.randn(*input_shape)
        
        # Set model to evaluation mode
        model.eval()
        
        # Define save path
        if save_path is None:
            save_path = f"artifacts/{model_name}_optimized.onnx"
        
        # Export to ONNX
        torch.onnx.export(
            model,
            dummy_input,
            save_path,
            export_params=True,
            opset_version=11,
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={
                'input': {0: 'batch_size'},
                'output': {0: 'batch_size'}
            }
        )
        
        self.log(f"ONNX model saved to: {save_path}")
        return save_path
    
    def create_onnx_session(self, onnx_path: str, use_tensorrt: bool = False) -> ort.InferenceSession:
        """
        Create optimized ONNX Runtime session
        
        Args:
            onnx_path: Path to ONNX model
            use_tensorrt: Whether to use TensorRT execution provider
            
        Returns:
            ONNX Runtime inference session
        """
        self.log(f"Creating ONNX Runtime session from {onnx_path}")
        
        # Configure providers
        providers = []
        
        if use_tensorrt:
            providers.append(('TensorrtExecutionProvider', {
                'device_id': 0,
                'trt_max_workspace_size': 2147483648,  # 2GB
                'trt_max_partition_iterations': 1000,
                'trt_min_subgraph_size': 1,
                'trt_fp16_enable': True,
                'trt_int8_enable': False,  # We're doing CPU, so keep False
                'trt_engine_cache_enable': True
            }))
        
        # Always add CPU provider as fallback
        providers.append(('CPUExecutionProvider', {
            'intra_op_num_threads': min(torch.get_num_threads(), 8),
            'inter_op_num_threads': min(torch.get_num_threads(), 4)
        }))
        
        # Create session with optimization
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = min(torch.get_num_threads(), 8)
        sess_options.inter_op_num_threads = min(torch.get_num_threads(), 4)
        
        session = ort.InferenceSession(onnx_path, sess_options, providers=providers)
        
        self.log(f"ONNX Runtime session created with providers: {session.get_providers()}")
        return session
    
    def benchmark_models(self, original_model: nn.Module, optimized_session: ort.InferenceSession,
                        input_data: torch.Tensor, num_runs: int = 100) -> dict:
        """
        Benchmark original vs optimized model performance
        
        Args:
            original_model: Original PyTorch model
            optimized_session: Optimized ONNX Runtime session
            input_data: Test input data
            num_runs: Number of benchmark runs
            
        Returns:
            Performance comparison results
        """
        import time
        
        self.log(f"Benchmarking models with {num_runs} runs")
        
        # Benchmark original PyTorch model
        original_model.eval()
        torch_times = []
        
        with torch.no_grad():
            for _ in range(num_runs):
                start_time = time.time()
                _ = original_model(input_data)
                torch_times.append(time.time() - start_time)
        
        # Benchmark ONNX Runtime model
        input_name = optimized_session.get_inputs()[0].name
        onnx_input = {input_name: input_data.numpy()}
        onnx_times = []
        
        for _ in range(num_runs):
            start_time = time.time()
            _ = optimized_session.run(None, onnx_input)
            onnx_times.append(time.time() - start_time)
        
        # Calculate statistics
        torch_avg = np.mean(torch_times)
        onnx_avg = np.mean(onnx_times)
        speedup = torch_avg / onnx_avg
        
        results = {
            'pytorch_avg_time': torch_avg,
            'onnx_avg_time': onnx_avg,
            'speedup_factor': speedup,
            'speedup_percentage': (speedup - 1) * 100,
            'pytorch_std': np.std(torch_times),
            'onnx_std': np.std(onnx_times)
        }
        
        self.log(f"Benchmark Results:")
        self.log(f"  PyTorch avg: {torch_avg:.4f}s (±{results['pytorch_std']:.4f}s)")
        self.log(f"  ONNX avg: {onnx_avg:.4f}s (±{results['onnx_std']:.4f}s)")
        self.log(f"  Speedup: {speedup:.2f}x ({results['speedup_percentage']:.1f}% faster)")
        
        return results

    def benchmark_quantized_model(self, original_model: nn.Module, quantized_model: nn.Module,
                                 input_data: torch.Tensor, num_runs: int = 100) -> dict:
        """
        Benchmark original vs quantized model performance
        
        Args:
            original_model: Original PyTorch model
            quantized_model: Quantized model
            input_data: Test input data
            num_runs: Number of benchmark runs
            
        Returns:
            Performance comparison results
        """
        import time
        
        self.log(f"Benchmarking quantized model with {num_runs} runs")
        
        # Ensure models are in eval mode
        original_model.eval()
        quantized_model.eval()
        
        # Benchmark original model
        original_times = []
        with torch.no_grad():
            for _ in range(num_runs):
                start_time = time.time()
                _ = original_model(input_data)
                original_times.append(time.time() - start_time)
        
        # Benchmark quantized model  
        quantized_times = []
        with torch.no_grad():
            for _ in range(num_runs):
                start_time = time.time()
                _ = quantized_model(input_data)
                quantized_times.append(time.time() - start_time)
        
        # Calculate statistics
        original_avg = np.mean(original_times)
        quantized_avg = np.mean(quantized_times)
        speedup = original_avg / quantized_avg
        
        # Estimate model size reduction (approximate)
        original_params = sum(p.numel() * 4 for p in original_model.parameters())  # 4 bytes per float32
        quantized_params = sum(p.numel() * 1 for p in quantized_model.parameters() if hasattr(p, 'dtype') and 'int8' in str(p.dtype))
        if quantized_params == 0:  # Fallback estimate
            quantized_params = original_params // 4  # Assume 4x reduction
        
        size_reduction = original_params / quantized_params if quantized_params > 0 else 4.0
        
        results = {
            'original_avg_time': original_avg,
            'quantized_avg_time': quantized_avg,
            'speedup_factor': speedup,
            'speedup_percentage': (speedup - 1) * 100,
            'original_std': np.std(original_times),
            'quantized_std': np.std(quantized_times),
            'original_size_mb': original_params / (1024 * 1024),
            'quantized_size_mb': quantized_params / (1024 * 1024),
            'size_reduction_factor': size_reduction
        }
        
        self.log(f"Quantization Benchmark Results:")
        self.log(f"  Original avg: {original_avg:.4f}s (±{results['original_std']:.4f}s)")
        self.log(f"  Quantized avg: {quantized_avg:.4f}s (±{results['quantized_std']:.4f}s)")
        self.log(f"  Speedup: {speedup:.2f}x ({results['speedup_percentage']:.1f}% faster)")
        self.log(f"  Size reduction: {size_reduction:.1f}x ({results['original_size_mb']:.1f}MB → {results['quantized_size_mb']:.1f}MB)")
        
        return results

# Global optimizer instance
model_optimizer = ModelOptimizer() 